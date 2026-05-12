# sources/monitorul_oficial.py

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


SEARCH_URL = "https://monitoruloficial.ro/cauta-publicare-profesionisti/"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_cui(cui: str) -> str:
    cui = (cui or "").strip().upper().replace("RO", "")
    cui = re.sub(r"\D+", "", cui)
    return cui


def detect_category(row: Dict[str, Any]) -> str:
    """
    Clasificare simplă, doar pentru organizare internă.
    Nu confundăm Monitorul Oficial cu insolvența.
    """
    if row.get("nr_monitor") in ("", "N/A", None):
        return "special_or_without_monitor_number"
    return "monitorul_oficial_publication"


def transform_entry(values: List[str]) -> Dict[str, Any]:
    nr_inr_mo = values[0] if len(values) > 0 else ""
    cui = values[1] if len(values) > 1 else ""
    nr_mo = values[2] if len(values) > 2 and values[2] else "N/A"
    data_mo = values[3] if len(values) > 3 and values[3] else "N/A"

    entry = {
        "nr_inregistrare_mo": clean_text(nr_inr_mo),
        "cui": clean_text(cui),
        "nr_monitor": clean_text(nr_mo),
        "data_monitor": clean_text(data_mo),
        "source": "monitoruloficial.ro",
    }

    entry["category"] = detect_category(
        {
            "nr_monitor": entry["nr_monitor"]
        }
    )

    return entry


def scrape_monitorul_oficial(page, cui: str) -> Dict[str, Any]:
    cui = normalize_cui(cui)

    print("[+] Opening Monitorul Oficial search page...")
    page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000)

    # inputul corect pe care l-ai identificat deja
    cui_input = page.locator('input[placeholder="CUI"]')
    if cui_input.count() == 0:
        raise RuntimeError("Nu am găsit inputul CUI pe Monitorul Oficial")

    print(f"[+] Filling CUI: {cui}")
    cui_input.first.fill(cui)

    print("[+] Clicking Caută...")
    try:
        page.get_by_role("button", name="Caută").click(timeout=5000)
    except Exception:
        page.locator('button:has-text("Caută")').first.click()

    page.wait_for_timeout(6000)

    # extragem tabelul
    rows = page.locator("table tbody tr")
    row_count = rows.count()

    publications: List[Dict[str, Any]] = []
    raw_rows: List[List[str]] = []

    for i in range(row_count):
        row = rows.nth(i)
        cells = row.locator("td")
        values: List[str] = []

        for j in range(cells.count()):
            txt = clean_text(cells.nth(j).inner_text())
            values.append(txt)

        if not values:
            continue

        raw_rows.append(values)

        # așteptăm 4 coloane: nr înregistrare, cui, nr MO, data MO
        if len(values) >= 2:
            publications.append(transform_entry(values))

    possible_special = sum(
        1 for x in publications if x.get("category") == "special_or_without_monitor_number"
    )

    return {
        "source": "Monitorul Oficial",
        "search_url": SEARCH_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "records": len(publications),
        "special_or_without_monitor_number_records": possible_special,
        "publications": publications,
        "raw_rows": raw_rows,
    }