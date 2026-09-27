# Databricks notebook source
# COMMAND ----------
%restart_python


# COMMAND ----------

import json
import logging
import random
import re
import time
import requests
import warnings
import urllib3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from IPython.display import display
from concurrent.futures import ThreadPoolExecutor, as_completed
from pyspark.sql.types import IntegerType, LongType, StringType, StructField, StructType, TimestampType
from typing import Any

from common.parsers.databricks_ai_parser import DatabricksAIParser
from contracts.types.entities import DocumentReference
from contracts.schemas.tils.til_profile_schema import normalize_til_profile
from silver.src.tils.til_profile_extraction_llm import SYSTEM_PROMPT, build_user_prompt

# Metadata-style widgets for runtime config parity.
# Updated widgets post PR
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
    try:
        _litellm_verify_tls_current = (dbutils.widgets.get("LITELLM_VERIFY_TLS") or "").strip()
    except Exception:
        _litellm_verify_tls_current = ""
    dbutils.widgets.text(
        "LITELLM_VERIFY_TLS",
        _litellm_verify_tls_current or "true",
        "Verify LiteLLM gateway TLS certificates (true/false). Set false only for dev cert-chain issues.",
    )
    dbutils.widgets.text(
        "PARSER_HOST",
        "qa-foundation.apps.gevernova.net",
        "Foundation-parser hostname (set to prd-foundation.apps.gevernova.net in prod)",
    )
    dbutils.widgets.text(
        "TIL_SOURCE_VOLUME_PATHS",
        "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new",
        "Comma-separated source /Volumes paths for TIL files",
    )
    dbutils.widgets.text(
        "TIL_PROFILE_OUTPUT_TABLE",
        "vaid.ai_sot_field_service_report.til_profile_osa_pipeline_aditi_tmp",
        "Delta table for TIL profile extraction output",
    )
    dbutils.widgets.text(
        "TIL_PROFILE_RUN_AUDIT_TABLE",
        "vaid.ai_sot_field_service_report.til_profile_run_audit",
        "Delta table for profile pipeline run history",
    )
    try:
        _parser_verify_tls_current = (dbutils.widgets.get("PARSER_VERIFY_TLS") or "").strip()
    except Exception:
        _parser_verify_tls_current = ""
    dbutils.widgets.text(
        "PARSER_VERIFY_TLS",
        _parser_verify_tls_current or "true",
        "Verify parser TLS certificates (true/false). Set false only for dev cert-chain issues.",
    )
    try:
        _parser_allow_insecure_tls_current = (dbutils.widgets.get("PARSER_ALLOW_INSECURE_TLS") or "").strip()
    except Exception:
        _parser_allow_insecure_tls_current = ""
    dbutils.widgets.text(
        "PARSER_ALLOW_INSECURE_TLS",
        _parser_allow_insecure_tls_current or "false",
        "Allow insecure TLS cert validation bypass for parser calls in dev only (true/false)",
    )
except Exception:
    pass

from common.tils.til_config import (
    TIL_LLM_MAX_TOKENS,
    TIL_LLM_MODEL,
    TIL_LLM_TEMPERATURE,
)
from common.tils.til_llm_client import extract_til_profile_via_llm

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("til.profile.batch")

# Security: Allow insecure TLS only in dev (corp proxy/Zscaler interception).
# Defaults to False in prod to prevent accidental certificate bypass.
# Gate behind this flag to avoid process-wide warning suppression.
try:
    _insecure_tls_raw = (dbutils.widgets.get("PARSER_ALLOW_INSECURE_TLS") or "").strip().lower()
    ALLOW_INSECURE_TLS = _insecure_tls_raw in {"1", "true", "t", "yes", "y", "on"}
except Exception:
    ALLOW_INSECURE_TLS = False

try:
    _verify_tls_raw = (dbutils.widgets.get("PARSER_VERIFY_TLS") or "").strip().lower()
    VERIFY_TLS = _verify_tls_raw not in {"0", "false", "f", "no", "n", "off"}
except Exception:
    VERIFY_TLS = not ALLOW_INSECURE_TLS

try:
    _litellm_verify_tls_raw = (dbutils.widgets.get("LITELLM_VERIFY_TLS") or "").strip().lower()
    LITELLM_VERIFY_TLS = _litellm_verify_tls_raw not in {"0", "false", "f", "no", "n", "off"}
except Exception:
    LITELLM_VERIFY_TLS = True


def _get_litellm_verify_setting() -> bool:
    """Resolve LiteLLM TLS verification from widget at call time."""
    try:
        raw_value = (dbutils.widgets.get("LITELLM_VERIFY_TLS") or "").strip().lower()
        return raw_value not in {"0", "false", "f", "no", "n", "off"}
    except Exception:
        return LITELLM_VERIFY_TLS


def _is_insecure_tls_enabled() -> bool:
    """Read TLS bypass intent from widget when available, else fallback to startup value."""
    try:
        verify_raw = (dbutils.widgets.get("PARSER_VERIFY_TLS") or "").strip().lower()
        verify_tls = verify_raw not in {"0", "false", "f", "no", "n", "off"}
        return not verify_tls
    except Exception:
        pass

    try:
        raw_value = (dbutils.widgets.get("PARSER_ALLOW_INSECURE_TLS") or "").strip().lower()
        return raw_value in {"1", "true", "t", "yes", "y", "on"}
    except Exception:
        return not VERIFY_TLS

# Parser service configuration — host resolved from widget/job-param so prod deployments
# can target prd-foundation.apps.gevernova.net without a code change.
try:
    HOST = (dbutils.widgets.get("PARSER_HOST") or "").strip() or "qa-foundation.apps.gevernova.net"
except Exception:
    HOST = "qa-foundation.apps.gevernova.net"
PARSER_ASYNC_SUBMIT_URL = f"https://{HOST}/v2/parser/async/parse"
PARSER_ASYNC_STATUS_URL_TMPL = f"https://{HOST}/v2/parser/async/status/{{operation_id}}"
PARSER_ASYNC_RESULT_URL_TMPL = f"https://{HOST}/v2/parser/async/result/{{operation_id}}"
HEADERS = {
    "Host": HOST,
    "environment": "development",
    "project-id": "000d72e9-8035-57bd-92aa-47c5e0fcbe6c",
}
REQUEST_TIMEOUT_S = 60
PARSER_ASYNC_POLL_INTERVAL_S = 2.0
PARSER_ASYNC_MAX_WAIT_S = 600.0
PARSER_ASYNC_HEARTBEAT_POLLS = 30
PARSER_ASYNC_RESULT_PROBE_POLLS = 60
PARSER_HTTP_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}
PARSER_HTTP_MAX_RETRIES = 5
PARSER_HTTP_BACKOFF_BASE_S = 2.0
PARSER_HTTP_BACKOFF_MAX_S = 30.0
PARSER_HTTP_BACKOFF_JITTER_S = 0.5
PARSER_ASYNC_SUBMIT_MAX_IN_FLIGHT = 1
LLM_MODEL = TIL_LLM_MODEL
LLM_TEMPERATURE = TIL_LLM_TEMPERATURE

LLM_MAX_TOKENS = TIL_LLM_MAX_TOKENS
VERBOSE_PROGRESS_LOGS = False
LIVE_PROGRESS_LOGS = True
PARSER_ASYNC_LIVE_HEARTBEAT_POLLS = 150

PARSER_ASYNC_SUBMIT_SEMAPHORE = threading.Semaphore(PARSER_ASYNC_SUBMIT_MAX_IN_FLIGHT)


def _get_verify_setting() -> bool:
    """
    Determine SSL/TLS certificate verification setting.
    Returns False only when explicitly allowed (corp TLS interception in dev).
    Scoped helper to avoid process-wide warning suppression.
    """
    verify_tls = True

    # Preferred control: direct verify flag.
    try:
        verify_raw = (dbutils.widgets.get("PARSER_VERIFY_TLS") or "").strip().lower()
        verify_tls = verify_raw not in {"0", "false", "f", "no", "n", "off"}
    except Exception:
        # Backward-compatible fallback.
        try:
            insecure_raw = (dbutils.widgets.get("PARSER_ALLOW_INSECURE_TLS") or "").strip().lower()
            allow_insecure_tls = insecure_raw in {"1", "true", "t", "yes", "y", "on"}
            verify_tls = not allow_insecure_tls
        except Exception:
            verify_tls = True

    if not verify_tls:
        # Suppress warnings only for this specific request, not globally.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)
    return verify_tls


