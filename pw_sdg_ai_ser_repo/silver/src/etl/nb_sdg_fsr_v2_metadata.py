# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_v2_metadata — P1: Metadata Extraction & Enrichment (Silver)
#
# Orchestrates stages 1-4 of the FSR V2 pipeline:
#   Stage 1 — Input source      : discover docs from volume or test ESN list
#   Stage 2 — Document parsing  : extract raw text via PyMuPDF
#   Stage 3 — Metadata processor: run preprocessor_v2
#   Stage 4 — Enrichment        : ESN mapping, region boundaries, inactive markers
#
# Writes results to fsr_metadata_v2.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pymupdf

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

import logging
import os
import concurrent.futures
import json
import re
import sys
import time
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.types import BooleanType, IntegerType, LongType, StringType, StructField, StructType, TimestampType

# Make silver/src/etl importable for fsr_v2 package modules.
_SILVER_ETL = os.path.normpath(os.path.join(os.getcwd(), "../../../silver/src/etl"))
if _SILVER_ETL not in sys.path:
	sys.path.insert(0, _SILVER_ETL)

# TODO: Validate this bundle-root import setup in dev and QA after deployment.
# Make the shared common/ package importable from the deployed bundle root.
# fsr_v2 modules depend on common.fsr_v2.* during import.
_BUNDLE_ROOT = str(Path(_SILVER_ETL).parents[2])
if _BUNDLE_ROOT not in sys.path:
	sys.path.insert(0, _BUNDLE_ROOT)

from fsr_v2 import enrichment
from fsr_v2 import input as inp
from fsr_v2 import metadata_processor as processor_impl
from fsr_v2 import parsing
from fsr_v2.metadata_enrichment import _run_merge_with_retry
from fsr_v2.llm_normalization import batch_extract_llm_metadata
from common.fsr_v2.enums import ExtractorMethod

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.p1")

spark = SparkSession.builder.getOrCreate()

# Notebook symbols are normally injected by `%run ../../../common/fsr_v2/config`.
# Keep lightweight fallbacks so this file remains executable/static-checkable.
if "get_runtime_param" not in globals():
	def get_runtime_param(name: str, default: str = "") -> str:  # type: ignore[no-redef]
		return os.getenv(name, default)

if "METADATA_TABLE_V2" not in globals():
	METADATA_TABLE_V2 = ""
if "INPUT_MODE" not in globals():
	INPUT_MODE = ""
if "DOC_EQUIPMENT_MAP_TABLE_V2" not in globals():
	DOC_EQUIPMENT_MAP_TABLE_V2 = ""
if "RUN_LOG_TABLE_V2" not in globals():
	RUN_LOG_TABLE_V2 = ""
if "DQ_LOG_TABLE_V2" not in globals():
	DQ_LOG_TABLE_V2 = ""
if "dq_log_schema_v2" not in globals():
	def dq_log_schema_v2():
		return StructType([
			StructField("dq_id", StringType(), False),
			StructField("run_id", StringType(), True),
			StructField("document_id", StringType(), True),
			StructField("pdf_name", StringType(), True),
			StructField("check_name", StringType(), False),
			StructField("severity", StringType(), False),
			StructField("failure_category", StringType(), True),
			StructField("detail", StringType(), True),
			StructField("created_at", TimestampType(), True),
		])


def _parse_runtime_list(name: str) -> list[str]:
	raw = get_runtime_param(name, "")
	if not raw:
		return []
	return [part.strip() for part in re.split(r"[,;\n]", raw) if part.strip()]


def _sql(value: str) -> str:
	return (value or "").replace("'", "''")


def _parse_verify_ssl(name: str, default: str = "false"):
	raw = get_runtime_param(name, default).strip()
	if raw.lower() in ("0", "false", "f", "no", "n", "off"):
		return False
	if os.path.exists(raw):
		return raw
	return True


METADATA_TABLE = get_runtime_param("METADATA_TABLE_V2", METADATA_TABLE_V2).strip()
CHUNK_TABLE = get_runtime_param("CHUNK_TABLE_V2", "").strip()
DOC_EQUIPMENT_MAP_TABLE = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", DOC_EQUIPMENT_MAP_TABLE_V2).strip()
RUN_LOG_TABLE = get_runtime_param("RUN_LOG_TABLE_V2", RUN_LOG_TABLE_V2).strip()
DQ_LOG_TABLE = get_runtime_param("DQ_LOG_TABLE_V2", DQ_LOG_TABLE_V2).strip()
INPUT_MODE = INPUT_MODE or get_runtime_param("INPUT_MODE", "volume_list")
PDF_VOLUME_PATHS = _parse_runtime_list("FSR_SOURCE_VOLUME_PATHS")
RUN_MODE = get_runtime_param("FSR_V2_RUN_MODE", "incremental").strip().lower()
REPAIR_MODE = RUN_MODE == "repair"
REPAIR_SCOPE_TABLE = get_runtime_param("FSR_V2_REPAIR_SCOPE_TABLE", "").strip()
REPAIR_RUN_ID = get_runtime_param("FSR_V2_REPAIR_RUN_ID", "").strip()
REPAIR_DRY_RUN = get_runtime_param("FSR_V2_REPAIR_DRY_RUN", "false").strip().lower() == "true"
REPAIR_KILL_SWITCH = get_runtime_param("FSR_V2_REPAIR_KILL_SWITCH", "false").strip().lower() == "true"
_repair_max_docs_raw = get_runtime_param("FSR_V2_REPAIR_MAX_DOCS", "").strip()
REPAIR_MAX_DOCS = int(_repair_max_docs_raw) if _repair_max_docs_raw else 0
REPAIR_STALE_CLAIM_MINUTES = int(get_runtime_param("FSR_V2_REPAIR_STALE_CLAIM_MINUTES", "60") or "60")
REPAIR_ROLLBACK_TABLE = get_runtime_param("FSR_V2_REPAIR_ROLLBACK_TABLE", "").strip()


def _normalize_target_doc_id(value: str) -> str:
	v = (value or "").strip()
	if len(v) >= 2 and ((v[0] == "'" and v[-1] == "'") or (v[0] == '"' and v[-1] == '"')):
		v = v[1:-1].strip()
	if v.lower().endswith(".pdf"):
		v = v[:-4]
	return v.lower()


TARGET_PDF_NAMES = [doc_id.strip() for doc_id in _parse_runtime_list("FSR_TARGET_PDF_NAMES") if doc_id.strip()]
TARGET_DOC_IDS_NORMALIZED = list(dict.fromkeys(_normalize_target_doc_id(doc_id) for doc_id in TARGET_PDF_NAMES))

LITELLM_BASE_URL = get_runtime_param("LITELLM_BASE_URL", "")
LITELLM_API_KEY = get_runtime_param("LITELLM_API_KEY", "")
LLM_MODEL = get_runtime_param("FSR_LLM_MODEL", "azure-gpt-5-2")
# SSL verification is off by default — the corporate gateway uses a cert not in the
# default trust store. Set FSR_LLM_VERIFY_SSL widget to a CA bundle path to enable it.
LLM_VERIFY_SSL = _parse_verify_ssl("FSR_LLM_VERIFY_SSL", "false")
METADATA_PROCESSOR_VERSION = get_runtime_param("FSR_V2_METADATA_PROCESSOR_VERSION", "v2").strip().lower()
PARSER_VERSION = get_runtime_param("FSR_V2_PARSER_VERSION", "pymupdf_v1.0").strip().lower()
PARSED_DOC_VOLUME_ROOT = get_runtime_param("FSR_PARSED_DOC_VOLUME_ROOT", "").strip()
LLM_EXTRACTION_PROMPT_VERSION = get_runtime_param("FSR_LLM_EXTRACTION_PROMPT_VERSION", "v2_with_hints").strip().lower()

IBAT_TABLE = get_runtime_param("FSR_IBAT_TABLE", "")
EV_SOT_TABLE = get_runtime_param("FSR_EVENT_VISION_TABLE", "")
PSOT_TABLE = get_runtime_param("FSR_PSOT_TABLE", "")
PDF_REF_TABLE = get_runtime_param("FSR_PDF_REF_VIEW", "").strip()

