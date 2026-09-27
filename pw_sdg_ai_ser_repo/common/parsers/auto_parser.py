"""Auto parser strategy.

Matches DS behavior: try foundation first, then pdfplumber fallback.
"""
from __future__ import annotations

from contracts.interfaces.parsers import DocumentParser
from contracts.types.entities import DocumentReference, ExtractedProfile

from .foundation_parser import FoundationParser
from .pdfplumber_parser import PdfPlumberParser


class AutoParser(DocumentParser):
    name = "auto"
    version = "v0"

    def __init__(self, primary: DocumentParser | None = None, fallback: DocumentParser | None = None) -> None:
        self.primary = primary or FoundationParser()
        self.fallback = fallback or PdfPlumberParser()

    def parse(self, document: DocumentReference, payload: bytes) -> ExtractedProfile:
        try:
            return self.primary.parse(document, payload)
        except Exception:
            return self.fallback.parse(document, payload)
