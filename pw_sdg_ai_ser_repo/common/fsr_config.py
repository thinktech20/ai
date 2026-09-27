# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# FSR Pipeline — Shared Configuration
#
# Runtime parameters, table/volume paths, secrets, and constants used by both
# Process 1 (metadata extraction) and Process 2 (chunk ingestion).
#
# All table names are parameterized via job base_parameters / env vars so the
# same code works against dev (main.gp_services_sdg_poc) and prod (vaid.*).
# ─────────────────────────────────────────────────────────────────────────────
import os
import re
import base64
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Helpers ─────────────────────────────────────────────────────────────────

def get_runtime_param(name: str, default: str = "") -> str:
    """Read a runtime setting from env var → Databricks widget → default."""
    env_val = os.getenv(name, "").strip()
    if env_val:
        return env_val
    try:
        widget_val = dbutils.widgets.get(name)  # noqa: F821
        if widget_val is not None and str(widget_val).strip() != "":
            return str(widget_val).strip()
    except Exception:
        pass
    return default


def get_runtime_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean runtime parameter."""
    raw = get_runtime_param(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "t", "yes", "y", "on")


def parse_runtime_list(name: str) -> Optional[List[str]]:
    """Parse a comma/newline/semicolon-delimited runtime parameter into a list."""
    raw = get_runtime_param(name, "")
    if not raw:
        return None
    values = [part.strip() for part in re.split(r"[,;\n]", raw) if part.strip()]
    return values or None


def decode_maybe_base64(value: str) -> str:
    """Decode base64-encoded secrets if accidentally stored encoded."""
    text = (value or "").strip()
    if not text:
        return text
    if text.startswith("sk-") or text.lower().startswith(("http://", "https://")):
        return text
    try:
        decoded = base64.b64decode(text).decode("utf-8").strip()
        if decoded:
            return decoded
    except Exception:
        pass
    return text


# ─── Catalogs & Schemas ─────────────────────────────────────────────────────

def get_dbr_auth():
    """Return (workspace_url, token) for Databricks REST API calls.

    Workspace URL is auto-detected from Spark config; token is read from
    the notebook context.  Falls back to env vars for local testing.
    """
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        ws_host = spark.conf.get("spark.databricks.workspaceUrl")
        ws_url = f"https://{ws_host}"
    except Exception:
        ws_url = os.getenv("DATABRICKS_HOST", "https://gevernova-ai-dev-dbr.cloud.databricks.com")
    token = None
    try:
        token = (dbutils.notebook.entry_point  # noqa: F821
                 .getDbutils().notebook().getContext()
                 .apiToken().get())
    except Exception:
        token = os.getenv("DATABRICKS_TOKEN", "")
    return ws_url, token or ""

JB_ENV = get_runtime_param("jb_env", "").strip().lower()

VIUD_CATALOG = get_runtime_param("FSR_CATALOG_VIUD", "viud")
VGPP_CATALOG = get_runtime_param("FSR_CATALOG_VGPP", "vgpp")

# POC schema — will be replaced with vaid.* schemas in production
POC_CATALOG = get_runtime_param("FSR_POC_CATALOG", "main")
POC_SCHEMA = get_runtime_param("FSR_POC_SCHEMA", "gp_services_sdg_poc")


# ─── Source Volumes (Bronze — read-only) ─────────────────────────────────────
# Driven by the FSR_SOURCE_VOLUME_PATHS job parameter (comma/semicolon/newline
# separated full /Volumes/... paths).  The ingestion catalog differs per env
# (viud / viup / viuq), so paths are passed in via DAB workflow variables
# (see databricks.yaml: fsr_source_volume_paths) rather than constructed here.
# No default — pipeline fails fast if the parameter is missing, to prevent
# accidental reads from the wrong env's volumes.

PDF_VOLUME_PATHS = parse_runtime_list("FSR_SOURCE_VOLUME_PATHS") or []
# Additional volumes from DS-team POC (may not be needed in production):
# /Volumes/<vgp_catalog>/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/
# /Volumes/<viu_catalog>/ing_ud_fsr_manual/manual_field_service_report/UAT_Files/


# ─── Table Names ─────────────────────────────────────────────────────────────
# IMPORTANT: These MUST be set as job parameters. No defaults — pipeline will
# fail fast if they are missing, to prevent accidental writes to wrong tables.

# Silver — document-level metadata registry (Process 1 output)
METADATA_TABLE = get_runtime_param("FSR_METADATA_TABLE", "")

# Gold — chunk rows with materialized metadata + embeddings (Process 2 output)
CHUNK_TABLE = get_runtime_param("FSR_CHUNK_TABLE", "")

# Operational — run audit log (written by P2 at end of each run)
RUN_LOG_TABLE = get_runtime_param("FSR_RUN_LOG_TABLE", "")

# Operational — data quality issues (written by validation notebook)
DQ_LOG_TABLE = get_runtime_param("FSR_DQ_LOG_TABLE", "")

# Reference tables (Bronze — read-only enrichment sources)
IBAT_EQUIPMENT_TABLE = get_runtime_param(
    "FSR_IBAT_TABLE",
    f"{VGPP_CATALOG}.prm_std_views.ibat_equipment_mst",
)
EVENT_VISION_SOT_TABLE = get_runtime_param(
    "FSR_EVENT_VISION_TABLE",
    f"{VGPP_CATALOG}.fsr_std_views.eventmgmt_event_vision_sot",
)
FSR_PDF_REF_VIEW = get_runtime_param(
    "FSR_PDF_REF_VIEW",
    f"{VGPP_CATALOG}.fsr_std_views.fsr_pdf_ref",
)
PSOT_TABLE = get_runtime_param(
    "FSR_PSOT_TABLE",
    f"{VGPP_CATALOG}.fsr_std_views.fsr_field_vision_field_services_report_psot",
)


# ─── Secrets / LLM Gateway ──────────────────────────────────────────────────

SECRET_SCOPE = get_runtime_param("FSR_SECRET_SCOPE", "fsr-pipeline")


def _get_secret(key: str, env_fallback: str = "") -> str:
    """Try job param (widget) first, then Databricks secret scope, then env var.

    Widget-first precedence: the secret scope (fsr-pipeline) is not yet
    provisioned in all environments.  Job parameters must be honored until
    the Databricks team finishes secret-scope setup.  Once the scope is
    live and verified, flip the order back to scope-first.
    """
    # 1. Job parameters (widgets) — always honoured when set
    try:
        widget_val = dbutils.widgets.get(key)  # noqa: F821
        if widget_val is not None and str(widget_val).strip() != "":
            return str(widget_val).strip()
    except Exception:
        pass
    # 2. Databricks secret scope — TODO: make this primary once scope is ready
    try:
        val = dbutils.secrets.get(scope=SECRET_SCOPE, key=key)  # noqa: F821
        if val:
            return val
    except Exception:
        pass
    return os.getenv(key, env_fallback)


# LiteLLM gateway URL + API key are wired via job parameters (widgets) or
# env vars only — see databricks.yaml (var.litellm_base_url / var.litellm_api_key)
# and the workflow ymls under silver/src/workflows/fsr/.
# Secret-scope lookup is intentionally NOT used here.
LITELLM_BASE_URL = get_runtime_param("LITELLM_BASE_URL", "")
LITELLM_API_KEY = get_runtime_param("LITELLM_API_KEY", "")


LLM_MODEL = get_runtime_param("FSR_LLM_MODEL", "gemini-3-flash")

_ssl_mode = get_runtime_param("FSR_LLM_VERIFY_SSL", "false").strip()
if _ssl_mode.lower() in ("0", "false", "f", "no", "n", "off"):
    LLM_VERIFY_SSL = False
elif os.path.exists(_ssl_mode):
    LLM_VERIFY_SSL = _ssl_mode
else:
    LLM_VERIFY_SSL = True

_dbr_ssl_mode = get_runtime_param("FSR_DATABRICKS_VERIFY_SSL", "false").strip()
if _dbr_ssl_mode.lower() in ("0", "false", "f", "no", "n", "off"):
    DATABRICKS_VERIFY_SSL = False
elif os.path.exists(_dbr_ssl_mode):
    DATABRICKS_VERIFY_SSL = _dbr_ssl_mode
else:
    DATABRICKS_VERIFY_SSL = True


# ─── Embedding Model ────────────────────────────────────────────────────────

EMBEDDING_MODEL = get_runtime_param(
    "FSR_EMBEDDING_MODEL", "azure-text-embedding-3-large-1"
)
EMBEDDING_DIMENSION = int(get_runtime_param("FSR_EMBEDDING_DIMENSION", "3072"))


# ─── Vector Search ───────────────────────────────────────────────────────────

VS_ENDPOINT_NAME = get_runtime_param("FSR_VS_ENDPOINT", "")
VS_INDEX_NAME = get_runtime_param("FSR_VS_INDEX", "")


# ─── Process 1 Tuning ───────────────────────────────────────────────────────

P1_BATCH_SIZE = int(get_runtime_param("FSR_BATCH_SIZE", "4"))

# Safety cap — limits how many docs a single run will process.
# Leave blank for production/backfill (P1 processes all new files, P2 uses P2_BATCH_SIZE).
# Set to a small number (e.g. 10) during development/testing.
P1_MAX_PDFS = None
_max_pdfs_raw = get_runtime_param("FSR_MAX_PDFS", "")
if _max_pdfs_raw:
    P1_MAX_PDFS = int(_max_pdfs_raw)

# DEBUG ONLY — comma-separated document_ids to process specific files.
# When set, ONLY these docs are processed (ignores all others).
# Leave blank for normal runs and backfill.
TARGET_PDF_NAMES = parse_runtime_list("FSR_TARGET_PDF_NAMES")

P1_EXTRACT_WORKERS = int(get_runtime_param("FSR_PDF_EXTRACT_WORKERS", "16"))
P1_LLM_CONCURRENCY = int(get_runtime_param("FSR_LLM_CONCURRENCY", "3"))
P1_LLM_CONCURRENCY_MAX = int(get_runtime_param("FSR_LLM_CONCURRENCY_MAX", "6"))
P1_LLM_CONCURRENCY_MIN = 1
P1_BATCH_THREADS = int(get_runtime_param("FSR_BATCH_THREADS", "4"))
P1_BATCH_THREADS_START = int(get_runtime_param("FSR_BATCH_THREADS_START", "2"))
P1_THREAD_RAMP_SECONDS = int(get_runtime_param("FSR_BATCH_THREAD_RAMP_SECONDS", "10"))
P1_MAX_RETRIES = int(get_runtime_param("FSR_MAX_RETRIES", "3"))

# Commit progress every N docs instead of all-at-once.
# Set to 0 or blank to commit all at end.
P1_COMMIT_BATCH = int(get_runtime_param("FSR_P1_COMMIT_BATCH", "500"))
P1_LLM_DELAY = float(get_runtime_param("FSR_P1_LLM_DELAY", "0"))  # seconds between LLM batches (0 = no delay)

FORCE_RESET = get_runtime_bool("FORCE_RESET", False)


# ─── Process 2 Tuning ───────────────────────────────────────────────────────

P2_BATCH_SIZE = int(get_runtime_param("FSR_P2_BATCH_SIZE", "50"))
P2_PDF_WORKERS = int(get_runtime_param("FSR_P2_PDF_WORKERS", "4"))
P2_MAX_RETRIES = int(get_runtime_param("FSR_P2_MAX_RETRIES", "3"))

# How many claim→process cycles P2 runs before stopping.
# 0 = drain the queue (process all pending docs). Set >0 for testing.
P2_MAX_ITERATIONS = int(get_runtime_param("FSR_P2_MAX_ITERATIONS", "0"))


# ─── Chunking Config ────────────────────────────────────────────────────────

@dataclass
class ChunkingConfig:
    chunk_size: int = 4000
    chunk_overlap: int = 200
    max_chunk_tokens: int = 4000
    max_chunk_chars: int = 20000
    max_depth: int = 5
    min_chunk_size: int = 100
    separator_patterns: List[str] = field(default_factory=lambda: [
        "\n## ", "\n### ", "\n#### ", "\n\n", "\n",
    ])
    preserve_structure: bool = True


CHUNKING_CONFIG = ChunkingConfig()


# ─── Status Constants ────────────────────────────────────────────────────────

class MetadataStatus:
    PENDING = "pending"      # stub row written at discovery, not yet scraped
    COMPLETED = "completed"  # metadata extraction succeeded
    FAILED = "failed"        # metadata extraction failed


class ChunkStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── File Filters ────────────────────────────────────────────────────────────

SKIP_SUFFIXES = frozenset({
    ".crdownload", ".tmp", ".part", ".download",
    ".DS_Store", ".json", ".txt", ".csv", ".xlsx",
})


# ─── ESN Validation ─────────────────────────────────────────────────────────
# Known-bad ESN values that LLMs sometimes return as placeholders.
# Pipeline will reject these and fall through to fsr_pdf_ref or leave null.
INVALID_ESN_PATTERNS = frozenset({
    "XXXXXX", "XXXXXXX", "XXXXXXXX",
    "UNKNOWN", "N/A", "NA", "TBD", "NONE", "NULL",
    "{UK_NATIONAL_INSURANCE_NUMBER}",
})


# ─── Multi-ESN / fsr_pdf_ref Expansion ──────────────────────────────────────
# When enabled, P2 duplicates chunk rows for each ESN found in fsr_pdf_ref.
FSR_MULTI_ESN_ENABLED = get_runtime_bool("FSR_MULTI_ESN_ENABLED", True)
# When true, multi-ESN fan-out logs what would change but does not write.
FSR_MULTI_ESN_DRY_RUN = get_runtime_bool("FSR_MULTI_ESN_DRY_RUN", False)


# ─── ESN LLM Detection (Tier 2) ─────────────────────────────────────────────
FSR_ESN_DETECT_ENABLED = get_runtime_bool("FSR_ESN_DETECT_ENABLED", False)
FSR_ESN_LLM_MODEL = get_runtime_param("FSR_ESN_LLM_MODEL", "gemini-3-flash")
FSR_ESN_MIN_COUNT = int(get_runtime_param("FSR_ESN_MIN_COUNT", "5"))
FSR_ESN_MIN_FRACTION = float(get_runtime_param("FSR_ESN_MIN_FRACTION", "0.10"))


# ─── Metadata Table Schema (for CREATE TABLE) ───────────────────────────────

METADATA_TABLE_DDL_COLS = """
    document_id         STRING      NOT NULL    COMMENT 'Normalized UUID stem from volume path — primary key, join key to fsr_pdf_ref.s3_filename',
    pdf_name            STRING                  COMMENT 'Human-readable PDF name — resolved from fsr_pdf_ref by matching document_id to s3_filename',
    volume_path         STRING      NOT NULL    COMMENT 'Full /Volumes/... path to the source PDF',
    title               STRING                  COMMENT 'Report title extracted from the PDF',
    customer            STRING                  COMMENT 'Customer / site name',
    esn                 STRING                  COMMENT 'Equipment Serial Number (resolved via precedence)',
    esn_source          STRING                  COMMENT 'How ESN was resolved: llm / ibat / null',
    equipment_sys_id    STRING                  COMMENT 'System ID from IBAT',
    equipment_type      STRING                  COMMENT 'Equipment type (e.g. Generator, Gas Turbine)',
    equipment_class_code STRING                 COMMENT 'Equipment sub-class / code',
    event_type          STRING                  COMMENT 'Event type (e.g. Call-Out, Inspection)',
    ev_project_id       STRING                  COMMENT 'Event Vision project ID',
    ev_equipment_event_id STRING                COMMENT 'Event Vision equipment event ID',
    ofs_event_id        STRING                  COMMENT 'OFS event ID',
    fsp_project_id      STRING                  COMMENT 'FSP project ID',
    xxx_project_id      STRING                  COMMENT 'Additional project ID (pipe-separated if multiple)',
    fsr_number          STRING                  COMMENT 'FSR document number',
    report_issued_date  STRING                  COMMENT 'Date the FSR was issued — format: YYYY-MM-DD',
    outage_start_date   STRING                  COMMENT 'Outage start date — format: YYYY-MM-DD',
    outage_end_date     STRING                  COMMENT 'Outage end date — format: YYYY-MM-DD',
    outage_type         STRING                  COMMENT 'Outage type — resolved from PSOT table via ev_equipment_event_id',
    technology_type     STRING                  COMMENT 'Technology type — resolved from PSOT table via ev_equipment_event_id',
    prepared_by         STRING                  COMMENT 'Name of the person who prepared the report',
    approved_by         STRING                  COMMENT 'Name of the person who approved the report',
    document_summary    STRING                  COMMENT 'LLM-generated full-document summary (3–5 sentences)',
    page_count          INT                     COMMENT 'Number of pages in the PDF',
    file_size_bytes     LONG                    COMMENT 'File size in bytes',
    file_last_modified  TIMESTAMP               COMMENT 'Last modified timestamp from volume listing',
    metadata_status     STRING      NOT NULL    COMMENT 'Scraping status: pending / completed / failed',
    metadata_error      STRING                  COMMENT 'Error message if metadata extraction failed',
    metadata_retry_count INT                    COMMENT 'Number of times P1 has attempted and failed this document',
    chunk_status        STRING      NOT NULL    COMMENT 'Chunking status: pending / in_progress / completed / failed',
    chunk_error         STRING                  COMMENT 'Error message if chunking failed',
    chunk_retry_count   INT                     COMMENT 'Number of times P2 has attempted and failed this document',
    ingested_at         TIMESTAMP               COMMENT 'When this row was first created (file discovery)',
    scraped_at          TIMESTAMP               COMMENT 'When metadata scraping last completed or failed',
    chunked_at          TIMESTAMP               COMMENT 'When chunking last completed or failed',
    all_esns            STRING                  COMMENT 'JSON array of all associated ESNs from fsr_pdf_ref + LLM detection',
    esn_detect_status   STRING                  COMMENT 'LLM ESN detection status: null/pending/completed/failed'
