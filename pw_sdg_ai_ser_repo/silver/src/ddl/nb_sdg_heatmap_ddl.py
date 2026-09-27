# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_heatmap_ddl — Create Heatmap embedding table
#
# Idempotent: uses CREATE TABLE IF NOT EXISTS.
# Run as the first task in the Heatmap workflow.
#
# When FORCE_RESET=true, drops and recreates the table.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/heatmap_config

# COMMAND ----------

import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("heatmap.ddl")

# COMMAND ----------

# ── FORCE_RESET: drop table ────────────────────────────────────────────────

if FORCE_RESET:
    spark.sql(f"DROP TABLE IF EXISTS {HEATMAP_EMBEDDING_TABLE}")
    log.warning(f"FORCE_RESET: dropped {HEATMAP_EMBEDDING_TABLE}")

# COMMAND ----------

# ── Create schema if not exists ─────────────────────────────────────────────
# Derive catalog.schema from HEATMAP_EMBEDDING_TABLE (format: catalog.schema.table)

_parts = HEATMAP_EMBEDDING_TABLE.split(".")
if len(_parts) >= 3:
    _schema_fqn = f"{_parts[0]}.{_parts[1]}"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {_schema_fqn}")
    log.info(f"Schema ready: {_schema_fqn}")

# COMMAND ----------

# ── Create embedding table ──────────────────────────────────────────────────

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {HEATMAP_EMBEDDING_TABLE} (
        {HEATMAP_TABLE_DDL_COLS}
    )
    USING DELTA
    COMMENT 'Heatmap issue_prompt embeddings'
""")
log.info(f"Heatmap embedding table ready: {HEATMAP_EMBEDDING_TABLE}")

# COMMAND ----------

# ── Verify ──────────────────────────────────────────────────────────────────

count = spark.sql(f"SELECT COUNT(*) AS n FROM {HEATMAP_EMBEDDING_TABLE}").first().n
cols = len(spark.table(HEATMAP_EMBEDDING_TABLE).columns)
log.info(f"  {HEATMAP_EMBEDDING_TABLE}: {count} rows, {cols} columns")
