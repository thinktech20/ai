# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_revert_multi_esn — Revert Multi-ESN Repair
#
# Reads audit tables written by nb_sdg_fsr_repair_multi_esn and undoes
# all changes:
#   - DELETEs chunk rows that were inserted
#   - RESTOREs metadata ESN values to their pre-repair state
#
# Audit tables consumed:
#   {catalog}.ai_std_con_field_service_report.fsr_repair_664196_chunk_inserts
#   {catalog}.ai_sot_field_service_report.fsr_repair_664196_metadata_updates_v2
#
# Run params:
#   DRY_RUN        (default "true")  — preview only, no writes
#   REVERT_RUN_ID  (default "" → latest run_id in chunk audit; "ALL" reverts every recorded run)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import logging

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.revert.multi_esn")

# COMMAND ----------

# ── Configuration ────────────────────────────────────────────────────────────
DRY_RUN = get_runtime_param("DRY_RUN", "true").strip().lower() == "true"

# #664326 — incremental mode: scope revert to a single repair pass.
# ""     → latest run_id present in chunk audit table (safest default)
# "ALL"  → revert every recorded run (earlier one-shot behavior)
# "<id>" → revert that specific run only
_REVERT_RUN_ID_RAW = get_runtime_param("REVERT_RUN_ID", "").strip()

_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]

AUDIT_CHUNK_INSERTS = f"{_std_prefix}.fsr_repair_664196_chunk_inserts"
AUDIT_METADATA_UPDATES = f"{_sot_prefix}.fsr_repair_664196_metadata_updates_v2"

# Resolve REVERT_RUN_ID → SQL predicate fragment used everywhere downstream.
if _REVERT_RUN_ID_RAW.upper() == "ALL":
    REVERT_RUN_ID = "ALL"
    _RUN_PRED = "1=1"
elif _REVERT_RUN_ID_RAW:
    REVERT_RUN_ID = _REVERT_RUN_ID_RAW
    _RUN_PRED = f"run_id = '{REVERT_RUN_ID}'"
else:
    # Default: pick the latest run_id present in the chunk audit table.
    try:
        _latest = spark.sql(f"""
            SELECT run_id
            FROM {AUDIT_CHUNK_INSERTS}
            WHERE run_id IS NOT NULL
            ORDER BY repaired_at DESC
            LIMIT 1
        """).first()
    except Exception:
        _latest = None
    if _latest and _latest["run_id"]:
        REVERT_RUN_ID = _latest["run_id"]
        _RUN_PRED = f"run_id = '{REVERT_RUN_ID}'"
    else:
        # No run_id recorded (audit rows from earlier pre-#664326 repair runs).
        # Fall back to the historical "revert everything" behavior.
        REVERT_RUN_ID = "ALL"
        _RUN_PRED = "1=1"

log.info("=== FSR Multi-ESN REVERT ===")
log.info(f"  Chunk table      : {CHUNK_TABLE}")
log.info(f"  Metadata table   : {METADATA_TABLE}")
log.info(f"  Audit (chunks)   : {AUDIT_CHUNK_INSERTS}")
log.info(f"  Audit (metadata) : {AUDIT_METADATA_UPDATES}")
log.info(f"  REVERT_RUN_ID    : {REVERT_RUN_ID}")
log.info(f"  DRY_RUN          : {DRY_RUN}")

# COMMAND ----------

# ── Step 1: Validate audit tables exist ──────────────────────────────────────
log.info("Step 1: Validating audit tables...")

try:
    inserted_count = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {AUDIT_CHUNK_INSERTS} WHERE {_RUN_PRED}"
    ).first().cnt
except Exception as e:
    log.error(f"Cannot read {AUDIT_CHUNK_INSERTS}: {e}")
    log.error("Repair was never run or audit table was dropped. Nothing to revert.")
    dbutils.notebook.exit("ABORT: chunk audit table not found — nothing to revert")  # noqa: F821

try:
    updated_count = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {AUDIT_METADATA_UPDATES} WHERE {_RUN_PRED}"
    ).first().cnt
except Exception as e:
    log.warning(f"Cannot read {AUDIT_METADATA_UPDATES}: {e}")
    updated_count = 0

log.info(f"  Scope            : {('ALL recorded runs' if REVERT_RUN_ID == 'ALL' else f'run_id={REVERT_RUN_ID}')}")
log.info(f"  Chunk rows to delete  : {inserted_count:,}")
log.info(f"  Metadata rows to restore: {updated_count}")

