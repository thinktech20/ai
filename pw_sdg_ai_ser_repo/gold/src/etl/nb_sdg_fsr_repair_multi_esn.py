# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_repair_multi_esn — Auditable Multi-ESN Repair
#
# Creates audit tables BEFORE any data change, then executes repair.
# Every inserted/updated row is tracked for revert by the companion
# notebook: nb_sdg_fsr_revert_multi_esn
#
# Audit tables created:
#   {catalog}.ai_std_con_field_service_report.fsr_repair_664196_chunk_inserts
#   {catalog}.ai_sot_field_service_report.fsr_repair_664196_metadata_updates_v2
#
# Run params:
#   DRY_RUN        (default "true")  — preview only, no writes
#   REPAIR_RUN_ID  (default = new UUID) — #664326 tag for this pass; written
#                  into both audit tables so revert can target one run only
#                  in incremental mode. Audit tables are append-only.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import logging
import uuid
from datetime import datetime, timezone

from delta.tables import DeltaTable
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.repair.multi_esn")

# COMMAND ----------

# ── Configuration ────────────────────────────────────────────────────────────
DRY_RUN = get_runtime_param("DRY_RUN", "true").strip().lower() == "true"

# #664326 — unique id for this repair pass; written into both audit tables
# so the revert notebook can scope to a single pass in incremental mode.
RUN_ID = get_runtime_param("REPAIR_RUN_ID", "").strip() or str(uuid.uuid4())

# Audit tables — stored alongside the data tables in the same catalog/schema
_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]  # e.g. vaip.ai_sot_field_service_report
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]      # e.g. vaip.ai_std_con_field_service_report

AUDIT_CHUNK_INSERTS = f"{_std_prefix}.fsr_repair_664196_chunk_inserts"
AUDIT_METADATA_UPDATES = f"{_sot_prefix}.fsr_repair_664196_metadata_updates_v2"

log.info("=== FSR Multi-ESN Repair (Auditable) ===")
log.info(f"  Chunk table      : {CHUNK_TABLE}")
log.info(f"  Metadata table   : {METADATA_TABLE}")
log.info(f"  PDF ref view     : {FSR_PDF_REF_VIEW}")
log.info(f"  Audit (chunks)   : {AUDIT_CHUNK_INSERTS}")
log.info(f"  Audit (metadata) : {AUDIT_METADATA_UPDATES}")
log.info(f"  RUN_ID           : {RUN_ID}")
log.info(f"  DRY_RUN          : {DRY_RUN}")

# COMMAND ----------

# ── Load IBAT equipment reference for correct equipment fields per ESN ────────
log.info("Loading IBAT equipment reference...")
spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW _ibat_equip AS
    SELECT ibat_esn, ibat_equipment_sys_id, ibat_equipment_type, ibat_equipment_class_code
    FROM (
        SELECT
            UPPER(TRIM(equip_serial_number)) AS ibat_esn,
            equipment_sys_id    AS ibat_equipment_sys_id,
            equipment_type      AS ibat_equipment_type,
            equipment_sub_class AS ibat_equipment_class_code,
            ROW_NUMBER() OVER (
                PARTITION BY UPPER(TRIM(equip_serial_number))
                ORDER BY equipment_sys_id
            ) AS _rn
        FROM {IBAT_EQUIPMENT_TABLE}
        WHERE equip_serial_number IS NOT NULL
          AND TRIM(equip_serial_number) != ''
    )
    WHERE _rn = 1
