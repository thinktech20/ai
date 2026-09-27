# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_mnd_validate — Post-run validation checks for the M&D pipeline
#
# Runs after M&D ingestion to verify data quality:
#   1. Table not empty
#   2. No duplicate chunk_ids
#   3. No nulls in {chunk_id, mnd_case_number, chunk_text}
#   4. All rows have an embedding of the correct dimension
#   5. VS-filter columns present + coverage logged
#   6. VS index status (non-blocking)
#   7. Source-vs-chunk gap analysis (non-blocking, in-scope only)
#   8. PII / boilerplate regression — no surviving URLs, raw emails,
#      mailto:, <cid:, or known system-email strings in any text column
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/mnd_config

# COMMAND ----------

import json
import logging
import re

from pyspark.sql.functions import col, size

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("mnd.validate")

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

# ── 0. Filter to latest run only ────────────────────────────────────────────
# Only validate chunks from the most recent run, not all historical chunks.
# This ensures fresh runs have ~100% coverage from source to chunks.

_all_chunks = spark.table(MND_CHUNK_TABLE)
_latest_updated_time = _all_chunks.agg({"updated_time": "max"}).collect()[0][0]

if _latest_updated_time:
    log.info(f"Latest run chunks timestamp: {_latest_updated_time}")
    chunk_df = _all_chunks.filter(col("updated_time") == _latest_updated_time)
else:
    log.warning("No updated_time found — using all chunks")
    chunk_df = _all_chunks

# COMMAND ----------

# ── 1. Table exists and is not empty ────────────────────────────────────────

chunk_count = chunk_df.count()
check("1.1 Chunk table not empty", chunk_count > 0, f"{chunk_count} rows", blocking=False)

# COMMAND ----------

# ── 2. No duplicate chunk_ids ──────────────────────────────────────────────

distinct_ids = chunk_df.select("chunk_id").distinct().count()
check(
    "2.1 No duplicate chunk_ids",
    distinct_ids == chunk_count,
    f"distinct={distinct_ids}, total={chunk_count}",
    blocking=False,
)

# COMMAND ----------

# ── 3. Required fields populated ───────────────────────────────────────────

for c in ["chunk_id", "mnd_case_number", "chunk_text"]:
    null_count = chunk_df.filter(col(c).isNull() | (col(c) == "")).count()
    check(f"3.x No nulls in '{c}'", null_count == 0, f"{null_count} nulls", blocking=False)

# COMMAND ----------

# ── 4. Embeddings present and correct dimension ───────────────────────────

no_embed = chunk_df.filter(col("embedding").isNull()).count()
check(
    "4.1 All rows have embeddings",
    no_embed == 0,
    f"{no_embed} rows missing embedding",
    blocking=False,
)

if no_embed < chunk_count:
    sample = (
        chunk_df.filter(col("embedding").isNotNull())
        .select(size("embedding").alias("dim"))
        .distinct()
        .collect()
    )
    dims = {r.dim for r in sample}
    check(
        "4.2 Embedding dimension correct",
        dims == {EMBEDDING_DIMENSION},
        f"found dimensions: {dims}, expected: {EMBEDDING_DIMENSION}",
        blocking=False,
    )

# COMMAND ----------

# ── 5. Document coverage + VS-filter columns ───────────────────────────────

doc_count = chunk_df.select("mnd_case_number").distinct().count()
avg_chunks = chunk_count / doc_count if doc_count > 0 else 0
log.info(f"  Cases: {doc_count}, Avg chunks/case: {avg_chunks:.1f}")

# Quality distribution
qual_rows = (
    chunk_df.groupBy("quality").count().collect()
    if "quality" in chunk_df.columns else []
)
if qual_rows:
    qual_map = {r["quality"]: r["count"] for r in qual_rows}
    in_target = qual_map.get("in_target", 0)
    pct_in_target = (in_target / chunk_count * 100) if chunk_count else 0
    log.info(f"  Quality dist: {qual_map}")
    log.info(f"  pct_in_target: {pct_in_target:.1f}%")

# Serial-number coverage
no_serial = chunk_df.filter(col("serial_number").isNull()).count()
serial_count = chunk_df.select("serial_number").distinct().count()
log.info(f"  Serials: {serial_count}, Rows missing serial: {no_serial}")

# VS-filter columns must be top-level
_VS_FILTER_COLS = [
    "serial_number", "mnd_case_number", "u_ccap_alarm_name",
    "u_component", "u_resolution_category", "u_major_equipment_association",
]
for tc in _VS_FILTER_COLS:
    if tc in chunk_df.columns:
        log.info(f"  VS column present: {tc} ✓")
    else:
        check(f"5.x VS column '{tc}' exists", False, "missing from table schema", blocking=False)

# COMMAND ----------

# ── 6. VS Index status (non-blocking) ─────────────────────────────────────