"""

CHUNK_TABLE_DDL_COLS = """
    chunk_id            STRING      NOT NULL    COMMENT 'Primary key — md5(document_id + "_" + chunk_index)',
    chunk_index         INT                     COMMENT 'Chunk position within document',
    document_id         STRING      NOT NULL    COMMENT 'FK to metadata registry — UUID filename stem of the source PDF',
    pdf_name            STRING                  COMMENT 'Human-readable PDF name — resolved from fsr_pdf_ref (nullable)',
    page_number         INT                     COMMENT 'Page number within the PDF where this chunk originates',
    chunk_text          STRING      NOT NULL    COMMENT 'Plain text content of the chunk',
    esn                 STRING                  COMMENT 'Equipment Serial Number — top-level column for VS filtering',
    report_date         DATE                    COMMENT 'Report issued date (kept for backward compatibility)',
    chunk_embedding     ARRAY<DOUBLE>           COMMENT 'Pre-computed embedding vector (3072 dimensions)',
    metadata            STRING                  COMMENT 'All contextual fields serialised as a JSON object',
    created_at          TIMESTAMP               COMMENT 'When this chunk row was written'
"""

RUN_LOG_TABLE_DDL_COLS = """
    run_id              STRING      NOT NULL    COMMENT 'Unique ID for this pipeline run',
    job_name            STRING                  COMMENT 'Databricks job name',
    start_time          TIMESTAMP   NOT NULL    COMMENT 'When the run started',
    end_time            TIMESTAMP               COMMENT 'When the run finished',
    duration_seconds    DOUBLE                  COMMENT 'Wall-clock duration of the run',
    docs_claimed        INT                     COMMENT 'Number of docs claimed for processing',
    docs_succeeded      INT                     COMMENT 'Number of docs successfully processed',
    docs_failed         INT                     COMMENT 'Number of docs that failed',
    chunks_written      INT                     COMMENT 'Total chunk rows written in this run',
    error_summary       STRING                  COMMENT 'Aggregated error summary if any failures',
    created_at          TIMESTAMP               COMMENT 'When this log row was written'
