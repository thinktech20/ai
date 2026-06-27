"""Job G: Query-time RAG flow (serving runtime shell).

This job models the online request path as a reusable skeleton (still no concrete
I/O): user query -> retrieve -> generate -> evaluate response quality signal.

It is intentionally independent from batch indexing jobs (B-F) so serving can
scale and evolve separately.
"""
from __future__ import annotations

from ..config import PipelineConfig


def run(config: PipelineConfig, request_id: str, user_query: str) -> None:
    """Execute the online RAG path for one request.

    Steps (to be implemented by adapters):
      1. Open audit row (job_til_query_rag) and MLflow run with request metadata.
      2. Build RetrievalQuery from user_query (+ optional filters/top_k).
      3. Call Retriever.retrieve(...) against the validated, synced index.
      4. Call Generator.generate(...) or GuardedGenerator.generate(...).
      5. Optionally call Evaluator/online judges for response-quality signals.
      6. Persist request/response telemetry and close audit row.
    """
    raise NotImplementedError
