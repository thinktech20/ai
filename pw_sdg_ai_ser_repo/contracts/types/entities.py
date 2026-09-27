"""Shared data models used by parser/chunker/embedder/vector-store contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DocumentReference:
    document_id: str
    source_path: str
    source_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExtractedProfile:
    document_id: str
    fields: dict[str, Any]
    elements: list[dict[str, Any]] = field(default_factory=list)
    parser_name: str = ""
    parser_version: str = ""


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    chunk_type: str = "text"
    section_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkWithEmbedding:
    chunk: Chunk
    embedding: list[float]
    embedding_model: str
    embedding_model_version: str
