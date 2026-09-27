# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_v2_adhoc_metadata — Adhoc metadata_extraction_v2 task
#
# First task of PW_SDG_FSR_V2_Ingestion_Adhoc. The triggering DAG passes no
# identifying parameters at all, so this task self-discovers its work by
# querying the SDG execution-log table for row(s) at
# current_stage='FILE_INGESTED'/status='IN_PROGRESS' (one query, any number of
# rows — supports concurrent/batched PDF uploads, not just a single PDF).
# Always runs to completion (no condition_task gate, so it never shows as
# "Skipped" in the Jobs UI):
#   1. Scans one ad-hoc Volume path for PDFs (reuses fsr_v2.input.load()
#      unmodified — same scan/skip/document_id rules as the main pipeline).
#   2. Filters to the subset eligible for P1 (excludes already-'completed' and
#      retry-exhausted 'failed' docs; see Eligibility filter below).
#   3. If that subset is non-empty, invokes the UNMODIFIED main P1 notebook
#      (nb_sdg_fsr_v2_metadata.py) via dbutils.notebook.run(), passing the
#      eligible doc_ids as FSR_TARGET_PDF_NAMES ("target mode") plus every
#      other P1 parameter forwarded explicitly (dbutils.notebook.run() does not
#      auto-inherit job-level parameters the way a native task does).
#   4. If nothing is eligible, logs that and completes as a no-op — still
#      "Succeeded", never "Skipped".
#   5. Publishes the FULL (unfiltered) found document_id list as a task value
#      for the downstream chunking_v2 task — P1 eligibility deliberately
#      excludes 'completed' docs, but those are exactly the ones P2 needs to
#      see (chunk_status may still be pending/failed for them from an earlier
#      run). See gold/src/etl/nb_sdg_fsr_v2_adhoc_chunks.py.
#   6. Re-checks each discovered row's actual metadata_status afterward and
#      updates its execution-log row individually — successful ones advance to
#      METADATA_EXTRACTED and are published (as a pdf_name/dag_run_id pair
#      list) for chunking_v2; anything else is marked SKIPPED and dropped.
#
# Eligibility filter for the P1 invocation (client-side only; does not touch
# fsr_v2 pipeline code or the shared retry queries in nb_sdg_fsr_v2_metadata.py):
#   - no row yet in fsr_metadata_v2                     -> eligible (new)
#   - metadata_status = 'pending'                       -> eligible
#   - metadata_status = 'failed' AND retry_count < max   -> eligible
#   - metadata_status = 'completed'                      -> excluded (already processed)
#   - metadata_status = 'date_filtered'                  -> excluded (terminal, outside year range)
#   - metadata_status = 'failed' AND retry_count >= max  -> excluded (retry cap reached)
# This keeps re-runs of this job idempotent and bounds retries for this job's
# own documents independently of the main pipeline's max-retry setting.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

import logging
import os
import sys
from pathlib import Path

from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.adhoc_metadata")

spark = SparkSession.builder.getOrCreate()

# Notebook symbols are normally injected by `%run ../../../common/fsr_v2/config`.
# Keep lightweight fallbacks so this file remains executable/static-checkable.
if "get_runtime_param" not in globals():
	def get_runtime_param(name: str, default: str = "") -> str:  # type: ignore[no-redef]
		return os.getenv(name, default)

if "METADATA_TABLE_V2" not in globals():
	METADATA_TABLE_V2 = ""

# Make fsr_v2 package importable — mirrors nb_sdg_fsr_v2_metadata.py's setup.
_SILVER_ETL = os.path.normpath(os.path.join(os.getcwd(), "../../../silver/src/etl"))
if _SILVER_ETL not in sys.path:
	sys.path.insert(0, _SILVER_ETL)
_BUNDLE_ROOT = str(Path(_SILVER_ETL).parents[2])
if _BUNDLE_ROOT not in sys.path:
	sys.path.insert(0, _BUNDLE_ROOT)

from fsr_v2 import input as inp  # noqa: E402 — unmodified: same volume-scan logic as main P1

