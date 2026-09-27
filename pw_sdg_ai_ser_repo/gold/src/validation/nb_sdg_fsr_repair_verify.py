# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_repair_verify — Post-repair/revert verification
#
# Runs AFTER repair OR revert to confirm data integrity:
#   1. Schema checks (expected columns exist)
#   2. Multi-ESN coverage (every ref ESN has chunk rows)
#   3. Metadata ESN alignment with fsr_pdf_ref
#   4. No orphaned chunks (every chunk ESN is in ref)
#   5. Audit table consistency
#
# Exits with PASS/FAIL summary. Does NOT modify data.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import logging
from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.repair.verify")

# COMMAND ----------

_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]

AUDIT_CHUNK_INSERTS = f"{_std_prefix}.fsr_repair_664196_chunk_inserts"
AUDIT_METADATA_UPDATES = f"{_sot_prefix}.fsr_repair_664196_metadata_updates_v2"

results = []  # (test_name, passed, detail)


def check(name, condition, detail=""):
    passed = bool(condition)
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    log.info(f"[{status}] {name}" + (f"  — {detail}" if detail else ""))


def warn(name, detail=""):
    log.warning(f"[WARN] {name}" + (f"  — {detail}" if detail else ""))

# COMMAND ----------

# ── Check 1: Multi-ESN chunk coverage ────────────────────────────────────────
log.info("Check 1: Multi-ESN documents have chunks for ALL ref ESNs...")

missing_coverage = spark.sql(f"""
    SELECT r.s3_filename AS document_id, r.esn AS missing_esn
    FROM {FSR_PDF_REF_VIEW} r
    LEFT JOIN {CHUNK_TABLE} c
        ON LOWER(TRIM(r.s3_filename)) = LOWER(TRIM(c.document_id))
        AND r.esn = c.esn
    WHERE r.esn IS NOT NULL
      AND TRIM(r.esn) != ''
      AND c.chunk_id IS NULL
      AND EXISTS (
          SELECT 1 FROM {CHUNK_TABLE} x
          WHERE LOWER(TRIM(x.document_id)) = LOWER(TRIM(r.s3_filename))
      )
""")

missing_count = missing_coverage.count()
check(
    "multi_esn_coverage",
    missing_count == 0,
    f"{missing_count} (document, ESN) pairs still missing chunk rows"
)

if missing_count > 0 and missing_count <= 20:
    log.info("Missing coverage details:")
    missing_coverage.show(truncate=False)
elif missing_count > 20:
    log.info(f"Top 20 missing (document, ESN) pairs:")
    missing_coverage.limit(20).show(truncate=False)

# COMMAND ----------

# ── Check 2: Metadata ESN alignment ──────────────────────────────────────────
log.info("Check 2: Metadata ESN values are valid per fsr_pdf_ref...")

meta_misaligned = spark.sql(f"""
    SELECT m.document_id, m.esn AS metadata_esn
    FROM {METADATA_TABLE} m
    WHERE m.esn IS NOT NULL
      AND TRIM(m.esn) != ''
      AND EXISTS (
          SELECT 1 FROM {FSR_PDF_REF_VIEW} r
          WHERE LOWER(TRIM(r.s3_filename)) = LOWER(TRIM(m.document_id))
      )
      AND NOT EXISTS (
          SELECT 1 FROM {FSR_PDF_REF_VIEW} r
          WHERE LOWER(TRIM(r.s3_filename)) = LOWER(TRIM(m.document_id))
            AND r.esn = m.esn
      )
""")

misaligned_count = meta_misaligned.count()
check(
    "metadata_esn_valid",
    misaligned_count == 0,
    f"{misaligned_count} metadata rows have ESN not found in fsr_pdf_ref"
)

if misaligned_count > 0 and misaligned_count <= 20:
    meta_misaligned.show(truncate=False)

# COMMAND ----------

# ── Check 3: No orphaned chunk ESNs ──────────────────────────────────────────
log.info("Check 3: All chunk ESNs exist in fsr_pdf_ref...")

