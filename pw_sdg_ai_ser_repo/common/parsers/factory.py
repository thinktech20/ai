"""Parser factory for method-based parser selection.

Supported methods:
- foundation (HTTP service)
- pdfplumber (local extraction)
- databricks_ai (Databricks native, requires DBR)
- auto (legacy fallback)
"""
from __future__ import annotations

from contracts.interfaces.parsers import DocumentParser

from .auto_parser import AutoParser
from .databricks_ai_parser import DatabricksAIParser
from .foundation_parser import FoundationParser
from .pdfplumber_parser import PdfPlumberParser


def build_parser(method: str = "auto") -> DocumentParser:
    method_key = (method or "auto").strip().lower()
    if method_key == "foundation":
        return FoundationParser()
    if method_key == "pdfplumber":
        return PdfPlumberParser()
    if method_key == "databricks_ai":
        return DatabricksAIParser()
    if method_key == "auto":
        return AutoParser()
    raise ValueError(f"Unsupported parser method: {method}. Expected foundation, pdfplumber, databricks_ai, or auto.")
