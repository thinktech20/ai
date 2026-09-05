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

VIUD_CATALOG = get_runtime_param("FSR_CATALOG_VIUD", "viud")
VGPD_CATALOG = get_runtime_param("FSR_CATALOG_VGPD", "vgpd")

# POC schema — will be replaced with vaid.* schemas in production
POC_CATALOG = get_runtime_param("FSR_POC_CATALOG", "main")
POC_SCHEMA = get_runtime_param("FSR_POC_SCHEMA", "gp_services_sdg_poc")


# ─── Source Volumes (Bronze — read-only) ─────────────────────────────────────

PDF_VOLUME_PATHS = [
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fieldvision/fv_field_service_report",
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports",
]
# Additional volumes from DS-team POC (may not be needed in production):
# f"/Volumes/{VGPD_CATALOG}/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/"
# f"/Volumes/{VIUD_CATALOG}/ing_ud_fsr_manual/manual_field_service_report/UAT_Files/"


# ─── Table Names ─────────────────────────────────────────────────────────────

# Silver — document-level metadata registry (Process 1 output)
# Placeholder name uses POC schema; production TBD per naming convention decision
METADATA_TABLE = get_runtime_param(
    "FSR_METADATA_TABLE",
    f"{POC_CATALOG}.{POC_SCHEMA}.fsr_metadata_registry",
)

# Gold — chunk rows with materialized metadata + embeddings (Process 2 output)
CHUNK_TABLE = get_runtime_param(
    "FSR_CHUNK_TABLE",
    f"{POC_CATALOG}.{POC_SCHEMA}.fsr_chunks",
)

# Reference tables (Bronze — read-only enrichment sources)
IBAT_EQUIPMENT_TABLE = get_runtime_param(
    "FSR_IBAT_TABLE",
    f"{VGPD_CATALOG}.prm_std_views.ibat_equipment_mst",
)
EVENT_VISION_SOT_TABLE = get_runtime_param(
    "FSR_EVENT_VISION_TABLE",
    f"{VGPD_CATALOG}.fsr_std_views.eventmgmt_event_vision_sot",
)
FSR_PDF_REF_VIEW = get_runtime_param(
    "FSR_PDF_REF_VIEW",
    f"{VGPD_CATALOG}.fsr_std_views.fsr_pdf_ref",
)


# ─── Secrets / LLM Gateway ──────────────────────────────────────────────────

SECRET_SCOPE = get_runtime_param("FSR_SECRET_SCOPE", "fsr-pipeline")


def _get_secret(key: str, env_fallback: str = "") -> str:
    """Try Databricks secret scope, then widget (job param), then env var."""
    try:
        val = dbutils.secrets.get(scope=SECRET_SCOPE, key=key)  # noqa: F821
        if val:
            return val
    except Exception:
        pass
    # Job parameters are passed as widgets on serverless
    try:
        widget_val = dbutils.widgets.get(key)  # noqa: F821
        if widget_val is not None and str(widget_val).strip() != "":
            return str(widget_val).strip()
    except Exception:
        pass
    return os.getenv(key, env_fallback)