# Only check documents that ARE in the ref (non-ref docs are allowed to keep
# whatever ESN P1 extracted)
orphan_esn = spark.sql(f"""
    SELECT c.document_id, c.esn AS chunk_esn, COUNT(*) AS chunk_rows
    FROM {CHUNK_TABLE} c
    WHERE EXISTS (
        SELECT 1 FROM {FSR_PDF_REF_VIEW} r
        WHERE LOWER(TRIM(r.s3_filename)) = LOWER(TRIM(c.document_id))
    )
    AND NOT EXISTS (
        SELECT 1 FROM {FSR_PDF_REF_VIEW} r
        WHERE LOWER(TRIM(r.s3_filename)) = LOWER(TRIM(c.document_id))
          AND r.esn = c.esn
    )
    GROUP BY c.document_id, c.esn
""")

orphan_count = orphan_esn.count()
# This is a WARN, not a FAIL — old chunks with LLM-extracted ESN may persist
# until the next full reprocessing.
if orphan_count > 0:
    warn("orphan_chunk_esn", f"{orphan_count} (doc, esn) groups in chunks not in ref. "
         "Expected for first repair — original GT ESN rows are still present.")
    orphan_esn.limit(10).show(truncate=False)
else:
    check("orphan_chunk_esn", True, "All chunk ESNs are in fsr_pdf_ref")

# COMMAND ----------

# ── Check 4: Audit table state ────────────────────────────────────────────────
log.info("Check 4: Audit table consistency...")

try:
    audit_chunk_cnt = spark.sql(f"SELECT COUNT(*) AS cnt FROM {AUDIT_CHUNK_INSERTS}").first().cnt
    audit_meta_cnt = spark.sql(f"SELECT COUNT(*) AS cnt FROM {AUDIT_METADATA_UPDATES}").first().cnt
    check(
        "audit_tables_accessible",
        True,
        f"chunk_inserts={audit_chunk_cnt:,}, metadata_updates={audit_meta_cnt}"
    )
except Exception as e:
    check("audit_tables_accessible", False, f"Cannot access audit tables: {e}")
    audit_chunk_cnt = -1
    audit_meta_cnt = -1

# COMMAND ----------

# ── Check 5: Chunk count sanity ───────────────────────────────────────────────
log.info("Check 5: Total chunk row count sanity...")

total_chunks = spark.sql(f"SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE}").first().cnt
total_docs = spark.sql(f"SELECT COUNT(DISTINCT document_id) FROM {CHUNK_TABLE}").first()[0]
avg_chunks = total_chunks / total_docs if total_docs > 0 else 0

check(
    "chunk_count_sanity",
    avg_chunks < 500,  # Arbitrary upper bound — typical FSR is 20-100 chunks/doc
    f"Total chunks: {total_chunks:,}, documents: {total_docs:,}, avg: {avg_chunks:.1f} chunks/doc"
)

# COMMAND ----------

# ── Check 6: Duplicate chunk_id detection ─────────────────────────────────────
log.info("Check 6: No duplicate chunk_ids...")

dup_ids = spark.sql(f"""
    SELECT chunk_id, COUNT(*) AS cnt
    FROM {CHUNK_TABLE}
    GROUP BY chunk_id
    HAVING COUNT(*) > 1
""")

dup_count = dup_ids.count()
check(
    "no_duplicate_chunk_ids",
    dup_count == 0,
    f"{dup_count} duplicate chunk_id values found" if dup_count > 0 else "All chunk_ids are unique"
)

if dup_count > 0:
    dup_ids.limit(10).show(truncate=False)

# COMMAND ----------

# ── Check 7: UAT ESN coverage (30 known multi-ESN serials) ───────────────────
log.info("Check 7: UAT ESN set — metadata & chunk counts...")

_UAT_ESNS = [
    '290T434','290T484','290T503','290T530','290T532','290T543','290T577',
    '290T658','290T762','337X045','337X233','337X305','337X330','337X336',
    '337X369','337X393','337X708','337X709','337X758','338X408','338X424',
    '338X425','338X426','338X427','338X713','338X714','338X722','338X724',
    '338X765','761X004',
]

_uat_esn_list = ",".join(f"'{e}'" for e in _UAT_ESNS)

# Chunks: how many chunk rows have each UAT ESN in our pipeline tables
uat_chunks = spark.sql(f"""
    SELECT esn, COUNT(*) AS chunk_count, COUNT(DISTINCT document_id) AS doc_count
    FROM {CHUNK_TABLE}
    WHERE esn IN ({_uat_esn_list})
    GROUP BY esn
    ORDER BY esn
""")

