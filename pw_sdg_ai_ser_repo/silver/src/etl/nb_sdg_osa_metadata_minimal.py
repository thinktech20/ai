# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_osa_metadata_minimal — Process 1A: Minimal Metadata Extraction (Silver)
#
# Purpose:
# - Discover PDF documents from configured source volumes
# - Register/refresh stub rows in the metadata table
# - Extract a structured document profile via the SAME LiteLLM-backed prompt/
#   schema used by data_service.services.osa_document_profile
#   (doc7_profile_extraction_system.txt), instead of deterministic regex
#   scraping of the PDF text
# - Mark per-document extraction status (completed / failed)
#
# Multi-family routing:
# - DOCUMENT_FAMILY_KEYS (list) drives one discovery/extract/write pass PER
#   FAMILY in a single job run, e.g. ["gek", "kb", "psib"]. Each family writes
#   to its own table, derived as FSR_METADATA_TABLE_TEMPLATE.format(family=...)
#   (default "vaid.ai_sot_field_service_report.{family}_metadata", matching the
#   already-deployed gek_metadata/kb_metadata/psib_metadata/til_metadata
#   convention) unless FSR_METADATA_TABLE is explicitly set (single-family
#   override only). A family with no matching files in the source volumes is
#   skipped, not fatal to the rest of the run. DOCUMENT_FAMILY_KEY (singular)
#   is kept as a backward-compatible single-family fallback.
#
# Concurrency:
# - Stage C's per-document extraction (each a blocking LiteLLM HTTP call) runs
#   on a ThreadPoolExecutor with MAX_WORKERS workers per family, instead of
#   sequentially. I/O-bound work, so threads give real wall-clock speedup.
#
# NOTE:
# ev_osa_parent (document family: GEK / GER / ETC / PSIB / KB) is now derived
# from the doc_id itself using the same DOC_TYPE_PATTERNS regex dict as
# data_service.services.osa_document_profile, instead of scanning the full
# PDF text for keyword mentions.
#
# The doc7 prompt schema does not extract fsr_number / outage_start_date /
# outage_end_date / prepared_by / approved_by, so those columns are left null
# here and are expected to be backfilled by enrich_updates_from_osa() from the
# OSA source table where available. report_issued_date and xxx_project_id
# (cross-referenced GEK/TIL/KB doc IDs) ARE document-level facts readable
# directly from the PDF text, so they are extracted deterministically via
# regex (extract_report_issued_date / extract_referenced_documents) alongside
# the LLM profile call, same as the prior deterministic-only pipeline.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pdfplumber python-docx

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import base64
import os
import logging
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import pdfplumber
from common.tils.til_llm_client import call_llm_for_doc_profile
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    coalesce,
    concat,
    expr,
    lit,
    lower,
    regexp_replace,
)
from pyspark.sql.types import (
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

try:
    dbutils  # type: ignore[name-defined]  # noqa: B018
except Exception:
    dbutils = None  # type: ignore[assignment]

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.p1a.metadata_minimal")

EXTRACTION_METHOD = "litellm_doc7_profile_v1"
OSA_DOC_JSON_COLUMN = "osa_doc_json"


# Notebook widgets for runtime-config parity with TIL profile flow.
try:
    dbutils.widgets.text("TIL_LLM_MAX_TOKENS", "", "Override LLM max tokens (blank = config default)")
    dbutils.widgets.text(
        "LITELLM_BASE_URL",
        "https://dev-gateway.apps.gevernova.net",
        "LiteLLM gateway base URL (blank = use default)",
    )
    dbutils.widgets.text(
        "LITELLM_API_KEY",
        "",
        "LiteLLM API key (blank = use env / secret scope)",
    )
    dbutils.widgets.text(
        "OSA_DOCUMENT_PROFILE_PROMPT_PATH",
        "",
        "Path to doc7_profile_extraction_system.txt (blank = use HARDCODE_CONFIG default)",
    )
    dbutils.widgets.text(
        "DOCUMENT_FAMILY_KEYS",
        "",
        "Comma-separated family tokens to process in one run, e.g. 'gek,kb,psib' (blank = DOCUMENT_FAMILY_KEY)",
    )
    dbutils.widgets.text(
        "MAX_WORKERS",
        "",
        "Concurrent PDF/LLM extraction workers per family (blank = HARDCODE_CONFIG default)",
    )
    dbutils.widgets.text("FORCE_REPROCESS", "false", "Force reprocess all docs (skip incremental detection; true/false)")
except Exception:
    pass


# COMMAND ----------

# ── Minimal Document-Family Job Config (only required settings) ─────────────
# Hardcode values here when you want notebook-local control.
HARDCODE_CONFIG = {
    # Document family filter token used for filename discovery (example: "gek", "til").
    # Kept for single-family backward compatibility; prefer DOCUMENT_FAMILY_KEYS below.
    "DOCUMENT_FAMILY_KEY": "gek",
    # Process multiple families in one job run, e.g. ["gek", "kb", "psib"]. Each family
    # gets its own discovery/extract/write pass and its own table (derived from
    # FSR_METADATA_TABLE_TEMPLATE) unless FSR_METADATA_TABLE is explicitly set, which
    # forces single-family mode into that exact table.
    "DOCUMENT_FAMILY_KEYS": [],
    # Example: ["/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/UAT_Files"]
    "FSR_SOURCE_VOLUME_PATHS": [],
    # Example: "main.gp_services_sdg_poc.osa_table"
    "FSR_OSA_TABLE": "",
    # Explicit single-table override. Leave blank to derive one table per family from
    # FSR_METADATA_TABLE_TEMPLATE (matches the already-deployed
    # vaid.ai_sot_field_service_report.{gek,kb,psib,til}_metadata convention).
    "FSR_METADATA_TABLE": "",
    "FSR_METADATA_TABLE_TEMPLATE": "vaid.ai_sot_field_service_report.{family}_metadata",
    # None or 0 = no cap
    "FSR_MAX_PDFS": None,
    # Failed-doc retry limit
    "FSR_MAX_RETRIES": 3,
    # True = extract and print only (no table writes)
    "PRINT_ONLY_MODE": False,
    # Optional: persist print-only merge preview as a table for clean inspection.
    "WRITE_PREVIEW_TABLE": False,
    # Explicit single preview-table override; leave blank to derive per family from
    # FSR_PREVIEW_TABLE_TEMPLATE.
    "PREVIEW_TABLE_NAME": "",
    "FSR_PREVIEW_TABLE_TEMPLATE": "vaid.ai_sot_field_service_report.{family}_metadata_preview",
    # Same prompt file used by data_service.services.osa_document_profile
    # (doc7_profile_extraction_system.txt). Assumed accessible on the cluster
    # at this path (e.g. a Volumes path deployed alongside the source PDFs).
    "OSA_DOCUMENT_PROFILE_PROMPT_PATH": "",
    "OSA_DOCUMENT_PROFILE_MODEL": "bedrock-claude-sonnet-4.6",
    "OSA_DOCUMENT_PROFILE_MAX_TOKENS": 4000,
    "OSA_DOCUMENT_PROFILE_RETRY_MAX_TOKENS": 12000,
    # "attachment" (default) sends the PDF as an inline base64 file part -- only
    # supported by vision-capable gateway models (e.g. bedrock-claude). "text" sends the
    # already-extracted page text instead, for models/keys that reject file content
    # (e.g. Azure OpenAI models require an uploaded file_id, not inline base64).
    "OSA_PDF_LLM_MODE": "attachment",
    # Concurrent PDF/LLM extraction workers per family. Stage C is I/O-bound (each
    # worker blocks on a LiteLLM HTTP call), so threads cut real wall-clock time.
    "MAX_WORKERS": 4,
    "FORCE_REPROCESS": False,
    # Fallback source for LITELLM_API_KEY when not supplied via widget/env/job param.
    # Never hardcode the key itself here -- only the scope/key name pointing at it.
    "LITELLM_SECRET_SCOPE": "fsr-pipeline",
    "LITELLM_SECRET_KEY": "LITELLM_API_KEY",
}


def _get_runtime_param(name: str, default: str = "") -> str:
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


def _get_secret_fallback(scope_name: str, key_name: str) -> str:
    """Best-effort fallback: read a value from a Databricks secret scope. Never raises;
    returns '' if dbutils/secrets are unavailable or the scope/key is missing so callers
    can layer this after widget/env checks without special-casing failures."""
    if not scope_name or not key_name or dbutils is None:
        return ""
    try:
        value = dbutils.secrets.get(scope=scope_name, key=key_name)  # noqa: F821
        return (value or "").strip()
    except Exception as e:  # noqa: BLE001
        log.warning("Could not read secret %s/%s: %s", scope_name, key_name, e)
        return ""


def _parse_runtime_list(name: str) -> list[str]:
    raw = _get_runtime_param(name, "")
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[,;\n]", raw) if part.strip()]


# Precedence for every _resolve_*_param helper below: an explicit runtime value
# (job base_parameter / widget / env var) always wins; HARDCODE_CONFIG is only a
# fallback default for interactive/notebook-local runs where no runtime value was
# supplied. (Previously HARDCODE_CONFIG won whenever it held a "real" bool/int --
# including its own False/4/etc. defaults -- which silently discarded job
# parameters like PRINT_ONLY_MODE/WRITE_PREVIEW_TABLE/MAX_WORKERS.)
def _resolve_list_param(name: str) -> list[str]:
    runtime = _parse_runtime_list(name)
    if runtime:
        return runtime
    hard = HARDCODE_CONFIG.get(name)
    return hard if isinstance(hard, list) else []


def _resolve_str_param(name: str) -> str:
    runtime = _get_runtime_param(name, "").strip()
    if runtime:
        return runtime
    hard = HARDCODE_CONFIG.get(name)
    return hard.strip() if isinstance(hard, str) else ""


def _resolve_int_param(name: str, default: int) -> int:
    raw = _get_runtime_param(name, "").strip()
    if raw:
        return int(raw)
    hard = HARDCODE_CONFIG.get(name)
    return hard if isinstance(hard, int) else default


def _resolve_bool_param(name: str, default: bool) -> bool:
    raw = _get_runtime_param(name, "").strip().lower()
    if raw:
        return raw in ("1", "true", "t", "yes", "y", "on")
    hard = HARDCODE_CONFIG.get(name)
    return hard if isinstance(hard, bool) else default


PDF_VOLUME_PATHS = _resolve_list_param("FSR_SOURCE_VOLUME_PATHS")
OSA_SOURCE_TABLE = _resolve_str_param("FSR_OSA_TABLE")
METADATA_TABLE = _resolve_str_param("FSR_METADATA_TABLE")
METADATA_TABLE_TEMPLATE = _resolve_str_param("FSR_METADATA_TABLE_TEMPLATE")
PREVIEW_TABLE_TEMPLATE = _resolve_str_param("FSR_PREVIEW_TABLE_TEMPLATE")
_max_pdfs_raw = _get_runtime_param("FSR_MAX_PDFS", "").strip()
if _max_pdfs_raw:
    P1_MAX_PDFS = int(_max_pdfs_raw)
else:
    _max_pdfs_val = HARDCODE_CONFIG.get("FSR_MAX_PDFS")
    P1_MAX_PDFS = _max_pdfs_val if isinstance(_max_pdfs_val, int) and _max_pdfs_val > 0 else None
P1_MAX_RETRIES = _resolve_int_param("FSR_MAX_RETRIES", 3)
PRINT_ONLY_MODE = _resolve_bool_param("PRINT_ONLY_MODE", False)
WRITE_PREVIEW_TABLE = _resolve_bool_param("WRITE_PREVIEW_TABLE", False)
PREVIEW_TABLE_NAME = _resolve_str_param("PREVIEW_TABLE_NAME")
DEBUG_DOC_ID = _resolve_str_param("DEBUG_DOC_ID").lower()
MAX_WORKERS = max(1, _resolve_int_param("MAX_WORKERS", 4))
FORCE_REPROCESS = _resolve_bool_param("FORCE_REPROCESS", False)

# Allowlist of valid document family keys (security: prevent Spark SQL injection via string formatting)
_ALLOWED_FAMILY_KEYS = {"gek", "ger", "kb", "psib", "til", "etc"}



DOCUMENT_FAMILY_KEY = (_resolve_str_param("DOCUMENT_FAMILY_KEY") or "gek").strip().lower()
DOCUMENT_FAMILY_KEYS = [k.strip().lower() for k in _resolve_list_param("DOCUMENT_FAMILY_KEYS") if k.strip()]
if not DOCUMENT_FAMILY_KEYS:
    DOCUMENT_FAMILY_KEYS = [DOCUMENT_FAMILY_KEY] if DOCUMENT_FAMILY_KEY else []
if not DOCUMENT_FAMILY_KEYS:
    raise ValueError(
        "DOCUMENT_FAMILY_KEYS (or DOCUMENT_FAMILY_KEY) must resolve to at least one "
        "non-empty family token, e.g. 'gek', 'kb', 'psib', 'til'."
    )

# Validate all family keys against allowlist (security: prevent SQL injection)
if DOCUMENT_FAMILY_KEY not in _ALLOWED_FAMILY_KEYS:
    raise ValueError(f"Unrecognized DOCUMENT_FAMILY_KEY: {DOCUMENT_FAMILY_KEY!r}")
# An explicit single-table override only makes sense for a single family.
if METADATA_TABLE and len(DOCUMENT_FAMILY_KEYS) > 1:
    raise ValueError(
        "FSR_METADATA_TABLE is an explicit single-table override and cannot be combined "
        "with multiple DOCUMENT_FAMILY_KEYS; leave FSR_METADATA_TABLE blank to derive "
        "one table per family from FSR_METADATA_TABLE_TEMPLATE."
    )


def resolve_metadata_table_for_family(family_key: str) -> str:
    if METADATA_TABLE:
        return METADATA_TABLE
    if not METADATA_TABLE_TEMPLATE:
        raise ValueError("Either FSR_METADATA_TABLE or FSR_METADATA_TABLE_TEMPLATE is required.")
    return METADATA_TABLE_TEMPLATE.format(family=family_key)


def resolve_preview_table_for_family(family_key: str) -> str:
    if PREVIEW_TABLE_NAME:
        return PREVIEW_TABLE_NAME
    if not PREVIEW_TABLE_TEMPLATE:
        return ""
    return PREVIEW_TABLE_TEMPLATE.format(family=family_key)

OSA_DOCUMENT_PROFILE_PROMPT_PATH = _resolve_str_param("OSA_DOCUMENT_PROFILE_PROMPT_PATH")
OSA_DOCUMENT_PROFILE_MODEL = _resolve_str_param("OSA_DOCUMENT_PROFILE_MODEL") or "bedrock-claude-sonnet-4.6"
OSA_DOCUMENT_PROFILE_MAX_TOKENS = _resolve_int_param("OSA_DOCUMENT_PROFILE_MAX_TOKENS", 4000)
OSA_DOCUMENT_PROFILE_RETRY_MAX_TOKENS = _resolve_int_param("OSA_DOCUMENT_PROFILE_RETRY_MAX_TOKENS", 12000)
OSA_PDF_LLM_MODE = (
    _resolve_str_param("OSA_PDF_LLM_MODE") or HARDCODE_CONFIG.get("OSA_PDF_LLM_MODE", "attachment")
).strip().lower()
# Same LITELLM_VERIFY_TLS param name/semantics as nb_sdg_til_profile.py: set false only
# to work around corp dev TLS cert-chain issues on the LiteLLM gateway.
LITELLM_VERIFY_TLS = _resolve_bool_param("LITELLM_VERIFY_TLS", True)


class MetadataStatus:
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


SKIP_SUFFIXES = frozenset(
    {
        ".crdownload",
        ".tmp",
        ".part",
        ".download",
        ".DS_Store",
        ".json",
        ".txt",
        ".csv",
        ".xlsx",
    }
)
# Legacy binary .doc is deliberately excluded: no reliable in-cluster text extractor
# (python-docx only reads OOXML .docx). Matching .doc files are skipped with a warning
# in process_document_family() rather than stubbed with placeholder metadata.
SUPPORTED_DOC_EXTENSIONS = ("pdf", "docx")
SUPPORTED_DOC_EXTENSIONS_REGEX = "|".join(SUPPORTED_DOC_EXTENSIONS)


if not PRINT_ONLY_MODE and not METADATA_TABLE and not METADATA_TABLE_TEMPLATE:
    raise ValueError(
        "Either FSR_METADATA_TABLE or FSR_METADATA_TABLE_TEMPLATE is required "
        "(set as a job parameter/widget or in HARDCODE_CONFIG)."
    )


REQUIRED_METADATA_COLUMNS: dict[str, str] = {
    "document_id": "STRING",
    "unique_key": "STRING",
    "pdf_name": "STRING",
    "volume_path": "STRING",
    "file_size_bytes": "BIGINT",
    "file_last_modified": "TIMESTAMP",
    "metadata_status": "STRING",
    "chunk_status": "STRING",
    "metadata_retry_count": "INT",
    "chunk_retry_count": "INT",
    "ingested_at": "TIMESTAMP",
    "title": "STRING",
    "fsr_number": "STRING",
    "document_summary": "STRING",
    "report_issued_date": "STRING",
    "outage_start_date": "STRING",
    "outage_end_date": "STRING",
    "prepared_by": "STRING",
    "approved_by": "STRING",
    "esn_source": "STRING",
    "xxx_project_id": "STRING",
    "ev_osa_parent": "STRING",
    "event_type": "STRING",
    "ev_osa_scope": "STRING",
    "page_count": "INT",
    "metadata_error": "STRING",
    "scraped_at": "TIMESTAMP",
    "ev_osa_scope_title": "STRING",
    "ev_osa_item": "STRING",
    "ev_osa_disposition": "STRING",
    "ev_osa_status": "STRING",
    "ev_osa_milestone": "STRING",
    "ev_milestone": "STRING",
    "extraction_confidence": "STRING",
    "raw_text": "STRING",
    OSA_DOC_JSON_COLUMN: "STRING",
}


def ensure_metadata_table_exists(table_name: str) -> None:
    if not table_name:
        return

    columns_sql = ",\n            ".join(
        f"{column_name} {column_type}" for column_name, column_type in REQUIRED_METADATA_COLUMNS.items()
    )
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
            {columns_sql}
    )
    USING DELTA
    """

    try:
        spark.sql(create_sql)
        log.info(f"Ensured metadata table exists: {table_name}")
    except Exception as e:  # noqa: BLE001
        raise ValueError(
            f"Unable to create metadata table {table_name}. "
            "Verify catalog/schema exists and that this cluster has CREATE TABLE permission. "
            f"Original error: {e}"
        ) from e


def ensure_metadata_column_exists(table_name: str, column_name: str, column_type: str = "STRING") -> None:
    if not table_name or not column_name:
        return
    try:
        existing_cols = {c.lower() for c in spark.table(table_name).columns}
    except Exception as e:  # noqa: BLE001
        log.warning(f"Cannot inspect metadata table {table_name} for column check: {e}")
        return

    if column_name.lower() in existing_cols:
        return

    try:
        spark.sql(f"ALTER TABLE {table_name} ADD COLUMNS ({column_name} {column_type})")
        log.info(f"Added missing metadata column {column_name} ({column_type}) to {table_name}")
    except Exception as e:  # noqa: BLE001
        log.warning(f"Failed to add metadata column {column_name} to {table_name}: {e}")


# COMMAND ----------

log.info("=== Process 1A — Minimal Metadata Extraction ===")
log.info(f"  Print only mode: {PRINT_ONLY_MODE}")
log.info(f"  OSA doc JSON column: {OSA_DOC_JSON_COLUMN}")
log.info(f"  OSA source table: {OSA_SOURCE_TABLE or 'n/a'}")
log.info(f"  Write preview table: {WRITE_PREVIEW_TABLE}")
log.info(f"  Debug doc id   : {DEBUG_DOC_ID or 'n/a'}")
log.info(f"  Doc family keys: {DOCUMENT_FAMILY_KEYS}")
log.info(f"  Allowed file extensions: {SUPPORTED_DOC_EXTENSIONS}")
log.info(f"  Volumes        : {PDF_VOLUME_PATHS}")
log.info(f"  Max PDFs       : {P1_MAX_PDFS or 'unlimited'} (per family)")
log.info(f"  Max retries    : {P1_MAX_RETRIES}")
log.info(f"  Max workers    : {MAX_WORKERS} (concurrent PDF/LLM extraction, per family)")
log.info(f"  Force reprocess: {FORCE_REPROCESS}")
log.info(f"  Profile model  : {OSA_DOCUMENT_PROFILE_MODEL}")
log.info(f"  Profile prompt : {OSA_DOCUMENT_PROFILE_PROMPT_PATH or 'n/a'}")
log.info(f"  LiteLLM URL    : {_get_runtime_param('LITELLM_BASE_URL', 'https://dev-gateway.apps.gevernova.net').rstrip('/')}")

for i, vol in enumerate(PDF_VOLUME_PATHS, start=1):
    log.info(f"  Source volume [{i}]: {vol}")
    log.info(f"  LIST probe     [{i}]: LIST '{vol}'")

if not PDF_VOLUME_PATHS:
    raise ValueError(
        "FSR_SOURCE_VOLUME_PATHS job parameter is required "
        "(comma-separated full /Volumes/... paths)"
    )


def ensure_metadata_table_ready(table_name: str) -> None:
    """Create the table (and backfill any missing columns) for one family's metadata table."""
    ensure_metadata_table_exists(table_name)
    for _col_name, _col_type in REQUIRED_METADATA_COLUMNS.items():
        ensure_metadata_column_exists(table_name, _col_name, _col_type)
    target_cols = {c.lower() for c in spark.table(table_name).columns}
    missing_required_cols = [c for c in REQUIRED_METADATA_COLUMNS if c.lower() not in target_cols]
    if missing_required_cols:
        raise ValueError(
            f"Target table {table_name} is missing required columns after setup checks: {missing_required_cols}"
        )