# Log resolved enrichment table wiring so a stale/blank widget is visible in
# driver logs — empty IBAT_TABLE silently disables the train-scoped resolver.
log.info(
	"Enrichment tables: FSR_IBAT_TABLE=%r  FSR_EVENT_VISION_TABLE=%r  "
	"FSR_PSOT_TABLE=%r  FSR_PDF_REF_VIEW=%r",
	IBAT_TABLE, EV_SOT_TABLE, PSOT_TABLE, PDF_REF_TABLE,
)
if not IBAT_TABLE:
	log.warning(
		"FSR_IBAT_TABLE is empty — IBAT train-scoped Generator/Steam Turbine "
		"ESN resolution is disabled for this run. Set the widget explicitly to "
		"restore fallback behavior."
	)

_max_retries_raw = get_runtime_param("FSR_V2_P1_MAX_RETRIES", "3").strip()
P1_MAX_RETRIES = int(_max_retries_raw) if _max_retries_raw else 3

_p1_workers_raw = get_runtime_param("FSR_V2_P1_WORKERS", "4").strip()
P1_WORKERS = int(_p1_workers_raw) if _p1_workers_raw else 4

_llm_batch_raw = get_runtime_param("FSR_V2_P1_LLM_BATCH_SIZE", "10").strip()
LLM_BATCH_SIZE = int(_llm_batch_raw) if _llm_batch_raw else 10

_llm_delay_raw = get_runtime_param("FSR_V2_P1_LLM_DELAY_S", "1").strip()
LLM_BATCH_DELAY = float(_llm_delay_raw) if _llm_delay_raw else 1.0

# Optional hard cap on documents processed per run (blank/0 = process the whole
# queue). Distinct from FSR_V2_P1_WORKERS, which sets how many threads run
# Stage 2-3 concurrently: workers control speed, this controls how much work one
# run attempts at all. Nothing is lost by capping — Stage 1 stub-registers the
# whole discovered queue as 'pending' before this applies, and the retry query
# at the top of the next run re-claims whatever is still 'pending'.
_max_docs_raw = get_runtime_param("FSR_V2_P1_MAX_DOCS", "").strip()
P1_MAX_DOCS = int(_max_docs_raw) if _max_docs_raw else 0

# How many docs are submitted to the thread pool at once. The run walks the
# queue in slices of this size until it is drained, so one trigger completes the
# backfill without anyone re-running the job. The slice only bounds how much is
# in flight — parsed page text for a whole 50K corpus will not fit in the driver.
_slice_raw = get_runtime_param("FSR_V2_P1_SLICE_SIZE", "2000").strip()
SLICE_SIZE = int(_slice_raw) if _slice_raw else 2000

# Safety valve for a long unattended run (blank/0 = no limit). Checked between
# slices, never mid-slice, so a run always stops on a clean boundary with its
# writes flushed.
_max_runtime_raw = get_runtime_param("FSR_V2_P1_MAX_RUNTIME_MINUTES", "").strip()
MAX_RUNTIME_MIN = int(_max_runtime_raw) if _max_runtime_raw else 0

# A PDF whose content pages are scanned images has no text layer, so extraction
# returns only the repeated page header/footer. The doc still completes and
# chunks, but with almost no retrievable content — indistinguishable from a
# healthy doc in every status column. Flag it as WARN so the OCR backlog is visible.
_dq_low_text_pages_raw = get_runtime_param("FSR_V2_DQ_LOW_TEXT_MIN_PAGES", "20").strip()
DQ_LOW_TEXT_MIN_PAGES = int(_dq_low_text_pages_raw) if _dq_low_text_pages_raw else 20

_dq_low_text_cpp_raw = get_runtime_param("FSR_V2_DQ_LOW_TEXT_CHARS_PER_PAGE", "200").strip()
DQ_LOW_TEXT_CHARS_PER_PAGE = int(_dq_low_text_cpp_raw) if _dq_low_text_cpp_raw else 200

if not METADATA_TABLE:
	raise ValueError("METADATA_TABLE_V2 is required")
if not LITELLM_BASE_URL or not LITELLM_API_KEY:
	raise ValueError("LITELLM_BASE_URL and LITELLM_API_KEY are required for enrichment")
if RUN_MODE not in {"incremental", "targeted", "repair"}:
	raise ValueError(f"Unsupported FSR_V2_RUN_MODE={RUN_MODE!r}")
if REPAIR_MODE:
	if not REPAIR_SCOPE_TABLE or not REPAIR_RUN_ID:
		raise ValueError(
			"FSR_V2_RUN_MODE=repair requires FSR_V2_REPAIR_SCOPE_TABLE and "
			"FSR_V2_REPAIR_RUN_ID"
		)
	if REPAIR_MAX_DOCS < 0:
		raise ValueError("FSR_V2_REPAIR_MAX_DOCS must be >= 0")
	if not CHUNK_TABLE:
		raise ValueError("FSR_V2_RUN_MODE=repair requires CHUNK_TABLE_V2")
	if REPAIR_STALE_CLAIM_MINUTES < 1:
		raise ValueError("FSR_V2_REPAIR_STALE_CLAIM_MINUTES must be >= 1")
	if not REPAIR_DRY_RUN and not REPAIR_ROLLBACK_TABLE:
		raise ValueError("Repair apply requires FSR_V2_REPAIR_ROLLBACK_TABLE")
else:
	if INPUT_MODE != "volume_list":
		raise ValueError(f"Unsupported INPUT_MODE={INPUT_MODE!r}; currently only 'volume_list' is implemented")
	if not PDF_VOLUME_PATHS:
		raise ValueError("FSR_SOURCE_VOLUME_PATHS is required for INPUT_MODE=volume_list")
if METADATA_PROCESSOR_VERSION not in {"v2"}:
	raise ValueError(
		f"Unsupported FSR_V2_METADATA_PROCESSOR_VERSION={METADATA_PROCESSOR_VERSION!r}; expected 'v2'"
	)
if PARSER_VERSION != "pymupdf_v1.0":
	raise ValueError(
		f"Unsupported FSR_V2_PARSER_VERSION={PARSER_VERSION!r}; expected 'pymupdf_v1.0'"
	)
if P1_WORKERS < 1:
	raise ValueError(f"FSR_V2_P1_WORKERS must be >= 1, got {P1_WORKERS}")
if LLM_BATCH_SIZE < 1:
	raise ValueError(f"FSR_V2_P1_LLM_BATCH_SIZE must be >= 1, got {LLM_BATCH_SIZE}")
if P1_MAX_DOCS < 0:
	raise ValueError(f"FSR_V2_P1_MAX_DOCS must be >= 0 (0 = unlimited), got {P1_MAX_DOCS}")
if SLICE_SIZE < 1:
	raise ValueError(f"FSR_V2_P1_SLICE_SIZE must be >= 1, got {SLICE_SIZE}")
if MAX_RUNTIME_MIN < 0:
	raise ValueError(f"FSR_V2_P1_MAX_RUNTIME_MINUTES must be >= 0 (0 = no limit), got {MAX_RUNTIME_MIN}")
if TARGET_DOC_IDS_NORMALIZED and P1_MAX_DOCS and len(TARGET_DOC_IDS_NORMALIZED) > P1_MAX_DOCS:
	# Silently dropping documents someone named explicitly is worse than refusing to run.
	raise ValueError(
		f"FSR_V2_P1_MAX_DOCS={P1_MAX_DOCS} would truncate a targeted batch of "
		f"{len(TARGET_DOC_IDS_NORMALIZED)} doc(s). Clear FSR_V2_P1_MAX_DOCS for targeted runs, "
		f"or raise it to at least {len(TARGET_DOC_IDS_NORMALIZED)}."
	)
if not PARSED_DOC_VOLUME_ROOT:
	log.warning("FSR_PARSED_DOC_VOLUME_ROOT is empty — parsed docs will NOT be cached to volume. P2 will re-parse PDFs.")

