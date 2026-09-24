from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
import urllib3

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from code_assets.runtime.config import get_db_connection
from code_assets.runtime.fsr_completion import default_completion_review, default_prior_service_evidence
from code_assets.runtime.service_history_completion import (
    default_service_history_completion_result,
    run_service_history_completion_service,
)
from code_assets.runtime.template_coverage import (
    default_template_coverage_result,
    evaluate_information_only,
    run_template_coverage_service,
)
from code_assets.runtime.llm import call_llm, parse_llm_response
from code_assets.experiments.step6.sbom_lookup import build_sbom_context


EVENT_MASTER_TABLE = "vgpd.fsr_std_views.eventmgmt_event_vision_sot"
EVENT_EQUIPMENT_TABLE = "vgpd.fsr_std_views.event_equipment_dtls_event_vision_sot"
IBAT_EQUIPMENT_TABLE = "vgpd.prm_std_views.IBAT_EQUIPMENT_MST"
TIL_PDF_FALLBACK_TABLE = "vgpd.qlt_std_views.u_til_pdf"
TIL_EQUIPMENT_METADATA_TABLE = "vgpd.qlt_std_views.u_til_equipment"
DEFAULT_CANDIDATE_DIR = PROJECT_ROOT / "docs" / "experiments" / "step6" / "gt_candidate_pool"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "experiments" / "step6" / "applicability"
DEFAULT_TIL_PROFILE_DIR = PROJECT_ROOT / "docs" / "experiments" / "step6" / "til_profile_pilot"
LOCAL_TIL_SAMPLE_DIR = PROJECT_ROOT / "context" / "data" / "workspace_notes" / "samples" / "TILs"
DEFAULT_PROMPT_PACK = "til_applicability_structured_v2026-05-28a"
DEFAULT_TIL_CONTEXT_MODE = "full_document"
DEFAULT_TIL_DOCUMENT_METHOD = os.getenv("STEP6_TIL_DOCUMENT_METHOD", "auto")
QUERY_CHUNK_SIZE = 200
DEFAULT_TIL_TEXT_MAX_CHARS = 6000
DEFAULT_PRIOR_SERVICE_RETRIEVAL_DEPTH_HINT = 10
EXCEL_ILLEGAL_CHAR_RE = re.compile(r"[\x00-\x08\x0B-\x0C\x0E-\x1F]")
FOUNDATION_URL = os.getenv(
    "TIL_FOUNDATION_URL",
    "https://dev-genai-foundation.apps.gevernova.net/pdf/extract/",
)
FOUNDATION_PROJECT_ID = os.getenv(
    "TIL_FOUNDATION_PROJECT_ID",
    "9f3cbb78-48a9-45cc-a1f2-52c6d02b58a3",
)
FOUNDATION_PROCESS_MODE = os.getenv("TIL_FOUNDATION_PROCESS_MODE", "accuracy")
FOUNDATION_MODE = os.getenv("TIL_FOUNDATION_MODE", "asynchronous")
USAGE_COUNTERS_FIELD = "usage_counters_to_check_or_consider"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROMPT_PACK_INSTRUCTIONS = {
    "til_applicability_structured_v2026-05-28a": {
        "system_intro": (
            "You are evaluating Step 6 TIL applicability for outage scoping. "
            "Use only the supplied case payload, structured lineage, and any document-derived enrichment included in that payload. "
            "Do not invent missing facts."
        ),
        "user_intro": "Step 6 TIL applicability evaluation.",
    },
    "til_applicability_structured_v2026-06-01a": {
        "system_intro": (
            "You are evaluating Step 6 TIL applicability for outage scoping. "
            "Use only the supplied case payload, structured lineage, and any document-derived enrichment included in that payload. "
            "Do not invent missing facts. Explicitly weigh outage type and TIL-recommended line items when they are present."
        ),
        "user_intro": "Step 6 TIL applicability evaluation.",
    },
}


PROMPT_GUIDANCE = (
    "Applicability rules:\n"
    "- Use only the supplied case payload. Do not invent missing facts.\n"
    "- Treat applicable_to, affected_units_technology, unit frame, unit combustion, and TIL enrichment as structured signals, not absolute truth when they disagree.\n"
    "- Treat outage type as part of the applicability context when the payload provides it; explain when outage timing or outage type changes the answer.\n"
    "- Treat TIL line items such as recommended inspections, repairs, replacements, and WBS-style activities as high-value evidence for applicability and prior-completion reasoning.\n"
    "- If template_coverage is supplied, treat template-covered items as context only and focus applicability reasoning on the gap or net-new line items.\n"
    "- If prior_service_evidence is supplied, use it to reason about prior completion, deferral, recurrence, and contradictions with disposition_status and disposition_notes. Do not collapse that evidence into a hard yes/no rule unless the evidence is explicit.\n"
    "- Treat disposition_status as a useful structured hint, not definitive truth. Treat detailed disposition_notes as stronger context than the status label alone when the notes describe what was completed, deferred, or left open.\n"
    "- If completion_review is supplied, treat it as a synthesized judgment over the retrieved prior_service_evidence. Weigh its status and applicability_impact alongside recurring indicators, intervals, and trigger language from the TIL profile.\n"
    "- If prior_service_evidence is unavailable or ambiguous, say so explicitly in missing_information_needed and suggested_next_checks instead of assuming completion.\n"
    "- If a TIL PDF excerpt is supplied, use that document language to reason about scope, recurrence, applicability, and timing.\n"
    "- If sbom_context is supplied, treat it as unit-configuration evidence only. A positive SBOM match strengthens applicability support, but no SBOM match is not sufficient by itself to mark the TIL not_applicable.\n"
    "- A candidate can still be relevant when from_serial_match is N if it came from outage context on another serial in the same project; note that as context-only support, not direct unit proof.\n"
    "- If the evidence supports the TIL in principle but there is unresolved unit configuration or completion uncertainty, use conditionally_applicable or insufficient_information rather than overcommitting.\n"
    "- Keep evidence_snippets short and grounded in supplied fields only.\n"
)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def excel_safe_text(value: object) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, indent=2)
    else:
        text = clean_text(value)
    text = EXCEL_ILLEGAL_CHAR_RE.sub("", text)
    return text[:32767]


def excel_safe_cell_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (str, Path, dict, list)):
        return excel_safe_text(value)
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value


def sanitize_excel_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    sanitized = frame.copy()
    for column_name in sanitized.columns:
        sanitized[column_name] = sanitized[column_name].map(excel_safe_cell_value)
    return sanitized


def markdown_safe_text(value: object) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, indent=2, default=str)
    else:
        text = clean_text(value)
    text = EXCEL_ILLEGAL_CHAR_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("|", "\\|").replace("\n", "<br>")


def markdown_companion_path(path: Path) -> Path:
    return path.with_suffix(".md")


def render_markdown_table(rows: list[dict[str, Any]], columns: list[str], headers: list[str] | None = None) -> str:
    if not rows:
        return "_No rows._\n"

    labels = headers or columns
    table_lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        table_lines.append(
            "| " + " | ".join(markdown_safe_text(row.get(column, "")) for column in columns) + " |"
        )
    return "\n".join(table_lines) + "\n"


def render_markdown_bullets(value: object) -> str:
    items = parse_list_value(value)
    if not items:
        return "_None_"
    return "\n".join(f"- {markdown_safe_text(item)}" for item in items)


def render_markdown_json_block(value: object) -> str:
    return "```json\n" + json.dumps(value, indent=2, default=str) + "\n```"


def case_markdown_label(row: dict[str, Any]) -> str:
    event_id = clean_text(row.get("matched_event_id")) or "unknown_event"
    esn = clean_text(row.get("matched_esn")) or "unknown_esn"
    til_num = clean_text(row.get("candidate_til_num")) or "unknown_til"
    return f"{event_id} / {esn} / {til_num}"


def write_run_payload_markdown(run_payload_md_path: Path, run_payload: dict[str, Any]) -> None:
    metric_rows = [{"metric": key, "value": value} for key, value in run_payload.items()]
    lines = [
        "# Run Payload",
        "",
        "## Metrics",
        "",
        render_markdown_table(metric_rows, ["metric", "value"], ["Metric", "Value"]).rstrip(),
        "",
    ]
    run_payload_md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_summary_markdown(summary_md_path: Path, run_payload: dict[str, Any], summary_df: pd.DataFrame) -> None:
    summary_rows = summary_df.to_dict(orient="records") if not summary_df.empty else []
    overview_columns = [
        "matched_event_id",
        "matched_esn",
        "candidate_til_num",
        "pipeline_disposition",
        "llm_recommendation",
        "til_context_availability",
        "template_coverage_class",
        "completion_review_status",
        "confidence",
    ]
    overview_headers = [
        "Event",
        "ESN",
        "TIL",
        "Pipeline",
        "LLM",
        "TIL Context",
        "Template Coverage",
        "Completion Review",
        "Confidence",
    ]
    lines = [
        "# Case Summary",
        "",
        f"Generated at: {markdown_safe_text(run_payload.get('generated_at_utc', ''))}",
        "",
        "## Run Metrics",
        "",
        render_markdown_table(
            [{"metric": key, "value": value} for key, value in summarize_results(summary_df).items()],
            ["metric", "value"],
            ["Metric", "Value"],
        ).rstrip(),
        "",
        "## Overview",
        "",
        render_markdown_table(summary_rows, overview_columns, overview_headers).rstrip(),
    ]

    if summary_rows:
        lines.extend(["", "## Case Notes", ""])
    for row in summary_rows:
        lines.extend(
            [
                f"### {case_markdown_label(row)}",
                "",
                f"- Pipeline disposition: {markdown_safe_text(row.get('pipeline_disposition'))}",
                f"- LLM recommendation: {markdown_safe_text(row.get('llm_recommendation'))}",
                f"- TIL context availability: {markdown_safe_text(row.get('til_context_availability'))}",
                f"- Template coverage: {markdown_safe_text(row.get('template_coverage_class'))} ({markdown_safe_text(row.get('template_coverage_status'))})",
                f"- Completion review: {markdown_safe_text(row.get('completion_review_status'))} / {markdown_safe_text(row.get('completion_review_overall_completion_status'))}",
                f"- Confidence: {markdown_safe_text(row.get('confidence'))}",
                "",
                "Reasoning summary:",
                markdown_safe_text(row.get("reasoning_summary")) or "_None_",
                "",
                "Missing information needed:",
                render_markdown_bullets(row.get("missing_information_needed")),
                "",
                "Suggested next checks:",
                render_markdown_bullets(row.get("suggested_next_checks")),
                "",
            ]
        )

    summary_md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_line_items_markdown(line_items_md_path: Path, line_item_df: pd.DataFrame) -> None:
    rows = line_item_df.to_dict(orient="records") if not line_item_df.empty else []
    lines = ["# Completion Line Items", ""]
    if not rows:
        lines.append("_No completion line item rows._")
        line_items_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            clean_text(row.get("matched_event_id")),
            clean_text(row.get("matched_esn")),
            clean_text(row.get("candidate_til_num")),
        )
        grouped.setdefault(key, []).append(row)

    for key, item_rows in grouped.items():
        lines.extend([f"## {key[0]} / {key[1]} / {key[2]}", ""])
        for item in item_rows:
            lines.extend(
                [
                    f"- [{markdown_safe_text(item.get('line_item_status'))} / {markdown_safe_text(item.get('due_again_status'))}] {markdown_safe_text(item.get('line_item_text'))}",
                    f"  Rationale: {markdown_safe_text(item.get('rationale')) or '_None_'}",
                    f"  Missing data: {render_markdown_bullets(item.get('missing_data_needed'))}",
                ]
            )
        lines.append("")

    line_items_md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_template_line_items_markdown(template_line_items_md_path: Path, template_line_item_df: pd.DataFrame) -> None:
    rows = template_line_item_df.to_dict(orient="records") if not template_line_item_df.empty else []
    lines = ["# Template Line Items", ""]
    if not rows:
        lines.append("_No template line item rows._")
        template_line_items_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            clean_text(row.get("matched_event_id")),
            clean_text(row.get("matched_esn")),
            clean_text(row.get("candidate_til_num")),
        )
        grouped.setdefault(key, []).append(row)

    for key, item_rows in grouped.items():
        lines.extend([f"## {key[0]} / {key[1]} / {key[2]}", ""])
        for status in ["covered", "gap", "unclear"]:
            matching_rows = [row for row in item_rows if clean_text(row.get("template_match_status")) == status]
            lines.extend([f"### {status.title()} Items", ""])
            if not matching_rows:
                lines.append("_None_")
            else:
                for item in matching_rows:
                    lines.append(f"- {markdown_safe_text(item.get('til_line_item_text'))}")
            lines.append("")

    template_line_items_md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_context_payload_markdown(context_payload_md_path: Path, prompt_payload_rows: list[dict[str, Any]]) -> None:
    lines = ["# Context Payloads", ""]
    if not prompt_payload_rows:
        lines.append("_No prompt payload rows._")
        context_payload_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    for row in prompt_payload_rows:
        lines.extend(
            [
                f"## {case_markdown_label(row)}",
                "",
                render_markdown_json_block(row.get("prompt_payload", {})),
                "",
            ]
        )

    context_payload_md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_template_coverage_markdown(
    template_coverage_md_path: Path,
    template_coverage_rows: list[dict[str, Any]],
) -> None:
    lines = ["# Template Coverage Records", ""]
    if not template_coverage_rows:
        lines.append("_No template coverage rows._")
        template_coverage_md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    for row in template_coverage_rows:
        result = row.get("template_coverage_result", {}) if isinstance(row.get("template_coverage_result"), dict) else {}
        lines.extend(
            [
                f"## {case_markdown_label(row)}",
                "",
                f"- Final disposition: {markdown_safe_text(row.get('final_disposition'))}",
                f"- Coverage status: {markdown_safe_text(result.get('status'))}",
                f"- Coverage class: {markdown_safe_text(result.get('template_coverage_class'))}",
                f"- Coverage confidence: {markdown_safe_text(result.get('template_coverage_confidence'))}",
                f"- Matched template: {markdown_safe_text(result.get('matched_template_code'))} / {markdown_safe_text(result.get('matched_template_display_name'))}",
                "",
                "Covered line items:",
                render_markdown_bullets(result.get("covered_til_line_items")),
                "",
                "Gap line items:",
                render_markdown_bullets(result.get("gap_til_line_items")),
                "",
                "Unclear line items:",
                render_markdown_bullets(result.get("unclear_til_line_items")),
                "",
                "Overlap reasoning:",
                markdown_safe_text(result.get("template_overlap_reasoning")) or "_None_",
                "",
                "Template coverage result:",
                render_markdown_json_block(result),
                "",
            ]
        )

    template_coverage_md_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def write_markdown_artifacts(
    *,
    run_payload_md_path: Path,
    summary_md_path: Path,
    line_items_md_path: Path,
    template_line_items_md_path: Path,
    context_payload_md_path: Path,
    template_coverage_md_path: Path,
    run_payload: dict[str, Any],
    summary_df: pd.DataFrame,
    line_item_df: pd.DataFrame,
    template_line_item_df: pd.DataFrame,
    prompt_payload_rows: list[dict[str, Any]],
    template_coverage_rows: list[dict[str, Any]],
) -> None:
    write_run_payload_markdown(run_payload_md_path, run_payload)
    write_summary_markdown(summary_md_path, run_payload, summary_df)
    write_line_items_markdown(line_items_md_path, line_item_df)
    write_template_line_items_markdown(template_line_items_md_path, template_line_item_df)
    write_context_payload_markdown(context_payload_md_path, prompt_payload_rows)
    write_template_coverage_markdown(template_coverage_md_path, template_coverage_rows)


