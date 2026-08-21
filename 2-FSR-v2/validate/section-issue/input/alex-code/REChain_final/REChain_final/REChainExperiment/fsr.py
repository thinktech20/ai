"""Step 4: Retrieve FSR (Field Service Report) chunks from Databricks Vector Search."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Sequence, Tuple

import requests

from .config import (
    FSR_CHUNK_TABLE,
    FSR_PDF_REF_VIEW,
    FSR_REPORT_VIEW,
    FSR_SCRAPED_MAPPING_VIEW,
    VS_INDEX_NAME,
    VS_TOKEN,
    VS_WORKSPACE_URL,
    get_db_connection,
    require_setting,
)
from .retry import RETRIABLE_STATUS_CODES, retry_request
from .vector_embeddings import get_query_vector

RETURN_COLUMNS = [
    "chunk_id", "pdf_name", "page_number", "chunk_text", "generator_serial",
]

PDF_REF_FILE_STEM_COLUMN = "s3_filename"
PDF_REF_DISPLAY_NAME_COLUMN = "PDF_name"
PDF_REF_ESN_COLUMN = "esn"
PDF_REF_EVENT_ID_COLUMN = "ev_equipment_event_id"

SCRAPED_MAPPING_FILE_COLUMN = "pdf_name"

FSR_REPORT_EVENT_ID_COLUMN = "event_id"
FSR_REPORT_ESN_COLUMN = "esn"
FSR_REPORT_STATUS_COLUMN = "report_unit_status"
FSR_REPORT_START_DATE_COLUMN = "start_date"
FSR_REPORT_END_DATE_COLUMN = "end_date"
FSR_REPORT_NAME_COLUMN = "report_name"

_SIMPLE_JSON_TYPES = (str, int, float, bool)


def _sql_quote(value: Any) -> str:
    return str(value).replace("'", "''")


def _sql_string_list(values: Sequence[Any]) -> str:
    cleaned = [f"'{_sql_quote(value)}'" for value in values if value is not None and str(value) != ""]
    if not cleaned:
        return "(NULL)"
    return "(" + ", ".join(cleaned) + ")"


def _lookup_ci(row: Dict[str, Any], *keys: str) -> Any:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def _normalize_pdf_key(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    if text.lower().endswith(".pdf"):
        text = text[:-4]
    return text


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, _SIMPLE_JSON_TYPES):
        return value
    return str(value)


def _json_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _json_safe(value) for key, value in row.items()}


def _query_sql(statement: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(statement)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _safe_parse_metadata(raw_value: Any) -> Dict[str, Any]:
    if isinstance(raw_value, dict):
        return raw_value
    text = str(raw_value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _pdf_ref_file_key(row: Dict[str, Any]) -> str:
    return _normalize_pdf_key(
        _lookup_ci(row, "s3_filename", "filename", "pdf_name", "PDF_name") or ""
    )


def _scraped_mapping_file_key(row: Dict[str, Any]) -> str:
    return _normalize_pdf_key(
        _lookup_ci(row, "filename", "pdf_name", "PDF_name", "s3_filename") or ""
    )


def _chunk_rows_by_id(chunk_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    if not chunk_ids:
        return {}
    statement = f"""
SELECT *
FROM {FSR_CHUNK_TABLE}
WHERE chunk_id IN {_sql_string_list(chunk_ids)}
ORDER BY chunk_id
"""
    rows = _query_sql(statement)
    return {str(row.get("chunk_id")): row for row in rows}


def _pdf_ref_rows(pdf_names: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not pdf_names:
        return {}
    normalized_pdf_names = list(dict.fromkeys(_normalize_pdf_key(name) for name in pdf_names if name))
    pdf_name_variants: List[str] = []
    for name in normalized_pdf_names:
        pdf_name_variants.append(name)
        pdf_name_variants.append(f"{name}.pdf")
    statement = f"""