# Version directory must already exist — no auto-mkdir; caller is responsible for creating the volume path.
PARSED_DOC_VOLUME_ROOT_VERSIONED = f"{PARSED_DOC_VOLUME_ROOT.rstrip('/')}/{PARSER_VERSION}" if PARSED_DOC_VOLUME_ROOT else ""
if PARSED_DOC_VOLUME_ROOT_VERSIONED:
	try:
		if not Path(PARSED_DOC_VOLUME_ROOT_VERSIONED).exists():
			raise ValueError(
				f"FSR_PARSED_DOC_VOLUME_ROOT path does not exist: {PARSED_DOC_VOLUME_ROOT_VERSIONED}. "
				f"Create the UC volume directory before running P1."
			)
	except ValueError:
		raise
	except Exception as _path_check_err:
		log.warning(f"Could not verify PARSED_DOC_VOLUME_ROOT_VERSIONED path (will attempt writes anyway): {_path_check_err}")
	log.info(f"Parsed doc root : {PARSED_DOC_VOLUME_ROOT_VERSIONED}")

parser_impl = parsing
P1_RUN_ID = uuid.uuid4().hex
P1_RUN_START = datetime.now(timezone.utc)

log.info("=== FSR V2 P1 (Metadata) ===")
log.info(f"Metadata table : {METADATA_TABLE}")
log.info(f"Run log table  : {RUN_LOG_TABLE or '(disabled)'}")
log.info(f"DQ log table   : {DQ_LOG_TABLE or '(disabled)'}")
log.info(f"Run ID         : {P1_RUN_ID}")
log.info(f"Input mode     : {INPUT_MODE}")
log.info(f"Volumes        : {len(PDF_VOLUME_PATHS)}")
log.info(f"LLM model      : {LLM_MODEL}")
log.info(f"Parser ver     : {PARSER_VERSION}")
log.info(f"Processor ver  : {METADATA_PROCESSOR_VERSION}")
log.info(f"Prompt ver     : {LLM_EXTRACTION_PROMPT_VERSION}")
if TARGET_PDF_NAMES:
	log.info(f"Target PDFs    : {len(TARGET_PDF_NAMES)} (DEBUG OVERRIDE — only these docs will be processed)")
else:
	log.info("Target PDFs    : all eligible")
log.info(f"Max retries    : {P1_MAX_RETRIES}")
log.info(f"P1 workers     : {P1_WORKERS}")
log.info(f"LLM batch size : {LLM_BATCH_SIZE}  delay={LLM_BATCH_DELAY}s")
log.info(f"Max docs/run   : {P1_MAX_DOCS or '(whole queue)'}")
log.info(f"Slice size     : {SLICE_SIZE}")
log.info(f"Max runtime    : {f'{MAX_RUNTIME_MIN} min' if MAX_RUNTIME_MIN else '(no limit)'}")
log.info(
	f"DQ low-text    : warn if >={DQ_LOW_TEXT_MIN_PAGES} pages and "
	f"<{DQ_LOW_TEXT_CHARS_PER_PAGE} chars/page"
)

# COMMAND ----------

# ── STAGE 1: INPUT SOURCE ─────────────────────────────────────────────────────
# Discover documents based on INPUT_MODE (volume_list | test_esns).
# Output: list of document references (path, doc_id)

try:
	existing_doc_ids = {
		row.document_id
		for row in spark.sql(f"SELECT document_id FROM {METADATA_TABLE}").collect()
	}
except Exception:
	existing_doc_ids = set()

if REPAIR_MODE:
	# Repair selection is entirely scope-driven. The metadata join is deliberately
	# left-joined so missing rows are visible to preflight but never enter P1.
	_scope_run = REPAIR_RUN_ID.replace("'", "''")
	_repair_limit = f"LIMIT {REPAIR_MAX_DOCS}" if REPAIR_MAX_DOCS else ""
	spark.sql(f"""
		UPDATE {REPAIR_SCOPE_TABLE}
		SET p1_status = 'failed',
			error_message = 'stale P1 claim recovered; retry is allowed'
		WHERE run_id = '{_scope_run}'
		  AND p1_status = 'in_progress'
		  AND started_at < current_timestamp() - INTERVAL {REPAIR_STALE_CLAIM_MINUTES} MINUTES
	""")
	_repair_rows = spark.sql(f"""
		SELECT COALESCE(s.document_id, s.requested_document_id) AS document_id,
		       s.requested_document_id AS scope_requested_document_id,
		       s.reason AS scope_reason,
		       COALESCE(m.volume_path, s.source_volume_path) AS volume_path,
		       COALESCE(m.file_size_bytes, s.source_file_size_bytes) AS file_size_bytes,
		       COALESCE(m.file_last_modified, s.source_file_last_modified) AS file_last_modified,
		       m.preprocessor_regions, COALESCE(ch.chunk_count, 0) AS before_chunk_count,
		       s.attempt_count
		FROM {REPAIR_SCOPE_TABLE} s
		LEFT JOIN {METADATA_TABLE} m ON lower(m.document_id) = lower(COALESCE(s.document_id, s.requested_document_id))
		LEFT JOIN (
			SELECT document_id, COUNT(*) AS chunk_count
			FROM {CHUNK_TABLE}
			GROUP BY document_id
		) ch ON lower(ch.document_id) = lower(m.document_id)
		WHERE s.run_id = '{_scope_run}'
		  AND s.resolution_status IN ('resolved', 'missing_target')
		  AND COALESCE(m.volume_path, s.source_volume_path) IS NOT NULL
		  AND trim(COALESCE(m.volume_path, s.source_volume_path)) <> ''
		  AND s.p1_status IN ('pending', 'failed')
		  AND COALESCE(s.attempt_count, 0) < {P1_MAX_RETRIES}
		ORDER BY s.document_id
		{_repair_limit}
	""").collect()

	if REPAIR_KILL_SWITCH:
		_repair_rows = []
		log.warning("Repair kill switch is enabled; P1 will claim no new documents")
	elif not REPAIR_DRY_RUN and _repair_rows:
		_repair_ids = ", ".join("'" + row.scope_requested_document_id.replace("'", "''") + "'" for row in _repair_rows)
		spark.sql(f"""
			UPDATE {REPAIR_SCOPE_TABLE}
			SET p1_status = 'in_progress',
				attempt_count = COALESCE(attempt_count, 0) + 1,
				started_at = current_timestamp(),
				p1_run_id = '{_sql(P1_RUN_ID)}',
				error_message = NULL
			WHERE run_id = '{_scope_run}'
			  AND requested_document_id IN ({_repair_ids})
			  AND resolution_status IN ('resolved', 'missing_target')
			  AND p1_status IN ('pending', 'failed')
		""")
		_repair_rows = spark.sql(f"""
			SELECT COALESCE(s.document_id, s.requested_document_id) AS document_id,
			       s.requested_document_id AS scope_requested_document_id,
			       s.reason AS scope_reason,
			       COALESCE(m.volume_path, s.source_volume_path) AS volume_path,
			       COALESCE(m.file_size_bytes, s.source_file_size_bytes) AS file_size_bytes,
			       COALESCE(m.file_last_modified, s.source_file_last_modified) AS file_last_modified,
			       m.preprocessor_regions, COALESCE(ch.chunk_count, 0) AS before_chunk_count,
			       s.attempt_count
			FROM {REPAIR_SCOPE_TABLE} s
			LEFT JOIN {METADATA_TABLE} m ON lower(m.document_id) = lower(COALESCE(s.document_id, s.requested_document_id))
			LEFT JOIN (
				SELECT document_id, COUNT(*) AS chunk_count FROM {CHUNK_TABLE} GROUP BY document_id
			) ch ON lower(ch.document_id) = lower(m.document_id)
			WHERE s.run_id = '{_scope_run}' AND s.p1_run_id = '{_sql(P1_RUN_ID)}'
			  AND s.p1_status = 'in_progress'
		""").collect()

	docs = []
	for row in _repair_rows:
		try:
			_before_regions = json.loads(row.preprocessor_regions) if row.preprocessor_regions else []
		except (TypeError, ValueError):
			_before_regions = []
		docs.append({
			"document_id": row.document_id,
			"_scope_requested_document_id": row.scope_requested_document_id,
			"_scope_reason": row.scope_reason,
			"volume_path": row.volume_path,
			"file_size_bytes": row.file_size_bytes,
			"file_last_modified": row.file_last_modified,
			"_before_region_count": len(_before_regions),
			"_before_chunk_count": int(row.before_chunk_count or 0),
			"_before_fingerprint": hashlib.sha256(
				f"{row.preprocessor_regions or ''}|{int(row.before_chunk_count or 0)}".encode()
			).hexdigest(),
		})
	if not REPAIR_DRY_RUN:
		if not docs:
			log.info("Repair mode: no claimed documents require snapshot or processing")
		else:
			_snapshot_ids = ", ".join("'" + doc["document_id"].replace("'", "''") + "'" for doc in docs)
			spark.sql(f"""
				CREATE TABLE IF NOT EXISTS {REPAIR_ROLLBACK_TABLE} (
					repair_run_id STRING,
					document_id STRING,
					snapshot_type STRING,
					snapshot_json STRING,
					captured_at TIMESTAMP
				) USING DELTA
			""")
			from pyspark.sql import functions as F  # noqa: PLC0415
			_existing_snapshots = spark.table(REPAIR_ROLLBACK_TABLE).select(
				"repair_run_id", "document_id", "snapshot_type"
			).where(F.col("repair_run_id") == REPAIR_RUN_ID)
			_snapshot_id_values = [doc["document_id"] for doc in docs]
			_metadata_df = spark.table(METADATA_TABLE).where(F.col("document_id").isin(_snapshot_id_values))
			_chunk_df = spark.table(CHUNK_TABLE).where(F.col("document_id").isin(_snapshot_id_values))
			_metadata_snapshots = (
				_metadata_df
				.select(
					F.lit(REPAIR_RUN_ID).alias("repair_run_id"),
					F.col("document_id"),
					F.lit("metadata").alias("snapshot_type"),
					F.to_json(F.struct(*[F.col(column) for column in _metadata_df.columns])).alias("snapshot_json"),
					F.current_timestamp().alias("captured_at"),
				)
				.join(_existing_snapshots, ["repair_run_id", "document_id", "snapshot_type"], "left_anti")
			)
			_chunk_snapshots = (
				_chunk_df
				.select(
					F.lit(REPAIR_RUN_ID).alias("repair_run_id"),
					F.col("document_id"),
					F.lit("chunks").alias("snapshot_type"),
					F.to_json(F.struct(*[F.col(column) for column in _chunk_df.columns])).alias("snapshot_json"),
					F.current_timestamp().alias("captured_at"),
				)
				.join(_existing_snapshots, ["repair_run_id", "document_id", "snapshot_type"], "left_anti")
			)
			_metadata_snapshots.unionByName(_chunk_snapshots).write.mode("append").saveAsTable(REPAIR_ROLLBACK_TABLE)
			spark.sql(f"""
				UPDATE {REPAIR_SCOPE_TABLE}
				SET rollback_status = 'available',
					rollback_artifact_uri = '{_sql(REPAIR_ROLLBACK_TABLE)}',
					rollback_snapshot_version = CAST(current_timestamp() AS STRING)
				WHERE run_id = '{_sql(REPAIR_RUN_ID)}'
				  AND requested_document_id IN ({', '.join("'" + doc["_scope_requested_document_id"].replace("'", "''") + "'" for doc in docs)})
			""")
		for _doc in docs:
			spark.sql(f"""
				UPDATE {REPAIR_SCOPE_TABLE}
				SET before_fingerprint = '{_sql(_doc["_before_fingerprint"])}',
					before_region_count = {_doc["_before_region_count"]},
					before_chunk_count = {_doc["_before_chunk_count"]}
				WHERE run_id = '{_sql(REPAIR_RUN_ID)}'
				  AND requested_document_id = '{_sql(_doc["_scope_requested_document_id"])}'
			""")
	log.info("Repair mode: selected %d existing scope document(s), dry_run=%s", len(docs), REPAIR_DRY_RUN)
