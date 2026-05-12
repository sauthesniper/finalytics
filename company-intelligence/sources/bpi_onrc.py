# sources/bpi_onrc.py

import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from utils.debug import save_html


load_dotenv()

ONRC_EMAIL = os.getenv("ONRC_EMAIL")
ONRC_PASSWORD = os.getenv("ONRC_PASSWORD")

LOGIN_URL = (
    "https://sso.onrc.ro/realms/onrc/protocol/openid-connect/auth"
    "?client_id=frontoffice-app"
    "&redirect_uri=https%3A%2F%2Fmyportal.onrc.ro%2Fhome"
    "&response_mode=fragment"
    "&response_type=code"
    "&scope=openid"
    "&ui_locales=ro"
)

PORTAL_HOME = "https://myportal.onrc.ro/home"

BPI_PJ_URL = (
    "https://myportal.onrc.ro/bpi-online/persoana-juridica"
)

SESSION_FILE = "onrc_session.json"


def clean_text(value: Any) -> str:

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def ensure_logged_in(page):

    #
    # dacă există sesiune validă
    #
    try:

        page.goto(
            BPI_PJ_URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(3000)

        #
        # dacă avem inputul CIF
        # suntem autentificați
        #
        cif_input = page.locator(
            'input[formcontrolname="pubPersonCuicnp"]'
        )

        if cif_input.count() > 0:

            print("[+] Already authenticated")

            return

    except:
        pass

    #
    # LOGIN FLOW
    #
    print("[+] Authentication required")

    page.goto(
        LOGIN_URL,
        wait_until="networkidle",
        timeout=60000
    )

    page.wait_for_timeout(3000)

    #
    # EMAIL
    #
    email_input = None

    for sel in [

        'input[type="email"]',

        'input[name="username"]',

        'input[id="username"]',
    ]:

        try:

            loc = page.locator(sel)

            if loc.count() > 0:

                email_input = loc.first

                print(f"[+] Email selector: {sel}")

                break

        except:
            pass

    if email_input is None:

        save_html(
            page,
            "debug_login_email_missing.html"
        )

        raise RuntimeError(
            "Nu am găsit câmpul email"
        )

    #
    # PASSWORD
    #
    password_input = None

    for sel in [

        'input[type="password"]',

        'input[name="password"]',

        'input[id="password"]',
    ]:

        try:

            loc = page.locator(sel)

            if loc.count() > 0:

                password_input = loc.first

                print(f"[+] Password selector: {sel}")

                break

        except:
            pass

    if password_input is None:

        save_html(
            page,
            "debug_login_password_missing.html"
        )

        raise RuntimeError(
            "Nu am găsit câmpul parolă"
        )

    #
    # FILL
    #
    print("[+] Filling credentials...")

    email_input.fill(
        ONRC_EMAIL
    )

    password_input.fill(
        ONRC_PASSWORD
    )

    #
    # LOGIN CLICK
    #
    clicked = False

    for sel in [

        '#kc-login',

        'button[type="submit"]',

        'input[type="submit"]',
    ]:

        try:

            loc = page.locator(sel)

            if loc.count() > 0:

                print(f"[+] Clicking login: {sel}")

                loc.first.click()

                clicked = True

                break

        except:
            pass

    if not clicked:

        password_input.press(
            "Enter"
        )

    print("[+] Waiting after login...")

    page.wait_for_timeout(12000)

    save_html(
        page,
        "debug_after_login.html"
    )

    #
    # OPEN BPI PAGE
    #
    page.goto(
        BPI_PJ_URL,
        wait_until="networkidle",
        timeout=60000
    )

    page.wait_for_timeout(4000)


def ensure_search_type_cif(page):

    try:

        selected = page.locator(
            'nz-select[formcontrolname="searchType"]'
        ).inner_text()

        if "CIF" in selected.upper():

            print("[+] CIF already selected")

            return

    except:
        pass

    print("[+] Selecting CIF from dropdown...")

    dropdown = page.locator(
        'nz-select[formcontrolname="searchType"]'
    )

    if dropdown.count() == 0:

        raise RuntimeError(
            "Nu am găsit dropdown-ul searchType"
        )

    dropdown.first.click()

    page.wait_for_timeout(1000)

    #
    # options overlay
    #
    options = page.locator(
        "nz-option-item"
    )

    found = False

    for i in range(options.count()):

        try:

            txt = clean_text(
                options.nth(i).inner_text()
            )

            if txt.upper() == "CIF":

                options.nth(i).click()

                found = True

                print("[+] CIF selected")

                break

        except:
            pass

    if not found:

        save_html(
            page,
            "debug_dropdown_missing.html"
        )

        raise RuntimeError(
            "Nu am găsit opțiunea CIF"
        )

    page.wait_for_timeout(1000)


def find_cif_input(page):

    selectors = [

        'input[formcontrolname="pubPersonCuicnp"]',

        'input[placeholder="CIF:"]',

        'input[placeholder*="CIF"]',

        'input[type="text"]',
    ]

    for sel in selectors:

        try:

            loc = page.locator(sel)

            if loc.count() > 0:

                print(f"[+] CIF input: {sel}")

                return loc.first

        except:
            pass

    return None


def click_search(page):

    try:

        btn = page.get_by_role(
            "button",
            name="Caută"
        )

        if btn.count() > 0:

            btn.first.click()

            print("[+] Search clicked")

            return

    except:
        pass

    #
    # fallback
    #
    buttons = page.locator("button")

    for i in range(buttons.count()):

        try:

            txt = clean_text(
                buttons.nth(i).inner_text()
            ).lower()

            if "caut" in txt:

                buttons.nth(i).click()

                print("[+] Search fallback clicked")

                return

        except:
            pass

    raise RuntimeError(
        "Nu am găsit butonul Caută"
    )


def parse_company_row(values):

    return {

        "index": values[0],

        "name": values[1],

        "cui": values[2],

        "nr_registru": values[3],

        "raw": values,
    }


def parse_bulletin_row(values):

    return {

        "numar_buletin": values[0],

        "an_buletin": values[1],

        "data_buletin": values[2],

        "raw": values,
    }


def extract_results(page):

    print("[+] Extracting table data...")

    page.wait_for_timeout(5000)

    save_html(
        page,
        "debug_bpi_results.html"
    )

    rows = page.locator(
        "table tr"
    )

    company = None

    bulletins: List[Dict[str, Any]] = []

    raw_rows = []

    for i in range(rows.count()):

        row = rows.nth(i)

        cells = row.locator("th, td")

        values = []

        for j in range(cells.count()):

            try:

                txt = clean_text(
                    cells.nth(j).inner_text()
                )

                if txt:
                    values.append(txt)

            except:
                pass

        if not values:
            continue

        raw_rows.append(values)

        #
        # COMPANY ROW
        #
        # ex:
        # 1 COMPANY_NAME 46943133 J...
        #
        if (

            company is None

            and len(values) >= 4

            and values[0].isdigit()

            and values[2].isdigit()
        ):

            company = parse_company_row(
                values
            )

            continue

        #
        # BULLETIN ROW
        #
        # ex:
        # 7043 2026 3/16/2026
        #
        if (

            len(values) >= 3

            and re.fullmatch(
                r"\d+",
                values[0]
            )

            and re.fullmatch(
                r"\d{4}",
                values[1]
            )
        ):

            bulletins.append(
                parse_bulletin_row(values)
            )

    return {

        "company": company,

        "bulletins": bulletins,

        "raw_rows": raw_rows,
    }


def check_bpi(
    page,
    cui
):

    ensure_logged_in(page)

    print("[+] Opening BPI PJ page...")

    page.goto(
        BPI_PJ_URL,
        wait_until="networkidle",
        timeout=60000
    )

    page.wait_for_timeout(3000)

    ensure_search_type_cif(page)

    #
    # CIF INPUT
    #
    cif_input = find_cif_input(page)

    if cif_input is None:

        save_html(
            page,
            "debug_cif_input_missing.html"
        )

        raise RuntimeError(
            "Nu am găsit inputul CIF"
        )

    print(f"[+] Filling CIF: {cui}")

    cif_input.fill(
        str(cui)
    )

    page.wait_for_timeout(1000)

    #
    # SEARCH
    #
    click_search(page)

    print("[+] Waiting for results...")

    page.wait_for_timeout(8000)

    #
    # EXTRACT
    #
    extracted = extract_results(
        page
    )

    return {

        "source": "ONRC BPI",

        "checked_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "search_type": "CIF",

        "company": extracted["company"],

        "bulletins": extracted["bulletins"],

        "raw_rows": extracted["raw_rows"],

        "possible_insolvency": (
            len(extracted["bulletins"]) > 0
        )
    }