# COMMAND ----------

# LIST output differs by DBR runtime. Normalize to one bigint ms column.
def normalize_list_df(df):
    cols = set(df.columns)
    if "modificationTime" in cols:
        from pyspark.sql.functions import unix_millis

        return df.withColumn("mod_time_ms", unix_millis(col("modificationTime")))
    if "modification_time" in cols:
        return df.withColumn("mod_time_ms", col("modification_time").cast("long"))
    raise ValueError(f"LIST output missing modification time column; got {df.columns}")


def _family_name_match(family_key: str):
    """Column expression matching filenames belonging to a family. ETC docs are also filed
    under an abbreviated 'e<3-digit-number>[r<rev>]' convention (e.g. e147r3.pdf) with no
    literal 'etc' substring, so match that pattern too when family_key == 'etc'."""
    name_col = lower(col("name"))
    # Allow a digit immediately after the family key (the dominant real-world
    # convention -- "GEK103566_M.pdf", "KB0011385.pdf" have NO separator between
    # the prefix and the id) while still rejecting a following LETTER (so e.g.
    # "etcetera.pdf" doesn't false-match "etc"). A prior `(?:[^a-z0-9]|$)` variant
    # required a non-alphanumeric separator or end-of-string right after the
    # prefix, which silently dropped the majority of real gek/kb filenames.
    family_prefix_pattern = rf"^(?:l7\s*[:_-]\s*)?{re.escape(family_key)}(?:[^a-z]|$)"
    name_match = name_col.rlike(family_prefix_pattern)
    if family_key == "etc":
        name_match = name_match | name_col.rlike(r"^(?:l7\s*[:_-]\s*)?e\d{3}(?:r\d+)?(?:[^a-z0-9]|$)")
    return name_match


