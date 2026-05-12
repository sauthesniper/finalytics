import json
import re
import sys
from datetime import datetime, timezone

import requests


MO_API_URL = "https://monitoruloficial.ro/ramo_customs/api/cui.php"


def normalize_cui(cui: str) -> str:
    """
    Normalizeaza CUI:
    - scoate RO
    - pastreaza doar cifrele
    """

    cui = cui.strip().upper()
    cui = cui.replace("RO", "")
    cui = re.sub(r"\D+", "", cui)

    return cui


def detect_category(entry: dict) -> str:
    """
    Detectie simpla categorie.
    """

    nr_mo = entry.get("nr_monitor")

    if nr_mo is None:
        return "unknown_publication"

    nr_mo = str(nr_mo)

    #
    # Heuristica simpla:
    # publicatiile fara numar MO
    # sunt foarte des:
    # - in curs
    # - proceduri speciale
    # - insolventa
    #

    if nr_mo == "N/A":
        return "special_procedure"

    return "monitorul_oficial"


def detect_insolvency(entry: dict) -> bool:
    """
    Heuristica minimalista.
    """

    return (
        entry.get("category") == "special_procedure"
    )


def fetch_monitorul_oficial(cui: str):

    payload = {
        "cui": cui,
        "nr": None
    }

    response = requests.post(
        MO_API_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def transform_entry(raw: dict) -> dict:

    nr_mo = raw.get("NR_MO")

    if nr_mo is None:
        nr_mo = "N/A"

    data_mo = raw.get("DATA_MO")

    if data_mo is None:
        data_mo = "N/A"

    else:
        data_mo = re.sub(r"\s+", " ", data_mo).strip()

    entry = {
        "nr_inregistrare_mo": raw.get("NR_INR_MO"),
        "cui": raw.get("CUI"),
        "nr_monitor": nr_mo,
        "data_monitor": data_mo,
        "source": "monitoruloficial.ro",
    }

    entry["category"] = detect_category(entry)

    entry["possible_insolvency"] = detect_insolvency(
        entry
    )

    return entry


def scrape_company(cui: str):

    cui = normalize_cui(cui)

    raw_data = fetch_monitorul_oficial(cui)

    transformed = []

    for item in raw_data.get("data", []):

        transformed.append(
            transform_entry(item)
        )

    result = {
        "query": {
            "cui": cui
        },
        "meta": {
            "source": "Monitorul Oficial Romania",
            "endpoint": MO_API_URL,
            "fetched_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "records": len(transformed)
        },
        "results": transformed
    }

    return result


if __name__ == "__main__":

    if len(sys.argv) != 2:

        print(
            "Usage: python3 company_monitor_scraper.py <CUI>"
        )

        sys.exit(1)

    result = scrape_company(sys.argv[1])

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )