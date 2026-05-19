"""
Agent eval tests (US13, US14, US9).

These run against the deterministic fallback path (no live LLM needed in
CI) and assert that agent outputs are grounded in the input data and
appropriate for the company's risk band. This is the "eval" harness the
SOW asks for.
"""
from app.scoring import compute_score
from app.agents.risk_analyst import run_risk_analyst
from app.agents.sales_strategist import run_sales_strategist
from app.agents.qa_agent import run_qa
from tests.fixtures import HEALTHY_BUNDLE, RISKY_BUNDLE


def test_risk_agent_structure():
    sc = compute_score(RISKY_BUNDLE)
    out = run_risk_analyst(RISKY_BUNDLE, sc)
    assert out["agent"] == "risk_analyst"
    assert out["summary"]
    assert isinstance(out["bullets"], list)
    assert "model" in out


def test_risk_agent_grounded_on_risky_company():
    sc = compute_score(RISKY_BUNDLE)
    out = run_risk_analyst(RISKY_BUNDLE, sc)
    text = (out["summary"] + " " + " ".join(out["bullets"])).lower()
    # Should reference the actual risk, not a generic safe message
    assert "risc ridicat" in text or "faliment" in text


def test_sales_agent_adapts_to_risk_band():
    # High risk -> advance payment guidance
    risky_sc = compute_score(RISKY_BUNDLE)
    risky_out = run_sales_strategist(RISKY_BUNDLE, risky_sc)
    risky_text = (risky_out["summary"] + " " + " ".join(risky_out["bullets"])).lower()
    assert "avans" in risky_text or "garanți" in risky_text

    # Healthy -> standard terms / long-term partnership
    healthy_sc = compute_score(HEALTHY_BUNDLE)
    healthy_out = run_sales_strategist(HEALTHY_BUNDLE, healthy_sc)
    healthy_text = (healthy_out["summary"] + " " + " ".join(healthy_out["bullets"])).lower()
    assert "termen" in healthy_text or "parteneriat" in healthy_text


def test_sales_agent_recommendations_differ_by_band():
    risky_out = run_sales_strategist(RISKY_BUNDLE, compute_score(RISKY_BUNDLE))
    healthy_out = run_sales_strategist(HEALTHY_BUNDLE, compute_score(HEALTHY_BUNDLE))
    assert risky_out["summary"] != healthy_out["summary"]


def test_qa_agent_returns_answer():
    sc = compute_score(HEALTHY_BUNDLE)
    out = run_qa(HEALTHY_BUNDLE, sc, "Este firma activa?")
    assert out["answer"]
    assert "model" in out


def test_qa_fallback_mentions_score():
    # Without an LLM, the fallback should still surface the score.
    sc = compute_score(HEALTHY_BUNDLE)
    out = run_qa(HEALTHY_BUNDLE, sc, "orice intrebare")
    if not out["used_llm"]:
        assert str(sc["score"]) in out["answer"]