def _vlog(message: str, *args: Any) -> None:
    if VERBOSE_PROGRESS_LOGS:
        log.info(message, *args)


def _plog(message: str, *args: Any) -> None:
    if LIVE_PROGRESS_LOGS:
        print(message % args if args else message)


# Pipeline configuration
try:
    _source_volume_paths = (dbutils.widgets.get("TIL_SOURCE_VOLUME_PATHS") or "").strip()
except Exception:
    _source_volume_paths = ""
SOURCE_VOLUMES = [
    path.strip() for path in _source_volume_paths.split(",") if path.strip()
] or [
    "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new",
]
SOURCE_FILE_EXTENSIONS = (".pdf", ".docx", ".doc")
# Batch processing controls (mirror the chunk notebook pattern).
USE_BATCH_PROCESSING = True
TIL_BATCH_SIZE = 10
TIL_PROFILE_CONCURRENCY = 4
# Optional: set to one PDF path for a quick single-file test.
# Leave as None to process all PDFs discovered in SOURCE_VOLUMES.
TEST_SINGLE_PDF_PATH = None
# Optional: process only first N discovered files for quick folder testing.
# Leave as None to process all discovered files.
TEST_FILE_LIMIT = None
try:
    OUTPUT_TABLE = (dbutils.widgets.get("TIL_PROFILE_OUTPUT_TABLE") or "").strip()
except Exception:
    OUTPUT_TABLE = ""
OUTPUT_TABLE = OUTPUT_TABLE or "vaid.ai_sot_field_service_report.til_profile_osa_pipeline_aditi_tmp"
try:
    PROFILE_RUN_AUDIT_TABLE = (dbutils.widgets.get("TIL_PROFILE_RUN_AUDIT_TABLE") or "").strip()
except Exception:
    PROFILE_RUN_AUDIT_TABLE = ""
PROFILE_RUN_AUDIT_TABLE = PROFILE_RUN_AUDIT_TABLE or "vaid.ai_sot_field_service_report.til_profile_run_audit"
WRITE_OUTPUT_TABLE = True
# Daily ingestion should append only unseen docs by default.
SKIP_ALREADY_INGESTED = True
SKIP_ALREADY_INGESTED_BY_NAME = True
# Keep history for daily runs; only reset when explicitly requested.
RESET_OUTPUT_TABLE = False
INCREMENTAL_WRITE_FLUSH_SIZE = 1

PROFILE_RUN_ID = f"til_profile_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
PROFILE_RUN_STARTED_AT = datetime.now(timezone.utc)