else:
	docs = inp.load(
		spark=spark,
		volume_paths=PDF_VOLUME_PATHS,
		existing_doc_ids=existing_doc_ids,
		target_document_ids=TARGET_PDF_NAMES,
		dbutils_client=globals().get("dbutils"),
	)

	if TARGET_DOC_IDS_NORMALIZED:
		target_docs_by_id = {doc["document_id"]: doc for doc in docs}
		# Concatenation, not a nested-quote f-string: Databricks serverless is Python
		# 3.10 and PEP 701 nested same-type quotes fail to parse there.
		target_ids_sql = ", ".join("'" + doc_id.replace("'", "''") + "'" for doc_id in TARGET_DOC_IDS_NORMALIZED)
		existing_target_rows = spark.sql(f"""
			SELECT document_id, volume_path, file_size_bytes, file_last_modified
			FROM {METADATA_TABLE}
			WHERE LOWER(document_id) IN ({target_ids_sql})
			  AND metadata_status IN ('pending', 'failed')
		""").collect()
		for row in existing_target_rows:
			target_docs_by_id.setdefault(row.document_id, {
				"document_id": row.document_id,
				"volume_path": row.volume_path,
				"file_size_bytes": row.file_size_bytes,
				"file_last_modified": row.file_last_modified,
			})
		docs = list(target_docs_by_id.values())
		log.info(f"Target mode queue: {len(docs)} doc(s) ready for processing")

	# Discovery mode: pick up pending + retry-eligible failed docs already in the table.
	if not TARGET_DOC_IDS_NORMALIZED:
		_queued_ids = {doc["document_id"] for doc in docs}
		_retry_rows = spark.sql(f"""
			SELECT document_id, volume_path, file_size_bytes, file_last_modified
			FROM {METADATA_TABLE}
			WHERE metadata_status = 'pending'
			UNION ALL
			SELECT document_id, volume_path, file_size_bytes, file_last_modified
			FROM {METADATA_TABLE}
			WHERE metadata_status = 'failed'
			  AND COALESCE(metadata_retry_count, 0) < {P1_MAX_RETRIES}
		""").collect()
		_added = 0
		for _row in _retry_rows:
			if _row.document_id not in _queued_ids:
				docs.append({
					"document_id": _row.document_id,
					"volume_path": _row.volume_path,
					"file_size_bytes": _row.file_size_bytes,
					"file_last_modified": _row.file_last_modified,
				})
				_queued_ids.add(_row.document_id)
				_added += 1
		if _added:
			log.info(f"Retry queue: added {_added} pending/failed doc(s) (retry cap: {P1_MAX_RETRIES})")

# Documents the input stage could not resolve to a single source file (e.g. an
# original plus a `_1` re-upload both claiming the id). They are recorded as
# failures with a DQ row instead of aborting the run, and are kept out of the
# work queue so nothing downstream reads an arbitrary one of the candidates.
input_error_docs = [doc for doc in docs if doc.get("error")]
if input_error_docs:
	docs = [doc for doc in docs if not doc.get("error")]
	log.warning(
		"Input stage: %d doc(s) unresolved and excluded from processing", len(input_error_docs)
	)

# Pre-register the full work queue as 'pending' before processing begins.
# Ensures docs are tracked in the table even if the job crashes mid-run;
# next run will pick them up via the retry query above.
if docs and not REPAIR_MODE:
	_stub_rows = [
		(doc["document_id"], doc["volume_path"], doc.get("file_size_bytes"), doc.get("file_last_modified"))
		for doc in docs
	]
	_stub_schema = StructType([
		StructField("document_id", StringType(), False),
		StructField("volume_path", StringType(), False),
		StructField("file_size_bytes", LongType(), True),
		StructField("file_last_modified", TimestampType(), True),
	])
	spark.createDataFrame(_stub_rows, schema=_stub_schema).createOrReplaceTempView("_fsr_v2_p1_stubs")
	spark.sql(f"""
		MERGE INTO {METADATA_TABLE} AS tgt
		USING _fsr_v2_p1_stubs AS src
		ON tgt.document_id = src.document_id
		WHEN MATCHED AND tgt.metadata_status NOT IN ('completed', 'failed') THEN UPDATE SET
			tgt.file_last_modified = src.file_last_modified,
			tgt.file_size_bytes    = src.file_size_bytes
		WHEN NOT MATCHED THEN INSERT (
			document_id, volume_path, file_size_bytes, file_last_modified,
			metadata_status, chunk_status, ingested_at
		) VALUES (
			src.document_id, src.volume_path, src.file_size_bytes, src.file_last_modified,
			'pending', 'pending', current_timestamp()
		)
	""")
	log.info(f"Stub MERGE: pre-registered {len(docs)} doc(s)")