def has_family_file(volumes: list[str], family_key: str) -> bool:
    """Return True if any source volume has a filename matching the configured family key."""
    for vol in volumes:
        try:
            list_df = normalize_list_df(spark.sql(f"LIST '{vol}'"))
            match_df = (
                list_df.filter(~lower("name").rlike(r"/$"))
                .filter(lower("name").rlike(rf"\.({SUPPORTED_DOC_EXTENSIONS_REGEX})$"))
                .filter(_family_name_match(family_key))
            )
            match_count = match_df.limit(1).count()
            if match_count > 0:
                log.info("%s gate: found at least one matching file in %s", family_key.upper(), vol)
                sample_rows = match_df.select("name").limit(10).collect()
                sample_names = [r["name"] for r in sample_rows]
                log.info(
                    "%s gate: sample matching filenames in %s: %s",
                    family_key.upper(),
                    vol,
                    sample_names,
                )
                return True
            log.info("%s gate: no matching filenames in %s", family_key.upper(), vol)
        except Exception as e:  # noqa: BLE001
            log.warning("%s gate: cannot scan volume %s: %s", family_key.upper(), vol, e)
    return False


# Per-family file-presence gate now lives inside process_document_family() below, so
# one family with zero matching files just gets skipped instead of aborting the whole
# multi-family run via dbutils.notebook.exit().