def sql_quote(value: str) -> str:
    return "'" + clean_text(value).replace("'", "''") + "'"


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def normalize_string(value: object) -> str:
    return clean_text(value).upper()


def normalize_til_key(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", clean_text(value).upper())


def call_til_foundation_service(pdf_bytes: bytes, pdf_filename: str) -> dict[str, Any]:
    response = requests.post(
        FOUNDATION_URL,
        data={
            "project_id": FOUNDATION_PROJECT_ID,
            "process_mode": FOUNDATION_PROCESS_MODE,
            "mode": FOUNDATION_MODE,
        },
        files={"file": (pdf_filename, pdf_bytes, "application/pdf")},
        timeout=300,
        verify=False,
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def extract_til_text_from_foundation_response(response: dict[str, Any], max_chars: int) -> str:
    collected: list[str] = []

    def _visit(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text:
                collected.append(text)
            return
        if isinstance(value, list):
            for item in value:
                _visit(item)
            return
        if isinstance(value, dict):
            for key in ["markdown", "text", "content", "extracted_text", "result"]:
                if key in value:
                    _visit(value.get(key))
            for item in value.values():
                if isinstance(item, (dict, list)):
                    _visit(item)

    _visit(response)
    return "\n\n".join(dict.fromkeys(collected))[:max_chars]


def extract_til_text_with_method(
    *,
    pdf_filename: str,
    local_pdf_path: str,
    local_extract_text_fn,
    method: str,
    max_chars: int,
    pdf_bytes: bytes | None = None,
) -> tuple[str, str, str]:
    selected_method = clean_text(method).lower() or "auto"

    if selected_method in {"auto", "local"}:
        try:
            local_text = clean_text(local_extract_text_fn(local_pdf_path, max_chars=max_chars))
            if local_text:
                return local_text[:max_chars], "", "local"
        except Exception as exc:
            if selected_method == "local":
                return "", clean_text(exc), "local"
            local_error = clean_text(exc)
        else:
            local_error = ""
    else:
        local_error = ""

    if selected_method in {"auto", "foundation"}:
        if not pdf_bytes:
            return "", local_error or "PDF bytes unavailable for foundation extraction.", "foundation"
        try:
            foundation_response = call_til_foundation_service(pdf_bytes, pdf_filename)
            foundation_text = extract_til_text_from_foundation_response(foundation_response, max_chars)
            if foundation_text:
                return foundation_text, "", "foundation"
            return "", local_error or "Foundation extraction returned no text.", "foundation"
        except Exception as exc:
            return "", clean_text(exc) or local_error, "foundation"

    return "", local_error, selected_method


def load_volume_pdf_bytes(volume_pdf_path: str, fs_cli_copy_fn, connect_copy_fn) -> bytes:
    try:
        local_path = fs_cli_copy_fn(volume_pdf_path)
    except Exception:
        local_path = connect_copy_fn(volume_pdf_path)
    return Path(local_path).read_bytes()


def extract_local_sample_til_number(filename: str) -> str:
    text = clean_text(Path(filename).stem).upper()
    explicit_match = re.search(r"TIL\s*(\d+(?:-\d+)?)\s*-?\s*R(\d+)", text)
    if explicit_match:
        return f"{explicit_match.group(1)}-R{explicit_match.group(2)}"

    compact_match = re.fullmatch(r"T(\d+)R(\d+)", re.sub(r"[^A-Z0-9]", "", text))
    if compact_match:
        number = compact_match.group(1)
        revision = compact_match.group(2)
        if len(number) > 4:
            number = number[:4] + "-" + number[4:]
        return f"{number}-R{revision}"
    return ""


def parse_list_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    text = clean_text(value)
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [clean_text(item) for item in parsed if clean_text(item)]
    if "|" in text:
        return [clean_text(item) for item in text.split("|") if clean_text(item)]
    if "," in text:
        return [clean_text(item) for item in text.split(",") if clean_text(item)]
    return [text]


def normalize_usage_counter_field(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(profile or {})
    normalized[USAGE_COUNTERS_FIELD] = parse_list_value(
        normalized.get(USAGE_COUNTERS_FIELD) or normalized.get("usage_counters")
    )
    return normalized


def profile_usage_counters(parsed_profile: dict[str, Any]) -> list[str]:
    return parse_list_value(parsed_profile.get(USAGE_COUNTERS_FIELD))


def profile_text_list(value: object) -> list[str]:
    return parse_list_value(value)


def extract_base_til_num(value: object) -> str:
    text = re.sub(r"^TIL\s*", "", clean_text(value).upper())
    text = re.sub(r"-?R\d+$", "", text)
    match = re.search(r"\d+(?:-\d+)?", text)
    return match.group(0) if match else ""


def parse_revision_number(value: object) -> int:
    match = re.search(r"R(\d+)$", clean_text(value).upper())
    return int(match.group(1)) if match else -1


def join_output_list(value: object) -> str:
    return " | ".join(parse_list_value(value))


def query_rows(sql_text: str) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_text)
            columns = [description[0] for description in cursor.description]
            return [
                {column: row[index] for index, column in enumerate(columns)}
                for row in cursor.fetchall()
            ]


def first_present_value(row: dict[str, Any], candidate_keys: list[str]) -> str:
    lowered = {str(key).lower(): key for key in row.keys()}
    for key in candidate_keys:
        actual_key = lowered.get(key.lower())
        if actual_key is None:
            continue
        value = clean_text(row.get(actual_key))
        if value:
            return value
    return ""


def build_powernow_til_metadata_lookup(case_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    candidate_tils = sorted({clean_text(value) for value in case_df["candidate_til_num"].tolist() if clean_text(value)})
    if not candidate_tils:
        return {}

    base_numbers = sorted({extract_base_til_num(value) for value in candidate_tils if extract_base_til_num(value)})
    if not base_numbers:
        return {}

    rows: list[dict[str, Any]] = []
    for chunk in chunked(base_numbers, QUERY_CHUNK_SIZE):
        quoted_bases = ", ".join(sql_quote(value) for value in chunk)
        sql_text = f"""
        SELECT *
        FROM {TIL_EQUIPMENT_METADATA_TABLE}
        WHERE REGEXP_EXTRACT(UPPER(TRIM(CAST(til_num AS STRING))), '(\\d+)', 1) IN ({quoted_bases})
        """
        try:
            rows.extend(query_rows(sql_text))
        except Exception:
            return {}

    catalog: list[dict[str, Any]] = []
    for row in rows:
        til_number = first_present_value(row, ["til_num", "til_number"])
        if not til_number:
            continue
        catalog.append(
            {
                **row,
                "til_number": til_number,
                "normalized_til_key": normalize_til_key(til_number),
                "base_til_num": extract_base_til_num(til_number),
                "revision_number": parse_revision_number(til_number),
            }
        )

    lookup: dict[str, dict[str, Any]] = {}
    for candidate_til in candidate_tils:
        normalized_candidate = normalize_til_key(candidate_til)
        base_candidate = extract_base_til_num(candidate_til)
        exact_matches = [row for row in catalog if row["normalized_til_key"] == normalized_candidate]
        base_matches = [row for row in catalog if row["base_til_num"] == base_candidate]
        ranked_matches = exact_matches or sorted(
            base_matches,
            key=lambda row: (row["revision_number"], row["til_number"]),
            reverse=True,
        )
        if not ranked_matches:
            continue

        selected = ranked_matches[0]
        metadata = {
            "powernow_metadata_found": True,
            "matched_til_number": selected["til_number"],
            "match_type": "exact_til_number" if exact_matches else "base_til_latest_revision",
            "title": first_present_value(selected, ["title", "til_title", "til_num_title", "document_title"]),
            "purpose": first_present_value(selected, ["purpose", "til_purpose", "description", "summary"]),
            "coarse_outage_type": first_present_value(selected, ["coarse_outage_type", "timing_code_text", "timing_text", "timing_code"]),
            "recurring_indicator": first_present_value(selected, ["recurring_indicator", "recurring_indicator_if_found", "recurring", "is_recurring"]),
            "compliance_category_code": first_present_value(selected, ["compliance_category_code", "compliance_category", "compliance_code"]),
            "compliance_category_text": first_present_value(selected, ["compliance_category_text", "compliance_category_desc", "compliance_text"]),
            "applicable_to": first_present_value(selected, ["applicable_to"]),
            "affected_units_technology": first_present_value(selected, ["affected_units_technology"]),
            "refresh_date": first_present_value(selected, ["refresh_date"]),
        }
        metadata_summary_parts = [
            metadata.get("title", ""),
            metadata.get("purpose", ""),
            metadata.get("coarse_outage_type", ""),
            metadata.get("recurring_indicator", ""),
            metadata.get("compliance_category_code", ""),
            metadata.get("compliance_category_text", ""),
            metadata.get("applicable_to", ""),
            metadata.get("affected_units_technology", ""),
        ]
        metadata["metadata_summary"] = " | ".join(part for part in metadata_summary_parts if part)
        lookup[normalized_candidate] = metadata

    return lookup


def find_latest_candidate_csv(explicit_path: Optional[Path]) -> Path:
    if explicit_path is not None:
        resolved = explicit_path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Candidate CSV not found: {resolved}")
        return resolved

    def is_full_candidate_pool_csv(path: Path) -> bool:
        name = path.name.lower()
        if not name.startswith("gt_til_candidate_pool") or not name.endswith(".csv"):
            return False
        if name.endswith("_filtered_out.csv"):
            return False
        if "top25_overlap" in name or "top25_unique" in name:
            return False
        return True

    candidates = sorted(
        [
            path
            for path in DEFAULT_CANDIDATE_DIR.glob("gt_til_candidate_pool*.csv")
            if is_full_candidate_pool_csv(path)
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"No candidate pool CSV found under {DEFAULT_CANDIDATE_DIR}")
    return candidates[0]


def load_candidate_cases(path: Path, limit: Optional[int]) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str).fillna("")
    if "candidate_removed_by_filter" in frame.columns:
        frame = frame.loc[frame["candidate_removed_by_filter"].isin(["", "N"])].copy()
    if limit is not None:
        frame = frame.head(limit).copy()
    return frame.reset_index(drop=True)


def fetch_ev_lookup(case_df: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    event_ids = sorted({clean_text(value) for value in case_df["matched_event_id"].tolist() if clean_text(value)})
    if not event_ids:
        return {}

    rows: list[dict[str, Any]] = []
    for chunk in chunked(event_ids, QUERY_CHUNK_SIZE):
        quoted_ids = ", ".join(sql_quote(value) for value in chunk)
        sql_text = f"""
        SELECT
            CAST(eq.ev_equipment_event_id AS STRING) AS matched_event_id,
            UPPER(TRIM(CAST(eq.ev_serial_number AS STRING))) AS matched_esn,
            CAST(eq.ev_scoping_project_id AS STRING) AS ev_scoping_project_id,
            TRIM(CAST(eq.ev_equipment_code AS STRING)) AS ev_equipment_code,
            TRIM(CAST(eq.ev_frame_type AS STRING)) AS ev_frame_type,
            TRIM(CAST(eq.ev_combustion_system AS STRING)) AS ev_combustion_system,
            TRIM(CAST(eq.ev_fuel_type AS STRING)) AS ev_fuel_type,
            TRIM(CAST(evt.ev_event_type AS STRING)) AS ev_event_type
        FROM {EVENT_EQUIPMENT_TABLE} eq
        LEFT JOIN {EVENT_MASTER_TABLE} evt
          ON evt.ev_equipment_event_id = eq.ev_equipment_event_id
        WHERE CAST(eq.ev_equipment_event_id AS STRING) IN ({quoted_ids})
        """
        rows.extend(query_rows(sql_text))

    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (clean_text(row.get("matched_event_id")), normalize_string(row.get("matched_esn")))
        if key[0] and key[1] and key not in lookup:
            lookup[key] = row
    return lookup


def fetch_ibat_lookup(case_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    esns = sorted({normalize_string(value) for value in case_df["matched_esn"].tolist() if clean_text(value)})
    if not esns:
        return {}

    rows: list[dict[str, Any]] = []
    for chunk in chunked(esns, QUERY_CHUNK_SIZE):
        quoted_esns = ", ".join(sql_quote(value) for value in chunk)
        sql_text = f"""
        SELECT
            UPPER(TRIM(CAST(equip_serial_number AS STRING))) AS matched_esn,
            TRIM(CAST(equipment_code AS STRING)) AS ibat_equipment_code,
            TRIM(CAST(combustion_system AS STRING)) AS ibat_combustion_system,
            TRIM(CAST(primary_fuel AS STRING)) AS primary_fuel,
            TRIM(CAST(secondary_fuel AS STRING)) AS secondary_fuel
        FROM {IBAT_EQUIPMENT_TABLE}
        WHERE UPPER(TRIM(CAST(equip_serial_number AS STRING))) IN ({quoted_esns})
        """
        rows.extend(query_rows(sql_text))

    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        esn = normalize_string(row.get("matched_esn"))
        if esn and esn not in lookup:
            lookup[esn] = row
    return lookup


def build_til_pdf_lookup(
    case_df: pd.DataFrame,
    *,
    include_text: bool,
    extraction_method: str,
) -> dict[str, dict[str, Any]]:
    try:
        from code_assets.experiments.step6.til_pdf_utils import (
            TIL_VOLUME_PATH,
            _copy_volume_pdf_via_databricks_connect,
            _copy_volume_pdf_via_databricks_fs_cli,
            _extract_text_from_pdf_path,
            _list_til_pdfs,
            _til_number_from_filename,
        )
    except Exception:
        return {}

    candidate_tils = sorted({clean_text(value) for value in case_df["candidate_til_num"].tolist() if clean_text(value)})
    if not candidate_tils:
        return {}

    pdf_paths: list[str] = []
    try:
        pdf_paths = _list_til_pdfs(TIL_VOLUME_PATH)
    except Exception:
        pdf_paths = []

    catalog: list[dict[str, Any]] = []
    for pdf_path in pdf_paths:
        filename = Path(pdf_path).name
        til_number = clean_text(_til_number_from_filename(filename))
        if not til_number:
            continue
        catalog.append(
            {
                "pdf_path": pdf_path,
                "filename": filename,
                "til_number": til_number,
                "normalized_til_key": normalize_til_key(til_number),
                "base_til_num": extract_base_til_num(til_number),
                "revision_number": parse_revision_number(til_number),
            }
        )

    lookup: dict[str, dict[str, Any]] = {}
    for candidate_til in candidate_tils:
        normalized_candidate = normalize_til_key(candidate_til)
        base_candidate = extract_base_til_num(candidate_til)
        exact_matches = [row for row in catalog if row["normalized_til_key"] == normalized_candidate]
        base_matches = [row for row in catalog if row["base_til_num"] == base_candidate]
        ranked_matches = exact_matches or sorted(
            base_matches,
            key=lambda row: (row["revision_number"], row["til_number"]),
            reverse=True,
        )
        if not ranked_matches:
            continue

        selected = ranked_matches[0]
        match_type = "exact_til_number" if exact_matches else "base_til_latest_revision"
        text_excerpt = ""
        extraction_error = ""
        extraction_method_used = "skipped"
        if include_text:
            pdf_bytes = None
            try:
                pdf_bytes = load_volume_pdf_bytes(
                    selected["pdf_path"],
                    _copy_volume_pdf_via_databricks_fs_cli,
                    _copy_volume_pdf_via_databricks_connect,
                )
            except Exception as exc:
                if extraction_method == "foundation":
                    extraction_error = clean_text(exc)
            text_excerpt, extraction_error, extraction_method_used = extract_til_text_with_method(
                pdf_filename=selected["filename"],
                local_pdf_path=selected["pdf_path"],
                local_extract_text_fn=_extract_text_from_pdf_path,
                method=extraction_method,
                max_chars=DEFAULT_TIL_TEXT_MAX_CHARS,
                pdf_bytes=pdf_bytes,
            )

        lookup[normalized_candidate] = {
            "document_found": True,
            "document_source": "til_volume",
            "pdf_path": selected["pdf_path"],
            "pdf_filename": selected["filename"],
            "matched_til_number": selected["til_number"],
            "match_type": match_type,
            "text_excerpt": text_excerpt,
            "text_available": bool(text_excerpt),
            "extraction_error": extraction_error,
            "extraction_method": extraction_method_used,
        }

    missing_candidate_tils = [
        candidate_til
        for candidate_til in candidate_tils
        if normalize_til_key(candidate_til) not in lookup
    ]
    if missing_candidate_tils:
        lookup.update(
            build_local_sample_til_pdf_lookup(
                missing_candidate_tils,
                _extract_text_from_pdf_path,
                include_text=include_text,
                extraction_method=extraction_method,
            )
        )

    missing_candidate_tils = [
        candidate_til
        for candidate_til in candidate_tils
        if normalize_til_key(candidate_til) not in lookup
    ]
    if missing_candidate_tils:
        lookup.update(
            build_til_pdf_fallback_lookup(
                missing_candidate_tils,
                _extract_text_from_pdf_path,
                include_text=include_text,
                extraction_method=extraction_method,
            )
        )

    return lookup


def build_local_sample_til_pdf_lookup(
    candidate_tils: list[str],
    extract_text_from_pdf_path_fn,
    *,
    include_text: bool,
    extraction_method: str,
) -> dict[str, dict[str, Any]]:
    if not candidate_tils or not LOCAL_TIL_SAMPLE_DIR.exists():
        return {}

    catalog: list[dict[str, Any]] = []
    for pdf_path in sorted(LOCAL_TIL_SAMPLE_DIR.rglob("*.pdf")):
        filename = pdf_path.name
        til_number = extract_local_sample_til_number(filename)
        if not til_number:
            continue
        catalog.append(
            {
                "pdf_path": str(pdf_path),
                "filename": filename,
                "til_number": til_number,
                "normalized_til_key": normalize_til_key(til_number),
                "base_til_num": extract_base_til_num(til_number),
                "revision_number": parse_revision_number(til_number),
            }
        )

    lookup: dict[str, dict[str, Any]] = {}
    for candidate_til in candidate_tils:
        normalized_candidate = normalize_til_key(candidate_til)
        base_candidate = extract_base_til_num(candidate_til)
        exact_matches = [row for row in catalog if row["normalized_til_key"] == normalized_candidate]
        base_matches = [row for row in catalog if row["base_til_num"] == base_candidate]
        ranked_matches = exact_matches or sorted(
            base_matches,
            key=lambda row: (row["revision_number"], row["til_number"]),
            reverse=True,
        )
        if not ranked_matches:
            continue

        selected = ranked_matches[0]
        text_excerpt = ""
        extraction_error = ""
        extraction_method_used = "skipped"
        if include_text:
            pdf_bytes = None
            try:
                pdf_bytes = Path(selected["pdf_path"]).read_bytes()
            except Exception as exc:
                if extraction_method == "foundation":
                    extraction_error = clean_text(exc)
            text_excerpt, extraction_error, extraction_method_used = extract_til_text_with_method(
                pdf_filename=selected["filename"],
                local_pdf_path=selected["pdf_path"],
                local_extract_text_fn=extract_text_from_pdf_path_fn,
                method=extraction_method,
                max_chars=DEFAULT_TIL_TEXT_MAX_CHARS,
                pdf_bytes=pdf_bytes,
            )

        lookup[normalized_candidate] = {
            "document_found": True,
            "document_source": "workspace_sample_pdf",
            "pdf_path": selected["pdf_path"],
            "pdf_filename": selected["filename"],
            "matched_til_number": selected["til_number"],
            "match_type": "exact_til_number" if exact_matches else "base_til_latest_revision",
            "text_excerpt": text_excerpt,
            "text_available": bool(text_excerpt),
            "extraction_error": extraction_error,
            "extraction_method": extraction_method_used,
        }

    return lookup


def build_til_pdf_fallback_lookup(
    candidate_tils: list[str],
    extract_text_from_pdf_path_fn,
    *,
    include_text: bool,
    extraction_method: str,
) -> dict[str, dict[str, Any]]:
    if not candidate_tils:
        return {}

    base_numbers = sorted({extract_base_til_num(value) for value in candidate_tils if extract_base_til_num(value)})
    if not base_numbers:
        return {}

    rows: list[dict[str, Any]] = []
    for chunk in chunked(base_numbers, QUERY_CHUNK_SIZE):
        quoted_bases = ", ".join(sql_quote(value) for value in chunk)
        sql_text = f"""
        SELECT
            pdf,
            CAST(file_name AS STRING) AS file_name,
            CAST(til_num AS STRING) AS til_num,
            CAST(refresh_date AS STRING) AS refresh_date
        FROM {TIL_PDF_FALLBACK_TABLE}
        WHERE REGEXP_EXTRACT(UPPER(TRIM(CAST(til_num AS STRING))), '(\\d+)', 1) IN ({quoted_bases})
        """
        try:
            rows.extend(query_rows(sql_text))
        except Exception:
            return {}

    catalog: list[dict[str, Any]] = []
    for row in rows:
        til_number = clean_text(row.get("til_num"))
        if not til_number or row.get("pdf") in (None, ""):
            continue
        catalog.append(
            {
                "payload": row.get("pdf"),
                "file_name": clean_text(row.get("file_name")),
                "til_number": til_number,
                "normalized_til_key": normalize_til_key(til_number),
                "base_til_num": extract_base_til_num(til_number),
                "revision_number": parse_revision_number(til_number),
                "refresh_date": clean_text(row.get("refresh_date")),
            }
        )

    lookup: dict[str, dict[str, Any]] = {}
    for candidate_til in candidate_tils:
        normalized_candidate = normalize_til_key(candidate_til)
        base_candidate = extract_base_til_num(candidate_til)
        exact_matches = [row for row in catalog if row["normalized_til_key"] == normalized_candidate]
        base_matches = [row for row in catalog if row["base_til_num"] == base_candidate]
        ranked_matches = exact_matches or sorted(
            base_matches,
            key=lambda row: (row["revision_number"], row["til_number"]),
            reverse=True,
        )
        if not ranked_matches:
            continue

        selected = ranked_matches[0]
        payload_bytes = selected.get("payload")
        text_excerpt = ""
        extraction_error = ""
        extraction_method_used = "skipped"
        temp_pdf_path = None
        if include_text:
            try:
                if isinstance(payload_bytes, str):
                    payload_bytes = payload_bytes.encode("utf-8")
                decoded_pdf = base64.b64decode(payload_bytes)
                temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                temp_file.write(decoded_pdf)
                temp_file.close()
                temp_pdf_path = temp_file.name
                text_excerpt, extraction_error, extraction_method_used = extract_til_text_with_method(
                    pdf_filename=selected["file_name"],
                    local_pdf_path=temp_pdf_path,
                    local_extract_text_fn=extract_text_from_pdf_path_fn,
                    method=extraction_method,
                    max_chars=DEFAULT_TIL_TEXT_MAX_CHARS,
                    pdf_bytes=decoded_pdf,
                )
            except Exception as exc:
                extraction_error = clean_text(exc)
            finally:
                if temp_pdf_path and os.path.exists(temp_pdf_path):
                    try:
                        os.unlink(temp_pdf_path)
                    except OSError:
                        pass

        lookup[normalized_candidate] = {
            "document_found": True,
            "document_source": "u_til_pdf_fallback",
            "pdf_path": f"{TIL_PDF_FALLBACK_TABLE}:{selected['til_number']}",
            "pdf_filename": selected["file_name"],
            "matched_til_number": selected["til_number"],
            "match_type": "exact_til_number" if exact_matches else "base_til_latest_revision",
            "text_excerpt": text_excerpt,
            "text_available": bool(text_excerpt),
            "extraction_error": extraction_error,
            "extraction_method": extraction_method_used,
            "refresh_date": selected["refresh_date"],
        }

    return lookup


def build_til_profile_lookup(case_df: pd.DataFrame, profile_root: Path) -> dict[str, dict[str, Any]]:
    candidate_tils = sorted({clean_text(value) for value in case_df["candidate_til_num"].tolist() if clean_text(value)})
    if not candidate_tils or not profile_root.exists():
        return {}

    if profile_root.name.startswith("til_profile_pilot_"):
        run_dirs = [profile_root]
    else:
        run_dirs = sorted(
            [path for path in profile_root.glob("til_profile_pilot_*") if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    if not run_dirs:
        return {}

    catalog: list[dict[str, Any]] = []
    for run_dir in run_dirs:
        for profile_path in run_dir.rglob("profile_response.json"):
            try:
                payload = json.loads(profile_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            extracted_document_path = profile_path.with_name("extracted_document.json")
            extracted_document: dict[str, Any] = {}
            if extracted_document_path.exists():
                try:
                    extracted_document = json.loads(extracted_document_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    extracted_document = {}

            parsed_profile = payload.get("parsed_profile") if isinstance(payload.get("parsed_profile"), dict) else {}
            parsed_profile = normalize_usage_counter_field(parsed_profile)
            requested_til = clean_text(payload.get("requested_til"))
            parsed_til_number = clean_text(parsed_profile.get("til_number"))
            parsed_revision = clean_text(parsed_profile.get("revision"))
            parsed_til = "-".join(part for part in [parsed_til_number, parsed_revision] if part)
            matched_til_number = requested_til or parsed_til or clean_text(profile_path.parent.name)
            if not matched_til_number:
                continue

            catalog.append(
                {
                    "profile_found": True,
                    "profile_source": "cached_profile_response",
                    "profile_path": str(profile_path),
                    "matched_til_number": matched_til_number,
                    "normalized_til_key": normalize_til_key(matched_til_number),
                    "base_til_num": extract_base_til_num(matched_til_number),
                    "revision_number": parse_revision_number(matched_til_number),
                    "parsed_profile": parsed_profile,
                    "extracted_document_path": str(extracted_document_path) if extracted_document_path.exists() else "",
                    "extracted_document_method": clean_text(extracted_document.get("method")),
                    "extracted_document_text_length": extracted_document.get("text_length") or 0,
                    "extracted_document_table_count": extracted_document.get("labeled_table_count") or 0,
                    "extracted_document_tables": extracted_document.get("labeled_tables", []),
                }
            )

    lookup: dict[str, dict[str, Any]] = {}
    for candidate_til in candidate_tils:
        normalized_candidate = normalize_til_key(candidate_til)
        base_candidate = extract_base_til_num(candidate_til)
        exact_matches = [row for row in catalog if row["normalized_til_key"] == normalized_candidate]
        base_matches = [row for row in catalog if row["base_til_num"] == base_candidate]
        ranked_matches = exact_matches or sorted(
            base_matches,
            key=lambda row: (row["revision_number"], row["matched_til_number"]),
            reverse=True,
        )
        if not ranked_matches:
            continue

        selected = dict(ranked_matches[0])
        selected["match_type"] = "exact_til_number" if exact_matches else "base_til_latest_revision"
        lookup[normalized_candidate] = selected

    return lookup


def build_selected_til_profile_context(
    profile_row: dict[str, Any],
    *,
    include_profile_content: bool,
) -> dict[str, Any]:
    parsed_profile = profile_row.get("parsed_profile") if isinstance(profile_row.get("parsed_profile"), dict) else {}
    frame_or_model_applicability_text = clean_text(parsed_profile.get("frame_or_model_applicability_text"))
    combustion_or_fuel_configuration_text = clean_text(parsed_profile.get("combustion_or_fuel_configuration_text"))
    hardware_or_part_configuration_text = clean_text(parsed_profile.get("hardware_or_part_configuration_text"))
    serial_or_unit_applicability_text = clean_text(parsed_profile.get("serial_or_unit_applicability_text"))
    exclusions_or_non_applicable_conditions_text = clean_text(parsed_profile.get("exclusions_or_non_applicable_conditions_text"))
    required_prior_modifications_text = clean_text(parsed_profile.get("required_prior_modifications_text"))
    prerequisite_outage_or_inspection_context_text = clean_text(parsed_profile.get("prerequisite_outage_or_inspection_context_text"))
    profile_found = bool(parsed_profile)
    content_found = profile_found
    profile_source = clean_text(profile_row.get("profile_source"))
    profile_match_type = clean_text(profile_row.get("match_type"))
    matched_til_number = clean_text(profile_row.get("matched_til_number"))
    line_items = parse_list_value(parsed_profile.get("service_recommendation_line_items"))

    context = {
        "profile_found": profile_found,
        "profile_content_available": content_found,
        "profile_content_included": include_profile_content and content_found,
        "profile_source": profile_source,
        "profile_match_type": profile_match_type,
        "profile_path": clean_text(profile_row.get("profile_path")),
        "matched_til_number": matched_til_number,
        "legacy_enrichment_found": False,
        "legacy_enrichment_table": "",
    }
    if not profile_found:
        return context

    context.update(
        {
            "title": clean_text(parsed_profile.get("title")),
            "purpose": clean_text(parsed_profile.get("purpose")),
            "coarse_outage_type": clean_text(parsed_profile.get("coarse_outage_type")),
            "recurring_indicator_if_found": clean_text(parsed_profile.get("recurring_indicator_if_found")),
            "scope_of_work": parse_list_value(parsed_profile.get("scope_of_work")),
            "service_recommendation_line_items": line_items,
            "til_line_items": line_items,
            "completion_criteria_text": clean_text(parsed_profile.get("completion_criteria_text")),
            "maintenance_trigger_text": clean_text(parsed_profile.get("maintenance_trigger_text")),
            "recommended_interval_or_trigger": parse_list_value(parsed_profile.get("recommended_interval_or_trigger")),
            USAGE_COUNTERS_FIELD: profile_usage_counters(parsed_profile),
            "usage_counter_requirements_text": clean_text(parsed_profile.get("usage_counter_requirements_text")),
            "sbom_dependency_flag": bool(parsed_profile.get("sbom_dependency_flag")),
            "sbom_trigger_reason": clean_text(parsed_profile.get("sbom_trigger_reason")),
            "mli_numbers": parsed_profile.get("mli_numbers", []),
            "parts_referenced": parsed_profile.get("parts_referenced", []),
            "reference_documents": parsed_profile.get("reference_documents", []),
            "tables_found_summary": parsed_profile.get("tables_found_summary", []),
            "extracted_document_path": clean_text(profile_row.get("extracted_document_path")),
            "extracted_document_method": clean_text(profile_row.get("extracted_document_method")),
            "extracted_document_table_count": profile_row.get("extracted_document_table_count") or 0,
            "extracted_document_tables": profile_row.get("extracted_document_tables", []),
            "source_snippets": parsed_profile.get("source_snippets", []),
            "configuration_summary": clean_text(parsed_profile.get("configuration_summary")),
            "configuration_variables": parse_list_value(parsed_profile.get("configuration_variables")),
            "frame_or_model_applicability_text": frame_or_model_applicability_text,
            "combustion_or_fuel_configuration_text": combustion_or_fuel_configuration_text,
            "hardware_or_part_configuration_text": hardware_or_part_configuration_text,
            "serial_or_unit_applicability_text": serial_or_unit_applicability_text,
            "exclusions_or_non_applicable_conditions_text": exclusions_or_non_applicable_conditions_text,
            "required_prior_modifications_text": required_prior_modifications_text,
            "prerequisite_outage_or_inspection_context_text": prerequisite_outage_or_inspection_context_text,
            "risk_summary": clean_text(parsed_profile.get("risk_summary")),
            "safety_or_damage_language_found": bool(parsed_profile.get("safety_or_damage_language_found")),
            "extraction_confidence": parsed_profile.get("extraction_confidence"),
            "frame_families": profile_text_list(frame_or_model_applicability_text),
            "combustion_systems": profile_text_list(combustion_or_fuel_configuration_text),
            "hardware_models": profile_text_list(hardware_or_part_configuration_text),
            "applicable_esn_list": profile_text_list(serial_or_unit_applicability_text),
            "applies_to_all_of_frame": parsed_profile.get("applies_to_all_of_frame"),
            "components_affected": parsed_profile.get("components_affected", []),
            "responsibility_hint": clean_text(parsed_profile.get("responsibility_hint")),
            "po_hint": clean_text(parsed_profile.get("po_hint")),
        }
    )
    return context


def build_system_prompt(prompt_pack: str) -> str:
    prompt_config = PROMPT_PACK_INSTRUCTIONS.get(prompt_pack, PROMPT_PACK_INSTRUCTIONS[DEFAULT_PROMPT_PACK])
    return (
        f"{prompt_config['system_intro']} "
        f"The current prompt_pack={prompt_pack}. "
        f"{PROMPT_GUIDANCE} "
        "Return valid JSON with keys: applicability_verdict, reasoning_summary, why_applicable, why_not_applicable, unit_context_used, document_context_used, structured_signals_used, missing_information_needed, suggested_next_checks, confidence, evidence_snippets."
    )


def load_system_prompt(prompt_pack: str, system_prompt_file: Optional[Path]) -> str:
    if system_prompt_file:
        return system_prompt_file.read_text(encoding="utf-8")
    return build_system_prompt(prompt_pack)


def build_user_prompt_template(prompt_pack: str) -> str:
    prompt_config = PROMPT_PACK_INSTRUCTIONS.get(prompt_pack, PROMPT_PACK_INSTRUCTIONS[DEFAULT_PROMPT_PACK])
    return (
        f"{prompt_config['user_intro']} Prompt pack: {prompt_pack}.\n\n"
        "Evaluation rules:\n"
        "- Judge only this single (event, ESN, TIL) case.\n"
        "- applicability_verdict must be one of: applicable, not_applicable, conditionally_applicable, insufficient_information.\n"
        "- Explicitly consider outage context when outage type is present.\n"
        "- Explicitly consider TIL line items and recommended maintenance actions when they are present.\n"
        "- If template_coverage is present, focus on template_gap_line_items as the effective review target and do not let template-covered items drive the verdict.\n"
        "- Explicitly use completion_review when it is present. If it says prior completion likely reduces current applicability, only override that when the TIL is recurring or the payload shows a new trigger/reset condition.\n"
        "- If sbom_context is present, use SBOM matches as supporting configuration evidence only. A missing SBOM match does not by itself prove the TIL is not applicable.\n"
        "- unit_context_used should briefly state the unit facts you relied on.\n"
        "- document_context_used should briefly state which TIL-derived context you relied on, or say unavailable.\n"
        "- structured_signals_used should be a short ordered list of the fields that mattered most.\n"
        "- missing_information_needed should be the specific missing facts that would change the answer, especially prior completion evidence when relevant.\n"
        "- suggested_next_checks should be concrete next actions, not generic statements.\n"
        "- confidence must be a float between 0 and 1.\n"
        "- evidence_snippets should be a short list of field-grounded observations from the payload, not invented document quotes.\n\n"
        "Case payload:\n"
        "{case_payload}\n"
    )


def build_user_prompt(case_payload: dict[str, Any], prompt_pack: str) -> str:
    return build_user_prompt_template(prompt_pack).format(
        case_payload=json.dumps(case_payload, indent=2, default=str)
    )


def build_case_payload(
    row: pd.Series,
    ev_lookup: dict[tuple[str, str], dict[str, Any]],
    ibat_lookup: dict[str, dict[str, Any]],
    til_profile_lookup: dict[str, dict[str, Any]],
    til_pdf_lookup: dict[str, dict[str, Any]],
    fsr_completion_result: dict[str, Any],
    template_coverage_result: dict[str, Any],
    prompt_pack: str,
    source_csv: Path,
    til_context_mode: str,
    til_profile_dir: Path,
) -> dict[str, Any]:
    event_key = clean_text(row.get("matched_event_id"))
    esn_key = normalize_string(row.get("matched_esn"))
    candidate_til_num = clean_text(row.get("candidate_til_num"))
    ev_row = ev_lookup.get((event_key, esn_key), {})
    ibat_row = ibat_lookup.get(esn_key, {})
    profile_row = til_profile_lookup.get(normalize_til_key(candidate_til_num), {})
    til_pdf_row = til_pdf_lookup.get(normalize_til_key(candidate_til_num), {})
    prior_service_row = (
        fsr_completion_result.get("prior_service_evidence")
        if isinstance(fsr_completion_result.get("prior_service_evidence"), dict)
        else default_prior_service_evidence()
    )
    completion_review = (
        fsr_completion_result.get("completion_review")
        if isinstance(fsr_completion_result.get("completion_review"), dict)
        else default_completion_review(prior_service_row)
    )
    template_coverage = (
        template_coverage_result if isinstance(template_coverage_result, dict) else default_template_coverage_result()
    )
    resolved_outage_type = clean_text(row.get("context_event_type")) or clean_text(ev_row.get("ev_event_type"))
    include_profile_content = til_context_mode in {"profile_only", "profile_plus_document"}
    include_document_text = til_context_mode in {"full_document", "profile_plus_document"}
    til_profile_context = build_selected_til_profile_context(
        profile_row,
        include_profile_content=include_profile_content,
    )
    sbom_context = build_sbom_context(row.get("matched_esn"), til_profile_context)

    structured_signals = {
        "candidate_til_num": candidate_til_num,
        "base_til_num": clean_text(row.get("base_til_num")),
        "candidate_revision": clean_text(row.get("candidate_revision")),
        "til_num_status": clean_text(row.get("til_num_status")),
        "disposition_status": clean_text(row.get("disposition_status")),
        "disposition_notes": clean_text(row.get("disposition_notes")),
        "applicable_to": clean_text(row.get("applicable_to")),
        "affected_units_technology": clean_text(row.get("affected_units_technology")),
        "from_serial_match": clean_text(row.get("from_serial_match")),
        "from_osa": clean_text(row.get("from_osa")),
        "osa_base_til_num": clean_text(row.get("osa_base_til_num")),
    }

    return {
        "case_identifiers": {
            "input_row_id": clean_text(row.get("input_row_id")),
            "source_ev_id": clean_text(row.get("source_ev_id")),
            "requested_esn": clean_text(row.get("requested_esn")),
            "matched_event_id": event_key,
            "matched_esn": esn_key,
            "ev_project_id": clean_text(row.get("ev_project_id")),
            "ev_scoping_project_id": clean_text(row.get("ev_scoping_project_id")),
        },
        "outage_context": {
            "context_event_type": resolved_outage_type,
            "outage_type": resolved_outage_type,
            "event_outage_type": resolved_outage_type,
            "context_event_status": clean_text(row.get("context_event_status")),
            "context_serial_numbers": clean_text(row.get("context_serial_numbers")),
            "source_serial_numbers": clean_text(row.get("source_serial_numbers")),
        },
        "unit_context": {
            "ev_equipment_code": clean_text(ev_row.get("ev_equipment_code")),
            "ev_frame_type": clean_text(ev_row.get("ev_frame_type")),
            "ev_combustion_system": clean_text(ev_row.get("ev_combustion_system")),
            "ev_fuel_type": clean_text(ev_row.get("ev_fuel_type")),
            "ibat_equipment_code": clean_text(ibat_row.get("ibat_equipment_code")),
            "ibat_combustion_system": clean_text(ibat_row.get("ibat_combustion_system")),
            "ibat_primary_fuel": clean_text(ibat_row.get("primary_fuel")),
            "ibat_secondary_fuel": clean_text(ibat_row.get("secondary_fuel")),
        },
        "candidate_context": structured_signals,
        "til_profile_context": til_profile_context,
        "til_document_source": {
            "document_found": bool(til_pdf_row.get("document_found")),
            "document_text_available": bool(til_pdf_row.get("text_available")),
            "document_text_included": include_document_text and bool(til_pdf_row.get("text_available")),
            "document_tables_available": bool(profile_row.get("extracted_document_tables")),
            "document_tables_included": include_document_text and bool(profile_row.get("extracted_document_tables")),
            "document_source": clean_text(til_pdf_row.get("document_source")),
            "pdf_filename": clean_text(til_pdf_row.get("pdf_filename")),
            "pdf_path": clean_text(til_pdf_row.get("pdf_path")),
            "matched_til_number": clean_text(til_pdf_row.get("matched_til_number")),
            "match_type": clean_text(til_pdf_row.get("match_type")),
            "extracted_document_path": clean_text(profile_row.get("extracted_document_path")),
            "extracted_document_method": clean_text(profile_row.get("extracted_document_method")),
            "table_count": profile_row.get("extracted_document_table_count") or 0,
            "labeled_tables": profile_row.get("extracted_document_tables", []) if include_document_text else [],
            "text_available": bool(til_pdf_row.get("text_available")),
            "text_excerpt": clean_text(til_pdf_row.get("text_excerpt")) if include_document_text else "",
            "extraction_error": clean_text(til_pdf_row.get("extraction_error")),
            "refresh_date": clean_text(til_pdf_row.get("refresh_date")),
        },
        "prior_service_evidence": {
            "status": clean_text(prior_service_row.get("status")),
            "source": clean_text(prior_service_row.get("source")),
            "evidence_count": prior_service_row.get("evidence_count") or 0,
            "report_count": prior_service_row.get("report_count") or 0,
            "candidate_chunk_count": prior_service_row.get("candidate_chunk_count") or 0,
            "evidence_source_systems": prior_service_row.get("evidence_source_systems", []),
            "evidence_source_counts": prior_service_row.get("evidence_source_counts", {}),
            "dates": prior_service_row.get("dates", []),
            "excerpts": prior_service_row.get("excerpts", []),
            "reasoning": clean_text(prior_service_row.get("reasoning")),
            "for_llm": clean_text(prior_service_row.get("for_llm")),
            "retrieval_error": clean_text(prior_service_row.get("retrieval_error")),
            "retrieval_query": clean_text(prior_service_row.get("retrieval_query")),
            "retrieval_queries": prior_service_row.get("retrieval_queries", []),
            "retrieval_sql_tokens": prior_service_row.get("retrieval_sql_tokens", []),
            "retrieval_signal_source": clean_text(prior_service_row.get("retrieval_signal_source")),
            "retrieval_branches": prior_service_row.get("retrieval_branches", []),
        },
        "completion_review": completion_review,
        "sbom_context": sbom_context,
        "template_coverage": {
            "status": clean_text(template_coverage.get("status")),
            "information_only_flag": bool(template_coverage.get("information_only_flag")),
            "information_only_reason": clean_text(template_coverage.get("information_only_reason")),
            "information_only_evidence": template_coverage.get("information_only_evidence", []),
            "template_coverage_class": clean_text(template_coverage.get("template_coverage_class")),
            "template_coverage_confidence": template_coverage.get("template_coverage_confidence") or 0.0,
            "matched_template_code": clean_text(template_coverage.get("matched_template_code")),
            "matched_template_display_name": clean_text(template_coverage.get("matched_template_display_name")),
            "matched_template_activity_ids": template_coverage.get("matched_template_activity_ids", []),
            "matched_template_activity_texts": template_coverage.get("matched_template_activity_texts", []),
            "covered_til_line_items": template_coverage.get("covered_til_line_items", []),
            "gap_til_line_items": template_coverage.get("gap_til_line_items", []),
            "unclear_til_line_items": template_coverage.get("unclear_til_line_items", []),
            "template_overlap_reasoning": clean_text(template_coverage.get("template_overlap_reasoning")),
            "template_partial_coverage_notes": clean_text(template_coverage.get("template_partial_coverage_notes")),
            "template_review_flag": bool(template_coverage.get("template_review_flag")),
        },
        "experiment_settings": {
            "prompt_pack": prompt_pack,
            "source_candidate_csv": str(source_csv),
            "til_context_mode": til_context_mode,
            "til_profile_dir": str(til_profile_dir),
        },
    }


def build_step6_service_history_completion_request(
    row: pd.Series,
    ev_lookup: dict[tuple[str, str], dict[str, Any]],
    ibat_lookup: dict[str, dict[str, Any]],
    til_profile_lookup: dict[str, dict[str, Any]],
    template_coverage_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_key = clean_text(row.get("matched_event_id"))
    esn_key = normalize_string(row.get("matched_esn"))
    candidate_til_num = clean_text(row.get("candidate_til_num"))
    ev_row = ev_lookup.get((event_key, esn_key), {})
    ibat_row = ibat_lookup.get(esn_key, {})
    profile_row = til_profile_lookup.get(normalize_til_key(candidate_til_num), {})
    completion_profile_context = build_selected_til_profile_context(
        profile_row,
        include_profile_content=True,
    )
    template_coverage = template_coverage_result if isinstance(template_coverage_result, dict) else default_template_coverage_result()
    original_service_line_items = completion_profile_context.get("service_recommendation_line_items", [])
    template_gap_line_items = template_coverage.get("gap_til_line_items", []) if isinstance(template_coverage.get("gap_til_line_items"), list) else []
    template_covered_line_items = template_coverage.get("covered_til_line_items", []) if isinstance(template_coverage.get("covered_til_line_items"), list) else []
    effective_service_line_items = template_gap_line_items or original_service_line_items
    resolved_outage_type = clean_text(row.get("context_event_type")) or clean_text(ev_row.get("ev_event_type"))

    additional_query_hints = [
        resolved_outage_type,
        clean_text(row.get("applicable_to")),
        clean_text(row.get("affected_units_technology")),
        clean_text(row.get("disposition_status")),
        clean_text(row.get("disposition_notes")),
        clean_text(completion_profile_context.get("configuration_summary")),
        clean_text(completion_profile_context.get("frame_or_model_applicability_text")),
        clean_text(completion_profile_context.get("combustion_or_fuel_configuration_text")),
        clean_text(completion_profile_context.get("hardware_or_part_configuration_text")),
        clean_text(completion_profile_context.get("serial_or_unit_applicability_text")),
        clean_text(completion_profile_context.get("exclusions_or_non_applicable_conditions_text")),
        clean_text(completion_profile_context.get("required_prior_modifications_text")),
        clean_text(completion_profile_context.get("prerequisite_outage_or_inspection_context_text")),
        clean_text(completion_profile_context.get("responsibility_hint")),
    ]

    return {
        "workflow_step": "step6",
        "source_type": "til",
        "service_history_source_systems": ["FSR", "ER"],
        "source_identifier": candidate_til_num,
        "title": clean_text(completion_profile_context.get("title")),
        "matched_event_id": event_key,
        "matched_esn": esn_key,
        "recurring_indicator_if_found": clean_text(completion_profile_context.get("recurring_indicator_if_found")),
        "completion_criteria_text": clean_text(completion_profile_context.get("completion_criteria_text")),
        "maintenance_trigger_text": clean_text(completion_profile_context.get("maintenance_trigger_text")),
        "recommended_interval_or_trigger": completion_profile_context.get("recommended_interval_or_trigger", []),
        USAGE_COUNTERS_FIELD: completion_profile_context.get(USAGE_COUNTERS_FIELD, []),
        "usage_counter_requirements_text": clean_text(completion_profile_context.get("usage_counter_requirements_text")),
        "disposition_status": clean_text(row.get("disposition_status")),
        "disposition_notes": clean_text(row.get("disposition_notes")),
        "frame_or_model_applicability_text": clean_text(completion_profile_context.get("frame_or_model_applicability_text")),
        "combustion_or_fuel_configuration_text": clean_text(completion_profile_context.get("combustion_or_fuel_configuration_text")),
        "hardware_or_part_configuration_text": clean_text(completion_profile_context.get("hardware_or_part_configuration_text")),
        "serial_or_unit_applicability_text": clean_text(completion_profile_context.get("serial_or_unit_applicability_text")),
        "exclusions_or_non_applicable_conditions_text": clean_text(completion_profile_context.get("exclusions_or_non_applicable_conditions_text")),
        "required_prior_modifications_text": clean_text(completion_profile_context.get("required_prior_modifications_text")),
        "prerequisite_outage_or_inspection_context_text": clean_text(completion_profile_context.get("prerequisite_outage_or_inspection_context_text")),
        "template_coverage_class": clean_text(template_coverage.get("template_coverage_class")),
        "original_service_line_items": original_service_line_items,
        "template_gap_line_items": template_gap_line_items,
        "template_covered_line_items": template_covered_line_items,
        "service_line_items": effective_service_line_items,
        "parts_referenced": completion_profile_context.get("parts_referenced", []),
        "additional_query_hints": [value for value in additional_query_hints if value],
        "unit_context": {
            "outage_type": resolved_outage_type,
            "disposition_status": clean_text(row.get("disposition_status")),
            "disposition_notes": clean_text(row.get("disposition_notes")),
            "ev_equipment_code": clean_text(ev_row.get("ev_equipment_code")),
            "ev_frame_type": clean_text(ev_row.get("ev_frame_type")),
            "ev_combustion_system": clean_text(ev_row.get("ev_combustion_system")),
            "ibat_equipment_code": clean_text(ibat_row.get("ibat_equipment_code")),
            "ibat_combustion_system": clean_text(ibat_row.get("ibat_combustion_system")),
            "ibat_primary_fuel": clean_text(ibat_row.get("primary_fuel")),
        },
    }


def build_template_coverage_request(
    row: pd.Series,
    til_profile_lookup: dict[str, dict[str, Any]],
    til_pdf_lookup: dict[str, dict[str, Any]],
    powernow_metadata_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    candidate_til_num = clean_text(row.get("candidate_til_num"))
    normalized_candidate = normalize_til_key(candidate_til_num)
    profile_row = til_profile_lookup.get(normalize_til_key(candidate_til_num), {})
    pdf_row = til_pdf_lookup.get(normalized_candidate, {})
    powernow_metadata = powernow_metadata_lookup.get(normalized_candidate, {})
    profile_context = build_selected_til_profile_context(profile_row, include_profile_content=True)
    information_only = evaluate_information_only(profile_context)
    fallback_title = (
        clean_text(profile_context.get("title"))
        or clean_text(powernow_metadata.get("title"))
        or clean_text(row.get("ev_osa_scope_title"))
        or candidate_til_num
    )
    fallback_purpose = clean_text(profile_context.get("purpose")) or clean_text(powernow_metadata.get("purpose"))
    fallback_coarse_outage_type = clean_text(profile_context.get("coarse_outage_type")) or clean_text(powernow_metadata.get("coarse_outage_type"))
    fallback_recurring_indicator = clean_text(profile_context.get("recurring_indicator_if_found")) or clean_text(powernow_metadata.get("recurring_indicator"))
    fallback_compliance_category_code = clean_text(profile_context.get("compliance_category_code")) or clean_text(powernow_metadata.get("compliance_category_code"))
    fallback_compliance_category_text = clean_text(profile_context.get("compliance_category_text")) or clean_text(powernow_metadata.get("compliance_category_text"))
    return {
        "workflow_step": "step6",
        "source_type": "til",
        "matched_event_id": clean_text(row.get("matched_event_id")),
        "matched_esn": clean_text(row.get("matched_esn")),
        "ev_scoping_project_id": clean_text(row.get("ev_scoping_project_id")),
        "candidate_til_num": candidate_til_num,
        "outage_type": clean_text(row.get("context_event_type")),
        "information_only_flag": bool(information_only.get("information_only_flag")),
        "information_only_reason": clean_text(information_only.get("information_only_reason")),
        "information_only_evidence": information_only.get("information_only_evidence", []),
        "til_context": {
            "title": fallback_title,
            "purpose": fallback_purpose,
            "service_line_items": profile_context.get("service_recommendation_line_items", []),
            "scope_of_work": profile_context.get("scope_of_work", []),
            "completion_criteria_text": clean_text(profile_context.get("completion_criteria_text")),
            "maintenance_trigger_text": clean_text(profile_context.get("maintenance_trigger_text")),
            "risk_summary": clean_text(profile_context.get("risk_summary")),
            "parts_referenced": profile_context.get("parts_referenced", []),
            "source_snippets": profile_context.get("source_snippets", []),
            "extraction_confidence": profile_context.get("extraction_confidence"),
            "coarse_outage_type": fallback_coarse_outage_type,
            "recurring_indicator": fallback_recurring_indicator,
            "compliance_category_code": fallback_compliance_category_code,
            "compliance_category_text": fallback_compliance_category_text,
            "applicable_to": clean_text(profile_context.get("applicable_to")) or clean_text(powernow_metadata.get("applicable_to")) or clean_text(row.get("applicable_to")),
            "affected_units_technology": clean_text(profile_context.get("affected_units_technology")) or clean_text(powernow_metadata.get("affected_units_technology")) or clean_text(row.get("affected_units_technology")),
            "ev_osa_scope_title": clean_text(row.get("ev_osa_scope_title")),
            "metadata_summary": clean_text(powernow_metadata.get("metadata_summary")),
            "powernow_metadata_found": bool(powernow_metadata.get("powernow_metadata_found")),
            "profile_found": bool(profile_context.get("profile_found")),
            "document_found": bool(pdf_row.get("document_found")),
            "document_source": clean_text(pdf_row.get("document_source")),
        },
    }


def default_system_prompt_artifact_path(output_dir: Path, output_stem: str, timestamp: str) -> Path:
    return output_dir / "system_prompt.txt"


def default_context_payload_artifact_path(output_dir: Path, output_stem: str, timestamp: str) -> Path:
    return output_dir / "context_payloads.json"


def default_template_coverage_records_path(output_dir: Path, output_stem: str, timestamp: str) -> Path:
    return output_dir / "template_coverage_records.json"


def write_template_coverage_artifacts(
    *,
    template_coverage_records_path: Path,
    candidate_csv: Path,
    template_coverage_rows: list[dict[str, Any]],
) -> None:
    template_coverage_records_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_candidate_csv": str(candidate_csv),
        "case_count": len(template_coverage_rows),
        "cases": template_coverage_rows,
    }
    template_coverage_records_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_prompt_artifacts(
    *,
    system_prompt_path: Path,
    context_payload_path: Path,
    system_prompt: str,
    prompt_pack: str,
    candidate_csv: Path,
    prompt_payload_rows: list[dict[str, Any]],
) -> None:
    system_prompt_path.parent.mkdir(parents=True, exist_ok=True)
    context_payload_path.parent.mkdir(parents=True, exist_ok=True)
    system_prompt_path.write_text(system_prompt, encoding="utf-8")
    context_payload_export = {
        "prompt_pack": prompt_pack,
        "source_candidate_csv": str(candidate_csv),
        "case_count": len(prompt_payload_rows),
        "cases": [
            {
                "input_row_id": clean_text(row.get("input_row_id")),
                "matched_event_id": clean_text(row.get("matched_event_id")),
                "matched_esn": clean_text(row.get("matched_esn")),
                "candidate_til_num": clean_text(row.get("candidate_til_num")),
                "prompt_payload": row.get("prompt_payload", {}),
            }
            for row in prompt_payload_rows
        ],
    }
    context_payload_path.write_text(json.dumps(context_payload_export, indent=2), encoding="utf-8")


def flatten_mapping(prefix: str, value: Any, destination: dict[str, str]) -> None:
    if isinstance(value, dict):
        for key, nested_value in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            flatten_mapping(next_prefix, nested_value, destination)
        return
    if isinstance(value, list):
        destination[prefix] = join_output_list(value)
        return
    destination[prefix] = clean_text(value)


def summarize_results(summary_df: pd.DataFrame) -> dict[str, Any]:
    if summary_df.empty:
        return {
            "rows_evaluated": 0,
            "parsed_response_rows": 0,
            "information_only_rows": 0,
            "template_covered_skip_rows": 0,
            "applicable_rows": 0,
            "not_applicable_rows": 0,
            "conditionally_applicable_rows": 0,
            "insufficient_information_rows": 0,
            "avg_confidence": 0.0,
            "from_osa_rows": 0,
            "direct_serial_match_rows": 0,
            "enrichment_found_rows": 0,
            "til_profile_found_rows": 0,
            "prior_service_evidence_rows": 0,
        }

    confidence_series = pd.to_numeric(summary_df["confidence"], errors="coerce")
    verdict_series = summary_df["applicability_verdict"].fillna("")
    prior_service_count_series = pd.to_numeric(
        summary_df.get("prior_service_evidence_count", pd.Series(dtype="float64")),
        errors="coerce",
    )
    return {
        "rows_evaluated": int(len(summary_df)),
        "parsed_response_rows": int(summary_df["parsed_response_present"].sum()),
        "information_only_rows": int(summary_df.get("final_disposition", pd.Series(dtype="object")).eq("information_only_skip").sum()),
        "template_covered_skip_rows": int(summary_df.get("final_disposition", pd.Series(dtype="object")).eq("template_covered_skip").sum()),
        "applicable_rows": int(verdict_series.eq("applicable").sum()),
        "not_applicable_rows": int(verdict_series.eq("not_applicable").sum()),
        "conditionally_applicable_rows": int(verdict_series.eq("conditionally_applicable").sum()),
        "insufficient_information_rows": int(verdict_series.eq("insufficient_information").sum()),
        "avg_confidence": float(round(confidence_series.dropna().mean(), 3)) if confidence_series.notna().any() else 0.0,
        "from_osa_rows": int(summary_df["from_osa"].eq("Y").sum()),
        "direct_serial_match_rows": int(summary_df["from_serial_match"].eq("Y").sum()),
        "enrichment_found_rows": int(summary_df["enrichment_found"].sum()),
        "til_profile_found_rows": int(summary_df.get("til_profile_found", pd.Series(dtype="int64")).sum()) if "til_profile_found" in summary_df.columns else 0,
        "prior_service_evidence_rows": int(prior_service_count_series.gt(0).sum()) if "prior_service_evidence_count" in summary_df.columns else 0,
        "til_document_found_rows": int(summary_df.get("til_document_found", pd.Series(dtype="int64")).sum()) if "til_document_found" in summary_df.columns else 0,
    }


def write_excel_report(
    workbook_path: Path,
    run_payload: dict[str, Any],
    summary_df: pd.DataFrame,
    line_item_df: pd.DataFrame,
    template_line_item_df: pd.DataFrame,
    input_rows: list[dict[str, Any]],
    prompt_rows: list[dict[str, Any]],
    system_prompt: str,
    system_prompt_path: Path,
    context_payload_path: Path,
    template_coverage_records_path: Path,
) -> None:
    run_summary_df = pd.DataFrame(
        [{"metric": key, "value": excel_safe_text(value)} for key, value in run_payload.items()]
    )
    summary_df = sanitize_excel_dataframe(summary_df)
    line_item_df = sanitize_excel_dataframe(line_item_df)
    template_line_item_df = sanitize_excel_dataframe(template_line_item_df)
    inputs_df = sanitize_excel_dataframe(pd.DataFrame(input_rows))
    prompts_df = sanitize_excel_dataframe(pd.DataFrame(prompt_rows))
    artifacts_df = pd.DataFrame(
        [
            {"artifact": "system_prompt", "content": excel_safe_text(system_prompt)},
            {"artifact": "prompt_pack", "content": excel_safe_text(run_payload.get("prompt_pack", ""))},
            {"artifact": "source_candidate_csv", "content": excel_safe_text(run_payload.get("source_candidate_csv", ""))},
            {"artifact": "system_prompt_path", "content": excel_safe_text(system_prompt_path)},
            {"artifact": "context_payload_path", "content": excel_safe_text(context_payload_path)},
            {"artifact": "template_coverage_records_path", "content": excel_safe_text(template_coverage_records_path)},
        ]
    )

    with pd.ExcelWriter(workbook_path) as writer:
        run_summary_df.to_excel(writer, sheet_name="run_summary", index=False)
        summary_df.to_excel(writer, sheet_name="case_summary", index=False)
        line_item_df.to_excel(writer, sheet_name="completion_line_items", index=False)
        template_line_item_df.to_excel(writer, sheet_name="template_line_items", index=False)
        inputs_df.to_excel(writer, sheet_name="llm_inputs", index=False)
        prompts_df.to_excel(writer, sheet_name="prompts", index=False)
        artifacts_df.to_excel(writer, sheet_name="prompt_artifacts", index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Step 6 TIL applicability evaluation over the ground-truth candidate pool.")
    parser.add_argument("--candidate-csv", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-stem", default="gt_til_applicability_eval")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--prompt-pack", default=DEFAULT_PROMPT_PACK)
    parser.add_argument("--system-prompt-file", type=Path)
    parser.add_argument(
        "--prior-service-retrieval-depth",
        "--prior-service-k",
        dest="prior_service_retrieval_depth",
        type=int,
        default=DEFAULT_PRIOR_SERVICE_RETRIEVAL_DEPTH_HINT,
        help="Hint for prior-service retrieval depth before reranking. Legacy alias: --prior-service-k",
    )
    parser.add_argument("--til-profile-dir", type=Path, default=DEFAULT_TIL_PROFILE_DIR)
    parser.add_argument(
        "--til-document-method",
        choices=["auto", "foundation", "pdfplumber"],
        default=DEFAULT_TIL_DOCUMENT_METHOD,
    )
    parser.add_argument(
        "--til-context-mode",
        choices=["full_document", "profile_only", "profile_plus_document"],
        default=DEFAULT_TIL_CONTEXT_MODE,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate_csv = find_latest_candidate_csv(args.candidate_csv)
    case_df = load_candidate_cases(candidate_csv, args.limit)
    if case_df.empty:
        raise RuntimeError(f"No surviving candidate rows found in {candidate_csv}")

    ev_lookup = fetch_ev_lookup(case_df)
    ibat_lookup = fetch_ibat_lookup(case_df)
    til_profile_lookup = build_til_profile_lookup(case_df, args.til_profile_dir)
    include_til_document_text = args.til_context_mode in {"full_document", "profile_plus_document"}
    til_pdf_lookup = build_til_pdf_lookup(
        case_df,
        include_text=include_til_document_text,
        extraction_method=args.til_document_method,
    )
    powernow_metadata_lookup = build_powernow_til_metadata_lookup(case_df)
    system_prompt = load_system_prompt(args.prompt_pack, args.system_prompt_file)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.output_dir / f"{args.output_stem}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = run_dir / "summary.xlsx"
    csv_path = run_dir / "summary.csv"
    line_item_csv_path = run_dir / "line_items.csv"
    template_line_item_csv_path = run_dir / "template_line_items.csv"
    json_path = run_dir / "run_payload.json"
    jsonl_path = run_dir / "records.jsonl"
    system_prompt_path = default_system_prompt_artifact_path(run_dir, args.output_stem, timestamp)
    context_payload_path = default_context_payload_artifact_path(run_dir, args.output_stem, timestamp)
    template_coverage_records_path = default_template_coverage_records_path(run_dir, args.output_stem, timestamp)
    run_payload_md_path = markdown_companion_path(json_path)
    summary_md_path = markdown_companion_path(csv_path)
    line_items_md_path = markdown_companion_path(line_item_csv_path)
    template_line_items_md_path = markdown_companion_path(template_line_item_csv_path)
    context_payload_md_path = markdown_companion_path(context_payload_path)
    template_coverage_md_path = markdown_companion_path(template_coverage_records_path)

    summary_rows: list[dict[str, Any]] = []
    line_item_rows: list[dict[str, Any]] = []
    template_line_item_rows: list[dict[str, Any]] = []
    input_rows: list[dict[str, Any]] = []
    prompt_rows: list[dict[str, Any]] = []
    prompt_payload_rows: list[dict[str, Any]] = []
    template_coverage_artifact_rows: list[dict[str, Any]] = []

    total_cases = len(case_df)
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for case_index, row in enumerate(case_df.to_dict(orient="records"), start=1):
            row_series = pd.Series(row)
            export_profile_context = build_selected_til_profile_context(
                til_profile_lookup.get(normalize_til_key(clean_text(row.get("candidate_til_num"))), {}),
                include_profile_content=True,
            )
            template_coverage_request = build_template_coverage_request(row_series, til_profile_lookup, til_pdf_lookup, powernow_metadata_lookup)
            template_coverage_result = {
                **default_template_coverage_result(),
                "information_only_flag": bool(template_coverage_request.get("information_only_flag")),
                "information_only_reason": clean_text(template_coverage_request.get("information_only_reason")),
                "information_only_evidence": template_coverage_request.get("information_only_evidence", []),
            }
            completion_review_raw_response = None
            completion_review_system_prompt = ""
            completion_review_user_prompt = ""
            completion_review_started_utc = None
            completion_review_completed_utc = None
            completion_review_elapsed_sec = None
            raw_response = None
            parsed_response = None
            llm_call_started_utc = None
            llm_call_completed_utc = None
            llm_call_elapsed_sec = None
            final_disposition = "full_review"
            downstream_scope_basis = "all_til_items"

            if template_coverage_request.get("information_only_flag"):
                template_coverage_result["status"] = "information_only_skip"
                service_history_result = default_service_history_completion_result()
                final_disposition = "information_only_skip"
                downstream_scope_basis = "information_only_skip"
            else:
                template_coverage_result = run_template_coverage_service(
                    template_coverage_request,
                    dry_run=args.dry_run,
                )
                if clean_text(template_coverage_result.get("template_coverage_class")) == "already_covered" and not template_coverage_result.get("gap_til_line_items"):
                    service_history_result = default_service_history_completion_result()
                    final_disposition = "template_covered_skip"
                    downstream_scope_basis = "skipped_template_covered"
                else:
                    gap_line_items = template_coverage_result.get("gap_til_line_items") if isinstance(template_coverage_result.get("gap_til_line_items"), list) else []
                    if gap_line_items:
                        downstream_scope_basis = "gap_items_only"
                    if args.dry_run:
                        service_history_result = default_service_history_completion_result()
                    else:
                        service_history_request = build_step6_service_history_completion_request(
                            row_series,
                            ev_lookup,
                            ibat_lookup,
                            til_profile_lookup,
                            template_coverage_result,
                        )
                        completion_review_started_utc = datetime.now(timezone.utc).isoformat()
                        completion_review_started = time.perf_counter()
                        service_history_result = run_service_history_completion_service(
                            service_history_request,
                            retrieval_depth_hint=args.prior_service_retrieval_depth,
                        )
                        completion_review_completed_utc = datetime.now(timezone.utc).isoformat()
                        completion_review_elapsed_sec = round(time.perf_counter() - completion_review_started, 3)
                        completion_review_raw_response = service_history_result.get("completion_review_raw_response")
                        completion_review_system_prompt = clean_text(service_history_result.get("completion_review_system_prompt"))
                        completion_review_user_prompt = clean_text(service_history_result.get("completion_review_user_prompt"))

            payload = build_case_payload(
                row_series,
                ev_lookup,
                ibat_lookup,
                til_profile_lookup,
                til_pdf_lookup,
                service_history_result,
                template_coverage_result,
                args.prompt_pack,
                candidate_csv,
                args.til_context_mode,
                args.til_profile_dir,
            )
            user_prompt = build_user_prompt(payload, args.prompt_pack)

            should_run_final_applicability = final_disposition == "full_review"
            if should_run_final_applicability and not args.dry_run:
                llm_call_started_utc = datetime.now(timezone.utc).isoformat()
                llm_started = time.perf_counter()
                print(
                    f"[step6-applicability] case {case_index}/{total_cases} starting LLM call: event={row.get('matched_event_id')} esn={row.get('matched_esn')} til={row.get('candidate_til_num')}",
                    flush=True,
                )
                raw_response = call_llm(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=args.temperature,
                )
                llm_call_completed_utc = datetime.now(timezone.utc).isoformat()
                llm_call_elapsed_sec = round(time.perf_counter() - llm_started, 3)
                parsed_response = parse_llm_response(raw_response) if raw_response else None
                print(
                    f"[step6-applicability] case {case_index}/{total_cases} completed LLM call: elapsed_sec={llm_call_elapsed_sec} raw_response_present={bool(raw_response)} parsed_response_present={parsed_response is not None}",
                    flush=True,
                )

            parsed_response = parsed_response if isinstance(parsed_response, dict) else {}
            prompt_record = {
                "input_row_id": clean_text(row.get("input_row_id")),
                "matched_event_id": clean_text(row.get("matched_event_id")),
                "matched_esn": clean_text(row.get("matched_esn")),
                "candidate_til_num": clean_text(row.get("candidate_til_num")),
                "final_disposition": final_disposition,
                "prompt_payload": payload,
                "template_coverage_result": payload.get("template_coverage", {}),
                "completion_review_system_prompt": completion_review_system_prompt,
                "completion_review_user_prompt": completion_review_user_prompt,
                "completion_review_raw_response": completion_review_raw_response,
                "completion_review_parsed_response": payload.get("completion_review", {}),
                "completion_review_started_utc": completion_review_started_utc,
                "completion_review_completed_utc": completion_review_completed_utc,
                "completion_review_elapsed_sec": completion_review_elapsed_sec,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "raw_response": raw_response,
                "parsed_response": parsed_response,
                "llm_call_started_utc": llm_call_started_utc,
                "llm_call_completed_utc": llm_call_completed_utc,
                "llm_call_elapsed_sec": llm_call_elapsed_sec,
            }
            handle.write(json.dumps(prompt_record) + "\n")
            handle.flush()
            template_coverage_artifact_rows.append(
                {
                    "input_row_id": clean_text(row.get("input_row_id")),
                    "matched_event_id": clean_text(row.get("matched_event_id")),
                    "matched_esn": clean_text(row.get("matched_esn")),
                    "candidate_til_num": clean_text(row.get("candidate_til_num")),
                    "final_disposition": final_disposition,
                    "template_coverage_request": template_coverage_request,
                    "template_coverage_result": template_coverage_result,
                    "template_coverage_system_prompt": clean_text(template_coverage_result.get("llm_prompt_artifacts", {}).get("system_prompt")),
                    "template_coverage_user_prompt": clean_text(template_coverage_result.get("llm_prompt_artifacts", {}).get("user_prompt")),
                    "template_coverage_raw_response": template_coverage_result.get("llm_raw_response"),
                    "template_coverage_parsed_response": template_coverage_result.get("llm_parsed_response"),
                }
            )
            prompt_payload_rows.append(
                {
                    "input_row_id": clean_text(row.get("input_row_id")),
                    "matched_event_id": clean_text(row.get("matched_event_id")),
                    "matched_esn": clean_text(row.get("matched_esn")),
                    "candidate_til_num": clean_text(row.get("candidate_til_num")),
                    "prompt_payload": payload,
                }
            )

            input_row = {
                "input_row_id": clean_text(row.get("input_row_id")),
                "matched_event_id": clean_text(row.get("matched_event_id")),
                "matched_esn": clean_text(row.get("matched_esn")),
                "candidate_til_num": clean_text(row.get("candidate_til_num")),
                "base_til_num": clean_text(row.get("base_til_num")),
                "from_serial_match": clean_text(row.get("from_serial_match")),
                "from_osa": clean_text(row.get("from_osa")),
                "candidate_revision": clean_text(row.get("candidate_revision")),
                "til_num_status": clean_text(row.get("til_num_status")),
                "disposition_status": clean_text(row.get("disposition_status")),
                "disposition_notes": clean_text(row.get("disposition_notes")),
                "applicable_to": clean_text(row.get("applicable_to")),
                "affected_units_technology": clean_text(row.get("affected_units_technology")),
                "context_event_type": clean_text(payload["outage_context"].get("context_event_type")),
                "ev_frame_type": clean_text(payload["unit_context"].get("ev_frame_type")),
                "ev_combustion_system": clean_text(payload["unit_context"].get("ev_combustion_system")),
                "ibat_combustion_system": clean_text(payload["unit_context"].get("ibat_combustion_system")),
                "ibat_primary_fuel": clean_text(payload["unit_context"].get("ibat_primary_fuel")),
                "til_context_mode": clean_text(payload["experiment_settings"].get("til_context_mode")),
                "enrichment_found": False,
                "til_profile_found": bool(export_profile_context.get("profile_found")),
                "til_profile_missing": not bool(export_profile_context.get("profile_found")),
                "til_profile_content_included": bool(payload["til_profile_context"].get("profile_content_included")),
                "til_profile_source": clean_text(export_profile_context.get("profile_source")),
                "til_profile_match_type": clean_text(export_profile_context.get("profile_match_type")),
                "til_profile_path": clean_text(export_profile_context.get("profile_path")),
                "til_profile_title": clean_text(export_profile_context.get("title")),
                "til_document_found": bool(payload["til_document_source"].get("document_found")),
                "til_document_missing": not bool(payload["til_document_source"].get("document_found")),
                "til_document_text_included": bool(payload["til_document_source"].get("document_text_included")),
                "til_document_source": clean_text(payload["til_document_source"].get("document_source")),
                "til_document_match_type": clean_text(payload["til_document_source"].get("match_type")),
                "til_document_pdf_filename": clean_text(payload["til_document_source"].get("pdf_filename")),
                "til_context_availability": (
                    "profile_and_document_found"
                    if bool(export_profile_context.get("profile_found")) and bool(payload["til_document_source"].get("document_found"))
                    else "profile_only"
                    if bool(export_profile_context.get("profile_found"))
                    else "document_only"
                    if bool(payload["til_document_source"].get("document_found"))
                    else "profile_and_document_missing"
                ),
                "til_line_items": join_output_list(export_profile_context.get("til_line_items", [])),
                "frame_families": join_output_list(export_profile_context.get("frame_families", [])),
                "combustion_systems": join_output_list(export_profile_context.get("combustion_systems", [])),
                "responsibility_hint": clean_text(export_profile_context.get("responsibility_hint")),
                "po_hint": clean_text(export_profile_context.get("po_hint")),
                "completion_criteria_text": clean_text(export_profile_context.get("completion_criteria_text")),
                "recommended_interval_or_trigger": join_output_list(export_profile_context.get("recommended_interval_or_trigger", [])),
                "sbom_dependency_flag": bool(payload["til_profile_context"].get("sbom_dependency_flag")),
                "sbom_trigger_reason": clean_text(payload["til_profile_context"].get("sbom_trigger_reason")),
                "sbom_check_status": clean_text(payload["sbom_context"].get("status")),
                "sbom_match_count": clean_text(payload["sbom_context"].get("match_count")),
                "sbom_source_type": clean_text(payload["sbom_context"].get("source_type")),
                "sbom_source_file": clean_text(payload["sbom_context"].get("source_file")),
                "sbom_strict_part_numbers": join_output_list(payload["sbom_context"].get("strict_part_numbers", [])),
                "sbom_strict_mli_numbers": join_output_list(payload["sbom_context"].get("strict_mli_numbers", [])),
                "sbom_matched_sections": join_output_list(payload["sbom_context"].get("matched_sections", [])),
                "sbom_condensed_matches": join_output_list(payload["sbom_context"].get("condensed_matches", [])),
                "information_only_flag": bool(payload["template_coverage"].get("information_only_flag")),
                "information_only_reason": clean_text(payload["template_coverage"].get("information_only_reason")),
                "information_only_evidence": join_output_list(payload["template_coverage"].get("information_only_evidence", [])),
                "template_coverage_status": clean_text(payload["template_coverage"].get("status")),
                "template_coverage_input_mode": clean_text(payload["template_coverage"].get("coverage_input_mode")),
                "template_coverage_limitations": join_output_list(payload["template_coverage"].get("coverage_limitations", [])),
                "template_coverage_class": clean_text(payload["template_coverage"].get("template_coverage_class")),
                "template_coverage_confidence": clean_text(payload["template_coverage"].get("template_coverage_confidence")),
                "matched_template_code": clean_text(payload["template_coverage"].get("matched_template_code")),
                "matched_template_display_name": clean_text(payload["template_coverage"].get("matched_template_display_name")),
                "matched_template_activity_ids": join_output_list(payload["template_coverage"].get("matched_template_activity_ids", [])),
                "matched_template_activity_texts": join_output_list(payload["template_coverage"].get("matched_template_activity_texts", [])),
                "covered_til_line_items": join_output_list(payload["template_coverage"].get("covered_til_line_items", [])),
                "template_gap_line_items": join_output_list(payload["template_coverage"].get("gap_til_line_items", [])),
                "template_unclear_til_line_items": join_output_list(payload["template_coverage"].get("unclear_til_line_items", [])),
                "template_overlap_reasoning": clean_text(payload["template_coverage"].get("template_overlap_reasoning")),
                "template_partial_coverage_notes": clean_text(payload["template_coverage"].get("template_partial_coverage_notes")),
                "template_review_flag": bool(payload["template_coverage"].get("template_review_flag")),
                "suppressed_by_standard_template": final_disposition == "template_covered_skip",
                "downstream_scope_basis": downstream_scope_basis,
                "prior_service_evidence_status": clean_text(payload["prior_service_evidence"].get("status")),
                "prior_service_evidence_source": clean_text(payload["prior_service_evidence"].get("source")),
                "prior_service_evidence_count": clean_text(payload["prior_service_evidence"].get("evidence_count")),
                "prior_service_report_count": clean_text(payload["prior_service_evidence"].get("report_count")),
                "prior_service_candidate_chunk_count": clean_text(payload["prior_service_evidence"].get("candidate_chunk_count")),
                "prior_service_retrieval_signal_source": clean_text(payload["prior_service_evidence"].get("retrieval_signal_source")),
                "prior_service_retrieval_query": clean_text(payload["prior_service_evidence"].get("retrieval_query")),
                "prior_service_retrieval_branches": join_output_list(payload["prior_service_evidence"].get("retrieval_branches", [])),
                "prior_service_retrieval_sql_tokens": join_output_list(payload["prior_service_evidence"].get("retrieval_sql_tokens", [])),
                "prior_service_evidence_source_systems": join_output_list(payload["prior_service_evidence"].get("evidence_source_systems", [])),
                "completion_review_status": clean_text(payload["completion_review"].get("status")),
                "completion_review_overall_completion_status": clean_text(payload["completion_review"].get("overall_completion_status")),
                "completion_review_applicability_impact": clean_text(payload["completion_review"].get("applicability_impact")),
                "completion_review_completed_line_item_count": clean_text(payload["completion_review"].get("completed_line_item_count")),
                "completion_review_unresolved_line_item_count": clean_text(payload["completion_review"].get("unresolved_line_item_count")),
                "completion_review_line_item_statuses": join_output_list(
                    [
                        f"{clean_text(item.get('line_item_id'))}:{clean_text(item.get('status'))}"
                        for item in payload["completion_review"].get("line_item_reviews", [])
                        if isinstance(item, dict)
                    ]
                ),
                "completion_review_confidence": clean_text(payload["completion_review"].get("confidence")),
            }
            summary_row = dict(input_row)
            summary_row.update(
                {
                    "pipeline_disposition": final_disposition,
                    "final_disposition": final_disposition,
                    "parsed_response_present": bool(parsed_response),
                    "llm_recommendation": clean_text(parsed_response.get("applicability_verdict")) if should_run_final_applicability else "",
                    "applicability_verdict": clean_text(parsed_response.get("applicability_verdict")) if should_run_final_applicability else "",
                    "reasoning_summary": clean_text(parsed_response.get("reasoning_summary")),
                    "why_applicable": join_output_list(parsed_response.get("why_applicable", [])),
                    "why_not_applicable": join_output_list(parsed_response.get("why_not_applicable", [])),
                    "unit_context_used": clean_text(parsed_response.get("unit_context_used")),
                    "document_context_used": clean_text(parsed_response.get("document_context_used")),
                    "structured_signals_used": join_output_list(parsed_response.get("structured_signals_used", [])),
                    "missing_information_needed": join_output_list(parsed_response.get("missing_information_needed", [])),
                    "suggested_next_checks": join_output_list(parsed_response.get("suggested_next_checks", [])),
                    "confidence": clean_text(parsed_response.get("confidence")),
                    "evidence_snippets": join_output_list(parsed_response.get("evidence_snippets", [])),
                    "llm_call_elapsed_sec": clean_text(llm_call_elapsed_sec),
                }
            )

            flattened_prompt_payload: dict[str, str] = {}
            flatten_mapping("prompt_payload", payload, flattened_prompt_payload)
            prompt_export_row = {
                "input_row_id": clean_text(row.get("input_row_id")),
                "matched_event_id": clean_text(row.get("matched_event_id")),
                "matched_esn": clean_text(row.get("matched_esn")),
                "candidate_til_num": clean_text(row.get("candidate_til_num")),
                "raw_response_present": bool(raw_response),
                "parsed_response_present": bool(parsed_response),
                "llm_call_elapsed_sec": clean_text(llm_call_elapsed_sec),
            }
            prompt_export_row.update(flattened_prompt_payload)

            summary_rows.append(summary_row)
            for item_status, item_values in (
                ("covered", payload["template_coverage"].get("covered_til_line_items", [])),
                ("gap", payload["template_coverage"].get("gap_til_line_items", [])),
                ("unclear", payload["template_coverage"].get("unclear_til_line_items", [])),
            ):
                for item_text in item_values if isinstance(item_values, list) else []:
                    template_line_item_rows.append(
                        {
                            "input_row_id": clean_text(row.get("input_row_id")),
                            "matched_event_id": clean_text(row.get("matched_event_id")),
                            "matched_esn": clean_text(row.get("matched_esn")),
                            "candidate_til_num": clean_text(row.get("candidate_til_num")),
                            "template_match_status": item_status,
                            "til_line_item_text": clean_text(item_text),
                            "matched_template_code": clean_text(payload["template_coverage"].get("matched_template_code")),
                            "matched_template_display_name": clean_text(payload["template_coverage"].get("matched_template_display_name")),
                            "matched_template_activity_ids": join_output_list(payload["template_coverage"].get("matched_template_activity_ids", [])),
                            "matched_template_activity_texts": join_output_list(payload["template_coverage"].get("matched_template_activity_texts", [])),
                            "template_overlap_reasoning": clean_text(payload["template_coverage"].get("template_overlap_reasoning")),
                            "template_review_flag": bool(payload["template_coverage"].get("template_review_flag")),
                        }
                    )
            for item in payload["completion_review"].get("line_item_reviews", []):
                if not isinstance(item, dict):
                    continue
                line_item_rows.append(
                    {
                        "input_row_id": clean_text(row.get("input_row_id")),
                        "matched_event_id": clean_text(row.get("matched_event_id")),
                        "matched_esn": clean_text(row.get("matched_esn")),
                        "candidate_til_num": clean_text(row.get("candidate_til_num")),
                        "prior_service_evidence_status": clean_text(payload["prior_service_evidence"].get("status")),
                        "prior_service_evidence_source_systems": join_output_list(payload["prior_service_evidence"].get("evidence_source_systems", [])),
                        "completion_review_status": clean_text(payload["completion_review"].get("status")),
                        "completion_review_overall_completion_status": clean_text(payload["completion_review"].get("overall_completion_status")),
                        "completion_review_confidence": clean_text(payload["completion_review"].get("confidence")),
                        "line_item_id": clean_text(item.get("line_item_id")),
                        "line_item_text": clean_text(item.get("line_item_text")),
                        "line_item_status": clean_text(item.get("status")),
                        "due_again_status": clean_text(item.get("due_again_status")),
                        "rationale": clean_text(item.get("rationale")),
                        "missing_data_needed": join_output_list(item.get("missing_data_needed", [])),
                    }
                )
            input_rows.append(input_row)
            prompt_rows.append(prompt_export_row)

    summary_df = pd.DataFrame(summary_rows)
    line_item_df = pd.DataFrame(line_item_rows)
    template_line_item_df = pd.DataFrame(template_line_item_rows)
    run_payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_candidate_csv": str(candidate_csv),
        "rows_input": int(len(case_df)),
        "prompt_pack": args.prompt_pack,
        "til_context_mode": args.til_context_mode,
        "til_profile_dir": str(args.til_profile_dir),
        "system_prompt_file": str(args.system_prompt_file) if args.system_prompt_file else "",
        "run_dir": str(run_dir),
        "system_prompt_path": str(system_prompt_path),
        "context_payload_path": str(context_payload_path),
        "template_coverage_records_path": str(template_coverage_records_path),
        "run_payload_markdown_path": str(run_payload_md_path),
        "summary_markdown_path": str(summary_md_path),
        "line_items_markdown_path": str(line_items_md_path),
        "template_line_items_markdown_path": str(template_line_items_md_path),
        "context_payload_markdown_path": str(context_payload_md_path),
        "template_coverage_markdown_path": str(template_coverage_md_path),
        "line_item_csv_path": str(line_item_csv_path),
        "template_line_item_csv_path": str(template_line_item_csv_path),
        "dry_run": bool(args.dry_run),
        "temperature": args.temperature,
    }
    run_payload.update(summarize_results(summary_df))

    summary_df.to_csv(csv_path, index=False)
    line_item_df.to_csv(line_item_csv_path, index=False)
    template_line_item_df.to_csv(template_line_item_csv_path, index=False)
    json_path.write_text(json.dumps(run_payload, indent=2), encoding="utf-8")
    write_prompt_artifacts(
        system_prompt_path=system_prompt_path,
        context_payload_path=context_payload_path,
        system_prompt=system_prompt,
        prompt_pack=args.prompt_pack,
        candidate_csv=candidate_csv,
        prompt_payload_rows=prompt_payload_rows,
    )
    write_template_coverage_artifacts(
        template_coverage_records_path=template_coverage_records_path,
        candidate_csv=candidate_csv,
        template_coverage_rows=template_coverage_artifact_rows,
    )
    write_excel_report(
        workbook_path,
        run_payload,
        summary_df,
        line_item_df,
        template_line_item_df,
        input_rows,
        prompt_rows,
        system_prompt,
        system_prompt_path,
        context_payload_path,
        template_coverage_records_path,
    )
    write_markdown_artifacts(
        run_payload_md_path=run_payload_md_path,
        summary_md_path=summary_md_path,
        line_items_md_path=line_items_md_path,
        template_line_items_md_path=template_line_items_md_path,
        context_payload_md_path=context_payload_md_path,
        template_coverage_md_path=template_coverage_md_path,
        run_payload=run_payload,
        summary_df=summary_df,
        line_item_df=line_item_df,
        template_line_item_df=template_line_item_df,
        prompt_payload_rows=prompt_payload_rows,
        template_coverage_rows=template_coverage_artifact_rows,
    )

    print(f"rows_input={len(case_df)}")
    print(f"parsed_response_rows={run_payload['parsed_response_rows']}")
    print(f"output_workbook={workbook_path}")
    print(f"output_csv={csv_path}")
    print(f"output_summary_markdown={summary_md_path}")
    print(f"output_json={json_path}")
    print(f"output_run_payload_markdown={run_payload_md_path}")
    print(f"output_jsonl={jsonl_path}")
    print(f"output_system_prompt={system_prompt_path}")
    print(f"output_context_payload={context_payload_path}")
    print(f"output_context_payload_markdown={context_payload_md_path}")
    print(f"output_template_coverage_records={template_coverage_records_path}")
    print(f"output_template_coverage_markdown={template_coverage_md_path}")
    print(f"output_template_line_items={template_line_item_csv_path}")
    print(f"output_line_items_markdown={line_items_md_path}")
    print(f"output_template_line_items_markdown={template_line_items_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