METADATA_TABLE = get_runtime_param("METADATA_TABLE_V2", METADATA_TABLE_V2).strip()
ADHOC_VOLUME_PATH = get_runtime_param("FSR_ADHOC_SOURCE_VOLUME_PATH", "").strip().rstrip("/")

_max_retries_raw = get_runtime_param("FSR_ADHOC_MAX_RETRIES", "3").strip()
MAX_RETRIES = int(_max_retries_raw) if _max_retries_raw else 3

_p1_timeout_raw = get_runtime_param("FSR_ADHOC_P1_TIMEOUT_SECONDS", "14400").strip()
P1_TIMEOUT_SECONDS = int(_p1_timeout_raw) if _p1_timeout_raw else 14400

if not METADATA_TABLE:
	raise ValueError("METADATA_TABLE_V2 is required")
if not ADHOC_VOLUME_PATH:
	raise ValueError("FSR_ADHOC_SOURCE_VOLUME_PATH is required")

log.info("=== FSR V2 Adhoc metadata_extraction_v2 ===")
log.info(f"Volume       : {ADHOC_VOLUME_PATH}")
log.info(f"Metadata tbl : {METADATA_TABLE}")
log.info(f"Max retries  : {MAX_RETRIES}")
log.info(f"P1 timeout   : {P1_TIMEOUT_SECONDS}s")

# COMMAND ----------
# ============================================================
# SDG EXECUTION STATE - DISCOVER READY ROWS
# The triggering DAG passes no identifying parameters at all — discover which
# execution-log row(s) are ready for P1 by querying the table directly instead
# of trusting per-run parameters that will never arrive.
# ============================================================

dbutils.widgets.text(  # noqa: F821
	"execution_table",
	get_runtime_param("FSR_SDG_EXECUTION_TABLE", "viud.ing_ud_fieldvision.sdg_user_attachments_execution_log_psot")
)
execution_table = dbutils.widgets.get("execution_table").strip()  # noqa: F821

if not execution_table:
	raise ValueError("execution_table parameter is missing")
# Catches an un-overridden "{{ dag_run.conf[...] }}" default (Databricks never
# evaluates Airflow's Jinja syntax) with a clear message instead of a cryptic
# SQL parse error.
if "{{" in execution_table or "}}" in execution_table:
	raise ValueError(
		f"execution_table still contains an un-templated placeholder ('{execution_table}') — "
		"the triggering caller must override this job parameter with a real value"
	)

_ready_rows = spark.sql(f"""
	SELECT pdf_name, dag_run_id, esn
	FROM {execution_table}
	WHERE status = 'IN_PROGRESS' AND current_stage = 'FILE_INGESTED'
""").collect()

READY_ROWS = [{"pdf_name": r["pdf_name"], "dag_run_id": r["dag_run_id"], "esn": r["esn"]} for r in _ready_rows]

log.info(f"SDG state table   : {execution_table}")
log.info(f"Discovered {len(READY_ROWS)} row(s) ready for P1: {[r['pdf_name'] for r in READY_ROWS]}")

# COMMAND ----------
# ── STEP 1-2: DISCOVER + FILTER ───────────────────────────────────────────────
# Scan the volume — reuses the exact scan/skip/document_id logic the main
# pipeline uses in Stage 1, just pointed at a single ad-hoc volume path.
found_docs = inp.load(
	spark=spark,
	volume_paths=[ADHOC_VOLUME_PATH],
	existing_doc_ids=set(),  # want every file currently present, regardless of prior status
	target_document_ids=None,
	dbutils_client=dbutils,  # noqa: F821
)
log.info(f"Found {len(found_docs)} PDF(s) in volume")

if not found_docs:
	target_ids: list[str] = []
