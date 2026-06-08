"""Local test harness for PDF parsing and planning a Databricks proof of concept.

This script is intentionally minimal and educational:
- It verifies the sample PDF exists.
- It attempts a local content inspection if a PDF parser is installed.
- It includes a Databricks-ready parsing template using ai_parse_document.

Run locally with:
    python3 dbx-playground/test_parse_pdf.py

If you want to run the Databricks portion, copy the relevant code into a Databricks notebook cell.
"""

from pathlib import Path
import sys

PDF_PATH = Path(__file__).resolve().parent / "sample-pdf" / "TIL 1603-R2 - R0 EROSION AND WATER INGESTION RECOMMENDATIONS.pdf"


def print_header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80 + "\n")


def verify_pdf():
    print_header("Step 1: Verify sample PDF")
    print(f"Sample PDF path: {PDF_PATH}")
    print(f"Exists: {PDF_PATH.exists()}")
    print(f"Size: {PDF_PATH.stat().st_size if PDF_PATH.exists() else 'N/A'} bytes")
    print(f"Python: {sys.version.split()[0]}")


def inspect_locally():
    print_header("Step 2: Local inspection")
    try:
        import PyPDF2
    except ModuleNotFoundError:
        print("PyPDF2 is not installed locally.")
        print("To inspect text locally, install it with: python3 -m pip install PyPDF2")
        return

    print("PyPDF2 is installed. Extracting first page text preview...\n")
    with open(PDF_PATH, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        print(f"Number of pages: {len(reader.pages)}")
        if len(reader.pages) > 0:
            page = reader.pages[0]
            text = page.extract_text() or ""
            print("First page text preview (first 500 chars):")
            print("-" * 40)
            print(text[:500].strip())
            print("-" * 40)


def print_databricks_template():
    print_header("Step 3: Databricks parsing template")
    print("Use this in a Databricks notebook once the PDF is accessible in DBFS or a volume.\n")
    print("# Databricks Python example")
    print("from pyspark.sql.functions import expr")
    print("docs_df = spark.read.format('binaryFile').load('<pdf-directory-path>')")
    print('parsed_df = docs_df.withColumn("parsed_content", expr("ai_parse_document(content, map(\"version\", \"2.0\", \"imageOutputPath\", \"<output-path>/parsed_images/\"))"))')
    print("parsed_df = parsed_df.drop('content')")
    print("display(parsed_df)")
    print("\nThen inspect nested fields like parsed_content:document:pages and parsed_content:metadata.")


def main():
    verify_pdf()
    inspect_locally()
    print_databricks_template()


if __name__ == '__main__':
    main()
