"""pdfplumber parser adapter for TIL profile extraction.

Extracts text and tables from a PDF using pdfplumber, with optional OCR for
image-heavy pages. Mirrors the logic in:
  SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/til_pdf_utils.py
  (_extract_text_from_pdf_path)
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

from contracts.types.entities import DocumentReference, ExtractedProfile


def _strip_boilerplate(text: str) -> str:
    """Remove common PDF footer/header boilerplate lines."""
    skip_patterns = re.compile(
        r"(GE Proprietary Information|UNCONTROLLED WHEN PRINTED|"
        r"Technical Information Letter|Page \d+ of \d+)",
        re.IGNORECASE,
    )
    lines = [l for l in text.splitlines() if not skip_patterns.search(l)]
    return "\n".join(lines).strip()


def _extract_table_text(page: Any) -> str:
    """Extract tables from a pdfplumber page as readable text."""
    tables = page.extract_tables() or []
    parts: list[str] = []
    for table in tables:
        rows = [
            " | ".join((cell or "").strip() for cell in row)
            for row in (table or [])
            if any(cell and cell.strip() for cell in row)
        ]
        if rows:
            parts.append("\n".join(rows))
    return "\n\n".join(parts) if parts else ""


class PdfPlumberParser:
    name = "pdfplumber"
    version = "v0"

    def __init__(
        self,
        max_text_chars: int = 40000,
        max_pages: int = 12,
    ) -> None:
        self.max_text_chars = max_text_chars
        self.max_pages = max_pages

    def parse(self, document: DocumentReference, payload: bytes) -> ExtractedProfile:
        text, tables = self._extract(payload)
        text = text[: self.max_text_chars]
        return ExtractedProfile(
            document_id=document.document_id,
            fields={
                "raw_text":          text,
                "raw_tables":        tables,
                "extraction_method": self.name,
                "table_count":       len(tables),
                "char_count":        len(text),
            },
            elements=[
                {"element_type": "table", "element_text": t}
                for t in tables
            ],
            parser_name=self.name,
            parser_version=self.version,
        )

    def _extract(self, pdf_bytes: bytes) -> tuple[str, list[str]]:
        try:
            import pdfplumber  # noqa: PLC0415 — optional dependency
        except ImportError as exc:
            raise ImportError(
                "pdfplumber is required for PdfPlumberParser. "
                "Install it with: %pip install pdfplumber"
            ) from exc

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            text_parts: list[str] = []
            table_parts: list[str] = []

            with pdfplumber.open(tmp_path) as pdf:
                for page_num, page in enumerate(
                    pdf.pages[: self.max_pages], start=1
                ):
                    raw_text = _strip_boilerplate(
                        (page.extract_text() or "").strip()
                    )
                    if raw_text:
                        text_parts.append(f"[Page {page_num}]\n{raw_text}")

                    table_text = _extract_table_text(page)
                    if table_text:
                        table_parts.append(table_text)

            return "\n\n".join(text_parts), table_parts
        finally:
            if tmp_path and Path(tmp_path).exists():
                Path(tmp_path).unlink(missing_ok=True)

