# company_publications_aggregator.py

import json
import re
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright


SEARCH_URL = "https://monitoruloficial.ro/cauta-publicare-profesionisti/"


def normalize_cui(cui: str) -> str:

    cui = cui.strip().upper()
    cui = cui.replace("RO", "")
    cui = re.sub(r"\D+", "", cui)

    return cui


def clean(value):

    if value is None:
        return None

    value = str(value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def classify_entry(entry):

    nr_monitor = entry.get("nr_monitor")

    if nr_monitor is None:
        return "special_procedure"

    return "monitorul_oficial"


def build_entry(raw):

    entry = {
        "nr_inregistrare_mo": clean(
            raw.get("NR_INR_MO")
        ),

        "cui": clean(
            raw.get("CUI")
        ),

        "nr_monitor": clean(
            raw.get("NR_MO")
        ),

        "data_monitor": clean(
            raw.get("DATA_MO")
        ),

        "source": "monitoruloficial.ro",
    }

    entry["category"] = classify_entry(
        entry
    )

    entry["possible_insolvency"] = (
        entry["category"] == "special_procedure"
    )

    return entry


def scrape_monitorul_oficial(cui):

    captured_json = None

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context()

        page = context.new_page()

        #
        # capturam raspunsul AJAX REAL
        #
        def handle_response(response):

            nonlocal captured_json

            if "ramo_customs/api/cui.php" in response.url:

                try:

                    data = response.json()

                    captured_json = data

                except Exception as e:

                    print("ERR JSON:", e)

        page.on(
            "response",
            handle_response
        )

        #
        # deschidem pagina
        #
        page.goto(
            SEARCH_URL,
            wait_until="networkidle",
            timeout=60000
        )

        #
        # completam CUI
        #
        page.locator(
            'input[placeholder="CUI"]'
        ).fill(cui)

        #
        # click cauta
        #
        page.locator(
            'button:has-text("Caută")'
        ).click()

        #
        # asteptam AJAX
        #
        page.wait_for_timeout(5000)

        browser.close()

    if captured_json is None:

        raise RuntimeError(
            "Nu am capturat raspunsul AJAX"
        )

    return captured_json


def aggregate_company(cui_input):

    cui = normalize_cui(cui_input)

    raw = scrape_monitorul_oficial(cui)

    transformed = []

    for item in raw.get("data", []):

        transformed.append(
            build_entry(item)
        )

    result = {

        "query": {
            "cui": cui,
            "original_input": cui_input
        },

        "meta": {

            "source": "Monitorul Oficial Romania",

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
            "Usage: python3 company_publications_aggregator.py <CUI>"
        )

        sys.exit(1)

    result = aggregate_company(
        sys.argv[1]
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )