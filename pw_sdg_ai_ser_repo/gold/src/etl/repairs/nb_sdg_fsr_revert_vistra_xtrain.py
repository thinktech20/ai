# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_revert_vistra_xtrain — Revert Vistra cross-train repair
#
# Reads audit tables written by nb_sdg_fsr_repair_vistra_xtrain and undoes
# all changes for a given REPAIR_RUN_ID (or all recorded runs):
#   - DELETEs chunk rows that were inserted (by chunk_id in audit table)
#   - DELETEs inserted metadata rows (by document_id in audit table)
#   - RESETs the staging row's {JB_ENV}_status back to 'pending'
#     (clears processed_at / run_id / error)
#   - DELETEs the audit rows for that scope (audit consumed)
#
# Audit tables consumed:
#   fsr_repair_vistra_chunk_inserts     (schema: repair_run_id, document_id,
#                                        base_document_id, chunk_id,
#                                        base_chunk_id, esn, chunk_index,
#                                        inserted_at)
#   fsr_repair_vistra_metadata_updates  (schema: repair_run_id, document_id,
#                                        base_document_id, inserted_esn,
#                                        inserted_at)
#
# Run params:
#   DRY_RUN         (default "true")  — preview only, no writes
#   REVERT_RUN_ID   ("" → latest run_id in chunk audit; "ALL" reverts every
#                    recorded run; "<id>" reverts that run only)
#   JB_ENV         required ("dev" or "prod") — drives which {env}_status
#                    column on staging gets reset
#
# Order of operations (safest order on partial failure):
#   1. Validate audit + count work in scope
#   2. DELETE inserted metadata rows (by document_id)
#   3. DELETE inserted chunk rows (by chunk_id)
#   4. RESET staging rows to 'pending'
#   5. Verify nothing remains in the data tables for this scope
#   6. DELETE audit rows for the scope
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../../common/fsr_config

# COMMAND ----------

import logging

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.revert.vistra.xtrain")

# COMMAND ----------

# ── Configuration ───────────────────────────────────────────────────────────
DRY_RUN = get_runtime_param("DRY_RUN", "true").strip().lower() == "true"
JB_ENV = get_runtime_param("jb_env", "").strip().lower()
if JB_ENV not in ("dev", "prod"):
    raise ValueError("JB_ENV must be 'dev' or 'prod' (matches the env the repair was run for).")

STATUS_COL = f"{JB_ENV}_status"
RUN_ID_COL = f"{JB_ENV}_run_id"
PROCESSED_AT_COL = f"{JB_ENV}_processed_at"
ERROR_COL = f"{JB_ENV}_error"

_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]

STAGING_TABLE = get_runtime_param("STAGING_TABLE", f"{_sot_prefix}.staging_vistra_gap")
AUDIT_CHUNK_TABLE = get_runtime_param(
    "AUDIT_CHUNK_TABLE", f"{_std_prefix}.fsr_repair_vistra_chunk_inserts"
)
AUDIT_META_TABLE = get_runtime_param(
    "AUDIT_META_TABLE", f"{_sot_prefix}.fsr_repair_vistra_metadata_updates"
)

_REVERT_RUN_ID_RAW = get_runtime_param("REVERT_RUN_ID", "").strip()


def _sql_quote(v: str) -> str:
    return "'" + str(v).replace("'", "''") + "'"


# Resolve REVERT_RUN_ID → SQL predicate.
if _REVERT_RUN_ID_RAW.upper() == "ALL":
    REVERT_RUN_ID = "ALL"
    _RUN_PRED = "1=1"
elif _REVERT_RUN_ID_RAW:
    REVERT_RUN_ID = _REVERT_RUN_ID_RAW
    _RUN_PRED = f"repair_run_id = {_sql_quote(REVERT_RUN_ID)}"
else:
    try:
        _latest = spark.sql(
            f"""
            SELECT repair_run_id
            FROM (
                SELECT repair_run_id, inserted_at FROM {AUDIT_CHUNK_TABLE}
                UNION ALL
                SELECT repair_run_id, inserted_at FROM {AUDIT_META_TABLE}
            ) a
            WHERE repair_run_id IS NOT NULL
            ORDER BY inserted_at DESC
            LIMIT 1
            """
        ).first()
    except Exception:
        _latest = None
    if _latest and _latest["repair_run_id"]:
        REVERT_RUN_ID = _latest["repair_run_id"]
        _RUN_PRED = f"repair_run_id = {_sql_quote(REVERT_RUN_ID)}"
    else:
        REVERT_RUN_ID = "ALL"
        _RUN_PRED = "1=1"

log.info("=== Vistra Cross-Train REVERT ===")
log.info(f"  STAGING_TABLE     : {STAGING_TABLE}")
log.info(f"  METADATA_TABLE    : {METADATA_TABLE}")
log.info(f"  CHUNK_TABLE       : {CHUNK_TABLE}")
log.info(f"  AUDIT_CHUNK_TABLE : {AUDIT_CHUNK_TABLE}")
log.info(f"  AUDIT_META_TABLE  : {AUDIT_META_TABLE}")
log.info(f"  JB_ENV           : {JB_ENV}  (status col: {STATUS_COL})")
log.info(f"  REVERT_RUN_ID     : {REVERT_RUN_ID}")
log.info(f"  DRY_RUN           : {DRY_RUN}")

# COMMAND ----------

# ── Step 1: Validate audit + count work in scope ────────────────────────────
log.info("Step 1: Validating audit tables...")

try:
    chunk_audit_count = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {AUDIT_CHUNK_TABLE} WHERE {_RUN_PRED}"
    ).first().cnt
except Exception as e:
    log.error(f"Cannot read {AUDIT_CHUNK_TABLE}: {e}")
    dbutils.notebook.exit("ABORT: chunk audit table not found — nothing to revert")  # noqa: F821

try:
    meta_audit_count = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED}"
    ).first().cnt
except Exception as e:
    log.warning(f"Cannot read {AUDIT_META_TABLE}: {e}")
    meta_audit_count = 0

log.info(f"  Scope                       : {('ALL recorded runs' if REVERT_RUN_ID == 'ALL' else f'repair_run_id={REVERT_RUN_ID}')}")
log.info(f"  Audited chunk rows in scope : {chunk_audit_count:,}")
log.info(f"  Audited meta  rows in scope : {meta_audit_count:,}")

if chunk_audit_count == 0 and meta_audit_count == 0:
    dbutils.notebook.exit("NOOP: no audit rows in scope — nothing to revert")  # noqa: F821

# Scope runs from both audit tables. This allows revert to recover even when
# chunk audit is missing but metadata audit exists (historical bug runs).
spark.sql(
    f"""
    CREATE OR REPLACE TEMP VIEW _v_revert_scope_runs AS
    SELECT DISTINCT repair_run_id
    FROM (
        SELECT repair_run_id FROM {AUDIT_CHUNK_TABLE} WHERE {_RUN_PRED}
        UNION
        SELECT repair_run_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED}
    ) s
    WHERE repair_run_id IS NOT NULL
    """
)

# Pre-counts: what actually exists right now that this revert will touch.
chunks_present = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE}
    WHERE chunk_id IN (SELECT chunk_id FROM {AUDIT_CHUNK_TABLE} WHERE {_RUN_PRED})
       OR document_id IN (SELECT document_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED})
    """
).first().cnt

meta_present = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt FROM {METADATA_TABLE}
    WHERE document_id IN (SELECT document_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED})
    """
).first().cnt

