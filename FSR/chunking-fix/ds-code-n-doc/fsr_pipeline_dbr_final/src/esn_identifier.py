"""
ESN Identification – one document-level LLM count call with uniform chunk tags.

The document is analyzed once, qualified ESNs are selected using the global
count and fraction thresholds, and every chunk in the document receives the
same ESN label set.
"""
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import fitz
import httpx

from config import LITELLM_BASE_URL, LITELLM_API_KEY, SECRET_SCOPE, CERT_PATH, CORP_PROXY
from pymupdf_guard import hold_pymupdf_lock
from utils import setup_logger

logger = setup_logger("esn_identifier")
logger.setLevel(logging.WARNING)

ESN_LLM_MODEL = os.getenv("ESN_LLM_MODEL", "azure-gpt-4o")
ESN_LLM_MAX_RETRIES = int(os.getenv("ESN_LLM_MAX_RETRIES", "5"))
ESN_LLM_RETRY_BASE_DELAY_SEC = float(os.getenv("ESN_LLM_RETRY_BASE_DELAY_SEC", "2.0"))
MIN_ESN_COUNT = 5
MIN_ESN_FRACTION = 0.10
DOC_TRUNCATE_WINDOW_CHARS = 1000
DOC_MAX_LLM_CHARS = DOC_TRUNCATE_WINDOW_CHARS * 3

_VALID_ESN_RE = re.compile(r"^[A-Z0-9]{4,12}$", re.IGNORECASE)
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

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


def _build_http_client() -> httpx.Client:
    """Build an httpx client respecting corporate proxy/cert settings."""
    verify = str(CERT_PATH) if CERT_PATH and Path(CERT_PATH).exists() else True
    base_host = (urlparse(LITELLM_BASE_URL).hostname or "").lower()
    bypass_proxy = base_host.endswith("research.gevernova.net")
    client_kwargs = {"verify": verify, "timeout": 120.0, "trust_env": False}
    if CORP_PROXY and not bypass_proxy:
        try:
            return httpx.Client(proxy=CORP_PROXY, **client_kwargs)
        except TypeError:
            return httpx.Client(proxies=CORP_PROXY, **client_kwargs)
    return httpx.Client(**client_kwargs)


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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _prepare_document_text_for_llm(text: str) -> str:
    """Keep the full document when possible, otherwise use start/middle/end windows."""
    normalized = _normalize_text(text)
    if len(normalized) <= DOC_MAX_LLM_CHARS:
        return normalized

    window = DOC_TRUNCATE_WINDOW_CHARS
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


def prepare_document_text_for_esn(document_text: str) -> str:
    """Prepare the preloaded document text once before dispatching LLM work."""
    return _prepare_document_text_for_llm(document_text)


def _extract_document_text(pdf_path: str) -> str:
    with hold_pymupdf_lock():
        try:
            doc = fitz.open(pdf_path)
        except Exception as exc:
            raise RuntimeError(f"Failed to open PDF for ESN text preload: {exc}") from exc

        try:
            pages = []
            for page in doc:
                page_text = _normalize_text(page.get_text("text"))
                if page_text:
                    pages.append(page_text)
            return "\n\n".join(pages)
        finally:
            doc.close()


def load_document_text_for_esn(pdf_path: str) -> str:
    """Load the full document text once on the caller thread."""
    return _extract_document_text(pdf_path)


def analyze_prepared_document_text_for_esn_counts(prepared_document_text: str) -> Dict[str, int]:
    """Run one LLM call over already-prepared document text."""
    if not LITELLM_API_KEY or not LITELLM_API_KEY.strip():
        raise RuntimeError(
            f"[ESN-LLM] Missing LITELLM_API_KEY in secret scope '{SECRET_SCOPE}'."
        )

    if not prepared_document_text:
        return {}

    url = LITELLM_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {LITELLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": ESN_LLM_MODEL,
        "messages": [
            {"role": "system", "content": _DOC_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _DOC_USER_TEMPLATE.format(document_text=prepared_document_text),
            },
        ],
        "max_completion_tokens": 400,
        "temperature": 0,
    }
    raw = ""
    last_error: BaseException | None = None

    with _build_http_client() as client:
        for attempt in range(1, ESN_LLM_MAX_RETRIES + 1):
            raw = ""
            try:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    if resp.status_code in _TRANSIENT_STATUS_CODES and attempt < ESN_LLM_MAX_RETRIES:
                        time.sleep(ESN_LLM_RETRY_BASE_DELAY_SEC * attempt)
                        last_error = error
                        continue
                    raise error

                raw = resp.json()["choices"][0]["message"]["content"].strip()
                return _parse_esn_count_response(raw)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                preview = (raw or "")[:5000].replace("\n", "\\n")
                raise RuntimeError(
                    f"[ESN-LLM] Failed to parse doc-level response: {exc}. Raw preview: {preview}"
                ) from exc
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                if attempt < ESN_LLM_MAX_RETRIES:
                    time.sleep(ESN_LLM_RETRY_BASE_DELAY_SEC * attempt)
                    last_error = exc
                    continue
                last_error = exc
                break
            except BaseException as exc:
                last_error = exc
                break

    if last_error is None:
        last_error = RuntimeError("Unknown doc-level LLM failure")
    raise RuntimeError(
        f"[ESN-LLM] Doc-level call failed ({type(last_error).__name__}): {last_error}"
    ) from last_error


def analyze_document_text_for_esn_counts(document_text: str) -> Dict[str, int]:
    """Run one LLM call over already-loaded document text."""
    return analyze_prepared_document_text_for_esn_counts(
        prepare_document_text_for_esn(document_text)
    )


def analyze_pdf_for_esn_counts(pdf_path: str) -> Dict[str, int]:
    """Run one LLM call over the full document and return raw ESN counts."""
    return analyze_document_text_for_esn_counts(load_document_text_for_esn(pdf_path))


def _qualify_esn_counts(
    counts: Dict[str, int],
    min_count: int,
    min_fraction: float,
) -> List[str]:
    total_mentions = sum(counts.values())
    if total_mentions <= 0:
        return []

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        esn
        for esn, count in ranked
        if count >= min_count and (count / total_mentions) >= min_fraction
    ]


def _fallback_generator_serial(meta: Dict[str, Any]) -> List[str]:
    fallback = _normalize_esn_token(meta.get("generator_serial"))
    return [fallback] if fallback else []


def identify_esns(
    chunks: List[Dict],
    doc_counts: Optional[Dict[str, int]] = None,
    min_count: int = MIN_ESN_COUNT,
    min_fraction: float = MIN_ESN_FRACTION,
) -> List[Dict]:
    """Apply one document-level ESN label set to every chunk."""
    if not chunks:
        return chunks

    qualified_doc_esns = _qualify_esn_counts(doc_counts or {}, min_count, min_fraction)

    for chunk in chunks:
        meta = chunk.setdefault("metadata", {})

        if qualified_doc_esns:
            final_labels = list(qualified_doc_esns)
            meta["esn_assignment_scope"] = "document"
        else:
            final_labels = _fallback_generator_serial(meta)
            meta["esn_assignment_scope"] = "fallback" if final_labels else "none"

        meta["chunk_esns"] = list(final_labels)
        meta["esn_labels"] = list(final_labels)
        if final_labels:
            meta["generator_serial"] = final_labels[0]

    return chunks