SELECT *
FROM {FSR_PDF_REF_VIEW}
WHERE {PDF_REF_FILE_STEM_COLUMN} IN {_sql_string_list(normalized_pdf_names)}
   OR {PDF_REF_DISPLAY_NAME_COLUMN} IN {_sql_string_list(pdf_name_variants)}
ORDER BY {PDF_REF_FILE_STEM_COLUMN}, {PDF_REF_DISPLAY_NAME_COLUMN}, {PDF_REF_ESN_COLUMN}, {PDF_REF_EVENT_ID_COLUMN}
"""
    rows = _query_sql(statement)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_pdf_ref_file_key(row), []).append(row)
    return grouped


def _scraped_mapping_rows(pdf_names: Sequence[str]) -> Dict[str, List[Dict[str, Any]]]:
    if not pdf_names:
        return {}
    normalized_pdf_names = list(dict.fromkeys(_normalize_pdf_key(name) for name in pdf_names if name))
    like_clauses = [
        f"LOWER({SCRAPED_MAPPING_FILE_COLUMN}) LIKE '%/{_sql_quote(name.lower())}.pdf'"
        for name in normalized_pdf_names
    ]
    where_clause = " OR ".join(like_clauses) if like_clauses else "1 = 0"
    statement = f"""
SELECT *
FROM {FSR_SCRAPED_MAPPING_VIEW}
WHERE {where_clause}
ORDER BY {SCRAPED_MAPPING_FILE_COLUMN}
"""
    rows = _query_sql(statement)
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(_scraped_mapping_file_key(row), []).append(row)
    return grouped


def _fsr_report_rows(pdf_ref_rows: Sequence[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    pairs: List[Tuple[str, str]] = []
    for row in pdf_ref_rows:
        esn = str(_lookup_ci(row, "esn") or "").strip()
        event_id = str(_lookup_ci(row, "event_id", "ev_equipment_event_id", "ev_ofs_event_id") or "").strip()
        if esn and event_id:
            pairs.append((esn, event_id))
    if not pairs:
        return {}

    pair_clauses = [
        f"({FSR_REPORT_ESN_COLUMN} = '{_sql_quote(esn)}' AND {FSR_REPORT_EVENT_ID_COLUMN} = '{_sql_quote(event_id)}')"
        for esn, event_id in dict.fromkeys(pairs)
    ]
    statement = f"""
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY {FSR_REPORT_ESN_COLUMN}, {FSR_REPORT_EVENT_ID_COLUMN}
            ORDER BY CASE UPPER(COALESCE({FSR_REPORT_STATUS_COLUMN}, ''))
                WHEN 'COMPLETED' THEN 1
                WHEN 'STARTED' THEN 2
                WHEN 'NOT STARTED' THEN 3
                WHEN 'HOLD' THEN 4
                ELSE 99
            END,
            COALESCE({FSR_REPORT_END_DATE_COLUMN}, {FSR_REPORT_START_DATE_COLUMN}) DESC,
            COALESCE({FSR_REPORT_NAME_COLUMN}, '') ASC
        ) AS row_num
    FROM {FSR_REPORT_VIEW}
    WHERE {' OR '.join(pair_clauses)}
)
SELECT * EXCEPT (row_num)
FROM ranked
WHERE row_num = 1
"""
    rows = _query_sql(statement)
    return {
        (str(_lookup_ci(row, FSR_REPORT_ESN_COLUMN) or ""), str(_lookup_ci(row, FSR_REPORT_EVENT_ID_COLUMN) or "")): row
        for row in rows
    }


def _choose_pdf_ref(chunk_row: Dict[str, Any], pdf_ref_rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not pdf_ref_rows:
        return None

    chunk_pdf_name = _normalize_pdf_key(_lookup_ci(chunk_row, "pdf_name") or "")
    chunk_serial = str(_lookup_ci(chunk_row, "generator_serial", "esn") or "").strip()
    exact_file_matches: List[Dict[str, Any]] = []
    exact_file_and_esn_matches: List[Dict[str, Any]] = []

    for row in pdf_ref_rows:
        row_pdf_name = _pdf_ref_file_key(row)
        if row_pdf_name != chunk_pdf_name:
            continue
        exact_file_matches.append(row)
        row_serial = str(_lookup_ci(row, "esn", "generator_serial") or "").strip()
        if chunk_serial and row_serial == chunk_serial:
            exact_file_and_esn_matches.append(row)

    if exact_file_and_esn_matches:
        return exact_file_and_esn_matches[0]
    if exact_file_matches:
        return exact_file_matches[0]
    return pdf_ref_rows[0]


def _build_results(
    vs_rows: Sequence[Dict[str, Any]],
    chunk_rows: Dict[str, Dict[str, Any]],
    pdf_ref_rows: Dict[str, List[Dict[str, Any]]],
    scraped_rows: Dict[str, List[Dict[str, Any]]],
    fsr_report_rows: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for vs_row in vs_rows:
        chunk_id = str(vs_row.get("chunk_id") or "")
        pdf_name = _normalize_pdf_key(vs_row.get("pdf_name") or "")
        full_chunk_row = dict(chunk_rows.get(chunk_id) or {})
        if not full_chunk_row:
            full_chunk_row = {
                "chunk_id": chunk_id,
                "pdf_name": pdf_name,
                "page_number": vs_row.get("page_number"),
                "chunk_text": vs_row.get("chunk_text"),
                "generator_serial": vs_row.get("generator_serial"),
            }

        parsed_metadata = _safe_parse_metadata(full_chunk_row.get("metadata"))
        selected_pdf_ref = _choose_pdf_ref(full_chunk_row, pdf_ref_rows.get(pdf_name, []))
        selected_scraped = (scraped_rows.get(pdf_name) or [None])[0]
        selected_fsr_report = None
        if selected_pdf_ref is not None:
            report_key = (
                str(_lookup_ci(selected_pdf_ref, "esn") or ""),
                str(_lookup_ci(selected_pdf_ref, "event_id", "ev_equipment_event_id", "ev_ofs_event_id") or ""),
            )
            selected_fsr_report = fsr_report_rows.get(report_key)

        result_row = {
            "chunk_id": chunk_id,
            "pdf_name": full_chunk_row.get("pdf_name", pdf_name),
            "page_number": full_chunk_row.get("page_number", vs_row.get("page_number")),
            "chunk_text": full_chunk_row.get("chunk_text", vs_row.get("chunk_text", "")),
            "generator_serial": full_chunk_row.get("generator_serial", vs_row.get("generator_serial", "")),
            "score": float(vs_row.get("score", 0.0) or 0.0),
            "start_page": parsed_metadata.get("start_page", full_chunk_row.get("page_number", vs_row.get("page_number"))),
            "end_page": parsed_metadata.get("end_page", parsed_metadata.get("start_page", full_chunk_row.get("page_number", vs_row.get("page_number")))),
            "section_1": parsed_metadata.get("section_1", ""),
            "section_2": parsed_metadata.get("section_2", ""),
            "section_3": parsed_metadata.get("section_3", ""),
            "section_4": parsed_metadata.get("section_4", ""),
            "section_5": parsed_metadata.get("section_5", ""),
            "start_date": _lookup_ci(selected_fsr_report or {}, "start_date", "outage_start_date") or _lookup_ci(selected_pdf_ref or {}, "outage_start_date", "report_issued_date"),
            "end_date": _lookup_ci(selected_fsr_report or {}, "end_date", "outage_end_date") or _lookup_ci(selected_pdf_ref or {}, "outage_end_date"),
            "report_name": _lookup_ci(selected_fsr_report or {}, "report_name") or _lookup_ci(selected_pdf_ref or {}, "PDF_name") or full_chunk_row.get("pdf_name", pdf_name),
            "event_type": _lookup_ci(selected_fsr_report or {}, "event_type") or _lookup_ci(selected_pdf_ref or {}, "ev_event_type"),
            "outage_type": _lookup_ci(selected_fsr_report or {}, "outage_type"),
            "technology_type": _lookup_ci(selected_fsr_report or {}, "technology_type"),
            "report_unit_status": _lookup_ci(selected_fsr_report or {}, "report_unit_status"),
            "metadata": _json_row(parsed_metadata),
            "pdf_ref": _json_row(selected_pdf_ref or {}),
            "fsr_report": _json_row(selected_fsr_report or {}),
            "scraped_mapping": _json_row(selected_scraped or {}),
        }
        results.append(result_row)

    return results


def query_fsr(
    serial_number: str,
    query: str,
    k: int = 10,
    query_type: str = "HYBRID",
) -> List[Dict]:
    """
    Query Databricks Vector Search for FSR chunks matching a serial + query.

    Args:
        serial_number: Equipment serial (e.g. "290T658") — filters on generator_serial
        query: Search query text (e.g. issue_prompt + severity criteria)
        k: Number of results to return
        query_type: "HYBRID" (vector + keyword) or "ANN" (vector only)

    Returns:
        List of dicts with chunk_id, pdf_name, page_number, chunk_text,
        generator_serial, score
    """
    token = require_setting(
        VS_TOKEN,
        name="Databricks Vector Search token",
        env_names=("VS_TOKEN", "DATABRICKS_TOKEN", "DB_TOKEN"),
        file_names=("dbr_token.txt",),
    )
    url = f"{VS_WORKSPACE_URL}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    query_vector = get_query_vector(query)
    body = {
        "query_text": query,
        "query_vector": query_vector,
        "columns": RETURN_COLUMNS,
        "num_results": k,
        "query_type": query_type.upper(),
        "filters_json": json.dumps({"generator_serial": serial_number}),
    }

    resp = retry_request(
        lambda: requests.post(url, headers=headers, json=body, timeout=60),
        label=f"FSR/{serial_number}",
        retriable_status_codes=RETRIABLE_STATUS_CODES,
    )
    if not resp.ok:
        message = f"FSR query failed HTTP {resp.status_code}: {resp.text[:200]}"
        print(f"[FSR] {message}")
        raise RuntimeError(message)

    data = resp.json()
    col_names = [c["name"] for c in data.get("manifest", {}).get("columns", [])]
    rows = data.get("result", {}).get("data_array", [])

    vs_rows = [{col: row[i] for i, col in enumerate(col_names)} for row in rows]

    chunk_ids = [str(row.get("chunk_id") or "") for row in vs_rows if row.get("chunk_id")]
    pdf_names = list(dict.fromkeys(str(row.get("pdf_name") or "") for row in vs_rows if row.get("pdf_name")))

    with ThreadPoolExecutor(max_workers=3) as executor:
        chunk_rows_future = executor.submit(_chunk_rows_by_id, chunk_ids)
        pdf_ref_future = executor.submit(_pdf_ref_rows, pdf_names)
        scraped_future = executor.submit(_scraped_mapping_rows, pdf_names)

        chunk_rows = chunk_rows_future.result()
        pdf_ref_by_filename = pdf_ref_future.result()
        scraped_by_filename = scraped_future.result()

    all_pdf_ref_rows = [row for rows_for_file in pdf_ref_by_filename.values() for row in rows_for_file]
    fsr_report_by_pair = _fsr_report_rows(all_pdf_ref_rows)
    results = _build_results(
        vs_rows,
        chunk_rows,
        pdf_ref_by_filename,
        scraped_by_filename,
        fsr_report_by_pair,
    )

    print(f"[FSR] Found {len(results)} chunks for serial='{serial_number}' ({query_type}, k={k})")
    return results
