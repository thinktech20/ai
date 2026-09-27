# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_mnd_ddl — Create M&D pipeline tables + Vector Search index
#
# Idempotent: uses CREATE TABLE IF NOT EXISTS.  Run as the first task in
# the M&D workflow.
#
# When FORCE_RESET=true (with FORCE_RESET_CONFIRM=true), drops the chunk
# table, truncates the run log, clears failed-records, and deletes the VS
# index so the pipeline recreates them with the latest schema.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../common/mnd_config

# COMMAND ----------

import json
import logging
import ssl
import urllib.error
import urllib.request

import requests
import urllib3

urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mnd.ddl")

# COMMAND ----------

# ── FORCE_RESET: drop table + clear log + delete VS index ──────────────────

if FORCE_RESET:
    if JB_ENV == "prod":
        raise ValueError("FORCE_RESET is not allowed when jb_env=prod")

    spark.sql(f"DROP TABLE IF EXISTS {MND_CHUNK_TABLE}")
    log.warning(f"FORCE_RESET: dropped {MND_CHUNK_TABLE}")

    if MND_PREPROCESSED_TABLE:
        spark.sql(f"DROP TABLE IF EXISTS {MND_PREPROCESSED_TABLE}")
        log.warning(f"FORCE_RESET: dropped {MND_PREPROCESSED_TABLE}")

    if MND_RUN_LOG_TABLE:
        try:
            spark.sql(f"TRUNCATE TABLE {MND_RUN_LOG_TABLE}")
            log.warning(f"FORCE_RESET: truncated {MND_RUN_LOG_TABLE} (watermark cleared)")
        except Exception:
            log.info(f"FORCE_RESET: {MND_RUN_LOG_TABLE} does not exist yet — skipping truncate")

    if MND_FAILED_RECORDS_TABLE:
        try:
            spark.sql(f"DELETE FROM {MND_FAILED_RECORDS_TABLE}")
            log.warning(f"FORCE_RESET: cleared {MND_FAILED_RECORDS_TABLE}")
        except Exception:
            log.info(f"FORCE_RESET: {MND_FAILED_RECORDS_TABLE} does not exist yet — skipping clear")

    if MND_VS_INDEX:
        try:
            ws_url, token = get_dbr_auth()
            headers = {"Authorization": f"Bearer {token}"}
            idx_url = f"{ws_url}/api/2.0/vector-search/indexes/{MND_VS_INDEX}"
            resp = requests.delete(idx_url, headers=headers, timeout=30, verify=LLM_VERIFY_SSL)
            if resp.ok:
                log.warning(f"FORCE_RESET: deleted VS index {MND_VS_INDEX}")
            elif resp.status_code == 404:
                log.info(f"FORCE_RESET: VS index {MND_VS_INDEX} does not exist")
            else:
                log.warning(f"FORCE_RESET: could not delete VS index: HTTP {resp.status_code}")
        except Exception as e:
            log.warning(f"FORCE_RESET: VS index deletion failed (non-blocking): {e}")

# COMMAND ----------

# ── Create schema if not exists ─────────────────────────────────────────────
# Derive catalog.schema from MND_CHUNK_TABLE (format: catalog.schema.table)

_parts = MND_CHUNK_TABLE.split(".")
if len(_parts) >= 3:
    _schema_fqn = f"{_parts[0]}.{_parts[1]}"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {_schema_fqn}")
    log.info(f"Schema ready: {_schema_fqn}")

# COMMAND ----------

# ── Create preprocessed table (PII-redacted record-level data) ─────────────
# Written after Presidio + Flair redaction, before chunking.
# Mirrors df_presidio / mnd_presidio_cleaned from E3_final.py.

if MND_PREPROCESSED_TABLE:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {MND_PREPROCESSED_TABLE} (
            {MND_PREPROCESSED_TABLE_DDL_COLS}
        )
        USING DELTA
        COMMENT 'M&D PII-redacted record-level data (E3_final.py mnd_presidio_cleaned parity)'
        TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
    """)
    log.info(f"M&D preprocessed table ready: {MND_PREPROCESSED_TABLE}")
else:
    log.info("MND_PREPROCESSED_TABLE not configured — skipping preprocessed table creation")

# COMMAND ----------

# ── Create chunk table ──────────────────────────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {MND_CHUNK_TABLE} (
        {MND_CHUNK_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'M&D chunk rows with embeddings (research notebook E3_final.py parity)'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")
log.info(f"M&D chunk table ready: {MND_CHUNK_TABLE}")

# COMMAND ----------

# ── Create run log table ────────────────────────────────────────────────────

if MND_RUN_LOG_TABLE:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {MND_RUN_LOG_TABLE} (
            {MND_RUN_LOG_DDL_COLS}
        )
        USING DELTA
        COMMENT 'M&D pipeline run log — tracks incremental watermark'
    """)
    log.info(f"M&D run log table ready: {MND_RUN_LOG_TABLE}")

