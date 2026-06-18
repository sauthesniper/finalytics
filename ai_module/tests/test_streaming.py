"""
Tests for the SSE streaming endpoints (US9, US13, US14 streaming).

The LLM is unavailable in CI, so these exercise the deterministic
fallback streaming path and assert the SSE event protocol.
"""
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app
from tests.fixtures import HEALTHY_BUNDLE, RISKY_BUNDLE

client = TestClient(app)


@pytest.fixture(autouse=True)
def patch_aggregate(monkeypatch):
    def fake_aggregate(cui, company_name):
        return RISKY_BUNDLE if cui == RISKY_BUNDLE["cui"] else HEALTHY_BUNDLE
    monkeypatch.setattr(main_module, "aggregate", fake_aggregate)


def _collect(path, body):
    with client.stream("POST", path, json=body) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        return "".join(r.iter_text())


def test_analyze_stream_protocol():
    raw = _collect("/analyze/stream", {"cui": "14388248"})
    # Required SSE events in order-ish
    for ev in ("event: status", "event: score",
               "event: risk_start", "event: risk_delta", "event: risk_end",
               "event: sales_start", "event: sales_delta", "event: sales_end",
               "event: done"):
        assert ev in raw, f"missing {ev}"


def test_analyze_stream_has_score_payload():
    raw = _collect("/analyze/stream", {"cui": "14388248"})
    assert '"band"' in raw
    assert '"score"' in raw


def test_ask_stream_protocol():
    raw = _collect("/ask/stream", {"cui": "14388248", "question": "Este activa?"})
    assert "event: start" in raw
    assert "event: delta" in raw
    assert "event: done" in raw


def test_ask_stream_requires_question():
    r = client.post("/ask/stream", json={"cui": "14388248", "question": "  "})
    assert r.status_code == 400


def test_stream_delta_carries_text():
    raw = _collect("/ask/stream", {"cui": "14388248", "question": "test"})
    # At least one delta event should carry a non-empty token
    assert '"t":' in raw
