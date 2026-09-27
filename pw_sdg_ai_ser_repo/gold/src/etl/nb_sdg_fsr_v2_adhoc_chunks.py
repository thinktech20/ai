# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_v2_adhoc_chunks — Adhoc chunking_v2 task
#
# Second task of PW_SDG_FSR_V2_Ingestion_Adhoc. Invokes the UNMODIFIED main P2
# notebook (nb_sdg_fsr_v2_chunks.py) via dbutils.notebook.run(), scoped to the
# document_ids discovered by nb_sdg_fsr_v2_adhoc_metadata via the main
# notebook's FSR_TARGET_DOCUMENT_IDS parameter — mirroring exactly how P1 is
# invoked in target mode via FSR_TARGET_PDF_NAMES.
#
# This replaces the earlier standalone fsr_v2_adhoc/adhoc_chunking.py copy —
# now that chunking.run() accepts an optional document_ids scope, there is no
# longer a need to maintain a separate claim/write-back implementation, and
# any future fix to the main P2 orchestration (e.g. the Delta-conflict-retry
# and partial-embedding-coverage fixes) is picked up automatically here too.
#
# If nothing was discovered, this task no-ops and still completes as
# Succeeded — same "always Succeeded, never Skipped" pattern as task 1.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.adhoc_p2")

# Notebook symbols are normally injected by `%run ../../../common/fsr_v2/config`.
if "get_runtime_param" not in globals():
	def get_runtime_param(name: str, default: str = "") -> str:  # type: ignore[no-redef]
		return os.getenv(name, default)

# Make fsr_v2 package importable — needed for the document_id normalization
# helper used by the per-document stage-update check below.
_SILVER_ETL = os.path.normpath(os.path.join(os.getcwd(), "../../../silver/src/etl"))
if _SILVER_ETL not in sys.path:
	sys.path.insert(0, _SILVER_ETL)
_BUNDLE_ROOT = str(Path(_SILVER_ETL).parents[2])
if _BUNDLE_ROOT not in sys.path:
	sys.path.insert(0, _BUNDLE_ROOT)

from fsr_v2 import input as inp  # noqa: E402 — unmodified: same doc_id normalization as P1

METADATA_TABLE = get_runtime_param("METADATA_TABLE_V2", "").strip()

# Target scope — set by metadata_extraction_v2 via a task-value reference in
# the job YAML (FSR_ADHOC_TARGET_PDF_NAMES base_parameter, sourced from that
# task's all_document_ids task value). Every PDF found in the volume,
# unfiltered by status — the main P2 notebook's own claim query filters to
# metadata_status='completed' AND chunk_status IN ('pending','failed').
_target_raw = get_runtime_param("FSR_ADHOC_TARGET_PDF_NAMES", "").strip()
TARGET_DOCUMENT_IDS = [d.strip() for d in _target_raw.split(",") if d.strip()]

_p2_timeout_raw = get_runtime_param("FSR_ADHOC_P2_TIMEOUT_SECONDS", "14400").strip()
P2_TIMEOUT_SECONDS = int(_p2_timeout_raw) if _p2_timeout_raw else 14400

log.info("=== FSR V2 Adhoc chunking_v2 ===")
log.info(f"Target doc IDs : {len(TARGET_DOCUMENT_IDS)}")
log.info(f"P2 timeout     : {P2_TIMEOUT_SECONDS}s")

# COMMAND ----------

# ============================================================
# SDG EXECUTION STATE - DISCOVERED ROWS
# pdf_name/dag_run_id pairs come from metadata_extraction_v2's task value
# (that task queries the execution-log table itself) — the triggering DAG
# passes no identifying parameters at all.
# ============================================================

import json

dbutils.widgets.text(
    "execution_table",
    get_runtime_param("FSR_SDG_EXECUTION_TABLE", "viud.ing_ud_fieldvision.sdg_user_attachments_execution_log_psot")
)
execution_table = dbutils.widgets.get("execution_table").strip()

if not execution_table:
    raise ValueError("execution_table parameter is missing")
if "{{" in execution_table or "}}" in execution_table:
    raise ValueError(
        f"execution_table still contains an un-templated placeholder ('{execution_table}') — "
        "the triggering caller must override this job parameter with a real value"
    )

_ready_pairs_raw = get_runtime_param("FSR_ADHOC_READY_PAIRS", "[]").strip()
try:
    READY_PAIRS = json.loads(_ready_pairs_raw) if _ready_pairs_raw else []
except ValueError:
    log.warning(f"FSR_ADHOC_READY_PAIRS was not valid JSON ({_ready_pairs_raw!r}) — treating as empty")
    READY_PAIRS = []

log.info(f"SDG state table   : {execution_table}")
log.info(f"Discovered {len(READY_PAIRS)} row(s) ready for P2: {[p['pdf_name'] for p in READY_PAIRS]}")

# COMMAND ----------

if not TARGET_DOCUMENT_IDS:
	log.info("No document_ids provided — nothing to chunk (no-op).")
