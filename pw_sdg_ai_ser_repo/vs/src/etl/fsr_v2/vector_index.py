"""Stage 6 — Vector Index Management.

Creates or syncs fsr_vs_index_v2 over fsr_chunks_v2.

Runs independently from P1/P2 — can be triggered separately for:
    create  — initial index creation (Delta Sync index from fsr_chunks_v2)
    sync    — trigger sync after P2 writes new chunks

INDEX_MODE knob controls which operation runs.

Reuses patterns from:
    - nb_sdg_fsr_vs_sync.py (endpoint check, sync trigger, retry logic)
    - nb_sdg_fsr_chunks.py  (VS index creation params: primary_key, embedding_col, metadata_cols)

Input:  fsr_chunks_v2 (source Delta table for the index)
Output: fsr_vs_index_v2 (created or synced Vector Search index)
"""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger("fsr.v2.vector_index")


_ONLINE_STATES = {"ONLINE", "ONLINE_NO_PENDING_UPDATE"}


def _api_call(
    ws_url: str,
    token: str,
    method: str,
    path: str,
    *,
    verify_ssl: Any = True,
    payload: dict | None = None,
    timeout: int = 30,
) -> requests.Response:
    url = f"{ws_url.rstrip('/')}{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    return requests.request(
        method=method,
        url=url,
        headers=headers,
        json=payload,
        timeout=timeout,
        verify=verify_ssl,
    )


def _endpoint_state(ws_url: str, token: str, endpoint_name: str, verify_ssl: Any = True) -> str:
    resp = _api_call(
        ws_url,
        token,
        "GET",
        f"/api/2.0/vector-search/endpoints/{endpoint_name}",
        verify_ssl=verify_ssl,
    )
    if not resp.ok:
        raise RuntimeError(
            f"Endpoint check failed for '{endpoint_name}': "
            f"HTTP {resp.status_code} {resp.text[:300]}"
        )
    return resp.json().get("endpoint_status", {}).get("state", "")


def _get_index(ws_url: str, token: str, index_name: str, verify_ssl: Any = True) -> dict | None:
    resp = _api_call(
        ws_url,
        token,
        "GET",
        f"/api/2.0/vector-search/indexes/{index_name}",
        verify_ssl=verify_ssl,
    )
    if resp.status_code == 404:
        return None
    if not resp.ok:
        raise RuntimeError(
            f"Index check failed for '{index_name}': "
            f"HTTP {resp.status_code} {resp.text[:300]}"
        )
    return resp.json()


def _index_state(index_info: dict) -> str:
    # REST payloads vary slightly by runtime/API rev; try common paths.
    return (
        (index_info.get("status") or {}).get("state")
        or (index_info.get("status") or {}).get("detailed_state")
        or (index_info.get("index_status") or {}).get("status")
        or (index_info.get("vector_search_index") or {}).get("status")
        or ""
    )


def _wait_index_online(
    ws_url: str,
    token: str,
    index_name: str,
    *,
    verify_ssl: Any = True,
    timeout_seconds: int = 600,
    poll_seconds: int = 10,
    label: str = "",
) -> None:
    _label = f" [{label}]" if label else ""
    start = time.time()
    while True:
        index_info = _get_index(ws_url, token, index_name, verify_ssl=verify_ssl)
        state = _index_state(index_info or {})
        elapsed = time.time() - start
        log.info(f"VS index '{index_name}' state: {state or 'UNKNOWN'}{_label} (elapsed: {elapsed:.0f}s)")
        if state in _ONLINE_STATES:
            log.info(f"VS index ready{_label} — total wait: {elapsed:.0f}s")
            return
        if elapsed >= timeout_seconds:
            raise RuntimeError(
                f"Timed out waiting for index '{index_name}' to become ONLINE "
                f"(last_state={state or 'UNKNOWN'}, elapsed: {elapsed:.0f}s)"
            )
        time.sleep(poll_seconds)


def _create_index(
    ws_url: str,
    token: str,
    *,
    chunk_table: str,
    index_name: str,
    endpoint_name: str,
    embedding_dimension: int,
    verify_ssl: Any = True,
) -> None:
    payload = {
        "name": index_name,
        "endpoint_name": endpoint_name,
        "primary_key": "chunk_id",
        "index_type": "DELTA_SYNC",
        "delta_sync_index_spec": {
            "source_table": chunk_table,
            "pipeline_type": "TRIGGERED",
            "embedding_vector_columns": [
                {"name": "chunk_embedding", "embedding_dimension": embedding_dimension}
            ],
            "columns_to_sync": [
                "chunk_id", "chunk_index", "document_id", "pdf_name",
                "page_number", "chunk_text",
                "region_primary_esn", "region_primary_equip_type", "active_esns",
                "report_date", "outage_start_date", "metadata", "created_at",
            ],
        },
    }
    resp = _api_call(
        ws_url,
        token,
        "POST",
        "/api/2.0/vector-search/indexes",
        verify_ssl=verify_ssl,
        payload=payload,
        timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"VS index creation failed: HTTP {resp.status_code} {resp.text[:500]}")