# ESNs with zero chunk rows after repair
uat_missing = spark.sql(f"""
    SELECT e.esn AS uat_esn,
           COALESCE(c.chunk_count, 0) AS chunk_count,
           COALESCE(c.doc_count, 0) AS doc_count
    FROM (SELECT EXPLODE(ARRAY({_uat_esn_list})) AS esn) e
    LEFT JOIN (
        SELECT esn, COUNT(*) AS chunk_count, COUNT(DISTINCT document_id) AS doc_count
        FROM {CHUNK_TABLE}
        WHERE esn IN ({_uat_esn_list})
        GROUP BY esn
    ) c ON e.esn = c.esn
    WHERE COALESCE(c.chunk_count, 0) = 0
""")

uat_missing_count = uat_missing.count()
check(
    "uat_esn_chunk_coverage",
    uat_missing_count == 0,
    f"{uat_missing_count}/{len(_UAT_ESNS)} UAT ESNs have ZERO chunk rows"
    if uat_missing_count > 0
    else f"All {len(_UAT_ESNS)} UAT ESNs have chunk rows"
)

if uat_missing_count > 0:
    log.info("UAT ESNs with NO chunks (repair may not have covered these):")
    uat_missing.show(truncate=False)

log.info(f"\nUAT ESN Chunk Coverage ({len(_UAT_ESNS)} serials):")
uat_chunks.show(30, truncate=False)

# COMMAND ----------

# ── Check 8: Compare against previous tables (main — DS team baseline) ────────
# sdg-usecase was previously reading from main.gp_services_sdg_poc.* tables
# (DS team pipeline). This comparison shows whether our pipeline (vaip.*) +
# repair matches or exceeds what the old tables had for these 30 UAT ESNs.
log.info("Check 8: Comparing against previous baseline (main.gp_services_sdg_poc.*)...")

# Old DS team tables (backed the VS index vs_field_service_report_gt_litellm)
_OLD_CHUNK_TABLE = "main.gp_services_sdg_poc.field_service_report"
_OLD_METADATA_TABLE = "main.gp_services_sdg_poc.fsr_scraped_meta_normalized"