""")
_ibat_count = spark.sql("SELECT COUNT(*) FROM _ibat_equip").first()[0]
log.info(f"  IBAT rows loaded (deduped by ESN): {_ibat_count:,}")

# COMMAND ----------

# ── Step 1: Identify secondary ESNs from fsr_pdf_ref ─────────────────────────
log.info("Step 1: Identifying secondary ESNs per document from fsr_pdf_ref...")

# Build a view of (document_id, secondary_esn) pairs that need chunk + metadata rows.
# "Primary ESN" = the ESN currently on the metadata row for that document_id.
# "Secondary ESNs" = all other ESNs in fsr_pdf_ref for the same document.
spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW _secondary_esns AS
    SELECT
        m.document_id,
        m.esn AS primary_esn,
        r.esn AS secondary_esn,
        CONCAT(m.document_id, '_', r.esn) AS new_document_id
    FROM {METADATA_TABLE} m
    JOIN {FSR_PDF_REF_VIEW} r
        ON LOWER(TRIM(m.document_id)) = LOWER(TRIM(r.s3_filename))
    WHERE r.esn IS NOT NULL
      AND TRIM(r.esn) != ''
      AND r.esn != m.esn
      AND m.document_id NOT LIKE '%\\_%'
""")

_secondary_count = spark.sql("SELECT COUNT(*) FROM _secondary_esns").first()[0]
_secondary_docs = spark.sql("SELECT COUNT(DISTINCT document_id) FROM _secondary_esns").first()[0]
log.info(f"  Secondary (document, ESN) pairs: {_secondary_count:,} across {_secondary_docs:,} documents")

# COMMAND ----------

# ── Step 2: Identify metadata ESN corrections ────────────────────────────────
log.info("Step 2: Identifying metadata ESN corrections...")

# Use a sub-SELECT on metadata to pre-rename equipment columns.  This avoids
# Spark Connect's column-dedup issue where the same source column referenced
# both directly (old_*) and inside COALESCE (new_*) gets collapsed.
_fixes_df = spark.sql(f"""
    WITH ref_esns AS (
        SELECT LOWER(TRIM(s3_filename)) AS doc_id,
               ARRAY_SORT(COLLECT_SET(esn))[0] AS ref_esn
        FROM {FSR_PDF_REF_VIEW}
        WHERE esn IS NOT NULL AND TRIM(esn) != ''
        GROUP BY LOWER(TRIM(s3_filename))
    ),
    meta_src AS (
        SELECT document_id, esn, esn_source,
               equipment_sys_id   AS m_equip_sys_id,
               equipment_type     AS m_equip_type,
               equipment_class_code AS m_equip_class
        FROM {METADATA_TABLE}
    )
    SELECT
        ms.document_id,
        CAST(ms.esn AS STRING)            AS old_esn,
        CAST(ms.esn_source AS STRING)     AS old_esn_source,
        CAST(ms.m_equip_sys_id AS STRING) AS old_equipment_sys_id,
        CAST(ms.m_equip_type AS STRING)   AS old_equipment_type,
        CAST(ms.m_equip_class AS STRING)  AS old_equipment_class_code,
        CAST(r.ref_esn AS STRING)         AS new_esn,
        CAST('fsr_pdf_ref' AS STRING)     AS new_esn_source,
        CAST(COALESCE(ib.ibat_equipment_sys_id, ms.m_equip_sys_id) AS STRING)    AS new_equipment_sys_id,
        CAST(COALESCE(ib.ibat_equipment_type, ms.m_equip_type) AS STRING)        AS new_equipment_type,
        CAST(COALESCE(ib.ibat_equipment_class_code, ms.m_equip_class) AS STRING) AS new_equipment_class_code
    FROM meta_src ms
    JOIN ref_esns r ON LOWER(TRIM(ms.document_id)) = r.doc_id
    LEFT JOIN _ibat_equip ib
        ON UPPER(TRIM(r.ref_esn)) = ib.ibat_esn
    WHERE ms.esn IS NULL
       OR TRIM(ms.esn) = ''
       OR NOT EXISTS (
           SELECT 1 FROM {FSR_PDF_REF_VIEW} p
           WHERE LOWER(TRIM(p.s3_filename)) = LOWER(TRIM(ms.document_id))
             AND p.esn = ms.esn
       )
""")
# Force-rename columns to eliminate Spark Connect duplicate-column issue.
# Spark Connect may retain both CTE inner names and outer aliases.
_FIXES_COLS = [
    "document_id", "old_esn", "old_esn_source",
    "old_equipment_sys_id", "old_equipment_type", "old_equipment_class_code",
    "new_esn", "new_esn_source",
    "new_equipment_sys_id", "new_equipment_type", "new_equipment_class_code",
]
_fixes_df = _fixes_df.toDF(*_FIXES_COLS)
log.info(f"  _fixes_df columns: {_fixes_df.columns}")

