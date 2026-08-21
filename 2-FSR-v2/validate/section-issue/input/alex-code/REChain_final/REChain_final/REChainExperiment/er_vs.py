"""Step 2 (alt): Retrieve ER (Engineering Record) chunks from Databricks Vector Search.

Lightweight alternative to er.py — queries a pre-built ER vector index
instead of fetching raw data, chunking, and embedding at runtime.
Same pattern as fsr.py.
"""

import json
from typing import Dict, List

import requests

from .config import (
    VS_WORKSPACE_URL,
    VS_TOKEN,
    ER_VS_INDEX_NAME,
    require_setting,
)
from .retry import RETRIABLE_STATUS_CODES, retry_request
from .vector_embeddings import get_query_vector

RETURN_COLUMNS = [
    "chunk_id", "er_case_number", "chunk_text", "serial_number",
    "opened_at", "status", "u_component", "u_field_action_taken",
    "equipment_id",
]


def _parse_er_identity(chunk_id: str, er_case_number: str) -> tuple[str, int]:
    chunk_id = str(chunk_id or "")
    er_case_number = str(er_case_number or "")

    if chunk_id:
        er_number, separator, suffix = chunk_id.rpartition(":")
        if separator and suffix.isdigit():
            return er_number, int(suffix)

    return er_case_number, 0


def query_er_vs(
    serial_number: str,
    query: str,
    k: int = 10,
    query_type: str = "HYBRID",
) -> List[Dict]:
    """
    Query Databricks Vector Search for ER chunks matching a serial + query.

    Args:
        serial_number: Equipment serial (e.g. "290T658") — filters on serial_number
        query: Search query text (e.g. issue_prompt + severity criteria)
        k: Number of results to return
        query_type: "HYBRID" (vector + keyword) or "ANN" (vector only)

    Returns:
        List of dicts matching er.py's public contract, with additional
        Databricks-native fields preserved for traceability.
    """
    token = require_setting(
        VS_TOKEN,
        name="Databricks Vector Search token",
        env_names=("VS_TOKEN", "DATABRICKS_TOKEN", "DB_TOKEN"),
        file_names=("dbr_token.txt",),
    )
    url = f"{VS_WORKSPACE_URL}/api/2.0/vector-search/indexes/{ER_VS_INDEX_NAME}/query"
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
        "filters_json": json.dumps({"serial_number": serial_number}),
    }

    resp = retry_request(
        lambda: requests.post(url, headers=headers, json=body, timeout=60),
        label=f"ER-VS/{serial_number}",
        retriable_status_codes=RETRIABLE_STATUS_CODES,
    )
    if not resp.ok:
        message = f"ER query failed HTTP {resp.status_code}: {resp.text[:200]}"
        print(f"[ER-VS] {message}")
        raise RuntimeError(message)

    raw = resp.json()

    col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]
    rows = raw.get("result", {}).get("data_array", [])

    results = []
    for row in rows:
        row_dict = {col: row[i] for i, col in enumerate(col_names)}
        chunk_id = row_dict.get("chunk_id", "")
        er_case_number = row_dict.get("er_case_number", "")
        er_number, chunk_index = _parse_er_identity(chunk_id, er_case_number)
        chunk_text = row_dict.get("chunk_text", "")
        results.append({
            "er_number": er_number,
            "serial_number": row_dict.get("serial_number", ""),
            "opened_at": row_dict.get("opened_at", ""),
            "status": row_dict.get("status", ""),
            "u_component": row_dict.get("u_component", ""),
            "u_field_action_taken": row_dict.get("u_field_action_taken", ""),
            "equipment_id": row_dict.get("equipment_id", ""),
            "chunk_text": chunk_text,
            "chunk_index": chunk_index,
            "score": float(row_dict.get("score", 0.0) or 0.0),
            "chunk_id": chunk_id,
            "er_case_number": er_case_number,
        })

    print(f"[ER-VS] Found {len(results)} chunks for serial='{serial_number}' ({query_type}, k={k})")
    return results
