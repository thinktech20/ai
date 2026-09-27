# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_v2_chunks — P2: Chunking & Embedding (Gold)
#
# Orchestrates stage 5 of the FSR V2 pipeline:
#   Stage 5 — Chunking & embedding: split text, generate embeddings, write to chunk table
#
# Reads from fsr_metadata_v2 (metadata_status=completed, chunk_status=pending/failed).
# Writes results to fsr_chunks_v2.
# Reuses existing chunking/embedding logic from nb_sdg_fsr_chunks.py.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet PyMuPDF langchain-text-splitters

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_v2/config

# COMMAND ----------

# COMMAND ----------

import sys, os, logging, uuid, warnings
from datetime import datetime, timezone
from pyspark.sql import SparkSession
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_silver = os.path.normpath(os.path.join(os.getcwd(), "../../../gold/src/etl"))
if _silver not in sys.path:
    sys.path.insert(0, _silver)
# TODO: Validate this bundle-root import setup in dev and QA after deployment.
# fsr_v2 modules import shared helpers from common.fsr_v2.*.
_bundle_root = os.path.normpath(os.path.join(_silver, "../../.."))
if _bundle_root not in sys.path:
    sys.path.insert(0, _bundle_root)
from fsr_v2 import chunking
from common.fsr_v2.enums import MergeStrategy, RegionAttributionMethod

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.p2")

# `%run ../../../common/fsr_v2/config` normally injects these symbols.
# Keep fallbacks so this notebook remains executable/static-checkable.
if "get_runtime_param" not in globals():
    def get_runtime_param(name: str, default: str = "") -> str:  # type: ignore[no-redef]
        return os.getenv(name, default)

if "METADATA_TABLE_V2" not in globals():
    METADATA_TABLE_V2 = ""
if "CHUNK_TABLE_V2" not in globals():
    CHUNK_TABLE_V2 = ""
if "RUN_LOG_TABLE_V2" not in globals():
    RUN_LOG_TABLE_V2 = ""


def _parse_int_param(name: str, default: int) -> int:
    raw = get_runtime_param(name, str(default)).strip()
    try:
        return int(raw)
    except Exception:
        return default


def _parse_float_param(name: str, default: float) -> float:
    raw = get_runtime_param(name, str(default)).strip()
    try:
        return float(raw)
    except Exception:
        return default


def _parse_verify_ssl(name: str, default: str = "false"):
    raw = get_runtime_param(name, default).strip()
    if raw.lower() in ("0", "false", "f", "no", "n", "off"):
        return False
    if os.path.exists(raw):
        return raw
    return True


spark = SparkSession.builder.getOrCreate()

# Resolve required table params at runtime so widget/job overrides are honored
# even if %run config executed before widgets were set in this session.
METADATA_TABLE_V2 = get_runtime_param("METADATA_TABLE_V2", METADATA_TABLE_V2).strip()
CHUNK_TABLE_V2 = get_runtime_param("CHUNK_TABLE_V2", CHUNK_TABLE_V2).strip()
RUN_LOG_TABLE_V2 = get_runtime_param("RUN_LOG_TABLE_V2", RUN_LOG_TABLE_V2).strip()

LITELLM_BASE_URL = get_runtime_param("LITELLM_BASE_URL", "")
LITELLM_API_KEY = get_runtime_param("LITELLM_API_KEY", "")
EMBEDDING_MODEL = get_runtime_param("FSR_EMBEDDING_MODEL", "azure-text-embedding-3-large-1")
# SSL verification is off by default — the corporate gateway uses a cert not in the
# default trust store. Set FSR_LLM_VERIFY_SSL widget to a CA bundle path to enable it.
LLM_VERIFY_SSL = _parse_verify_ssl("FSR_LLM_VERIFY_SSL", "false")

P2_BATCH_SIZE = _parse_int_param("FSR_P2_BATCH_SIZE", 50)
P2_MAX_RETRIES = _parse_int_param("FSR_P2_MAX_RETRIES", 3)
P2_MAX_ITERATIONS = _parse_int_param("FSR_P2_MAX_ITERATIONS", 0)
EMBED_BATCH_SIZE = _parse_int_param("FSR_EMBED_BATCH_SIZE", 32)
P2_EMBED_CONCURRENCY = _parse_int_param("FSR_P2_EMBED_CONCURRENCY", 4)
EMBED_FAIL_THRESHOLD = _parse_float_param("FSR_EMBED_FAIL_THRESHOLD", 0.0)
STALE_CLAIM_MINUTES = _parse_int_param("FSR_STALE_CLAIM_MINUTES", 30)
EXPECTED_EMBED_DIMENSION = _parse_int_param("FSR_EMBEDDING_DIMENSION", 0)
REPAIR_SCOPE_TABLE = get_runtime_param("FSR_V2_REPAIR_SCOPE_TABLE", "").strip()
REPAIR_RUN_ID = get_runtime_param("FSR_V2_REPAIR_RUN_ID", "").strip()
RUN_MODE = get_runtime_param("FSR_V2_RUN_MODE", "incremental").strip().lower()
REPAIR_DRY_RUN = get_runtime_param("FSR_V2_REPAIR_DRY_RUN", "false").strip().lower() == "true"

