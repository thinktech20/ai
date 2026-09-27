# Databricks notebook source
# nb_sdg_til_metadata — Process 1: TIL Metadata Extraction & Registration (Silver)
#
# Discovers TIL PDFs in source volumes, extracts text via ai_parse_document,
# normalizes fields via LLM, and writes results to the metadata registry table.
#
# Purpose: Extract structured TIL profiles for downstream applicability logic
# and retrieval workflows (Steps 6 and beyond).

# COMMAND ----------

# MAGIC %pip install --quiet pydantic requests mlflow-skinny

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# ── Notebook parameters (widgets) ───────────────────────────────────────────
# Define widgets so the notebook can be parameterised either interactively
# (top-of-notebook widget UI) or as a job task. The default target list is the
# full DS-shared batch, and TIL_P1_MAX_PDFS must stay blank for that run.
# Set TIL_P1_MAX_PDFS to a small number only for ad-hoc smoke runs.
# Targeting by file name is preferred over TIL-number regex because misnamed
# files vanish silently from the regex path. Strict semantics: a substring that
# matches >1 file is flagged as ``ambiguous_match`` rather than silently
# processing all of them.

dbutils.widgets.text("jb_env", "dev", "Environment")
dbutils.widgets.text("TIL_P1_MAX_PDFS", "", "Max PDFs (blank = all)")
dbutils.widgets.text(
    "TIL_P1_TARGET_PDF_NAMES",
    "1502-2R1,1509-R4,1562-R1,1584-R1,1603-R2,1615-R1,1638-R3,1769,1850-R3,1870-R2,1907-R1,1937-R2,1945-R2,1972-R2,2045-R2,2069,2167-R1,2212-R3,2284,2297,2322-R2,2342-R1,2467,2511,2558",
    "Target PDF file names or substrings (comma-separated)",
)
dbutils.widgets.text("TIL_SOURCE_VOLUME_PATHS", "", "Override TIL source volume paths")
dbutils.widgets.text(
    "TIL_METADATA_TABLE",
    "vaid.ai_sot_field_service_report.til_metadata",
    "Override TIL metadata table FQN",
)
dbutils.widgets.text("TIL_LLM_MAX_TOKENS", "", "Override LLM max tokens (blank = config default)")
dbutils.widgets.text("FORCE_REPROCESS", "false", "Force reprocess all TILs (skip incremental detection; true/false)")
# LLM gateway (FSR-aligned). Workflow injects these via ${var.litellm_*};
# for interactive runs, paste the key into the widget.
dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net", "LiteLLM gateway base URL (blank = use default)")
dbutils.widgets.text("LITELLM_API_KEY", "", "LiteLLM API key (blank = use env / default)")

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)
from delta.tables import DeltaTable

import hashlib
import json
import time
import logging
import re
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow
from common.llm_client import get_last_llm_call_diagnostics

# Import our custom modules
from common.tils.til_config import (
    MAX_CHARS_PER_PDF,
    P1_MAX_PDFS,
    P1_TARGET_PDF_NAMES,
    TIL_ELEMENTS_TABLE,
    TIL_LLM_MAX_TOKENS,
    TIL_LLM_MODEL,
    TIL_LLM_TEMPERATURE,
    TIL_LOW_CONFIDENCE_THRESHOLD,
    TIL_METADATA_TABLE,
    TIL_SOURCE_VOLUME_PATHS,
)
from common.tils.til_llm_client import extract_til_profile_via_llm
from contracts.schemas.tils.til_profile_schema import normalize_til_profile
from contracts.types.entities import DocumentReference
from silver.src.tils.til_profile_extraction_llm import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from silver.src.tils.til_profile_extraction import (
    build_pdf_catalog,
    clean_text,
    pick_pdf_row_by_name,
)
from common.parsers.databricks_ai_parser import DatabricksAIParser

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    force=True,
)
for handler in logging.getLogger().handlers:
    handler.setLevel(logging.WARNING)
logging.getLogger("py4j").setLevel(logging.WARNING)
logging.getLogger("py4j.clientserver").setLevel(logging.WARNING)
log = logging.getLogger("til.p1.metadata")
log.setLevel(logging.INFO)
log.propagate = False
if not any(getattr(h, "name", "") == "til-p1-stdout" for h in log.handlers):
    _handler = logging.StreamHandler(sys.stdout)
    _handler.name = "til-p1-stdout"
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s"))
    log.addHandler(_handler)

# Parse FORCE_REPROCESS flag early (before it's used in log.info)
_force_reprocess_str = (dbutils.widgets.get("FORCE_REPROCESS") or "false").strip().lower()
FORCE_REPROCESS = _force_reprocess_str in ("true", "1", "yes")

log.info(
    "P1 start | table=%s | model=%s | max_pdfs=%s | target_tils=%s | source_volumes=%s | force_reprocess=%s",
    TIL_METADATA_TABLE,
    TIL_LLM_MODEL,
    P1_MAX_PDFS or "unlimited",
    len(P1_TARGET_PDF_NAMES) if P1_TARGET_PDF_NAMES else "all",
    len(TIL_SOURCE_VOLUME_PATHS),
    FORCE_REPROCESS,
)

