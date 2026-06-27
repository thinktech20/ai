"""Retriever contract — query -> top-k relevant chunks.

The retriever is the runtime/serving counterpart to the batch indexing path.
Pipeline jobs do not call it; consumer-facing surfaces (a PyFunc wrapper, a
serving endpoint, downstream apps) do.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ..config import VectorStoreConfig
from ..types import RetrievedChunk


@dataclass(frozen=True)
class RetrievalQuery:
    text: str
    top_k: int = 5
    filters: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Retriever(Protocol):
    """Look up relevant chunks for a query.

    Implementations: Databricks Vector Search retriever, hybrid (vector + BM25),
    metadata-filtered retrievers, etc.
    """

    config: VectorStoreConfig

    def retrieve(self, query: RetrievalQuery) -> list[RetrievedChunk]: ...