CHUNK_SIZE = _parse_int_param("FSR_CHUNK_SIZE", 3800)
CHUNK_OVERLAP = _parse_int_param("FSR_CHUNK_OVERLAP", 150)
MIN_CHUNK_SIZE = _parse_int_param("FSR_MIN_CHUNK_SIZE", 450)
MERGE_STRATEGY = get_runtime_param("FSR_MERGE_STRATEGY", MergeStrategy.V2_4LEVEL_CASCADE.value).strip()
REGION_ATTRIBUTION_METHOD = get_runtime_param(
    "FSR_REGION_ATTRIBUTION_METHOD",
    RegionAttributionMethod.CHAR_OFFSET_MAX_OVERLAP.value,
).strip()

# Optional explicit scope — comma-separated document_ids. Empty (default)
# preserves the unscoped queue-drain behavior; only a caller that needs to
# restrict claims to a specific document set (e.g. one Volume) sets this.
_target_doc_ids_raw = get_runtime_param("FSR_TARGET_DOCUMENT_IDS", "").strip()
TARGET_DOCUMENT_IDS = (
    [d.strip() for d in _target_doc_ids_raw.split(",") if d.strip()]
    if _target_doc_ids_raw else None
)

if not METADATA_TABLE_V2 or not CHUNK_TABLE_V2:
    raise ValueError("METADATA_TABLE_V2 and CHUNK_TABLE_V2 are required")
if not LITELLM_BASE_URL or not LITELLM_API_KEY:
    raise ValueError("LITELLM_BASE_URL and LITELLM_API_KEY are required for chunk embeddings")
if RUN_MODE not in {"incremental", "targeted", "repair"}:
    raise ValueError(f"Unsupported FSR_V2_RUN_MODE={RUN_MODE!r}")
if RUN_MODE == "repair":
    if not REPAIR_SCOPE_TABLE or not REPAIR_RUN_ID:
        raise ValueError(
            "FSR_V2_RUN_MODE=repair requires FSR_V2_REPAIR_SCOPE_TABLE and "
            "FSR_V2_REPAIR_RUN_ID"
        )
    if REPAIR_DRY_RUN:
        dbutils.notebook.exit("Repair dry run: P2 did not claim or write documents")  # noqa: F821

P2_RUN_ID = uuid.uuid4().hex
P2_RUN_START = datetime.now(timezone.utc)

log.info("=== FSR V2 P2 (Chunking) ===")
log.info(f"Metadata table : {METADATA_TABLE_V2}")
log.info(f"Chunk table    : {CHUNK_TABLE_V2}")
log.info(f"Run log table  : {RUN_LOG_TABLE_V2 or '(disabled)'}")
log.info(f"Run ID         : {P2_RUN_ID}")
log.info(f"Embedding model: {EMBEDDING_MODEL}")
log.info(f"LLM base URL   : {LITELLM_BASE_URL}")
log.info(f"API key set    : {bool(LITELLM_API_KEY)}")
log.info(f"Batch size     : {P2_BATCH_SIZE}")
log.info(f"Max retries    : {P2_MAX_RETRIES}")
log.info(f"Max iterations : {P2_MAX_ITERATIONS or 'unlimited (drain queue)'}")
log.info(f"Embed batch size: {EMBED_BATCH_SIZE}")
log.info(f"Embed concurrency: {P2_EMBED_CONCURRENCY}")
log.info(f"Embed fail threshold: {EMBED_FAIL_THRESHOLD}")
log.info(f"Stale claim minutes: {STALE_CLAIM_MINUTES}")
log.info(f"Chunk size     : {CHUNK_SIZE}")
log.info(f"Chunk overlap  : {CHUNK_OVERLAP}")
log.info(f"Min chunk size : {MIN_CHUNK_SIZE}")
log.info("Strategy       : region_first:recursive")
log.info(f"Merge strategy : {MERGE_STRATEGY}")
log.info(f"Region method  : {REGION_ATTRIBUTION_METHOD}")
log.info(f"Expected dim   : {EXPECTED_EMBED_DIMENSION or '(unchecked)'}")
log.info(f"Repair scope   : {REPAIR_SCOPE_TABLE or '(normal queue)'} / {REPAIR_RUN_ID or '(none)'}")
log.info(f"Target scope   : {len(TARGET_DOCUMENT_IDS) if TARGET_DOCUMENT_IDS is not None else 'unscoped (queue-drain)'}")

