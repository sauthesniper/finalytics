"""Unit tests for the Collaboration Health Score engine (US3, US4)."""
from app.scoring import compute_score, WEIGHTS
from tests.fixtures import HEALTHY_BUNDLE, RISKY_BUNDLE, SPARSE_BUNDLE


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_healthy_company_scores_high():
    result = compute_score(HEALTHY_BUNDLE)
    assert result["score"] >= 70
    assert result["band"] == "healthy"


def test_risky_company_scores_low():
    result = compute_score(RISKY_BUNDLE)
    assert result["score"] < 40
    assert result["band"] == "high_risk"


def test_healthy_beats_risky():
    healthy = compute_score(HEALTHY_BUNDLE)
    risky = compute_score(RISKY_BUNDLE)
    assert healthy["score"] > risky["score"]


def test_score_bounded_0_100():
    for bundle in (HEALTHY_BUNDLE, RISKY_BUNDLE, SPARSE_BUNDLE):
        result = compute_score(bundle)
        assert 0 <= result["score"] <= 100


def test_explainability_present():
    result = compute_score(RISKY_BUNDLE)
    # US4: every score must come with pillars and reasons
    assert len(result["pillars"]) == len(WEIGHTS)
    for pillar in result["pillars"]:
        assert pillar["reasons"], f"pillar {pillar['key']} has no reasons"
    # bankruptcy must show up as a negative
    joined = " ".join(result["negatives"]).lower()
    assert "faliment" in joined


def test_missing_data_flagged():
    result = compute_score(SPARSE_BUNDLE)
    # intel + serp missing -> insolvency pillar marked unavailable
    assert any("insolven" in m.lower() for m in result["missing_data"])


def test_inactive_company_penalized():
    result = compute_score(RISKY_BUNDLE)
    legal = next(p for p in result["pillars"] if p["key"] == "legal_fiscal")
    assert legal["score"] < 50