# Convert volume path to local DBFS path for pdfplumber open().
def to_local_dbfs_path(volume_path: str) -> str:
    # Unity Catalog Volumes are typically accessible directly as /Volumes/... for
    # Python file IO. Keep that path first and fall back to /dbfs only if needed.
    if volume_path.startswith("dbfs:/"):
        volume_path = volume_path.replace("dbfs:/", "/dbfs/", 1)

    if volume_path.startswith("/Volumes/") and os.path.exists(volume_path):
        return volume_path

    if volume_path.startswith("/Volumes/"):
        dbfs_fuse_path = f"/dbfs{volume_path}"
        return dbfs_fuse_path

    return volume_path


# ── LLM profile extraction, mirroring data_service.services.osa_document_profile ──

# Same doc-id family patterns as data_service.services.osa_document_profile,
# reused so ev_osa_parent is derived deterministically from the doc_id itself.
_GEK_DOC_ID_RE = re.compile(r"(?i)GEK\s*[-_]?\s*(\d{5,7})")
_GER_DOC_ID_RE = re.compile(r"(?i)(?:L7\s*:\s*)?GER\s*[-_]?\s*(\d{3,4})")
_ETC_DOC_ID_RE = re.compile(r"(?i)(?:ETC|e)\s*[-_]*\s*(\d{3})(?:r\d+)?")
_PSIB_DOC_ID_RE = re.compile(
    r"(?i)(?:L7\s*:\s*)?(?:PSIB|PSSB|PSIB\s*/\s*PSSB)\s*[-_]?\s*(\d{8}[A-Z]?)(?:\s*[-_]?\s*R\d+)?"
)
_KB_DOC_ID_RE = re.compile(r"(?i)KB\s*[-_]*\s*(\d{6,7})")

DOC_TYPE_PATTERNS = {
    "GEK": _GEK_DOC_ID_RE,
    "GER": _GER_DOC_ID_RE,
    "ETC": _ETC_DOC_ID_RE,
    "PSIB": _PSIB_DOC_ID_RE,
    "KB": _KB_DOC_ID_RE,
}


def detect_ev_osa_parent_from_doc_id(document_id: str) -> str | None:
    for doc_type, pattern in DOC_TYPE_PATTERNS.items():
        if pattern.search(document_id or ""):
            return f"L7: {doc_type}"
    return None


def _normalize_profile(doc_id: str, filename: str, profile: dict) -> dict:
    acceptance = profile.get("acceptance_guidance")
    if not isinstance(acceptance, dict):
        acceptance = {}

    def _normalize_unit_acceptance(unit: dict):
        unit_acceptance = unit.get("acceptance_guidance")
        if isinstance(unit_acceptance, (list, dict)):
            return unit_acceptance
        title = unit.get("work_item_title")
        if title and title in acceptance:
            legacy_value = acceptance.get(title)
            if isinstance(legacy_value, (list, dict)):
                return legacy_value
        return []

    units = profile.get("units_of_work") if isinstance(profile.get("units_of_work"), list) else []
    return {
        "doc_id": doc_id,
        "filename": filename,
        "title": profile.get("title") or "",
        "original_language": profile.get("original_language") or "",
        "purpose": profile.get("purpose") or "",
        "purpose_snippets": profile.get("purpose_snippets") or [],
        "units_of_work": [
            {
                "work_item_title": unit.get("work_item_title") or "",
                "work_item_description": unit.get("work_item_description") or "",
                "scope_of_work": unit.get("scope_of_work") or [],
                "completion_criteria": unit.get("completion_criteria") or "",
                "parts_referenced": unit.get("parts_referenced") or unit.get("part_numbers_referenced") or [],
                "acceptance_guidance": _normalize_unit_acceptance(unit),
                "work_item_confidence": unit.get("work_item_confidence") or "",
            }
            for unit in units
            if isinstance(unit, dict)
        ],
        "source_confidence": profile.get("source_confidence") or profile.get("extraction_confidence") or "",
    }


def normalize_extracted_date(date_text: str) -> str:
    date_text = (date_text or "").strip()
    # Normalize year-first numeric dates (YYYY-M-D, YYYY/M/D) to YYYY-MM-DD.
    ymd_match = re.fullmatch(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", date_text)
    if ymd_match:
        year, month, day = ymd_match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return date_text


def extract_date_near_label(text: str, labels: list[str]) -> str | None:
    date_pattern = r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})"
    for label in labels:
        pattern = rf"(?im)\b{label}\b\s*[:\-,]?\s*.*?{date_pattern}"
        match = re.search(pattern, text)
        if match:
            return normalize_extracted_date(match.group(1))
    return None


def extract_first_date_general(text: str) -> str | None:
    date_pattern = r"(\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})"
    match = re.search(rf"(?is){date_pattern}", text or "")
    if match:
        return normalize_extracted_date(match.group(1))
    return None


def extract_report_issued_date(text: str) -> str | None:
    # Ported from the prior deterministic-regex pipeline: the doc7 LLM schema does
    # not extract this, but it's a fixed document-level fact (revision/issue date
    # printed on the document) readable directly from the PDF text.
    labeled_date = extract_date_near_label(
        text,
        ["report issued date", "issued date", "report date", "revised", "released"],
    )
    if labeled_date:
        return labeled_date
    return extract_first_date_general(text)


def extract_referenced_documents(text: str) -> str | None:
    # Ported from the prior deterministic-regex pipeline: cross-referenced
    # GEK/TIL/KB document IDs mentioned in the body text (xxx_project_id column).
    refs: set[str] = set()
    for m in re.finditer(r"\bGEK[\s:_-]?([0-9][0-9A-Z.-]*)", text, re.IGNORECASE):
        refs.add(f"GEK-{m.group(1).upper().rstrip('.-')}")
    for m in re.finditer(r"\bTIL[\s:_-]?([0-9][0-9A-Z.-]*)", text, re.IGNORECASE):
        refs.add(f"TIL-{m.group(1).upper().rstrip('.-')}")
    for m in re.finditer(r"\bKB00[0-9A-Z][\w-]*", text, re.IGNORECASE):
        refs.add(m.group(0).upper())
    if not refs:
        return None
    return "; ".join(sorted(refs))


_EXTRACTION_PROMPT_CACHE: str | None = None
_EXTRACTION_PROMPT_LOCK = threading.Lock()


