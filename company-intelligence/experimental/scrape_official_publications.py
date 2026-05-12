# scrape_official_publications.py

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


def scrape_company_publications(cui: str):

    cui = normalize_cui(cui)

    result = {
        "cui": cui,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ajax_requests": [],
        "ajax_responses": [],
        "results": []
    }

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False,
            slow_mo=300
        )

        context = browser.new_context()

        page = context.new_page()

        #
        # INTERCEPTAM TOATE REQUESTURILE
        #
        def handle_request(request):

            url = request.url

            if "ramo" in url or "admin-ajax" in url or "api" in url:

                print("\n================ REQUEST ================")
                print("URL:", url)
                print("METHOD:", request.method)

                try:
                    post_data = request.post_data
                    print("POST DATA:", post_data)
                except:
                    post_data = None

                result["ajax_requests"].append({
                    "url": url,
                    "method": request.method,
                    "post_data": post_data
                })

        #
        # INTERCEPTAM TOATE RESPONSE-URILE
        #
        def handle_response(response):

            url = response.url

            if "ramo" in url or "admin-ajax" in url or "api" in url:

                print("\n================ RESPONSE ================")
                print("URL:", url)
                print("STATUS:", response.status)

                try:

                    text = response.text()

                    print("BODY:")
                    print(text[:3000])

                    result["ajax_responses"].append({
                        "url": url,
                        "status": response.status,
                        "body": text
                    })

                    #
                    # incercam sa parse JSON
                    #
                    try:

                        data = json.loads(text)

                        if isinstance(data, list):
                            result["results"] = data

                        elif isinstance(data, dict):
                            result["results"] = data

                    except:
                        pass

                except Exception as e:
                    print("ERR RESPONSE:", e)

        page.on("request", handle_request)
        page.on("response", handle_response)

        print("[+] Opening page...")

        page.goto(
            SEARCH_URL,
            wait_until="networkidle",
            timeout=60000
        )

        print("[+] Filling CUI...")

        page.locator(
            'input[placeholder="CUI"]'
        ).fill(cui)

        print("[+] Clicking search...")

        page.locator(
            'button:has-text("Caută")'
        ).click()

        print("[+] Waiting for AJAX...")

        page.wait_for_timeout(10000)

        #
        # salvam html final
        #
        with open(
            "final_page.html",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(page.content())

        browser.close()

    return result


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print(
            "Usage: python3 scrape_official_publications.py <CUI>"
        )
        sys.exit(1)

    data = scrape_company_publications(sys.argv[1])

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        )
    )