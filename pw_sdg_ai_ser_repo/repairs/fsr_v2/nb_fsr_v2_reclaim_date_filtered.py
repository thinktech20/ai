# Databricks notebook source
# Requeue rows skipped by the retired one-time document-year filter.

# COMMAND ----------

import logging

from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.reclaim.date_filtered")

spark = SparkSession.builder.getOrCreate()

dbutils.widgets.text("METADATA_TABLE_V2", "")  # noqa: F821
dbutils.widgets.dropdown("RECLAIM_DRY_RUN", "true", ["true", "false"])  # noqa: F821

METADATA_TABLE = dbutils.widgets.get("METADATA_TABLE_V2").strip()  # noqa: F821
DRY_RUN = dbutils.widgets.get("RECLAIM_DRY_RUN").strip().lower() != "false"  # noqa: F821

if not METADATA_TABLE:
    raise ValueError("METADATA_TABLE_V2 is required")

before_count = spark.sql(f"""
    SELECT COUNT(*) AS docs
    FROM {METADATA_TABLE}
    WHERE metadata_status = 'date_filtered'
""").first().docs

log.info("Legacy date-filtered rows: %d", before_count)

if DRY_RUN:
    dbutils.notebook.exit(f"DRY_RUN: {before_count} row(s) would be reclaimed")  # noqa: F821

spark.sql(f"""
    UPDATE {METADATA_TABLE}
    SET metadata_status = 'pending',
        metadata_error = NULL,
        updated_at = current_timestamp()
    WHERE metadata_status = 'date_filtered'
""")

after_count = spark.sql(f"""
    SELECT COUNT(*) AS docs
    FROM {METADATA_TABLE}
    WHERE metadata_status = 'date_filtered'
""").first().docs

if after_count:
    raise RuntimeError(f"Reclaim incomplete: {after_count} date_filtered row(s) remain")

dbutils.notebook.exit(f"RECLAIMED: {before_count} row(s) moved to pending")  # noqa: F821