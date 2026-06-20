"""
Collaboration Health Score engine (US3) with explainability (US4).

Produces a deterministic 0-100 score from aggregated company data,
broken down into weighted pillars, each with human-readable reasons.
Higher score = safer to collaborate with.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

# Pillar weights (must sum to 1.0)
WEIGHTS = {
    "legal_fiscal": 0.30,
    "insolvency": 0.30,
    "transparency": 0.15,
    "activity": 0.15,
    "freshness": 0.10,
}

PILLAR_LABELS = {
    "legal_fiscal": "Stare juridică & fiscală",
    "insolvency": "Risc de insolvență",
    "transparency": "Transparență & prezență digitală",
    "activity": "Activitate & vechime",
    "freshness": "Prospețimea datelor",
}


def _truthy(value: Any) -> bool:
    """Interpret ANAF-style truthy values ('Da', True, 1)."""
    if isinstance(value, str):
        return value.strip().lower() in ("da", "true", "yes", "1")
    return bool(value)


def _company_age_years(anaf: Dict[str, Any]) -> float:
    """Best-effort company age in years from ANAF registration date."""
    raw = (anaf or {}).get("data_inregistrare")
    if not raw:
        return -1.0
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y%m%d"):
        try:
            dt = datetime.strptime(str(raw)[:10], fmt)
            return max(0.0, (datetime.now() - dt).days / 365.25)
        except ValueError:
            continue
    return -1.0


def _score_legal_fiscal(anaf: Dict[str, Any]) -> Tuple[float, List[str], bool]:
    if not anaf:
        return 50.0, ["Date ANAF indisponibile — scor neutru."], False

    score = 100.0
    reasons: List[str] = []

    inactiv = _truthy((anaf.get("stare_inactiv") or {}).get("statusInactivi"))
    if inactiv:
        score -= 70
        reasons.append("Firmă declarată INACTIVĂ la ANAF (-70).")
    else:
        reasons.append("Firmă activă la ANAF.")

    stare = (anaf.get("stare_inregistrare") or "").lower()
    if "radiere" in stare or "radiata" in stare:
        score -= 60
        reasons.append("Stare de înregistrare indică radiere (-60).")

    platitor_tva = _truthy((anaf.get("tva") or {}).get("platitorTVA"))
    if platitor_tva:
        score += 0  # neutral-positive; absence isn't penalized hard
        reasons.append("Plătitor de TVA — operează în regim standard.")
    else:
        score -= 5
        reasons.append("Neplătitor de TVA (-5).")

    return max(0.0, min(100.0, score)), reasons, True


def _score_insolvency(intel: Dict[str, Any]) -> Tuple[float, List[str], bool]:
    if not intel:
        return 50.0, ["Date BPI/Monitorul Oficial indisponibile — scor neutru."], False

    flags = intel.get("risk_flags") or {}
    bpi = intel.get("bpi") or {}
    bulletins = bpi.get("bulletins") or []

    score = 100.0
    reasons: List[str] = []

    if flags.get("bankruptcy"):
        score -= 90
        reasons.append("Faliment detectat în BPI (-90).")
    elif flags.get("insolvency") or bulletins:
        score -= 60
        reasons.append(f"Proceduri de insolvență în BPI: {len(bulletins)} buletine (-60).")
    else:
        reasons.append("Fără buletine de insolvență în BPI.")

    if flags.get("reorganization"):
        score -= 20
        reasons.append("Indicii de reorganizare judiciară (-20).")

    return max(0.0, min(100.0, score)), reasons, True


def _score_transparency(anaf: Dict[str, Any], serp: Dict[str, Any]) -> Tuple[float, List[str], bool]:
    has_anaf = bool(anaf)
    has_serp = bool(serp)
    if not has_anaf and not has_serp:
        return 50.0, ["Date de transparență indisponibile — scor neutru."], False

    score = 50.0
    reasons: List[str] = []

    if has_anaf and _truthy(anaf.get("statusRO_e_Factura")):
        score += 25
        reasons.append("Înregistrată în RO e-Factura (+25).")
    elif has_anaf:
        reasons.append("Neînregistrată în RO e-Factura.")

    if has_serp and serp.get("status") == "found":
        conf = float(serp.get("confidence") or 0)
        bump = round(25 * conf)
        score += bump
        reasons.append(f"Website oficial găsit ({serp.get('domain')}, încredere {int(conf*100)}%) (+{bump}).")
    elif has_serp:
        reasons.append("Niciun website oficial identificat.")

    return max(0.0, min(100.0, score)), reasons, True


def _score_activity(anaf: Dict[str, Any], intel: Dict[str, Any]) -> Tuple[float, List[str], bool]:
    if not anaf and not intel:
        return 50.0, ["Date de activitate indisponibile — scor neutru."], False

    score = 50.0
    reasons: List[str] = []

    age = _company_age_years(anaf or {})
    if age >= 0:
        if age >= 10:
            score += 30
            reasons.append(f"Vechime solidă: ~{age:.0f} ani (+30).")
        elif age >= 3:
            score += 20
            reasons.append(f"Vechime moderată: ~{age:.0f} ani (+20).")
        else:
            score += 5
            reasons.append(f"Firmă tânără: ~{age:.1f} ani (+5).")
    else:
        reasons.append("Data înregistrării indisponibilă.")

    mo = (intel or {}).get("monitorul_oficial") or {}
    records = mo.get("records") or 0
    if records > 0:
        score += 10
        reasons.append(f"{records} publicații în Monitorul Oficial (+10).")
    if (intel or {}).get("risk_flags", {}).get("high_activity_company"):
        reasons.append("Volum ridicat de evenimente publice (monitorizare recomandată).")

    return max(0.0, min(100.0, score)), reasons, True


def _score_freshness(bundle: Dict[str, Any]) -> Tuple[float, List[str], bool, str]:
    sources = bundle.get("sources") or []
    fetched = None
    intel = bundle.get("intel") or {}
    meta = intel.get("meta") or {}
    if meta.get("fetched_at"):
        fetched = meta["fetched_at"]

    if not sources:
        return 0.0, ["Nicio sursă nu a răspuns."], False, fetched or "n/a"

    # More sources answering = fresher, more complete picture.
    coverage = len(sources) / 3.0  # anaf, intel, serp
    score = round(min(1.0, coverage) * 100)
    reasons = [f"Surse interogate cu succes: {', '.join(sources)}."]
    return float(score), reasons, True, fetched or datetime.now(timezone.utc).isoformat()


def compute_score(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the full Collaboration Health Score from an aggregated bundle."""
    anaf = bundle.get("anaf")
    intel = bundle.get("intel")
    serp = bundle.get("serp")

    pillars_raw = {}
    pillars_raw["legal_fiscal"] = _score_legal_fiscal(anaf)
    pillars_raw["insolvency"] = _score_insolvency(intel)
    pillars_raw["transparency"] = _score_transparency(anaf, serp)
    pillars_raw["activity"] = _score_activity(anaf, intel)
    fresh_score, fresh_reasons, fresh_avail, fetched_at = _score_freshness(bundle)
    pillars_raw["freshness"] = (fresh_score, fresh_reasons, fresh_avail)

    overall = 0.0
    pillars: List[Dict[str, Any]] = []
    positives: List[str] = []
    negatives: List[str] = []
    missing: List[str] = []

    for key, (pscore, reasons, available) in pillars_raw.items():
        weight = WEIGHTS[key]
        overall += pscore * weight
        pillars.append({
            "key": key,
            "label": PILLAR_LABELS[key],
            "score": round(pscore, 1),
            "weight": weight,
            "reasons": reasons,
            "data_available": available,
        })
        if not available:
            missing.append(PILLAR_LABELS[key])
        for r in reasons:
            if "(+" in r:
                positives.append(r)
            elif "(-" in r:
                negatives.append(r)

    overall_int = int(round(overall))
    if overall_int < 40:
        band = "high_risk"
    elif overall_int < 70:
        band = "caution"
    else:
        band = "healthy"

    return {
        "cui": bundle.get("cui"),
        "company_name": bundle.get("company_name"),
        "score": overall_int,
        "band": band,
        "pillars": pillars,
        "positives": positives,
        "negatives": negatives,
        "missing_data": missing,
        "data_freshness": fetched_at,
    }