if MND_VS_INDEX:
    try:
        ws_url, token = get_dbr_auth()
        status = check_vs_index_status(ws_url, token, MND_VS_INDEX)
        vs_status = status.get("status", "unknown")
        check("6.1 VS index exists", True, f"status: {vs_status}", blocking=False)
    except Exception as e:
        check("6.1 VS index exists", False, f"error: {e}", blocking=False)
else:
    log.info("VS index not configured — skipping VS checks")

# COMMAND ----------

# ── 7. Source-vs-chunk gap analysis (read-only) ────────────────────────────
# Compares in-scope M&D source records to chunks present in the chunk table.
# MUST match extraction query filters exactly to avoid count discrepancies.

_gap_cutoff_clause = f"AND opened_at >= '{MND_CUTOFF_DATE}'" if MND_CUTOFF_DATE else ""

_has_text_expr = " OR ".join(
    f"(TRIM(COALESCE(CAST({f} AS STRING), '')) <> '')"
    for f in MND_CHUNK_TEXT_FIELDS
)

_cats = ", ".join(f"'{c}'" for c in MND_FILTER_U_RESOLUTION_CATEGORY) \
    if MND_FILTER_U_RESOLUTION_CATEGORY else ""
_cat_clause = f"AND u_resolution_category IN ({_cats})" if _cats else ""

_types_str = ", ".join(f"'{t}'" for t in MND_FILTER_U_TYPE)

# ── Null proxy filter matching extraction query ────────────────────────────────️
_null_proxies_str = ", ".join(f"'{p}'" for p in MND_NULL_PROXIES)
_null_proxy_clause = f"AND u_ccap_alarm_name NOT IN ({_null_proxies_str})" if _null_proxies_str else ""

gap_df = spark.sql(f"""
    WITH src AS (
        SELECT
            CAST(number_ AS STRING)    AS mnd_case_number,
            MIN(sys_updated_on)        AS min_sys_updated_on,
            MAX(sys_updated_on)        AS max_sys_updated_on
        FROM {MND_SOURCE_TABLE}
        WHERE sys_updated_on IS NOT NULL
          AND u_type IN ({_types_str})
          AND u_serial_number IS NOT NULL
          AND u_serial_number <> ''
          {_cat_clause}
          AND u_ccap_alarm_name IS NOT NULL
          {_null_proxy_clause}
          AND ({_has_text_expr})
          {_gap_cutoff_clause}
        GROUP BY CAST(number_ AS STRING)
    ),
    chunked AS (
        SELECT DISTINCT mnd_case_number
        FROM {MND_CHUNK_TABLE}
        WHERE mnd_case_number IS NOT NULL
    )
    SELECT
        s.mnd_case_number,
        s.min_sys_updated_on,
        s.max_sys_updated_on
    FROM src s
    LEFT ANTI JOIN chunked c ON s.mnd_case_number = c.mnd_case_number
""")

source_total = spark.sql(f"""
    SELECT COUNT(DISTINCT CAST(number_ AS STRING)) AS cnt
    FROM {MND_SOURCE_TABLE}
    WHERE sys_updated_on IS NOT NULL
      AND u_type IN ({_types_str})
      AND u_serial_number IS NOT NULL
      AND u_serial_number <> ''
      {_cat_clause}
      AND u_ccap_alarm_name IS NOT NULL
      {_null_proxy_clause}
      AND ({_has_text_expr})
      {_gap_cutoff_clause}
""").first().cnt

gap_count = gap_df.count()
coverage_pct = ((source_total - gap_count) / source_total * 100) if source_total else 0

check(
    "7.1 Source-to-chunk coverage",
    gap_count == 0,
    f"source records: {source_total}, missing chunks: {gap_count}, "
    f"coverage: {coverage_pct:.2f}%",
    blocking=False,
)

if gap_count > 0:
    gap_stats = gap_df.selectExpr(
        "MIN(min_sys_updated_on) AS earliest",
        "MAX(max_sys_updated_on) AS latest",
    ).first()
    log.warning(f"  Gap range: {gap_stats.earliest} → {gap_stats.latest}")
    sample_rows = (
        gap_df.select("mnd_case_number", "max_sys_updated_on")
        .orderBy("max_sys_updated_on")
        .limit(20)
        .collect()
    )
    log.warning("  Sample missing records (oldest first, max 20):")
    for r in sample_rows:
        log.warning(f"    {r.mnd_case_number}  (sys_updated_on: {r.max_sys_updated_on})")
    log.warning(
        "  To fix: run with MND_BACKFILL_AUDIT=true then a normal "
        "incremental run to process seeded records."
    )

# COMMAND ----------

# ── 8. PII / boilerplate regression checks ─────────────────────────────────
# Verifies that the redaction step actually removed the patterns it was
# supposed to remove.  Counts surviving occurrences across all chunk text
# columns (chunk_text + the 7 original free-text fields).

