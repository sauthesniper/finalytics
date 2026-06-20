import pdfplumber
import json
from pathlib import Path

def pdf_to_json(cui: str):
    # Setup paths
    input_folder = Path("data_pdf") / cui
    output_folder = Path("data_json") / cui
    output_folder.mkdir(parents=True, exist_ok=True)
    
    if not input_folder.exists():
        print(f"❌ Folderul {input_folder} nu există.")
        return

    pdf_files = list(input_folder.glob("*.pdf"))
    if not pdf_files:
        print(f"⚠️ Nu am găsit fișiere PDF în {input_folder}")
        return

    for pdf_path in pdf_files:
        print(f"📄 Procesez: {pdf_path.name}")
        
        # We use a list of lines instead of one giant string
        raw_data = {"filename": pdf_path.name, "lines": []}
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                lines = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        # Split by newline so each line is its own list entry
                        lines.extend(text.split('\n'))
                
                raw_data["lines"] = lines
            
            # Save as JSON
            json_filename = output_folder / f"{pdf_path.stem}.json"
            with open(json_filename, "w", encoding="utf-8") as f:
                json.dump(raw_data, f, ensure_ascii=False, indent=4)
            
            print(f"✅ Salvat (format listă): {json_filename}")
            
        except Exception as e:
            print(f"❌ Eroare la procesarea {pdf_path.name}: {e}")

if __name__ == "__main__":
    cui_input = input("Introdu CUI pentru conversie: ").strip()
    pdf_to_json(cui_input)