else:
	log.info(f"Invoking main P2 notebook for {len(TARGET_DOCUMENT_IDS)} doc(s)")

	# Derive the sibling path to nb_sdg_fsr_v2_chunks from this notebook's own
	# workspace path — dbutils.notebook.run() needs an absolute workspace path.
	_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()  # noqa: F821
	_this_notebook_path = _ctx.notebookPath().get()
	_p2_notebook_path = "/".join(_this_notebook_path.split("/")[:-1]) + "/nb_sdg_fsr_v2_chunks"
	log.info(f"P2 notebook path: {_p2_notebook_path}")

	# dbutils.notebook.run() does not inherit job-level parameters the way a
	# native task does — every P2 widget must be forwarded explicitly.
	p2_args = {
		"METADATA_TABLE_V2": get_runtime_param("METADATA_TABLE_V2", ""),
		"CHUNK_TABLE_V2": get_runtime_param("CHUNK_TABLE_V2", ""),
		"RUN_LOG_TABLE_V2": get_runtime_param("RUN_LOG_TABLE_V2", ""),
		"FSR_TARGET_DOCUMENT_IDS": ",".join(TARGET_DOCUMENT_IDS),
		"LITELLM_BASE_URL": get_runtime_param("LITELLM_BASE_URL", ""),
		"LITELLM_API_KEY": get_runtime_param("LITELLM_API_KEY", ""),
		"FSR_EMBEDDING_MODEL": get_runtime_param("FSR_EMBEDDING_MODEL", "azure-text-embedding-3-large-1"),
		"FSR_LLM_VERIFY_SSL": get_runtime_param("FSR_LLM_VERIFY_SSL", "false"),
		"FSR_P2_MAX_RETRIES": get_runtime_param("FSR_P2_MAX_RETRIES", "3"),
		"FSR_P2_MAX_ITERATIONS": get_runtime_param("FSR_P2_MAX_ITERATIONS", "0"),
		"FSR_EMBED_BATCH_SIZE": get_runtime_param("FSR_EMBED_BATCH_SIZE", "32"),
		"FSR_P2_EMBED_CONCURRENCY": get_runtime_param("FSR_P2_EMBED_CONCURRENCY", "4"),
		"FSR_EMBED_FAIL_THRESHOLD": get_runtime_param("FSR_EMBED_FAIL_THRESHOLD", "0.0"),
		"FSR_STALE_CLAIM_MINUTES": get_runtime_param("FSR_STALE_CLAIM_MINUTES", "30"),
		"FSR_EMBEDDING_DIMENSION": get_runtime_param("FSR_EMBEDDING_DIMENSION", "0"),
		"FSR_CHUNK_SIZE": get_runtime_param("FSR_CHUNK_SIZE", "3800"),
		"FSR_CHUNK_OVERLAP": get_runtime_param("FSR_CHUNK_OVERLAP", "150"),
		"FSR_MIN_CHUNK_SIZE": get_runtime_param("FSR_MIN_CHUNK_SIZE", "450"),
		"FSR_MERGE_STRATEGY": get_runtime_param("FSR_MERGE_STRATEGY", "v2_4level_cascade"),
		"FSR_REGION_ATTRIBUTION_METHOD": get_runtime_param("FSR_REGION_ATTRIBUTION_METHOD", "char_offset_max_overlap"),
	}

	# Raises on child failure/timeout — propagates as this task's own failure.
	_p2_run_id = dbutils.notebook.run(_p2_notebook_path, P2_TIMEOUT_SECONDS, p2_args)  # noqa: F821
	log.info(f"P2 child notebook run complete: run_id={_p2_run_id}")

log.info("=== Adhoc chunking_v2 complete ===")

# COMMAND ----------

# ============================================================
# SDG STAGE UPDATE - CHUNKED_AND_EMBEDDED (per discovered row)
# Reflects the ACTUAL per-document P2 outcome for each row — a batch P2 call
# can succeed overall while a given document ends up failed/incomplete, or
# never even reached P2 because its metadata extraction didn't complete.
# Rows that aren't 'completed' are marked SKIPPED and not forwarded to P3.
# ============================================================

_ready_pairs_out = []

for _pair in READY_PAIRS:
    _pdf_name = _pair["pdf_name"]
    _dag_run_id = _pair["dag_run_id"]
    _doc_id = inp._target_document_id(_pdf_name)
    _doc_id_sql = _doc_id.replace("'", "''")

    _post_rows = spark.sql(f"""
        SELECT metadata_status, chunk_status
        FROM {METADATA_TABLE}
        WHERE document_id = '{_doc_id_sql}'
    """).collect()

    if _post_rows and _post_rows[0]["metadata_status"] == "completed" and _post_rows[0]["chunk_status"] == "completed":
        stage_value, status_value, event_status = "CHUNKED_AND_EMBEDDED", "IN_PROGRESS", "SUCCESS"
        _ready_pairs_out.append({"pdf_name": _pdf_name, "dag_run_id": _dag_run_id})
    else:
        stage_value, status_value, event_status = "SKIPPED", "SKIPPED", "SKIPPED"

    log.info(f"Per-document P2 outcome: pdf_name={_pdf_name} document_id={_doc_id} -> stage={stage_value}")

    chunking_update_sql = f"""
    UPDATE {execution_table}
    SET
        chunking_refresh_timestamp = current_timestamp(),
        embedding_refresh_timestamp = current_timestamp(),
        last_stage_processed_at = current_timestamp(),
        current_stage = '{stage_value}',
        status = '{status_value}',
        timeline_metadata = to_json(
            concat(
                from_json(
                    COALESCE(timeline_metadata, '[]'),
                    'array<struct<event:string,event_time:string,status:string>>'
                ),
                array(
                    named_struct(
                        'event', '{stage_value}',
                        'event_time', CAST(current_timestamp() AS STRING),
                        'status', '{event_status}'
                    )
                )
            )
        )
    WHERE pdf_name = :pdf_name
      AND dag_run_id = :dag_run_id
    """
    spark.sql(chunking_update_sql, args={"pdf_name": _pdf_name, "dag_run_id": _dag_run_id})

dbutils.jobs.taskValues.set(key="ready_pdf_dag_pairs", value=json.dumps(_ready_pairs_out))
log.info(
    f"SDG state updated for {len(READY_PAIRS)} row(s); "
    f"{len(_ready_pairs_out)} advanced to CHUNKED_AND_EMBEDDED, published for vector_index_sync_v2"
)