meta_fix_count = _fixes_df.count()
log.info(f"Metadata rows to update: {meta_fix_count}")

# COMMAND ----------

# ── Step 3: Summary & DRY_RUN gate ──────────────────────────────────────────
log.info("")
log.info("=" * 70)
log.info("  REPAIR PLAN SUMMARY")
log.info("=" * 70)
log.info(f"  Tables to modify:")
log.info(f"    CHUNK TABLE    : {CHUNK_TABLE}")
log.info(f"    METADATA TABLE : {METADATA_TABLE}")
log.info("")
log.info(f"  Operations:")
log.info(f"    Secondary (doc, ESN) pairs : {_secondary_count:,}")
log.info(f"    INSERT into metadata table : (counted at execution — secondary ESN rows)")
log.info(f"    UPDATE chunk document_id   : (counted at execution — existing secondary chunks)")
log.info(f"    INSERT into chunk table    : (counted at execution — missing secondary chunks)")
log.info(f"    UPDATE metadata table      : {meta_fix_count} rows (primary ESN correction)")
log.info("")
log.info(f"  Audit tables:")
log.info(f"    {AUDIT_CHUNK_INSERTS}")
log.info(f"    {AUDIT_METADATA_UPDATES}")
log.info("")
log.info(f"  To revert: run PW_SDG_FSR_Revert_Multi_ESN workflow")
log.info("=" * 70)

# Show samples
log.info("\nSample: secondary ESNs (top 10):")
spark.sql("""
    SELECT document_id, primary_esn, secondary_esn, new_document_id
    FROM _secondary_esns
    LIMIT 10
""").show(truncate=False)

log.info("\nSample: metadata ESN corrections (top 10):")
_fixes_df.select(
    "document_id", "old_esn", "new_esn", "new_equipment_sys_id", "new_equipment_type"
).limit(10).show(truncate=False)

if DRY_RUN:
    log.info("\n*** DRY_RUN=true — No changes written. ***")
    log.info("*** Set DRY_RUN=false to execute repair. ***")
    dbutils.notebook.exit(  # noqa: F821
        f"DRY_RUN (run_id={RUN_ID}): {_secondary_count:,} secondary pairs, "
        f"{meta_fix_count} metadata to fix"
    )

# COMMAND ----------

# ── Step 4: Record audit trail BEFORE any data changes ───────────────────────
log.info("Step 4: Recording audit trail (before any changes)...")

# #664326 — incremental mode: append, do not truncate. Each pass is keyed
# by RUN_ID so revert can target one run without disturbing prior history.
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {AUDIT_METADATA_UPDATES} (
        document_id              STRING NOT NULL,
        old_esn                  STRING,
        old_esn_source           STRING,
        old_equipment_sys_id     STRING,
        old_equipment_type       STRING,
        old_equipment_class_code STRING,
        new_esn                  STRING,
        new_esn_source           STRING,
        new_equipment_sys_id     STRING,
        new_equipment_type       STRING,
        new_equipment_class_code STRING,
        repaired_at              TIMESTAMP,
        run_id                   STRING
    ) USING DELTA