staging_to_reset = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt FROM {STAGING_TABLE}
    WHERE {RUN_ID_COL} IN (SELECT repair_run_id FROM _v_revert_scope_runs)
    """
).first().cnt

log.info("")
log.info("=" * 70)
log.info("  REVERT PLAN")
log.info("=" * 70)
log.info(f"  DELETE FROM {CHUNK_TABLE} by chunk_id  : {chunks_present:,} rows present")
log.info(f"  DELETE FROM {METADATA_TABLE} by doc_id : {meta_present:,} rows present")
log.info(f"  RESET staging {STATUS_COL}='pending'   : {staging_to_reset:,} rows present")
log.info("=" * 70)

if chunk_audit_count > 0:
    log.info("\nSample: chunk audit entries (top 10):")
    spark.sql(
        f"""
        SELECT repair_run_id, document_id, base_document_id, chunk_id, esn, chunk_index, inserted_at
        FROM {AUDIT_CHUNK_TABLE}
        WHERE {_RUN_PRED}
        LIMIT 10
        """
    ).show(truncate=False)
else:
    log.info("\nNo chunk audit rows in scope; revert will use metadata-audit document_id fallback for chunk cleanup.")

if meta_audit_count > 0:
    log.info("\nSample: metadata audit entries (top 10):")
    spark.sql(
        f"""
        SELECT repair_run_id, document_id, base_document_id, inserted_esn, inserted_at
        FROM {AUDIT_META_TABLE}
        WHERE {_RUN_PRED}
        LIMIT 10
        """
    ).show(truncate=False)

if DRY_RUN:
    log.info("\n*** DRY_RUN=true — No changes made. ***")
    dbutils.notebook.exit(  # noqa: F821
        f"DRY_RUN (scope={REVERT_RUN_ID}, env={JB_ENV}): would delete "
        f"{chunks_present:,} chunks + {meta_present:,} metadata rows, "
        f"reset {staging_to_reset:,} staging rows"
    )

# COMMAND ----------

# ── Step 2: Delete inserted metadata rows ───────────────────────────────────
if meta_present > 0:
    log.info("Step 2: Deleting inserted metadata rows...")
    spark.sql(
        f"""
        DELETE FROM {METADATA_TABLE}
        WHERE document_id IN (
            SELECT document_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED}
        )
        """
    )
    log.info(f"  Deleted {meta_present:,} metadata rows")
else:
    log.info("Step 2: No inserted metadata rows present — skipped")

# COMMAND ----------

# ── Step 3: Delete inserted chunk rows ──────────────────────────────────────
if chunks_present > 0:
    log.info("Step 3: Deleting inserted chunk rows...")
    spark.sql(
        f"""
        DELETE FROM {CHUNK_TABLE}
        WHERE chunk_id IN (SELECT chunk_id FROM {AUDIT_CHUNK_TABLE} WHERE {_RUN_PRED})
           OR document_id IN (SELECT document_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED})
        """
    )
    log.info(f"  Deleted {chunks_present:,} chunk rows")
else:
    log.info("Step 3: No inserted chunk rows present — skipped")

# COMMAND ----------

# ── Step 4: Reset staging rows to 'pending' ─────────────────────────────────
if staging_to_reset > 0:
    log.info(f"Step 4: Resetting staging rows where {RUN_ID_COL} in scope...")
    spark.sql(
        f"""
        UPDATE {STAGING_TABLE}
        SET {STATUS_COL} = 'pending',
            {PROCESSED_AT_COL} = NULL,
            {RUN_ID_COL} = NULL,
            {ERROR_COL} = NULL
        WHERE {RUN_ID_COL} IN (SELECT repair_run_id FROM _v_revert_scope_runs)
        """
    )
    log.info(f"  Reset {staging_to_reset:,} staging rows to 'pending'")
else:
    log.info("Step 4: No staging rows to reset — skipped")

# COMMAND ----------

# ── Step 5: Post-revert verification ────────────────────────────────────────
log.info("Step 5: Post-revert verification...")

remaining_chunks = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE}
    WHERE chunk_id IN (SELECT chunk_id FROM {AUDIT_CHUNK_TABLE} WHERE {_RUN_PRED})
       OR document_id IN (SELECT document_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED})
    """
).first().cnt
remaining_meta = spark.sql(
    f"""
    SELECT COUNT(*) AS cnt FROM {METADATA_TABLE}
    WHERE document_id IN (SELECT document_id FROM {AUDIT_META_TABLE} WHERE {_RUN_PRED})
    """
).first().cnt

if remaining_chunks > 0 or remaining_meta > 0:
    log.error(
        f"  UNEXPECTED: chunks_left={remaining_chunks}, meta_left={remaining_meta}"
    )
    raise RuntimeError("Revert incomplete — see counts above")
log.info("  ✓ No audited chunk or metadata rows remain in scope")

# COMMAND ----------

# ── Step 6: Remove audit rows for this scope ────────────────────────────────
log.info("Step 6: Removing audit rows for this revert scope (audit consumed)...")
spark.sql(f"DELETE FROM {AUDIT_CHUNK_TABLE} WHERE {_RUN_PRED}")
spark.sql(f"DELETE FROM {AUDIT_META_TABLE}  WHERE {_RUN_PRED}")
log.info(f"  Audit rows removed (scope: {REVERT_RUN_ID}). Re-running revert with same scope = no-op.")

# COMMAND ----------

log.info("")
log.info("=" * 70)
log.info("  REVERT COMPLETE")
log.info("=" * 70)
log.info(f"  Chunks deleted          : {chunks_present:,}")
log.info(f"  Metadata rows deleted   : {meta_present:,}")
log.info(f"  Staging rows reset      : {staging_to_reset:,}")
log.info("")
log.info(f"  NEXT STEPS:")
log.info(f"    1. Trigger VS index sync to remove deleted vectors:")
log.info(f"       Endpoint: {VS_ENDPOINT_NAME}")
log.info(f"       Index:    {VS_INDEX_NAME}")
log.info(f"    2. Re-run the repair (with a new REPAIR_RUN_ID) once cause is fixed.")
log.info("")

dbutils.notebook.exit(  # noqa: F821
    f"REVERTED (scope={REVERT_RUN_ID}, env={JB_ENV}): "
    f"chunks_deleted={chunks_present}, meta_deleted={meta_present}, "
    f"staging_reset={staging_to_reset}"
)
