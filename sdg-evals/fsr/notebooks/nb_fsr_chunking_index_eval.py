# Databricks notebook source
# MAGIC %md
# MAGIC # FSR Chunking/Index Eval Harness
# MAGIC
# MAGIC Logs layer-1 chunking/index metrics to MLflow.
# MAGIC Use this for chunking/index experiment comparisons (for example chunk size/overlap variants).

# COMMAND ----------

# MAGIC %pip install --quiet mlflow-skinny databricks-vectorsearch

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import sys, os
import json

REPO_ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from fsr.retrieval_eval.chunking_index_harness import ChunkingIndexEvalConfig, run_eval

# COMMAND ----------

dbutils.widgets.text("BASELINE_METADATA_TABLE", "vaid.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("BASELINE_CHUNK_TABLE", "vaid.ai_std_con_field_service_report.fsr_chunks_v2")
dbutils.widgets.text("BASELINE_VS_INDEX", "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")

dbutils.widgets.text("CANDIDATE_METADATA_TABLE", "")
dbutils.widgets.text("CANDIDATE_CHUNK_TABLE", "")
dbutils.widgets.text("CANDIDATE_VS_INDEX", "")

dbutils.widgets.text("MLFLOW_EXPERIMENT", "/Users/madhurima.saxena@gevernova.com/fsr_eval_chunking_index")
dbutils.widgets.text("RUN_NAME_PREFIX", "fsr_chunking_index")
dbutils.widgets.text("EMBEDDING_DIMENSION", "3072")
dbutils.widgets.text("FSR_VS_ENDPOINT", "pw-ser-sdg-vector-search")
dbutils.widgets.text("CANDIDATE_ID", "baseline")

BASELINE_METADATA_TABLE = dbutils.widgets.get("BASELINE_METADATA_TABLE")
BASELINE_CHUNK_TABLE = dbutils.widgets.get("BASELINE_CHUNK_TABLE")
BASELINE_VS_INDEX = dbutils.widgets.get("BASELINE_VS_INDEX")

CANDIDATE_METADATA_TABLE = dbutils.widgets.get("CANDIDATE_METADATA_TABLE")
CANDIDATE_CHUNK_TABLE = dbutils.widgets.get("CANDIDATE_CHUNK_TABLE")
CANDIDATE_VS_INDEX = dbutils.widgets.get("CANDIDATE_VS_INDEX")

EXPERIMENT = dbutils.widgets.get("MLFLOW_EXPERIMENT")
RUN_NAME_PREFIX = dbutils.widgets.get("RUN_NAME_PREFIX").strip() or "fsr_chunking_index_eval"
EMBED_DIM = int(dbutils.widgets.get("EMBEDDING_DIMENSION") or "3072")
VS_ENDPOINT = dbutils.widgets.get("FSR_VS_ENDPOINT")
CANDIDATE_ID = dbutils.widgets.get("CANDIDATE_ID")

# COMMAND ----------

baseline_cfg = ChunkingIndexEvalConfig(
    metadata_table=BASELINE_METADATA_TABLE,
    chunk_table=BASELINE_CHUNK_TABLE,
    experiment_name=EXPERIMENT,
    embedding_dimension=EMBED_DIM,
    vs_endpoint_name=VS_ENDPOINT,
    vs_index_name=BASELINE_VS_INDEX,
)

baseline_run_id = run_eval(
    spark=spark,
    cfg=baseline_cfg,
    run_name_prefix=f"{RUN_NAME_PREFIX}_baseline",
    extra_tags={
        "eval_suite": "fsr_eval",
        "eval_layer": "chunking_index",
        "variant": "baseline",
        "candidate_id": CANDIDATE_ID,
    },
)
print(f"Baseline MLflow run id: {baseline_run_id}")


# COMMAND ----------

candidate_enabled = bool(CANDIDATE_CHUNK_TABLE.strip())

if not candidate_enabled:
    print("Candidate table not provided. Baseline run only.")
else:
    candidate_metadata = CANDIDATE_METADATA_TABLE.strip() or BASELINE_METADATA_TABLE
    candidate_vs_index = CANDIDATE_VS_INDEX.strip() or BASELINE_VS_INDEX

    candidate_cfg = ChunkingIndexEvalConfig(
        metadata_table=candidate_metadata,
        chunk_table=CANDIDATE_CHUNK_TABLE,
        experiment_name=EXPERIMENT,
        embedding_dimension=EMBED_DIM,
        vs_endpoint_name=VS_ENDPOINT,
        vs_index_name=candidate_vs_index,
    )

    candidate_run_id = run_eval(
        spark=spark,
        cfg=candidate_cfg,
        run_name_prefix=f"{RUN_NAME_PREFIX}_candidate",
        extra_tags={
            "eval_suite": "fsr_eval",
            "eval_layer": "chunking_index",
            "variant": "candidate",
            "candidate_id": CANDIDATE_ID,
        },
    )
    print(f"Candidate MLflow run id: {candidate_run_id}")

    # Lightweight side-by-side summary (direct SQL, no MLflow API dependency)
    def _quick_metrics(meta_table: str, chunk_table: str) -> dict:
        row = spark.sql(
            f"""
            SELECT
                (SELECT COUNT(*) FROM {meta_table} WHERE metadata_status = 'completed') AS completed_meta_docs,
                (SELECT COUNT(DISTINCT document_id) FROM {chunk_table}) AS chunk_docs,
                (SELECT COUNT(*) FROM {chunk_table}) AS total_chunks,
                (SELECT SUM(CASE WHEN chunk_text IS NULL OR TRIM(chunk_text) = '' THEN 1 ELSE 0 END) FROM {chunk_table}) AS empty_chunk_text_count,
                (SELECT SUM(CASE WHEN chunk_embedding IS NULL THEN 1 ELSE 0 END) FROM {chunk_table}) AS null_embedding_count
            """
        ).first()
        completed = int(row.completed_meta_docs or 0)
        chunk_docs = int(row.chunk_docs or 0)
        return {
            "completed_meta_docs": completed,
            "chunk_docs": chunk_docs,
            "chunk_doc_coverage_ratio": (chunk_docs / completed) if completed else 0.0,
            "total_chunks": int(row.total_chunks or 0),
            "empty_chunk_text_count": int(row.empty_chunk_text_count or 0),
            "null_embedding_count": int(row.null_embedding_count or 0),
        }

    base_m = _quick_metrics(BASELINE_METADATA_TABLE, BASELINE_CHUNK_TABLE)
    cand_m = _quick_metrics(candidate_metadata, CANDIDATE_CHUNK_TABLE)

    comparison = {
        "candidate_id": CANDIDATE_ID,
        "baseline_run_id": baseline_run_id,
        "candidate_run_id": candidate_run_id,
        "baseline": base_m,
        "candidate": cand_m,
        "delta": {
            "chunk_doc_coverage_ratio": cand_m["chunk_doc_coverage_ratio"] - base_m["chunk_doc_coverage_ratio"],
            "total_chunks": cand_m["total_chunks"] - base_m["total_chunks"],
            "empty_chunk_text_count": cand_m["empty_chunk_text_count"] - base_m["empty_chunk_text_count"],
            "null_embedding_count": cand_m["null_embedding_count"] - base_m["null_embedding_count"],
        },
    }
    print(json.dumps(comparison, indent=2))
