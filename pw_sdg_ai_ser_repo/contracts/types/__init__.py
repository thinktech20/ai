"""Typed entities used across pipeline contracts."""

from .entities import Chunk, ChunkWithEmbedding, DocumentReference, ExtractedProfile

__all__ = [
    "DocumentReference",
    "ExtractedProfile",
    "Chunk",
    "ChunkWithEmbedding",
]
