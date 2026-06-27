"""Job C: Silver metadata extraction.

Claims rows where metadata_status='pending', runs the configured parser,
writes extracted metadata to Silver, and transitions the row to 'completed'
or 'failed'.
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, pipeline_run_id: str) -> None:
    """Run the parser over the next batch of pending documents.

    Steps:
      1. Reset stale in_progress rows older than runtime.stale_claim_minutes.
      2. Claim a batch of metadata_status='pending' rows (size = runtime.batch_size).
      3. For each row:
         - load payload from Bronze Volume
         - call DocumentParser.parse(...)
         - upsert ExtractedMetadata into silver_til_metadata (or its generic equivalent)
         - mark metadata_status='completed' on success, 'failed' (with retry bump) on exception
      4. Log per-batch counts and parser_version to MLflow.
      5. Close audit row.
    """
    raise NotImplementedError