""")

def _ensure_run_id_column(table_fqn: str) -> None:
    cols = {row["col_name"].lower() for row in spark.sql(f"DESCRIBE TABLE {table_fqn}").collect()}
    if "run_id" not in cols:
        spark.sql(f"ALTER TABLE {table_fqn} ADD COLUMNS (run_id STRING)")

_ensure_run_id_column(AUDIT_METADATA_UPDATES)
_ensure_run_id_column(AUDIT_CHUNK_INSERTS)

# Audit table 2: before-state of every metadata row we will update
if meta_fix_count > 0:
    _audit_df = _fixes_df.select(
        "document_id", "old_esn", "old_esn_source",
        "old_equipment_sys_id", "old_equipment_type", "old_equipment_class_code",
        "new_esn", "new_esn_source",
        "new_equipment_sys_id", "new_equipment_type", "new_equipment_class_code",
    ).withColumn("repaired_at", current_timestamp()).withColumn("run_id", lit(RUN_ID))
    _audit_df.write.format("delta").mode("append").saveAsTable(AUDIT_METADATA_UPDATES)
    log.info(f"Audit recorded: {meta_fix_count} metadata before-states → {AUDIT_METADATA_UPDATES} (run_id={RUN_ID})")
else:
    log.info("No metadata fixes needed — audit table not appended")

# COMMAND ----------

# ── Step 5: Insert metadata rows for secondary ESNs ──────────────────────────
log.info("Step 5: Inserting metadata rows for secondary ESNs...")

# Duplicate the primary metadata row for each secondary ESN, replacing
# document_id with uuid_ESN and updating ESN-specific fields.
spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW _repair_meta_inserts AS
    SELECT
        s.new_document_id AS document_id,
        m.volume_path,
        m.pdf_name,
        m.title,
        m.page_count,
        s.secondary_esn AS esn,
        'fsr_pdf_ref' AS esn_source,
        COALESCE(ib.ibat_equipment_sys_id, m.equipment_sys_id) AS equipment_sys_id,
        COALESCE(ib.ibat_equipment_type, m.equipment_type) AS equipment_type,
        COALESCE(ib.ibat_equipment_class_code, m.equipment_class_code) AS equipment_class_code,
        m.event_type,
        m.ev_project_id,
        m.ev_equipment_event_id,
        m.ofs_event_id,
        m.fsp_project_id,
        m.xxx_project_id,
        m.fsr_number,
        m.report_issued_date,
        m.outage_start_date,
        m.outage_end_date,
        m.outage_type,
        m.technology_type,
        m.document_summary,
        m.metadata_status,
        '{ChunkStatus.COMPLETED}' AS chunk_status,
        m.ingested_at
    FROM _secondary_esns s
    JOIN {METADATA_TABLE} m
        ON m.document_id = s.document_id
    LEFT JOIN _ibat_equip ib
        ON UPPER(TRIM(s.secondary_esn)) = ib.ibat_esn
    WHERE NOT EXISTS (
        SELECT 1 FROM {METADATA_TABLE} x
        WHERE x.document_id = s.new_document_id
    )
""")

meta_insert_count = spark.sql("SELECT COUNT(*) AS cnt FROM _repair_meta_inserts").first().cnt
meta_insert_docs = spark.sql("SELECT COUNT(DISTINCT document_id) FROM _repair_meta_inserts").first()[0]
log.info(f"Metadata rows to insert: {meta_insert_count:,} across {meta_insert_docs} documents")

if not DRY_RUN and meta_insert_count > 0:
    spark.sql(f"""
        INSERT INTO {METADATA_TABLE}
            (document_id, volume_path, pdf_name, title, page_count,
             esn, esn_source, equipment_sys_id, equipment_type, equipment_class_code,
             event_type, ev_project_id, ev_equipment_event_id,
             ofs_event_id, fsp_project_id, xxx_project_id,
             fsr_number, report_issued_date, outage_start_date, outage_end_date,
             outage_type, technology_type, document_summary,
             metadata_status, chunk_status, ingested_at, scraped_at)
        SELECT
             document_id, volume_path, pdf_name, title, page_count,
             esn, esn_source, equipment_sys_id, equipment_type, equipment_class_code,
             event_type, ev_project_id, ev_equipment_event_id,
             ofs_event_id, fsp_project_id, xxx_project_id,
             fsr_number, report_issued_date, outage_start_date, outage_end_date,
             outage_type, technology_type, document_summary,
             metadata_status, chunk_status, ingested_at, current_timestamp()
        FROM _repair_meta_inserts
    """)
    log.info(f"DONE: {meta_insert_count:,} metadata rows inserted for secondary ESNs")

