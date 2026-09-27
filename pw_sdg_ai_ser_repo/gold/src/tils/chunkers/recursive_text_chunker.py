"""Baseline recursive text chunker (scaffold).

Uses profile text fields to build chunks. Keep this adapter small and
replaceable so chunk strategy can evolve without pipeline rewrites.
"""
from __future__ import annotations

import hashlib
from typing import Iterable

from contracts.interfaces.chunkers import Chunker
from contracts.types.entities import Chunk, ExtractedProfile


class RecursiveTextChunker(Chunker):
    name = "recursive_text"
    version = "v0"

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, profile: ExtractedProfile) -> list[Chunk]:
        # Minimal baseline scaffold: chunk only `raw_text` if present.
        # Replace with structure-aware chunking once parser output stabilizes.
        raw_text = str(profile.fields.get("raw_text") or "").strip()
        if not raw_text:
            return []

        pieces = list(self._sliding_window(raw_text, self.chunk_size, self.chunk_overlap))
        chunks: list[Chunk] = []
        for idx, text in enumerate(pieces):
            chunk_id = hashlib.sha1(f"{profile.document_id}:{idx}:{text}".encode("utf-8")).hexdigest()[:16]
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=profile.document_id,
                    text=text,
                    chunk_type="text",
                    section_path=None,
                    metadata={"chunk_index": idx, "chunker": self.name, "chunker_version": self.version},
                )
            )
        return chunks

    @staticmethod
    def _sliding_window(text: str, size: int, overlap: int) -> Iterable[str]:
        if size <= 0:
            return []
        step = max(1, size - max(0, overlap))
        return (text[start : start + size] for start in range(0, len(text), step))
