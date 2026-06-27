"""Job F: Vector index sync trigger.

This is NOT a per-row claim/process job. The Vector Search index is a Delta
Sync index in self-managed-embeddings mode: Job D writes vectors to the Gold
chunk table, and this job triggers Delta Sync to propagate them to the index.

Pattern mirrors FSR's pw_sdg_fsr_vs_sync: explicit POST /sync at end of
pipeline plus a daily safety-net cron, instead of relying on auto-sync timing.

No vector_sync_status column is needed; sync is table-wide, one API call.
Validation gating is enforced before chunks land in the source table.
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, pipeline_run_id: str) -> None:
    """Trigger a sync of the configured Vector Search index.

    Steps (to be implemented by the adapter layer):
      1. Open audit row (job_til_vs_sync).
      2. Open MLflow run, log endpoint + index names.
      3. Verify endpoint is ONLINE (GET /api/2.0/vector-search/endpoints/{name}).
      4. Verify index exists (GET /api/2.0/vector-search/indexes/{index}).
      5. POST /api/2.0/vector-search/indexes/{index}/sync, with bounded retry
         on transient "endpoint warming" responses.
      6. Log sync trigger result to MLflow; close audit row.

    Sync trigger frequency must remain shorter than the source chunk table's
    delta.deletedFileRetentionDuration. The companion daily cron is configured
    on the job, not in this module.
    """
    raise NotImplementedError