# Applied after the stub MERGE, not before: the whole queue stays registered as
# 'pending' and durable, and only this run's slice is processed.

_effective_max_docs = REPAIR_MAX_DOCS if REPAIR_MODE else P1_MAX_DOCS
if _effective_max_docs and len(docs) > _effective_max_docs:
	log.info(
		"Document cap=%d: processing %d of %d queued doc(s) this run; the "
		"remaining stay pending for a later run",
		_effective_max_docs, _effective_max_docs, len(docs),
	)
	docs = docs[:_effective_max_docs]

log.info(f"Stage 1 complete: {len(docs)} docs to process (new + retry)")

# COMMAND ----------

# ── STAGE 2: DOCUMENT PARSING ─────────────────────────────────────────────────
# Extract raw text from each PDF using PyMuPDF.
# Output: {doc_id -> parsed_text, page_map}


def _build_map_rows(doc_id: str, regions: list, rec: dict) -> list[dict]:
	"""Build equipment map rows from in-memory regions and the post-enrichment rec.

	Avoids reading back from the metadata table — uses data already in memory
	after Stage 4 completes. Returns one row per unique (doc_id, esn).
	"""
	import json as _json
	from collections import defaultdict
	from datetime import datetime, timezone

	doc_primary_esn = (rec.get("primary_esn") or "").strip().upper()
	inactive_raw = rec.get("inactive_esns")  # JSON string '["ESN1", ...]' or None
	inactive_set: set[str] = set()
	if inactive_raw:
		try:
			inactive_set = {e.strip().upper() for e in _json.loads(inactive_raw) if e.strip()}
		except (ValueError, TypeError):
			pass

	agg: dict = defaultdict(lambda: {"equip_type": None, "technology_code": None, "count": 0})
	for region in (regions or []):
		meta = region.get("metadata") or {}
		esn = (meta.get("primary_esn") or "").strip().upper()
		if not esn:
			continue
		agg[esn]["count"] += 1
		if meta.get("primary_equip_type") and not agg[esn]["equip_type"]:
			agg[esn]["equip_type"] = meta["primary_equip_type"].strip()
		if meta.get("primary_technology_code") and not agg[esn]["technology_code"]:
			agg[esn]["technology_code"] = meta["primary_technology_code"].strip()

	# Regions are the richer source, but a doc whose regions carry no ESN would
	# otherwise get no map row at all and vanish from every ESN join. Seed from the
	# doc-level fields so the map always covers what the metadata itself claims.
	for esn, equip_type in (
		(doc_primary_esn, (rec.get("primary_equip_type") or "").strip() or None),
		((rec.get("gt_esn") or "").strip().upper(), "Gas Turbine"),
		((rec.get("gen_esn") or "").strip().upper(), "Generator"),
		((rec.get("st_esn") or "").strip().upper(), "Steam Turbine"),
	):
		if esn and esn not in agg:
			agg[esn]["equip_type"] = equip_type  # count stays 0: no region backed it

	now = datetime.now(timezone.utc)
	return [
		{
			"document_id": doc_id,
			"esn": esn,
			"equip_type": data["equip_type"],
			"technology_code": data["technology_code"],
			"is_primary_esn": (esn == doc_primary_esn),
			"is_active": (esn not in inactive_set),
			"source_region_count": data["count"],
			"created_at": now,
			"updated_at": now,
		}
		for esn, data in agg.items()
	]


_EQUIP_MAP_SCHEMA = StructType([
	StructField("document_id",         StringType(),    False),
	StructField("esn",                 StringType(),    False),
	StructField("equip_type",          StringType(),    True),
	StructField("technology_code",     StringType(),    True),
	StructField("is_primary_esn",      BooleanType(),   True),
	StructField("is_active",           BooleanType(),   True),
	StructField("source_region_count", IntegerType(),   True),
	StructField("created_at",          TimestampType(), True),
	StructField("updated_at",          TimestampType(), True),
])


def _write_equipment_map(batch_map_rows: list[dict], batch_doc_ids: list[str]) -> None:
	"""MERGE one batch's equipment-map rows, right after that batch's metadata write.

	This must stay per-batch. When it ran once at the end of the notebook instead,
	an interrupted run left every doc it had already marked
	metadata_status='completed' with zero equipment-map rows — and since the
	Stage 1 retry query only re-queues 'pending'/'failed', those docs were never
	revisited. Writing per batch bounds that loss to the one in-flight batch.
	`batch_map_rows` may be empty while `batch_doc_ids` is not (docs with no ESN);
	the MERGE still runs so stale rows for those docs are deleted.
	"""
	if not DOC_EQUIPMENT_MAP_TABLE or not batch_doc_ids:
		return
	ids_sql = ", ".join("'" + did.replace("'", "''") + "'" for did in batch_doc_ids)
	spark.createDataFrame(batch_map_rows, schema=_EQUIP_MAP_SCHEMA) \
		.createOrReplaceTempView("_fsr_v2_equipment_map_p1_batch")
	_run_merge_with_retry(spark, f"""
		MERGE INTO {DOC_EQUIPMENT_MAP_TABLE} AS tgt
		USING _fsr_v2_equipment_map_p1_batch AS src
		ON tgt.document_id = src.document_id
		AND tgt.esn = src.esn
		WHEN MATCHED THEN UPDATE SET
			tgt.equip_type = src.equip_type,
			tgt.technology_code = src.technology_code,
			tgt.is_primary_esn = src.is_primary_esn,
			tgt.is_active = src.is_active,
			tgt.source_region_count = src.source_region_count,
			tgt.updated_at = current_timestamp()
		WHEN NOT MATCHED THEN INSERT *
		WHEN NOT MATCHED BY SOURCE AND tgt.document_id IN ({ids_sql}) THEN DELETE
	""", f"equipment-map batch ({len(batch_doc_ids)} docs)")


doc_map = {d["document_id"]: d for d in docs}
success_count = 0
success_ids: list[str] = []
equip_map_row_count = 0  # running total written, for the run summary
failed_rows = [
	{
		"document_id": d["document_id"],
		"pdf_name": Path(d.get("volume_path", "")).name,
		"volume_path": d.get("volume_path", ""),
		"file_size_bytes": d.get("file_size_bytes"),
		"file_last_modified": str(d.get("file_last_modified") or ""),
		"metadata_error": d["error"],
		"dq_check_name": "p1_input_resolution",
		"dq_failure_category": "ambiguous_source_file",
	}
	for d in input_error_docs
]
warn_rows = []  # non-fatal data-quality findings (doc still completes)
_llm_batch_count = 0  # incremented as batches fire, not computed from a final list length

# Running totals survive the per-batch flush, which clears the buffers above.
failed_count = 0
warn_count = 0
_dq_rows_dropped = 0
failed_sample: list[str] = []  # first few errors, for the run-log summary