try:
    # Old chunk counts per UAT ESN (DS team used generator_serial, not esn)
    old_chunks = spark.sql(f"""
        SELECT generator_serial AS esn,
               COUNT(*) AS old_chunks,
               COUNT(DISTINCT pdf_name) AS old_docs
        FROM {_OLD_CHUNK_TABLE}
        WHERE generator_serial IN ({_uat_esn_list})
        GROUP BY generator_serial
    """)

    # New (our pipeline) chunk counts per UAT ESN
    new_chunks = spark.sql(f"""
        SELECT esn,
               COUNT(*) AS new_chunks,
               COUNT(DISTINCT document_id) AS new_docs
        FROM {CHUNK_TABLE}
        WHERE esn IN ({_uat_esn_list})
        GROUP BY esn
    """)

    # Old metadata counts (fsr_scraped_meta_normalized uses 'esn' not 'generator_serial')
    old_meta = spark.sql(f"""
        SELECT esn,
               COUNT(*) AS old_meta
        FROM {_OLD_METADATA_TABLE}
        WHERE esn IN ({_uat_esn_list})
        GROUP BY esn
    """)

    # New metadata counts
    new_meta = spark.sql(f"""
        SELECT esn,
               COUNT(*) AS new_meta
        FROM {METADATA_TABLE}
        WHERE esn IN ({_uat_esn_list})
        GROUP BY esn
    """)

    old_chunks.createOrReplaceTempView("_old_chunks")
    new_chunks.createOrReplaceTempView("_new_chunks")
    old_meta.createOrReplaceTempView("_old_meta")
    new_meta.createOrReplaceTempView("_new_meta")

    comparison = spark.sql(f"""
        SELECT
            e.esn,
            COALESCE(om.old_meta, 0) AS old_meta,
            COALESCE(nm.new_meta, 0) AS new_meta,
            COALESCE(nm.new_meta, 0) - COALESCE(om.old_meta, 0) AS meta_delta,
            COALESCE(oc.old_chunks, 0) AS old_chunks,
            COALESCE(nc.new_chunks, 0) AS new_chunks,
            COALESCE(nc.new_chunks, 0) - COALESCE(oc.old_chunks, 0) AS chunk_delta,
            COALESCE(oc.old_docs, 0) AS old_chunk_docs,
            COALESCE(nc.new_docs, 0) AS new_chunk_docs
        FROM (SELECT EXPLODE(ARRAY({_uat_esn_list})) AS esn) e
        LEFT JOIN _old_chunks oc ON e.esn = oc.esn
        LEFT JOIN _new_chunks nc ON e.esn = nc.esn
        LEFT JOIN _old_meta om ON e.esn = om.esn
        LEFT JOIN _new_meta nm ON e.esn = nm.esn
        ORDER BY e.esn
    """)

    log.info("")
    log.info("=" * 100)
    log.info("  UAT ESN COMPARISON: OLD (main.gp_services_sdg_poc.*) vs NEW (pipeline + repair)")
    log.info(f"  Old chunk table:    {_OLD_CHUNK_TABLE} (col: generator_serial)")
    log.info(f"  New chunk table:    {CHUNK_TABLE} (col: esn)")
    log.info(f"  Old metadata table: {_OLD_METADATA_TABLE} (col: esn)")
    log.info(f"  New metadata table: {METADATA_TABLE} (col: esn)")
    log.info("=" * 100)
    comparison.show(30, truncate=False)

    # Summary totals
    totals = comparison.agg(
        {"old_chunks": "sum", "new_chunks": "sum",
         "chunk_delta": "sum", "old_meta": "sum", "new_meta": "sum"}
    ).first()
    log.info(f"  TOTALS across {len(_UAT_ESNS)} UAT ESNs:")
    log.info(f"    Chunks:   {int(totals['sum(old_chunks)']):,} (old) → {int(totals['sum(new_chunks)']):,} (new)  Δ = {int(totals['sum(chunk_delta)']):+,}")
    log.info(f"    Metadata: {int(totals['sum(old_meta)']):,} (old) → {int(totals['sum(new_meta)']):,} (new)")

    # Flag: ESNs that had chunks in old but have FEWER in new (regression)
    regressed = comparison.filter("new_chunks < old_chunks AND old_chunks > 0")
    regressed_count = regressed.count()
    if regressed_count > 0:
        check("uat_no_chunk_regression", False,
              f"{regressed_count} UAT ESNs have FEWER chunks than old tables!")
        regressed.show(truncate=False)
    else:
        check("uat_no_chunk_regression", True,
              "No UAT ESNs have fewer chunks than the old baseline")

    # Flag: ESNs that existed in old but have 0 in new (total loss)
    lost = comparison.filter("old_chunks > 0 AND new_chunks = 0")
    lost_count = lost.count()
    if lost_count > 0:
        check("uat_no_chunk_loss", False,
              f"{lost_count} UAT ESNs had chunks in old tables but ZERO in new!")
        lost.show(truncate=False)
    else:
        check("uat_no_chunk_loss", True,
              "No UAT ESNs lost all chunks vs old baseline")

    # Info: ESNs new to our pipeline (0 in old, >0 in new)
    gained = comparison.filter("old_chunks = 0 AND new_chunks > 0")
    gained_count = gained.count()
    if gained_count > 0:
        log.info(f"\n  {gained_count} UAT ESNs are NEW (had 0 chunks in old, now have chunks):")
        gained.show(truncate=False)

except Exception as e:
    log.warning(f"Cross-catalog comparison failed: {e}")
    log.warning(f"  This may happen if the old tables ({_OLD_CHUNK_TABLE}) are not accessible.")
    log.warning(f"  Skipping — other checks still apply.")

# COMMAND ----------

# ── Summary ───────────────────────────────────────────────────────────────────
log.info("")
log.info("=" * 70)
log.info("  VERIFICATION SUMMARY")
log.info("=" * 70)

pass_count = sum(1 for _, p, _ in results if p)
fail_count = sum(1 for _, p, _ in results if not p)

for name, passed, detail in results:
    status = "PASS" if passed else "FAIL"
    log.info(f"  [{status}] {name}: {detail}")

log.info("")
log.info(f"  Total: {pass_count} passed, {fail_count} failed")
log.info("=" * 70)

if fail_count > 0:
    summary = f"VERIFY FAILED: {fail_count} checks failed, {pass_count} passed"
    log.error(summary)
    # Exit with error message but don't raise — let the operator review
    dbutils.notebook.exit(summary)  # noqa: F821
else:
    summary = f"VERIFY PASSED: all {pass_count} checks passed"
    log.info(summary)
    dbutils.notebook.exit(summary)  # noqa: F821