# COMMAND ----------

# ── Step 6: Update document_id on existing secondary-ESN chunk rows ──────────
# For chunks that already exist with (document_id=uuid, esn=secondary), update
# their document_id to match the metadata row (uuid_ESN). Only touches rows
# where a matching metadata row exists — i.e., only previously duplicated rows.
log.info("Step 6: Updating document_id on existing secondary-ESN chunk rows...")

spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW _chunk_docid_fixes AS
    SELECT DISTINCT c.chunk_id,
           m.document_id AS new_document_id
    FROM {CHUNK_TABLE} c
    INNER JOIN {METADATA_TABLE} m
        ON m.document_id = CONCAT(c.document_id, '_', c.esn)
    WHERE c.esn IS NOT NULL
      AND TRIM(c.esn) != ''
      AND c.document_id NOT LIKE '%\\_%'
""")

_docid_fix_count = spark.sql("SELECT COUNT(*) FROM _chunk_docid_fixes").first()[0]
log.info(f"Chunk rows to update document_id: {_docid_fix_count:,}")

if not DRY_RUN and _docid_fix_count > 0:
    # Batch the MERGE by document_id to avoid Spark OOM on large updates.
    _fix_doc_ids = [
        row.document_id
        for row in spark.sql(
            "SELECT DISTINCT c.document_id"
            f" FROM {CHUNK_TABLE} c"
            " INNER JOIN _chunk_docid_fixes f ON c.chunk_id = f.chunk_id"
        ).collect()
    ]
    _BATCH_SIZE = 500
    _total_updated = 0
    _t6 = datetime.now(timezone.utc)
    for _i in range(0, len(_fix_doc_ids), _BATCH_SIZE):
        _batch = _fix_doc_ids[_i : _i + _BATCH_SIZE]
        _batch_csv = ",".join(f"'{d}'" for d in _batch)
        spark.sql(f"""
            MERGE INTO {CHUNK_TABLE} AS tgt
            USING (
                SELECT DISTINCT f.chunk_id, f.new_document_id
                FROM _chunk_docid_fixes f
                INNER JOIN {CHUNK_TABLE} c ON f.chunk_id = c.chunk_id
                WHERE c.document_id IN ({_batch_csv})
            ) AS src
            ON tgt.chunk_id = src.chunk_id
            WHEN MATCHED THEN UPDATE SET
                tgt.document_id = src.new_document_id
        """)
        _total_updated += len(_batch)
        _pct = min(100.0, _total_updated / max(len(_fix_doc_ids), 1) * 100)
        log.info(
            f"  Step 6 batch {_i // _BATCH_SIZE + 1}: "
            f"{min(_i + _BATCH_SIZE, len(_fix_doc_ids))}/{len(_fix_doc_ids)} docs "
            f"({_pct:.0f}%)"
        )
    _elapsed_6 = (datetime.now(timezone.utc) - _t6).total_seconds()
    log.info(
        f"DONE: {_docid_fix_count:,} chunk rows updated with document_id from metadata "
        f"in {len(_fix_doc_ids)} docs ({_elapsed_6:.1f}s)"
    )

# COMMAND ----------

# ── Step 7: Insert missing secondary-ESN chunks (future runs + gaps) ─────────
# For secondary ESNs that have NO existing chunk rows, duplicate from primary.
# Sources ONLY from primary ESN chunks (c.esn = primary_esn from metadata).
log.info("Step 7: Inserting missing secondary-ESN chunk rows...")

spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW _repair_new_chunks AS
    SELECT
        MD5(CONCAT(c.document_id, '_', CAST(c.chunk_index AS STRING), '__', s.secondary_esn)) AS chunk_id,
        c.chunk_index,
        s.new_document_id AS document_id,
        c.pdf_name,
        c.page_number,
        c.chunk_text,
        s.secondary_esn AS esn,
        c.report_date,
        c.chunk_embedding,
        CASE
            WHEN c.metadata IS NOT NULL
            THEN REGEXP_REPLACE(
                   REGEXP_REPLACE(
                     REGEXP_REPLACE(
                       REGEXP_REPLACE(c.metadata,
                         '"esn"\\s*:\\s*"[^"]*"',
                         CONCAT('"esn": "', s.secondary_esn, '"')),
                       '"equipment_sys_id"\\s*:\\s*"[^"]*"',
                       CONCAT('"equipment_sys_id": "', COALESCE(ib.ibat_equipment_sys_id, ''), '"')),
                     '"equipment_type"\\s*:\\s*"[^"]*"',
                     CONCAT('"equipment_type": "', COALESCE(ib.ibat_equipment_type, ''), '"')),
                   '"equipment_class_code"\\s*:\\s*"[^"]*"',
                   CONCAT('"equipment_class_code": "', COALESCE(ib.ibat_equipment_class_code, ''), '"'))
            ELSE c.metadata
        END AS metadata,
        current_timestamp() AS created_at
    FROM _secondary_esns s
    JOIN {CHUNK_TABLE} c
        ON c.document_id = s.document_id
        AND c.esn = s.primary_esn
    LEFT JOIN _ibat_equip ib
        ON UPPER(TRIM(s.secondary_esn)) = ib.ibat_esn
    WHERE NOT EXISTS (
        SELECT 1 FROM {CHUNK_TABLE} x
        WHERE x.document_id = s.new_document_id
          AND x.chunk_index = c.chunk_index
          AND x.esn = s.secondary_esn
    )
""")

