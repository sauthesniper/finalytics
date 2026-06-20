"""
Builds a compact, factual context string from aggregated data + score.

This context is the single source of truth handed to every AI agent so
that the LLM stays grounded and cannot invent fields. Keeping it small
also keeps token usage (and hallucination surface) low.
"""
from typing import Dict, Any

# Caps for user-provided documents, to bound token usage / hallucination surface.
MAX_DOCS = 8
MAX_DOC_CHARS = 4000


def build_context(bundle: Dict[str, Any], score: Dict[str, Any]) -> str:
    lines = []
    name = bundle.get("company_name") or "necunoscut"
    cui = bundle.get("cui") or "necunoscut"
    lines.append(f"FIRMA: {name} (CUI {cui})")
    lines.append(f"SCOR COLABORARE: {score['score']}/100 (categorie: {score['band']})")

    anaf = bundle.get("anaf") or {}
    if anaf:
        inactiv = (anaf.get("stare_inactiv") or {}).get("statusInactivi")
        tva = (anaf.get("tva") or {}).get("platitorTVA")
        lines.append("ANAF:")
        lines.append(f"  - denumire: {anaf.get('denumire')}")
        lines.append(f"  - stare inregistrare: {anaf.get('stare_inregistrare')}")
        lines.append(f"  - inactiv: {inactiv}")
        lines.append(f"  - platitor TVA: {tva}")
        lines.append(f"  - e-Factura: {anaf.get('statusRO_e_Factura')}")
        lines.append(f"  - cod CAEN: {anaf.get('cod_CAEN')}")
        lines.append(f"  - data inregistrare: {anaf.get('data_inregistrare')}")
    else:
        lines.append("ANAF: indisponibil")

    intel = bundle.get("intel") or {}
    if intel:
        flags = intel.get("risk_flags") or {}
        mo = intel.get("monitorul_oficial") or {}
        bpi = intel.get("bpi") or {}
        lines.append("INTEL (Monitorul Oficial + BPI):")
        lines.append(f"  - publicatii Monitorul Oficial: {mo.get('records', 0)}")
        lines.append(f"  - buletine BPI (insolventa): {len(bpi.get('bulletins') or [])}")
        lines.append(f"  - flags: insolventa={flags.get('insolvency')}, "
                     f"faliment={flags.get('bankruptcy')}, "
                     f"reorganizare={flags.get('reorganization')}, "
                     f"activitate_ridicata={flags.get('high_activity_company')}")
    else:
        lines.append("INTEL: indisponibil")

    serp = bundle.get("serp") or {}
    if serp and serp.get("status") == "found":
        lines.append(f"WEBSITE: {serp.get('website')} (incredere {int((serp.get('confidence') or 0)*100)}%)")
    else:
        lines.append("WEBSITE: neidentificat")

    lines.append("MOTIVE SCOR (pozitive): " + ("; ".join(score.get("positives") or []) or "niciunul"))
    lines.append("MOTIVE SCOR (negative): " + ("; ".join(score.get("negatives") or []) or "niciunul"))

    docs = bundle.get("user_documents") or []
    if docs:
        lines.append("")
        lines.append("DOCUMENTE FURNIZATE DE UTILIZATOR "
                     "(folosește-le ca sursă suplimentară, alături de datele oficiale):")
        for d in docs[:MAX_DOCS]:
            name = (d.get("name") or "document").strip()
            content = (d.get("content") or "").strip()[:MAX_DOC_CHARS]
            if not content:
                continue
            lines.append(f"--- {name} ---")
            lines.append(content)

    return "\n".join(lines)