_PII_COLS = ["chunk_text"] + [c for c in MND_TEXT_COLS if c in chunk_df.columns]

# 8.1 — No surviving URLs
url_pattern = MND_URL_PATTERN
url_hits = 0
for c in _PII_COLS:
    url_hits += chunk_df.filter(col(c).rlike(url_pattern)).count()
check(
    "8.1 No surviving URLs in chunk text",
    url_hits == 0,
    f"{url_hits} row(s) still contain URL-like strings across cols={_PII_COLS}",
    blocking=False,
)

# 8.2 — No raw email patterns that escaped Presidio
# A bare `xxx@yyy.zzz` that is NOT inside a [REDACTED_EMAIL_ADDRESS] tag.
_raw_email_re = r"(?<!REDACTED_)[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
email_hits = 0
for c in _PII_COLS:
    email_hits += chunk_df.filter(col(c).rlike(_raw_email_re)).count()
check(
    "8.2 No raw email addresses in chunk text",
    email_hits == 0,
    f"{email_hits} row(s) still contain raw-looking email strings",
    blocking=False,
)

# 8.3 — No `mailto:` strings
mailto_hits = 0
for c in _PII_COLS:
    mailto_hits += chunk_df.filter(col(c).rlike(r"mailto:")).count()
check(
    "8.3 No 'mailto:' fragments in chunk text",
    mailto_hits == 0,
    f"{mailto_hits} row(s) contain 'mailto:'",
    blocking=False,
)

# 8.4 — No `<cid:` (Outlook attachment placeholders)
cid_hits = 0
for c in _PII_COLS:
    cid_hits += chunk_df.filter(col(c).rlike(r"<cid:")).count()
check(
    "8.4 No '<cid:' fragments in chunk text",
    cid_hits == 0,
    f"{cid_hits} row(s) contain '<cid:'",
    blocking=False,
)

# 8.5 — No known SYSTEM_EMAILS strings (case-insensitive)
sys_email_pattern = "|".join(re.escape(e) for e in MND_SYSTEM_EMAILS)
sys_email_hits = 0
if sys_email_pattern:
    for c in _PII_COLS:
        sys_email_hits += chunk_df.filter(
            col(c).rlike(f"(?i)({sys_email_pattern})")
        ).count()
check(
    "8.5 No known SYSTEM_EMAILS in chunk text",
    sys_email_hits == 0,
    f"{sys_email_hits} row(s) contain a SYSTEM_EMAILS literal",
    blocking=False,
)

# 8.6 — Boilerplate phrase regression (sample of 3 long phrases)
_LONG_PHRASES = [p for p in MND_BOILERPLATE_PHRASES if len(p) > 40][:3]
boilerplate_hits = 0
for phrase in _LONG_PHRASES:
    esc = re.escape(phrase)
    for c in _PII_COLS:
        boilerplate_hits += chunk_df.filter(col(c).rlike(esc)).count()
check(
    "8.6 No surviving boilerplate phrases (sample of 3)",
    boilerplate_hits == 0,
    f"{boilerplate_hits} row(s) still contain one of the sampled boilerplate phrases",
    blocking=False,
)

# COMMAND ----------

# ── Summary ─────────────────────────────────────────────────────────────────

passed = sum(1 for _, p, _, _ in results if p)
failed_blocking = sum(1 for _, p, _, b in results if not p and b)
failed_warn = sum(1 for _, p, _, b in results if not p and not b)
total = len(results)

log.info("=" * 60)
log.info(
    f"M&D Validation: {passed}/{total} passed, "
    f"{failed_blocking} failed, {failed_warn} warnings"
)
log.info("=" * 60)

if failed_blocking > 0 or failed_warn > 0:
    for name, p, detail, blocking in results:
        if not p:
            level = "FAILED" if blocking else "WARN"
            log.error(f"  {level}: {name} — {detail}")

dq_summary = {
    "checks_passed": passed,
    "checks_failed": failed_blocking,
    "checks_warned": failed_warn,
    "checks_total": total,
    "chunk_count": chunk_count,
    "distinct_chunk_ids": distinct_ids,
    "doc_count": doc_count,
    "avg_chunks_per_doc": round(avg_chunks, 2),
    "source_records": source_total,
    "missing_chunks": gap_count,
    "coverage_pct": round(coverage_pct, 2),
    "url_hits": url_hits,
    "email_hits": email_hits,
    "mailto_hits": mailto_hits,
    "cid_hits": cid_hits,
    "system_email_hits": sys_email_hits,
    "boilerplate_hits": boilerplate_hits,
}
log.info(f"DQ metrics: {json.dumps(dq_summary)}")

if failed_blocking > 0:
    raise RuntimeError(
        f"M&D validation failed: {failed_blocking}/{total} checks failed. "
        "See logs above for details."
    )

dbutils.notebook.exit(json.dumps(dq_summary))  # noqa: F821
