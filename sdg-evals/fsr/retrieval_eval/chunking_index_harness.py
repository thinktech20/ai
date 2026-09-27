"""FSR chunking/index eval harness — lightweight layer-1 metrics.

Purpose:
- Measure chunk-table and metadata-table health/coverage after chunking/index knobs change.
- Log one comparable MLflow run for quick A/B across chunking/index variants.
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import mlflow


@dataclass
class ChunkingIndexEvalConfig:
    metadata_table: str
    chunk_table: str
    experiment_name: str
    embedding_dimension: int = 3072
    vs_endpoint_name: str | None = None
    vs_index_name: str | None = None


def run_eval(
    spark,
    cfg: ChunkingIndexEvalConfig,
    run_name_prefix: str = "fsr_chunking_index_eval",
    extra_tags: dict[str, str] | None = None,
) -> str:
    """Run chunking/index layer eval and return MLflow run id."""
    mlflow.set_experiment(cfg.experiment_name)

    metrics = _compute_metrics(
        spark=spark,
        metadata_table=cfg.metadata_table,
        chunk_table=cfg.chunk_table,
        embedding_dimension=cfg.embedding_dimension,
    )
    index_summary = _describe_index(cfg.vs_endpoint_name, cfg.vs_index_name)

    run_name = f"{run_name_prefix}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(
            {
                "metadata_table": cfg.metadata_table,
                "chunk_table": cfg.chunk_table,
                "embedding_dimension": cfg.embedding_dimension,
                "vs_endpoint_name": cfg.vs_endpoint_name or "",
                "vs_index_name": cfg.vs_index_name or "",
            }
        )
        mlflow.log_metrics({k: float(v) for k, v in metrics.items()})
        mlflow.set_tags(
            {
                "pipeline": "fsr",
                "stage": "chunking_index_eval",
                "index_describe_ok": str(index_summary.get("ok", False)).lower(),
                **(extra_tags or {}),
            }
        )

        payload = {
            "config": {
                "metadata_table": cfg.metadata_table,
                "chunk_table": cfg.chunk_table,
                "embedding_dimension": cfg.embedding_dimension,
                "vs_endpoint_name": cfg.vs_endpoint_name,
                "vs_index_name": cfg.vs_index_name,
            },
            "metrics": metrics,
            "index_summary": index_summary,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as fh:
            json.dump(payload, fh, indent=2, default=str)
            payload_path = fh.name
        mlflow.log_artifact(payload_path, artifact_path="chunking_index")

        return run.info.run_id


def _compute_metrics(
    spark,
    metadata_table: str,
    chunk_table: str,
    embedding_dimension: int,
) -> dict[str, float]:
    completed_meta_docs = spark.sql(
        f"SELECT COUNT(*) AS n FROM {metadata_table} WHERE metadata_status = 'completed'"
    ).first().n

    chunk_totals = spark.sql(
        f"""
        SELECT
            COUNT(*) AS total_chunks,
            COUNT(DISTINCT chunk_id) AS distinct_chunk_ids,
            COUNT(DISTINCT document_id) AS chunk_docs,
            SUM(CASE WHEN chunk_text IS NULL OR TRIM(chunk_text) = '' THEN 1 ELSE 0 END) AS empty_chunk_text_count,
            SUM(CASE WHEN chunk_embedding IS NULL THEN 1 ELSE 0 END) AS null_embedding_count,
            SUM(CASE WHEN chunk_embedding IS NOT NULL AND SIZE(chunk_embedding) != {int(embedding_dimension)} THEN 1 ELSE 0 END) AS bad_embedding_dim_count,
            AVG(LENGTH(chunk_text)) AS avg_chunk_text_chars,
            PERCENTILE_APPROX(LENGTH(chunk_text), 0.95) AS p95_chunk_text_chars
        FROM {chunk_table}
        """
    ).first()

    per_doc = spark.sql(
        f"SELECT document_id, COUNT(*) AS chunk_count FROM {chunk_table} GROUP BY document_id"
    )
    per_doc_stats = per_doc.selectExpr(
        "AVG(chunk_count) AS avg_chunks_per_doc",
        "PERCENTILE_APPROX(chunk_count, 0.5) AS p50_chunks_per_doc",
        "PERCENTILE_APPROX(chunk_count, 0.95) AS p95_chunks_per_doc",
        "MAX(chunk_count) AS max_chunks_per_doc",
    ).first()

    missing_chunk_docs = spark.sql(
        f"""
        SELECT COUNT(*) AS n
        FROM {metadata_table} m
        LEFT ANTI JOIN (SELECT DISTINCT document_id FROM {chunk_table}) c
          ON m.document_id = c.document_id
        WHERE m.metadata_status = 'completed'
        """
    ).first().n

    total_chunks = int(chunk_totals.total_chunks or 0)
    distinct_chunk_ids = int(chunk_totals.distinct_chunk_ids or 0)
    chunk_docs = int(chunk_totals.chunk_docs or 0)

    coverage_ratio = (chunk_docs / completed_meta_docs) if completed_meta_docs else 0.0
    duplicate_chunk_rows = max(total_chunks - distinct_chunk_ids, 0)

    return {
        "completed_meta_docs": float(completed_meta_docs or 0),
        "chunk_docs": float(chunk_docs),
        "chunk_doc_coverage_ratio": float(coverage_ratio),
        "missing_chunk_docs": float(missing_chunk_docs or 0),
        "total_chunks": float(total_chunks),
        "duplicate_chunk_rows": float(duplicate_chunk_rows),
        "empty_chunk_text_count": float(chunk_totals.empty_chunk_text_count or 0),
        "null_embedding_count": float(chunk_totals.null_embedding_count or 0),
        "bad_embedding_dim_count": float(chunk_totals.bad_embedding_dim_count or 0),
        "avg_chunk_text_chars": float(chunk_totals.avg_chunk_text_chars or 0),
        "p95_chunk_text_chars": float(chunk_totals.p95_chunk_text_chars or 0),
        "avg_chunks_per_doc": float(per_doc_stats.avg_chunks_per_doc or 0),
        "p50_chunks_per_doc": float(per_doc_stats.p50_chunks_per_doc or 0),
        "p95_chunks_per_doc": float(per_doc_stats.p95_chunks_per_doc or 0),
        "max_chunks_per_doc": float(per_doc_stats.max_chunks_per_doc or 0),
    }


def _describe_index(vs_endpoint_name: str | None, vs_index_name: str | None) -> dict[str, Any]:
    if not vs_endpoint_name or not vs_index_name:
        return {"ok": False, "skipped": True, "reason": "vs endpoint/index not provided"}
    try:
        from databricks.vector_search.client import VectorSearchClient

        client = VectorSearchClient(disable_notice=True)
        index = client.get_index(endpoint_name=vs_endpoint_name, index_name=vs_index_name)
        desc = index.describe()
        return {"ok": True, "describe": desc}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}
