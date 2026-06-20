"""
Q&A Agent (US9) — "Întreabă AI-ul despre firmă".

Answers free-form questions about a company strictly from the
aggregated data context. Falls back to a helpful message when the LLM
is unavailable.
"""
from typing import Dict, Any

from app.llm import chat, MODEL
from app.agents.context import build_context

SYSTEM_PROMPT = (
    "Ești asistentul Finalytics. Răspunzi la întrebări despre o firmă din România "
    "folosind EXCLUSIV contextul factual primit (ANAF, Monitorul Oficial, BPI, scor). "
    "Răspunde scurt și la obiect, în limba română. "
    "Dacă informația cerută nu se află în context, spune clar că nu este disponibilă."
)


def run_qa(bundle: Dict[str, Any], score: Dict[str, Any], question: str) -> Dict[str, Any]:
    context = build_context(bundle, score)
    user_prompt = f"{context}\n\nÎNTREBARE: {question}\n\nRăspuns:"
    text, used_llm = chat(SYSTEM_PROMPT, user_prompt, temperature=0.2, max_tokens=400)

    if not (used_llm and text):
        name = bundle.get("company_name") or f"CUI {bundle.get('cui')}"
        text = (
            f"Momentan nu pot genera un răspuns AI (model indisponibil). "
            f"Pe baza datelor: {name} are scorul de colaborare {score['score']}/100 "
            f"(categorie: {score['band']}). "
            "Reformulează întrebarea sau consultă cardurile de date pentru detalii."
        )

    return {
        "answer": text,
        "cui": bundle.get("cui"),
        "model": MODEL if used_llm else "rule-based-fallback",
        "used_llm": used_llm,
    }
