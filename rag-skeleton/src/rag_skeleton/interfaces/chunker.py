"""Chunker contract — extracted metadata/elements -> retrieval chunks."""
from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from ..config import ChunkerConfig
from ..types import Chunk, ExtractedMetadata


@runtime_checkable
class Chunker(Protocol):
    """Produce retrieval-ready chunks from parsed output.

    Implementations: section-based, semantic, table-aware, formula-aware, etc.
    """

    config: ChunkerConfig

    def chunk(self, metadata: ExtractedMetadata) -> Iterable[Chunk]: ...