if inserted_count == 0 and updated_count == 0:
    log.info("Audit tables have no rows for the requested scope — nothing to revert.")
    dbutils.notebook.exit("NOOP: no audit rows in scope — nothing to revert")  # noqa: F821

# COMMAND ----------

# ── Step 2: Preview ──────────────────────────────────────────────────────────
log.info("Step 2: Revert plan...")
log.info("")
log.info("=" * 70)
log.info("  REVERT PLAN")
log.info("=" * 70)
log.info(f"  DELETE FROM {CHUNK_TABLE}")
log.info(f"    WHERE chunk_id IN ({AUDIT_CHUNK_INSERTS})  → {inserted_count:,} rows")
log.info("")
log.info(f"  MERGE INTO {METADATA_TABLE}")
log.info(f"    RESTORE old_esn, old_esn_source FROM {AUDIT_METADATA_UPDATES}  → {updated_count} rows")
log.info("=" * 70)

# Show samples
log.info("\nSample: chunk audit entries (top 10):")
spark.sql(f"""
    SELECT chunk_id, document_id, esn, chunk_index, repaired_at, run_id
    FROM {AUDIT_CHUNK_INSERTS}
    WHERE {_RUN_PRED}
    LIMIT 10
""").show(truncate=False)

if updated_count > 0:
    log.info("\nSample: metadata audit entries (top 10):")
    spark.sql(f"""
        SELECT document_id, old_esn, old_esn_source, new_esn, repaired_at, run_id
        FROM {AUDIT_METADATA_UPDATES}
        WHERE {_RUN_PRED}
        LIMIT 10
    """).show(truncate=False)

if DRY_RUN:
    log.info("\n*** DRY_RUN=true — No changes made. ***")
    log.info("*** Set DRY_RUN=false to execute revert. ***")
    dbutils.notebook.exit(  # noqa: F821
        f"DRY_RUN (scope={REVERT_RUN_ID}): would delete {inserted_count:,} chunks, restore {updated_count} metadata rows"
    )

# COMMAND ----------

# ── Step 3: Pre-revert validation ────────────────────────────────────────────
log.info("Step 3: Validating audit data matches current table state...")

# Check: how many audited chunk_ids actually exist in the chunk table right now?
actual_chunks_to_delete = spark.sql(f"""
    SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE}
    WHERE chunk_id IN (SELECT chunk_id FROM {AUDIT_CHUNK_INSERTS} WHERE {_RUN_PRED})
""").first().cnt
log.info(f"  Audited chunk_ids found in chunk table: {actual_chunks_to_delete:,} / {inserted_count:,}")

if actual_chunks_to_delete == 0 and inserted_count > 0:
    log.warning("  No audited chunk rows found — they may have already been deleted (partial revert).")
    log.warning("  Proceeding with metadata restore only.")

# Check: how many audited metadata rows still have the new_esn value?
if updated_count > 0:
    meta_still_repaired = spark.sql(f"""
        SELECT COUNT(*) AS cnt FROM {METADATA_TABLE} m
        JOIN (SELECT * FROM {AUDIT_METADATA_UPDATES} WHERE {_RUN_PRED}) a
          ON m.document_id = a.document_id
        WHERE m.esn = a.new_esn
    """).first().cnt
    log.info(f"  Metadata rows still showing repaired ESN: {meta_still_repaired:,} / {updated_count:,}")

# COMMAND ----------

# ── Step 4: Restore metadata FIRST (safer order) ────────────────────────────
# Metadata is restored before chunk deletion so that on partial failure:
#   - If metadata restore fails → no changes made, system still consistent
#   - If metadata OK but chunk delete fails → old ESN restored, extra chunks
#     are harmless orphans, audit intact for retry
if updated_count > 0:
    log.info("Step 4: Restoring metadata ESN + equipment values...")

    spark.sql(f"""
        MERGE INTO {METADATA_TABLE} AS tgt
        USING (SELECT * FROM {AUDIT_METADATA_UPDATES} WHERE {_RUN_PRED}) AS src
        ON tgt.document_id = src.document_id
        WHEN MATCHED THEN UPDATE SET
            tgt.esn = src.old_esn,
            tgt.esn_source = src.old_esn_source,
            tgt.equipment_sys_id = src.old_equipment_sys_id,
            tgt.equipment_type = src.old_equipment_type,
            tgt.equipment_class_code = src.old_equipment_class_code
    """)
    log.info(f"RESTORED {updated_count} metadata rows to pre-repair state")
