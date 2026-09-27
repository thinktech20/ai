# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_er_ddl — Create ER pipeline chunk table
#
# Idempotent: uses CREATE TABLE IF NOT EXISTS.
# Run as the first task in the ER workflow.
#
# When FORCE_RESET=true, drops the table and deletes the VS index so the
# pipeline recreates them with the latest schema.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/er_config

# COMMAND ----------

import logging
import requests
import urllib3

urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("er.ddl")

# COMMAND ----------

# ── FORCE_RESET: drop table + delete VS index ──────────────────────────────

if FORCE_RESET:
    spark.sql(f"DROP TABLE IF EXISTS {ER_CHUNK_TABLE}")
    log.warning(f"FORCE_RESET: dropped {ER_CHUNK_TABLE}")

    if ER_RUN_LOG_TABLE:
        try:
            spark.sql(f"TRUNCATE TABLE {ER_RUN_LOG_TABLE}")
            log.warning(f"FORCE_RESET: truncated {ER_RUN_LOG_TABLE} (watermark cleared)")
        except Exception:
            log.info(f"FORCE_RESET: {ER_RUN_LOG_TABLE} does not exist yet — skipping truncate")

    if ER_VS_INDEX:
        try:
            ws_url, token = get_dbr_auth()
            headers = {"Authorization": f"Bearer {token}"}
            idx_url = f"{ws_url}/api/2.0/vector-search/indexes/{ER_VS_INDEX}"
            resp = requests.delete(idx_url, headers=headers, timeout=30)
            if resp.ok:
                log.warning(f"FORCE_RESET: deleted VS index {ER_VS_INDEX}")
            elif resp.status_code == 404:
                log.info(f"FORCE_RESET: VS index {ER_VS_INDEX} does not exist")
            else:
                log.warning(f"FORCE_RESET: could not delete VS index: HTTP {resp.status_code}")
        except Exception as e:
            log.warning(f"FORCE_RESET: VS index deletion failed (non-blocking): {e}")

# COMMAND ----------

# ── Create schema if not exists ─────────────────────────────────────────────
# Derive catalog.schema from ER_CHUNK_TABLE (format: catalog.schema.table)

_parts = ER_CHUNK_TABLE.split(".")
if len(_parts) >= 3:
    _schema_fqn = f"{_parts[0]}.{_parts[1]}"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {_schema_fqn}")
    log.info(f"Schema ready: {_schema_fqn}")

# COMMAND ----------

# ── Create chunk table ──────────────────────────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {ER_CHUNK_TABLE} (
        {ER_CHUNK_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'ER chunk rows with embeddings'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")
log.info(f"ER chunk table ready: {ER_CHUNK_TABLE}")

# COMMAND ----------

# ── Create run log table ─────────────────────────────────────────────
# NOTE: The run log grows by 1 row per pipeline run.  At daily cadence this
# is trivial (~365 rows/year).  If run frequency increases, consider adding
# a periodic cleanup or partitioning by run_started_at.

if ER_RUN_LOG_TABLE:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {ER_RUN_LOG_TABLE} (
            {ER_RUN_LOG_DDL_COLS}
        )
        USING DELTA
        COMMENT 'ER pipeline run log — tracks incremental watermark'
    """)
    log.info(f"ER run log table ready: {ER_RUN_LOG_TABLE}")

# COMMAND ----------

# ── Create failed records table ──────────────────────────────────────
# Tracks per-record embedding failures for individual retry without
# blocking the watermark.  Successful retries delete rows; persistent
# failures (attempts >= ER_MAX_RECORD_ATTEMPTS) remain for inspection.

if ER_FAILED_RECORDS_TABLE:
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {ER_FAILED_RECORDS_TABLE} (
            {ER_FAILED_RECORDS_DDL_COLS}
        )
        USING DELTA
        COMMENT 'ER per-record embedding failure tracking — supports individual retry'
    """)
    log.info(f"ER failed records table ready: {ER_FAILED_RECORDS_TABLE}")

count = spark.sql(f"SELECT COUNT(*) AS n FROM {ER_CHUNK_TABLE}").first().n
cols = len(spark.table(ER_CHUNK_TABLE).columns)
log.info(f"  {ER_CHUNK_TABLE}: {count} rows, {cols} columns")

# COMMAND ----------

# ── Ensure VS index exists ──────────────────────────────────────────────────
# If the chunk table already has data but no VS index, create one so the
# initial build starts immediately.  Safe to re-run: if the index already
# exists, this is a no-op that logs the current status.

import json
import ssl
import urllib.request
import urllib.error

if ER_VS_INDEX and ER_VS_ENDPOINT:
    ws_url, token = get_dbr_auth()
    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE

    # 1. Check endpoint
    try:
        ep_url = f"{ws_url}/api/2.0/vector-search/endpoints/{ER_VS_ENDPOINT}"
        ep_req = urllib.request.Request(ep_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(ep_req, context=_ctx, timeout=30) as resp:  # noqa: S310
            ep_info = json.loads(resp.read())
        ep_state = ep_info.get("endpoint_status", {}).get("state", "UNKNOWN")
        log.info(f"VS endpoint '{ER_VS_ENDPOINT}' state: {ep_state}")
        if ep_state != "ONLINE":
            log.warning(f"VS endpoint is NOT ONLINE (state={ep_state}) — index creation may fail")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        log.error(f"VS endpoint check failed: HTTP {e.code} — {body}")
        if e.code == 403:
            log.error(f"  → Grant CAN_USE on endpoint '{ER_VS_ENDPOINT}' to the service principal")
        # Non-fatal in DDL — the ingestion notebook will also check
    except Exception as e:
        log.warning(f"VS endpoint check failed (non-blocking): {e}")

    # 2. Check / create index
    _index_exists = False
    try:
        idx_status = check_vs_index_status(ws_url, token, ER_VS_INDEX)
        log.info(f"VS index '{ER_VS_INDEX}' already exists — status: "
                 f"{idx_status.get('status', 'unknown')}")
        _index_exists = True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.info(f"VS index '{ER_VS_INDEX}' does not exist — will create")
        else:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"VS index check failed: HTTP {e.code} — {body}")

    if not _index_exists:
        create_payload = {
            "name": ER_VS_INDEX,
            "endpoint_name": ER_VS_ENDPOINT,
            "primary_key": "chunk_id",
            "index_type": "DELTA_SYNC",
            "delta_sync_index_spec": {
                "source_table": ER_CHUNK_TABLE,
                "pipeline_type": "TRIGGERED",
                "embedding_vector_columns": [
                    {
                        "name": "chunk_embedding",
                        "embedding_dimension": int(get_runtime_param("ER_EMBEDDING_DIMENSION", "3072")),
                    }
                ],
            },
        }
        log.info(f"Creating VS index: {json.dumps(create_payload)}")
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
            log.error(f"  Source table: {ER_CHUNK_TABLE} ({count} rows)")
            log.error(f"  Endpoint: {ER_VS_ENDPOINT}")
            log.error("  → The ingestion notebook will retry index creation on its next run")
        except Exception as e:
            log.error(f"VS index creation failed (unexpected): {e}")
else:
    log.info("VS index/endpoint not configured — skipping VS index check")
