# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_er_validate — Post-run validation checks for ER pipeline
#
# Runs after ER ingestion to verify data quality: table not empty,
# no duplicate chunk_ids, embedding dimensions correct, VS queryable.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/er_config

# COMMAND ----------

import json
import logging
from pyspark.sql.functions import col, count, size

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("er.validate")

results = []

def check(name, condition, detail="", blocking=True):
    passed = bool(condition)
    results.append((name, passed, detail, blocking))
    if not passed and not blocking:
        log.warning(f"[WARN] {name}" + (f"  — {detail}" if detail else ""))
    else:
        status = "PASS" if passed else "FAIL"
        log.info(f"[{status}] {name}" + (f"  — {detail}" if detail else ""))

# COMMAND ----------

# ── 1. Table exists and is not empty ────────────────────────────────────────

chunk_df = spark.table(ER_CHUNK_TABLE)
chunk_count = chunk_df.count()
check("1.1 Chunk table not empty", chunk_count > 0, f"{chunk_count} rows")

# COMMAND ----------

# ── 2. No duplicate chunk_ids ──────────────────────────────────────────────

distinct_ids = chunk_df.select("chunk_id").distinct().count()
check("2.1 No duplicate chunk_ids",
      distinct_ids == chunk_count,
      f"distinct={distinct_ids}, total={chunk_count}")

# COMMAND ----------

# ── 3. Required fields populated ───────────────────────────────────────────

for c in ["chunk_id", "er_case_number", "chunk_text"]:
    null_count = chunk_df.filter(col(c).isNull() | (col(c) == "")).count()
    check(f"3.x No nulls in '{c}'", null_count == 0, f"{null_count} nulls")

# COMMAND ----------

# ── 4. Embeddings present and correct dimension ───────────────────────────

no_embed = chunk_df.filter(col("chunk_embedding").isNull()).count()
check("4.1 All rows have embeddings", no_embed == 0,
      f"{no_embed} rows missing embedding")

if no_embed < chunk_count:
    # Check dimension on rows that do have embeddings
    sample = chunk_df.filter(col("chunk_embedding").isNotNull()).select(
        size("chunk_embedding").alias("dim")
    ).distinct().collect()
    dims = {r.dim for r in sample}
    check("4.2 Embedding dimension correct",
          dims == {EMBEDDING_DIMENSION},
          f"found dimensions: {dims}, expected: {EMBEDDING_DIMENSION}")

# COMMAND ----------

# ── 5. Document coverage ───────────────────────────────────────────────────

doc_count = chunk_df.select("er_case_number").distinct().count()
avg_chunks = chunk_count / doc_count if doc_count > 0 else 0
log.info(f"  Documents: {doc_count}, Avg chunks/doc: {avg_chunks:.1f}")

# total_chunks populated
no_total = chunk_df.filter(col("total_chunks").isNull()).count()
check("5.1 total_chunks populated", no_total == 0,
      f"{no_total} rows missing total_chunks")

# serial_number coverage
no_serial = chunk_df.filter(col("serial_number").isNull()).count()
serial_count = chunk_df.select("serial_number").distinct().count()
log.info(f"  Serials: {serial_count}, Rows missing serial: {no_serial}")

# VS filter key columns present as top-level
for tc in ["er_case_number", "serial_number", "opened_at", "status",
           "u_component", "u_field_action_taken", "equipment_id"]:
    if tc in chunk_df.columns:
        log.info(f"  VS column present: {tc} ✓")
    else:
        check(f"5.x VS column '{tc}' exists", False, "missing from table schema")

# COMMAND ----------

# ── 6. VS Index status (non-blocking) ─────────────────────────────────────

if ER_VS_INDEX:
    try:
        ws_url, token = get_dbr_auth()
        status = check_vs_index_status(ws_url, token, ER_VS_INDEX)
        vs_status = status.get("status", "unknown")
        check("6.1 VS index exists", True, f"status: {vs_status}")
    except Exception as e:
        check("6.1 VS index exists", False, f"error: {e}")
else:
    log.info("VS index not configured — skipping VS checks")

# COMMAND ----------

# ── 7. Source-vs-chunk gap analysis (read-only) ────────────────────────────
# Compares ER source records (within scope) to chunks in the chunk table.
# Reports how many source records have NO chunks — i.e. data that was
# extracted but never made it through embed+write (timeout, OOM, etc.).
# This is purely informational — no rows are written or seeded.