def _ensure_profile_run_audit_table() -> None:
    if not WRITE_OUTPUT_TABLE or not PROFILE_RUN_AUDIT_TABLE:
        return
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {PROFILE_RUN_AUDIT_TABLE} (
            run_id STRING NOT NULL,
            output_table STRING NOT NULL,
            delta_version BIGINT,
            run_started_at TIMESTAMP NOT NULL,
            run_completed_at TIMESTAMP,
            status STRING NOT NULL,
            discovered_count INT,
            success_count INT,
            failed_count INT,
            skipped_count INT,
            error_message STRING
        )
        USING DELTA
        COMMENT 'Profile pipeline runs and output Delta versions'
    """)

def _write_profile_run_audit(
    status: str,
    discovered_count: int,
    success_count: int,
    failed_count: int,
    skipped_count: int,
    error_message: str | None = None,
) -> None:
    if not WRITE_OUTPUT_TABLE or not PROFILE_RUN_AUDIT_TABLE:
        return
    try:
        history = spark.sql(f"DESCRIBE HISTORY {OUTPUT_TABLE}")
        matching_commit = (
            history.where(history.userMetadata == PROFILE_RUN_ID)
            .select("version")
            .orderBy("version", ascending=False)
            .first()
        )
        delta_version = matching_commit["version"] if matching_commit else None
    except Exception as exc:
        log.warning("Could not resolve Delta version for run %s: %s", PROFILE_RUN_ID, exc)
        delta_version = None

    audit_schema = StructType([
        StructField("run_id", StringType(), False),
        StructField("output_table", StringType(), False),
        StructField("delta_version", LongType(), True),
        StructField("run_started_at", TimestampType(), False),
        StructField("run_completed_at", TimestampType(), True),
        StructField("status", StringType(), False),
        StructField("discovered_count", IntegerType(), True),
        StructField("success_count", IntegerType(), True),
        StructField("failed_count", IntegerType(), True),
        StructField("skipped_count", IntegerType(), True),
        StructField("error_message", StringType(), True),
    ])
    audit_row = [(
        PROFILE_RUN_ID,
        OUTPUT_TABLE,
        int(delta_version) if delta_version is not None else None,
        PROFILE_RUN_STARTED_AT,
        datetime.now(timezone.utc),
        status,
        discovered_count,
        success_count,
        failed_count,
        skipped_count,
        error_message,
    )]
    try:
        (
            spark.createDataFrame(audit_row, schema=audit_schema)
            .write.format("delta")
            .mode("append")
            .saveAsTable(PROFILE_RUN_AUDIT_TABLE)
        )
    except Exception as exc:
        log.warning("Could not write profile run audit for %s: %s", PROFILE_RUN_ID, exc)

def _write_profile_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    (
        spark.createDataFrame(rows, schema=output_schema)
        .write.format("delta")
        .option("userMetadata", PROFILE_RUN_ID)
        .mode("append")
        .saveAsTable(OUTPUT_TABLE)
    )

# Metadata-style optional override: blank means gateway default max tokens.
try:
    _llm_max_tokens_override = (dbutils.widgets.get("TIL_LLM_MAX_TOKENS") or "").strip()
    if _llm_max_tokens_override:
        try:
            LLM_MAX_TOKENS = int(_llm_max_tokens_override)
            if LLM_MAX_TOKENS <= 0:
                raise ValueError("must be > 0")
        except Exception as exc:
            raise ValueError(
                f"Invalid TIL_LLM_MAX_TOKENS value '{_llm_max_tokens_override}'. Provide a positive integer."
            ) from exc
    else:
        LLM_MAX_TOKENS = None
except Exception:
    # In non-widget contexts, keep shared-config default.
    pass

# Use Databricks structured parser only for parsed_profile_json path.
TIL_PARSER = DatabricksAIParser()


# COMMAND ----------

log.info("=== TIL Profile Batch Ingestion ===")
log.info(f"  Parser host    : {HOST}")
log.info(f"  LiteLLM model  : {LLM_MODEL}")
log.info(f"  Output table   : {OUTPUT_TABLE}")
log.info(f"  Skip ingested  : {SKIP_ALREADY_INGESTED}")
log.info(f"  Insecure TLS   : {ALLOW_INSECURE_TLS}")
log.info(f"  Source volumes : {SOURCE_VOLUMES}")


# COMMAND ----------

def clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def canonicalize_til_number(value: object) -> str:
    text = clean_text(value).upper()
    if not text:
        return ""

    # "T" glued directly to digits (e.g. "T11073") has no word boundary to anchor
    # "TIL\s*" against, so match it via lookahead instead.
    match = re.search(
        r"\b(?:TIL\s*|T(?=[0-9]))([0-9]+(?:\s*-\s*[0-9]+)?(?:\s*-\s*(?:R\s*)?[0-9]+|\s*R\s*[0-9]+)?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return re.sub(r"\s+", "", match.group(1)).upper()

    return re.sub(r"\s+", "", text.removeprefix("TIL")).strip()


def _reconcile_til_number(llm_raw: object, filename_raw: object) -> str:
    """Prefer the LLM value; fall back to the filename value only when the LLM
    dropped a hyphen the filename preserved (legacy "T<base>-<rev>" identifiers
    are sometimes transcribed by the LLM without the hyphen, e.g. "T1107-3" ->
    "T11073"). Filenames with an invalid suffix (e.g. "1287-7FA", a frame code,
    not a revision) never produce a hyphen here, so they naturally fall through
    to the LLM value.
    """
    llm_canonical = canonicalize_til_number(llm_raw)
    filename_canonical = canonicalize_til_number(filename_raw)

    if "-" not in llm_canonical and "-" in filename_canonical:
        return filename_canonical
    return llm_canonical or filename_canonical


def normalize_til_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", canonicalize_til_number(value))


def extract_base_til_num(value: str) -> str:
    til = clean_text(value).upper()
    match = re.search(r"(\d+)(?:-[0-9]+)?R\d+", til)
    if match:
        return match.group(1)
    fallback = re.search(r"(\d+)", til)
    return fallback.group(1) if fallback else ""


def extract_til_revision_number(value: str) -> str:
    til = clean_text(value).upper()
    parts = til.split("-", 1)
    return parts[1].strip() if len(parts) == 2 and parts[1].strip() else ""


def parse_revision_number(value: str) -> int:
    til = clean_text(value).upper()
    match = re.search(r"R(\d+)", til)
    return int(match.group(1)) if match else -1


def _extract_til_number(pdf_path: str) -> str:
    filename = Path(pdf_path).name
    # Return only canonical TIL id token (base with optional dash and optional revision),
    # never the trailing title text.
    # Examples:
    # - "TIL 1046-2 - ..." -> "1046-2"
    # - "TIL 1234-1R1 - ..." -> "1234-1R1"
    # - "t1345r4.pdf" -> "1345R4" (bare "T" glued to digits, no word boundary between them)
    match = re.search(
        r"\b(?:TIL\s*|T(?=[0-9]))?([0-9]+(?:\s*-\s*[0-9]+)?(?:\s*-\s*(?:R\s*)?[0-9]+|\s*R\s*[0-9]+)?)\b",
        filename,
        flags=re.IGNORECASE,
    )
    if match:
        token = re.sub(r"\s+", "", match.group(1)).upper()
        return token

    stem = Path(pdf_path).stem
    stem_match = re.search(
        r"\b(?:T(?=[0-9]))?([0-9]+(?:\s*-\s*[0-9]+)?(?:\s*-\s*(?:R\s*)?[0-9]+|\s*R\s*[0-9]+)?)\b",
        stem,
        flags=re.IGNORECASE,
    )
    if stem_match:
        return re.sub(r"\s+", "", stem_match.group(1)).upper()

    return stem


def _guess_mime_type(file_path: str) -> str:
    suffix = Path(file_path).suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix == ".doc":
        return "application/msword"
    return "application/octet-stream"


def call_llm_for_profile_extraction(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any] | None, str | None, float]:
    """Call shared LiteLLM client and return parsed profile, raw response, latency."""
    verify_ssl = _get_litellm_verify_setting()
    return extract_til_profile_via_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        verify_ssl=verify_ssl,
    )


_PART_NUMBER_TOKEN_RE = re.compile(r"\b[A-Z0-9][A-Z0-9./-]{3,}\b")
_PART_NUMBER_RANGE_RE = re.compile(r"\b(through|thru|from|to)\b", re.IGNORECASE)


def _best_part_number_token(text: str) -> str:
    candidates = _PART_NUMBER_TOKEN_RE.findall((text or "").upper())
    for token in candidates:
        if any(ch.isdigit() for ch in token):
            return token
    return ""


def _normalize_part_number_and_context(part_number: Any, context: Any) -> tuple[Any, str]:
    part_text = clean_text(part_number)
    context_text = clean_text(context)
    if not part_text:
        return (None, context_text)

    normalized_space = re.sub(r"\s+", " ", part_text).strip()
    contains_range_word = bool(_PART_NUMBER_RANGE_RE.search(normalized_space))
    contains_multi_token = " " in normalized_space

    best_token = _best_part_number_token(normalized_space)
    if not best_token:
        if normalized_space and normalized_space not in context_text:
            context_text = f"{context_text} | part_number_raw: {normalized_space}".strip(" |")
        return (None, context_text)

    if (contains_range_word or contains_multi_token) and normalized_space not in context_text:
        context_text = f"{context_text} | part_number_raw: {normalized_space}".strip(" |")

    return (best_token, context_text)


def _normalize_source_location(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""

    collapsed = re.sub(r"\s+", " ", text)
    page_match = re.search(r"\b(?:page|pg|p)\.?\s*[:#-]?\s*(\d+)\b", collapsed, re.IGNORECASE)
    table_match = re.search(r"\btable\s*[:#-]?\s*([A-Za-z0-9._-]+)\b", collapsed, re.IGNORECASE)

    page = page_match.group(1) if page_match else ""
    table = table_match.group(1) if table_match else ""
    if page and table:
        return f"Page {page}, Table {table}"
    if page:
        return f"Page {page}, Body text"
    if table:
        return f"Table {table}"
    return collapsed


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = clean_text(value).lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return None


def _normalize_service_line_item_annotations(profile: dict[str, Any]) -> list[dict[str, Any]]:
    line_items = [clean_text(item) for item in (profile.get("service_recommendation_line_items") or []) if clean_text(item)]
    raw_annotations = profile.get("service_line_item_annotations") or []
    if not isinstance(raw_annotations, list):
        raw_annotations = [raw_annotations]

    by_exact_text: dict[str, dict[str, Any]] = {}
    positional_annotations: list[dict[str, Any]] = []
    for item in raw_annotations:
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        positional_annotations.append(normalized_item)
        line_text = clean_text(normalized_item.get("line_item_text"))
        if line_text and line_text not in by_exact_text:
            by_exact_text[line_text] = normalized_item

    if line_items:
        normalized_annotations: list[dict[str, Any]] = []
        for idx, line_text in enumerate(line_items, start=1):
            matched = by_exact_text.get(line_text)
            if matched is None and idx - 1 < len(positional_annotations):
                matched = positional_annotations[idx - 1]
            matched = matched or {}

            normalized_annotations.append(
                {
                    "line_item_id": clean_text(matched.get("line_item_id")) or f"item_{idx}",
                    "line_item_text": line_text,
                    "execution_classification": clean_text(matched.get("execution_classification")) or None,
                    "activity_grouping": clean_text(matched.get("activity_grouping")) or None,
                    "system_or_component": clean_text(matched.get("system_or_component")) or None,
                    "classification_rationale": clean_text(matched.get("classification_rationale")) or None,
                }
            )
        return normalized_annotations

    normalized_annotations = []
    for idx, item in enumerate(positional_annotations, start=1):
        normalized_annotations.append(
            {
                "line_item_id": clean_text(item.get("line_item_id")) or f"item_{idx}",
                "line_item_text": clean_text(item.get("line_item_text")),
                "execution_classification": clean_text(item.get("execution_classification")) or None,
                "activity_grouping": clean_text(item.get("activity_grouping")) or None,
                "system_or_component": clean_text(item.get("system_or_component")) or None,
                "classification_rationale": clean_text(item.get("classification_rationale")) or None,
            }
        )
    return normalized_annotations


def _derive_information_only_flag(profile: dict[str, Any]) -> bool | None:
    annotations = profile.get("service_line_item_annotations") or []
    saw_classification = False
    for item in annotations:
        if not isinstance(item, dict):
            continue
        classification = clean_text(item.get("execution_classification")).lower()
        if not classification:
            continue
        saw_classification = True
        if classification == "execution_focused":
            return False

    if saw_classification:
        return True

    return _coerce_bool(profile.get("information_only_flag"))


def _finalize_profile_for_output(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if profile is None or not isinstance(profile, dict):
        return profile

    finalized = dict(profile)
    finalized["service_line_item_annotations"] = _normalize_service_line_item_annotations(finalized)
    finalized["information_only_flag"] = _derive_information_only_flag(finalized)
    return finalized


def canonicalize_profile_for_contract(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Apply light shape canonicalization before strict schema normalization."""
    if profile is None or not isinstance(profile, dict):
        return None

    if isinstance(profile.get("til_profile"), dict):
        profile = profile.get("til_profile")
    elif isinstance(profile.get("profile"), dict):
        profile = profile.get("profile")

    canonical = dict(profile)

    list_fields = [
        "scope_of_work",
        "service_recommendation_line_items",
        "service_line_item_annotations",
        "recommended_interval_or_trigger",
        "usage_counters_to_check_or_consider",
        "configuration_variables",
        "severity_signals",
        "failure_consequences",
        "missing_information_flags",
        "source_snippets",
        "tables_found_summary",
        "parts_referenced",
        "reference_documents",
        "mli_numbers",
    ]

    for field in list_fields:
        value = canonical.get(field)
        if value is None:
            continue
        if isinstance(value, list):
            continue
        canonical[field] = [value]

    normalized_parts: list[dict[str, Any]] = []
    for item in (canonical.get("parts_referenced") or []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        part_number, part_context = _normalize_part_number_and_context(
            normalized_item.get("part_number"),
            normalized_item.get("context"),
        )
        normalized_item["part_number"] = part_number
        normalized_item["context"] = part_context
        normalized_item["source_location"] = _normalize_source_location(
            normalized_item.get("source_location")
        )
        normalized_parts.append(normalized_item)
    canonical["parts_referenced"] = normalized_parts

    try:
        if canonical.get("extraction_confidence") is not None:
            canonical["extraction_confidence"] = float(canonical["extraction_confidence"])
    except Exception:
        pass

    return canonical


def _workspace_sample_priority(row: dict) -> tuple[int, str]:
    if row.get("source") != "workspace_sample_pdf":
        return (1, str(row.get("file_name") or ""))
    return (0, str(row.get("file_name") or ""))


def pick_pdf_row(requested_til: str, catalog: list[dict]) -> dict | None:
    normalized_requested = normalize_til_key(requested_til)
    base_requested = extract_base_til_num(requested_til)
    requested_base_key = re.search(r"\d{4}", base_requested)
    requested_base_key_text = requested_base_key.group(0) if requested_base_key else ""

    exact_matches = [row for row in catalog if row["normalized_til_key"] == normalized_requested]
    base_matches = [
        row
        for row in catalog
        if row["base_til_num"] == base_requested
        or (requested_base_key_text and clean_text(row.get("til_number")).startswith(requested_base_key_text))
    ]

    ranked_exact_matches = sorted(exact_matches, key=_workspace_sample_priority)
    ranked_base_matches = sorted(
        base_matches,
        key=lambda row: (
            -row["revision_number"],
            _workspace_sample_priority(row)[0],
            row["til_number"],
        ),
    )
    ranked_matches = ranked_exact_matches or ranked_base_matches
    if not ranked_matches:
        return None

    selected = dict(ranked_matches[0])
    selected["match_type"] = "exact_til_number" if exact_matches else "base_til_latest_revision"
    selected["requested_til_number"] = requested_til
    return selected


def _looks_like_markdown_table_header(line: str) -> bool:
    return "|" in line and line.count("|") >= 2


def _looks_like_markdown_table_separator(line: str) -> bool:
    compact = line.replace(" ", "")
    return bool(re.fullmatch(r"\|?[:\-\|]+\|?", compact)) and "-" in compact


def _extract_labeled_markdown_tables(text_content: str) -> list[dict]:
    lines = text_content.splitlines()
    labeled_tables: list[dict] = []

    current_label = None
    current_description = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        label_match = re.search(r"(Table\s+\d+)\s*:\s*(.+)", line, flags=re.IGNORECASE)
        if label_match:
            current_label = label_match.group(1)
            current_description = label_match.group(2).strip()

        if i + 1 < len(lines):
            header = lines[i].rstrip()
            separator = lines[i + 1].rstrip()
            if _looks_like_markdown_table_header(header) and _looks_like_markdown_table_separator(separator):
                block = [header, separator]
                i += 2
                while i < len(lines) and "|" in lines[i]:
                    block.append(lines[i].rstrip())
                    i += 1

                labeled_tables.append(
                    {
                        "label": current_label,
                        "description": current_description,
                        "content": "\n".join(block).strip(),
                    }
                )
                continue

        i += 1

    return labeled_tables


def _sanitize_extracted_text(text: str) -> str:
    """Remove embedded image payloads so text_content keeps only readable extracted text."""
    sanitized = text or ""

    # Drop markdown images that embed bytes/base64 payloads inline.
    sanitized = re.sub(r"!\[[^\]]*\]\(\s*data:image[^)]*\)", "", sanitized, flags=re.IGNORECASE)

    # Drop raw base64 blobs that can appear in parser output for images.
    sanitized = re.sub(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]{100,}", "", sanitized)

    # Compact excessive blank lines created after removals.
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    return sanitized.strip()


def _extract_text_and_tables(body: str, content_type: str) -> tuple[str, list[dict]]:
    body = body or ""
    content_type = (content_type or "").lower()

    if "application/json" in content_type:
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return body, _extract_labeled_markdown_tables(body)

        for key in ("markdown", "text", "content", "body"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                clean_value = _sanitize_extracted_text(value)
                return clean_value, _extract_labeled_markdown_tables(clean_value)

        results = payload.get("results")
        if isinstance(results, dict):
            text_chunks: list[str] = []
            for page_key in sorted(results.keys(), key=lambda k: int(k) if str(k).isdigit() else str(k)):
                page_items = results.get(page_key) or []
                if not isinstance(page_items, list):
                    continue
                for item in page_items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") in {"text", "table"}:
                        for piece in item.get("content", []):
                            if isinstance(piece, str) and piece.strip():
                                text_chunks.append(piece.strip())
            text_content = _sanitize_extracted_text("\n\n".join(text_chunks))
            return text_content, _extract_labeled_markdown_tables(text_content)

        fallback = _sanitize_extracted_text(json.dumps(payload, ensure_ascii=False))
        return fallback, _extract_labeled_markdown_tables(fallback)

    clean_body = _sanitize_extracted_text(body)
    return clean_body, _extract_labeled_markdown_tables(clean_body)


def _extract_operation_id(payload: dict[str, Any]) -> str:
    for key in ("operation_id", "operationId", "id", "job_id", "jobId"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _get_async_status_value(payload: dict[str, Any]) -> str:
    for key in ("status", "state", "operation_status", "operationStatus"):
        value = payload.get(key)
        if value is not None:
            return str(value).strip().lower()
    return ""


def _compute_retry_delay_s(attempt: int) -> float:
    base = PARSER_HTTP_BACKOFF_BASE_S * (2 ** max(0, attempt - 1))
    capped = min(base, PARSER_HTTP_BACKOFF_MAX_S)
    jitter = random.uniform(0.0, PARSER_HTTP_BACKOFF_JITTER_S)
    return capped + jitter


def _request_with_backoff(
    method: str,
    url: str,
    request_name: str,
    max_attempts: int | None = None,
    **kwargs: Any,
) -> requests.Response:
    attempts = max_attempts or PARSER_HTTP_MAX_RETRIES
    attempts = max(1, attempts)

    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(method=method, url=url, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt >= attempts:
                raise

            delay_s = _compute_retry_delay_s(attempt)
            _vlog(
                "%s request exception on attempt %s/%s. Retrying in %.1fs. Error: %s",
                request_name,
                attempt,
                attempts,
                delay_s,
                exc,
            )
            time.sleep(delay_s)
            continue

        if response.status_code in PARSER_HTTP_RETRY_STATUS_CODES and attempt < attempts:
            delay_s = _compute_retry_delay_s(attempt)
            preview = (response.text or "").strip().replace("\n", " ")[:200]
            _vlog(
                "%s returned retryable HTTP %s on attempt %s/%s. Retrying in %.1fs. body=%s",
                request_name,
                response.status_code,
                attempt,
                attempts,
                delay_s,
                preview,
            )
            time.sleep(delay_s)
            continue

        return response

    if last_exc is not None:
        raise RuntimeError(f"{request_name} failed after retries") from last_exc
    raise RuntimeError(f"{request_name} failed after retries")


def _submit_parser_async(pdf_path: str) -> str:
    data = {"output_format": "markdown"}
    with PARSER_ASYNC_SUBMIT_SEMAPHORE:
        _vlog("Parser submit gate acquired for %s", pdf_path)
        with open(pdf_path, "rb") as f:
            files = {"file": (Path(pdf_path).name, f, _guess_mime_type(pdf_path))}
            response = _request_with_backoff(
                method="POST",
                url=PARSER_ASYNC_SUBMIT_URL,
                request_name=f"parser async submit [{pdf_path}]",
                headers=HEADERS,
                files=files,
                data=data,
                verify=_get_verify_setting(),  # nosec B501: explicit fallback for corp TLS chain issues in dev
                timeout=REQUEST_TIMEOUT_S,
            )
    if response.status_code not in (200, 201, 202):
        raise RuntimeError(
            f"Async parser submit returned HTTP {response.status_code} for {pdf_path}: {response.text[:500]}"
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise RuntimeError(f"Async parser submit returned non-JSON response for {pdf_path}") from exc

    operation_id = _extract_operation_id(payload if isinstance(payload, dict) else {})
    if not operation_id:
        raise RuntimeError(f"Async parser submit response missing operation id for {pdf_path}: {str(payload)[:500]}")
    _plog("[progress] submit ok: operation_id=%s file=%s", operation_id, pdf_path)
    return operation_id


def _wait_for_parser_async_completion(operation_id: str, pdf_path: str) -> None:
    started = time.time()
    last_status: str | None = None
    poll_count = 0
    while True:
        elapsed = time.time() - started
        if elapsed > PARSER_ASYNC_MAX_WAIT_S:
            raise TimeoutError(
                f"Async parser status timeout after {PARSER_ASYNC_MAX_WAIT_S}s for {pdf_path} "
                f"(operation_id={operation_id}, last_status={last_status or '<unknown>'})"
            )

        poll_count += 1
        status_url = PARSER_ASYNC_STATUS_URL_TMPL.format(operation_id=operation_id)
        response = _request_with_backoff(
            method="GET",
            url=status_url,
            request_name=f"parser async status [{operation_id}]",
            headers=HEADERS,
            verify=_get_verify_setting(),  # nosec B501: explicit fallback for corp TLS chain issues in dev
            timeout=REQUEST_TIMEOUT_S,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Async parser status returned HTTP {response.status_code} for {pdf_path} "
                f"(operation_id={operation_id}): {response.text[:500]}"
            )

        payload = response.json() if response.text else {}
        status_value = _get_async_status_value(payload if isinstance(payload, dict) else {})

        if status_value != last_status:
            _vlog(
                "Parser async status transition for %s (operation_id=%s): %s -> %s (elapsed=%.1fs)",
                pdf_path,
                operation_id,
                last_status or "<start>",
                status_value or "<empty>",
                elapsed,
            )
            last_status = status_value
        elif poll_count % PARSER_ASYNC_HEARTBEAT_POLLS == 0:
            _vlog(
                "Parser async status heartbeat for %s (operation_id=%s): %s (elapsed=%.1fs, polls=%s)",
                pdf_path,
                operation_id,
                status_value or "<empty>",
                elapsed,
                poll_count,
            )

        if poll_count % PARSER_ASYNC_LIVE_HEARTBEAT_POLLS == 0:
            _plog(
                "[progress] waiting: file=%s operation_id=%s status=%s elapsed=%.1fs polls=%s",
                pdf_path,
                operation_id,
                status_value or "<empty>",
                elapsed,
                poll_count,
            )

        # Some backends can lag status updates while result becomes available first.
        if poll_count % PARSER_ASYNC_RESULT_PROBE_POLLS == 0:
            try:
                result_url = PARSER_ASYNC_RESULT_URL_TMPL.format(operation_id=operation_id)
                result_probe = _request_with_backoff(
                    method="GET",
                    url=result_url,
                    request_name=f"parser async result probe [{operation_id}]",
                    max_attempts=2,
                    headers=HEADERS,
                    verify=_get_verify_setting(),  # nosec B501: explicit fallback for corp TLS chain issues in dev
                    timeout=REQUEST_TIMEOUT_S,
                )
                if result_probe.status_code == 200 and (result_probe.text or "").strip():
                    _vlog(
                        "Parser async result became available before terminal status for %s (operation_id=%s). Continuing.",
                        pdf_path,
                        operation_id,
                    )
                    return
            except Exception:
                pass

        if status_value in {"completed", "complete", "done", "success", "succeeded"}:
            return
        if status_value in {"failed", "error", "cancelled", "canceled"}:
            raise RuntimeError(
                f"Async parser reported terminal status '{status_value}' for {pdf_path} "
                f"(operation_id={operation_id}): {str(payload)[:500]}"
            )

        time.sleep(PARSER_ASYNC_POLL_INTERVAL_S)


def _fetch_parser_async_result(operation_id: str, pdf_path: str) -> tuple[str, str]:
    result_url = PARSER_ASYNC_RESULT_URL_TMPL.format(operation_id=operation_id)
    response = _request_with_backoff(
        method="GET",
        url=result_url,
        request_name=f"parser async result [{operation_id}]",
        headers=HEADERS,
        verify=_get_verify_setting(),  # nosec B501: explicit fallback for corp TLS chain issues in dev
        timeout=REQUEST_TIMEOUT_S,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Async parser result returned HTTP {response.status_code} for {pdf_path} "
            f"(operation_id={operation_id}): {response.text[:500]}"
        )
    return response.text or "", response.headers.get("Content-Type", "")


def _discover_source_rows_from_volumes(volume_paths: list[str]) -> list[dict[str, Any]]:
    source_rows: list[dict[str, Any]] = []
    allowed = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in SOURCE_FILE_EXTENSIONS}
    for volume in volume_paths:
        root = Path(volume)
        if not root.exists():
            continue
        for path_obj in root.rglob("*"):
            if not path_obj.is_file():
                continue
            if path_obj.suffix.lower() not in allowed:
                continue
            normalized_path = str(path_obj).replace("\\", "/")
            try:
                stat = path_obj.stat()
                modified_ts = float(stat.st_mtime)
                file_size = int(stat.st_size)
            except Exception:
                modified_ts = 0.0
                file_size = 0
            source_rows.append(
                {
                    "til_number": _extract_til_number(normalized_path),
                    "normalized_til_key": normalize_til_key(_extract_til_number(normalized_path)),
                    "pdf_path": normalized_path,
                    "file_last_modified_ts": modified_ts,
                    "file_size_bytes": file_size,
                }
            )

    # No filename/TIL-key pre-skip: keep discovery exhaustive and defer
    # duplicate decisions to post-LLM til_number checks.
    path_map: dict[str, dict[str, Any]] = {}
    for row in source_rows:
        path_key = clean_text(row.get("pdf_path"))
        if not path_key:
            continue
        path_map[path_key] = row

    return sorted(path_map.values(), key=lambda item: clean_text(item.get("pdf_path")))


def _build_catalog_from_paths(pdf_paths: list[str]) -> list[dict]:
    catalog: list[dict] = []
    for pdf_path in pdf_paths:
        path_obj = Path(pdf_path)
        til_number = _extract_til_number(pdf_path)
        catalog.append(
            {
                "pdf_path": pdf_path,
                "file_name": path_obj.name,
                "til_number": til_number,
                "normalized_til_key": normalize_til_key(til_number),
                "base_til_num": extract_base_til_num(til_number),
                "revision_number": parse_revision_number(til_number),
                "source": "workspace_sample_pdf",
            }
        )
    return catalog


def _resolve_match_for_pdf(pdf_path: str, catalog: list[dict]) -> tuple[str, str]:
    requested_til = _extract_til_number(pdf_path)
    selected_pdf_row = pick_pdf_row(requested_til, catalog)
    matched_til_number = requested_til
    match_type = "exact_til_number"
    if selected_pdf_row:
        matched_til_number = clean_text(selected_pdf_row.get("til_number")) or requested_til
        match_type = clean_text(selected_pdf_row.get("match_type")) or "exact_til_number"
    return matched_til_number, match_type


def _extract_foundation_doc_json(
    pdf_path: str,
    matched_til_number: str,
    match_type: str,
) -> dict:
    try:
        operation_id = _submit_parser_async(pdf_path)
        _wait_for_parser_async_completion(operation_id, pdf_path)
        body, content_type = _fetch_parser_async_result(operation_id, pdf_path)
    except requests.RequestException as e:
        raise RuntimeError(f"Parser request failed for {pdf_path}: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Parser async flow failed for {pdf_path}: {e}") from e

    text_content, labeled_tables = _extract_text_and_tables(body, content_type)

    return {
        "method": "foundation_async",
        "pdf_path": pdf_path,
        "matched_til_number": matched_til_number,
        "match_type": match_type,
        "parser_operation_id": operation_id,
        "text_length": len(text_content),
        "labeled_table_count": len(labeled_tables),
        "text_content": text_content,
        "labeled_tables": labeled_tables,
    }


def _extract_parsed_profile_json_with_databricks(
    pdf_path: str,
    pdf_bytes: bytes,
    matched_til_number: str,
    match_type: str,
) -> str | None:
    doc_ref = DocumentReference(
        document_id=matched_til_number,
        source_path=pdf_path,
        source_hash=None,
        metadata={
            "til_number": matched_til_number,
            "match_type": match_type,
        },
    )
    parsed_output = TIL_PARSER.parse(doc_ref, pdf_bytes)
    parser_fields = parsed_output.fields or {}
    pdf_text = (parser_fields.get("raw_text") or "").strip()
    tables = parser_fields.get("raw_tables") or []

    user_prompt = build_user_prompt(pdf_text, tables)
    parsed_profile, _raw_profile, _ = call_llm_for_profile_extraction(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )
    if parsed_profile:
        parsed_profile = canonicalize_profile_for_contract(parsed_profile)
        parsed_profile = normalize_til_profile(parsed_profile)
        parsed_profile = _finalize_profile_for_output(parsed_profile)

    return json.dumps(parsed_profile, default=str) if parsed_profile else None


def _extract_parsed_profile_json_from_foundation_doc(
    foundation_doc_json: dict[str, Any],
) -> str | None:
    pdf_text = clean_text(foundation_doc_json.get("text_content"))
    labeled_tables = foundation_doc_json.get("labeled_tables") or []
    if not isinstance(labeled_tables, list):
        labeled_tables = []

    user_prompt = build_user_prompt(pdf_text, labeled_tables)
    parsed_profile, _raw_profile, _ = call_llm_for_profile_extraction(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
    )
    if parsed_profile:
        parsed_profile = canonicalize_profile_for_contract(parsed_profile)
        parsed_profile = normalize_til_profile(parsed_profile)
        parsed_profile = _finalize_profile_for_output(parsed_profile)

    return json.dumps(parsed_profile, default=str) if parsed_profile else None


def extract_doc_json_for_pdf(pdf_path: str, catalog: list[dict]) -> dict:
    matched_til_number, match_type = _resolve_match_for_pdf(pdf_path, catalog)

    foundation_doc_json = _extract_foundation_doc_json(
        pdf_path=pdf_path,
        matched_til_number=matched_til_number,
        match_type=match_type,
    )

    return {
        "pdf_path": pdf_path,
        "matched_til_number": matched_til_number,
        "match_type": match_type,
        "parsed_profile_json": None,
        "extracted_doc_json": json.dumps(foundation_doc_json, default=str),
    }


def _extract_llm_til_number_from_profile_json(parsed_profile_json: str | None) -> str:
    if not parsed_profile_json:
        return ""
    try:
        payload = json.loads(parsed_profile_json)
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""

    canonical_payload = canonicalize_profile_for_contract(payload)
    if not isinstance(canonical_payload, dict):
        canonical_payload = payload

    for field in ("til_number", "til_id", "document_number", "til_no"):
        value = clean_text(canonical_payload.get(field))
        if value:
            return value
    return ""


def _build_output_row(
    til_number: str,
    pdf_path: str,
    parsed_profile_json: str | None,
    extracted_doc_json: str | None,
) -> dict[str, Any]:
    return {
        "til_number": til_number,
        "til_base_number": extract_base_til_num(til_number) or None,
        "til_revision_number": extract_til_revision_number(til_number) or None,
        "pdf_path": pdf_path,
        "parsed_profile_json": parsed_profile_json,
        "extracted_doc_json": extracted_doc_json,
    }


def _populate_parsed_profile_json_on_main_thread(
    rows: list[dict[str, Any]],
    seen_til_keys: set[str],
) -> int:
    """Run parsed-profile generation on main thread so Spark-bound parser keeps active session."""
    if not rows:
        return 0

    started = time.time()
    total = len(rows)
    pending_success_writes: list[dict[str, Any]] = []
    skipped_duplicates = 0

    def _flush_success_rows() -> None:
        nonlocal skipped_duplicates
        if not WRITE_OUTPUT_TABLE or not pending_success_writes:
            return
        write_rows: list[dict[str, Any]] = []
        for item in pending_success_writes:
            llm_til_number = _extract_llm_til_number_from_profile_json(item.get("parsed_profile_json"))
            effective_til_number = _reconcile_til_number(llm_til_number, item.get("til_number"))
            effective_til_key = normalize_til_key(effective_til_number)

            if SKIP_ALREADY_INGESTED and effective_til_key and effective_til_key in seen_til_keys:
                item["duplicate_skipped"] = True
                skipped_duplicates += 1
                continue

            if effective_til_key:
                seen_til_keys.add(effective_til_key)
            item["duplicate_skipped"] = False
            item["til_number"] = effective_til_number

            if not item.get("parsed_profile_json"):
                item["extract_status"] = "error"
                continue

            write_rows.append(
                _build_output_row(
                    til_number=effective_til_number,
                    pdf_path=clean_text(item.get("pdf_path")),
                    parsed_profile_json=item.get("parsed_profile_json"),
                    extracted_doc_json=item.get("extracted_doc_json"),
                )
            )

        if write_rows:
            _write_profile_rows(write_rows)
        pending_success_writes.clear()

    for idx, row in enumerate(rows, start=1):
        if clean_text(row.get("extract_status")).lower() == "error":
            row["parsed_profile_json"] = None
            if idx % 10 == 0 or idx == total:
                _vlog(
                    "  Parsed profile progress: %s/%s docs  elapsed=%.1fs",
                    idx,
                    total,
                    time.time() - started,
                )
            continue

        pdf_path = clean_text(row.get("pdf_path"))
        matched_til_number = clean_text(row.get("matched_til_number")) or clean_text(row.get("til_number"))
        match_type = clean_text(row.get("match_type")) or "exact_til_number"

        extracted_doc_json_raw = clean_text(row.get("extracted_doc_json"))
        foundation_doc_json: dict[str, Any] = {}
        if extracted_doc_json_raw:
            try:
                parsed_obj = json.loads(extracted_doc_json_raw)
                if isinstance(parsed_obj, dict):
                    foundation_doc_json = parsed_obj
            except Exception:
                foundation_doc_json = {}

        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
            parsed_profile_json = _extract_parsed_profile_json_with_databricks(
                pdf_path=pdf_path,
                pdf_bytes=pdf_bytes,
                matched_til_number=matched_til_number,
                match_type=match_type,
            )
        except Exception as exc:
            _vlog(
                "Databricks parser unavailable for %s; falling back to foundation async content for parsed_profile_json. Error: %s",
                pdf_path,
                exc,
            )
            parsed_profile_json = _extract_parsed_profile_json_from_foundation_doc(foundation_doc_json)

        if not parsed_profile_json:
            row["extract_status"] = "error"
            row["parsed_profile_json"] = None
            continue

        row["parsed_profile_json"] = parsed_profile_json
        pending_success_writes.append(row)
        if len(pending_success_writes) >= max(1, INCREMENTAL_WRITE_FLUSH_SIZE):
            _flush_success_rows()

        if idx % 10 == 0 or idx == total:
            _vlog(
                "  Parsed profile progress: %s/%s docs  elapsed=%.1fs",
                idx,
                total,
                time.time() - started,
            )

    _flush_success_rows()
    return skipped_duplicates


def safe_extract_til_batch(batch_idx: int, batch_pdf_paths: list[str], catalog: list[dict]) -> list[dict]:
    """Extract one batch of TIL docs; keep going if one file fails."""
    batch_rows: list[dict] = []
    for pdf_path in batch_pdf_paths:
        til_number = clean_text(_extract_til_number(pdf_path))
        try:
            extracted_result = extract_doc_json_for_pdf(pdf_path, catalog)
            til_number = clean_text(extracted_result.get("matched_til_number")) or til_number
            if not til_number:
                raise ValueError(f"Missing matched_til_number for extracted result: {pdf_path}")
            batch_rows.append(
                {
                    "til_number": til_number,
                    "matched_til_number": til_number,
                    "pdf_path": clean_text(extracted_result.get("pdf_path")),
                    "match_type": clean_text(extracted_result.get("match_type")) or "exact_til_number",
                    "extract_status": "ok",
                    "parsed_profile_json": extracted_result.get("parsed_profile_json"),
                    "extracted_doc_json": extracted_result.get("extracted_doc_json"),
                }
            )
        except Exception as exc:
            log.warning(f"[batch {batch_idx}] failed for {pdf_path}: {exc}")
            failure_payload = {
                "method": "foundation_async",
                "pdf_path": pdf_path,
                "matched_til_number": til_number,
                "match_type": "error",
                "parser_error": str(exc),
            }
            batch_rows.append(
                {
                    "til_number": til_number or clean_text(Path(pdf_path).stem),
                    "matched_til_number": til_number,
                    "pdf_path": pdf_path,
                    "match_type": "error",
                    "extract_status": "error",
                    "parsed_profile_json": None,
                    "extracted_doc_json": json.dumps(failure_payload, default=str),
                }
            )
    return batch_rows


# COMMAND ----------

output_schema = StructType([
    StructField("til_number", StringType(), False),
    StructField("til_base_number", StringType(), True),
    StructField("til_revision_number", StringType(), True),
    StructField("pdf_path", StringType(), True),
    StructField("parsed_profile_json", StringType(), True),
    StructField("extracted_doc_json", StringType(), True),
])

_ensure_profile_run_audit_table()

if WRITE_OUTPUT_TABLE and spark.catalog.tableExists(OUTPUT_TABLE):
    existing_output_columns = {field.name for field in spark.table(OUTPUT_TABLE).schema.fields}
    missing_output_columns = [
        column_name
        for column_name in ("til_base_number", "til_revision_number")
        if column_name not in existing_output_columns
    ]
    if missing_output_columns:
        spark.sql(
            f"ALTER TABLE {OUTPUT_TABLE} ADD COLUMNS ({', '.join(f'{name} STRING' for name in missing_output_columns)})"
        )

if WRITE_OUTPUT_TABLE and RESET_OUTPUT_TABLE:
    # Optional reset for controlled backfills; disabled by default for daily ingestion.
    (
        spark.createDataFrame([], schema=output_schema)
        .write.format("delta")
        .option("overwriteSchema", "true")
        .option("userMetadata", PROFILE_RUN_ID)
        .mode("overwrite")
        .saveAsTable(OUTPUT_TABLE)
    )

source_rows = _discover_source_rows_from_volumes(SOURCE_VOLUMES)
pdf_paths = [clean_text(row.get("pdf_path")) for row in source_rows if clean_text(row.get("pdf_path"))]
if not source_rows:
    raise ValueError(
        f"No source files found in SOURCE_VOLUMES for extensions {SOURCE_FILE_EXTENSIONS}: {SOURCE_VOLUMES}"
    )

existing_til_keys_for_skip: set[str] = set()
existing_pdf_names_for_skip: set[str] = set()
if WRITE_OUTPUT_TABLE and SKIP_ALREADY_INGESTED and spark.catalog.tableExists(OUTPUT_TABLE):
    try:
        existing_rows = spark.table(OUTPUT_TABLE).select("til_number", "pdf_path").collect()
        existing_til_keys_for_skip = {
            normalize_til_key(clean_text(row["til_number"]))
            for row in existing_rows
            if row["til_number"] is not None and clean_text(row["til_number"])
        }
        existing_pdf_names_for_skip = {
            Path(clean_text(row["pdf_path"]).replace("\\", "/")).name.lower()
            for row in existing_rows
            if row["pdf_path"] is not None and clean_text(row["pdf_path"])
        }
        print(
            f"LLM-key duplicate skip enabled. Existing TIL keys in table: {len(existing_til_keys_for_skip)}"
        )
        if SKIP_ALREADY_INGESTED_BY_NAME:
            print(
                f"PDF-name duplicate skip enabled. Existing PDF names in table: {len(existing_pdf_names_for_skip)}"
            )
    except Exception as exc:
        log.warning("Could not apply incremental skip filter from OUTPUT_TABLE %s: %s", OUTPUT_TABLE, exc)

if SKIP_ALREADY_INGESTED_BY_NAME and existing_pdf_names_for_skip:
    discovered_pdf_count = len(pdf_paths)
    pdf_paths = [
        pdf_path
        for pdf_path in pdf_paths
        if Path(pdf_path.replace("\\", "/")).name.lower() not in existing_pdf_names_for_skip
    ]
    print(
        f"PDF-name incremental filter: {discovered_pdf_count - len(pdf_paths)} already-ingested files skipped; "
        f"{len(pdf_paths)} files remain."
    )

if not pdf_paths:
    print("No new files to process after incremental skip filter.")
    output_rows_for_df: list[dict[str, str | None]] = []
    output_df = spark.createDataFrame(output_rows_for_df, schema=output_schema)
    display({
        "source_volumes": SOURCE_VOLUMES,
        "source_file_extensions": list(SOURCE_FILE_EXTENSIONS),
        "test_file_limit": TEST_FILE_LIMIT,
        "pdf_count": 0,
        "output_row_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "failed_files": [],
        "columns": ["til_number", "pdf_path", "parsed_profile_json", "extracted_doc_json"],
        "write_output_table": WRITE_OUTPUT_TABLE,
        "output_table": OUTPUT_TABLE if WRITE_OUTPUT_TABLE else None,
        "skip_already_ingested": SKIP_ALREADY_INGESTED,
        "reset_output_table": RESET_OUTPUT_TABLE,
    })
    _write_profile_run_audit(
        status="completed",
        discovered_count=0,
        success_count=0,
        failed_count=0,
        skipped_count=0,
    )
    dbutils.notebook.exit("No new files to process")

if TEST_SINGLE_PDF_PATH:
    normalized_target = clean_text(TEST_SINGLE_PDF_PATH).replace("\\", "/")
    matching_paths = [p for p in pdf_paths if p.replace("\\", "/") == normalized_target]
    if not matching_paths:
        raise ValueError(
            "TEST_SINGLE_PDF_PATH was provided but not found in discovered source files. "
            f"test_path={normalized_target}"
        )
    pdf_paths = matching_paths
    print(f"Single-file test mode enabled. Processing only: {pdf_paths[0]}")
elif TEST_FILE_LIMIT is not None:
    try:
        _test_file_limit = int(TEST_FILE_LIMIT)
    except Exception as exc:
        raise ValueError(f"TEST_FILE_LIMIT must be an integer or None. Got: {TEST_FILE_LIMIT}") from exc
    if _test_file_limit <= 0:
        raise ValueError(f"TEST_FILE_LIMIT must be > 0 when set. Got: {_test_file_limit}")

    total_discovered = len(pdf_paths)
    pdf_paths = pdf_paths[:_test_file_limit]
    print(
        f"Limited-file test mode enabled. Processing first {len(pdf_paths)} of {total_discovered} discovered files."
    )

catalog = _build_catalog_from_paths(pdf_paths)

output_rows: list[dict[str, str | None]] = []
failed_files: list[str] = []
failed_rows: list[dict[str, Any]] = []
success_count = 0
skipped_duplicate_count = 0
seen_til_keys = set(existing_til_keys_for_skip)
if pdf_paths:
    if USE_BATCH_PROCESSING:
        batches = [
            (i // TIL_BATCH_SIZE, pdf_paths[i:i + TIL_BATCH_SIZE])
            for i in range(0, len(pdf_paths), TIL_BATCH_SIZE)
        ]
        total_batches = len(batches)
        completed_batches = 0
        t0 = time.time()

        _vlog(
            f"Processing {len(pdf_paths)} documents in {total_batches} batches "
            f"(batch_size={TIL_BATCH_SIZE}, concurrency={TIL_PROFILE_CONCURRENCY})"
        )

        with ThreadPoolExecutor(max_workers=TIL_PROFILE_CONCURRENCY) as pool:
            futures = {
                pool.submit(safe_extract_til_batch, bidx, batch_paths, catalog): bidx
                for bidx, batch_paths in batches
            }
            for future in as_completed(futures):
                batch_idx = futures[future]
                completed_batches += 1
                batch_rows = future.result()
                # Parse profile and write successes as each batch returns.
                skipped_duplicate_count += _populate_parsed_profile_json_on_main_thread(batch_rows, seen_til_keys)
                output_rows.extend(batch_rows)
                if completed_batches % 5 == 0 or completed_batches == total_batches:
                    _vlog(
                        f"  TIL progress: {completed_batches}/{total_batches} batches  "
                        f"rows={len(output_rows)}  elapsed={time.time() - t0:.1f}s"
                    )

        output_rows = sorted(output_rows, key=lambda row: (row.get("til_number") or "", row.get("pdf_path") or ""))

        failed_rows = [
            row for row in output_rows
            if clean_text(row.get("extract_status")).lower() == "error"
        ]
        duplicate_skipped_rows = [row for row in output_rows if bool(row.get("duplicate_skipped"))]
        failed_files = [clean_text(row.get("pdf_path")) for row in failed_rows if clean_text(row.get("pdf_path"))]
        success_count = len(output_rows) - len(failed_rows) - len(duplicate_skipped_rows)
    else:
        _vlog("Processing %s documents sequentially", len(pdf_paths))
        for idx, pdf_path in enumerate(pdf_paths, start=1):
            _plog("[progress] start file %s/%s: %s", idx, len(pdf_paths), pdf_path)
            try:
                extracted_result = extract_doc_json_for_pdf(pdf_path, catalog)
                matched_til_number = clean_text(extracted_result.get("matched_til_number")) or clean_text(_extract_til_number(pdf_path))
                match_type = clean_text(extracted_result.get("match_type")) or "exact_til_number"
                extracted_doc_json = clean_text(extracted_result.get("extracted_doc_json"))

                foundation_doc_json: dict[str, Any] = {}
                if extracted_doc_json:
                    try:
                        parsed_obj = json.loads(extracted_doc_json)
                        if isinstance(parsed_obj, dict):
                            foundation_doc_json = parsed_obj
                    except Exception:
                        foundation_doc_json = {}

                try:
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    parsed_profile_json = _extract_parsed_profile_json_with_databricks(
                        pdf_path=pdf_path,
                        pdf_bytes=pdf_bytes,
                        matched_til_number=matched_til_number,
                        match_type=match_type,
                    )
                except Exception as exc:
                    _vlog(
                        "Databricks parser unavailable for %s; falling back to foundation async content for parsed_profile_json. Error: %s",
                        pdf_path,
                        exc,
                    )
                    parsed_profile_json = _extract_parsed_profile_json_from_foundation_doc(foundation_doc_json)

                success_row = {
                    "til_number": matched_til_number,
                    "til_base_number": None,
                    "til_revision_number": None,
                    "pdf_path": clean_text(extracted_result.get("pdf_path")) or pdf_path,
                    "parsed_profile_json": parsed_profile_json,
                    "extracted_doc_json": extracted_doc_json,
                }

                llm_til_number = _extract_llm_til_number_from_profile_json(parsed_profile_json)
                effective_til_number = _reconcile_til_number(llm_til_number, matched_til_number)
                effective_til_key = normalize_til_key(effective_til_number)
                if SKIP_ALREADY_INGESTED and effective_til_key and effective_til_key in seen_til_keys:
                    skipped_duplicate_count += 1
                    _plog(
                        "[progress] skipped duplicate %s/%s by LLM til_number: %s",
                        idx,
                        len(pdf_paths),
                        effective_til_number,
                    )
                    continue
                if effective_til_key:
                    seen_til_keys.add(effective_til_key)
                success_row["til_number"] = effective_til_number
                success_row["til_base_number"] = extract_base_til_num(effective_til_number) or None
                success_row["til_revision_number"] = extract_til_revision_number(effective_til_number) or None

                if WRITE_OUTPUT_TABLE:
                    _write_profile_rows([success_row])
                    _plog("[progress] wrote success row %s/%s: %s", idx, len(pdf_paths), success_row.get("pdf_path"))
                else:
                    if not parsed_profile_json:
                        raise ValueError(f"Profile extraction returned empty parsed_profile_json for {pdf_path}")

                    success_row = _build_output_row(
                        til_number=effective_til_number,
                        pdf_path=clean_text(extracted_result.get("pdf_path")) or pdf_path,
                        parsed_profile_json=parsed_profile_json,
                        extracted_doc_json=extracted_doc_json,
                    )
                    output_rows.append(success_row)
                    _plog("[progress] processed success %s/%s: %s", idx, len(pdf_paths), success_row.get("pdf_path"))

                success_count += 1
            except Exception as exc:
                log.warning(f"[sequential] failed for {pdf_path}: {exc}")
                failed_files.append(pdf_path)

            if idx % 10 == 0 or idx == len(pdf_paths):
                _vlog("  Sequential progress: %s/%s files", idx, len(pdf_paths))

        failed_rows = [{"pdf_path": p} for p in failed_files]

reported_output_row_count = success_count if WRITE_OUTPUT_TABLE else len(output_rows)

print("Run summary:")
print(f"  discovered_files: {len(pdf_paths)}")
print(f"  output_rows: {reported_output_row_count}")
print(f"  succeeded_files: {success_count}")
print(f"  failed_files: {len(failed_rows)}")
print(f"  skipped_duplicates: {skipped_duplicate_count}")
if failed_files:
    print("Failed file list:")
    for file_path in failed_files:
        print(f"  - {file_path}")

_write_profile_run_audit(
    status="completed" if not failed_files else "failed",
    discovered_count=len(pdf_paths),
    success_count=success_count,
    failed_count=len(failed_files),
    skipped_count=skipped_duplicate_count,
)

output_rows_for_df = [
    {
        "til_number": clean_text(row.get("til_number")),
        "til_base_number": extract_base_til_num(row.get("til_number")) or None,
        "til_revision_number": extract_til_revision_number(row.get("til_number")) or None,
        "pdf_path": clean_text(row.get("pdf_path")),
        "parsed_profile_json": row.get("parsed_profile_json"),
        "extracted_doc_json": row.get("extracted_doc_json"),
    }
    for row in output_rows
]


# COMMAND ----------

output_df = spark.createDataFrame(output_rows_for_df, schema=output_schema)


def _display_wrapped_preview(df, rows: int = 20) -> None:
    """Render a readable wrapped table preview for long JSON text columns."""
    preview_pd = df.limit(rows).toPandas()
    styled = (
        preview_pd.style
        .set_table_styles(
            [
                {"selector": "th", "props": [("text-align", "left"), ("white-space", "nowrap")]},
                {
                    "selector": "td",
                    "props": [
                        ("white-space", "pre-wrap"),
                        ("word-break", "break-word"),
                        ("vertical-align", "top"),
                    ],
                },
            ]
        )
        .set_properties(subset=["til_number"], **{"min-width": "220px", "max-width": "280px"})
        .set_properties(subset=["pdf_path"], **{"min-width": "360px", "max-width": "520px"})
        .set_properties(subset=["parsed_profile_json"], **{"min-width": "420px", "max-width": "760px"})
        .set_properties(subset=["extracted_doc_json"], **{"min-width": "520px", "max-width": "980px"})
    )

    try:
        displayHTML(styled.to_html())
    except Exception:
        # Fallback for runtimes without displayHTML support.
        display(df.limit(rows))

if WRITE_OUTPUT_TABLE:
    print(f"Wrote {success_count} successful rows to {OUTPUT_TABLE}")
    print(f"Skipped {len(failed_rows)} failed rows from table write")
    if success_count > 0 and spark.catalog.tableExists(OUTPUT_TABLE):
        print("Wrapped preview of written table (first 20 rows):")
        _display_wrapped_preview(spark.table(OUTPUT_TABLE).select(
            "til_number", "til_base_number", "til_revision_number", "pdf_path", "parsed_profile_json", "extracted_doc_json"
        ))
    else:
        print("No successful rows were written; skipping table preview.")
else:
    print("WRITE_OUTPUT_TABLE is False; skipping table write.")
    print("Wrapped preview of output_df (first 20 rows):")
    _display_wrapped_preview(output_df.select(
        "til_number", "til_base_number", "til_revision_number", "pdf_path", "parsed_profile_json", "extracted_doc_json"
    ))

display({
    "source_volumes": SOURCE_VOLUMES,
    "source_file_extensions": list(SOURCE_FILE_EXTENSIONS),
    "test_file_limit": TEST_FILE_LIMIT,
    "pdf_count": len(pdf_paths),
    "output_row_count": reported_output_row_count,
    "success_count": success_count,
    "failed_count": len(failed_rows),
    "skipped_duplicates": skipped_duplicate_count,
    "failed_files": failed_files,
    "columns": [
        "til_number",
        "til_base_number",
        "til_revision_number",
        "pdf_path",
        "parsed_profile_json",
        "extracted_doc_json",
    ],
    "write_output_table": WRITE_OUTPUT_TABLE,
    "output_table": OUTPUT_TABLE if WRITE_OUTPUT_TABLE else None,
    "skip_already_ingested": SKIP_ALREADY_INGESTED,
    "reset_output_table": RESET_OUTPUT_TABLE,
})
