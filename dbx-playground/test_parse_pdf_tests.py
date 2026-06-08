from pathlib import Path
from PyPDF2 import PdfReader

PDF_PATH = Path('dbx-playground/sample-pdf/TIL 1603-R2 - R0 EROSION AND WATER INGESTION RECOMMENDATIONS.pdf')


def test_pdf_exists():
    assert PDF_PATH.exists(), f"PDF file not found: {PDF_PATH}"


def test_pdf_is_readable():
    reader = PdfReader(PDF_PATH)
    assert len(reader.pages) > 0, "PDF should contain at least one page"


def test_first_page_has_text():
    reader = PdfReader(PDF_PATH)
    first_text = reader.pages[0].extract_text() or ''
    assert first_text.strip(), "First page should contain extractable text"