# COMMAND ----------

# ── Create failed records table ─────────────────────────────────────────────

if MND_FAILED_RECORDS_TABLE:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {MND_FAILED_RECORDS_TABLE} (
            {MND_FAILED_RECORDS_DDL_COLS}
        )
        USING DELTA
        COMMENT 'M&D per-record processing failure tracking — supports individual retry'
    """)
    log.info(f"M&D failed records table ready: {MND_FAILED_RECORDS_TABLE}")

count = spark.sql(f"SELECT COUNT(*) AS n FROM {MND_CHUNK_TABLE}").first().n
cols = len(spark.table(MND_CHUNK_TABLE).columns)
log.info(f"  {MND_CHUNK_TABLE}: {count} rows, {cols} columns")

# COMMAND ----------

# ── Ensure VS index exists ──────────────────────────────────────────────────
# HYBRID (dense + BM25) DELTA_SYNC index keyed on chunk_id.  primary_key,
# embedding_dimension and embedding_vector_column match the research
# notebook so existing retrieval code requires no changes.

if MND_VS_INDEX and MND_VS_ENDPOINT:
    ws_url, token = get_dbr_auth()
    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE

    # 1. Check endpoint
    try:
        ep_url = f"{ws_url}/api/2.0/vector-search/endpoints/{MND_VS_ENDPOINT}"
        ep_req = urllib.request.Request(ep_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(ep_req, context=_ctx, timeout=30) as resp:  # noqa: S310
            ep_info = json.loads(resp.read())
        ep_state = ep_info.get("endpoint_status", {}).get("state", "UNKNOWN")
        log.info(f"VS endpoint '{MND_VS_ENDPOINT}' state: {ep_state}")
        if ep_state != "ONLINE":
            log.warning(f"VS endpoint is NOT ONLINE (state={ep_state}) — index creation may fail")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        log.error(f"VS endpoint check failed: HTTP {e.code} — {body}")
        if e.code == 403:
            log.error(f"  → Grant CAN_USE on endpoint '{MND_VS_ENDPOINT}' to the service principal")
    except Exception as e:
        log.warning(f"VS endpoint check failed (non-blocking): {e}")

    # 2. Check / create index
    _index_exists = False
    try:
        idx_status = check_vs_index_status(ws_url, token, MND_VS_INDEX)
        log.info(f"VS index '{MND_VS_INDEX}' already exists — status: "
                 f"{idx_status.get('status', 'unknown')}")
        _index_exists = True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.info(f"VS index '{MND_VS_INDEX}' does not exist — will create")
        else:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"VS index check failed: HTTP {e.code} — {body}")

    if not _index_exists:
        # The research notebook uses HYBRID with a Databricks-managed
        # embedding endpoint for query-time embedding; chunks already carry
        # pre-computed vectors in `embedding` for serving.
        embedding_spec = {
            "name": "embedding",
            "embedding_dimension": EMBEDDING_DIMENSION,
        }
        if MND_VS_EMBEDDING_MODEL_ENDPOINT:
            embedding_spec["embedding_model_endpoint_name"] = MND_VS_EMBEDDING_MODEL_ENDPOINT

        create_payload = {
            "name": MND_VS_INDEX,
            "endpoint_name": MND_VS_ENDPOINT,
            "primary_key": "chunk_id",
            "index_type": "DELTA_SYNC",
            "delta_sync_index_spec": {
                "source_table": MND_CHUNK_TABLE,
                "pipeline_type": "TRIGGERED",
                "embedding_vector_columns": [embedding_spec],
            },
        }
        log.info(f"Creating VS index ({MND_VS_INDEX_TYPE}): {json.dumps(create_payload)}")
        try:
            create_url = f"{ws_url}/api/2.0/vector-search/indexes"
            req = urllib.request.Request(
                create_url,
                data=json.dumps(create_payload).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, context=_ctx, timeout=60) as resp:  # noqa: S310
                resp_body = json.loads(resp.read())
            log.info(f"VS index created — initial build will index all {count} existing rows: {resp_body}")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"VS index creation failed: HTTP {e.code} — {body}")
            log.error(f"  Source table: {MND_CHUNK_TABLE} ({count} rows)")
            log.error(f"  Endpoint: {MND_VS_ENDPOINT}")
            log.error("  → The ingestion notebook will retry index creation on its next run")
        except Exception as e:
            log.error(f"VS index creation failed (unexpected): {e}")
else:
    log.info("VS index/endpoint not configured — skipping VS index check")
