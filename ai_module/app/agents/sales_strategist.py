"""
Sales Strategist Agent (US14 + US8).

Turns the company profile and score into concrete commercial and
partnership recommendations (payment terms, contract safeguards,
outreach angle). LLM-backed with a deterministic fallback.
"""
from typing import Dict, Any, List, Tuple

from app.llm import chat, MODEL
from app.agents.context import build_context
from app.agents.parsing import parse_summary_bullets

SYSTEM_PROMPT = (
    "Ești un strateg de vânzări și parteneriate B2B pentru piața din România. "
    "Pe baza profilului unei firme și a scorului de colaborare, oferi recomandări "
    "comerciale concrete și acționabile, în limba română. "
    "Folosește DOAR datele primite. Adaptează termenii de plată și garanțiile la nivelul de risc. "
    "Răspunde cu un paragraf de strategie, apoi 3-5 acțiuni concrete marcate cu '- '."
)


def _fallback(bundle: Dict[str, Any], score: Dict[str, Any]) -> Tuple[str, List[str]]:
    band = score["band"]
    name = bundle.get("company_name") or f"CUI {bundle.get('cui')}"
    if band == "high_risk":
        summary = (
            f"Pentru {name} (scor {score['score']}/100, risc ridicat) recomandăm o abordare "
            "prudentă: colaborare doar cu plată în avans și fără expunere financiară semnificativă."
        )
        bullets = [
            "Solicită plata 100% în avans sau garanții bancare.",
            "Evită creditul comercial și termenele de plată extinse.",
            "Verifică periodic statusul BPI înainte de fiecare tranzacție.",
            "Limitează valoarea contractelor inițiale.",
        ]
    elif band == "caution":
        summary = (
            f"Pentru {name} (scor {score['score']}/100, risc moderat) recomandăm o relație "
            "comercială graduală, cu monitorizare activă."
        )
        bullets = [
            "Începe cu comenzi mici și termene de plată scurte (avans 30-50%).",
            "Introdu clauze de penalitate pentru întârziere în contract.",
            "Activează alerte pentru schimbări de risc.",
            "Reevaluează termenii după primele 2-3 tranzacții reușite.",
        ]
    else:
        summary = (
            f"Pentru {name} (scor {score['score']}/100, risc scăzut) există o bază solidă "
            "pentru un parteneriat comercial pe termen lung."
        )
        bullets = [
            "Poți oferi termene de plată standard (30 de zile).",
            "Propune un contract-cadru pentru volume recurente.",
            "Explorează oportunități de parteneriat strategic.",
            "Menține monitorizarea de rutină a profilului.",
        ]
    return summary, bullets


def run_sales_strategist(bundle: Dict[str, Any], score: Dict[str, Any]) -> Dict[str, Any]:
    context = build_context(bundle, score)
    user_prompt = (
        f"{context}\n\n"
        "Oferă strategia comercială și recomandările de colaborare pentru această firmă."
    )
    text, used_llm = chat(SYSTEM_PROMPT, user_prompt, temperature=0.4)

    if used_llm and text:
        summary, bullets = parse_summary_bullets(text)
        if not bullets:
            _, bullets = _fallback(bundle, score)
    else:
        summary, bullets = _fallback(bundle, score)

    return {
        "agent": "sales_strategist",
        "cui": bundle.get("cui"),
        "company_name": bundle.get("company_name"),
        "summary": summary,
        "bullets": bullets,
        "model": MODEL if used_llm else "rule-based-fallback",
        "used_llm": used_llm,
    }
