"""
Server-side integrations with the other Finalytics microservices.

Centralizes calls to the AI module (score + agents) and raw data
services so the backend can build reports, snapshots and alerts without
relying on the browser to orchestrate.
"""
import os
from datetime import date
from typing import Optional, Dict, Any

import requests

AI_URL = os.getenv("AI_URL", "http://ai-api:8003")
ANAF_URL = os.getenv("ANAF_URL", "http://anaf-api:8002")
INTEL_URL = os.getenv("INTEL_URL", "http://intel-api:8000")

AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "90"))
ANAF_TIMEOUT = int(os.getenv("ANAF_TIMEOUT", "30"))
INTEL_TIMEOUT = int(os.getenv("INTEL_TIMEOUT", "120"))


def get_score(cui: Optional[str], company_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Fetch the Collaboration Health Score from the AI module."""
    try:
        resp = requests.post(
            f"{AI_URL}/score",
            json={"cui": cui, "company_name": company_name},
            timeout=AI_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def get_full_analysis(cui: Optional[str], company_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Fetch score + both agent assessments from the AI module."""
    try:
        resp = requests.post(
            f"{AI_URL}/analyze",
            json={"cui": cui, "company_name": company_name},
            timeout=AI_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def get_compare(companies: list) -> Optional[Dict[str, Any]]:
    """Proxy a compare request to the AI module."""
    try:
        resp = requests.post(
            f"{AI_URL}/compare",
            json={"companies": companies},
            timeout=AI_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None


def get_anaf(cui: str) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.post(
            f"{ANAF_URL}/efactura",
            json={"cui": int(cui), "data": date.today().isoformat()},
            timeout=ANAF_TIMEOUT,
        )
        resp.raise_for_status()
        found = resp.json().get("found") or []
        return found[0] if found else None
    except (requests.RequestException, ValueError):
        return None


def get_intel(cui: str) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(f"{INTEL_URL}/company/{cui}", timeout=INTEL_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None