_gap_cutoff_clause = f"AND opened_at >= '{ER_CUTOFF_DATE}'" if ER_CUTOFF_DATE else ""

# Exclude source records where all 13 text fields are empty — those produce
# zero chunks by design and must not be counted as gaps.
_has_text_expr = " OR ".join(
    f"(TRIM(COALESCE(CAST({f} AS STRING), '')) <> '')"
    for f in ER_TEXT_FIELDS
)

gap_df = spark.sql(f"""
    WITH src AS (
        SELECT
            CAST(number AS STRING) AS er_case_number,
            MIN(sys_updated_on) AS min_sys_updated_on,
            MAX(sys_updated_on) AS max_sys_updated_on
        FROM {ER_SOURCE_TABLE}
        WHERE sys_updated_on IS NOT NULL
          AND ({_has_text_expr})
          {_gap_cutoff_clause}
        GROUP BY CAST(number AS STRING)
    ),
    chunked AS (
        SELECT DISTINCT er_case_number
        FROM {ER_CHUNK_TABLE}
        WHERE er_case_number IS NOT NULL
    )
    SELECT
        s.er_case_number,
        s.min_sys_updated_on,
        s.max_sys_updated_on
    FROM src s
    LEFT ANTI JOIN chunked c ON s.er_case_number = c.er_case_number
""")

source_total = spark.sql(f"""
    SELECT COUNT(DISTINCT CAST(number AS STRING)) AS cnt
    FROM {ER_SOURCE_TABLE}
    WHERE sys_updated_on IS NOT NULL
      AND ({_has_text_expr})
      {_gap_cutoff_clause}
""").first().cnt

gap_count = gap_df.count()
coverage_pct = ((source_total - gap_count) / source_total * 100) if source_total else 0

check("7.1 Source-to-chunk coverage",
      gap_count == 0,
      f"source records: {source_total}, "
      f"missing chunks: {gap_count}, "
      f"coverage: {coverage_pct:.2f}%",
      blocking=False)

if gap_count > 0:
    # Show date range of missing records to help diagnose which run dropped them
    gap_stats = gap_df.selectExpr(
        "MIN(min_sys_updated_on) AS earliest",
        "MAX(max_sys_updated_on) AS latest",
    ).first()
    log.warning(
        f"  Gap range: {gap_stats.earliest} → {gap_stats.latest}"
    )
    # Show a sample of missing er_case_numbers (up to 20)
    sample_rows = gap_df.select("er_case_number", "max_sys_updated_on") \
                        .orderBy("max_sys_updated_on") \
                        .limit(20).collect()
    log.warning(f"  Sample missing records (oldest first, max 20):")
    for r in sample_rows:
        log.warning(f"    {r.er_case_number}  (sys_updated_on: {r.max_sys_updated_on})")
    log.warning(
        f"  To fix: run with ER_BACKFILL_AUDIT=true, "
        f"then a normal incremental run to process seeded records."
    )

# COMMAND ----------

# ── Summary ─────────────────────────────────────────────────────────────────

passed = sum(1 for _, p, _, _ in results if p)
failed_blocking = sum(1 for _, p, _, b in results if not p and b)
failed_warn = sum(1 for _, p, _, b in results if not p and not b)
total = len(results)

log.info("=" * 60)
log.info(f"ER Validation: {passed}/{total} passed, "
         f"{failed_blocking} failed, {failed_warn} warnings")
log.info("=" * 60)

if failed_blocking > 0 or failed_warn > 0:
    for name, p, detail, blocking in results:
        if not p:
            level = "FAILED" if blocking else "WARN"
            log.error(f"  {level}: {name} — {detail}")

# ── DQ summary metrics ──────────────────────────────────────────────────────
dq_summary = {
    "checks_passed": passed,
    "checks_failed": failed_blocking,
    "checks_warned": failed_warn,
    "checks_total": total,
    "chunk_count": chunk_count,
    "distinct_chunk_ids": distinct_ids,
    "doc_count": doc_count,
    "avg_chunks_per_doc": round(avg_chunks, 2),
}
log.info(f"DQ metrics: {json.dumps(dq_summary)}")

if failed_blocking > 0:
    raise RuntimeError(
        f"ER validation failed: {failed_blocking}/{total} checks failed. "
        f"See logs above for details."
    )

dbutils.notebook.exit(json.dumps(dq_summary))  # noqa: F821
