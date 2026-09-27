# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# ER (Engineering Report) Pipeline — Configuration
#
# Runtime parameters for the ER ingestion pipeline.
# Loaded via: %run ../../../common/er_config
#
# Depends on: %run ../../../common/sdg_common_utils  (must be run first)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ./sdg_common_utils

# COMMAND ----------

# ─── Source Table ─────────────────────────────────────────────────────────────
# ER source of truth (read-only view)

ER_SOURCE_TABLE = get_runtime_param("ER_SOURCE_TABLE", "")

# ─── Target Table (Chunks + Embeddings) ──────────────────────────────────────

ER_CHUNK_TABLE = get_runtime_param("ER_CHUNK_TABLE", "")

# ─── Vector Search ───────────────────────────────────────────────────────────

ER_VS_ENDPOINT = get_runtime_param("ER_VS_ENDPOINT", "pw-ser-sdg-vector-search")
ER_VS_INDEX = get_runtime_param("ER_VS_INDEX", "")

# ─── Secrets / LLM Gateway ──────────────────────────────────────────────────

ER_SECRET_SCOPE = get_runtime_param("ER_SECRET_SCOPE", "fsr-pipeline")

_runtime_base_url = get_runtime_param("ER_LITELLM_PROXY_URL", "")
_runtime_api_key = get_runtime_param("ER_LITELLM_API_KEY", "")