else:
	found_ids = [d["document_id"] for d in found_docs]
	_ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in found_ids)
	status_rows = spark.sql(f"""
		SELECT document_id, metadata_status, COALESCE(metadata_retry_count, 0) AS retry_count
		FROM {METADATA_TABLE}
		WHERE document_id IN ({_ids_sql})
	""").collect()
	status_by_id = {r.document_id: (r.metadata_status, r.retry_count) for r in status_rows}

	target_ids = []
	skipped_completed = 0
	skipped_date_filtered = 0
	skipped_exhausted = 0
	for doc_id in found_ids:
		status, retry_count = status_by_id.get(doc_id, (None, 0))
		if status == "completed":
			skipped_completed += 1
			continue
		# Terminal status set by nb_sdg_fsr_v2_metadata.py when a doc falls outside
		# FSR_V2_MIN_DOC_YEAR/MAX_DOC_YEAR — never re-claimed by the main pipeline either.
		if status == "date_filtered":
			skipped_date_filtered += 1
			continue
		if status == "failed" and retry_count >= MAX_RETRIES:
			skipped_exhausted += 1
			continue
		target_ids.append(doc_id)

	log.info(
		f"Eligible for P1: {len(target_ids)}  |  skipped_completed={skipped_completed}  "
		f"skipped_date_filtered={skipped_date_filtered}  "
		f"skipped_retry_exhausted={skipped_exhausted}"
	)

# Published for the downstream chunking_v2 task — deliberately unfiltered by
# status, so docs already metadata-completed but stuck at the chunking stage
# are still visible to P2's own claim query.
all_found_ids = ",".join(d["document_id"] for d in found_docs)
dbutils.jobs.taskValues.set(key="all_document_ids", value=all_found_ids)  # noqa: F821
log.info(f"Published all_document_ids task value ({len(found_docs)} doc id(s))")

# COMMAND ----------

# ── STEP 3-4: CONDITIONALLY INVOKE THE UNMODIFIED MAIN P1 NOTEBOOK ───────────
# Always completes as "Succeeded" (never "Skipped") whether or not there was
# anything to process — this task itself always runs; it just chooses whether
# to invoke the child notebook.

if not target_ids:
	log.info("No P1-eligible documents this run — nothing to process (no-op).")
else:
	target_pdf_names = ",".join(target_ids)
	log.info(f"Invoking main P1 notebook for {len(target_ids)} doc(s)")

	# Derive the sibling path to nb_sdg_fsr_v2_metadata from this notebook's own
	# workspace path — dbutils.notebook.run() needs an absolute workspace path,
	# and ${var.filename_param} (used in the job YAML) is a bundle-deploy-time
	# substitution, not something readable from Python at runtime.
	_ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()  # noqa: F821
	_this_notebook_path = _ctx.notebookPath().get()
	_p1_notebook_path = "/".join(_this_notebook_path.split("/")[:-1]) + "/nb_sdg_fsr_v2_metadata"
	log.info(f"P1 notebook path: {_p1_notebook_path}")

	# dbutils.notebook.run() does not inherit job-level parameters the way a
	# native task does — every P1 widget must be forwarded explicitly.
	p1_args = {
		"jb_env": get_runtime_param("jb_env", ""),
		"METADATA_TABLE_V2": METADATA_TABLE,
		"DOC_EQUIPMENT_MAP_TABLE_V2": get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", ""),
		"RUN_LOG_TABLE_V2": get_runtime_param("RUN_LOG_TABLE_V2", ""),
		"DQ_LOG_TABLE_V2": get_runtime_param("DQ_LOG_TABLE_V2", ""),
		"INPUT_MODE": "volume_list",
		"FSR_SOURCE_VOLUME_PATHS": ADHOC_VOLUME_PATH,
		"FSR_PARSED_DOC_VOLUME_ROOT": get_runtime_param("FSR_PARSED_DOC_VOLUME_ROOT", ""),
		"FSR_TARGET_PDF_NAMES": target_pdf_names,
		"FSR_V2_P1_MAX_RETRIES": str(MAX_RETRIES),
		"FSR_V2_P1_WORKERS": get_runtime_param("FSR_V2_P1_WORKERS", "4"),
		"FSR_V2_P1_LLM_BATCH_SIZE": get_runtime_param("FSR_V2_P1_LLM_BATCH_SIZE", "10"),
		"FSR_V2_P1_LLM_DELAY_S": get_runtime_param("FSR_V2_P1_LLM_DELAY_S", "1"),
		"FSR_V2_MIN_DOC_YEAR": get_runtime_param("FSR_V2_MIN_DOC_YEAR", "2016"),
		"FSR_V2_MAX_DOC_YEAR": get_runtime_param("FSR_V2_MAX_DOC_YEAR", ""),
		"FSR_V2_DQ_LOW_TEXT_MIN_PAGES": get_runtime_param("FSR_V2_DQ_LOW_TEXT_MIN_PAGES", "20"),
		"FSR_V2_DQ_LOW_TEXT_CHARS_PER_PAGE": get_runtime_param("FSR_V2_DQ_LOW_TEXT_CHARS_PER_PAGE", "200"),
		"FSR_V2_PARSER_VERSION": get_runtime_param("FSR_V2_PARSER_VERSION", "pymupdf_v1.0"),
		"FSR_V2_METADATA_PROCESSOR_VERSION": get_runtime_param("FSR_V2_METADATA_PROCESSOR_VERSION", "v2"),
		"FSR_LLM_EXTRACTION_PROMPT_VERSION": get_runtime_param("FSR_LLM_EXTRACTION_PROMPT_VERSION", "v2_with_hints"),
		"FSR_IBAT_TABLE": get_runtime_param("FSR_IBAT_TABLE", ""),
		"FSR_EVENT_VISION_TABLE": get_runtime_param("FSR_EVENT_VISION_TABLE", ""),
		"FSR_PSOT_TABLE": get_runtime_param("FSR_PSOT_TABLE", ""),
		"FSR_LLM_MODEL": get_runtime_param("FSR_LLM_MODEL", "azure-gpt-5-2"),
		"LITELLM_BASE_URL": get_runtime_param("LITELLM_BASE_URL", ""),
		"LITELLM_API_KEY": get_runtime_param("LITELLM_API_KEY", ""),
	}

	# Raises on child failure/timeout — propagates as this task's own failure,
	# which is what stops chunking_v2 from running (default ALL_SUCCESS).
	_p1_run_id = dbutils.notebook.run(_p1_notebook_path, P1_TIMEOUT_SECONDS, p1_args)  # noqa: F821
	log.info(f"P1 child notebook run complete: run_id={_p1_run_id}")

