import json
import os
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

from utils.normalize import normalize_cui

from sources.monitorul_oficial import (
    scrape_monitorul_oficial
)

from sources.bpi_onrc import (
    check_bpi
)

from sources.risk_flags import (
    build_risk_flags
)


CACHE_DIR = "cache"


def ensure_cache():

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )


def cache_path(cui):

    return os.path.join(
        CACHE_DIR,
        f"{cui}.json"
    )


def load_cache(cui):

    path = cache_path(cui)

    if os.path.exists(path):

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    return None


def save_cache(cui, data):

    path = cache_path(cui)

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def aggregate_company_data(cui_input):

    cui = normalize_cui(cui_input)

    ensure_cache()

    #
    # CACHE
    #
    cached = load_cache(cui)

    if cached:

        print("[+] Loaded from cache")

        return cached

    result = {

        "query": {

            "input": cui_input,

            "normalized_cui": cui
        },

        "meta": {

            "fetched_at": datetime.now(
                timezone.utc
            ).isoformat(),

            "sources": []
        }
    }

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox"
            ]
        )

        context = browser.new_context()

        page = context.new_page()

        #
        # MONITORUL OFICIAL
        #
        print(
            "[+] Scraping Monitorul Oficial..."
        )

        monitor_data = scrape_monitorul_oficial(
            page,
            cui
        )

        result["monitorul_oficial"] = (
            monitor_data
        )

        result["meta"]["sources"].append(
            "monitorul_oficial"
        )

        #
        # BPI
        #
        print(
            "[+] Scraping BPI..."
        )

        bpi_data = check_bpi(
            page,
            cui
        )

        result["bpi"] = bpi_data

        result["meta"]["sources"].append(
            "bpi_onrc"
        )

        #
        # FLAGS
        #
        result["risk_flags"] = (
            build_risk_flags(
                monitor_data,
                bpi_data
            )
        )

        browser.close()

    #
    # CACHE SAVE
    #
    save_cache(
        cui,
        result
    )

    return result


def main():

    if len(sys.argv) != 2:

        print(
            "Usage: python3 company_intelligence.py <CUI>"
        )

        sys.exit(1)

    result = aggregate_company_data(
        sys.argv[1]
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":

    main()