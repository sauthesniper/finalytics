# ONRC Automation Pipeline

This project automates the retrieval, conversion, and extraction of corporate data from the BERC (Buletinul Electronic al Registrului Comerțului) portal.

## Workflow Instructions

To process a company's data, follow these steps in order. Ensure your environment is set up and the necessary Python libraries are installed.

### 1. Retrieve Metadata

Run the script to collect the initial listing of records for the target company.

```bash
python descarca_firma.py
```

**Input:** Enter the desired CUI.

**Finish:** Input `"exit"` when prompted to stop the script.

### 2. Download Publications

Download the corresponding PDF files based on the records collected.

```bash
python descarca_buletine.py
```

**Input:** Enter the same CUI.

**Action:** The script will automatically filter, access the portal, and download the relevant PDFs into the `data_pdf/<CUI>/` directory. Please wait for the script to finish all downloads.

### 3. Data Conversion

Transform the downloaded PDF files into a machine-readable JSON format.

```bash
python pdf_to_json.py
```

**Input:** Enter the CUI.

**Action:** This will parse the PDFs and create structured JSON files in `data_json/<CUI>/`, making the data ready for further extraction and analysis.

## Directory Structure Reference

The scripts maintain the following organization to ensure your data is processed reliably:

- `data_pdf/` — Stores raw PDF files organized by CUI subfolders.
- `data_json/` — Stores raw extracted text (as line lists) from the PDFs.

## Prerequisites

Ensure you have the following installed:

- Playwright:

  ```bash
  pip install playwright
  playwright install
  ```

- pdfplumber:

  ```bash
  pip install pdfplumber
  ```
