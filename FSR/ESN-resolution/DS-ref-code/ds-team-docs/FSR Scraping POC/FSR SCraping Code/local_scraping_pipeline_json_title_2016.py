%pip install pdfplumber

import os
import pdfplumber
import json

# -----------------------------
# Config
# -----------------------------
MAIN_PDF_FOLDER = "/Volumes/vgpd/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/"
OUTPUT_JSON = "/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/n_pdfs_extracted_title_2016_Vinayaka_230.json"
MAX_PDFS = None   # <-- no limit, process all PDFs

# -----------------------------
# Flexible Extraction with Multi-line Support + Title
# -----------------------------
def extract_fields_from_pdf(pdf_path):
    fields = {"PDF Name / path / identifier": pdf_path}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()

            if text:
                lines = text.splitlines()
                current_key = None

                # --- Capture title (first 2–3 lines before any colon fields) ---
                title_lines = []
                for line in lines:
                    if ":" in line:
                        break
                    title_lines.append(line.strip())
                if title_lines:
                    fields["Title"] = " ".join(title_lines)

                # --- Process key:value fields ---
                for line in lines:
                    if ":" in line:
                        parts = line.split(":", 1)
                        key = parts[0].strip()
                        value = parts[1].strip()

                        current_key = key
                        if key in fields:
                            fields[key] = f"{fields[key]} | {value}"
                        else:
                            fields[key] = value
                    else:
                        if current_key:
                            fields[current_key] += " " + line.strip()

    except Exception as e:
        print(f"Error extracting {pdf_path}: {e}")

    return fields

# -----------------------------
# Main Pipeline
# -----------------------------
def main():
    results = []
    count = 0

    for root, dirs, files in os.walk(MAIN_PDF_FOLDER):
        for filename in files:
            if filename.lower().endswith(".pdf"):
                if MAX_PDFS and count >= MAX_PDFS:
                    print(f"Reached limit of {MAX_PDFS} PDFs. Stopping.")
                    break

                pdf_path = os.path.join(root, filename)
                print(f"Processing: {pdf_path}")
                data = extract_fields_from_pdf(pdf_path)
                results.append(data)
                count += 1
        if MAX_PDFS and count >= MAX_PDFS:
            break

    output = {"FSR_data": results}

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    print(f"✅ Extraction complete. Processed {count} PDFs. Results saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    import time

    start_time = time.time()
    main()
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"Execution time: {execution_time} seconds")