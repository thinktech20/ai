# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_ddl — Create FSR pipeline tables (metadata + chunks)
#
# Idempotent: uses CREATE TABLE IF NOT EXISTS.
# Run as the first task in the workflow to ensure tables exist before
# Process 1 and Process 2.
#
# When FORCE_RESET=true, drops all tables first so they are recreated with
# the latest schema, and deletes the VS index so P2 recreates it fresh.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import logging
import os
import requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fsr.ddl")
log.info(f"jb_env: {JB_ENV or 'unset'}")
if DATABRICKS_VERIFY_SSL is False:
    log.warning("TLS certificate verification is DISABLED for Databricks REST calls (FSR_DATABRICKS_VERIFY_SSL=false)")
elif isinstance(DATABRICKS_VERIFY_SSL, str):
    log.info(f"Using custom CA bundle for Databricks REST calls: {DATABRICKS_VERIFY_SSL}")

# COMMAND ----------

# ── FORCE_RESET: drop tables + delete VS index ─────────────────────────────

if FORCE_RESET:
    if JB_ENV == "prod":
        raise ValueError("FORCE_RESET is not allowed when jb_env=prod")
    for tbl in [METADATA_TABLE, CHUNK_TABLE, RUN_LOG_TABLE, DQ_LOG_TABLE]:
        spark.sql(f"DROP TABLE IF EXISTS {tbl}")
        log.warning(f"FORCE_RESET: dropped {tbl}")

    # Delete VS index so P2 recreates it with the latest schema
    try:
        ws_url, token = get_dbr_auth()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        idx_url = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}"
        resp = requests.delete(idx_url, headers=headers, timeout=30, verify=DATABRICKS_VERIFY_SSL)
        if resp.ok:
            log.warning(f"FORCE_RESET: deleted VS index {VS_INDEX_NAME}")
        elif resp.status_code == 404:
            log.info(f"FORCE_RESET: VS index {VS_INDEX_NAME} does not exist (nothing to delete)")
        else:
            log.warning(f"FORCE_RESET: could not delete VS index: HTTP {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        log.warning(f"FORCE_RESET: VS index deletion failed (non-blocking): {e}")

# COMMAND ----------

# ── Create metadata registry table (silver) ─────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {METADATA_TABLE} (
        {METADATA_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR document-level metadata registry'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.autoOptimize.optimizeWrite' = 'true'
    )
""")
log.info(f"Metadata table ready: {METADATA_TABLE}")

# Idempotent for existing tables — SET TBLPROPERTIES is a no-op if value matches.
# optimizeWrite pairs with ZORDER: keeps MERGE-emitted files at target size so
# the optimization persists between OPTIMIZE runs (small files = ZORDER drift).
spark.sql(f"ALTER TABLE {METADATA_TABLE} SET TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')")
log.info(f"Metadata table autoOptimize.optimizeWrite enabled")

# ── Schema evolution — add columns that may not exist on older tables ────────
try:
    spark.sql(f"ALTER TABLE {METADATA_TABLE} ADD COLUMNS (chunk_retry_count INT COMMENT 'Number of times P2 has attempted and failed this document')")
    log.info("Added chunk_retry_count column")
except Exception as e:
    if "already exists" in str(e).lower():
        log.info("chunk_retry_count column already exists — OK")
    else:
        raise
try:
    spark.sql(f"ALTER TABLE {METADATA_TABLE} ADD COLUMNS (metadata_retry_count INT COMMENT 'Number of times P1 has attempted and failed this document')")
    log.info("Added metadata_retry_count column")
except Exception as e:
    if "already exists" in str(e).lower() or "fields_already_exist" in str(e).lower():
        log.info("metadata_retry_count column already exists — OK")
    else:
        raise
try:
    spark.sql(f"ALTER TABLE {METADATA_TABLE} ADD COLUMNS (all_esns STRING COMMENT 'JSON array of all associated ESNs from fsr_pdf_ref + LLM detection')")
    log.info("Added all_esns column")
except Exception as e:
    if "already exists" in str(e).lower() or "fields_already_exist" in str(e).lower():
        log.info("all_esns column already exists — OK")
    else:
        raise

# ── ZORDER on document_id ────────────────────────────────────────
# P1's stub MERGE and per-doc UPDATEs all join on document_id. Without ZORDER,
# Delta file skipping degrades as the table grows past ~100k rows. OPTIMIZE
# is incremental and idempotent — cheap on subsequent runs.
try:
    spark.sql(f"OPTIMIZE {METADATA_TABLE} ZORDER BY (document_id)")
    log.info(f"OPTIMIZE ZORDER BY (document_id) completed on {METADATA_TABLE}")
except Exception as e:
    log.warning(f"OPTIMIZE ZORDER on {METADATA_TABLE} failed (non-blocking): {e}")
# COMMAND ----------

# ── Create chunk table (gold) ───────────────────────────────────────────────

# delta.deletedFileRetentionDuration is set to 30 days so the Databricks Vector
# Search managed sync pipeline can always replay the change stream. VS sync
# fails if its interval exceeds the source table's retention window (default
# 7 days) — observed in prod 2026-05-08 onwards when sync went stale.
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CHUNK_TABLE} (
        {CHUNK_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR chunk rows with materialized metadata and embeddings'
    TBLPROPERTIES (
        'delta.enableChangeDataFeed' = 'true',
        'delta.deletedFileRetentionDuration' = 'interval 30 days',
        'delta.autoOptimize.optimizeWrite' = 'true'
    )
""")
log.info(f"Chunk table ready: {CHUNK_TABLE}")

