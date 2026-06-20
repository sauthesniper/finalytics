"""
BERC Module API - FastAPI wrapper for ONRC BERC PDF download and parsing.
"""
import os
import json
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from pdf_to_json import pdf_to_json, extract_field, extract_articles
import fitz


app = FastAPI(
    title="BERC Module API",
    description="Downloads and parses ONRC BERC reports by CUI",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config from env
ONRC_USERNAME = os.getenv("ONRC_USERNAME", "finbotv1")
ONRC_PASSWORD = os.getenv("ONRC_PASSWORD", "L0remIpsum*")
BROWSER_PROFILE = os.getenv("BROWSER_PROFILE", "/tmp/berc_profile")

LOGIN_URL = "https://sso.onrc.ro/realms/onrc/protocol/openid-connect/auth?client_id=frontoffice-app&redirect_uri=https%3A%2F%2Fmyportal.onrc.ro%2Fhome&response_mode=fragment&response_type=code&scope=openid&ui_locales=ro"
REPORT_GENERATION_URL = "https://portal.berc.onrc.ro/report-generation"

DATA_DIR = Path("/app/data_pdf")
DATA_DIR.mkdir(parents=True, exist_ok=True)


class BercRequest(BaseModel):
    cui: str


class BercResponse(BaseModel):
    cui: str
    status: str
    profesionist: Optional[dict] = None
    tabel_articole_publicate: Optional[dict] = None
    metadata: Optional[dict] = None
    error: Optional[str] = None


def download_berc_pdf(cui: str) -> Path:
    """Download BERC PDF for a given CUI using Playwright."""
    cui = cui.strip()
    pdf_path = DATA_DIR / f"{cui}.pdf"

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE,
            headless=True,
            accept_downloads=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1200,900"
            ]
        )

        page = context.new_page()

        # Login
        page.goto(LOGIN_URL, timeout=30000)
        page.wait_for_load_state("networkidle")

        if "myportal.onrc.ro/home" in page.url:
            pass  # already logged in
        else:
            page.locator("#username").wait_for(state="visible", timeout=30000)
            page.locator("#username").fill(ONRC_USERNAME)
            page.locator("#password").fill(ONRC_PASSWORD)
            page.locator("#kc-login").click()
            page.wait_for_url("**://myportal.onrc.ro/home**", timeout=60000)
            page.wait_for_load_state("networkidle")

        # Open BERC
        try:
            with page.context.expect_page(timeout=30000) as new_page_info:
                page.get_by_text(
                    "Buletinul Electronic al Registrului Comerțului",
                    exact=False
                ).click()
            berc_page = new_page_info.value
            berc_page.wait_for_load_state("networkidle")
        except PlaywrightTimeoutError:
            berc_pages = [
                tab for tab in page.context.pages
                if not tab.is_closed() and "portal.berc.onrc.ro" in tab.url
            ]
            if not berc_pages:
                context.close()
                raise Exception("Could not open BERC tab")
            berc_page = berc_pages[-1]

        berc_page.bring_to_front()
        berc_page.goto(REPORT_GENERATION_URL)
        berc_page.wait_for_load_state("networkidle")

        # Fill form
        berc_page.locator(".mat-select-trigger").first.click()
        berc_page.locator(
            "mat-option:has-text('Articole publicate pentru un profesionist')"
        ).click()

        cui_input = berc_page.locator("#commonRcsearching_fiscalCode")
        cui_input.wait_for(state="visible", timeout=30000)
        cui_input.click()
        berc_page.keyboard.press("Control+A")
        berc_page.keyboard.press("Backspace")

        for ch in cui:
            berc_page.keyboard.type(ch)
            berc_page.wait_for_timeout(30)

        # Search
        search_btn = berc_page.locator("#commonRcsearching_showButton")
        search_btn.wait_for(state="visible", timeout=30000)
        search_btn.scroll_into_view_if_needed()
        search_btn.dispatch_event("mouseover")
        search_btn.dispatch_event("mousedown")
        search_btn.dispatch_event("mouseup")
        search_btn.dispatch_event("click")

        berc_page.wait_for_timeout(5000)

        radio_count = berc_page.locator("input[type='radio']").count()

        if radio_count == 0:
            context.close()
            raise Exception(f"No results found for CUI {cui}")

        berc_page.locator("input[type='radio']").first.check(force=True)

        # Download
        with berc_page.expect_download(timeout=60000) as download_info:
            berc_page.locator(
                "#commonCompaniesListComponent_searchArticleButton"
            ).click()

        download = download_info.value
        download.save_as(str(pdf_path))

        context.close()

    return pdf_path


def parse_berc_pdf(pdf_path: Path) -> dict:
    """Parse a BERC PDF into structured JSON."""
    doc = fitz.open(str(pdf_path))

    all_lines = []
    for page in doc:
        page_text = page.get_text()
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        all_lines.extend(lines)

    text = "\n".join(all_lines)

    data = {
        "metadata": {
            "source_file": pdf_path.name,
            "pages": len(doc)
        },
        "profesionist": {
            "denumire": extract_field(text, "Denumire profesionist"),
            "numar_registrul_comertului": extract_field(
                text, "Număr de ordine în registrul comerțului"
            ),
            "euid": extract_field(
                text, "Identificator unic la nivel european (EUID)"
            ),
            "cui": extract_field(text, "Cod unic de înregistrare (CUI)"),
            "adresa_sediu": extract_field(text, "Adresă sediu")
        },
        "tabel_articole_publicate": {
            "coloane": [
                "categorie_publicitate",
                "numar_cerere",
                "data_cerere",
                "numar_buletin",
                "data_buletin"
            ],
            "randuri": extract_articles(all_lines)
        }
    }

    doc.close()
    return data


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/berc/{cui}")
def get_berc_report(cui: str):
    """Download and parse BERC report for a given CUI."""
    cui = cui.strip()

    if not cui.isdigit():
        raise HTTPException(status_code=400, detail="CUI must be numeric")

    # Check if we already have the PDF cached
    pdf_path = DATA_DIR / f"{cui}.pdf"

    try:
        if not pdf_path.exists():
            pdf_path = download_berc_pdf(cui)

        data = parse_berc_pdf(pdf_path)

        return BercResponse(
            cui=cui,
            status="found",
            profesionist=data["profesionist"],
            tabel_articole_publicate=data["tabel_articole_publicate"],
            metadata=data["metadata"],
            error=None
        )

    except Exception as e:
        return BercResponse(
            cui=cui,
            status="error",
            error=str(e)
        )