def load_extraction_prompt_cached() -> str:
    # Double-checked locking: Stage C now calls this from multiple worker threads
    # concurrently, so guard the first (cache-populating) read.
    global _EXTRACTION_PROMPT_CACHE
    if _EXTRACTION_PROMPT_CACHE is not None:
        return _EXTRACTION_PROMPT_CACHE
    with _EXTRACTION_PROMPT_LOCK:
        if _EXTRACTION_PROMPT_CACHE is not None:
            return _EXTRACTION_PROMPT_CACHE
        if not OSA_DOCUMENT_PROFILE_PROMPT_PATH:
            raise ValueError(
                "OSA_DOCUMENT_PROFILE_PROMPT_PATH is required (same doc7_profile_extraction_system.txt "
                "prompt used by data_service.services.osa_document_profile)."
            )
        with open(OSA_DOCUMENT_PROFILE_PROMPT_PATH, "r", encoding="utf-8") as fh:
            _EXTRACTION_PROMPT_CACHE = fh.read()
        return _EXTRACTION_PROMPT_CACHE


def _resolve_litellm_auth() -> tuple[str, str, str]:
    """Return (api_key, base_url, system_prompt)."""
    api_key = _get_runtime_param("LITELLM_API_KEY", "").strip()
    if not api_key:
        api_key = _get_secret_fallback(
            HARDCODE_CONFIG.get("LITELLM_SECRET_SCOPE", ""),
            HARDCODE_CONFIG.get("LITELLM_SECRET_KEY", "LITELLM_API_KEY"),
        )
    if not api_key:
        raise RuntimeError(
            "Missing required LITELLM_API_KEY (checked widget/env, then Databricks secret "
            f"scope '{HARDCODE_CONFIG.get('LITELLM_SECRET_SCOPE', '')}')."
        )
    base_url = _get_runtime_param("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net").rstrip("/")
    system_prompt = load_extraction_prompt_cached()
    return api_key, base_url, system_prompt


def run_profile_llm_with_pdf(document_id: str, local_pdf_path: str, filename: str) -> dict:
    """Call the LiteLLM gateway with the PDF attached."""
    api_key, base_url, system_prompt = _resolve_litellm_auth()

    with open(local_pdf_path, "rb") as fh:
        pdf_bytes = fh.read()
    encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    base64_pdf = f"data:application/pdf;base64,{encoded_pdf}"
    user_prompt = (
        "Extract the full document profile from the attached PDF.\n"
        f"Document ID: {document_id}\n"
        f"Filename: {filename}\n"
        "Follow the required JSON schema strictly.\n"
        "Return only valid JSON."
    )
    user_content = [
        {"type": "text", "text": user_prompt},
        {"type": "file", "file": {"file_data": base64_pdf}},
    ]
    parsed = call_llm_for_doc_profile(
        system_prompt,
        user_content,
        api_key=api_key,
        base_url=base_url,
        model=OSA_DOCUMENT_PROFILE_MODEL,
        max_tokens=OSA_DOCUMENT_PROFILE_MAX_TOKENS,
        retry_max_tokens=OSA_DOCUMENT_PROFILE_RETRY_MAX_TOKENS,
        verify_ssl=LITELLM_VERIFY_TLS,
    )
    return _normalize_profile(document_id, filename, parsed)


def run_profile_llm_with_text(document_id: str, doc_text: str, filename: str) -> dict:
    """Call the LiteLLM gateway with extracted document text inline (no file attachment)."""
    api_key, base_url, system_prompt = _resolve_litellm_auth()

    user_prompt = (
        "Extract the full document profile from the document text below.\n"
        f"Document ID: {document_id}\n"
        f"Filename: {filename}\n"
        "Follow the required JSON schema strictly.\n"
        "Return only valid JSON.\n\n"
        "--- DOCUMENT TEXT START ---\n"
        f"{doc_text}\n"
        "--- DOCUMENT TEXT END ---"
    )
    user_content = [{"type": "text", "text": user_prompt}]
    parsed = call_llm_for_doc_profile(
        system_prompt,
        user_content,
        api_key=api_key,
        base_url=base_url,
        model=OSA_DOCUMENT_PROFILE_MODEL,
        max_tokens=OSA_DOCUMENT_PROFILE_MAX_TOKENS,
        retry_max_tokens=OSA_DOCUMENT_PROFILE_RETRY_MAX_TOKENS,
        verify_ssl=LITELLM_VERIFY_TLS,
    )
    return _normalize_profile(document_id, filename, parsed)


def extract_docx_text(local_docx_path: str) -> str:
    """Extract paragraph + table text from a .docx (OOXML) file via python-docx.
    Legacy binary .doc is NOT supported by python-docx and is filtered out before
    discovery (see SUPPORTED_DOC_EXTENSIONS), so this is never called for .doc."""
    from docx import Document as _DocxDocument

    doc = _DocxDocument(local_docx_path)
    parts = [p.text for p in doc.paragraphs if p.text]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text:
                    parts.append(cell.text)
    return "\n".join(parts)


