# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_ddl — Create FSR pipeline tables (metadata + chunks)
#
# Idempotent: uses CREATE TABLE IF NOT EXISTS.
# Run as the first task in the workflow to ensure tables exist before
# Process 1 and Process 2.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ./fsr_config

# COMMAND ----------

import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fsr.ddl")

# COMMAND ----------

# ── Create metadata registry table (silver) ─────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {METADATA_TABLE} (
        {METADATA_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR document-level metadata registry'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")
log.info(f"Metadata table ready: {METADATA_TABLE}")

# COMMAND ----------

# ── Create chunk table (gold) ───────────────────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CHUNK_TABLE} (
        {CHUNK_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'FSR chunk rows with materialized metadata and embeddings'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
""")
log.info(f"Chunk table ready: {CHUNK_TABLE}")

# COMMAND ----------

# ── Verify ──────────────────────────────────────────────────────────────────

for table_name in [METADATA_TABLE, CHUNK_TABLE]:
    count = spark.sql(f"SELECT COUNT(*) AS n FROM {table_name}").first().n
    cols = len(spark.table(table_name).columns)
    log.info(f"  {table_name}: {count} rows, {cols} columns")