def _flush_pending_writes() -> None:
	"""Persist buffered failure and DQ rows for the batches so far.

	Called at batch cadence rather than end of run. Held to the end, an
	interrupted run leaves failed docs with no recorded error and
	metadata_retry_count still 0 — so the retry cap never engages and a doc that
	crashes the run is retried forever — and the DQ rows are lost outright, since
	nothing else records why a doc failed.
	"""
	global failed_rows, warn_rows
	global failed_count, warn_count, _dq_rows_dropped

	if REPAIR_MODE and REPAIR_DRY_RUN:
		if failed_rows:
			log.warning("DRY RUN repair failures: %d document(s) were not written", len(failed_rows))
		failed_rows = []
	elif REPAIR_MODE and failed_rows:
		_failed_schema = StructType([
			StructField("document_id", StringType(), True),
			StructField("metadata_error", StringType(), True),
		])
		spark.createDataFrame(
			[{"document_id": row["document_id"], "metadata_error": row["metadata_error"]} for row in failed_rows],
			schema=_failed_schema,
		).createOrReplaceTempView("_fsr_v2_repair_failed_docs")
		_run_merge_with_retry(spark, f"""
			MERGE INTO {METADATA_TABLE} AS tgt
			USING _fsr_v2_repair_failed_docs AS src
			ON tgt.document_id = src.document_id
			WHEN MATCHED THEN UPDATE SET
				tgt.metadata_status = 'failed',
				tgt.metadata_error = src.metadata_error,
				tgt.metadata_retry_count = COALESCE(tgt.metadata_retry_count, 0) + 1,
				tgt.scraped_at = current_timestamp(),
				tgt.updated_at = current_timestamp()
		""", f"repair failed-doc flush ({len(failed_rows)} docs)")
		for row in failed_rows:
			spark.sql(f"""
				UPDATE {REPAIR_SCOPE_TABLE}
				SET p1_status = 'failed', error_message = '{_sql(str(row['metadata_error'])[:1000])}'
				WHERE run_id = '{_sql(REPAIR_RUN_ID)}'
				  AND (
				      lower(document_id) = lower('{_sql(row['document_id'])}')
				      OR lower(requested_document_id) = lower(regexp_replace('{_sql(row['document_id'])}', '(?i)\\.pdf$', ''))
				  )
			""")
		log.info("Repair failure write-back: %d document(s)", len(failed_rows))
	elif failed_rows:
		_failed_schema = StructType([
			StructField("document_id", StringType(), True),
			StructField("file_last_modified", StringType(), True),
			StructField("file_size_bytes", LongType(), True),
			StructField("metadata_error", StringType(), True),
			StructField("pdf_name", StringType(), True),
			StructField("volume_path", StringType(), True),
		])
		# failed_rows also carries DQ-routing keys that are not table columns.
		_cols = [f.name for f in _failed_schema.fields]
		spark.createDataFrame(
			[{k: row.get(k) for k in _cols} for row in failed_rows], schema=_failed_schema,
		).createOrReplaceTempView("_fsr_v2_p1_failed_docs")
		_run_merge_with_retry(spark, f"""
			MERGE INTO {METADATA_TABLE} AS tgt
			USING _fsr_v2_p1_failed_docs AS src
			ON tgt.document_id = src.document_id
			WHEN MATCHED THEN UPDATE SET
				tgt.metadata_status       = 'failed',
				tgt.metadata_error        = src.metadata_error,
				tgt.metadata_retry_count  = COALESCE(tgt.metadata_retry_count, 0) + 1,
				tgt.scraped_at            = current_timestamp()
			WHEN NOT MATCHED THEN INSERT (
				document_id, pdf_name, volume_path, file_size_bytes, file_last_modified,
				metadata_status, metadata_error, metadata_retry_count,
				chunk_status, ingested_at, scraped_at
			) VALUES (
				src.document_id, src.pdf_name, src.volume_path, src.file_size_bytes,
				CAST(NULLIF(src.file_last_modified, '') AS TIMESTAMP),
				'failed', src.metadata_error, 1,
				'pending', current_timestamp(), current_timestamp()
			)
		""", f"failed-doc flush ({len(failed_rows)} docs)")
		log.info("Failed write-back: %d doc(s) marked 'failed'", len(failed_rows))

	if (failed_rows or warn_rows) and DQ_LOG_TABLE:
		try:
			_now = datetime.now(timezone.utc)
			_dq_rows = []
			for row in failed_rows:
				_check = row.get("dq_check_name") or "p1_metadata_ingest"
				_dq_rows.append({
					"dq_id": hashlib.md5(f"{P1_RUN_ID}|{row['document_id']}|{_check}".encode()).hexdigest(),
					"run_id": P1_RUN_ID,
					"document_id": row["document_id"],
					"pdf_name": row["pdf_name"],
					"check_name": _check,
					"severity": "FAIL",
					"failure_category": row.get("dq_failure_category") or "metadata_pipeline_error",
					"detail": (row["metadata_error"] or "")[:500],
					"created_at": _now,
				})
			for row in warn_rows:
				_dq_rows.append({
					"dq_id": hashlib.md5(f"{P1_RUN_ID}|{row['document_id']}|{row['check_name']}".encode()).hexdigest(),
					"run_id": P1_RUN_ID,
					"document_id": row["document_id"],
					"pdf_name": row["pdf_name"],
					"check_name": row["check_name"],
					"severity": "WARN",
					"failure_category": row["failure_category"],
					"detail": row["detail"][:500],
					"created_at": _now,
				})
			spark.createDataFrame(_dq_rows, schema=dq_log_schema_v2()) \
				.write.mode("append").saveAsTable(DQ_LOG_TABLE)
			log.info("DQ log v2: wrote %d FAIL + %d WARN row(s)", len(failed_rows), len(warn_rows))
		except Exception as _e:
			# Non-blocking, but counted — a silently empty DQ log has hidden real
			# problems before, so the run summary reports the drop.
			_dq_rows_dropped += len(failed_rows) + len(warn_rows)
			log.warning(f"DQ log v2 write failed (non-blocking): {_e}")

	if failed_rows:
		for row in failed_rows[: max(0, 10 - len(failed_sample))]:
			failed_sample.append(f"{row['document_id'][:30]}: {(row['metadata_error'] or '')[:80]}")
		failed_count += len(failed_rows)
		failed_rows = []
	if warn_rows:
		warn_count += len(warn_rows)
		warn_rows = []


def _check_low_text_extraction(doc_id: str, parsed_doc) -> None:
	"""Record a WARN when a multi-page PDF yields far too little text to be useful."""
	pages = getattr(parsed_doc, "pages", None) or []
	n_pages = len(pages)
	if n_pages < DQ_LOW_TEXT_MIN_PAGES:
		return
	total_chars = sum(len(p or "") for p in pages)
	chars_per_page = total_chars / n_pages
	if chars_per_page >= DQ_LOW_TEXT_CHARS_PER_PAGE:
		return
	nonempty = sum(1 for p in pages if (p or "").strip())
	warn_rows.append({
		"document_id": doc_id,
		"pdf_name": Path(getattr(parsed_doc, "volume_path", "") or "").name,
		"check_name": "p1_low_text_extraction",
		"failure_category": "no_text_layer_suspected_scan",
		"detail": (
			f"{n_pages} pages yielded {total_chars} chars "
			f"({chars_per_page:.1f}/page, threshold {DQ_LOW_TEXT_CHARS_PER_PAGE}); "
			f"only {nonempty} page(s) had text. Likely image-only/scanned PDF — needs OCR."
		),
	})
	log.warning(
		"  [DQ-WARN/low-text] %s: %d pages -> %d chars (%.1f/page), %d non-empty",
		doc_id[:50], n_pages, total_chars, chars_per_page, nonempty,
	)


def _stage2_stage3(doc: dict):
	"""Run stages 2+3 for one document in a worker thread.

	Returns (doc_id, parsed_doc, processor_output, error_msg).
	"""
	doc_id = doc["document_id"]
	try:
		# Stage 2: parse PDF
		parsed_doc = parser_impl.parse_pymupdf(doc)
		if PARSED_DOC_VOLUME_ROOT_VERSIONED:
			parsed_doc = parser_impl.save_parsed_document(parsed_doc, PARSED_DOC_VOLUME_ROOT_VERSIONED, PARSER_VERSION)

		# Stage 3: preprocess
		processor_output = processor_impl.run(
			parsed_doc,
			spark=spark,
			ibat_table=IBAT_TABLE or None,
		)
		return doc_id, parsed_doc, processor_output, None
	except Exception as exc:
		return doc_id, None, None, str(exc)[:500]


