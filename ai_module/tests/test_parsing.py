"""Tests for the LLM output parser (handles messy bullet formatting)."""
from app.agents.parsing import parse_summary_bullets


def test_basic_split():
    text = "Sinteza aici.\n- punct unu\n- punct doi"
    summary, bullets = parse_summary_bullets(text)
    assert summary == "Sinteza aici."
    assert bullets == ["punct unu", "punct doi"]


def test_doubled_dash_cleaned():
    text = "Rezumat.\n- - actiune dubla\n* * alta"
    _, bullets = parse_summary_bullets(text)
    assert bullets == ["actiune dubla", "alta"]


def test_numbered_bullets():
    text = "Rezumat.\n1. primul\n2) al doilea"
    _, bullets = parse_summary_bullets(text)
    assert bullets == ["primul", "al doilea"]


def test_no_bullets_returns_full_summary():
    text = "Doar un paragraf fara puncte."
    summary, bullets = parse_summary_bullets(text)
    assert summary == "Doar un paragraf fara puncte."
    assert bullets == []
