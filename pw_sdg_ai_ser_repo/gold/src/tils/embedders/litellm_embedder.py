"""LiteLLM embedding adapter (scaffold)."""
from __future__ import annotations

from contracts.interfaces.embedders import Embedder
from contracts.types.entities import Chunk, ChunkWithEmbedding


class LiteLLMEmbedder(Embedder):
    def __init__(self, model_name: str, model_version: str = "v0") -> None:
        self.model_name = model_name
        self.model_version = model_version

    def embed(self, chunks: list[Chunk]) -> list[ChunkWithEmbedding]:
        raise NotImplementedError(
            "Implement LiteLLM /embeddings call and map vectors to ChunkWithEmbedding."
        )