def _run_llm_batch(_batch: list[tuple[str, tuple]], _batch_num: int):
	"""Stage 4 for one LLM batch: batched extraction call, then per-doc enrichment + MERGE write.

	Called as soon as `_batch` fills, not after all of Stage 2-3 finishes — this
	is what makes completions land continuously instead of only after every
	submitted doc has cleared parsing/preprocessing. Mutates the shared
	success_count/success_ids/failed_rows/
	_llm_batch_count/equip_map_row_count accumulators declared above.
	"""
	global success_count, _llm_batch_count, equip_map_row_count
	_llm_batch_count += 1
	log.info("LLM batch %d (%d docs)", _batch_num, len(_batch))
	if REPAIR_MODE and REPAIR_DRY_RUN:
		for _doc_id, (_parsed_doc, _processor_output) in _batch:
			log.info(
				"DRY RUN repair candidate: %s regions=%d profile=%s",
				_doc_id,
				len(_processor_output.get("regions", []) or []),
				(_processor_output.get("metadata", {}) or {}).get("preprocessor_profile", "shared"),
			)
		return

	_docs_data = [
		{
			"page1_text": parsed_doc.pages[0] if parsed_doc.pages else "",
			"volume_path": parsed_doc.volume_path,
			"hints": proc_out.get("hints", ""),
		}
		for _, (parsed_doc, proc_out) in _batch
	]
	try:
		_llm_results = batch_extract_llm_metadata(
			_docs_data,
			llm_extraction_prompt_version=LLM_EXTRACTION_PROMPT_VERSION,
			llm_base_url=LITELLM_BASE_URL,
			llm_api_key=LITELLM_API_KEY,
			llm_model=LLM_MODEL,
			llm_verify_ssl=LLM_VERIFY_SSL,
		)
	except Exception as _batch_exc:
		log.error("LLM batch %d failed: %s", _batch_num, _batch_exc)
		for doc_id, (parsed_doc, _) in _batch:
			doc = doc_map[doc_id]
			failed_rows.append({
				"document_id": doc_id,
				"pdf_name": Path(doc.get("volume_path", "")).name,
				"volume_path": doc.get("volume_path", ""),
				"file_size_bytes": doc.get("file_size_bytes"),
				"file_last_modified": str(doc.get("file_last_modified") or ""),
				"metadata_error": str(_batch_exc)[:500],
			})
		return

	_batch_map_rows: list[dict] = []
	_batch_success_ids: list[str] = []

	for doc_id, (parsed_doc, processor_output) in _batch:
		doc = doc_map[doc_id]
		_llm_meta = _llm_results.get(parsed_doc.volume_path)
		if _llm_meta is None:
			# LLM returned no row for this doc — treat as failure
			failed_rows.append({
				"document_id": doc_id,
				"pdf_name": Path(doc.get("volume_path", "")).name,
				"volume_path": doc.get("volume_path", ""),
				"file_size_bytes": doc.get("file_size_bytes"),
				"file_last_modified": str(doc.get("file_last_modified") or ""),
				"metadata_error": "LLM returned no matching row for this document",
			})
			log.warning("  [LLM-MISS] %s: no row in batch response", doc_id[:50])
			continue
		try:
			rec = enrichment.run(
				spark=spark,
				parsed_doc=parsed_doc,
				processor_output=processor_output,
				metadata_table=METADATA_TABLE,
				llm_base_url=LITELLM_BASE_URL,
				llm_api_key=LITELLM_API_KEY,
				llm_model=LLM_MODEL,
				llm_verify_ssl=LLM_VERIFY_SSL,
				file_size_bytes=doc.get("file_size_bytes"),
				file_last_modified=doc.get("file_last_modified"),
				ibat_table=IBAT_TABLE or None,
				ev_sot_table=EV_SOT_TABLE or None,
				psot_table=PSOT_TABLE or None,
				pdf_ref_table=PDF_REF_TABLE or None,
				llm_extraction_prompt_version=LLM_EXTRACTION_PROMPT_VERSION,
				extractor_method=ExtractorMethod.PYMUPDF_V1_0.value,
				llm_meta=_llm_meta,
			)
			success_count += 1
			success_ids.append(doc_id)
			_batch_success_ids.append(doc_id)
			if REPAIR_MODE and not REPAIR_DRY_RUN:
				_proc_meta = processor_output.get("metadata", {}) or {}
				_proc_regions = processor_output.get("regions", []) or []
				_profile_detection = _proc_meta.get("profile_detection") or {}
				_after_profile = _proc_meta.get("preprocessor_profile") or "shared"
				_after_strategy = "components_labels_and_appendix_fallback" if _after_profile == "final_master_report" else "shared_section_preprocessor"
				_after_fingerprint = hashlib.sha256(
					json.dumps(_proc_regions, sort_keys=True, separators=(",", ":")).encode()
				).hexdigest()
				spark.sql(f"""
					UPDATE {REPAIR_SCOPE_TABLE}
					SET document_id = '{_sql(doc_id)}', resolution_status = 'resolved',
						p1_status = 'completed', p2_status = 'pending',
						actual_preprocessor_profile = '{_sql(str(_after_profile or ""))}',
						actual_preprocessor_strategy = '{_sql(_after_strategy)}',
						preprocessor_version = '{_sql(str(_proc_meta.get("preprocessor_profile_version") or METADATA_PROCESSOR_VERSION))}',
						parser_version = '{_sql(PARSER_VERSION)}',
						detection_method = '{_sql(str(_profile_detection.get("method") or ""))}',
						detection_signals = '{_sql(json.dumps(_profile_detection.get("signals") or []))}',
						detection_confidence = '{_sql(str(_profile_detection.get("confidence") or ""))}',
						fallback_reason = '{_sql(json.dumps(sorted({str((r.get("metadata") or {}).get("fallback_reason")) for r in _proc_regions if (r.get("metadata") or {}).get("fallback_reason")})))}',
						after_fingerprint = '{_sql(_after_fingerprint)}',
						after_region_count = {len(_proc_regions)},
						error_message = NULL
					WHERE run_id = '{_sql(REPAIR_RUN_ID)}'
					  AND requested_document_id = '{_sql(doc.get("_scope_requested_document_id") or doc_id)}'
				""")
			_check_low_text_extraction(doc_id, parsed_doc)
			if REPAIR_MODE:
				warn_rows.append({
					"document_id": doc_id,
					"pdf_name": Path(doc.get("volume_path", "")).name,
					"check_name": "p1_target_overwrite",
					"failure_category": "target_document_overwritten",
					"detail": (
						f"repair_run_id={REPAIR_RUN_ID}; reason={doc.get('_scope_reason', 'unknown')}; "
						f"p1_run_id={P1_RUN_ID}; profile={_after_profile or 'shared'}; "
						f"before_regions={doc.get('_before_region_count', 0)}; "
						f"after_regions={len(_proc_regions)}; "
						f"before_chunks={doc.get('_before_chunk_count', 0)}"
					),
				})
			_batch_map_rows.extend(_build_map_rows(doc_id, processor_output.get("regions", []), rec))
		except Exception as e:
			failed_rows.append({
				"document_id": doc_id,
				"pdf_name": Path(doc.get("volume_path", "")).name,
				"volume_path": doc.get("volume_path", ""),
				"file_size_bytes": doc.get("file_size_bytes"),
				"file_last_modified": str(doc.get("file_last_modified") or ""),
				"metadata_error": str(e)[:500],
			})
			log.warning("  [FAIL] %s: %s", doc_id[:50], e)

	# Equipment map for exactly the docs this batch just marked 'completed'.
	# A failure here must not be swallowed: silently continuing would recreate the
	# very inconsistency this per-batch write exists to prevent.
	_write_equipment_map(_batch_map_rows, _batch_success_ids)
	equip_map_row_count += len(_batch_map_rows)

	# Same reasoning as the map write: durable at batch cadence, not end of run.
	_flush_pending_writes()


log.info(f"Processing {len(docs)} docs with P1_WORKERS={P1_WORKERS}")

