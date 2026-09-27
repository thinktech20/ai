# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_repair_ddl — DDL setup for Multi-ESN repair (#664196)
#
# Creates the audit tables used by the repair and revert notebooks.
# Idempotent: CREATE TABLE IF NOT EXISTS.
#
# Run as the FIRST task in the repair workflow to guarantee tables exist
# before any data operations.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import logging
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.repair.ddl")


def _ensure_run_id_column(table_fqn: str) -> None:
    """#664326 — idempotently add `run_id STRING` to an audit table.

    Databricks Spark SQL does not support `ALTER TABLE ... ADD COLUMNS IF NOT EXISTS`,
    so we check the catalog first and only ALTER when the column is missing.
    """
    cols = {row["col_name"].lower() for row in spark.sql(f"DESCRIBE TABLE {table_fqn}").collect()}
    if "run_id" in cols:
        return
    spark.sql(
        f"ALTER TABLE {table_fqn} ADD COLUMNS "
        f"(run_id STRING COMMENT '#664326 repair-run identifier')"
    )
    log.info(f"  Added missing column run_id to {table_fqn}")

# COMMAND ----------

# ── Derive audit table names ────────────────────────────────────────────────
_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]

AUDIT_CHUNK_INSERTS = f"{_std_prefix}.fsr_repair_664196_chunk_inserts"
AUDIT_METADATA_UPDATES = f"{_sot_prefix}.fsr_repair_664196_metadata_updates_v2"

RESET_AUDIT = get_runtime_param("RESET_AUDIT", "false").strip().lower() == "true"

log.info(f"DDL target audit tables:")
log.info(f"  {AUDIT_CHUNK_INSERTS}")
log.info(f"  {AUDIT_METADATA_UPDATES}")
log.info(f"  RESET_AUDIT: {RESET_AUDIT}")

# COMMAND ----------

# ── Reset audit tables if requested ──────────────────────────────────────────
if RESET_AUDIT:
    log.warning("RESET_AUDIT=true — dropping and recreating audit tables!")
    spark.sql(f"DROP TABLE IF EXISTS {AUDIT_CHUNK_INSERTS}")
    spark.sql(f"DROP TABLE IF EXISTS {AUDIT_METADATA_UPDATES}")
    log.warning(f"  Dropped: {AUDIT_CHUNK_INSERTS}")
    log.warning(f"  Dropped: {AUDIT_METADATA_UPDATES}")

# COMMAND ----------

# ── Create audit table: chunk inserts ────────────────────────────────────────
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {AUDIT_CHUNK_INSERTS} (
        chunk_id        STRING NOT NULL  COMMENT 'PK of inserted chunk row',
        document_id     STRING           COMMENT 'FK to metadata table',
        esn             STRING           COMMENT 'ESN assigned to this duplicate row',
        chunk_index     INT              COMMENT 'chunk position within document',
        repaired_at     TIMESTAMP        COMMENT 'when this INSERT was executed',
        run_id          STRING           COMMENT '#664326 repair-run identifier (UUID); enables per-run revert in incremental mode'
    )
    USING DELTA
    COMMENT '#664196 Multi-ESN repair audit — tracks every chunk row inserted. Used by revert workflow.'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false')