def _trigger_sync(
    ws_url: str,
    token: str,
    index_name: str,
    *,
    verify_ssl: Any = True,
    retries: int = 3,
    retry_wait_seconds: int = 20,
) -> None:
    for attempt in range(1, retries + 1):
        resp = _api_call(
            ws_url,
            token,
            "POST",
            f"/api/2.0/vector-search/indexes/{index_name}/sync",
            verify_ssl=verify_ssl,
            payload={},
        )
        if resp.ok:
            return
        if resp.status_code == 400 and "not ready" in (resp.text or "").lower() and attempt < retries:
            log.info(f"Endpoint/index warming (attempt {attempt}/{retries}) — waiting {retry_wait_seconds}s")
            time.sleep(retry_wait_seconds)
            continue
        raise RuntimeError(f"VS sync failed: HTTP {resp.status_code} {resp.text[:300]}")


def run(
    chunk_table: str,
    index_name: str,
    endpoint_name: str,
    mode: str,
    *,
    workspace_url: str,
    token: str,
    verify_ssl: Any = True,
    embedding_dimension: int = 3072,
) -> None:
    """Create or sync fsr_vs_index_v2.

    Args:
        chunk_table:    fsr_chunks_v2 — source Delta table
        index_name:     fully qualified VS index name (fsr_vs_index_v2)
        endpoint_name:  VS endpoint name (must be ONLINE)
        mode:           operation to perform — create | sync

    Steps (create):
        1. Verify endpoint is ONLINE
        2. Create Delta Sync index on chunk_table
           - primary_key: chunk_id
           - embedding_col: chunk_embedding
           - metadata_cols: esn, primary_equip_type, document_id, pdf_name, page_number, ...
        3. Poll until index is ONLINE
        4. Trigger initial sync so the source table rows are loaded into the index
        5. Poll again until sync completes (ONLINE / ONLINE_NO_PENDING_UPDATE)

    Steps (sync):
        1. Verify endpoint is ONLINE + index exists
        2. Trigger sync (reuse nb_sdg_fsr_vs_sync retry pattern)
        3. Poll for sync completion
    """
    if not workspace_url or not token:
        raise ValueError("workspace_url and token are required")
    if not chunk_table or not index_name or not endpoint_name:
        raise ValueError("chunk_table, index_name, and endpoint_name are required")

    mode_norm = (mode or "").strip().lower()
    if mode_norm not in {"create", "sync"}:
        raise ValueError(f"Invalid mode={mode!r}; expected 'create' or 'sync'")

    ep_state = _endpoint_state(workspace_url, token, endpoint_name, verify_ssl=verify_ssl)
    log.info(f"VS endpoint '{endpoint_name}' state: {ep_state}")
    if ep_state != "ONLINE":
        raise RuntimeError(f"Endpoint not ONLINE (state={ep_state}); aborting")

    idx = _get_index(workspace_url, token, index_name, verify_ssl=verify_ssl)

    if mode_norm == "create":
        if idx is None:
            log.info(f"VS index does not exist — creating: {index_name}")
            _create_index(
                workspace_url,
                token,
                chunk_table=chunk_table,
                index_name=index_name,
                endpoint_name=endpoint_name,
                embedding_dimension=embedding_dimension,
                verify_ssl=verify_ssl,
            )
        else:
            log.info(f"VS index already exists: {index_name}")
        _wait_index_online(workspace_url, token, index_name, verify_ssl=verify_ssl, label="index ready")
        # A newly created TRIGGERED DELTA_SYNC index is ONLINE but empty.
        # Trigger an initial sync to populate it from the source table.
        # Use a generous timeout (3600s) so the first full load completes even for large tables.
        log.info(f"Triggering initial sync for '{index_name}'")
        _trigger_sync(workspace_url, token, index_name, verify_ssl=verify_ssl)
        _wait_index_online(
            workspace_url, token, index_name,
            verify_ssl=verify_ssl,
            timeout_seconds=3600,
            label="initial sync",
        )
        return

    # sync mode
    if idx is None:
        raise RuntimeError(f"VS index does not exist: {index_name}. Run mode='create' first.")
    _trigger_sync(workspace_url, token, index_name, verify_ssl=verify_ssl)
    log.info(f"VS sync triggered for '{index_name}'")
    _wait_index_online(workspace_url, token, index_name, verify_ssl=verify_ssl, label="sync")