"""

DQ_LOG_TABLE_DDL_COLS = """
    dq_id               STRING      NOT NULL    COMMENT 'Unique ID for this finding (md5 of run_id + document_id + check_name)',
    run_id              STRING                  COMMENT 'Pipeline run ID that produced this finding',
    document_id         STRING                  COMMENT 'Document with the issue (NULL for global checks)',
    pdf_name            STRING                  COMMENT 'Human-readable PDF name (NULL for global checks)',
    check_name          STRING      NOT NULL    COMMENT 'Name of the validation check',
    severity            STRING      NOT NULL    COMMENT 'FAIL or WARN',
    failure_category    STRING                  COMMENT 'Routing hint for terminal failures. Current values seen: corrupt_source, image_only_or_no_text, pdf_parse_error, partial_embed, gateway_error, unknown. Open to grow as SRE/ops categorize new patterns. NULL for non-terminal checks.',
    detail              STRING                  COMMENT 'Description of the issue',
    created_at          TIMESTAMP               COMMENT 'When this finding was logged'
"""


def dq_log_schema():
    """Canonical Spark StructType for rows written to DQ_LOG_TABLE.

    Single source of truth for the DQ-log write schema — used by P1
    metadata, validation, and the generic backfill so they cannot drift.
    Mirrors DQ_LOG_TABLE_DDL_COLS above.
    """
    from pyspark.sql.types import StructType, StructField, StringType, TimestampType
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


# ─── Required Parameter Validation ───────────────────────────────────────────
# Fail fast if critical job parameters are missing. This runs on import (%run)
# so the notebook fails immediately with a clear message.

_REQUIRED_PARAMS = {
    "FSR_METADATA_TABLE": METADATA_TABLE,
    "FSR_CHUNK_TABLE": CHUNK_TABLE,
    "FSR_RUN_LOG_TABLE": RUN_LOG_TABLE,
    "FSR_DQ_LOG_TABLE": DQ_LOG_TABLE,
    "FSR_VS_ENDPOINT": VS_ENDPOINT_NAME,
    "FSR_VS_INDEX": VS_INDEX_NAME,
}

_missing = [name for name, val in _REQUIRED_PARAMS.items() if not val]
if _missing:
    _msg = (
        f"MISSING REQUIRED JOB PARAMETERS: {', '.join(_missing)}\n"
        f"These must be set as job parameters — there are no defaults.\n"
        f"Set them in the workflow YAML or pass as job parameters."
    )
    raise ValueError(_msg)
