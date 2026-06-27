"""Job B: Bronze ingestion / discovery.

Scans the upstream Bronze Volume, computes source_hash + uniqueness key, and
inserts new documents into the Silver registry with all stage statuses set to
`pending`. Re-runs are idempotent on (source_hash, selected source attributes).
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, pipeline_run_id: str) -> None:
    """Discover new documents in Bronze and seed Silver registry rows.

    Steps (to be implemented by the adapter layer):
      1. Open audit row (job_bronze_ingestion).
      2. Open MLflow run, log run_mode and input_scope as parameters.
      3. List the Bronze Volume scope and compute source_hash per file.
      4. MERGE into the Silver registry on unique_key; new rows start with
        metadata_status=pending and chunk_status=pending.
      5. Log discovered/new/skipped counts as MLflow metrics.
      6. Close audit row.
    """
    raise NotImplementedError