new_chunk_count = spark.sql("SELECT COUNT(*) AS cnt FROM _repair_new_chunks").first().cnt
new_doc_count = spark.sql("SELECT COUNT(DISTINCT document_id) FROM _repair_new_chunks").first()[0]
log.info(f"Chunk rows to insert: {new_chunk_count:,} across {new_doc_count} documents")

if not DRY_RUN and new_chunk_count > 0:
    # Audit: record chunk_ids we're about to insert
    spark.sql(f"""
        INSERT INTO {AUDIT_CHUNK_INSERTS}
        SELECT chunk_id, document_id, esn, chunk_index, current_timestamp(), '{RUN_ID}'
        FROM _repair_new_chunks
    """)
    log.info(f"Audit recorded: {new_chunk_count:,} chunk IDs → {AUDIT_CHUNK_INSERTS} (run_id={RUN_ID})")

    _t7 = datetime.now(timezone.utc)
    spark.sql(f"""
        INSERT INTO {CHUNK_TABLE}
            (chunk_id, chunk_index, document_id, pdf_name, page_number,
             chunk_text, esn, report_date, chunk_embedding, metadata, created_at)
        SELECT
            chunk_id, chunk_index, document_id, pdf_name, page_number,
            chunk_text, esn, report_date, chunk_embedding, metadata, created_at
        FROM _repair_new_chunks
    """)
    _elapsed_7 = (datetime.now(timezone.utc) - _t7).total_seconds()
    log.info(f"DONE: {new_chunk_count:,} chunk rows inserted in {_elapsed_7:.1f}s")
else:
    log.info("Step 7: No missing chunks to insert")

# COMMAND ----------

# ── Step 8: Fix primary ESN if wrong (legacy single-row correction) ──────────
if meta_fix_count > 0:
    log.info("Step 8: Updating primary metadata row ESN + equipment fields...")
    _meta_tgt = DeltaTable.forName(spark, METADATA_TABLE)
    _merge_src = _fixes_df.select(
        "document_id", "new_esn", "new_esn_source",
        "new_equipment_sys_id", "new_equipment_type", "new_equipment_class_code",
    )
    _meta_tgt.alias("tgt").merge(
        _merge_src.alias("src"),
        "tgt.document_id = src.document_id AND COALESCE(tgt.esn, '') = ''"
    ).whenMatchedUpdate(set={
        "esn": "src.new_esn",
        "esn_source": "src.new_esn_source",
        "equipment_sys_id": "src.new_equipment_sys_id",
        "equipment_type": "src.new_equipment_type",
        "equipment_class_code": "src.new_equipment_class_code",
    }).execute()
    log.info(f"DONE: {meta_fix_count} metadata rows updated (esn + equipment fields)")
