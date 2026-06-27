"""Vector store sink contract — publish validated Gold chunks to retrieval index."""
from __future__ import annotations

from typing import Iterable, Protocol, runtime_checkable

from ..config import VectorStoreConfig
from ..types import ChunkWithEmbedding


@runtime_checkable
class VectorStoreSink(Protocol):
    """Upsert and delete chunks in the target vector index.

    Implementations: Databricks Vector Search, external vector DBs, etc.
    """

    config: VectorStoreConfig

    def upsert(self, items: Iterable[ChunkWithEmbedding]) -> None: ...

    def delete(self, chunk_ids: Iterable[str]) -> None: ...