# Idempotent for existing tables — SET TBLPROPERTIES is a no-op if value matches.
spark.sql(f"ALTER TABLE {CHUNK_TABLE} SET TBLPROPERTIES ('delta.deletedFileRetentionDuration' = 'interval 30 days')")
log.info("Chunk table deletedFileRetentionDuration set to 30 days (VS sync safety)")

spark.sql(f"ALTER TABLE {CHUNK_TABLE} SET TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true')")
log.info("Chunk table autoOptimize.optimizeWrite enabled")

# ── ZORDER on chunk_id, document_id ────────────────────────────────
# P2's chunk MERGE joins on chunk_id (PK); ad-hoc queries filter by
# document_id. ZORDER on both lets Delta skip files for either access path.
try:
    spark.sql(f"OPTIMIZE {CHUNK_TABLE} ZORDER BY (chunk_id, document_id)")
    log.info(f"OPTIMIZE ZORDER BY (chunk_id, document_id) completed on {CHUNK_TABLE}")
except Exception as e:
    log.warning(f"OPTIMIZE ZORDER on {CHUNK_TABLE} failed (non-blocking): {e}")

# COMMAND ----------

# ── Create run audit log table ──────────────────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {RUN_LOG_TABLE} (
        {RUN_LOG_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR pipeline run audit log — one row per P2 run'
""")
log.info(f"Run log table ready: {RUN_LOG_TABLE}")

# COMMAND ----------

# ── Create data quality log table ───────────────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {DQ_LOG_TABLE} (
        {DQ_LOG_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR validation data quality findings — issues and warnings per doc'
""")
log.info(f"Data quality log table ready: {DQ_LOG_TABLE}")

# ── Schema evolution — add columns that may not exist on older tables ───────
try:
    spark.sql(f"ALTER TABLE {DQ_LOG_TABLE} ADD COLUMNS (failure_category STRING COMMENT 'Routing hint for terminal failures. Current values seen: corrupt_source, image_only_or_no_text, pdf_parse_error, partial_embed, gateway_error, unknown. Open to grow as SRE/ops categorize new patterns. NULL for non-terminal checks.')")
    log.info("Added failure_category column to DQ log table")
except Exception as e:
    if "already exists" in str(e).lower() or "fields_already_exist" in str(e).lower():
        log.info("failure_category column already exists — OK")
    else:
        raise

# COMMAND ----------

# ── Verify ──────────────────────────────────────────────────────────────────

for table_name in [METADATA_TABLE, CHUNK_TABLE, RUN_LOG_TABLE, DQ_LOG_TABLE]:
    count = spark.sql(f"SELECT COUNT(*) AS n FROM {table_name}").first().n
    cols = len(spark.table(table_name).columns)
    log.info(f"  {table_name}: {count} rows, {cols} columns")