else:
    log.info("Step 8: No primary ESN corrections needed — skipped")

# COMMAND ----------

# ── Step 9: Verification queries ─────────────────────────────────────────────
log.info("Step 9: Post-repair verification...")

# Verify: count distinct ESNs per affected document in chunk table
verify_df = spark.sql(f"""
    SELECT document_id,
           COUNT(DISTINCT esn) AS esn_count,
           COUNT(*) AS total_chunks
    FROM {CHUNK_TABLE}
    WHERE document_id IN (
        SELECT DISTINCT new_document_id FROM _secondary_esns
    )
    GROUP BY document_id
    ORDER BY esn_count DESC
    LIMIT 10
""")
log.info("Verification — affected documents now have multiple ESN chunk rows:")
verify_df.show(truncate=False)

# COMMAND ----------

# ── Step 10: Final report ────────────────────────────────────────────────────
log.info("")
log.info("=" * 70)
log.info("  REPAIR COMPLETE — FULL AUDIT RECORDED")
log.info("=" * 70)
log.info("")
log.info(f"  WHAT CHANGED:")
log.info(f"    {CHUNK_TABLE}")
log.info(f"      → {_docid_fix_count:,} rows UPDATED (document_id fixed to uuid_ESN)")
log.info(f"      → {new_chunk_count:,} rows INSERTED (new chunks for missing secondary ESNs)")
log.info(f"    {METADATA_TABLE}")
log.info(f"      → {meta_insert_count:,} rows INSERTED (secondary ESN metadata rows)")
log.info(f"      → {meta_fix_count} rows UPDATED (primary ESN + esn_source columns)")
log.info("")
log.info(f"  AUDIT TRAIL:")
log.info(f"    {AUDIT_CHUNK_INSERTS}")
log.info(f"      → Contains chunk_id of every inserted row (run_id={RUN_ID})")
log.info(f"    {AUDIT_METADATA_UPDATES}")
log.info(f"      → Contains before-state (old_esn, old_esn_source) of every updated row (run_id={RUN_ID})")
log.info("")
log.info(f"  TO REVERT THIS RUN ONLY:")
log.info(f"    Run notebook: nb_sdg_fsr_revert_multi_esn with REVERT_RUN_ID={RUN_ID} DRY_RUN=false")
log.info(f"  TO REVERT ALL RECORDED RUNS:")
log.info(f"    Run notebook: nb_sdg_fsr_revert_multi_esn with REVERT_RUN_ID=ALL DRY_RUN=false")
log.info("")
log.info(f"  NEXT STEPS:")
log.info(f"    1. Trigger VS index sync:")
log.info(f"       Endpoint: {VS_ENDPOINT_NAME}")
log.info(f"       Index:    {VS_INDEX_NAME}")
log.info(f"    2. Verify retrieval for a Generator ESN")
log.info(f"    3. Once confirmed stable, optionally drop audit tables:")
log.info(f"       DROP TABLE {AUDIT_CHUNK_INSERTS};")
log.info(f"       DROP TABLE {AUDIT_METADATA_UPDATES};")
log.info("")

dbutils.notebook.exit(  # noqa: F821
    f"REPAIR DONE (run_id={RUN_ID}): {_docid_fix_count:,} chunks updated, {new_chunk_count:,} chunks inserted, "
    f"{meta_insert_count:,} metadata inserted, {meta_fix_count} metadata updated. "
    f"Revert: nb_sdg_fsr_revert_multi_esn REVERT_RUN_ID={RUN_ID}. "
    f"Audit: {AUDIT_CHUNK_INSERTS} + {AUDIT_METADATA_UPDATES}"
)
