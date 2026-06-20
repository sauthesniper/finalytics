"""
Risk Analyst Agent (US13).

Interprets the aggregated data and the Collaboration Health Score and
explains the company's risk in natural Romanian. Uses an LLM when
available, otherwise produces a deterministic, fully-grounded summary.
"""
from typing import Dict, Any, List, Tuple

from app.llm import chat, MODEL
from app.agents.context import build_context
from app.agents.parsing import parse_summary_bullets

SYSTEM_PROMPT = (
    "Ești un analist de risc financiar pentru firme din România. "
    "Primești date factuale despre o firmă (ANAF, Monitorul Oficial, BPI) și un scor. "
    "Explică riscul colaborării în limba română, clar și concis. "
    "Folosește DOAR informațiile primite; nu inventa cifre sau fapte. "
    "Răspunde cu un paragraf de sinteză, apoi 3-5 puncte cheie marcate cu '- '."
)


def _fallback(bundle: Dict[str, Any], score: Dict[str, Any]) -> Tuple[str, List[str]]:
    band = score["band"]
    name = bundle.get("company_name") or f"CUI {bundle.get('cui')}"
    band_text = {
        "high_risk": "risc ridicat",
        "caution": "risc moderat — necesită atenție",
        "healthy": "risc scăzut",
    }.get(band, "risc nedeterminat")
    summary = (
        f"{name} are un scor de colaborare de {score['score']}/100 ({band_text}). "
        "Evaluarea se bazează pe starea juridică/fiscală, semnalele de insolvență, "
        "transparența și vechimea firmei."
    )
    bullets = list(score.get("negatives") or [])[:4]
    if not bullets:
        bullets = (score.get("positives") or [])[:4]
    if score.get("missing_data"):
        bullets.append("Date lipsă: " + ", ".join(score["missing_data"]))
    return summary, bullets


def build_user_prompt(bundle: Dict[str, Any], score: Dict[str, Any]) -> str:
    """The exact user prompt used by the Risk Analyst (shared with streaming)."""
    return (
        f"{build_context(bundle, score)}\n\n"
        "Realizează evaluarea de risc pentru colaborarea cu această firmă."
    )


def fallback_text(bundle: Dict[str, Any], score: Dict[str, Any]) -> str:
    """Deterministic risk text (used when the LLM is unavailable, incl. streaming)."""
    summary, bullets = _fallback(bundle, score)
    return summary + "\n" + "\n".join("- " + b for b in bullets)


def run_risk_analyst(bundle: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    context = build_context(bundle, score)
    user_prompt = (
        f"{context}\n\n"
        "Realizează evaluarea de risc pentru colaborarea cu această firmă."
    )
    text, used_llm = chat(SYSTEM_PROMPT, user_prompt, temperature=0.2)

    if used_llm and text:
        summary, bullets = parse_summary_bullets(text)
        if not bullets:
            bullets = (score.get("negatives") or score.get("positives") or [])[:4]
    else:
        summary, bullets = _fallback(bundle, score)

    return {
        "agent": "risk_analyst",
        "cui": bundle.get("cui"),
        "company_name": bundle.get("company_name"),
        "summary": summary,
        "bullets": bullets,
        "model": MODEL if used_llm else "rule-based-fallback",
        "used_llm": used_llm,
    }
