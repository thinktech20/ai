"""Stage 4A — LLM Normalization.

Contains the cover-page/admin field normalization logic used by FSR v2 P1
metadata enrichment.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from common.fsr_v2.enums import LLMExtractionPromptVersion
from common.fsr_v2.prompts.normalization_prompt import (
    NORMALIZATION_PROMPT_SUFFIX as NORMALIZATION_PROMPT_SUFFIX_V2_WITH_HINTS,
    SYSTEM_PROMPT as SYSTEM_PROMPT_V2_WITH_HINTS,
)

_COLUMN_MAP = {
    "ESN": "esn",
    "Equipment Sys ID": "equipment_sys_id",
    "Equipment Type": "equipment_type",
    "Equipment Class / Code": "equipment_class_code",
    "Event Type": "event_type",
    "EV Project ID": "ev_project_id",
    "EV Equipment Event ID": "ev_equipment_event_id",
    "OFS Event ID": "ofs_event_id",
    "FSP project ID": "fsp_project_id",
    "Project ID": "xxx_project_id",
    "PDF Name / path / identifier": "_volume_path",
    "FSR Number (#)": "fsr_number",
    "Report Issued Date": "report_issued_date",
    "Outage Start Date": "outage_start_date",
    "Outage End Date": "outage_end_date",
    "Job Start Date": "job_start_date",
    "Approved Date": "approved_date",
}

_PROMPT_VARIANTS: dict[str, tuple[str, str]] = {
    LLMExtractionPromptVersion.V2_WITH_HINTS.value: (
        SYSTEM_PROMPT_V2_WITH_HINTS,
        NORMALIZATION_PROMPT_SUFFIX_V2_WITH_HINTS,
    ),
}


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_llm_json_object(raw: str) -> dict:
    """Best-effort JSON object parsing for LLM responses."""
    cleaned = _strip_json_fences(raw)

    candidates: list[str] = [cleaned]
    left = cleaned.find("{")
    right = cleaned.rfind("}")
    if left != -1 and right != -1 and left < right:
        candidates.append(cleaned[left : right + 1])

    for cand in candidates:
        text = cand.strip()
        if not text:
            continue
        text = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue

    raise ValueError("LLM response is not a valid JSON object")


def _build_llm_fields_from_page1(page1_text: str, volume_path: str) -> dict:
    llm_fields = {"PDF Name / path / identifier": volume_path}
    lines = (page1_text or "").splitlines()
    current_key = None
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if key in llm_fields:
                llm_fields[key] = f"{llm_fields[key]} | {value}"
            else:
                llm_fields[key] = value
        elif current_key:
            llm_fields[current_key] += " " + line.strip()
    return llm_fields


def _map_llm_row(row: dict) -> dict:
    """Map one LLM response row through _COLUMN_MAP and clean values."""
    mapped = {_COLUMN_MAP.get(k, k): v for k, v in row.items() if k in _COLUMN_MAP}
    mapped.pop("_volume_path", None)
    out = {}
    for key, value in mapped.items():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            out[key] = text
    return out


def _call_llm(
    prompt: str,
    system_prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    verify_ssl: Any = True,
) -> str:
    import requests  # noqa: PLC0415

    base = base_url.rstrip("/")
    urls = [f"{base}/chat/completions", f"{base}/v1/chat/completions"]
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(1, 4):
        for url in urls:
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=120, verify=verify_ssl)
                if resp.status_code == 404:
                    continue
                if not resp.ok:
                    body = (resp.text or "")[:2000]
                    raise requests.HTTPError(f"{resp.status_code} {resp.reason} body={body}")
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                last_err = e
                if attempt < 3:
                    time.sleep(5 * (2 ** (attempt - 1)))
    raise RuntimeError(f"LLM call failed after all retries: {last_err}")


def extract_llm_metadata(
    page1_text: str,
    volume_path: str,
    hints: str,
    *,
    llm_extraction_prompt_version: str,
    llm_base_url: str,
    llm_api_key: str,
    llm_model: str,
    llm_verify_ssl: Any = True,
) -> dict:
    """Run normalization prompt for a single document."""
    result = batch_extract_llm_metadata(
        [{"page1_text": page1_text, "volume_path": volume_path, "hints": hints}],
        llm_extraction_prompt_version=llm_extraction_prompt_version,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        llm_verify_ssl=llm_verify_ssl,
    )
    return result.get(volume_path, {})


def batch_extract_llm_metadata(
    docs: list[dict],
    *,
    llm_extraction_prompt_version: str,
    llm_base_url: str,
    llm_api_key: str,
    llm_model: str,
    llm_verify_ssl: Any = True,
) -> dict[str, dict]:
    """Run normalization prompt for a batch of documents.

    Args:
        docs: list of {"page1_text", "volume_path", "hints"} dicts.

    Returns:
        {volume_path: llm_meta_dict} — missing keys mean no LLM row for that doc.
    """
    system_prompt, prompt_suffix = _PROMPT_VARIANTS.get(llm_extraction_prompt_version, (None, None))
    if not system_prompt or not prompt_suffix:
        supported = ", ".join(sorted(_PROMPT_VARIANTS))
        raise ValueError(
            f"Unsupported llm_extraction_prompt_version={llm_extraction_prompt_version!r}; "
            f"supported values: {supported}"
        )

    fields_list = []
    for item in docs:
        f = _build_llm_fields_from_page1(item.get("page1_text") or "", item["volume_path"])
        if item.get("hints", "").strip():
            f["_preprocessor_hints"] = item["hints"].strip()
        fields_list.append(f)

    prompt = (
        f"Here is a JSON list of PDF fields:\n{json.dumps(fields_list, indent=2)}\n\n"
        + prompt_suffix
    )
    raw = _call_llm(prompt, system_prompt, llm_base_url, llm_api_key, llm_model, llm_verify_ssl)
    cleaned = _strip_json_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except Exception:
        parsed = _parse_llm_json_object(cleaned)

    if isinstance(parsed, dict) and "FSR_data" in parsed:
        parsed = parsed["FSR_data"]
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        return {}

    result: dict[str, dict] = {}
    for row in parsed:
        vp = None
        for key in ("PDF Name / path / identifier", "_volume_path"):
            vp = row.get(key)
            if vp:
                break
        if not vp:
            continue
        vp = str(vp).strip()
        result[vp] = _map_llm_row(row)
    return result
