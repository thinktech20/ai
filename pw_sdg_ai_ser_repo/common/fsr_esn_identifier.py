# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# fsr_esn_identifier — Tier 2: LLM-based ESN frequency analysis
#
# Adapted from DS Experiments/fsr_pipeline_dbr_final/src/esn_identifier.py
# (original by DS team; adapted for pipeline use in #664196)
#
# Analyzes document text with one LLM call to count ESN mentions.
# ESNs that meet the minimum count + fraction thresholds are qualified.
# Used by P2 (nb_sdg_fsr_chunks) and by the backfill notebook (Tier 3).
#
# Public API:
#   analyze_document_text_for_esn_counts(text: str) -> Dict[str, int]
#   qualify_esn_counts(counts, min_count, min_fraction) -> List[str]
#
# Config consumed from fsr_config (already %run before this file):
#   FSR_ESN_DETECT_ENABLED, FSR_ESN_LLM_MODEL, FSR_ESN_MIN_COUNT,
#   FSR_ESN_MIN_FRACTION, LITELLM_BASE_URL, LITELLM_API_KEY, LLM_VERIFY_SSL
# ─────────────────────────────────────────────────────────────────────────────

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger("fsr.esn_identifier")

# ─── Constants ───────────────────────────────────────────────────────────────

_VALID_ESN_RE = re.compile(r"^[A-Z0-9]{4,12}$", re.IGNORECASE)
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

# Document truncation — keep start, middle, end windows when doc is too long.
_DOC_TRUNCATE_WINDOW_CHARS = 1000
_DOC_MAX_LLM_CHARS = _DOC_TRUNCATE_WINDOW_CHARS * 3

_ESN_MAX_RETRIES = 3
_ESN_RETRY_BASE_DELAY_SEC = 2.0

_DOC_SYSTEM_PROMPT = """\
You identify equipment serial numbers (ESNs) in field service report text.

Rules:
- An ESN is a 4-12 character alphanumeric code identifying a gas turbine or generator.
- Count only explicit ESN mentions across the full document.
- Keys in the JSON response must be the ESN values themselves.
- Values must be integer mention counts.
- Do not infer missing ESNs.
- Do not return part numbers, ER case numbers, dates, TIL numbers, page numbers, or other non-ESN identifiers.
- If no ESNs are explicitly mentioned, return {}.

Respond with ONLY a JSON object, for example {"297837": 7, "290T658": 2}.
No markdown. No prose. No explanation.
"""

_DOC_USER_TEMPLATE = """\
Count explicit ESN mentions in this field service report.

Return ONLY a JSON object whose keys are ESNs and whose values are integer counts.
Return all explicit ESN counts you can find across the full document, including counts below 5.
The downstream pipeline applies the minimum-count and percentage thresholds.

Document text:
{document_text}
"""


# ─── JSON parsing helpers ─────────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    parts = t.split("```")
    if len(parts) >= 3:
        inner = parts[1].strip()
        if inner.lower().startswith("json"):
            inner = inner[4:].strip()
        return inner
    return t


def _extract_first_json_container(text: str) -> str:
    start = None
    stack: List[str] = []
    in_string = False
    escaped = False
    pairs = {"{": "}", "[": "]"}
    closers = set(pairs.values())

    for i, ch in enumerate(text):
        if start is None:
            if ch in pairs:
                start = i
                stack = [ch]
                in_string = False
                escaped = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch in pairs:
            stack.append(ch)
        elif ch in closers and stack:
            opener = stack[-1]
            if pairs.get(opener) == ch:
                stack.pop()
            if not stack:
                return text[start:i + 1]

    raise ValueError("No balanced JSON object/array found in LLM response")


def _repair_truncated_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise ValueError("No opening '{' found for truncated JSON repair")

    depth = 0
    in_string = False
    escaped = False
    last_top_level_comma = -1

    for i, ch in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch in "{[":
            depth += 1
        elif ch in "}]":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 1:
            last_top_level_comma = i

    if last_top_level_comma < 0:
        raise ValueError("No top-level comma found for truncated JSON repair")

    repaired = text[start:last_top_level_comma].rstrip()
    if repaired.endswith(","):
        repaired = repaired[:-1].rstrip()
    repaired += "}"
    return repaired


