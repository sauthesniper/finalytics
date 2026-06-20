"""
Tests for user-provided documents added to the grounding context.

The agents (Risk, Sales, Q&A) all build their prompt from
build_context(); attaching documents must surface them in that context
so the LLM can use them, while staying bounded in size.
"""
from app.scoring import compute_score
from app.agents.context import build_context, MAX_DOC_CHARS
from tests.fixtures import HEALTHY_BUNDLE


def test_context_includes_user_documents():
    bundle = dict(HEALTHY_BUNDLE)
    bundle["user_documents"] = [
        {"name": "contract.txt", "content": "Termen de plata: 90 de zile calendaristice."}
    ]
    ctx = build_context(bundle, compute_score(bundle))
    assert "DOCUMENTE FURNIZATE" in ctx
    assert "contract.txt" in ctx
    assert "90 de zile" in ctx


def test_context_truncates_long_documents():
    bundle = dict(HEALTHY_BUNDLE)
    bundle["user_documents"] = [{"name": "big.txt", "content": "x" * 10000}]
    ctx = build_context(bundle, compute_score(bundle))
    # The document body must be capped: no run longer than MAX_DOC_CHARS,
    # and the full 10k blob must not be present.
    assert ("x" * (MAX_DOC_CHARS + 1)) not in ctx
    assert ("x" * (MAX_DOC_CHARS - 10)) in ctx


def test_context_without_documents_is_unchanged():
    bundle = dict(HEALTHY_BUNDLE)
    ctx = build_context(bundle, compute_score(bundle))
    assert "DOCUMENTE FURNIZATE" not in ctx


def test_context_skips_empty_documents():
    bundle = dict(HEALTHY_BUNDLE)
    bundle["user_documents"] = [{"name": "empty.txt", "content": "   "}]
    ctx = build_context(bundle, compute_score(bundle))
    # Header may appear but the empty body must not add the file separator.
    assert "empty.txt" not in ctx
