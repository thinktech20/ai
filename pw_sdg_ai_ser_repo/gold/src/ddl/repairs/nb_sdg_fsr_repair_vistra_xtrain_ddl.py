# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_repair_vistra_xtrain_ddl — DDL setup for Vistra cross-train repair
#
# Creates:
#   1) staging_vistra_gap
#   2) fsr_repair_vistra_chunk_inserts
#   3) fsr_repair_vistra_metadata_updates
#
# Idempotent: CREATE TABLE IF NOT EXISTS
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../../common/fsr_config

# COMMAND ----------

import logging
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.repair.vistra.ddl")

# COMMAND ----------

_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]

STAGING_TABLE = get_runtime_param(
    "STAGING_TABLE",
    f"{_sot_prefix}.staging_vistra_gap",
)
AUDIT_CHUNK_TABLE = get_runtime_param(
    "AUDIT_CHUNK_TABLE",
    f"{_std_prefix}.fsr_repair_vistra_chunk_inserts",
)
AUDIT_META_TABLE = get_runtime_param(
    "AUDIT_META_TABLE",
    f"{_sot_prefix}.fsr_repair_vistra_metadata_updates",
)

log.info("DDL targets:")
log.info(f"  STAGING_TABLE    : {STAGING_TABLE}")
log.info(f"  AUDIT_CHUNK_TABLE: {AUDIT_CHUNK_TABLE}")
log.info(f"  AUDIT_META_TABLE : {AUDIT_META_TABLE}")

# COMMAND ----------

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {STAGING_TABLE} (
        pdf_stem                 STRING,
        document_id              STRING,
        plant                    STRING,
        tagged_esn               STRING,
        tagged_equipment_type    STRING,
        tagged_event_type        STRING,
        matched_event_date       STRING,
        missing_esn              STRING,
        missing_equipment_type   STRING,
        sibling_event_type       STRING,
        sibling_event_id         STRING,
        keyword_count            INT,
        keywords_found           STRING,
        gap_confirmed            STRING,
        report_date              STRING,
        confidence               STRING,
        source                   STRING,
        dev_status               STRING,
        dev_processed_at         TIMESTAMP,
        dev_run_id               STRING,
        dev_error                STRING,
        prod_status              STRING,
        prod_processed_at        TIMESTAMP,
        prod_run_id              STRING,
        prod_error               STRING,
        loaded_at                TIMESTAMP
    )
    USING DELTA
    COMMENT 'Vistra cross-train repair staging table (xlsx-backed work ledger).'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false')
""")
log.info(f"Ready: {STAGING_TABLE}")

# COMMAND ----------

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {AUDIT_CHUNK_TABLE} (
        repair_run_id            STRING,
        document_id              STRING,
        base_document_id         STRING,
        chunk_id                 STRING,
        base_chunk_id            STRING,
        esn                      STRING,
        chunk_index              INT,
        inserted_at              TIMESTAMP
    )
    USING DELTA
    COMMENT 'Vistra repair audit: chunk rows inserted by run_id.'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false')
""")
log.info(f"Ready: {AUDIT_CHUNK_TABLE}")

# COMMAND ----------

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {AUDIT_META_TABLE} (
        repair_run_id            STRING,
        document_id              STRING,
        base_document_id         STRING,
        inserted_esn             STRING,
        inserted_at              TIMESTAMP
    )
    USING DELTA
    COMMENT 'Vistra repair audit: metadata rows inserted by run_id.'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false')
""")
log.info(f"Ready: {AUDIT_META_TABLE}")

# COMMAND ----------

meta_count = spark.sql(f"SELECT COUNT(*) AS cnt FROM {METADATA_TABLE}").first().cnt
chunk_count = spark.sql(f"SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE}").first().cnt
ibat_count = spark.sql(f"SELECT COUNT(*) AS cnt FROM {IBAT_EQUIPMENT_TABLE}").first().cnt

log.info("")
log.info("=" * 60)
log.info("  Vistra DDL SETUP COMPLETE")
log.info("=" * 60)
log.info(f"  Metadata rows: {meta_count:,}")
log.info(f"  Chunk rows   : {chunk_count:,}")
log.info(f"  IBAT rows    : {ibat_count:,}")

# COMMAND ----------

dbutils.notebook.exit(  # noqa: F821
    f"DDL OK: staging={STAGING_TABLE}, audit_chunk={AUDIT_CHUNK_TABLE}, "
    f"audit_meta={AUDIT_META_TABLE}"
)