""")
# Idempotent column add for tables that pre-date #664326
_ensure_run_id_column(AUDIT_CHUNK_INSERTS)
log.info(f"Ready: {AUDIT_CHUNK_INSERTS}")

# COMMAND ----------

# ── Create audit table: metadata updates ─────────────────────────────────────
# #664326 — schema upgrades happen via the idempotent _ensure_run_id_column()
# helper below; no DROP needed (and DROP fails for users without MANAGE).

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {AUDIT_METADATA_UPDATES} (
        document_id             STRING NOT NULL  COMMENT 'PK of updated metadata row',
        old_esn                 STRING           COMMENT 'ESN value BEFORE repair',
        old_esn_source          STRING           COMMENT 'esn_source BEFORE repair',
        old_equipment_sys_id    STRING           COMMENT 'equipment_sys_id BEFORE repair',
        old_equipment_type      STRING           COMMENT 'equipment_type BEFORE repair',
        old_equipment_class_code STRING          COMMENT 'equipment_class_code BEFORE repair',
        new_esn                 STRING           COMMENT 'ESN value AFTER repair',
        new_esn_source          STRING           COMMENT 'esn_source AFTER repair',
        new_equipment_sys_id    STRING           COMMENT 'equipment_sys_id AFTER repair',
        new_equipment_type      STRING           COMMENT 'equipment_type AFTER repair',
        new_equipment_class_code STRING          COMMENT 'equipment_class_code AFTER repair',
        repaired_at             TIMESTAMP        COMMENT 'when this UPDATE was executed',
        run_id                  STRING           COMMENT '#664326 repair-run identifier (UUID); enables per-run revert in incremental mode'
    )
    USING DELTA
    COMMENT '#664196 Multi-ESN repair audit — before-state of metadata updates. Used by revert workflow.'
    TBLPROPERTIES ('delta.enableChangeDataFeed' = 'false')
""")
# Idempotent column add for tables that pre-date #664326
_ensure_run_id_column(AUDIT_METADATA_UPDATES)
log.info(f"Ready: {AUDIT_METADATA_UPDATES}")

# COMMAND ----------

# ── Validate ref view accessibility ──────────────────────────────────────────
log.info(f"Checking access to fsr_pdf_ref view: {FSR_PDF_REF_VIEW}")

ref_count = spark.sql(f"SELECT COUNT(*) AS cnt FROM {FSR_PDF_REF_VIEW}").first().cnt
log.info(f"  fsr_pdf_ref total rows: {ref_count:,}")

if ref_count == 0:
    raise RuntimeError(
        f"fsr_pdf_ref view ({FSR_PDF_REF_VIEW}) is EMPTY. "
        "Cannot proceed — repair relies on this as ESN authority."
    )

multi_esn_docs = spark.sql(f"""
    SELECT COUNT(*) AS cnt FROM (
        SELECT s3_filename
        FROM {FSR_PDF_REF_VIEW}
        WHERE esn IS NOT NULL AND TRIM(esn) != ''
        GROUP BY s3_filename
        HAVING COUNT(DISTINCT esn) > 1
    )
""").first().cnt
log.info(f"  Multi-ESN documents in ref: {multi_esn_docs:,}")

# COMMAND ----------

# ── Validate chunk & metadata table accessibility ────────────────────────────
log.info(f"Checking access to data tables...")

meta_count = spark.sql(f"SELECT COUNT(*) AS cnt FROM {METADATA_TABLE}").first().cnt
chunk_count = spark.sql(f"SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE}").first().cnt
log.info(f"  Metadata table rows: {meta_count:,}")
log.info(f"  Chunk table rows   : {chunk_count:,}")

if meta_count == 0:
    raise RuntimeError(f"Metadata table ({METADATA_TABLE}) is EMPTY — nothing to repair.")
if chunk_count == 0:
    raise RuntimeError(f"Chunk table ({CHUNK_TABLE}) is EMPTY — nothing to repair.")

# COMMAND ----------

log.info("")
log.info("=" * 60)
log.info("  DDL SETUP COMPLETE — ready for repair execution")
log.info("=" * 60)
log.info(f"  Audit tables created (if not existed)")
log.info(f"  Ref view accessible ({ref_count:,} rows, {multi_esn_docs:,} multi-ESN docs)")
log.info(f"  Data tables accessible (meta: {meta_count:,}, chunks: {chunk_count:,})")
log.info("")

dbutils.notebook.exit(  # noqa: F821
    f"DDL OK: audit tables ready, ref={ref_count:,} rows ({multi_esn_docs:,} multi-ESN), "
    f"meta={meta_count:,}, chunks={chunk_count:,}"
)
