# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_vs_sync — Standalone Vector Search index sync trigger
#
# One-shot utility notebook. Triggers a sync of the FSR Vector Search index
# from its configured source chunk table. Does NOT touch the chunk table or
# metadata table — purely an index-sync operation, safe to re-run.
#
# Use cases:
#   • Manual catch-up sync after backfill (when end-of-job auto-sync is missed)
#   • Recovery if the chunking job's sync step fails or bails
#   • Operational on-demand sync without re-running ingestion
#
# Required job params:
#   FSR_VS_ENDPOINT — VS endpoint name (must match an existing endpoint)
#   FSR_VS_INDEX    — fully qualified index name
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import time
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.vs_sync")

# COMMAND ----------

log.info("=== FSR Vector Search Sync (standalone) ===")
log.info(f"  VS endpoint : {VS_ENDPOINT_NAME}")
log.info(f"  VS index    : {VS_INDEX_NAME}")
log.info(f"  jb_env      : {JB_ENV or 'unset'}")

if not VS_ENDPOINT_NAME or not VS_INDEX_NAME:
    raise ValueError("FSR_VS_ENDPOINT and FSR_VS_INDEX must both be set as job params")

# COMMAND ----------


def trigger_vs_sync():
    ws_url, token = get_dbr_auth()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # ── 1. Verify endpoint exists and is ONLINE ─────────────────────────────
    ep_url = f"{ws_url}/api/2.0/vector-search/endpoints/{VS_ENDPOINT_NAME}"
    try:
        resp = requests.get(ep_url, headers=headers, timeout=30, verify=DATABRICKS_VERIFY_SSL)
    except Exception as e:
        raise RuntimeError(f"Cannot reach endpoint API: {e}") from e

    if not resp.ok:
        raise RuntimeError(
            f"Endpoint check failed for '{VS_ENDPOINT_NAME}': "
            f"HTTP {resp.status_code} {resp.text[:300]}"
        )

    state = resp.json().get("endpoint_status", {}).get("state", "")
    log.info(f"VS endpoint '{VS_ENDPOINT_NAME}' state: {state}")
    if state != "ONLINE":
        raise RuntimeError(f"Endpoint not ONLINE (state={state}); aborting sync")

    # ── 2. Verify index exists ──────────────────────────────────────────────
    idx_url = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}"
    resp = requests.get(idx_url, headers=headers, timeout=30, verify=DATABRICKS_VERIFY_SSL)
    if not resp.ok:
        raise RuntimeError(
            f"Index check failed for '{VS_INDEX_NAME}': "
            f"HTTP {resp.status_code} {resp.text[:300]}"
        )
    log.info(f"VS index exists: {VS_INDEX_NAME}")

    # ── 3. Trigger sync (with retry on warming endpoint) ────────────────────
    sync_url = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}/sync"
    for attempt in range(1, 4):
        try:
            resp = requests.post(
                sync_url, headers=headers, json={},
                timeout=30, verify=DATABRICKS_VERIFY_SSL,
            )
        except Exception as e:
            raise RuntimeError(f"Sync POST error: {e}") from e

        if resp.ok:
            log.info(f"VS sync triggered for '{VS_INDEX_NAME}'")
            return

        if resp.status_code == 400 and "not ready" in resp.text.lower():
            log.info(f"Endpoint warming (attempt {attempt}/3) — waiting 20s...")
            time.sleep(20)
            continue

        raise RuntimeError(
            f"VS sync failed: HTTP {resp.status_code} {resp.text[:300]}"
        )

    raise RuntimeError("VS sync failed after 3 attempts")


trigger_vs_sync()
log.info("=== FSR VS sync complete ===")
