"""Prompt assembly: formats heatmap, IBAT, FSR, ER dicts into the LLM user prompt.

Accepts raw dicts (as produced by chain.py) — no dependency on IssueContext.
Adds chunk deduplication and per-chunk truncation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List

from .config import clean_scalar

_NAN_RE = re.compile(r":\s*nan\b", flags=re.IGNORECASE)

_IBAT_FIELDS = [
    ("equip_serial_number", "Serial Number"),
    ("equipment_name", "Plant"),
    ("equipment_model", "Equipment Model"),
    ("equipment_code", "Equipment Code"),
    ("cooling_system", "Cooling System"),
    ("excitation_system", "Excitation System"),
    ("equipment_status", "Status"),
    ("original_apparent_pwr_mva", "Capacity MVA"),
    ("present_voltage_v", "Voltage"),
    ("speed_rpm", "Speed RPM"),
    ("equipment_comm_date", "Commission Date"),
    ("contract_type", "Contract Type"),
    ("csa_contract_number", "CSA Contract"),
    ("er_support_level", "ER Support Level"),
    ("rotor_rewind", "Rotor Rewind"),
    ("stator_rewind", "Stator Rewind"),
]

_SEVERITY_LABELS = {
    "severity_criteria_0_no_data": "Not Mentioned",
    "severity_criteria_1_light": "Light",
    "severity_criteria_2_medium": "Medium",
    "severity_criteria_3_heavy": "Heavy",
    "severity_criteria_4_immediate": "Immediate",
}


@dataclass(slots=True)
class PromptBuildResult:
    user_prompt: str
    fsr_chunk_count: int
    er_chunk_count: int


# ── Helpers ──────────────────────────────────────────────────────

def _truncate(value: Any, max_chars: int) -> str:
    text = clean_scalar(value)
    if not text:
        return "N/A"
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " ... [truncated]"


def _normalize_prompt_scalar(value: Any) -> str:
    text = clean_scalar(value)
    if text.lower() in {"", "none", "null", "n/a", "nan"}:
        return ""
    return text


def _dedupe_chunks(chunks: List[Dict], key_fields: tuple[str, ...]) -> List[Dict]:
    seen: set[tuple[str, ...]] = set()
    unique: List[Dict] = []
    for c in chunks:
        key = tuple(clean_scalar(c.get(f, "")) for f in key_fields)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _select_chunks(chunks: List[Dict], max_items: int, key_fields: tuple[str, ...]) -> List[Dict]:
    return _dedupe_chunks(chunks, key_fields)[:max_items]


# ── Section formatters ───────────────────────────────────────────

def format_ibat_section(ibat: Dict) -> str:
    if not ibat:
        return "IBAT DATA:\nNo IBAT data available."
    lines = ["IBAT DATA:"]
    for field_name, label in _IBAT_FIELDS:
        lines.append(f"{label}: {clean_scalar(ibat.get(field_name, '')) or 'N/A'}")
    return "\n".join(lines)


def format_heatmap_section(heatmap: Dict) -> str:
    if not heatmap:
        return "HEATMAP QUESTION:\nNo heatmap data available."
    lines = [
        "HEATMAP QUESTION:",
        f"Component: {clean_scalar(heatmap.get('component', '')) or 'N/A'}",
        f"Issue Name: {clean_scalar(heatmap.get('issue_name', '')) or 'N/A'}",
        f"Issue Grouping: {clean_scalar(heatmap.get('issue_grouping', '')) or 'N/A'}",
        f"Issue Question: {clean_scalar(heatmap.get('issue_prompt', '')) or 'N/A'}",
        "Severity Criteria:",
    ]
    for col, label in _SEVERITY_LABELS.items():
        val = clean_scalar(heatmap.get(col, ""))
        if val:
            lines.append(f"  {label}: {val}")
    return "\n".join(lines)


def format_fsr_section(chunks: List[Dict], max_chunk_chars: int = 10000) -> str:
    if not chunks:
        return "No FSR chunks available."
    parts: List[str] = []
    for i, c in enumerate(chunks, 1):
        section_values = [_normalize_prompt_scalar(c.get(f"section_{idx}", "")) for idx in range(1, 6)]
        section_path = " > ".join(value for value in section_values if value)
        start_page = _normalize_prompt_scalar(c.get("start_page", c.get("page_number", "")))
        end_page = _normalize_prompt_scalar(c.get("end_page", c.get("page_number", "")))
        if start_page and end_page:
            page_range = start_page if start_page == end_page else f"{start_page}-{end_page}"
        else:
            page_range = start_page or end_page or "N/A"
        parts.append(
            f"--- FSR Chunk {i} ---\n"
            f"Chunk ID: {clean_scalar(c.get('chunk_id', '')) or 'N/A'}\n"
            f"Report Name: {clean_scalar(c.get('report_name', c.get('pdf_name', ''))) or 'N/A'}\n"
            f"Page Range: {page_range}\n"
            f"Serial: {clean_scalar(c.get('generator_serial', '')) or 'N/A'}\n"
            f"Start Date: {clean_scalar(c.get('start_date', '')) or 'N/A'}\n"
            f"End Date: {clean_scalar(c.get('end_date', '')) or 'N/A'}\n"
            f"Section Path: {section_path or 'N/A'}\n"
            f"Event Type: {clean_scalar(c.get('event_type', '')) or 'N/A'}\n"
            f"Outage Type: {clean_scalar(c.get('outage_type', '')) or 'N/A'}\n"
            f"Technology Type: {clean_scalar(c.get('technology_type', '')) or 'N/A'}\n"
            f"Report Unit Status: {clean_scalar(c.get('report_unit_status', '')) or 'N/A'}\n"
            f"Score: {clean_scalar(c.get('score', '')) or 'N/A'}\n"
            f"Context: {_truncate(c.get('chunk_text', ''), max_chunk_chars)}"
        )
    return "\n\n".join(parts)


def format_er_section(chunks: List[Dict], max_chunk_chars: int = 10000) -> str:
    if not chunks:
        return "No ER chunks available."
    parts: List[str] = []
    for i, c in enumerate(chunks, 1):
        parts.append(
            f"--- ER Chunk {i} ---\n"
            f"Chunk ID: {clean_scalar(c.get('chunk_id', '')) or 'N/A'}\n"
            f"ER Number: {clean_scalar(c.get('er_number', '')) or 'N/A'}\n"
            f"Chunk Index: {clean_scalar(c.get('chunk_index', '')) or '0'}\n"
            f"Opened At: {clean_scalar(c.get('opened_at', '')) or 'N/A'}\n"
            f"Component: {clean_scalar(c.get('u_component', '')) or 'N/A'}\n"
            f"Status: {clean_scalar(c.get('status', '')) or 'N/A'}\n"
            f"Field Action Taken: {clean_scalar(c.get('u_field_action_taken', '')) or 'N/A'}\n"
            f"Score: {clean_scalar(c.get('score', '')) or 'N/A'}\n"
            f"Context: {_truncate(c.get('chunk_text', c.get('Text', '')), max_chunk_chars)}"
        )
    return "\n\n".join(parts)


# ── Public API ───────────────────────────────────────────────────

def build_user_prompt(
    ibat: Dict,
    heatmap: Dict,
    fsr_chunks: List[Dict],
    er_chunks: List[Dict],
    max_fsr_chunks: int = 20,
    max_er_chunks: int = 20,
    max_chunk_chars: int = 10000,
) -> PromptBuildResult:
    """Assemble the full user prompt from all 4 data sources."""
    selected_fsr = _select_chunks(fsr_chunks, max_fsr_chunks, ("chunk_id", "pdf_name", "page_number"))
    selected_er = _select_chunks(er_chunks, max_er_chunks, ("chunk_id", "er_number", "chunk_index", "opened_at"))

    parts = [
        "=== HEATMAP_QUESTION ===",
        format_heatmap_section(heatmap),
        "",
        "=== IBAT ===",
        format_ibat_section(ibat),
        "",
        "=== FSR_CHUNKS ===",
        format_fsr_section(selected_fsr, max_chunk_chars),
        "",
        "=== ER_CHUNKS ===",
        format_er_section(selected_er, max_chunk_chars),
    ]

    prompt = "\n".join(parts)
    prompt = _NAN_RE.sub(": N/A", prompt)

    return PromptBuildResult(
        user_prompt=prompt,
        fsr_chunk_count=len(selected_fsr),
        er_chunk_count=len(selected_er),
    )