else:
    log.info("Step 4: No metadata to restore — skipped")

# COMMAND ----------

# ── Step 5: Delete inserted chunk rows ───────────────────────────────────────
if actual_chunks_to_delete > 0:
    log.info("Step 5: Deleting repair-inserted chunk rows...")

    spark.sql(f"""
        DELETE FROM {CHUNK_TABLE}
        WHERE chunk_id IN (SELECT chunk_id FROM {AUDIT_CHUNK_INSERTS} WHERE {_RUN_PRED})
    """)
    log.info(f"DELETED {actual_chunks_to_delete:,} chunk rows from {CHUNK_TABLE}")
else:
    log.info("Step 5: No chunk rows to delete (already removed or never inserted)")

# COMMAND ----------

# ── Step 6: Post-revert verification ────────────────────────────────────────
log.info("Step 6: Post-revert verification...")

# Confirm no audited chunk_ids remain
remaining = spark.sql(f"""
    SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE}
    WHERE chunk_id IN (SELECT chunk_id FROM {AUDIT_CHUNK_INSERTS} WHERE {_RUN_PRED})
""").first().cnt

if remaining > 0:
    log.error(f"  UNEXPECTED: {remaining} audited chunk_ids still in chunk table!")
    raise RuntimeError(f"Revert incomplete: {remaining} chunk rows not deleted")
else:
    log.info("  ✓ All audited chunk_ids confirmed removed from chunk table")

# Confirm metadata ESNs restored
if updated_count > 0:
    still_new = spark.sql(f"""
        SELECT COUNT(*) AS cnt FROM {METADATA_TABLE} m
        JOIN (SELECT * FROM {AUDIT_METADATA_UPDATES} WHERE {_RUN_PRED}) a
          ON m.document_id = a.document_id
        WHERE m.esn = a.new_esn AND a.old_esn != a.new_esn
    """).first().cnt
    if still_new > 0:
        log.error(f"  UNEXPECTED: {still_new} metadata rows still have repaired ESN!")
        raise RuntimeError(f"Revert incomplete: {still_new} metadata rows not restored")
    else:
        log.info("  ✓ All metadata ESN values confirmed restored to pre-repair state")

# COMMAND ----------

# ── Step 7: Clean up audit rows for this run ────────────────────────────────
log.info("Step 7: Removing audit rows for this revert scope (audit consumed)...")

spark.sql(f"DELETE FROM {AUDIT_CHUNK_INSERTS}    WHERE {_RUN_PRED}")
spark.sql(f"DELETE FROM {AUDIT_METADATA_UPDATES} WHERE {_RUN_PRED}")
log.info(f"Audit rows removed (scope: {REVERT_RUN_ID}). Re-running revert with the same scope will be a no-op.")

# COMMAND ----------

# ── Final report ─────────────────────────────────────────────────────────────
log.info("")
log.info("=" * 70)
log.info("  REVERT COMPLETE — STATE FULLY RESTORED")
log.info("=" * 70)
log.info(f"  {actual_chunks_to_delete:,} chunk rows DELETED")
log.info(f"  {updated_count} metadata rows RESTORED (esn + equipment fields)")
log.info(f"  Post-revert verification PASSED")
log.info(f"  Audit tables TRUNCATED (safe to re-run repair)")
log.info("")
log.info(f"  NEXT STEPS:")
log.info(f"    1. Trigger VS index sync to remove deleted vectors")
log.info(f"       Endpoint: {VS_ENDPOINT_NAME}")
log.info(f"       Index:    {VS_INDEX_NAME}")
log.info(f"    2. Optionally drop audit tables if no longer needed:")
log.info(f"       DROP TABLE {AUDIT_CHUNK_INSERTS};")
log.info(f"       DROP TABLE {AUDIT_METADATA_UPDATES};")
log.info("")

dbutils.notebook.exit(  # noqa: F821
    f"REVERTED (scope={REVERT_RUN_ID}): {actual_chunks_to_delete:,} chunks deleted, {updated_count} metadata restored. "
    f"Verification passed. Audit rows removed for scope."
)