def extract_document_profile(document_id: str, volume_path: str) -> dict:
    # Stage C: LLM-backed profile extraction via the shared doc7 prompt/schema.
    file_name = os.path.basename(str(volume_path))
    file_ext = os.path.splitext(file_name)[1].lower()

    if file_ext == ".docx":
        local_path = to_local_dbfs_path(volume_path)
        full_text = extract_docx_text(local_path)
        profile = run_profile_llm_with_text(document_id, full_text, file_name)
        return {
            "page_count": None,
            "title": profile.get("title") or None,
            "document_summary": profile.get("purpose") or None,
            "ev_osa_parent": detect_ev_osa_parent_from_doc_id(document_id),
            "extraction_confidence": profile.get("source_confidence") or "low",
            "report_issued_date": extract_report_issued_date(full_text),
            "referenced_documents": extract_referenced_documents(full_text),
            "raw_text": full_text,
            "profile": profile,
        }

    if file_ext != ".pdf":
        raise ValueError(f"Unsupported file extension: {file_ext}")

    local_path = to_local_dbfs_path(volume_path)
    with pdfplumber.open(local_path) as pdf:
        page_count = len(pdf.pages)
        # [PAGE N] markers match the build_document_profiles.py offline extractor.
        page_chunks = []
        for idx, page in enumerate(pdf.pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if page_text:
                page_chunks.append(f"[PAGE {idx}]\n{page_text}")
        full_text = "\n\n".join(page_chunks)

    if OSA_PDF_LLM_MODE == "text":
        profile = run_profile_llm_with_text(document_id, full_text, file_name)
    else:
        profile = run_profile_llm_with_pdf(document_id, local_path, file_name)

    return {
        "page_count": page_count,
        "title": profile.get("title") or None,
        "document_summary": profile.get("purpose") or None,
        "ev_osa_parent": detect_ev_osa_parent_from_doc_id(document_id),
        "extraction_confidence": profile.get("source_confidence") or "low",
        "report_issued_date": extract_report_issued_date(full_text),
        "referenced_documents": extract_referenced_documents(full_text),
        "raw_text": full_text,
        "profile": profile,
    }


def enrich_updates_from_osa(updates_df):
    if not OSA_SOURCE_TABLE:
        return updates_df

    try:
        osa_df = spark.table(OSA_SOURCE_TABLE)
    except Exception as e:  # noqa: BLE001
        log.warning(f"OSA enrichment skipped: cannot read table {OSA_SOURCE_TABLE}: {e}")
        return updates_df

    if "ev_osa_parent" not in osa_df.columns or "ev_osa_scope" not in osa_df.columns:
        log.warning(
            "OSA enrichment skipped: table %s missing required columns ev_osa_parent and/or ev_osa_scope",
            OSA_SOURCE_TABLE,
        )
        return updates_df

    osa_fields = [
        "ev_osa_parent",
        "ev_osa_scope",
        "ev_osa_scope_title",
        "ev_osa_item",
        "ev_osa_disposition",
        "ev_osa_status",
        "ev_osa_milestone",
        "ev_milestone",
        "report_issued_date",
        "outage_start_date",
        "outage_end_date",
        "prepared_by",
        "approved_by",
    ]
    available_osa_fields = [c for c in osa_fields if c in osa_df.columns]

    osa_lookup_df = (
        osa_df.withColumn(
            "_osa_parent_token",
            expr("regexp_extract(lower(coalesce(ev_osa_parent, '')), '([a-z0-9]+)\\s*$', 1)"),
        )
        .withColumn(
            "_osa_scope_token",
            expr("regexp_extract(lower(coalesce(ev_osa_scope, '')), '^[a-z0-9]+', 0)"),
        )
        .withColumn("_norm_document_id", concat(col("_osa_parent_token"), col("_osa_scope_token")))
        .filter(col("_norm_document_id") != "")
        .select(
            col("_norm_document_id"),
            *[col(c).alias(f"osa_{c}") for c in available_osa_fields],
        )
        .dropDuplicates(["_norm_document_id"])
    )

    updates_with_key_df = updates_df.withColumn(
        "_norm_document_id",
        expr(
            """
            CASE
                            WHEN regexp_extract(regexp_replace(lower(coalesce(document_id, '')), '[^a-z0-9]', ''), '([a-z]{2,}[0-9][a-z0-9]*)', 1) <> ''
                                THEN regexp_extract(regexp_replace(lower(coalesce(document_id, '')), '[^a-z0-9]', ''), '([a-z]{2,}[0-9][a-z0-9]*)', 1)
                            ELSE regexp_extract(regexp_replace(lower(coalesce(document_id, '')), '[^a-z0-9]', ''), '^([a-z0-9]+)', 1)
            END
            """
        ),
    )

    enriched_df = updates_with_key_df.join(osa_lookup_df, on="_norm_document_id", how="left")

    # Fill missing values from OSA for any overlapping update column.
    protected_fields = {"document_id", "pdf_name", "metadata_status", "metadata_error", "scraped_at"}
    prefer_osa_fields = {
        "ev_osa_parent",
        "ev_osa_scope",
        "ev_osa_scope_title",
        "ev_osa_item",
        "ev_osa_disposition",
        "ev_osa_status",
        "ev_osa_milestone",
        "ev_milestone",
        "report_issued_date",
        "outage_start_date",
        "outage_end_date",
        "prepared_by",
        "approved_by",
    }
    for field_name in updates_df.columns:
        if field_name in protected_fields:
            continue
        osa_col = f"osa_{field_name}"
        if osa_col in enriched_df.columns:
            if field_name in prefer_osa_fields:
                enriched_df = enriched_df.withColumn(field_name, coalesce(col(osa_col), col(field_name)))
            else:
                enriched_df = enriched_df.withColumn(field_name, coalesce(col(field_name), col(osa_col)))

    # If OSA does not provide scope title, fall back to scope text.
    if "ev_osa_scope" in enriched_df.columns and "ev_osa_scope_title" in enriched_df.columns:
        enriched_df = enriched_df.withColumn(
            "ev_osa_scope_title",
            coalesce(col("ev_osa_scope_title"), col("ev_osa_scope")),
        )

    # Drop only temporary OSA join aliases; keep real business columns like osa_doc_json.
    drop_cols = [f"osa_{c}" for c in available_osa_fields if f"osa_{c}" in enriched_df.columns]
    drop_cols.extend(["_norm_document_id"])
    return enriched_df.drop(*drop_cols)


# COMMAND ----------

def process_document_family(family_key: str, metadata_table: str, preview_table_name: str) -> None:
    """Run Stage A (discovery/stub) + Stage B (claim queue) + Stage C (concurrent LLM
    extraction + write) for a single document family, e.g. 'gek' / 'kb' / 'psib' / 'til'.
    Any family with zero matching files in the source volumes is skipped (not fatal)."""

    if not has_family_file(PDF_VOLUME_PATHS, family_key):
        log.info(
            "%s gate: no filenames containing '%s' found in source volumes; skipping family.",
            family_key.upper(),
            family_key.upper(),
        )
        return

    # 1) Discovery + stub registration
    log.info("Stage A: %s-only discovery and metadata stub registration", family_key.upper())
    skip_suffixes_pattern = "|".join(s.replace(".", r"\.") for s in SKIP_SUFFIXES)

    per_vol_dfs = []
    discovered_df = None
    for vol in PDF_VOLUME_PATHS:
        log.info(f"Scanning volume with LIST: {vol}")
        try:
            list_df = normalize_list_df(spark.sql(f"LIST '{vol}'"))
            vol_prefix = vol.rstrip("/")

            skipped_doc_df = (
                list_df.filter(~lower("name").rlike(f"({skip_suffixes_pattern})$"))
                .filter(~lower("name").rlike(r"/$"))
                .filter(lower("name").rlike(r"\.doc$"))
                .filter(_family_name_match(family_key))
            )
            skipped_doc_names = [r["name"] for r in skipped_doc_df.select("name").collect()]
            if skipped_doc_names:
                log.warning(
                    "%s gate: skipping %d legacy .doc file(s) in %s -- no reliable in-cluster "
                    "text extractor for binary Word format, not written to %s: %s",
                    family_key.upper(), len(skipped_doc_names), vol, metadata_table, skipped_doc_names,
                )

            vol_stub_df = (
                list_df.filter(~lower("name").rlike(f"({skip_suffixes_pattern})$"))
                .filter(~lower("name").rlike(r"/$"))
                .filter(lower("name").rlike(rf"\.({SUPPORTED_DOC_EXTENSIONS_REGEX})$"))
                .filter(_family_name_match(family_key))
                .withColumn("_doc_id_raw", lower(regexp_replace("name", rf"(?i)\.({SUPPORTED_DOC_EXTENSIONS_REGEX})$", "")))
                .withColumn(
                    "document_id",
                    expr(
                        """
                        CASE
                                                WHEN regexp_extract(regexp_replace(_doc_id_raw, '[^a-z0-9]', ''), '([a-z]{2,}[0-9][a-z0-9]*)', 1) <> ''
                                                    THEN regexp_extract(regexp_replace(_doc_id_raw, '[^a-z0-9]', ''), '([a-z]{2,}[0-9][a-z0-9]*)', 1)
                                                ELSE regexp_extract(regexp_replace(_doc_id_raw, '[^a-z0-9]', ''), '^([a-z0-9]+)', 1)
                        END
                        """
                    ),
                )
                # ETC's abbreviated filename convention ("e147r3") normalized to the canonical
                # "etc147r3" prefix so it matches the full-name convention ("etc129r2").
                .withColumn("document_id", regexp_replace(col("document_id"), r"^e(\d)", "etc$1"))
                .filter(col("document_id") != "")
                .select(
                    col("document_id"),
                    concat(lit(f"{vol_prefix}/"), col("name")).alias("volume_path"),
                    col("size").cast("long").alias("file_size_bytes"),
                    expr("timestamp_millis(mod_time_ms)").alias("file_last_modified"),
                    lit(MetadataStatus.PENDING).alias("metadata_status"),
                    lit(ChunkStatus.PENDING).alias("chunk_status"),
                )
            )
            per_vol_dfs.append(vol_stub_df)
        except Exception as e:  # noqa: BLE001
            log.warning(f"Cannot list volume {vol}: {e}")

    if per_vol_dfs:
        from functools import reduce
        from pyspark.sql.functions import count, desc, row_number
        from pyspark.sql.window import Window

        discovered_df = reduce(lambda a, b: a.unionByName(b), per_vol_dfs)

        # Deduplicate duplicate document_id across volumes.
        dedupe_w = Window.partitionBy("document_id").orderBy(
            desc("file_last_modified"), desc("file_size_bytes"), col("volume_path")
        )
        dup_w = Window.partitionBy("document_id")

        discovered_df = (
            discovered_df.withColumn("_dup_count", count(lit(1)).over(dup_w))
            .withColumn("_rn", row_number().over(dedupe_w))
            .filter(col("_rn") == 1)
            .drop("_dup_count", "_rn")
        )

        if P1_MAX_PDFS:
            discovered_df = discovered_df.limit(P1_MAX_PDFS)

        if not PRINT_ONLY_MODE:
            discovered_df.createOrReplaceTempView("_fsr_minimal_stubs")

            merge_stubs_sql = f"""
            MERGE INTO {metadata_table} AS tgt
            USING _fsr_minimal_stubs AS src
            ON tgt.document_id = src.document_id
            WHEN MATCHED THEN UPDATE SET
                tgt.volume_path       = src.volume_path,
                tgt.file_last_modified = src.file_last_modified,
                tgt.file_size_bytes    = src.file_size_bytes
            WHEN NOT MATCHED THEN INSERT (
                document_id,
                unique_key,
                pdf_name,
                volume_path,
                file_size_bytes,
                file_last_modified,
                metadata_status,
                chunk_status,
                metadata_retry_count,
                chunk_retry_count,
                ingested_at
            ) VALUES (
                src.document_id,
                src.document_id,
                src.document_id,
                src.volume_path,
                src.file_size_bytes,
                src.file_last_modified,
                src.metadata_status,
                src.chunk_status,
                0,
                0,
                current_timestamp()
            )
            """
            spark.sql(merge_stubs_sql)

    # 2) Claim work queue for minimal metadata extraction
    log.info(
        "Stage B: claim %s-only work queue (incremental skip by existing document_id)",
        family_key.upper(),
    )
    if discovered_df is not None:
        work_rows = discovered_df.select("document_id", "volume_path").collect()
    else:
        work_rows = []

    if P1_MAX_PDFS:
        work_rows = work_rows[:P1_MAX_PDFS]

    existing_doc_ids_for_skip: set[str] = set()
    if not FORCE_REPROCESS and not PRINT_ONLY_MODE and spark.catalog.tableExists(metadata_table):
        try:
            existing_doc_ids_for_skip = {
                _row["document_id"]
                for _row in (
                    spark.table(metadata_table)
                    .select("document_id")
                    .where("document_id IS NOT NULL")
                    .collect()
                )
                if _row["document_id"]
            }
        except Exception as _se:
            log.warning("Could not load existing document IDs for incremental detection: %s", _se)

    if existing_doc_ids_for_skip:
        _before_skip_count = len(work_rows)
        work_rows = [
            _row for _row in work_rows if _row["document_id"] not in existing_doc_ids_for_skip
        ]
        _skipped_count = _before_skip_count - len(work_rows)
        if _skipped_count > 0:
            log.info("Incremental skip (existing document_id match): skipped %d docs", _skipped_count)

    log.info(f"Work queue size: {len(work_rows)}")

    # 3) Extract + write status updates
    log.info("Stage C: LLM-backed profile extraction + status merge (max_workers=%s)", MAX_WORKERS)
    update_schema = StructType(
        [
            StructField("document_id", StringType(), False),
            StructField("pdf_name", StringType(), True),
            StructField("volume_path", StringType(), True),
            StructField("title", StringType(), True),
            StructField("fsr_number", StringType(), True),
            StructField("document_summary", StringType(), True),
            StructField("report_issued_date", StringType(), True),
            StructField("outage_start_date", StringType(), True),
            StructField("outage_end_date", StringType(), True),
            StructField("prepared_by", StringType(), True),
            StructField("approved_by", StringType(), True),
            StructField("esn_source", StringType(), True),
            StructField("xxx_project_id", StringType(), True),
            StructField("ev_osa_parent", StringType(), True),
            StructField("ev_osa_scope", StringType(), True),
            StructField("ev_osa_scope_title", StringType(), True),
            StructField("ev_osa_item", StringType(), True),
            StructField("ev_osa_disposition", StringType(), True),
            StructField("ev_osa_status", StringType(), True),
            StructField("ev_osa_milestone", StringType(), True),
            StructField("ev_milestone", StringType(), True),
            StructField("extraction_confidence", StringType(), True),
            StructField("raw_text", StringType(), True),
            StructField(OSA_DOC_JSON_COLUMN, StringType(), True),
            StructField("page_count", IntegerType(), True),
            StructField("metadata_status", StringType(), False),
            StructField("metadata_error", StringType(), True),
            StructField("scraped_at", TimestampType(), True),
        ]
    )

    now_utc = datetime.now(timezone.utc)

    def _extract_one(row) -> dict:
        """Extract a single document's profile. Runs on a worker thread; every
        exception is caught here so one bad document can never abort the batch."""
        document_id = row["document_id"]
        volume_path = row["volume_path"]

        try:
            info = extract_document_profile(document_id, volume_path)
            return {
                "document_id": document_id,
                "pdf_name": document_id,
                "volume_path": volume_path,
                "title": info["title"],
                # Not part of the doc7 profile schema; left for OSA-table enrichment / manual backfill.
                "fsr_number": None,
                "document_summary": info["document_summary"],
                "report_issued_date": info.get("report_issued_date"),
                "outage_start_date": None,
                "outage_end_date": None,
                "prepared_by": None,
                "approved_by": None,
                "esn_source": EXTRACTION_METHOD,
                "xxx_project_id": info.get("referenced_documents"),
                "ev_osa_parent": info["ev_osa_parent"],
                "ev_osa_scope": None,
                "ev_osa_scope_title": info["title"],
                "ev_osa_item": info["document_summary"],
                "ev_osa_disposition": None,
                "ev_osa_status": "NOT_STARTED",
                "ev_osa_milestone": None,
                "ev_milestone": None,
                "extraction_confidence": info["extraction_confidence"],
                "raw_text": info.get("raw_text"),
                OSA_DOC_JSON_COLUMN: json.dumps(info["profile"], ensure_ascii=False),
                "page_count": info["page_count"],
                "metadata_status": MetadataStatus.COMPLETED,
                "metadata_error": None,
                "scraped_at": now_utc,
            }
        except Exception as e:  # noqa: BLE001
            error_profile = {
                "doc_id": document_id,
                "filename": os.path.basename(str(volume_path)),
                "title": "",
                "original_language": "",
                "purpose": "",
                "purpose_snippets": [],
                "units_of_work": [],
                "source_confidence": "",
                "error": str(e)[:500],
            }
            return {
                "document_id": document_id,
                "pdf_name": document_id,
                "volume_path": volume_path,
                "title": None,
                "fsr_number": None,
                "document_summary": None,
                "report_issued_date": None,
                "outage_start_date": None,
                "outage_end_date": None,
                "prepared_by": None,
                "approved_by": None,
                "esn_source": EXTRACTION_METHOD,
                "xxx_project_id": None,
                "ev_osa_parent": detect_ev_osa_parent_from_doc_id(document_id),
                "ev_osa_scope": None,
                "ev_osa_scope_title": None,
                "ev_osa_item": None,
                "ev_osa_disposition": None,
                "ev_osa_status": None,
                "ev_osa_milestone": None,
                "ev_milestone": None,
                "extraction_confidence": "low",
                "raw_text": None,
                OSA_DOC_JSON_COLUMN: json.dumps(error_profile, ensure_ascii=False),
                "page_count": None,
                "metadata_status": MetadataStatus.FAILED,
                "metadata_error": str(e)[:8000],
                "scraped_at": now_utc,
            }

    updates = []
    if work_rows:
        # I/O-bound work (blocking HTTP calls to the LiteLLM gateway per document), so
        # threads give real wall-clock speedup despite the GIL. Only the main thread
        # appends to `updates`, so no additional locking is required around the list.
        worker_count = min(MAX_WORKERS, len(work_rows))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(_extract_one, row) for row in work_rows]
            for future in as_completed(futures):
                updates.append(future.result())

    if updates:
        updates_df = spark.createDataFrame(updates, schema=update_schema)
        updates_df = enrich_updates_from_osa(updates_df)
        if DEBUG_DOC_ID:
            try:
                debug_pre_df = updates_df.filter(lower(col("document_id")) == lit(DEBUG_DOC_ID)).select(
                    "document_id",
                    "ev_osa_parent",
                    "ev_osa_scope",
                    "ev_osa_scope_title",
                    "ev_osa_item",
                    "ev_osa_status",
                )
                log.info("Debug pre-merge row for %s", DEBUG_DOC_ID)
                debug_pre_df.show(20, truncate=False)
            except Exception as e:  # noqa: BLE001
                log.warning(f"Failed to print debug pre-merge row: {e}")
        stubs_preview_df = discovered_df.select(
            "document_id",
            "volume_path",
            "file_size_bytes",
            "file_last_modified",
            "metadata_status",
            "chunk_status",
        )

        merged_preview_df = (
            stubs_preview_df.alias("t")
            .join(updates_df.alias("s"), on="document_id", how="left")
            .select(
                col("document_id"),
                coalesce(col("s.pdf_name"), col("document_id")).alias("pdf_name"),
                coalesce(col("s.volume_path"), col("t.volume_path")).alias("volume_path"),
                col("file_size_bytes"),
                col("file_last_modified"),
                col("s.title").alias("title"),
                col("s.fsr_number").alias("fsr_number"),
                col("s.document_summary").alias("document_summary"),
                col("s.report_issued_date").alias("report_issued_date"),
                col("s.outage_start_date").alias("outage_start_date"),
                col("s.outage_end_date").alias("outage_end_date"),
                col("s.prepared_by").alias("prepared_by"),
                col("s.approved_by").alias("approved_by"),
                col("s.esn_source").alias("esn_source"),
                col("s.xxx_project_id").alias("xxx_project_id"),
                col("s.ev_osa_parent").alias("ev_osa_parent"),
                col("s.ev_osa_scope").alias("ev_osa_scope"),
                col("s.ev_osa_scope_title").alias("ev_osa_scope_title"),
                col("s.ev_osa_item").alias("ev_osa_item"),
                col("s.ev_osa_disposition").alias("ev_osa_disposition"),
                col("s.ev_osa_status").alias("ev_osa_status"),
                col("s.ev_osa_milestone").alias("ev_osa_milestone"),
                col("s.ev_milestone").alias("ev_milestone"),
                col("s.extraction_confidence").alias("extraction_confidence"),
                col("s.raw_text").alias("raw_text"),
                col(f"s.{OSA_DOC_JSON_COLUMN}").alias(OSA_DOC_JSON_COLUMN),
                col("s.page_count").alias("page_count"),
                coalesce(col("s.metadata_status"), col("t.metadata_status")).alias("metadata_status"),
                col("s.metadata_error").alias("metadata_error"),
                col("s.scraped_at").alias("scraped_at"),
                col("chunk_status"),
            )
        )

        merged_preview_df.createOrReplaceTempView("_fsr_minimal_merge_preview")
        # Step-7-style bridge view for OSA candidate downstream stages.
        step7_candidate_preview_df = merged_preview_df.select(
            col("document_id").alias("source_document_id"),
            col("volume_path").alias("source_volume_path"),
            col("xxx_project_id").alias("referenced_documents"),
            col("ev_osa_parent"),
            col("ev_osa_scope"),
            col("ev_osa_scope_title"),
            col("ev_osa_item"),
            col("ev_osa_disposition"),
            col("ev_osa_status"),
            col("ev_osa_milestone"),
            col("ev_milestone"),
            col("prepared_by"),
            col("approved_by"),
            col("report_issued_date"),
            col("outage_start_date"),
            col("outage_end_date"),
            col("extraction_confidence"),
            lit(EXTRACTION_METHOD).alias("extraction_method"),
            col("metadata_status"),
            col("metadata_error"),
            col("scraped_at"),
        )
        step7_candidate_preview_df.createOrReplaceTempView("_step7_osa_candidate_preview")
        log.info("Preview temp view created: _fsr_minimal_merge_preview")
        log.info("Step-7 bridge view created: _step7_osa_candidate_preview")

        if PRINT_ONLY_MODE:
            log.info("PRINT_ONLY_MODE enabled: building merge-style preview table (no writes).")
            if WRITE_PREVIEW_TABLE and preview_table_name:
                merged_preview_df.write.mode("overwrite").format("delta").saveAsTable(preview_table_name)
                log.info(f"Preview table written: {preview_table_name}")
                preview_out_df = spark.table(preview_table_name).orderBy("document_id")
            else:
                preview_out_df = spark.sql("SELECT * FROM _fsr_minimal_merge_preview ORDER BY document_id")

            try:
                if "display" in globals():
                    globals()["display"](preview_out_df)
                else:
                    preview_out_df.show(200, truncate=False)
            except Exception:
                preview_out_df.show(200, truncate=False)
        else:
            # Build the merge source from the exact preview output to keep parity.
            write_df = (
                merged_preview_df
                .withColumn("unique_key", col("document_id"))
                .withColumn("event_type", col("ev_osa_parent"))
                .withColumn(
                    "metadata_retry_count",
                    expr(f"CASE WHEN metadata_status = '{MetadataStatus.FAILED}' THEN 1 ELSE 0 END"),
                )
                .withColumn("chunk_retry_count", lit(0))
                .withColumn("ingested_at", coalesce(col("scraped_at"), expr("current_timestamp()")))
            )

            # Real MERGE INTO keyed on document_id: only touches rows this run actually
            # discovered/processed, so a transient volume-LIST failure or a debug
            # FSR_MAX_PDFS cap can never silently wipe out unrelated existing rows
            # the way a full-table mode("overwrite") would.
            write_df.createOrReplaceTempView("_fsr_minimal_write_src")
            merge_cols = list(REQUIRED_METADATA_COLUMNS.keys())
            update_set_sql = ",\n                    ".join(
                f"tgt.{c} = src.{c}" for c in merge_cols if c != "document_id"
            )
            insert_cols_sql = ", ".join(merge_cols)
            insert_vals_sql = ", ".join(f"src.{c}" for c in merge_cols)
            spark.sql(
                f"""
                MERGE INTO {metadata_table} AS tgt
                USING _fsr_minimal_write_src AS src
                ON tgt.document_id = src.document_id
                WHEN MATCHED THEN UPDATE SET
                    {update_set_sql}
                WHEN NOT MATCHED THEN INSERT (
                    {insert_cols_sql}
                ) VALUES (
                    {insert_vals_sql}
                )
                """
            )

            written_docs_df = (
                spark.table(metadata_table)
                .join(write_df.select("document_id").distinct(), on="document_id", how="inner")
                .orderBy("document_id")
            )
            log.info("Write-mode output (rows this run merged into the target table):")
            try:
                if "display" in globals():
                    globals()["display"](written_docs_df)
                else:
                    written_docs_df.show(200, truncate=False)
            except Exception:
                written_docs_df.show(200, truncate=False)

            if DEBUG_DOC_ID:
                try:
                    debug_post_df = spark.sql(
                        f"""
                        SELECT
                          document_id,
                          ev_osa_parent,
                          event_type,
                          ev_osa_scope,
                          ev_osa_scope_title,
                          ev_osa_item,
                          ev_osa_status,
                          metadata_status,
                          metadata_error
                        FROM {metadata_table}
                        WHERE lower(document_id) = '{DEBUG_DOC_ID}'
                        """
                    )
                    log.info("Debug post-write row for %s", DEBUG_DOC_ID)
                    debug_post_df.show(20, truncate=False)
                except Exception as e:  # noqa: BLE001
                    log.warning(f"Failed to print debug post-write row: {e}")

    if not PRINT_ONLY_MODE:
        result = spark.sql(
            f"""
            SELECT
              metadata_status,
              COUNT(*) AS n
            FROM {metadata_table}
            GROUP BY metadata_status
            ORDER BY metadata_status
            """
        )

        log.info("Current metadata status distribution for %s:", family_key.upper())
        result.show(truncate=False)
    else:
        log.info("PRINT_ONLY_MODE complete for %s: extracted metadata shown above.", family_key.upper())


# COMMAND ----------

for _family_key in DOCUMENT_FAMILY_KEYS:
    _metadata_table = resolve_metadata_table_for_family(_family_key)
    _preview_table_name = resolve_preview_table_for_family(_family_key)
    log.info("=" * 78)
    log.info("Processing family=%s  metadata_table=%s", _family_key.upper(), _metadata_table)
    if not PRINT_ONLY_MODE:
        ensure_metadata_table_ready(_metadata_table)
    process_document_family(_family_key, _metadata_table, _preview_table_name)

log.info("Process 1A complete (families processed: %s)", DOCUMENT_FAMILY_KEYS)
