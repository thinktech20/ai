"""TIL Pipeline Shared Configuration.

Single source of truth for TIL-specific runtime parameters, table names,
status enums, and LiteLLM settings. Helper functions are inlined here so the
module is importable from any context (Databricks Repos, bundle deploys, or
local tests) without depending on `%run`-style notebook helpers.
"""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ─── Runtime parameter helpers ─────────────────────────────────────────────
# Self-contained so this module is importable from any context (Databricks
# Repos, bundle deploys, local tests) without depending on package-relative
# imports of common.sdg_common_utils that can fail in Databricks workspaces.

_DBUTILS_SENTINEL: object = object()
_dbutils_cache: object = _DBUTILS_SENTINEL


def _get_dbutils():
    """Resolve dbutils once. Notebook globals expose dbutils, but imported
    modules don't — fall back to the SDK runtime helper that works inside
    plain Python modules on DBR.
    """
    global _dbutils_cache
    if _dbutils_cache is not _DBUTILS_SENTINEL:
        return _dbutils_cache
    try:
        from databricks.sdk.runtime import dbutils as _dbu  # type: ignore
        _dbutils_cache = _dbu
    except Exception:
        _dbutils_cache = None
    return _dbutils_cache


def get_runtime_param(name: str, default: str = "") -> str:
    env_val = os.getenv(name, "").strip()
    if env_val:
        return env_val
    dbu = _get_dbutils()
    if dbu is not None:
        try:
            widget_val = dbu.widgets.get(name)
            if widget_val is not None and str(widget_val).strip() != "":
                return str(widget_val).strip()
        except Exception:
            pass
    return default


def get_runtime_bool(name: str, default: bool = False) -> bool:
    raw = get_runtime_param(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "t", "yes", "y", "on")


def parse_runtime_list(name: str) -> Optional[list[str]]:
    raw = get_runtime_param(name, "")
    if not raw:
        return None
    values = [part.strip() for part in re.split(r"[,;\n]", raw) if part.strip()]
    return values or None


# ─── Catalog & Schema Configuration ────────────────────────────────────────

JB_ENV = get_runtime_param("jb_env", "dev").strip().lower()

VIUD_CATALOG = get_runtime_param("TIL_CATALOG_VIUD", "viud")
VGPD_CATALOG = get_runtime_param("TIL_CATALOG_VGPD", "vgpd")
POC_CATALOG = get_runtime_param("TIL_POC_CATALOG", "vaid")
POC_SCHEMA = get_runtime_param("TIL_POC_SCHEMA", "ai_sot_field_service_report")

# Canonical TIL write namespace (aligned with FSR pattern).
TIL_CATALOG = get_runtime_param("TIL_CATALOG", POC_CATALOG)
TIL_SCHEMA = get_runtime_param("TIL_SCHEMA", POC_SCHEMA)

TIL_METADATA_TABLE = get_runtime_param(
    "TIL_METADATA_TABLE",
    f"{TIL_CATALOG}.{TIL_SCHEMA}.til_metadata",
)
TIL_CHUNKS_TABLE = get_runtime_param(
    "TIL_CHUNKS_TABLE",
    f"{TIL_CATALOG}.{TIL_SCHEMA}.til_chunks",
)
TIL_ELEMENTS_TABLE = get_runtime_param(
    "TIL_ELEMENTS_TABLE",
    f"{TIL_CATALOG}.{TIL_SCHEMA}.til_elements",
)
TIL_VALIDATION_RESULTS_TABLE = get_runtime_param(
    "TIL_VALIDATION_RESULTS_TABLE",
    f"{TIL_CATALOG}.{TIL_SCHEMA}.til_validation_results",
)
TIL_EVALUATION_RESULTS_TABLE = get_runtime_param(
    "TIL_EVALUATION_RESULTS_TABLE",
    f"{TIL_CATALOG}.{TIL_SCHEMA}.til_evaluation_results",
)
TIL_PIPELINE_RUN_AUDIT_TABLE = get_runtime_param(
    "TIL_PIPELINE_RUN_AUDIT_TABLE",
    f"{TIL_CATALOG}.{TIL_SCHEMA}.til_pipeline_run_audit",
)
TIL_PROFILE_TABLE = get_runtime_param(
    "TIL_PROFILE_TABLE",
    f"{TIL_CATALOG}.{TIL_SCHEMA}.til_profile",
)


