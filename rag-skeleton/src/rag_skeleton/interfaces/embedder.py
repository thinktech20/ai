"""Embedder contract — chunks -> vectors."""
from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from ..config import EmbedderConfig
from ..types import Chunk, ChunkWithEmbedding


@runtime_checkable
class Embedder(Protocol):
    """Generate embedding vectors for chunks.

    Implementations: Databricks foundation model embeddings, OSS models, etc.
    """

    config: EmbedderConfig

    def embed(self, chunks: Iterable[Chunk]) -> Iterable[ChunkWithEmbedding]: ...
