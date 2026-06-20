import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

# --- CONFIGURATION ---
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
EDGE_PROFILE = r"C:\temp\edge_onrc_profile"
LOGIN_URL = "https://sso.onrc.ro/realms/onrc/protocol/openid-connect/auth?client_id=frontoffice-app&redirect_uri=https%3A%2F%2Fmyportal.onrc.ro%2Fhome&response_mode=fragment&response_type=code&scope=openid&ui_locales=ro"
FILTER_URL = "https://portal.berc.onrc.ro/view-publication/filter-publication"
USERNAME = "finbotv1"
PASSWORD = "L0remIpsum*"
BASE_DATA_DIR = Path("data_pdf")
JSON_DIR = Path("data_json")

async def login_and_open_berc(context):
    page = await context.new_page()
    await page.goto(LOGIN_URL)
    
    if "sso.onrc.ro" in page.url:
        await page.locator("#username").fill(USERNAME)
        await page.locator("#password").fill(PASSWORD)
        await page.locator("#kc-login").click()

    while "myportal.onrc.ro/home" not in page.url:
        await asyncio.sleep(1)
    
    async with context.expect_page() as new_page_info:
        await page.get_by_text("Buletinul Electronic al Registrului Comerțului", exact=False).click()
    berc_page = await new_page_info.value
    
    await berc_page.goto(FILTER_URL)
    await berc_page.wait_for_load_state("networkidle")
    
    await page.close()
    return berc_page

async def main():
    cui = input("Introdu CUI: ").strip()
    
    # Folder and log setup
    cui_folder = BASE_DATA_DIR / cui
    cui_folder.mkdir(parents=True, exist_ok=True)
    log_file = cui_folder / "downloads.txt"
    
    # Read already downloaded files
    downloaded_files = set()
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            downloaded_files = {line.strip() for line in f if line.strip()}
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=EDGE_PROFILE, 
            executable_path=EDGE_PATH, 
            headless=False,
            accept_downloads=True
        )
        
        berc_page = await login_and_open_berc(context)
        
        records = []
        for path in JSON_DIR.glob(f"{cui}*.json"):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for row in data.get("tabel_articole_publicate", {}).get("randuri", []):
                    records.append({"numar": row["numar_buletin"], "an": row["data_buletin"].split(".")[-1]})

        for rec in records:
            file_id = f"{rec['numar']}_{rec['an']}"
            
            # Skip if already in downloads.txt
            if file_id in downloaded_files:
                print(f"⏩ Deja descărcat: {file_id}. Sar peste.")
                continue

            print(f"🔄 Procesez: {file_id}")
            try:
                await berc_page.locator("#commonPublicationFilter_numberInput").fill(rec['numar'])
                await berc_page.locator("input[formcontrolname='year']").fill(rec['an'])
                await berc_page.locator("button:has-text('Cauta')").click()
                await berc_page.wait_for_timeout(2000)
                
                await berc_page.locator("mat-expansion-panel").first.click()
                
                async with context.expect_page() as new_page_info:
                    btn = berc_page.locator("#clientFilterPublication_downloadPublication")
                    if await btn.count() == 0:
                        btn = berc_page.locator("button:has-text('Descarcă')")
                    await btn.first.click()
                
                new_page = await new_page_info.value
                await new_page.wait_for_load_state("networkidle")
                
                await new_page.keyboard.press("Control+s")
                
                async with new_page.expect_download() as download_info:
                    await asyncio.sleep(2)
                
                download = await download_info.value
                # Saving to the specific CUI folder
                await download.save_as(cui_folder / f"{cui}_{file_id}.pdf")
                
                # Update log file
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"{file_id}\n")
                downloaded_files.add(file_id)
                
                await new_page.close()
                print(f"✅ Salvat: {file_id}")
                
            except Exception as e:
                print(f"❌ Eroare la {file_id}: {e}")
                await berc_page.goto(FILTER_URL)

        await context.close()

if __name__ == "__main__":
    asyncio.run(main())