# Stage 2-3 (parse+preprocess, threaded) and Stage 4 (LLM batch + per-doc write)
# are interleaved: as soon as LLM_BATCH_SIZE docs clear Stage 2-3, Stage 4 fires
# for that batch immediately rather than waiting for every submitted doc to
# finish Stage 2-3 first. Previously Stage 4 (and its per-doc MERGE into
# METADATA_TABLE) could not start until the entire discovered set — potentially
# tens of thousands of docs — finished Stage 2-3, so nothing landed in the
# table for hours on a large corpus even though writes are per-doc once they
# start. This also bounds blast radius on a crash to one partial batch instead
# of the whole run.
#
# The work is then walked in slices of SLICE_SIZE. One trigger drains the whole
# queue; the slice only bounds how many docs are submitted to the pool at once,
# so in-flight parsed page text stays bounded no matter how large the corpus is.
_llm_batch_num = 0
_slice_count = 0
_run_deadline = (P1_RUN_START.timestamp() + MAX_RUNTIME_MIN * 60) if MAX_RUNTIME_MIN else None
_stopped_early = None

for _slice_start in range(0, len(docs), SLICE_SIZE):
	if _run_deadline and time.time() >= _run_deadline:
		_stopped_early = f"FSR_V2_P1_MAX_RUNTIME_MINUTES={MAX_RUNTIME_MIN} reached"
		log.warning(
			"%s — stopping after %d slice(s); %d doc(s) left for the next run",
			_stopped_early, _slice_count, len(docs) - _slice_start,
		)
		break

	_slice = docs[_slice_start:_slice_start + SLICE_SIZE]
	_slice_count += 1
	log.info(
		"=== Slice %d: docs %d-%d of %d ===",
		_slice_count, _slice_start + 1, _slice_start + len(_slice), len(docs),
	)

	_stage23_buffer: list[tuple[str, tuple]] = []

	with concurrent.futures.ThreadPoolExecutor(max_workers=P1_WORKERS) as _pool:
		_futures = {_pool.submit(_stage2_stage3, doc): doc for doc in _slice}

		for _idx, _future in enumerate(concurrent.futures.as_completed(_futures), start=1):
			_doc_id, _parsed_doc, _proc_out, _err = _future.result()
			# A Future holds its result until it is released. Keeping all of them in
			# _futures for the whole run pins every parsed PDF's full page text in
			# driver memory and is what OOM'd the large QA run — drop each one as
			# soon as its result has been consumed.
			_futures.pop(_future, None)
			_future = None
			_doc = doc_map[_doc_id]
			if _err:
				failed_rows.append({
					"document_id": _doc_id,
					"pdf_name": Path(_doc.get("volume_path", "")).name,
					"volume_path": _doc.get("volume_path", ""),
					"file_size_bytes": _doc.get("file_size_bytes"),
					"file_last_modified": str(_doc.get("file_last_modified") or ""),
					"metadata_error": _err,
				})
				log.warning("  [FAIL/stage2-3] %s: %s", _doc_id[:50], _err)
			else:
				_stage23_buffer.append((_doc_id, (_parsed_doc, _proc_out)))
				if len(_stage23_buffer) >= LLM_BATCH_SIZE:
					if _llm_batch_num > 0 and LLM_BATCH_DELAY > 0:
						time.sleep(LLM_BATCH_DELAY)
					_llm_batch_num += 1
					_run_llm_batch(_stage23_buffer, _llm_batch_num)
					_stage23_buffer = []
			if _idx % 100 == 0:
				log.info(
					"P1 progress: slice %d, %d/%d screened | run totals: "
					"written=%d in-flight=%d failed=%d",
					_slice_count, _idx, len(_slice), success_count,
					len(_stage23_buffer),
					failed_count + len(failed_rows),
				)

	# Flush any partial batch smaller than LLM_BATCH_SIZE left after the pool drains.
	if _stage23_buffer:
		if _llm_batch_num > 0 and LLM_BATCH_DELAY > 0:
			time.sleep(LLM_BATCH_DELAY)
		_llm_batch_num += 1
		_run_llm_batch(_stage23_buffer, _llm_batch_num)
		_stage23_buffer = []

	# Stage 2-3 failures found after the last LLM batch of this slice are still
	# buffered; nothing else writes them.
	_flush_pending_writes()

	log.info(
		"Slice %d done | run totals: succeeded=%d failed=%d",
		_slice_count, success_count, failed_count,
	)

# Covers the case where no slice ran at all — an empty queue, or the runtime cap
# tripping before the first slice. failed_rows is seeded with Stage 1 input
# resolution errors before the loop, and nothing else would write them.
_flush_pending_writes()

log.info(
	"P1 totals: queued=%d | slices=%d | succeeded=%d | failed=%d | LLM batches=%d",
	len(docs), _slice_count, success_count, failed_count, _llm_batch_count,
)

# COMMAND ----------

# ── RUN SUMMARY ───────────────────────────────────────────────────────────────
# Failure and DQ rows are written per batch by _flush_pending_writes,
# not here. Holding them to the end meant an interrupted run recorded no failures
# at all: retry counts stayed 0 so the retry cap never engaged, and the DQ rows
# were lost outright.

log.info(
	f"P1 complete: total={len(docs)}, succeeded={success_count}, failed={failed_count}, "
	f"dq_warnings={warn_count}"
)
if _dq_rows_dropped:
	log.error(
		"%d DQ log row(s) could not be written this run — the DQ log is incomplete "
		"for run_id=%s. Check the DQ log table for schema drift.",
		_dq_rows_dropped, P1_RUN_ID,
	)

# COMMAND ----------

# ── STAGE 5: EQUIPMENT MAP RECONCILIATION ─────────────────────────────────────
# The equipment map is written per LLM batch inside _run_llm_batch, together with
# that batch's metadata rows — not here. This cell only reports the result and
# checks for drift, so an interrupted run still leaves metadata and equipment map
# consistent with each other.
# Retrieval should gate on chunk_status = 'completed' to avoid serving docs
# that have metadata but no chunks yet.

if not DOC_EQUIPMENT_MAP_TABLE:
	log.info("Equipment map: skipped (DOC_EQUIPMENT_MAP_TABLE_V2 not set)")
elif not success_ids:
	log.info("Equipment map: nothing written (no succeeded docs in this run)")
else:
	log.info(
		f"Equipment map: {equip_map_row_count} row(s) written across "
		f"{_llm_batch_count} batch(es) for {len(success_ids)} succeeded doc(s)"
	)
	try:
		_orphans = spark.sql(f"""
			SELECT COUNT(*) AS n
			FROM {METADATA_TABLE} m
			LEFT ANTI JOIN {DOC_EQUIPMENT_MAP_TABLE} e ON m.document_id = e.document_id
			WHERE m.metadata_status = 'completed'
		""").first().n
		if _orphans:
			log.warning(
				"Equipment map drift: %d doc(s) are metadata_status='completed' with no "
				"equipment-map row. Docs with no ESN at all are expected here; a large "
				"count means an earlier run was interrupted before its map write — "
				"repair with validation/fsr_v2/nb_fsr_v2_repair_equipment_map.",
				_orphans,
			)
	except Exception as _e:
		log.warning(f"Equipment map drift check failed (non-blocking): {_e}")

if RUN_LOG_TABLE:
	try:
		_run_end = datetime.now(timezone.utc)
		_duration = (_run_end - P1_RUN_START).total_seconds()
		_err_summary = "; ".join(failed_sample) if failed_sample else None
		_err_sql = f"'{_err_summary.replace(chr(39), chr(39) * 2)}'" if _err_summary else "NULL"
		spark.sql(f"""
			INSERT INTO {RUN_LOG_TABLE} (
				run_id, job_name, start_time, end_time, duration_seconds,
				docs_claimed, docs_succeeded, docs_failed, chunks_written,
				p1_workers, llm_batch_count, docs_date_filtered,
				error_summary, created_at
			) VALUES (
				'{P1_RUN_ID}',
				'PW_SDG_FSR_V2_Metadata',
				TIMESTAMP('{P1_RUN_START.strftime('%Y-%m-%d %H:%M:%S')}'),
				TIMESTAMP('{_run_end.strftime('%Y-%m-%d %H:%M:%S')}'),
				{_duration:.1f},
				{len(docs)},
				{success_count},
				{failed_count},
				NULL,
				{P1_WORKERS},
				{_llm_batch_count},
				0,
				{_err_sql},
				current_timestamp()
			)
		""")
		log.info(f"Run log v2: wrote P1 summary row to {RUN_LOG_TABLE}")
	except Exception as _e:
		log.warning(f"Run log v2 write failed (non-blocking): {_e}")