# ─── Source Volumes ────────────────────────────────────────────────────────

TIL_SOURCE_VOLUME_PATHS = parse_runtime_list("TIL_SOURCE_VOLUME_PATHS") or [
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fsr_manual/manual_field_service_report/TILS_new",
]


# ─── Process 1: Metadata Extraction ────────────────────────────────────────

LLM_MODEL = get_runtime_param("TIL_LLM_MODEL", "azure-gpt-5-2")
LLM_TEMPERATURE = float(get_runtime_param("TIL_LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(get_runtime_param("TIL_LLM_MAX_TOKENS", "16000"))
LLM_USE_GATEWAY_DEFAULT_MAX_TOKENS = get_runtime_param(
    "TIL_LLM_USE_GATEWAY_DEFAULT_MAX_TOKENS", "true"
).strip().lower() in {"1", "true", "yes", "y"}
LLM_CONTEXT_WINDOW_TOKENS = int(get_runtime_param("TIL_LLM_CONTEXT_WINDOW", "4096"))

MAX_CHARS_PER_PDF = int(get_runtime_param("TIL_MAX_CHARS_PER_PDF", "40000"))

P1_MAX_PDFS = get_runtime_param("TIL_P1_MAX_PDFS", "")
P1_MAX_PDFS = int(P1_MAX_PDFS) if P1_MAX_PDFS else None

# Targeted ingestion: when set, only PDFs whose file name contains one of these
# (case-insensitive substring match) are processed. Matching is strict — a
# substring that resolves to >1 file is flagged as ``ambiguous_match`` rather
# than silently processing multiple files. Filenames are preferred over TIL
# numbers because filename → TIL-number regex parsing is brittle (misnamed
# files vanish silently). Pass either exact filenames or distinctive substrings.
P1_TARGET_PDF_NAMES = parse_runtime_list("TIL_P1_TARGET_PDF_NAMES")
P1_BATCH_SIZE = int(get_runtime_param("TIL_P1_BATCH_SIZE", "10"))
P1_COMMIT_BATCH = get_runtime_param("TIL_P1_COMMIT_BATCH", "")
P1_COMMIT_BATCH = int(P1_COMMIT_BATCH) if P1_COMMIT_BATCH else None
P1_MAX_RETRIES = int(get_runtime_param("TIL_P1_MAX_RETRIES", "2"))
TIL_LOW_CONFIDENCE_THRESHOLD = float(get_runtime_param("TIL_LOW_CONFIDENCE_THRESHOLD", "0.85"))


# ─── LiteLLM Gateway Configuration ─────────────────────────────────────────

def _read_secret_file(*paths: Path) -> str:
    for path in paths:
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except Exception:
            pass
    return ""


def _decode_maybe_base64(value: str) -> str:
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


def _validate_litellm_base_url(value: str) -> str:
    url = (value or "").strip()
    if not url:
        return url
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError(
            f"Invalid LITELLM_BASE_URL: {url!r}. Provide full URL with scheme, e.g. https://dev-gateway.apps.gevernova.net"
        )
    return url


def get_litellm_config() -> dict[str, str]:
    # Align with FSR: source from LITELLM_BASE_URL / LITELLM_API_KEY first
    # (env var or widget) so a cluster/workflow configured for FSR also works
    # for TIL without duplicate parameters. Fall back to legacy TIL_LLM_*.
    base_url = _validate_litellm_base_url(
        get_runtime_param("LITELLM_BASE_URL", "")
        or get_runtime_param("TIL_LLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
    )
    api_key = (
        get_runtime_param("LITELLM_API_KEY", "")
        or get_runtime_param("TIL_LLM_API_KEY", "")
    )
    model = get_runtime_param("TIL_LLM_MODEL", "azure-gpt-5-2")

    defaults = {
        "base_url": base_url,
        "api_key": _decode_maybe_base64(api_key),
        "model": model,
    }

    if not defaults["api_key"]:
        config_files = (
            Path.home() / ".litellm_config",
            Path("/etc/litellm_config"),
            Path("/Workspace/config/litellm_config"),
        )
        api_key = _read_secret_file(*config_files)
        if api_key:
            defaults["api_key"] = _decode_maybe_base64(api_key)

    if not defaults["api_key"]:
        raise ValueError("LiteLLM API key not found. Set LITELLM_API_KEY or create ~/.litellm_config")

    return defaults


def get_litellm_base_url() -> str:
    return get_litellm_config()["base_url"]


def get_litellm_api_key() -> str:
    return get_litellm_config()["api_key"]


def get_litellm_model() -> str:
    return get_litellm_config()["model"]


# ─── Process 2: Chunking (Future) ──────────────────────────────────────────

P2_CHUNK_SIZE_CHARS = int(get_runtime_param("TIL_P2_CHUNK_SIZE_CHARS", "1024"))
P2_CHUNK_OVERLAP = int(get_runtime_param("TIL_P2_CHUNK_OVERLAP", "256"))


# Backward-compatible aliases used by older notebook code.
TIL_LLM_MODEL = LLM_MODEL
TIL_LLM_TEMPERATURE = LLM_TEMPERATURE
TIL_LLM_MAX_TOKENS = LLM_MAX_TOKENS
TIL_LLM_USE_GATEWAY_DEFAULT_MAX_TOKENS = LLM_USE_GATEWAY_DEFAULT_MAX_TOKENS
TIL_LLM_TIMEOUT_SECONDS = int(get_runtime_param("TIL_LLM_TIMEOUT_SECONDS", "300"))
TIL_LLM_MAX_RETRIES = P1_MAX_RETRIES
# Source LLM gateway from FSR-aligned names first (LITELLM_*), fall back to
# legacy TIL_LLM_* widget/env for backward compatibility.
TIL_LLM_BASE_URL = (
    _validate_litellm_base_url(get_runtime_param("LITELLM_BASE_URL", ""))
    or get_runtime_param("TIL_LLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
)
TIL_LLM_API_KEY = _decode_maybe_base64(
    get_runtime_param("LITELLM_API_KEY", "")
    or get_runtime_param("TIL_LLM_API_KEY", "")
)


# ─── Status Enums ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MetadataStatus:
    """States for metadata extraction workflow (aligned with DS team E6.2 taxonomy)."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    PDF_NOT_FOUND = "pdf_not_found"
    LLM_PARSE_FAILED = "llm_parse_failed"
    FAILED = "failed"

    @classmethod
    def all(cls):
        return [
            cls.PENDING,
            cls.PROCESSING,
            cls.COMPLETED,
            cls.PDF_NOT_FOUND,
            cls.LLM_PARSE_FAILED,
            cls.FAILED,
        ]


@dataclass(frozen=True)
class ChunkStatus:
    """States for chunking workflow."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

    @classmethod
    def all(cls):
        return [cls.PENDING, cls.PROCESSING, cls.COMPLETED, cls.FAILED]


# ─── Validation ────────────────────────────────────────────────────────────

def validate_config() -> None:
    """Validate the most important configuration values."""
    errors = []

    if not TIL_SOURCE_VOLUME_PATHS:
        errors.append("TIL_SOURCE_VOLUME_PATHS is empty")

    if not TIL_METADATA_TABLE:
        errors.append("TIL_METADATA_TABLE not set")

    if JB_ENV not in ("dev", "staging", "prod"):
        errors.append(f"jb_env must be dev/staging/prod, got {JB_ENV}")

    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