# Backward-compatible local aliases used throughout the notebook body.
LLM_MODEL = TIL_LLM_MODEL
LLM_TEMPERATURE = TIL_LLM_TEMPERATURE
LLM_MAX_TOKENS = TIL_LLM_MAX_TOKENS

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
    # Blank widget = use gateway default (do not cap output tokens).
    LLM_MAX_TOKENS = None

# COMMAND ----------

# ── Shared parser setup ────────────────────────────────────────────────────

TIL_PARSER = DatabricksAIParser(max_text_chars=MAX_CHARS_PER_PDF)

# Stable run id stamped on every row written by this notebook execution.
# Format mirrors FSR audit conventions: timestamp + short uuid for uniqueness
# across concurrent runs.
P1_RUN_ID = f"til_p1_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


# COMMAND ----------

# ── Helper: Call LLM for profile extraction ────────────────────────────────

def call_llm_for_profile_extraction(
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any] | None, str | None, float]:
    """Call LLM via shared LiteLLM client and return parsed profile + raw + latency."""
    _ = temperature
    return extract_til_profile_via_llm(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


_PART_NUMBER_TOKEN_RE = re.compile(r"\b[A-Z0-9][A-Z0-9./-]{3,}\b")
_PART_NUMBER_RANGE_RE = re.compile(r"\b(through|thru|from|to)\b", re.IGNORECASE)


def _best_part_number_token(text: str) -> str:
    """Pick the first strong identifier-like token from a free-form part string."""
    # Prefer identifier-like tokens that contain digits (for example 146E3626)
    # and ignore pure words that may appear in prose/range text.
    candidates = _PART_NUMBER_TOKEN_RE.findall((text or "").upper())
    for token in candidates:
        if any(ch.isdigit() for ch in token):
            return token
    return ""


def _normalize_part_number_and_context(part_number: Any, context: Any) -> tuple[Any, str]:
    """Keep part_number identifier-only and move qualifiers/ranges into context."""
    part_text = clean_text(part_number)
    context_text = clean_text(context)
    if not part_text:
        return (None, context_text)

    normalized_space = re.sub(r"\s+", " ", part_text).strip()
    contains_range_word = bool(_PART_NUMBER_RANGE_RE.search(normalized_space))
    contains_multi_token = " " in normalized_space

    best_token = _best_part_number_token(normalized_space)
    if not best_token:
        # If no identifier can be recovered, keep traceability in context and
        # clear part_number so downstream logic does not use prose as an ID.
        if normalized_space and normalized_space not in context_text:
            context_text = f"{context_text} | part_number_raw: {normalized_space}".strip(" |")
        return (None, context_text)

    # If range/prose was present, preserve full text in context for traceability.
    if (contains_range_word or contains_multi_token) and normalized_space not in context_text:
        context_text = f"{context_text} | part_number_raw: {normalized_space}".strip(" |")

    return (best_token, context_text)


def _normalize_source_location(value: Any) -> str:
    """Normalize source location to DS-style page/location text when possible."""
    text = clean_text(value)
    if not text:
        return ""

    collapsed = re.sub(r"\s+", " ", text)
    page_match = re.search(r"\b(?:page|pg|p)\.?\s*[:#-]?\s*(\d+)\b", collapsed, re.IGNORECASE)
    table_match = re.search(r"\btable\s*[:#-]?\s*([A-Za-z0-9._-]+)\b", collapsed, re.IGNORECASE)

    page = page_match.group(1) if page_match else ""
    table = table_match.group(1) if table_match else ""
    # Prefer a stable DS-style rendering so outputs are comparable across runs.
    if page and table:
        return f"Page {page}, Table {table}"
    if page:
        return f"Page {page}, Body text"
    if table:
        return f"Table {table}"
    return collapsed


def canonicalize_profile_for_contract(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Apply light shape canonicalization before strict schema normalization.

    This keeps AI Parse richness while preventing avoidable type drift
    (scalar-vs-list, numeric-as-string) at the pipeline boundary.
    """
    if profile is None or not isinstance(profile, dict):
        return None

    # Some responses wrap the actual payload as {"til_profile": {...}}.
    if isinstance(profile.get("til_profile"), dict):
        profile = profile.get("til_profile")
    elif isinstance(profile.get("profile"), dict):
        profile = profile.get("profile")

    canonical = dict(profile)

    list_fields = [
        "scope_of_work",
        "service_recommendation_line_items",
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

    # Keep dict-shaped part entries and normalize key fields for DS parity.
    # - part_number: identifier-only
    # - source_location: page/location style when parsable
    normalized_parts: list[dict[str, Any]] = []
    for item in (canonical.get("parts_referenced") or []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        # Normalize part identifiers first, then preserve any non-identifier
        # qualifiers in context for auditability.
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
        # Leave as-is; downstream normalize function will provide safe defaults.
        pass

    return canonical


def profile_list_count(profile: dict[str, Any] | None, field: str) -> int:
    if not isinstance(profile, dict):
        return 0
    value = profile.get(field)
    return len(value) if isinstance(value, list) else 0


# COMMAND ----------

# ── Main extraction pipeline ───────────────────────────────────────────────

def build_til_elements(
    document_id: str,
    parser_fields: dict[str, Any],
    extraction_method: str,
    parser_version: str,
    run_id: str,
) -> list[dict[str, Any]]:
    """Build granular extraction elements for traceability.

    We capture a short text element plus each extracted table block so
    downstream debugging can inspect parser evidence per document.
    """
    elements: list[dict[str, Any]] = []

    raw_text = (parser_fields.get("raw_text") or "").strip()
    if raw_text:
        snippet = raw_text[:10000]
        snippet_hash = hashlib.sha1(snippet.encode("utf-8")).hexdigest()[:8]
        elements.append({
            "document_id": document_id,
            "element_id": f"text_001_{snippet_hash}",
            "element_type": "section",
            "element_text": snippet,
            "page_number": None,
            "bbox_json": None,
            "section_path": "document.raw_text",
            "source_method": extraction_method,
            "parser_version": parser_version,
            "run_id": run_id,
        })

    tables = parser_fields.get("raw_tables") or []
    for idx, table in enumerate(tables, start=1):
        content = (table or {}).get("content", "")
        content = content.strip() if isinstance(content, str) else ""
        if not content:
            continue
        table_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]
        page_number = (table or {}).get("page")
        try:
            page_number = int(page_number) if page_number is not None else None
        except Exception:
            page_number = None

        bbox = (table or {}).get("bbox")
        bbox_json = json.dumps(bbox, default=str) if bbox is not None else None

        # ai_parse_document commonly stores page context under bbox[*].page_id
        # (0-based). If table.page is absent, derive a 1-based page number.
        if page_number is None and isinstance(bbox, list) and bbox:
            try:
                page_id = bbox[0].get("page_id") if isinstance(bbox[0], dict) else None
                if page_id is not None:
                    page_number = int(page_id) + 1
            except Exception:
                page_number = None

        elements.append({
            "document_id": document_id,
            "element_id": f"table_{idx:03d}_{table_hash}",
            "element_type": "table",
            "element_text": content[:10000],
            "page_number": page_number,
            "bbox_json": bbox_json,
            "section_path": f"table_{idx}",
            "source_method": extraction_method,
            "parser_version": parser_version,
            "run_id": run_id,
        })

    # Preserve additional parser richness (titles, sections, figures, etc.)
    # without imposing brittle field-level regex extraction.
    raw_elements = parser_fields.get("raw_elements") or []
    max_non_table = 60
    non_table_idx = 0
    for raw in raw_elements:
        if non_table_idx >= max_non_table:
            break
        el_type = ((raw or {}).get("type") or "").lower()
        if el_type == "table":
            continue

        content = (raw or {}).get("content", "")
        content = content.strip() if isinstance(content, str) else ""
        if not content:
            continue

        non_table_idx += 1
        content_hash = hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]
        bbox = (raw or {}).get("bbox")
        bbox_json = json.dumps(bbox, default=str) if bbox is not None else None

        page_number = None
        if isinstance(bbox, list) and bbox:
            try:
                page_id = bbox[0].get("page_id") if isinstance(bbox[0], dict) else None
                if page_id is not None:
                    page_number = int(page_id) + 1
            except Exception:
                page_number = None

        elements.append({
            "document_id": document_id,
            "element_id": f"raw_{non_table_idx:03d}_{content_hash}",
            "element_type": el_type or "text",
            "element_text": content[:10000],
            "page_number": page_number,
            "bbox_json": bbox_json,
            "section_path": f"raw.{el_type or 'text'}.{non_table_idx}",
            "source_method": extraction_method,
            "parser_version": parser_version,
            "run_id": run_id,
        })

    return elements

def extract_til_profile(
    til_pdf_bytes: bytes,
    pdf_row: dict[str, Any],
) -> dict[str, Any]:
    """Extract a TIL profile from PDF bytes for a matched pdf catalog row.

    Returns a dict containing all DS-aligned identifier fields plus extraction
    results. Status uses the DS taxonomy plus explicit gateway-filter outcome:
    ``completed`` | ``llm_parse_failed`` | ``llm_content_filtered`` | ``failed``.
    """
    start_time = time.time()
    matched_til_number = pdf_row.get("til_number") or ""
    requested_til_number = pdf_row.get("requested_til_number") or matched_til_number
    match_type = pdf_row.get("match_type") or "exact_til_number"
    source_path = pdf_row.get("pdf_path") or ""
    source_system = pdf_row.get("source") or "databricks_volume"
    source_hash = hashlib.sha256(til_pdf_bytes).hexdigest() if til_pdf_bytes else None
    pdf_file_hash = hashlib.md5(til_pdf_bytes).hexdigest() if til_pdf_bytes else None

    base_result: dict[str, Any] = {
        "requested_til_number": requested_til_number,
        "matched_til_number": matched_til_number,
        "match_type": match_type,
        "source_path": source_path,
        "source_system": source_system,
        "source_hash": source_hash,
        "pdf_file_hash": pdf_file_hash,
        "parsed_profile": None,
        "raw_profile": None,
        "extracted_text_char_count": 0,
        "extracted_table_count": 0,
        "extracted_document_method": "databricks_ai",
        "parser_method": "databricks_ai",
        "parser_name": TIL_PARSER.name,
        "parser_version": TIL_PARSER.version,
        "extraction_confidence": 0.0,
        "latency_s": 0.0,
        "metadata_status": "failed",
        "error_message": None,
        "run_id": P1_RUN_ID,
        "elements": [],
        "parser_raw_element_count": 0,
        "profile_scope_count": 0,
        "profile_reco_count": 0,
        "profile_parts_count": 0,
        "profile_snippets_count": 0,
    }

    try:
        log.info(f"Extracting text from {matched_til_number} via shared DatabricksAIParser...")

        doc_ref = DocumentReference(
            document_id=matched_til_number,
            source_path=source_path or f"til://{matched_til_number}.pdf",
            source_hash=source_hash,
            metadata={
                "til_number": matched_til_number,
                "requested_til_number": requested_til_number,
                "match_type": match_type,
            },
        )

        parsed_output = TIL_PARSER.parse(doc_ref, til_pdf_bytes)
        parser_fields = parsed_output.fields or {}
        pdf_text = (parser_fields.get("raw_text") or "").strip()
        tables = parser_fields.get("raw_tables") or []

        # Keep table payload out of the main text body when it is already
        # passed as structured JSON to the prompt. Duplicating it here makes
        # table-heavy TILs much larger without adding new signal.

        if len(pdf_text) > MAX_CHARS_PER_PDF:
            log.warning(
                f"Truncating extracted text for {matched_til_number} from {len(pdf_text)} to {MAX_CHARS_PER_PDF} chars"
            )
            pdf_text = pdf_text[:MAX_CHARS_PER_PDF]

        base_result["extracted_text_char_count"] = len(pdf_text)
        base_result["extracted_table_count"] = len(tables)
        base_result["parser_raw_element_count"] = int(parser_fields.get("raw_element_count") or 0)
        base_result["extracted_document_method"] = parser_fields.get("extraction_method", "databricks_ai")
        base_result["parser_method"] = base_result["extracted_document_method"]
        document_id = Path(source_path).stem.lower() if source_path else (requested_til_number or "unknown").lower()
        base_result["elements"] = build_til_elements(
            document_id=document_id,
            parser_fields=parser_fields,
            extraction_method=base_result["extracted_document_method"],
            parser_version=base_result["parser_version"],
            run_id=P1_RUN_ID,
        )

        log.info(f"  Extracted {len(pdf_text)} chars, {len(tables)} tables")

        user_prompt = build_user_prompt(pdf_text, tables)

        log.info(f"Calling LLM for {matched_til_number}...")
        parsed_profile, raw_response, _llm_latency = call_llm_for_profile_extraction(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )

        base_result["raw_profile"] = raw_response

        if parsed_profile:
            parsed_profile = canonicalize_profile_for_contract(parsed_profile)
            parsed_profile = normalize_til_profile(parsed_profile)
            base_result["parsed_profile"] = parsed_profile
            base_result["extraction_confidence"] = parsed_profile.get("extraction_confidence", 0.0) or 0.0
            base_result["profile_scope_count"] = profile_list_count(parsed_profile, "scope_of_work")
            base_result["profile_reco_count"] = profile_list_count(parsed_profile, "service_recommendation_line_items")
            base_result["profile_parts_count"] = profile_list_count(parsed_profile, "parts_referenced")
            base_result["profile_snippets_count"] = profile_list_count(parsed_profile, "source_snippets")
            base_result["metadata_status"] = "completed"

        else:
            base_result["metadata_status"] = "llm_parse_failed"
            llm_diag = get_last_llm_call_diagnostics()
            if llm_diag.get("status") == "no_text_response":
                finish_reason = llm_diag.get("finish_reason") or "unknown"
                completion_tokens = llm_diag.get("completion_tokens")
                prompt_tokens = llm_diag.get("prompt_tokens")
                if finish_reason == "content_filter":
                    base_result["metadata_status"] = "llm_content_filtered"
                base_result["error_message"] = (
                    f"LLM returned 200 but no text (finish_reason={finish_reason}, "
                    f"prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens})"
                )
            elif llm_diag.get("status") == "http_error":
                base_result["error_message"] = f"LLM request failed with HTTP {llm_diag.get('status_code')}"
            elif llm_diag.get("status") == "request_exception":
                base_result["error_message"] = (
                    f"LLM request exception: {llm_diag.get('exception_type')}: "
                    f"{llm_diag.get('exception_message')}"
                )
            else:
                base_result["error_message"] = "LLM returned no parseable profile"

        base_result["latency_s"] = time.time() - start_time
        return base_result

    except Exception as exc:
        log.error(f"Extraction failed for {matched_til_number}: {exc}", exc_info=True)
        base_result["metadata_status"] = "failed"
        base_result["error_message"] = str(exc)
        base_result["latency_s"] = time.time() - start_time
        return base_result


# COMMAND ----------

# ── Discover and process TILs ──────────────────────────────────────────────

log.info("Discovering TIL PDFs...")
catalog = build_pdf_catalog(spark, TIL_SOURCE_VOLUME_PATHS)

if not catalog:
    log.error("No TIL volumes accessible. Check volume paths and permissions.")
    raise ValueError("TIL volume discovery failed")

log.info(f"Discovered {len(catalog)} TIL PDFs across {len(TIL_SOURCE_VOLUME_PATHS)} volume(s)")

# Resolve target pdf rows. When TIL_P1_TARGET_PDF_NAMES is set, use
# pick_pdf_row_by_name (strict case-insensitive substring match on file_name).
# Otherwise, treat every discovered PDF as its own request.

pdf_rows_to_process: list[dict[str, Any]] = []
unresolved_requests: list[dict[str, str]] = []

if P1_TARGET_PDF_NAMES:
    for requested in P1_TARGET_PDF_NAMES:
        requested_clean = clean_text(requested)
        if not requested_clean:
            continue
        matched, error = pick_pdf_row_by_name(requested_clean, catalog)
        if matched is None:
            log.warning(f"Skipping target '{requested_clean}': {error}")
            unresolved_requests.append({"target": requested_clean, "error": error or "no_match"})
            continue
        # pick_pdf_row_by_name sets requested_pdf_name; keep an alias on
        # requested_til_number so downstream output uses a single column.
        matched.setdefault("requested_til_number", matched.get("til_number"))
        pdf_rows_to_process.append(matched)
else:
    for row in catalog:
        enriched = dict(row)
        enriched.setdefault("requested_til_number", row.get("til_number"))
        enriched.setdefault("match_type", "exact_til_number")
        pdf_rows_to_process.append(enriched)

if P1_MAX_PDFS:
    pdf_rows_to_process = pdf_rows_to_process[:P1_MAX_PDFS]

if P1_TARGET_PDF_NAMES and P1_MAX_PDFS and len(P1_TARGET_PDF_NAMES) > P1_MAX_PDFS:
    raise ValueError(
        f"TIL_P1_MAX_PDFS={P1_MAX_PDFS} would cap a targeted batch of {len(P1_TARGET_PDF_NAMES)} PDFs. "
        "Leave TIL_P1_MAX_PDFS blank for the full DS batch."
    )

til_count = len(pdf_rows_to_process)
log.info(f"Selected {til_count} TILs to process (unresolved requests: {len(unresolved_requests)})")

if til_count == 0 and not unresolved_requests:
    log.warning("No TILs matched criteria. Exiting.")
    dbutils.notebook.exit("No matching TILs")

# COMMAND ----------

# ── Process each TIL ──────────────────────────────────────────────────────

# Load existing metadata for incremental detection
existing_metadata_lookup: dict[str, dict[str, Any]] = {}
if spark.catalog.tableExists(TIL_METADATA_TABLE):
    try:
        table_df = spark.table(TIL_METADATA_TABLE)
        table_columns = set(table_df.columns)
        
        # Check which incremental columns are available in the table
        has_pdf_file_hash = "pdf_file_hash" in table_columns
        has_content_hash = "content_hash" in table_columns
        
        # Build select list based on available columns
        select_cols = ["matched_til_number", "parsed_profile_json", "extraction_confidence", 
                       "metadata_status", "parser_name", "parser_version"]
        if has_pdf_file_hash:
            select_cols.insert(1, "pdf_file_hash")
        if has_content_hash:
            select_cols.insert(1, "content_hash")
        
        existing_df = table_df.select(*select_cols)
        for row in existing_df.collect():
            til_num = row["matched_til_number"]
            if til_num:
                existing_metadata_lookup[til_num] = {
                    "pdf_file_hash": row.get("pdf_file_hash") if has_pdf_file_hash else None,
                    "content_hash": row.get("content_hash") if has_content_hash else None,
                    "parsed_profile_json": row["parsed_profile_json"],
                    "extraction_confidence": row["extraction_confidence"],
                    "metadata_status": row["metadata_status"],
                    "parser_name": row["parser_name"],
                    "parser_version": row["parser_version"],
                }
        log.info(f"Loaded {len(existing_metadata_lookup)} existing metadata records for incremental detection "
                 f"(has_pdf_file_hash={has_pdf_file_hash}, has_content_hash={has_content_hash})")
    except Exception as e:
        log.warning(f"Could not load existing metadata for incremental detection: {e}")
        existing_metadata_lookup = {}

results: list[dict[str, Any]] = []
status_tracker: dict[str, str] = {
    row["matched_til_number"] if "matched_til_number" in row else row["til_number"]: "pending"
    for row in pdf_rows_to_process
}
log.info(f"Initialized status as pending for {len(status_tracker)} TILs")

incremental_skipped = 0

for i, pdf_row in enumerate(pdf_rows_to_process):
    matched_til_number = pdf_row.get("til_number") or pdf_row.get("matched_til_number") or ""
    requested_til_number = pdf_row.get("requested_til_number") or matched_til_number
    pdf_path = pdf_row.get("pdf_path") or ""
    status_tracker[matched_til_number] = "processing"

    log.info(f"[{i+1}/{til_count}] {matched_til_number} (requested={requested_til_number}): pending -> processing")

    try:
        with open(pdf_path, "rb") as fh:
            pdf_bytes = fh.read()
        
        # Compute PDF file hash for incremental detection
        pdf_file_hash = hashlib.md5(pdf_bytes).hexdigest() if pdf_bytes else None
        
        # Check if this PDF has been processed before with same content
        # Skip incremental detection if FORCE_REPROCESS is enabled
        existing = existing_metadata_lookup.get(matched_til_number)
        if not FORCE_REPROCESS and existing and existing.get("pdf_file_hash") == pdf_file_hash:
            # PDF unchanged: reuse existing metadata, skip parsing + LLM
            incremental_skipped += 1
            log.info(f"  → PDF unchanged (hash match). Skipping extraction, reusing existing metadata.")
            result = {
                "requested_til_number": requested_til_number,
                "matched_til_number": matched_til_number,
                "match_type": pdf_row.get("match_type", "exact_til_number"),
                "source_path": pdf_path,
                "source_system": pdf_row.get("source", "databricks_volume"),
                "source_hash": None,
                "pdf_file_hash": pdf_file_hash,
                "parsed_profile": json.loads(existing["parsed_profile_json"]) if existing["parsed_profile_json"] else None,
                "raw_profile": None,
                "extracted_text_char_count": 0,
                "extracted_table_count": 0,
                "extracted_document_method": "incremental_reuse",
                "parser_method": existing.get("parser_name", "unknown"),
                "parser_name": existing.get("parser_name"),
                "parser_version": existing.get("parser_version"),
                "extraction_confidence": existing.get("extraction_confidence", 0.0),
                "latency_s": 0.0,
                "metadata_status": "completed_incremental_skip",
                "error_message": None,
                "run_id": P1_RUN_ID,
                "elements": [],

                "parser_raw_element_count": 0,
                "profile_scope_count": 0,
                "profile_reco_count": 0,
                "profile_parts_count": 0,
                "profile_snippets_count": 0,
            }
            status_tracker[matched_til_number] = "completed"
            results.append(result)
        else:
            # PDF is new or changed: proceed with normal extraction
            result = extract_til_profile(pdf_bytes, pdf_row)
            status_tracker[matched_til_number] = result["metadata_status"]
            results.append(result)

            status = result["metadata_status"]
            if status == "completed":
                log.info(
                    f"{matched_til_number}: processing -> completed "
                    f"(confidence: {result['extraction_confidence']:.2f}, latency: {result['latency_s']:.1f}s)"
                )
            else:
                log.warning(f"{matched_til_number}: processing -> {status} ({result.get('error_message')})")

    except Exception as exc:
        log.error(f"Failed to process {matched_til_number}: {exc}")
        status_tracker[matched_til_number] = "failed"
        results.append({
            "requested_til_number": requested_til_number,
            "matched_til_number": matched_til_number,
            "match_type": pdf_row.get("match_type", "exact_til_number"),
            "source_path": pdf_path,
            "source_system": pdf_row.get("source", "databricks_volume"),
            "source_hash": None,
            "pdf_file_hash": None,
            "parsed_profile": None,
            "raw_profile": None,
            "extracted_text_char_count": 0,
            "extracted_table_count": 0,
            "extracted_document_method": "databricks_ai",
            "parser_method": "databricks_ai",
            "parser_name": TIL_PARSER.name,
            "parser_version": TIL_PARSER.version,
            "extraction_confidence": 0.0,
            "latency_s": 0.0,
            "metadata_status": "failed",
            "error_message": str(exc),
            "run_id": P1_RUN_ID,
            "elements": [],
        })

log.info(f"Processing complete: {til_count} TILs, {incremental_skipped} skipped via incremental detection")

# Record pdf_not_found entries for requested PDF names that had no catalog
# match or were ambiguous (matched >1 file). Surfacing them as audit rows
# avoids silent drops when filenames or substrings drift.
for entry in unresolved_requests:
    results.append({
        "requested_til_number": entry["target"],
        "matched_til_number": None,
        "match_type": None,
        "source_path": None,
        "source_system": None,
        "source_hash": None,
        "pdf_file_hash": None,
        "parsed_profile": None,
        "raw_profile": None,
        "extracted_text_char_count": 0,
        "extracted_table_count": 0,
        "extracted_document_method": None,
        "parser_method": None,
        "parser_name": None,
        "parser_version": None,
        "extraction_confidence": 0.0,
        "latency_s": 0.0,
        "metadata_status": "pdf_not_found",
        "error_message": entry["error"],
        "run_id": P1_RUN_ID,
        "elements": [],
    })

# COMMAND ----------

# ── Write results to Delta table ───────────────────────────────────────────

selected_raw_responses = [
    {
        "matched_til_number": result["matched_til_number"],
        "requested_til_number": result["requested_til_number"],
        "status": result["metadata_status"],
        "confidence": result["extraction_confidence"],
        "raw_profile": result.get("raw_profile"),
    }
    for result in results
    if result.get("raw_profile")
    and (
        result.get("metadata_status") != "completed"
        or result.get("extraction_confidence", 0.0) < TIL_LOW_CONFIDENCE_THRESHOLD
    )
]

# Build DDL-aligned output rows.
output_rows = []
for result in results:
    parsed_profile = result.get("parsed_profile")
    requested = result.get("requested_til_number")
    matched = result.get("matched_til_number")
    src_path = result.get("source_path")
    src_hash = result.get("source_hash")
    # Mirrors FSR: document_id is the deterministic PDF stem (lower-cased)
    # when we have a matched PDF; falls back to the requested TIL number
    # for pdf_not_found / ambiguous-match audit rows.
    document_id = (
        Path(src_path).stem.lower() if src_path else (requested or "unknown").lower()
    )
    # unique_key per DDL: til_number + source_hash + stable attrs.
    unique_key = f"{matched or requested or 'unknown'}__{src_hash or 'no_hash'}"
    # Compute content_hash on parsed profile for incremental detection
    content_hash = None
    if parsed_profile:
        profile_json = json.dumps(parsed_profile, default=str, sort_keys=True)
        content_hash = hashlib.md5(profile_json.encode()).hexdigest()
    
    row = {
        "document_id": document_id,
        "unique_key": unique_key,
        "requested_til_number": requested,
        "matched_til_number": matched,
        "match_type": result.get("match_type"),
        "source_path": src_path,
        "source_hash": src_hash,
        "pdf_file_hash": result.get("pdf_file_hash"),
        "source_system": result.get("source_system"),
        "parser_method": result.get("parser_method"),
        "parser_name": result.get("parser_name"),
        "parser_version": result.get("parser_version"),
        "parsed_profile_json": json.dumps(parsed_profile, default=str) if parsed_profile else None,
        "raw_profile_json": result.get("raw_profile"),
        "profile_found": bool(parsed_profile),
        "content_hash": content_hash,
        "extracted_document_method": result.get("extracted_document_method"),
        "extracted_text_char_count": int(result.get("extracted_text_char_count") or 0),
        "extracted_table_count": int(result.get("extracted_table_count") or 0),
        "extraction_confidence": float(result.get("extraction_confidence") or 0.0),
        "metadata_status": result.get("metadata_status") or "failed",
        "error_message": result.get("error_message"),
        "llm_model": LLM_MODEL,
        "metadata_processed_ts": datetime.now(timezone.utc).isoformat(),
        "run_id": result.get("run_id") or P1_RUN_ID,

    }
    output_rows.append(row)

# Explicit schema so Spark does not have to infer types from rows whose
# optional columns (source_hash, parsed_profile_json, error_message, ...) may
# all be None on a failure-only run.
output_schema = StructType([
    StructField("document_id", StringType(), False),
    StructField("unique_key", StringType(), False),
    StructField("requested_til_number", StringType(), True),
    StructField("matched_til_number", StringType(), True),
    StructField("match_type", StringType(), True),
    StructField("source_path", StringType(), True),
    StructField("source_hash", StringType(), True),
    StructField("pdf_file_hash", StringType(), True),
    StructField("source_system", StringType(), True),
    StructField("parser_method", StringType(), True),
    StructField("parser_name", StringType(), True),
    StructField("parser_version", StringType(), True),
    StructField("parsed_profile_json", StringType(), True),
    StructField("raw_profile_json", StringType(), True),
    StructField("profile_found", BooleanType(), True),
    StructField("content_hash", StringType(), True),
    StructField("extracted_document_method", StringType(), True),
    StructField("extracted_text_char_count", LongType(), True),
    StructField("extracted_table_count", IntegerType(), True),
    StructField("extraction_confidence", DoubleType(), True),
    StructField("metadata_status", StringType(), True),
    StructField("error_message", StringType(), True),
    StructField("llm_model", StringType(), True),
    StructField("metadata_processed_ts", StringType(), True),
    StructField("run_id", StringType(), True),
])

output_df = spark.createDataFrame(output_rows, schema=output_schema)
output_df = output_df.withColumn("metadata_processed_ts", current_timestamp())

# Merge on matched_til_number (business key: one row per til_number).
# Content_hash enables incremental detection: if hash matches, extraction is unchanged.
merge_condition = "t.matched_til_number = s.matched_til_number"
update_columns = {
    "requested_til_number": "s.requested_til_number",
    "matched_til_number": "s.matched_til_number",
    "match_type": "s.match_type",
    "source_path": "s.source_path",
    "source_hash": "s.source_hash",
    "pdf_file_hash": "s.pdf_file_hash",
    "source_system": "s.source_system",
    "parser_method": "s.parser_method",
    "parser_name": "s.parser_name",
    "parser_version": "s.parser_version",
    "parsed_profile_json": "s.parsed_profile_json",
    "raw_profile_json": "s.raw_profile_json",
    "profile_found": "s.profile_found",
    "content_hash": "s.content_hash",
    "extracted_document_method": "s.extracted_document_method",
    "extracted_text_char_count": "s.extracted_text_char_count",
    "extracted_table_count": "s.extracted_table_count",
    "extraction_confidence": "s.extraction_confidence",
    "metadata_status": "s.metadata_status",
    "error_message": "s.error_message",
    "llm_model": "s.llm_model",
    "metadata_processed_ts": "s.metadata_processed_ts",
    "run_id": "s.run_id",

}
insert_columns = {
    "document_id": "s.document_id",
    "unique_key": "s.unique_key",
    **update_columns,
}

if spark.catalog.tableExists(TIL_METADATA_TABLE):
    write_mode = "merge"
    target_table = DeltaTable.forName(spark, TIL_METADATA_TABLE)
    (
        target_table.alias("t")
        .merge(output_df.alias("s"), merge_condition)
        .whenMatchedUpdate(
            condition="t.content_hash != s.content_hash OR t.content_hash IS NULL",
            set=update_columns
        )
        .whenNotMatchedInsert(values=insert_columns)
        .execute()
    )
else:
    write_mode = "create"
    (
        output_df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(TIL_METADATA_TABLE)
    )

log.info(f"Profiles persisted | mode={write_mode} | table={TIL_METADATA_TABLE} | rows={len(results)}")

# ── Write element-level trace rows ─────────────────────────────────────────

element_rows = [
    element
    for result in results
    for element in (result.get("elements") or [])
]

if element_rows:
    elements_schema = StructType([
        StructField("document_id", StringType(), False),
        StructField("element_id", StringType(), False),
        StructField("element_type", StringType(), True),
        StructField("element_text", StringType(), True),
        StructField("page_number", IntegerType(), True),
        StructField("bbox_json", StringType(), True),
        StructField("section_path", StringType(), True),
        StructField("source_method", StringType(), True),
        StructField("parser_version", StringType(), True),
        StructField("run_id", StringType(), True),
    ])

    elements_df = spark.createDataFrame(element_rows, schema=elements_schema)
    element_merge_condition = "t.document_id = s.document_id AND t.element_id = s.element_id"
    element_update_columns = {
        "element_type": "s.element_type",
        "element_text": "s.element_text",
        "page_number": "s.page_number",
        "bbox_json": "s.bbox_json",
        "section_path": "s.section_path",
        "source_method": "s.source_method",
        "parser_version": "s.parser_version",
        "run_id": "s.run_id",
    }
    element_insert_columns = {
        "document_id": "s.document_id",
        "element_id": "s.element_id",
        **element_update_columns,
    }

    if spark.catalog.tableExists(TIL_ELEMENTS_TABLE):
        (
            DeltaTable.forName(spark, TIL_ELEMENTS_TABLE)
            .alias("t")
            .merge(elements_df.alias("s"), element_merge_condition)
            .whenMatchedUpdate(set=element_update_columns)
            .whenNotMatchedInsert(values=element_insert_columns)
            .execute()
        )
        log.info(f"Elements persisted | mode=merge | table={TIL_ELEMENTS_TABLE} | rows={len(element_rows)}")
    else:
        (
            elements_df.write
            .format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .saveAsTable(TIL_ELEMENTS_TABLE)
        )
        log.info(f"Elements persisted | mode=create | table={TIL_ELEMENTS_TABLE} | rows={len(element_rows)}")
else:
    log.info("No element rows generated in this run.")

success_count = sum(1 for r in results if r["metadata_status"] == "completed")
avg_confidence = sum(r["extraction_confidence"] for r in results) / len(results) if results else 0.0
avg_latency = sum(r["latency_s"] for r in results) / len(results) if results else 0.0
completed_results = [r for r in results if r.get("metadata_status") == "completed"]
avg_scope_items = (
    sum(float(r.get("profile_scope_count") or 0.0) for r in completed_results) / len(completed_results)
    if completed_results
    else 0.0
)
avg_reco_items = (
    sum(float(r.get("profile_reco_count") or 0.0) for r in completed_results) / len(completed_results)
    if completed_results
    else 0.0
)
avg_parts_items = (
    sum(float(r.get("profile_parts_count") or 0.0) for r in completed_results) / len(completed_results)
    if completed_results
    else 0.0
)
avg_snippet_items = (
    sum(float(r.get("profile_snippets_count") or 0.0) for r in completed_results) / len(completed_results)
    if completed_results
    else 0.0
)
avg_parser_raw_elements = (
    sum(float(r.get("parser_raw_element_count") or 0.0) for r in results) / len(results)
    if results
    else 0.0
)

with mlflow.start_run(run_name=f"til_metadata_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}") as run:
    mlflow.log_params(
        {
            "job_name": "PW_SDG_TIL_P1_Metadata",
            "pipeline_run_id": P1_RUN_ID,
            "llm_model": LLM_MODEL,
            "llm_temperature": LLM_TEMPERATURE,
            "llm_max_tokens": LLM_MAX_TOKENS,
            "raw_response_threshold": TIL_LOW_CONFIDENCE_THRESHOLD,
            "metadata_table": TIL_METADATA_TABLE,
        }
    )
    mlflow.log_metrics(
        {
            "documents_processed": float(len(results)),
            "documents_succeeded": float(success_count),
            "documents_failed": float(len(results) - success_count),
            "avg_confidence": float(avg_confidence),
            "avg_latency_s": float(avg_latency),
            "avg_profile_scope_items": float(avg_scope_items),
            "avg_profile_recommendation_items": float(avg_reco_items),
            "avg_profile_parts_referenced": float(avg_parts_items),
            "avg_profile_source_snippets": float(avg_snippet_items),
            "avg_parser_raw_elements": float(avg_parser_raw_elements),
        }
    )
    mlflow.set_tags(
        {
            "pipeline": "til",
            "stage": "process_1_metadata",
            "output_table": TIL_METADATA_TABLE,
        }
    )

    if selected_raw_responses:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as handle:
            for item in selected_raw_responses:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            raw_response_artifact = handle.name
        mlflow.log_artifact(raw_response_artifact, artifact_path="raw_responses")

# COMMAND ----------

# ── Summary ──────────────────────────────────────────────────────────────

log.info("=== Process 1 Complete ===")
log.info(f"  Total processed: {len(results)}")
log.info(f"  Successful: {success_count}/{len(results)} ({100*success_count/max(len(results),1):.0f}%)")
log.info(f"  Avg confidence: {avg_confidence:.2f}")
log.info(f"  Avg latency: {avg_latency:.1f}s")
log.info(f"  Total time: {sum(r['latency_s'] for r in results):.1f}s")
log.info(f"  Status counts  : {dict((s, list(status_tracker.values()).count(s)) for s in set(status_tracker.values()))}")

# Display summary
display(spark.sql(
    f"SELECT requested_til_number, matched_til_number, match_type, "
    f"extraction_confidence, metadata_status, llm_model, error_message "
    f"FROM {TIL_METADATA_TABLE} ORDER BY metadata_processed_ts DESC LIMIT 30"
))