LITELLM_BASE_URL = decode_maybe_base64(
    _runtime_base_url
    or get_secret(ER_SECRET_SCOPE, "LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
)
LITELLM_API_KEY = decode_maybe_base64(
    _runtime_api_key or get_secret(ER_SECRET_SCOPE, "LITELLM_API_KEY", "")
)

# ─── Embedding Model ────────────────────────────────────────────────────────

EMBEDDING_MODEL = get_runtime_param("ER_LITELLM_MODEL", "azure-text-embedding-3-large-1")
EMBEDDING_DIMENSION = int(get_runtime_param("ER_EMBEDDING_DIMENSION", "3072"))
ER_EMBEDDING_REQUEST_PATH = get_runtime_param("ER_EMBEDDING_REQUEST_PATH", "/v1/embeddings")

_ssl_mode = get_runtime_param("ER_LLM_VERIFY_SSL", "false").strip()
if _ssl_mode.lower() in ("0", "false", "f", "no", "n", "off"):
    LLM_VERIFY_SSL = False
elif os.path.exists(_ssl_mode):
    LLM_VERIFY_SSL = _ssl_mode
else:
    LLM_VERIFY_SSL = True

# ─── Chunking Config ────────────────────────────────────────────────────────
# ER uses sliding window chunking on combined text fields.

ER_CHUNK_SIZE = int(get_runtime_param("ER_CHUNK_SIZE", "4096"))
ER_CHUNK_OVERLAP_PCT = float(get_runtime_param("ER_CHUNK_OVERLAP_PCT", "0.10"))
ER_CHUNK_OVERLAP = int(ER_CHUNK_SIZE * ER_CHUNK_OVERLAP_PCT)

# ─── Source Text Fields ──────────────────────────────────────────────────────
# These 13 text columns from the ER source table are combined per record
# before chunking. Column names match the source view schema.

ER_TEXT_FIELDS = [
    "close_notes",
    "comments",
    "comments_and_work_notes",
    "description_",
    "short_description",
    "u_desired_deliverable",
    "u_feedback_comments",
    "u_field_action_taken",
    "u_immediate_response_explanati",
    "u_resolve_notes",
    "user_input",
    "work_notes",
    "work_notes_list",
]

# ─── Run Log Table ──────────────────────────────────────────────────────────
# Tracks each pipeline run and the high-watermark (MAX sys_updated_on) used
# for incremental extraction. If not set, falls back to full load every run.

ER_RUN_LOG_TABLE = get_runtime_param("ER_RUN_LOG_TABLE", "")

# ─── Failed Records Table ────────────────────────────────────────────────────
# Tracks per-record embedding failures so individual records can be retried
# on subsequent runs without freezing the watermark.  Successful retries are
# deleted; persistent failures (attempts >= ER_MAX_RECORD_ATTEMPTS) stay for
# operator inspection.

ER_FAILED_RECORDS_TABLE = get_runtime_param("ER_FAILED_RECORDS_TABLE", "")
ER_MAX_RECORD_ATTEMPTS = int(get_runtime_param("ER_MAX_RECORD_ATTEMPTS", "3"))

# ─── Backfill Audit Mode ─────────────────────────────────────────────────────
# When ER_BACKFILL_AUDIT=true, the pipeline runs an audit query that finds
# source records with sys_updated_on <= current watermark but no rows in the
# chunk table.  These "missing" records are seeded into ER_FAILED_RECORDS_TABLE
# with attempts=0 so the next normal pipeline run picks them up via the
# Pattern 2 retry path.  The audit run does NOT extract / embed / write —
# it exits after seeding so the operator can review counts before processing.

ER_BACKFILL_AUDIT = get_runtime_bool("ER_BACKFILL_AUDIT", False)

# Optional comma-separated list of er_case_numbers to seed directly into the
# failed-records table during an audit run.  When provided, the audit SKIPS
# the source-vs-chunks comparison entirely and seeds only these IDs — the
# backfill marker is NOT consulted, so this is the escape hatch for re-auditing
# specific records below the marker.
ER_BACKFILL_RECORD_IDS = parse_runtime_list("ER_BACKFILL_RECORD_IDS")

# Optional date range for targeted re-ingestion.  When both are set during
# an audit run, ALL source records in the range are seeded into the
# failed-records table (regardless of whether chunks already exist).  The
# next normal run re-processes them; chunk MERGE deduplication ensures no
# duplicates.  Backfill marker is NOT advanced (operator-chosen range).
ER_BACKFILL_DATE_FROM = get_runtime_param("ER_BACKFILL_DATE_FROM", "")
ER_BACKFILL_DATE_TO = get_runtime_param("ER_BACKFILL_DATE_TO", "")

# ─── Filters ─────────────────────────────────────────────────────────────────
# Optional runtime filters for subset processing.

ER_SERIAL_NUMBERS = parse_runtime_list("ER_SERIAL_NUMBERS")
ER_CUTOFF_DATE = get_runtime_param("ER_CUTOFF_DATE", "2016-01-01")

# Safety limit: cap the number of source records per run to prevent OOM
# on the driver from toPandas().  0 = unlimited.
ER_MAX_RECORDS = int(get_runtime_param("ER_MAX_RECORDS", "0"))

# ─── Batch Tuning ────────────────────────────────────────────────────────────

ER_EMBEDDING_BATCH_SIZE = int(get_runtime_param("ER_EMBEDDING_BATCH_SIZE", "50"))
ER_EMBEDDING_CONCURRENCY = int(get_runtime_param("ER_EMBEDDING_CONCURRENCY", "4"))
ER_MAX_RETRIES = int(get_runtime_param("ER_MAX_RETRIES", "3"))

# Number of source records to process per micro-batch (chunk → embed → write).
# Keeps peak driver memory proportional to this size rather than the full
# extract volume.  Reduces OOM risk on long date-range / full-load runs.
# 0 = disable micro-batching (process all records at once — legacy behaviour).
ER_RECORD_BATCH_SIZE = int(get_runtime_param("ER_RECORD_BATCH_SIZE", "5000"))

FORCE_RESET = get_runtime_bool("FORCE_RESET", False)
# Require a second confirmation parameter to actually execute destructive resets
FORCE_RESET_CONFIRM = get_runtime_bool("FORCE_RESET_CONFIRM", False)
if FORCE_RESET and not FORCE_RESET_CONFIRM:
    import logging as _lr
    _lr.getLogger("er.config").warning(
        "FORCE_RESET=true but FORCE_RESET_CONFIRM=false — "
        "reset will NOT execute.  Set both to true to confirm."
    )
    FORCE_RESET = False

# ─── DDL ─────────────────────────────────────────────────────────────────────

ER_RUN_LOG_DDL_COLS = """
    run_id              STRING      NOT NULL    COMMENT 'Primary key — uuid4 or timestamp-based run identifier',
    pipeline            STRING                  COMMENT 'Pipeline name — always er_ingestion',
    run_started_at      TIMESTAMP               COMMENT 'When this pipeline run started',
    run_completed_at    TIMESTAMP               COMMENT 'When this pipeline run completed',
    status              STRING                  COMMENT 'completed / failed',
    records_extracted   INT                     COMMENT 'Raw records extracted from source',
    chunks_written      INT                     COMMENT 'Chunk rows written to chunk table',
    watermark_ts        STRING                  COMMENT 'MAX(sys_updated_on) of extracted records — used as floor on next run'
"""

ER_CHUNK_TABLE_DDL_COLS = """
    chunk_id            STRING      NOT NULL    COMMENT 'Primary key — md5(er_case_number + "_" + chunk_index)',
    chunk_index         INT                     COMMENT 'Chunk position within document',
    total_chunks        INT                     COMMENT 'Total chunks produced for this ER record',
    er_case_number      STRING      NOT NULL    COMMENT 'ER case number from source (number column) — VS query key',
    serial_number       STRING                  COMMENT 'Equipment serial number — VS filter key',
    opened_at           STRING                  COMMENT 'ER opened timestamp',
    status              STRING                  COMMENT 'ER status from source',
    u_component         STRING                  COMMENT 'Component metadata',
    u_field_action_taken STRING                 COMMENT 'Field action metadata',
    equipment           STRING                  COMMENT 'Equipment description (u_equipment from source)',
    equipment_id        STRING                  COMMENT 'Equipment identifier',
    chunk_text          STRING      NOT NULL    COMMENT 'Plain text content of the chunk',
    chunk_embedding     ARRAY<DOUBLE>           COMMENT 'Pre-computed embedding vector (self-managed)',
    metadata            STRING                  COMMENT 'Additional source columns serialised as JSON',
    created_at          TIMESTAMP               COMMENT 'When this chunk row was written'
"""

ER_FAILED_RECORDS_DDL_COLS = """
    er_case_number      STRING      NOT NULL    COMMENT 'Primary key — ER case number from source',
    sys_updated_on      TIMESTAMP               COMMENT 'Source sys_updated_on at time of failure (used for retry extract)',
    first_failed_at     TIMESTAMP               COMMENT 'When this record first failed embedding',
    last_attempted_at   TIMESTAMP               COMMENT 'Most recent retry attempt timestamp',
    attempts            INT                     COMMENT 'Number of failed attempts (record stops retrying at ER_MAX_RECORD_ATTEMPTS)',
    last_error          STRING                  COMMENT 'Truncated error message from the most recent failure',
    last_run_id         STRING                  COMMENT 'run_id of the most recent attempt — joins to er_run_log'
"""

# ─── Required Parameter Validation ───────────────────────────────────────────

_REQUIRED_PARAMS = {
    "ER_SOURCE_TABLE": ER_SOURCE_TABLE,
    "ER_CHUNK_TABLE": ER_CHUNK_TABLE,
}

_missing = [name for name, val in _REQUIRED_PARAMS.items() if not val]
if _missing:
    _msg = (
        f"MISSING REQUIRED ER JOB PARAMETERS: {', '.join(_missing)}\n"
        f"Set them in the workflow YAML or pass as job parameters."
    )
    raise ValueError(_msg)
