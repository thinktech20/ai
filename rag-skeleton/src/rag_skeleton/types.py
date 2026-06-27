"""Domain types passed between pipeline stages.

These are framework-agnostic dataclasses. Adapters convert to/from Spark
rows, Delta tables, or external services at the boundary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Document:
    """A raw document discovered in the Bronze landing layer."""

    document_id: str
    source_path: str
    source_hash: str
    source_metadata: dict[str, Any] = field(default_factory=dict)
    discovered_ts: datetime | None = None


@dataclass(frozen=True)
class ExtractedMetadata:
    """Output of the parser stage (Silver)."""

    document_id: str
    fields: dict[str, Any]
    elements: list[dict[str, Any]] = field(default_factory=list)
    parser_version: str = ""
    quality_signals: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """A retrieval unit produced by the chunker (pre-embedding)."""

    chunk_id: str
    document_id: str
    text: str
    chunk_type: str = "text"
    section_path: str | None = None
    page_span: tuple[int, int] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkWithEmbedding:
    """Chunk plus its embedding vector (Gold)."""

    chunk: Chunk
    embedding: list[float]
    embedding_model: str
    embedding_model_version: str


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk returned from a retriever, plus its similarity score."""

    chunk: Chunk
    score: float
    retrieval_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GenerationResult:
    """Output of the generator stage (LLM call) in a RAG flow."""

    answer: str
    citations: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
