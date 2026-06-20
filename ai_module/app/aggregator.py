"""
Aggregates company data from the other Finalytics microservices.

Calls ANAF, Company-Intelligence and SERP over the internal Docker
network and returns a single normalized dict that the scoring engine
and the AI agents consume.
"""
import os
from datetime import date
from typing import Optional, Dict, Any

import requests

# Internal service URLs (overridable via env for local dev / tests)
ANAF_URL = os.getenv("ANAF_URL", "http://anaf-api:8002")
INTEL_URL = os.getenv("INTEL_URL", "http://intel-api:8000")
SERP_URL = os.getenv("SERP_URL", "http://serp-api:3000")
SERP_API_KEY = os.getenv("SERP_API_KEY", "dev-secret-key")

# Per-call timeouts (seconds). Intel scrapes a browser, so it is generous.
ANAF_TIMEOUT = int(os.getenv("ANAF_TIMEOUT", "30"))
INTEL_TIMEOUT = int(os.getenv("INTEL_TIMEOUT", "120"))
SERP_TIMEOUT = int(os.getenv("SERP_TIMEOUT", "30"))


def _fetch_anaf(cui: str) -> Optional[Dict[str, Any]]:
    """Fetch fiscal data from the ANAF proxy. Returns the first company or None."""
    try:
        resp = requests.post(
            f"{ANAF_URL}/efactura",
            json={"cui": int(cui), "data": date.today().isoformat()},
            timeout=ANAF_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        found = data.get("found") or []
        return found[0] if found else None
    except (requests.RequestException, ValueError):
        return None


def _fetch_intel(cui: str) -> Optional[Dict[str, Any]]:
    """Fetch Monitorul Oficial + BPI intelligence."""
    try:
        resp = requests.get(f"{INTEL_URL}/company/{cui}", timeout=INTEL_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def _fetch_serp(company_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Discover the company's official website."""
    if not company_name:
        return None
    try:
        resp = requests.post(
            f"{SERP_URL}/discover",
            json={"companyName": company_name},
            headers={"x-api-key": SERP_API_KEY},
            timeout=SERP_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def aggregate_light(cui: Optional[str], company_name: Optional[str]) -> Dict[str, Any]:
    """
    Minimal bundle for the Web Research Agent: ANAF only.

    The agent does its own active web searching, so it does NOT need the slow
    intel scrape or the deterministic SERP discovery — it just needs the
    company name and address (to enrich its queries). This avoids re-running
    the heavy aggregation a second time per analysis.
    """
    bundle: Dict[str, Any] = {
        "cui": cui,
        "company_name": company_name,
        "anaf": None,
        "serp": None,
        "sources": [],
    }
    if cui:
        anaf = _fetch_anaf(cui)
        if anaf:
            bundle["anaf"] = anaf
            bundle["sources"].append("anaf")
            if not company_name and anaf.get("denumire"):
                bundle["company_name"] = anaf["denumire"]
    return bundle


def aggregate(cui: Optional[str], company_name: Optional[str]) -> Dict[str, Any]:
    """
    Gather all available data for a company into a single bundle.

    The returned dict always has the keys: cui, company_name, anaf,
    intel, serp, sources (list of services that responded).
    """
    bundle: Dict[str, Any] = {
        "cui": cui,
        "company_name": company_name,
        "anaf": None,
        "intel": None,
        "serp": None,
        "sources": [],
    }

    if cui:
        anaf = _fetch_anaf(cui)
        if anaf:
            bundle["anaf"] = anaf
            bundle["sources"].append("anaf")
            # Fill the company name from ANAF if the caller didn't give one
            if not company_name and anaf.get("denumire"):
                bundle["company_name"] = anaf["denumire"]
                company_name = anaf["denumire"]

        intel = _fetch_intel(cui)
        if intel:
            bundle["intel"] = intel
            bundle["sources"].append("intel")

    serp = _fetch_serp(bundle["company_name"])
    if serp:
        bundle["serp"] = serp
        bundle["sources"].append("serp")

    return bundle
