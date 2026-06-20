import fitz
import json
import re
from pathlib import Path

PDF_DIR = Path("data_pdf")
JSON_DIR = Path("data_json")
JSON_DIR.mkdir(exist_ok=True)


def normalize_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def extract_field(text: str, label: str):
    pattern = rf"{re.escape(label)}:\s*(.*)"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return None


def extract_articles(lines):
    articles = []

    ignored = [
        "ARTICOLE PUBLICATE",
        "Articole publicate",
        "Categorie publicitate",
        "Număr cerere",
        "Număr buletin",
        "din data"
    ]

    buffer = []

    for line in lines:
        if any(x in line for x in ignored):
            continue

        buffer.append(line)

        combined = " ".join(buffer)

        matches = re.findall(r"(\d+)\/(\d{2}\.\d{2}\.\d{4})", combined)

        if len(matches) >= 2:
            request = matches[-2]
            bulletin = matches[-1]

            category = re.sub(
                r"\d+\/\d{2}\.\d{2}\.\d{4}",
                "",
                combined
            ).strip()

            category = re.sub(r"\s+", " ", category)

            articles.append({
                "categorie_publicitate": category,
                "numar_cerere": request[0],
                "data_cerere": request[1],
                "numar_buletin": bulletin[0],
                "data_buletin": bulletin[1]
            })

            buffer = []

    return articles


def pdf_to_json(pdf_path: Path):
    doc = fitz.open(pdf_path)

    all_pages = []
    all_lines = []

    for page_index, page in enumerate(doc):
        page_text = page.get_text()

        lines = [
            line.strip()
            for line in page_text.splitlines()
            if line.strip()
        ]

        all_pages.append({
            "page_number": page_index + 1,
            "lines": lines
        })

        all_lines.extend(lines)

    text = "\n".join(all_lines)

    # separă secțiuni
    header_lines = []
    article_lines = []
    company_lines = []

    section = "header"

    for line in all_lines:

        if "Categorie publicitate" in line:
            section = "articles"

        if "Denumire profesionist:" in line:
            section = "company"

        if section == "header":
            header_lines.append(line)

        elif section == "articles":
            article_lines.append(line)

        elif section == "company":
            company_lines.append(line)

    data = {
        "metadata": {
            "source_file": pdf_path.name,
            "pages": len(doc)
        },

        "document": {
            "titlu": all_lines[0] if all_lines else None,
            "tip_raport": "Articole publicate pentru un profesionist"
        },

        "profesionist": {
            "denumire": extract_field(text, "Denumire profesionist"),
            "numar_registrul_comertului": extract_field(
                text,
                "Număr de ordine în registrul comerțului"
            ),
            "euid": extract_field(
                text,
                "Identificator unic la nivel european (EUID)"
            ),
            "cui": extract_field(
                text,
                "Cod unic de înregistrare (CUI)"
            ),
            "adresa_sediu": extract_field(
                text,
                "Adresă sediu"
            )
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

    output_path = JSON_DIR / f"{pdf_path.stem}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON salvat: {output_path}")
    
if __name__ == "__main__":
    pdf_files = list(PDF_DIR.glob("*.pdf"))

    print("PDF_DIR =", PDF_DIR.resolve())
    print("PDF-uri găsite:", len(pdf_files))

    for pdf in pdf_files:
        print("Procesez:", pdf)
        pdf_to_json(pdf)