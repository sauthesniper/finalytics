"""
Tests for feedback (US10), alerts (US6), history (US5), compare (US7)
and export (US11). Integration calls to the AI module are monkeypatched.
"""
import pytest

import main as main_module


FAKE_SCORE = {
    "cui": "14388248",
    "company_name": "INTERNET TEAM SRL",
    "score": 82,
    "band": "healthy",
    "pillars": [{"key": "legal_fiscal", "label": "Legal", "score": 95, "weight": 0.3, "reasons": ["ok"]}],
    "positives": ["Firmă activă (+10)"],
    "negatives": [],
    "missing_data": [],
}

FAKE_ANALYSIS = {
    "score": FAKE_SCORE,
    "risk_analyst": {"agent": "risk_analyst", "summary": "Risc scăzut.", "bullets": ["ok"], "used_llm": False, "model": "x"},
    "sales_strategist": {"agent": "sales_strategist", "summary": "Parteneriat.", "bullets": ["ok"], "used_llm": False, "model": "x"},
}


@pytest.fixture(autouse=True)
def patch_integrations(monkeypatch):
    monkeypatch.setattr(main_module.integrations, "get_score", lambda cui, name: dict(FAKE_SCORE))
    monkeypatch.setattr(main_module.integrations, "get_full_analysis", lambda cui, name: dict(FAKE_ANALYSIS))
    monkeypatch.setattr(main_module.integrations, "get_compare", lambda companies: {
        "items": [], "ranking": ["INTERNET TEAM SRL"], "recommendation": "ok"
    })


# ── Feedback ──────────────────────────────────────────────────────────────

def test_add_and_get_feedback(client, auth_headers):
    r = client.post("/feedback", json={"cui": "14388248", "rating": 5, "comment": "great"},
                    headers=auth_headers)
    assert r.status_code == 200

    r2 = client.get("/feedback/14388248")
    assert r2.status_code == 200
    body = r2.json()
    assert body["count"] >= 1
    assert body["average_rating"] is not None


def test_feedback_invalid_rating(client, auth_headers):
    r = client.post("/feedback", json={"cui": "1", "rating": 9}, headers=auth_headers)
    assert r.status_code == 400


def test_feedback_requires_auth(client):
    assert client.post("/feedback", json={"cui": "1", "rating": 5}).status_code == 401


# ── Alerts ────────────────────────────────────────────────────────────────

def test_track_and_list_alerts(client, auth_headers):
    r = client.post("/alerts/track", json={"cui": "14388248", "company_name": "INTERNET TEAM SRL"},
                    headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["tracked"]["baseline_score"] == 82

    r2 = client.get("/alerts", headers=auth_headers)
    assert r2.status_code == 200
    assert len(r2.json()["tracked"]) == 1


def test_check_alerts_detects_change(client, auth_headers, monkeypatch):
    client.post("/alerts/track", json={"cui": "14388248"}, headers=auth_headers)
    # Now simulate a worsened score
    worsened = dict(FAKE_SCORE)
    worsened["score"] = 30
    worsened["band"] = "high_risk"
    monkeypatch.setattr(main_module.integrations, "get_score", lambda cui, name: dict(worsened))

    r = client.post("/alerts/check", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["changes"]
    assert body["changes"][0]["direction"] == "worsened"


def test_untrack(client, auth_headers):
    client.post("/alerts/track", json={"cui": "999"}, headers=auth_headers)
    r = client.delete("/alerts/999", headers=auth_headers)
    assert r.status_code == 200


# ── History ───────────────────────────────────────────────────────────────

def test_history_after_track(client, auth_headers):
    client.post("/alerts/track", json={"cui": "14388248"}, headers=auth_headers)
    r = client.get("/history/14388248")
    assert r.status_code == 200
    assert len(r.json()["snapshots"]) >= 1


# ── Compare ───────────────────────────────────────────────────────────────

def test_compare_requires_two(client, auth_headers):
    r = client.post("/compare", json={"companies": [{"cui": "1"}]}, headers=auth_headers)
    assert r.status_code == 400


def test_compare_ok(client, auth_headers):
    r = client.post("/compare", json={"companies": [{"cui": "1"}, {"cui": "2"}]},
                    headers=auth_headers)
    assert r.status_code == 200
    assert "ranking" in r.json()


# ── Export ────────────────────────────────────────────────────────────────

def test_export_json(client, auth_headers):
    r = client.post("/export", json={"cui": "14388248", "format": "json"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["collaboration_score"]["score"] == 82


def test_export_pdf(client, auth_headers):
    r = client.post("/export", json={"cui": "14388248", "format": "pdf"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_export_requires_ref(client, auth_headers):
    r = client.post("/export", json={"format": "json"}, headers=auth_headers)
    assert r.status_code == 400
