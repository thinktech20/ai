"""Method 1B — Download TIL PDF and extract with Foundation Service API.

Downloads TIL PDF from Databricks Volumes, sends to the GE Vernova
Foundation Service PDF extraction endpoint (Textract-based), which returns
structured text, tables, and image descriptions per page.

Usage (from repo root):
    python experiments/e6_2/read_1b_FoundationService.py
"""
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import sys
sys.path.insert(0, ".")

import json
from datetime import datetime
from pathlib import Path

import requests

from experiments.config import DB_HOST, DB_TOKEN
from experiments.e6_2.pdf_reader import list_til_pdfs, download_til_pdf

# ══════════════════════════════════════════════════════════════════════════════
# INPUT — Change these values
# ══════════════════════════════════════════════════════════════════════════════

TIL_BASE_NUM = "1603" #,1502, 1603, 2284

# Foundation Service settings
FOUNDATION_URL = "https://dev-genai-foundation.apps.gevernova.net/pdf/extract/"
PROJECT_ID = "9f3cbb78-48a9-45cc-a1f2-52c6d02b58a3"
PROCESS_MODE = "accuracy"  # "accuracy" or "speed"
MODE = "asynchronous"

# ══════════════════════════════════════════════════════════════════════════════

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def call_foundation_service(pdf_bytes: bytes, pdf_filename: str) -> dict:
    """Send PDF to Foundation Service and return extraction results."""
    files = {
        "file": (pdf_filename, pdf_bytes, "application/pdf"),
    }
    data = {
        "mode": MODE,
        "process_mode": PROCESS_MODE,
        "part_number": "",
        "model_name": "string",
    }
    headers = {
        "accept": "application/json",
        "project-id": PROJECT_ID,
    }

    response = requests.post(
        FOUNDATION_URL,
        headers=headers,
        files=files,
        data=data,
        verify=False,
        timeout=300,
        proxies={"http": "", "https": ""},
    )

    if response.status_code != 200:
        print(f"    ERROR: Foundation Service returned {response.status_code}")
        print(f"    {response.text[:500]}")
        return {}

    return response.json()


def parse_foundation_response(response: dict) -> tuple[str, list[dict]]:
    """Parse Foundation Service response into text content and labeled tables.

    Labeled tables (pages with explicit "Table N:" in text) go into tables_found.
    Everything else — text, images, and unlabeled tables — goes into text_content
    so that the profile LLM can see all available information.

    Returns:
        text_content: concatenated text + images + unlabeled tables from all pages
        tables: list of {page, label, source, content} dicts (labeled tables only)
    """
    import re

    results = response.get("results", {})
    text_pages = []
    tables_found = []

    for page_key in sorted(results.keys(), key=lambda x: int(x)):
        page_num = int(page_key)
        page_items = results[page_key]

        page_text = ""
        page_tables_raw = []
        page_images_raw = []

        for item in page_items:
            item_type = item.get("type", "")

            if item_type == "text":
                for content in item.get("content", []):
                    clean = content.strip()
                    if clean:
                        text_pages.append(clean)
                        page_text += clean + "\n"

            elif item_type == "table":
                for content in item.get("content", []):
                    clean = content.strip()
                    if clean and clean != "Extracted Tables:":
                        page_tables_raw.append({
                            "source": item.get("source", "textract"),
                            "content": clean,
                        })

            elif item_type == "image":
                for content in item.get("content", []):
                    clean = content.strip()
                    if clean:
                        page_images_raw.append(clean)

        # Labeled tables go to tables_found; unlabeled tables go to text_content
        label_match = re.search(r"(Table \d+):\s*(.+)", page_text)
        if label_match and page_tables_raw:
            label = label_match.group(1)
            description = label_match.group(2).strip()
            for tbl in page_tables_raw:
                tables_found.append({
                    "page": page_num,
                    "label": label,
                    "description": description,
                    "source": tbl["source"],
                    "content": tbl["content"],
                })
        elif page_tables_raw:
            for tbl in page_tables_raw:
                text_pages.append(f"[Unlabeled table from page {page_num}]\n{tbl['content']}")

        # Images always go into text_content
        for img_text in page_images_raw:
            text_pages.append(f"[Image description from page {page_num}]\n{img_text}")

    text_content = "\n\n".join(text_pages)
    return text_content, tables_found


