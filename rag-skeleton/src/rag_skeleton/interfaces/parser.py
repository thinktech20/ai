"""Parser contract — Bronze binary -> structured metadata."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..config import ParserConfig
from ..types import Document, ExtractedMetadata


@runtime_checkable
class DocumentParser(Protocol):
    """Extract structured metadata and elements from a raw document.

    Implementations: ai_parse_document adapter, custom DS parser, etc.
    """

    config: ParserConfig

    def parse(self, document: Document, payload: bytes) -> ExtractedMetadata: ...
