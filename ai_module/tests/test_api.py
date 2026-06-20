"""
API integration tests for the AI module.

Network calls to other services are monkeypatched so the tests run
hermetically in CI.
"""
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from tests.fixtures import HEALTHY_BUNDLE, RISKY_BUNDLE

client = TestClient(app)


@pytest.fixture(autouse=True)
def patch_aggregate(monkeypatch):
    """Return a fixture bundle based on the requested CUI."""
    def fake_aggregate(cui, company_name):
        base = RISKY_BUNDLE if cui == RISKY_BUNDLE["cui"] else HEALTHY_BUNDLE
        # Return a fresh copy: endpoints may attach documents to the bundle,
        # and we must not mutate the shared fixture across tests.
        return dict(base)
    # Patch the symbol imported into main
    monkeypatch.setattr(main_module, "aggregate", fake_aggregate)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "ai-module"


def test_score_endpoint():
    r = client.post("/score", json={"cui": "14388248"})
    assert r.status_code == 200
    body = r.json()
    assert body["band"] == "healthy"
    assert len(body["pillars"]) == 5


def test_score_requires_ref():
    r = client.post("/score", json={})
    assert r.status_code == 400


def test_risk_agent_endpoint():
    r = client.post("/agent/risk", json={"cui": "49068564"})
    assert r.status_code == 200
    assert r.json()["agent"] == "risk_analyst"


def test_sales_agent_endpoint():
    r = client.post("/agent/sales", json={"cui": "14388248"})
    assert r.status_code == 200
    assert r.json()["agent"] == "sales_strategist"


def test_ask_endpoint():
    r = client.post("/ask", json={"cui": "14388248", "question": "Este activa?"})
    assert r.status_code == 200
    assert r.json()["answer"]


def test_ask_requires_question():
    r = client.post("/ask", json={"cui": "14388248", "question": "  "})
    assert r.status_code == 400


def test_ask_accepts_user_documents():
    r = client.post("/ask", json={
        "cui": "14388248",
        "question": "Ce termen de plata are contractul?",
        "documents": [{"name": "contract.txt", "content": "Termen de plata 90 de zile."}],
    })
    assert r.status_code == 200
    assert r.json()["answer"]


def test_analyze_accepts_user_documents():
    r = client.post("/analyze", json={
        "cui": "14388248",
        "documents": [{"name": "note.txt", "content": "Plati intarziate in trecut."}],
    })
    assert r.status_code == 200
    assert "risk_analyst" in r.json()


def test_analyze_endpoint():
    r = client.post("/analyze", json={"cui": "14388248"})
    assert r.status_code == 200
    body = r.json()
    assert "score" in body and "risk_analyst" in body and "sales_strategist" in body


def test_compare_endpoint():
    r = client.post("/compare", json={"companies": [
        {"cui": "14388248"}, {"cui": "49068564"}
    ]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    # healthy company must rank first
    assert body["items"][0]["score"] >= body["items"][1]["score"]


def test_compare_needs_two():
    r = client.post("/compare", json={"companies": [{"cui": "14388248"}]})
    assert r.status_code == 422  # pydantic min_length


def test_web_research_endpoint(monkeypatch):
    import app.agents.web_research as wr
    monkeypatch.setattr(wr, "llm_available", lambda: False)  # hermetic: no live LLM
    monkeypatch.setattr(main_module, "aggregate_light", lambda c, n: dict(HEALTHY_BUNDLE))
    r = client.post("/agent/web-research", json={"cui": "14388248"})
    assert r.status_code == 200
    body = r.json()
    assert body["agent"] == "web_research"
    assert "steps" in body
    # HEALTHY_BUNDLE has a serp website -> fallback surfaces it
    assert body["website"] == "https://internetteam.ro"


def test_web_research_stream_endpoint(monkeypatch):
    import app.agents.web_research as wr
    monkeypatch.setattr(wr, "llm_available", lambda: False)
    monkeypatch.setattr(main_module, "aggregate_light", lambda c, n: dict(HEALTHY_BUNDLE))
    r = client.post("/agent/web-research/stream", json={"cui": "14388248"})
    assert r.status_code == 200
    # SSE stream must contain the start and answer events.
    assert "event: start" in r.text
    assert "event: answer" in r.text
    assert "event: done" in r.text
