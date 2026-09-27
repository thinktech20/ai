"""Shared parser adapters usable across pipelines.

Keep optional legacy parser imports lazy so pipelines that only need a concrete
parser adapter do not fail on missing contract-interface modules.
"""

from .databricks_ai_parser import DatabricksAIParser
from .foundation_parser import FoundationParser
from .pdfplumber_parser import PdfPlumberParser

try:
    from .auto_parser import AutoParser
    from .factory import build_parser
except ModuleNotFoundError as exc:
    if exc.name != "contracts.interfaces":
        raise

    AutoParser = None

    def build_parser(method: str = "auto"):
        method_key = (method or "auto").strip().lower()
        if method_key == "foundation":
            return FoundationParser()
        if method_key == "pdfplumber":
            return PdfPlumberParser()
        if method_key == "databricks_ai":
            return DatabricksAIParser()
        raise ModuleNotFoundError(
            "contracts.interfaces is not available in this repo checkout. "
            "Only foundation, pdfplumber, and databricks_ai parsers can be imported here."
        ) from exc


__all__ = [
    "FoundationParser",
    "PdfPlumberParser",
    "DatabricksAIParser",
    "AutoParser",
    "build_parser",
]
