"""Databricks Vector Search Delta Sync trigger adapter."""
from __future__ import annotations

from contracts.interfaces.vector_stores import VectorStore
from contracts.types.entities import ChunkWithEmbedding


class DatabricksDeltaSyncStore(VectorStore):
    def __init__(self, index_name: str, endpoint_name: str) -> None:
        self.index_name = index_name
        self.endpoint_name = endpoint_name

    def upsert(self, items: list[ChunkWithEmbedding]) -> None:
        # In Delta Sync mode, rows are written to Delta table first.
        # Index sync picks them up via explicit sync trigger.
        _ = items
        return None

    def sync(self) -> None:
        raise NotImplementedError(
            "Implement POST /api/2.0/vector-search/indexes/{index}/sync trigger."
        )
