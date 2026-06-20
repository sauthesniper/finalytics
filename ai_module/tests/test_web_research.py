"""
Evals for the agentic Web Research Agent.

Covers both paths:
  - deterministic fallback (no LLM) — must always emit a trace + answer,
  - the ReAct loop with a mocked LLM that calls tools then finishes,
  - the tool implementations (search proxy + page verification).
"""
import json

import app.agents.web_research as wr


# ─── Fake OpenAI tool-calling message objects ─────────────────────────────────

class _FakeFn:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, id, name, arguments):
        self.id = id
        self.type = "function"
        self.function = _FakeFn(name, arguments)


class _FakeMsg:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


HEALTHY_BUNDLE = {
    "cui": "14388248",
    "company_name": "INTERNET TEAM SRL",
    "anaf": {"adresa": "Bucuresti", "cod_CAEN": "6201"},
    "serp": {"status": "found", "website": "https://internetteam.ro",
             "confidence": 0.8, "alternatives": [
                 {"domain": "internetteam.ro", "url": "https://internetteam.ro"}]},
}


# ─── Fallback path (no LLM) ───────────────────────────────────────────────────

def test_fallback_uses_serp_when_no_llm(monkeypatch):
    monkeypatch.setattr(wr, "llm_available", lambda: False)
    out = wr.run_web_research(HEALTHY_BUNDLE)
    assert out["agent"] == "web_research"
    assert out["used_llm"] is False
    assert out["website"] == "https://internetteam.ro"
    # The trace must show an active search step (so the UI can render it).
    assert any(s["type"] == "tool_call" for s in out["steps"])


def test_fallback_not_found(monkeypatch):
    monkeypatch.setattr(wr, "llm_available", lambda: False)
    bundle = {"cui": "999", "company_name": "INEXISTENTA SRL",
              "serp": {"status": "not_found", "alternatives": []}}
    out = wr.run_web_research(bundle)
    assert out["website"] is None
    assert out["confidence"] == 0.0


# ─── Agentic loop with a mocked LLM ───────────────────────────────────────────

def test_agentic_loop_searches_then_finishes(monkeypatch):
    monkeypatch.setattr(wr, "llm_available", lambda: True)

    calls = {"n": 0}

    def fake_chat_with_tools(messages, tools, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeMsg(
                content="Caut firma pe web.",
                tool_calls=[_FakeToolCall("c1", "search_web",
                                          json.dumps({"query": "INTERNET TEAM SRL Romania"}))],
            ), True
        return _FakeMsg(
            content=None,
            tool_calls=[_FakeToolCall("c2", "finish",
                                      json.dumps({"website": "https://internetteam.ro",
                                                  "confidence": 0.9,
                                                  "summary": "Website oficial confirmat."}))],
        ), True

    monkeypatch.setattr(wr, "chat_with_tools", fake_chat_with_tools)
    monkeypatch.setattr(wr, "_tool_search_web",
                        lambda q: [{"title": "Internet Team", "url": "https://internetteam.ro"}])

    events = list(wr.run_web_research_stream(HEALTHY_BUNDLE))
    types = [e["type"] for e in events]
    assert types[0] == "start" and events[0]["used_llm"] is True
    assert "tool_call" in types and "tool_result" in types
    assert events[-1]["type"] == "answer"
    assert events[-1]["website"] == "https://internetteam.ro"
    assert events[-1]["confidence"] == 0.9


def test_loop_stops_after_max_steps(monkeypatch):
    monkeypatch.setattr(wr, "llm_available", lambda: True)
    # LLM always searches, never finishes -> must terminate at MAX_STEPS.
    monkeypatch.setattr(wr, "chat_with_tools", lambda m, t, **k: (
        _FakeMsg(tool_calls=[_FakeToolCall("c", "search_web", json.dumps({"query": "x"}))]), True))
    monkeypatch.setattr(wr, "_tool_search_web", lambda q: [])
    events = list(wr.run_web_research_stream(HEALTHY_BUNDLE))
    assert events[-1]["type"] == "answer"
    # Bounded number of search calls.
    assert sum(1 for e in events if e.get("tool") == "search_web" and e["type"] == "tool_call") <= wr.MAX_STEPS


def test_llm_failure_falls_back(monkeypatch):
    monkeypatch.setattr(wr, "llm_available", lambda: True)
    monkeypatch.setattr(wr, "chat_with_tools", lambda m, t, **k: (None, False))
    out = wr.run_web_research(HEALTHY_BUNDLE)
    assert out["website"] == "https://internetteam.ro"  # fell back to serp data


# ─── Tools ────────────────────────────────────────────────────────────────────

def test_strip_html_removes_tags_and_scripts():
    html = "<html><script>var x=1</script><body><h1>INTERNET TEAM</h1></body></html>"
    text = wr._strip_html(html)
    assert "INTERNET TEAM" in text
    assert "var x" not in text
    assert "<" not in text


def test_fetch_page_verifies_company_name(monkeypatch):
    class _Resp:
        status_code = 200
        text = "<html><body>Bine ați venit la INTERNET TEAM SRL</body></html>"
        def raise_for_status(self): pass

    monkeypatch.setattr(wr.requests, "get", lambda *a, **k: _Resp())
    page = wr._tool_fetch_page("https://internetteam.ro", "INTERNET TEAM SRL", "14388248")
    assert page["ok"] is True
    assert page["verified"] is True


def test_fetch_page_rejects_bad_url():
    page = wr._tool_fetch_page("ftp://x", "X", None)
    assert page["ok"] is False
    assert page["verified"] is False


# ─── Light aggregation (perf: agent must not trigger the heavy intel scrape) ──

def test_aggregate_light_only_calls_anaf(monkeypatch):
    import app.aggregator as agg

    calls = {"anaf": 0}

    def fake_anaf(cui):
        calls["anaf"] += 1
        return {"denumire": "X SRL", "adresa": "Bucuresti", "cod_CAEN": "6201"}

    def boom(*a, **k):
        raise AssertionError("heavy service must not be called by aggregate_light")

    monkeypatch.setattr(agg, "_fetch_anaf", fake_anaf)
    monkeypatch.setattr(agg, "_fetch_intel", boom)
    monkeypatch.setattr(agg, "_fetch_serp", boom)

    bundle = agg.aggregate_light("14388248", None)
    assert bundle["company_name"] == "X SRL"     # name filled from ANAF
    assert bundle["anaf"]["adresa"] == "Bucuresti"
    assert calls["anaf"] == 1
    assert bundle["serp"] is None                # no SERP discovery
    assert "intel" not in bundle["sources"]      # no intel scrape
