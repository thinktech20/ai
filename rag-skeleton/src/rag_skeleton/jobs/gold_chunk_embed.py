"""Job D: Gold chunking + embedding.

Claims rows where metadata_status='completed' AND chunk_status='pending',
runs Chunker -> Embedder, writes Gold chunks with embeddings, and transitions
chunk_status.
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, pipeline_run_id: str) -> None:
    """Chunk + embed eligible documents.

    Steps:
      1. Reset stale in_progress rows.
      2. Claim batch of (metadata_status='completed', chunk_status='pending').
      3. For each row:
         - load ExtractedMetadata from Silver
         - call Chunker.chunk(...)
         - call Embedder.embed(...)
         - upsert ChunkWithEmbedding rows into gold_til_chunks (or generic equivalent)
         - mark chunk_status='completed' / 'failed'
      4. Log chunker/embedder versions, chunk count, embed latency to MLflow.
      5. Close audit row.
    """
    raise NotImplementedError
