import time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from pdf_to_json import pdf_to_json

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_PROFILE = r"C:\temp\edge_onrc_profile"

LOGIN_URL = "https://sso.onrc.ro/realms/onrc/protocol/openid-connect/auth?client_id=frontoffice-app&redirect_uri=https%3A%2F%2Fmyportal.onrc.ro%2Fhome&response_mode=fragment&response_type=code&scope=openid&ui_locales=ro"

REPORT_GENERATION_URL = "https://portal.berc.onrc.ro/report-generation"

DATA_DIR = Path("data_pdf")
DATA_DIR.mkdir(exist_ok=True)

USERNAME = "finbotv1"
PASSWORD = "L0remIpsum*"


def login_si_mergi_la_report_generation(page):
    page.goto(LOGIN_URL)
    page.wait_for_load_state("networkidle")

    # Dacă este deja logat, poate ajunge direct în MyPortal
    if "myportal.onrc.ro/home" in page.url:
        print("✅ Era deja logat. Ajuns direct în MyPortal")
    else:
        print("🔐 Nu era logat. Fac login...")

        page.locator("#username").wait_for(state="visible", timeout=30000)
        page.locator("#username").fill(USERNAME)
        page.locator("#password").fill(PASSWORD)
        page.locator("#kc-login").click()

        print("✅ Login apăsat")

        page.wait_for_url("**://myportal.onrc.ro/home**", timeout=60000)
        page.wait_for_load_state("networkidle")

        print("✅ Ajuns în MyPortal")

    # Click pe BERC și prinde tab-ul nou
    print("➡️ Deschid BERC...")

    try:
        with page.context.expect_page(timeout=30000) as new_page_info:
            page.get_by_text(
                "Buletinul Electronic al Registrului Comerțului",
                exact=False
            ).click()

        berc_page = new_page_info.value
        berc_page.wait_for_load_state("networkidle")

    except PlaywrightTimeoutError:
        # fallback: dacă nu a prins popup-ul, caută tab-ul manual
        berc_pages = [
            tab for tab in page.context.pages
            if not tab.is_closed() and "portal.berc.onrc.ro" in tab.url
        ]

        if not berc_pages:
            raise Exception("Nu am găsit tab-ul BERC după click.")

        berc_page = berc_pages[-1]

    berc_page.bring_to_front()

    print("✅ Ajuns în BERC:", berc_page.url)

    berc_page.goto(REPORT_GENERATION_URL)
    berc_page.wait_for_load_state("networkidle")

    print("✅ Ajuns la report-generation")

    return berc_page


def gaseste_sau_deschide_berc(context):
    # Dacă BERC report-generation e deja deschis, îl folosim direct
    berc_pages = [
        tab for tab in context.pages
        if (
            not tab.is_closed()
            and "portal.berc.onrc.ro/report-generation" in tab.url
        )
    ]

    if berc_pages:
        page = berc_pages[-1]
        page.bring_to_front()
        page.wait_for_load_state("networkidle")

        print("✅ Folosesc tab-ul BERC existent")

        return page

    # Altfel pornim flow-ul normal
    page = context.new_page()
    return login_si_mergi_la_report_generation(page)


def completeaza_si_descarca_pdf(page, cui: str):
    cui = cui.strip()

    page.wait_for_load_state("networkidle")

    # Select raport
    page.locator(".mat-select-trigger").first.click()

    page.locator(
        "mat-option:has-text('Articole publicate pentru un profesionist')"
    ).click()

    # Introdu CUI
    cui_input = page.locator("#commonRcsearching_fiscalCode")
    cui_input.wait_for(state="visible", timeout=30000)
    cui_input.click()

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    for ch in cui:
        page.keyboard.type(ch)
        page.wait_for_timeout(30)

    print("Valoare CUI:", cui_input.input_value())

    # Caută
    search_btn = page.locator("#commonRcsearching_showButton")
    search_btn.wait_for(state="visible", timeout=30000)
    search_btn.scroll_into_view_if_needed()

    search_btn.dispatch_event("mouseover")
    search_btn.dispatch_event("mousedown")
    search_btn.dispatch_event("mouseup")
    search_btn.dispatch_event("click")

    page.wait_for_timeout(5000)

    radio_count = page.locator("input[type='radio']").count()
    print("Radio count:", radio_count)

    if radio_count == 0:
        page.screenshot(path="dupa_cautare.png", full_page=True)
        print("❌ Nu au apărut rezultate. Verifică dupa_cautare.png")
        return

    radio_buttons = page.locator("input[type='radio']")
    count = radio_buttons.count()

    json_paths = []

    for i in range(count):

        print(f"⬇️ Descarc document {i + 1}/{count}")

        radio = radio_buttons.nth(i)
        radio.check(force=True)

        with page.expect_download(timeout=60000) as download_info:
            page.locator(
                "#commonCompaniesListComponent_searchArticleButton"
            ).click()

        download = download_info.value

        path = DATA_DIR / f"{cui}_{i + 1}.pdf"

        download.save_as(path)

        print(f"✅ PDF salvat: {path}")

        json_path = pdf_to_json(path)

        print(f"✅ Conversie terminată: {json_path}")

        json_paths.append(json_path)

        page.wait_for_timeout(1000)

    return json_paths


def descarca_pdf_firma(context, cui: str):
    cui = cui.strip()

    page = gaseste_sau_deschide_berc(context)
    json_path = completeaza_si_descarca_pdf(page, cui)

    return json_path


if __name__ == "__main__":
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=EDGE_PROFILE,
            executable_path=EDGE_PATH,
            headless=True,  # pune True dacă merge complet în background
            accept_downloads=True,
            args=[
                "--window-position=-32000,-32000",
                "--window-size=1200,900"
            ]
        )

        while True:
            cui = input("Introdu CUI sau exit: ").strip()

            if cui.lower() in ["exit", "quit", "q"]:
                break

            if not cui:
                continue

            descarca_pdf_firma(context, cui)

        context.close()