_preflight = spark.sql(f"""
    SELECT
      SUM(CASE WHEN metadata_status='completed' AND chunk_status IN ('pending','failed') THEN 1 ELSE 0 END) AS eligible_docs,
      SUM(CASE WHEN metadata_status='completed' AND chunk_status='failed' AND COALESCE(chunk_retry_count, 0) >= {P2_MAX_RETRIES} THEN 1 ELSE 0 END) AS retry_exhausted_docs,
      SUM(CASE WHEN metadata_status='completed' AND chunk_status='completed' THEN 1 ELSE 0 END) AS already_completed_docs,
      SUM(CASE WHEN metadata_status='completed' AND chunk_status='in_progress' THEN 1 ELSE 0 END) AS in_progress_docs
    FROM {METADATA_TABLE_V2}
""").first()

log.info(
    "Preflight queue: "
    f"eligible={_preflight.eligible_docs or 0}, "
    f"retry_exhausted={_preflight.retry_exhausted_docs or 0}, "
    f"already_completed={_preflight.already_completed_docs or 0}, "
    f"in_progress={_preflight.in_progress_docs or 0}"
)

# COMMAND ----------

# ── STAGE 5: CHUNKING & EMBEDDING ─────────────────────────────────────────────
# Batch-claim docs from fsr_metadata_v2 with pending/failed chunk_status.
# Chunk text region-first, recursively split within each region, inherit the
# region metadata, generate embeddings, and write to fsr_chunks_v2.
# Batch loop: claim P2_BATCH_SIZE docs per iteration until queue drained.

stats = chunking.run(
    spark=spark,
    metadata_table=METADATA_TABLE_V2,
    chunk_table=CHUNK_TABLE_V2,
    llm_base_url=LITELLM_BASE_URL,
    llm_api_key=LITELLM_API_KEY,
    embedding_model=EMBEDDING_MODEL,
    llm_verify_ssl=LLM_VERIFY_SSL,
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    min_chunk_size=MIN_CHUNK_SIZE,
    batch_size=P2_BATCH_SIZE,
    max_retries=P2_MAX_RETRIES,
    max_iterations=P2_MAX_ITERATIONS,
    embed_batch_size=EMBED_BATCH_SIZE,
    embed_concurrency=P2_EMBED_CONCURRENCY,
    embed_fail_threshold=EMBED_FAIL_THRESHOLD,
    stale_claim_minutes=STALE_CLAIM_MINUTES,
    merge_strategy=MERGE_STRATEGY,
    region_attribution_method=REGION_ATTRIBUTION_METHOD,
    expected_embed_dimension=EXPECTED_EMBED_DIMENSION,
    run_id=P2_RUN_ID,
    repair_scope_table=REPAIR_SCOPE_TABLE or None,
    repair_run_id=REPAIR_RUN_ID or None,
    document_ids=TARGET_DOCUMENT_IDS,
)

log.info(
    "P2 summary: "
    f"iterations={stats.get('iterations', 0)}, "
    f"succeeded={stats.get('succeeded', 0)}, "
    f"failed={stats.get('failed', 0)}, "
    f"chunks_written={stats.get('chunks_written', 0)}"
)

if RUN_LOG_TABLE_V2:
    try:
        _run_end = datetime.now(timezone.utc)
        _duration = (_run_end - P2_RUN_START).total_seconds()
        _docs_succeeded = int(stats.get("succeeded", 0) or 0)
        _docs_failed = int(stats.get("failed", 0) or 0)
        _docs_claimed = _docs_succeeded + _docs_failed
        _chunks_written = int(stats.get("chunks_written", 0) or 0)
        _error_summary = None
        if _docs_failed:
            _error_summary = (
                f"{_docs_failed} document(s) failed during P2; "
                f"see {METADATA_TABLE_V2}.chunk_error for details"
            )
        _error_sql = f"'{_error_summary}'" if _error_summary else "NULL"
        spark.sql(f"""
            INSERT INTO {RUN_LOG_TABLE_V2} VALUES (
                '{P2_RUN_ID}',
                'PW_SDG_FSR_V2_Chunking',
                TIMESTAMP('{P2_RUN_START.strftime('%Y-%m-%d %H:%M:%S')}'),
                TIMESTAMP('{_run_end.strftime('%Y-%m-%d %H:%M:%S')}'),
                {_duration:.1f},
                {_docs_claimed},
                {_docs_succeeded},
                {_docs_failed},
                {_chunks_written},
                {_error_sql},
                current_timestamp()
            )
        """)
        log.info(f"Run log v2: wrote P2 summary row to {RUN_LOG_TABLE_V2}")
    except Exception as _e:
        log.warning(f"Run log v2 write failed (non-blocking): {_e}")