log.info("=== Adhoc metadata_extraction_v2 complete ===")

# COMMAND ----------

# ============================================================
# SDG STAGE UPDATE - METADATA_EXTRACTED (per discovered row)
# Reflects the ACTUAL per-document P1 outcome for each row — a batch P1 call
# can succeed overall while a given document ends up failed/date_filtered/
# still pending, so re-check fsr_metadata_v2 rather than assuming success.
# Rows that aren't 'completed' are marked SKIPPED and not forwarded to P2.
# ============================================================

import json  # noqa: E402

_ready_pairs_out = []

for _row in READY_ROWS:
	_pdf_name = _row["pdf_name"]
	_dag_run_id = _row["dag_run_id"]
	_doc_id = inp._target_document_id(_pdf_name)  # noqa: F821
	_doc_id_sql = _doc_id.replace("'", "''")

	_post_rows = spark.sql(f"""
		SELECT metadata_status
		FROM {METADATA_TABLE}
		WHERE document_id = '{_doc_id_sql}'
	""").collect()

	if _post_rows and _post_rows[0]["metadata_status"] == "completed":
		stage_value, status_value, event_status = "METADATA_EXTRACTED", "IN_PROGRESS", "SUCCESS"
		_ready_pairs_out.append({"pdf_name": _pdf_name, "dag_run_id": _dag_run_id})
	else:
		stage_value, status_value, event_status = "SKIPPED", "SKIPPED", "SKIPPED"

	log.info(f"Per-document P1 outcome: pdf_name={_pdf_name} document_id={_doc_id} -> stage={stage_value}")

	metadata_update_sql = f"""
	UPDATE {execution_table}
	SET
	    ingestion_refresh_timestamp = current_timestamp(),
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
	spark.sql(metadata_update_sql, args={"pdf_name": _pdf_name, "dag_run_id": _dag_run_id})  # noqa: F821

dbutils.jobs.taskValues.set(key="ready_pdf_dag_pairs", value=json.dumps(_ready_pairs_out))  # noqa: F821
log.info(
	f"SDG state updated for {len(READY_ROWS)} row(s); "
	f"{len(_ready_pairs_out)} advanced to METADATA_EXTRACTED, published for chunking_v2"
)