def read_til_1b_foundation(til_base_num: str) -> dict:
    """Download TIL PDF and extract content via Foundation Service."""

    # Step 1: Find and download PDF from Volumes
    print(f"[1] Searching for PDF matching TIL base number: {til_base_num}")
    pdf_paths = list_til_pdfs(til_base_num, DB_HOST, DB_TOKEN)

    if not pdf_paths:
        print("    ERROR: No PDF found in Volumes.")
        return {"status": "pdf_not_found", "til_base_num": til_base_num}

    pdf_path = pdf_paths[0]
    print(f"    Found: {pdf_path}")

    pdf_bytes = download_til_pdf(pdf_path, DB_HOST, DB_TOKEN)
    if pdf_bytes is None:
        print("    ERROR: Failed to download PDF.")
        return {"status": "pdf_download_failed", "til_base_num": til_base_num}

    print(f"    Downloaded: {len(pdf_bytes)} bytes")

    # Step 2: Send to Foundation Service
    pdf_filename = pdf_path.split("/")[-1] if "/" in pdf_path else f"TIL_{til_base_num}.pdf"
    print(f"[2] Sending to Foundation Service ({PROCESS_MODE} mode)...")
    print(f"    URL: {FOUNDATION_URL}")
    print(f"    File: {pdf_filename}")

    response = call_foundation_service(pdf_bytes, pdf_filename)
    if not response:
        return {"status": "foundation_service_error", "til_base_num": til_base_num}

    status = response.get("status", "unknown")
    print(f"    Status: {status}")

    # Step 3: Parse response
    print(f"[3] Parsing extraction results...")
    text_content, tables_found = parse_foundation_response(response)
    print(f"    Text length: {len(text_content)} chars")
    print(f"    Tables found: {len(tables_found)}")
    for t in tables_found:
        print(f"      Page {t['page']}, {t['label']}: {t['description']}")

    # Step 4: Save results (grouped by TIL base number)
    til_dir = RESULTS_DIR / til_base_num
    til_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save text
    text_path = til_dir / f"1b_foundation_{til_base_num}_{timestamp}_text.json"
    text_data = {
        "method": "1b_foundation_service",
        "til_base_num": til_base_num,
        "pdf_path": pdf_path,
        "pdf_size_bytes": len(pdf_bytes),
        "text_length": len(text_content),
        "tables_count": len(tables_found),
        "text_content": text_content,
    }
    text_path.write_text(json.dumps(text_data, indent=2), encoding="utf-8")

    # Save tables separately
    tables_path = til_dir / f"1b_foundation_{til_base_num}_{timestamp}_tables.json"
    tables_data = {
        "til_base_num": til_base_num,
        "pdf_path": pdf_path,
        "tables": tables_found,
    }
    tables_path.write_text(json.dumps(tables_data, indent=2), encoding="utf-8")

    # Save raw Foundation Service response
    raw_path = til_dir / f"1b_foundation_{til_base_num}_{timestamp}_raw.json"
    raw_path.write_text(json.dumps(response, indent=2), encoding="utf-8")

    print(f"[4] Saved:")
    print(f"    Text:   {text_path}")
    print(f"    Tables: {tables_path}")
    print(f"    Raw:    {raw_path}")

    return {"text_data": text_data, "tables_data": tables_data}


if __name__ == "__main__":
    result = read_til_1b_foundation(TIL_BASE_NUM)
    if "text_data" in result:
        print(f"\nDone. Text: {result['text_data']['text_length']} chars, Tables: {result['text_data']['tables_count']}")