def _normalize_esn_token(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    token = value.strip().strip('"\'[]()')
    if not token:
        return None
    token = token.upper()
    if not _VALID_ESN_RE.match(token):
        return None
    return token


def _coerce_positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(round(value)) if value > 0 else None
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except (TypeError, ValueError):
            return None
        return int(round(parsed)) if parsed > 0 else None
    return None


def _normalize_esn_count_payload(parsed: Any) -> Dict[str, int]:
    if not isinstance(parsed, dict):
        raise ValueError("Expected JSON object mapping ESN -> count")
    counts: Dict[str, int] = {}
    for raw_esn, raw_count in parsed.items():
        esn = _normalize_esn_token(raw_esn)
        count = _coerce_positive_int(raw_count)
        if not esn or count is None:
            continue
        counts[esn] = counts.get(esn, 0) + count
    return counts


def _parse_esn_count_response(raw: str) -> Dict[str, int]:
    cleaned = _strip_markdown_fences(raw)

    try:
        json_text = _extract_first_json_container(cleaned)
        parsed = json.loads(json_text)
        return _normalize_esn_count_payload(parsed)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    try:
        repaired = _repair_truncated_json_object(cleaned)
        parsed = json.loads(repaired)
        return _normalize_esn_count_payload(parsed)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    normalized = cleaned.strip().lower()
    if normalized in {"", "{}", "[]", "none", "null", "no esn", "no esns"}:
        return {}

    raise ValueError("Unable to parse ESN count response as JSON object")


# ─── Text preparation ─────────────────────────────────────────────────────────

def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def prepare_document_text_for_esn(text: str) -> str:
    """Keep the full document when possible, otherwise sample start/middle/end."""
    normalized = _normalize_text(text)
    if len(normalized) <= _DOC_MAX_LLM_CHARS:
        return normalized

    window = _DOC_TRUNCATE_WINDOW_CHARS
    middle_start = max(
        window,
        min((len(normalized) // 2) - (window // 2), len(normalized) - (2 * window)),
    )
    middle_end = middle_start + window

    return "\n...\n".join([
        normalized[:window],
        normalized[middle_start:middle_end],
        normalized[-window:],
    ])


# ─── LLM call ─────────────────────────────────────────────────────────────────

def analyze_document_text_for_esn_counts(document_text: str) -> Dict[str, int]:
    """Analyze document text with one LLM call. Returns {esn: mention_count}.

    Uses LITELLM_BASE_URL, LITELLM_API_KEY, LLM_VERIFY_SSL and FSR_ESN_LLM_MODEL
    from fsr_config (must be %run before this notebook).

    Raises RuntimeError on unrecoverable failures. Transient HTTP errors are
    retried up to _ESN_MAX_RETRIES times.
    """
    if not LITELLM_API_KEY or not LITELLM_API_KEY.strip():
        raise RuntimeError("[ESN-LLM] LITELLM_API_KEY not set — cannot run ESN detection")

    prepared = prepare_document_text_for_esn(document_text)
    if not prepared:
        return {}

    base = LITELLM_BASE_URL.rstrip("/")
    urls = [f"{base}/v1/chat/completions", f"{base}/chat/completions"]
    headers = {
        "Authorization": f"Bearer {LITELLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": FSR_ESN_LLM_MODEL,
        "messages": [
            {"role": "system", "content": _DOC_SYSTEM_PROMPT},
            {"role": "user", "content": _DOC_USER_TEMPLATE.format(document_text=prepared)},
        ],
        "max_completion_tokens": 400,
        "temperature": 0,
    }

    last_error = None
    for attempt in range(1, _ESN_MAX_RETRIES + 1):
        for url in urls:
            try:
                resp = requests.post(url, headers=headers, json=payload,
                                     timeout=120, verify=LLM_VERIFY_SSL)
                if resp.status_code == 404:
                    continue
                if resp.status_code in _TRANSIENT_STATUS_CODES and attempt < _ESN_MAX_RETRIES:
                    last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    time.sleep(_ESN_RETRY_BASE_DELAY_SEC * attempt)
                    break
                resp.raise_for_status()
                raw = resp.json()["choices"][0]["message"]["content"].strip()
                return _parse_esn_count_response(raw)
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(f"[ESN-LLM] Unexpected response structure: {exc}") from exc
            except requests.exceptions.RequestException as exc:
                if attempt < _ESN_MAX_RETRIES:
                    last_error = exc
                    time.sleep(_ESN_RETRY_BASE_DELAY_SEC * attempt)
                    break
                raise RuntimeError(f"[ESN-LLM] Network error after {attempt} attempts: {exc}") from exc

    raise RuntimeError(
        f"[ESN-LLM] Failed after {_ESN_MAX_RETRIES} attempts. Last error: {last_error}"
    )


# ─── Threshold qualification ──────────────────────────────────────────────────

def qualify_esn_counts(
    counts: Dict[str, int],
    min_count: int = 5,
    min_fraction: float = 0.10,
) -> List[str]:
    """Return ESNs that meet count + fraction thresholds, sorted by frequency desc.

    Args:
        counts:       {esn: mention_count} from analyze_document_text_for_esn_counts()
        min_count:    minimum raw mention count (default: FSR_ESN_MIN_COUNT = 5)
        min_fraction: minimum fraction of total mentions (default: FSR_ESN_MIN_FRACTION = 0.10)

    Returns:
        List of qualifying ESN strings, ranked by count descending.
    """
    total = sum(counts.values())
    if total <= 0:
        return []
    return [
        esn
        for esn, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        if count >= min_count and (count / total) >= min_fraction
    ]