LITELLM_BASE_URL = decode_maybe_base64(
    _get_secret("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
)
LITELLM_API_KEY = decode_maybe_base64(
    _get_secret("LITELLM_API_KEY", "")
)

LLM_MODEL = get_runtime_param("FSR_LLM_MODEL", "gemini-3-flash")

_ssl_mode = get_runtime_param("FSR_LLM_VERIFY_SSL", "false").strip()
if _ssl_mode.lower() in ("0", "false", "f", "no", "n", "off"):
    LLM_VERIFY_SSL = False
elif os.path.exists(_ssl_mode):
    LLM_VERIFY_SSL = _ssl_mode
else:
    LLM_VERIFY_SSL = True


# ─── Embedding Model ────────────────────────────────────────────────────────

EMBEDDING_MODEL = get_runtime_param(
    "FSR_EMBEDDING_MODEL", "azure-text-embedding-3-large-1"
)
EMBEDDING_DIMENSION = int(get_runtime_param("FSR_EMBEDDING_DIMENSION", "3072"))


# ─── Vector Search ───────────────────────────────────────────────────────────

VS_ENDPOINT_NAME = get_runtime_param("FSR_VS_ENDPOINT", "pw-ser-sdg-vector-search")
VS_INDEX_NAME = get_runtime_param(
    "FSR_VS_INDEX",
    f"{POC_CATALOG}.{POC_SCHEMA}.vs_fsr_chunks",
)


# ─── Process 1 Tuning ───────────────────────────────────────────────────────

P1_BATCH_SIZE = int(get_runtime_param("FSR_BATCH_SIZE", "4"))
P1_MAX_PDFS = None  # set to int for dev testing
_max_pdfs_raw = get_runtime_param("FSR_MAX_PDFS", "")
if _max_pdfs_raw:
    P1_MAX_PDFS = int(_max_pdfs_raw)

P1_EXTRACT_WORKERS = int(get_runtime_param("FSR_PDF_EXTRACT_WORKERS", "16"))
P1_LLM_CONCURRENCY = int(get_runtime_param("FSR_LLM_CONCURRENCY", "3"))
P1_LLM_CONCURRENCY_MAX = int(get_runtime_param("FSR_LLM_CONCURRENCY_MAX", "6"))
P1_LLM_CONCURRENCY_MIN = 1
P1_BATCH_THREADS = int(get_runtime_param("FSR_BATCH_THREADS", "4"))
P1_BATCH_THREADS_START = int(get_runtime_param("FSR_BATCH_THREADS_START", "2"))
P1_THREAD_RAMP_SECONDS = int(get_runtime_param("FSR_BATCH_THREAD_RAMP_SECONDS", "10"))
P1_MAX_RETRIES = int(get_runtime_param("FSR_MAX_RETRIES", "3"))

FORCE_RESET = get_runtime_bool("FORCE_RESET", False)


# ─── Process 2 Tuning ───────────────────────────────────────────────────────

P2_BATCH_SIZE = int(get_runtime_param("FSR_P2_BATCH_SIZE", "50"))
P2_PDF_WORKERS = int(get_runtime_param("FSR_P2_PDF_WORKERS", "4"))


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
    COMPLETED = "completed"
    FAILED = "failed"


# ─── File Filters ────────────────────────────────────────────────────────────

SKIP_SUFFIXES = frozenset({
    ".crdownload", ".tmp", ".part", ".download",
    ".DS_Store", ".json", ".txt", ".csv", ".xlsx",
})


# ─── Metadata Table Schema (for CREATE TABLE) ───────────────────────────────

METADATA_TABLE_DDL_COLS = """
    pdf_name            STRING      NOT NULL    COMMENT 'UUID filename — primary key, join key to fsr_pdf_ref',
    volume_path         STRING      NOT NULL    COMMENT 'Full /Volumes/... path to the source PDF',
    title               STRING                  COMMENT 'Title extracted from page-1 text',
    customer            STRING                  COMMENT 'Customer / site name (nullable)',
    esn                 STRING                  COMMENT 'Equipment Serial Number (resolved via precedence)',
    esn_source          STRING                  COMMENT 'How ESN was resolved: sot / llm / regex / null',
    equipment_sys_id    STRING,
    equipment_type      STRING,
    equipment_code      STRING,
    event_type          STRING,
    ev_project_id       STRING,
    ev_equipment_event_id STRING,
    ofs_event_id        STRING,
    fsp_project_id      STRING,
    project_id          STRING,
    fsr_number          STRING,
    report_issued_date  STRING                  COMMENT 'YYYY-MM-DD normalized',
    outage_start_date   STRING                  COMMENT 'YYYY-MM-DD normalized',
    outage_end_date     STRING                  COMMENT 'YYYY-MM-DD normalized',
    prepared_by         STRING                  COMMENT 'Report author (nullable — needs verification)',
    approved_by         STRING                  COMMENT 'Report approver (nullable)',
    page_count          INT                     COMMENT 'Number of pages in the PDF',
    file_size_bytes     LONG                    COMMENT 'File size in bytes',
    file_last_modified  TIMESTAMP               COMMENT 'Last modified timestamp from volume listing',
    metadata_status     STRING      NOT NULL    COMMENT 'pending / completed / failed',
    metadata_error      STRING                  COMMENT 'Error message if metadata_status = failed',
    metadata_retry_count INT                    COMMENT 'Number of extraction retry attempts',
    metadata_version    INT                     COMMENT 'Bump when enrichment logic changes',
    chunk_status        STRING      NOT NULL    COMMENT 'pending / completed / failed',
    chunk_error         STRING                  COMMENT 'Error message if chunk_status = failed',
    ingested_at         TIMESTAMP               COMMENT 'When this row was first created',
    scraped_at          TIMESTAMP               COMMENT 'When metadata scraping completed',
    updated_at          TIMESTAMP               COMMENT 'Last modification timestamp'
"""

CHUNK_TABLE_DDL_COLS = """
    chunk_id            STRING      NOT NULL    COMMENT 'pdf_name + chunk_index hash',
    pdf_name            STRING      NOT NULL    COMMENT 'FK to metadata registry (UUID filename)',
    chunk_index         INT         NOT NULL    COMMENT '0-based chunk position within document',
    chunk_text          STRING      NOT NULL    COMMENT 'Chunk content',
    embedding           ARRAY<DOUBLE>           COMMENT 'Pre-computed embedding vector (3072-dim)',
    title               STRING                  COMMENT 'Materialized from metadata registry',
    esn                 STRING                  COMMENT 'Materialized from metadata registry',
    equipment_type      STRING                  COMMENT 'Materialized from metadata registry',
    event_type          STRING                  COMMENT 'Materialized from metadata registry',
    report_issued_date  STRING                  COMMENT 'Materialized from metadata registry',
    page_count          INT                     COMMENT 'Materialized from metadata registry',
    chunk_count         INT                     COMMENT 'Total chunks in this document',
    start_page          INT                     COMMENT 'First page this chunk spans',
    end_page            INT                     COMMENT 'Last page this chunk spans',
    chunk_size          INT                     COMMENT 'Character length of chunk_text',
    ingested_at         TIMESTAMP               COMMENT 'When this chunk row was written'
"""
