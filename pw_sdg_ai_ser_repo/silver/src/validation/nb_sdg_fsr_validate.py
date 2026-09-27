# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_validate — Post-run validation checks
#
# Runs after Process 1 + Process 2 to verify data quality, schema
# compliance, and cross-process consistency.
#
# document_id is PK. Statuses: pending / completed / failed.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import logging
import hashlib
from datetime import datetime, timezone
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, avg, length, size, when, lower, lit, get_json_object,
    min as spark_min, max as spark_max,
)

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.validate")

import uuid as _uuid
VALIDATE_RUN_ID = _uuid.uuid4().hex[:12]

results = []  # (test_name, passed, detail)
warnings = []  # (test_name, detail) — logged but don't fail the run
dq_findings = []  # (document_id, pdf_name, check_name, severity, failure_category, detail)

def check(name, condition, detail=""):
    passed = bool(condition)
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    log.info(f"[{status}] {name}" + (f"  — {detail}" if detail else ""))

def warn(name, condition, detail=""):
    """Log a warning if condition is False — does not fail the run."""
    passed = bool(condition)
    if not passed:
        warnings.append((name, detail))
        log.warning(f"[WARN] {name}" + (f"  — {detail}" if detail else ""))
    else:
        log.info(f"[PASS] {name}" + (f"  — {detail}" if detail else ""))

def log_dq(document_id, pdf_name, check_name, severity, detail, failure_category=None):
    """Record a per-document data quality finding.

    failure_category is a routing hint populated only for terminal failures
    (check 5.7). Left NULL for WARN-level data-quality findings. The set of
    values is open and expected to grow as new failure patterns are seen.
    """
    dq_findings.append((document_id, pdf_name, check_name, severity, failure_category, detail))

log.info(f"Validating:")
log.info(f"  Metadata: {METADATA_TABLE}")
log.info(f"  Chunks:   {CHUNK_TABLE}")
log.info(f"  DQ log:   {DQ_LOG_TABLE}")
log.info(f"  Run ID:   {VALIDATE_RUN_ID}")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS 1 — Metadata Registry Validation
# ═══════════════════════════════════════════════════════════════════════════════
log.info("=== Process 1 — Metadata Registry ===")

meta_df = spark.table(METADATA_TABLE)
meta_count = meta_df.count()

# 1.1  Table is not empty
check("1.1 Metadata table not empty", meta_count > 0, f"{meta_count} rows")

# 1.2  No duplicate document_ids
distinct_ids = meta_df.select("document_id").distinct().count()
check("1.2 No duplicate document_ids", distinct_ids == meta_count,
      f"distinct={distinct_ids}, total={meta_count}")

# 1.3  All required fields populated
required_cols = ["document_id", "volume_path", "metadata_status", "chunk_status"]
for c in required_cols:
    null_count = meta_df.filter(col(c).isNull() | (col(c) == "")).count()
    check(f"1.3 No nulls in '{c}'", null_count == 0, f"{null_count} nulls")

# 1.4  metadata_status values are valid
valid_meta_statuses = {MetadataStatus.PENDING, MetadataStatus.COMPLETED, MetadataStatus.FAILED}
actual_statuses = set(row.metadata_status for row in meta_df.select("metadata_status").distinct().collect())
bad_statuses = actual_statuses - valid_meta_statuses
check("1.4 Valid metadata_status values", len(bad_statuses) == 0,
      f"found: {actual_statuses}" + (f", invalid: {bad_statuses}" if bad_statuses else ""))

# 1.5  chunk_status values are valid
valid_chunk_statuses = {ChunkStatus.PENDING, ChunkStatus.IN_PROGRESS, ChunkStatus.COMPLETED, ChunkStatus.FAILED}
actual_cs = set(row.chunk_status for row in meta_df.select("chunk_status").distinct().collect())
bad_cs = actual_cs - valid_chunk_statuses
check("1.5 Valid chunk_status values", len(bad_cs) == 0,
      f"found: {actual_cs}" + (f", invalid: {bad_cs}" if bad_cs else ""))

# 1.6  All 'completed' docs have page_count > 0
completed_df = meta_df.filter(col("metadata_status") == MetadataStatus.COMPLETED)
completed_count = completed_df.count()
no_pages = completed_df.filter((col("page_count").isNull()) | (col("page_count") <= 0)).count()
check("1.6 All 'completed' docs have page_count > 0", no_pages == 0,
      f"{completed_count} completed docs, {no_pages} missing page_count")

# 1.7  All 'completed' docs have a title
no_title_df = completed_df.filter(col("title").isNull() | (col("title") == ""))
no_title = no_title_df.count()
check("1.7 All 'completed' docs have title", no_title == 0,
      f"{no_title} missing title")
for r in no_title_df.select("document_id", "pdf_name").collect():
    log_dq(r.document_id, r.pdf_name, "1.7 Missing title", "WARN", "title is null or empty")

# 1.8  Date format check (YYYY-MM-DD)
date_cols = ["report_issued_date", "outage_start_date", "outage_end_date"]
for dc in date_cols:
    bad_date_df = completed_df.filter(
        col(dc).isNotNull() & (col(dc) != "") &
        ~col(dc).rlike(r"^\d{4}-\d{2}-\d{2}$")
    )
    bad_dates = bad_date_df.count()
    check(f"1.8 Date format '{dc}'", bad_dates == 0,
          f"{bad_dates} non-YYYY-MM-DD values")
    for r in bad_date_df.select("document_id", "pdf_name", col(dc).alias("bad_value")).collect():
        log_dq(r.document_id, r.pdf_name, f"1.8 Bad date format '{dc}'",
               "WARN", f"value='{r.bad_value}'")

# 1.9  No 'failed' docs without error message
failed_no_err = meta_df.filter(
    (col("metadata_status") == MetadataStatus.FAILED) &
    (col("metadata_error").isNull() | (col("metadata_error") == ""))
).count()
check("1.9 Failed docs have error messages", failed_no_err == 0,
      f"{failed_no_err} failed without error")

# 1.10  Completed docs have scraped_at
no_scraped = completed_df.filter(col("scraped_at").isNull()).count()
check("1.10 Completed docs have scraped_at", no_scraped == 0,
      f"{no_scraped} missing scraped_at")

# 1.11  document_summary coverage on completed metadata rows.
# Soft-WARN only — failures are routed to fsr_data_quality_log by the
# backfill runner (check_name='doc_summary_extraction'), and to the
# pipeline log by P1 incremental for newly discovered docs.
if "document_summary" in meta_df.columns:
    completed_summary_total = completed_df.count()
    if completed_summary_total > 0:
        missing_summary = completed_df.filter(
            col("document_summary").isNull() | (col("document_summary") == "")
        ).count()
        missing_pct = (missing_summary / completed_summary_total) * 100
        warn(
            "1.11 document_summary coverage on completed docs",
            missing_pct < 30,
            f"{missing_summary}/{completed_summary_total} ({missing_pct:.1f}%) "
            f"completed docs have no document_summary; see fsr_data_quality_log "
            f"check_name='doc_summary_extraction' for failure breakdown",
        )

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS 2 — Chunk Table Validation
# ═══════════════════════════════════════════════════════════════════════════════
log.info("=== Process 2 — Chunk Table ===")

chunk_df = spark.table(CHUNK_TABLE)
chunk_count = chunk_df.count()

# 2.1  Chunk table is not empty
check("2.1 Chunk table not empty", chunk_count > 0, f"{chunk_count} rows")

# 2.2  No duplicate chunk_ids
distinct_chunks = chunk_df.select("chunk_id").distinct().count()
check("2.2 No duplicate chunk_ids", distinct_chunks == chunk_count,
      f"distinct={distinct_chunks}, total={chunk_count}")

# 2.3  document_id is not null/empty (NOT NULL FK to metadata)
null_doc_ids = chunk_df.filter(col("document_id").isNull() | (col("document_id") == "")).count()
check("2.3 No null document_id in chunks", null_doc_ids == 0, f"{null_doc_ids} nulls")

# 2.4  chunk_text is not empty
empty_text = chunk_df.filter(col("chunk_text").isNull() | (col("chunk_text") == "")).count()
check("2.4 No empty chunk_text", empty_text == 0, f"{empty_text} empty")

# 2.5  Embedding dimension is correct
null_embeddings = chunk_df.filter(col("chunk_embedding").isNull()).count()
check("2.5a No null chunk_embeddings", null_embeddings == 0, f"{null_embeddings} nulls")

bad_dim = chunk_df.filter(
    col("chunk_embedding").isNotNull() & (size(col("chunk_embedding")) != EMBEDDING_DIMENSION)
).count()
check(f"2.5b Embedding dim = {EMBEDDING_DIMENSION}", bad_dim == 0,
      f"{bad_dim} wrong dimension")

# 2.6  page_number is positive where present
bad_pages = chunk_df.filter(col("page_number").isNotNull() & (col("page_number") <= 0)).count()
check("2.6 page_number > 0 where present", bad_pages == 0, f"{bad_pages} violations")

# 2.7  Chunk text size within expected bounds
max_expected = CHUNKING_CONFIG.chunk_size + 200
oversized = chunk_df.filter(length(col("chunk_text")) > max_expected).count()
check(f"2.7 Chunk text length <= {max_expected}", oversized == 0,
      f"{oversized} oversized chunks")

# 2.8  metadata JSON is valid (not null/empty for chunks)
null_metadata = chunk_df.filter(col("metadata").isNull() | (col("metadata") == "")).count()
check("2.8 No null metadata JSON", null_metadata == 0, f"{null_metadata} nulls")

# 2.9  created_at is populated
null_created = chunk_df.filter(col("created_at").isNull()).count()
check("2.9 created_at populated", null_created == 0, f"{null_created} nulls")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-PROCESS — Metadata ↔ Chunk Consistency
# ═══════════════════════════════════════════════════════════════════════════════
log.info("=== Cross-Process — Metadata ↔ Chunks ===")

# 3.1  Every 'completed' chunk_status doc has chunks
completed_docs = set(
    row.document_id for row in
    meta_df.filter(col("chunk_status") == ChunkStatus.COMPLETED).select("document_id").collect()
)
chunked_docs = set(
    row.document_id for row in
    chunk_df.select("document_id").distinct().collect()
)
completed_no_chunks = completed_docs - chunked_docs
check("3.1 All 'completed' docs have chunks", len(completed_no_chunks) == 0,
      f"{len(completed_no_chunks)} completed docs missing chunks")

# 3.2  No orphan chunks (chunk document_id not in metadata document_id)
meta_doc_ids = set(
    row.document_id for row in meta_df.select("document_id").collect()
)
orphan_chunks = chunked_docs - meta_doc_ids
check("3.2 No orphan chunks", len(orphan_chunks) == 0,
      f"{len(orphan_chunks)} orphan document_ids in chunk table")

# 3.3  Chunk esn matches metadata esn (top-level column check)
join_df = chunk_df.alias("c").join(
    meta_df.alias("m"), col("c.document_id") == col("m.document_id")
).select(
    col("c.document_id"),
    (col("c.esn") != col("m.esn")).alias("esn_mismatch"),
)
esn_mismatches = join_df.filter(col("esn_mismatch") == True).select("document_id").distinct().count()
check("3.3 Chunk esn matches metadata esn", esn_mismatches == 0,
      f"{esn_mismatches} docs with esn mismatch")

# 3.4  No stale pending chunks for completed metadata
# Warn-only — P2 may legitimately lag behind P1 during large runs
stale = meta_df.filter(
    (col("metadata_status") == MetadataStatus.COMPLETED) &
    (col("chunk_status") == ChunkStatus.PENDING)
).count()
warn("3.4 No stale pending chunks for completed metadata", stale == 0,
     f"{stale} docs still pending after both processes ran")

# 3.5  pdf_name derivation coverage
completed_meta = meta_df.filter(col("metadata_status") == MetadataStatus.COMPLETED)
completed_total = completed_meta.count()
no_pdf_name_df = completed_meta.filter(col("pdf_name").isNull() | (col("pdf_name") == ""))
no_pdf_name = no_pdf_name_df.count()
check("3.5 Completed docs have pdf_name derived", no_pdf_name == 0,
      f"{no_pdf_name}/{completed_total} completed docs missing pdf_name")
for r in no_pdf_name_df.select("document_id").collect():
    log_dq(r.document_id, None, "3.5 Missing pdf_name", "WARN",
           "pdf_name is null — doc not found in fsr_pdf_ref")

# 3.6  document_id is lowercase normalized (no .pdf suffix)
bad_doc_ids = meta_df.filter(
    col("document_id").rlike(r"\.(pdf|PDF)$") | (col("document_id") != lower(col("document_id")))
).count()
check("3.6 document_id normalized (lowercase, no .pdf)", bad_doc_ids == 0,
      f"{bad_doc_ids} non-normalized document_ids")

# 3.7  Chunked docs have chunked_at timestamp
chunked_no_ts = meta_df.filter(
    (col("chunk_status") == ChunkStatus.COMPLETED) & col("chunked_at").isNull()
).count()
check("3.7 Completed chunks have chunked_at", chunked_no_ts == 0,
      f"{chunked_no_ts} missing chunked_at")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMA ALIGNMENT — Enrichment Quality
# ═══════════════════════════════════════════════════════════════════════════════
log.info("=== Schema Alignment — Enrichment & Metadata JSON ===")

# 4.1  Enrichment coverage — count populated enrichment fields per completed doc
enrichment_fields = ["esn", "equipment_type", "event_type", "report_issued_date", "outage_type"]
completed_meta = meta_df.filter(col("metadata_status") == MetadataStatus.COMPLETED)
completed_total_4 = completed_meta.count()

if completed_total_4 > 0:
    enrichment_expr = sum(
        when(col(f).isNotNull() & (col(f) != lit("")), lit(1)).otherwise(lit(0))
        for f in enrichment_fields
    ).alias("enrichment_score")
    score_df = completed_meta.select("document_id", "pdf_name", enrichment_expr)
    scores = score_df.collect()
    avg_score = sum(r.enrichment_score for r in scores) / len(scores)
    min_score = min(r.enrichment_score for r in scores)
    warn("4.1 Enrichment score >= 3/5 for all completed docs", min_score >= 3,
          f"min={min_score}, avg={avg_score:.1f} across {completed_total_4} docs (fields: {enrichment_fields})")
    # Log per-doc findings for low-enrichment docs
    for r in scores:
        if r.enrichment_score < 3:
            log_dq(r.document_id, r.pdf_name, "4.1 Low enrichment score",
                   "WARN", f"score={r.enrichment_score}/5 (fields: {enrichment_fields})")
else:
    warn("4.1 Enrichment score >= 3/5 for all completed docs", False, "no completed docs")

# 4.2  Metadata JSON has expected keys (sample first chunk)
expected_json_keys = [
    "pdf_name", "page_number", "title", "esn",
    "equipment_sys_id", "equipment_type", "equipment_class_code",
    "event_type", "ev_project_id", "ev_equipment_event_id",
    "ofs_event_id", "fsp_project_id", "xxx_project_id",
    "fsr_number", "report_issued_date", "outage_start_date", "outage_end_date",
    "outage_type", "technology_type",
]

if chunk_count > 0:
    sample_row = chunk_df.filter(col("metadata").isNotNull()).limit(1)
    missing_keys = []
    for k in expected_json_keys:
        val = sample_row.select(get_json_object(col("metadata"), f"$.{k}")).first()
        if val is None or val[0] is None:
            # Key might exist but be null-valued — check if key is present at all
            # get_json_object returns None for missing keys AND null values,
            # so we just check the key exists in the raw string
            raw = sample_row.select("metadata").first()[0]
            if f'"{k}"' not in raw:
                missing_keys.append(k)
    check("4.2 Chunk metadata JSON has all expected keys", len(missing_keys) == 0,
          f"missing: {missing_keys}" if missing_keys else f"all {len(expected_json_keys)} keys present")
else:
    check("4.2 Chunk metadata JSON has all expected keys", False, "no chunks")

# 4.3  report_date populated on chunks where report_issued_date exists in metadata
if chunk_count > 0:
    has_report_date_in_meta = chunk_df.filter(
        get_json_object(col("metadata"), "$.report_issued_date").isNotNull()
        & (get_json_object(col("metadata"), "$.report_issued_date") != lit(""))
        & (get_json_object(col("metadata"), "$.report_issued_date") != lit("None"))
    ).count()
    has_report_date_col = chunk_df.filter(col("report_date").isNotNull()).count()
    check("4.3 report_date populated where report_issued_date exists",
          has_report_date_in_meta == 0 or has_report_date_col > 0,
          f"report_date col={has_report_date_col}, metadata has report_issued_date={has_report_date_in_meta}")
else:
    check("4.3 report_date populated where report_issued_date exists", False, "no chunks")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# BACKFILL SAFETY — Parallel Run & Claim Integrity
# ═══════════════════════════════════════════════════════════════════════════════
log.info("=== Backfill Safety — Parallel Run & Claim Integrity ===")

# 5.1  No duplicate chunk rows (same chunk_id appearing more than once)
chunk_id_counts = chunk_df.groupBy("chunk_id").count().filter(col("count") > 1)
dup_chunk_count = chunk_id_counts.count()
check("5.1 No duplicate chunk rows", dup_chunk_count == 0,
      f"{dup_chunk_count} chunk_ids with duplicate rows")

# 5.2  No stale in_progress claims (docs stuck in in_progress after run completes)
# Warn-only — P2 job may still be running when validation executes
in_progress_count = meta_df.filter(col("chunk_status") == ChunkStatus.IN_PROGRESS).count()
warn("5.2 No stale in_progress claims", in_progress_count == 0,
     f"{in_progress_count} docs still in_progress (may indicate crashed run)")

# 5.3  Every completed doc has at least 1 chunk (no empty completions from race condition)
if completed_docs and chunked_docs:
    completed_with_chunks = completed_docs & chunked_docs
    for doc_id in completed_with_chunks:
        pass  # 3.1 already checks this; skip iteration
    # Check chunk count per completed doc — flag any with suspiciously few chunks
    chunk_per_doc = chunk_df.groupBy("document_id").count()
    zero_chunk_completed = len(completed_docs - chunked_docs)
    check("5.3 No completed docs with zero chunks", zero_chunk_completed == 0,
          f"{zero_chunk_completed} completed docs have no chunk rows")

# 5.4  No duplicate document_id + page_number combinations (parallel run wrote same chunk)
if chunk_count > 0:
    from pyspark.sql.functions import concat_ws
    dup_combos = chunk_df.groupBy("document_id", "page_number").count().filter(col("count") > 50)
    suspicious_combos = dup_combos.count()
    check("5.4 No suspicious chunk duplication per doc+page", suspicious_combos == 0,
          f"{suspicious_combos} doc+page combos with >50 chunks (possible duplicate processing)")

# 5.5  Chunk count aligns with page count (sanity ratio check)
if completed_docs and chunk_count > 0:
    ratio_df = chunk_df.groupBy("document_id").count().alias("c").join(
        meta_df.select("document_id", "pdf_name", "page_count").alias("m"),
        col("c.document_id") == col("m.document_id")
    ).withColumn("ratio", col("count") / col("page_count"))
    extreme_rows = ratio_df.filter(
        (col("ratio") > 20) | (col("ratio") < 0.1)
    ).collect()
    warn("5.5 Chunk-to-page ratio is reasonable", len(extreme_rows) == 0,
          f"{len(extreme_rows)} docs with extreme chunk/page ratio (>20x or <0.1x)")
    for r in extreme_rows:
        log_dq(r.document_id, r.pdf_name, "5.5 Extreme chunk/page ratio",
               "WARN", f"chunks={r['count']}, pages={r.page_count}, ratio={r.ratio:.1f}")

# 5.6  Failed docs have chunk_error populated
failed_chunks_no_err = meta_df.filter(
    (col("chunk_status") == ChunkStatus.FAILED) &
    (col("chunk_error").isNull() | (col("chunk_error") == ""))
).count()
check("5.6 Failed chunk docs have chunk_error", failed_chunks_no_err == 0,
      f"{failed_chunks_no_err} failed without chunk_error message")

# 5.7  Log failed docs to DQ table for visibility
#
#   SRE-readiness behaviors layered on top of the original check:
#   (1) De-dup — skip docs whose (document_id, check_name) was already logged
#       in the last DQ_FAIL_DEDUP_DAYS days. Stops the daily re-log of the
#       standing terminal-failure population.
#   (2) Failure-category hint — map the raw error string to a short label so
#       SRE can route to the right owner without grepping `detail`. Current
#       set is open and expected to grow as new patterns are seen.
#   (3) pdf_name backfill — metadata-fail rows have pdf_name=NULL because
#       failure happens before fsr_pdf_ref lookup. Resolve from pdf_ref where
#       available, fall back to volume_path basename.
#
DQ_FAIL_DEDUP_DAYS = 2
FAIL_CHECK_NAMES = ("Failed metadata extraction", "Failed chunk ingestion")

# (1) Pre-load already-logged terminal docs (keyed by document_id + check_name)
already_logged_terminal = set()
try:
    rows = spark.sql(f"""
        SELECT DISTINCT document_id, check_name
        FROM {DQ_LOG_TABLE}
        WHERE check_name IN ('Failed metadata extraction', 'Failed chunk ingestion')
          AND created_at >= current_timestamp() - INTERVAL {DQ_FAIL_DEDUP_DAYS} DAYS
          AND document_id IS NOT NULL
    """).collect()
    already_logged_terminal = {(r.document_id, r.check_name) for r in rows}
    log.info(f"5.7 de-dup: {len(already_logged_terminal)} (doc, check) pairs already logged in last {DQ_FAIL_DEDUP_DAYS} days — will skip")
except Exception as e:
    log.warning(f"5.7 de-dup lookup skipped (DQ table unreadable, likely first run): {e}")

# (3) Pre-load pdf_name resolver from fsr_pdf_ref
pdf_name_lookup = {}
try:
    rows = spark.sql(f"""
        SELECT LOWER(s3_filename) AS doc_id, PDF_name AS name
        FROM {FSR_PDF_REF_VIEW}
    """).collect()
    pdf_name_lookup = {r.doc_id: r.name for r in rows if r.doc_id and r.name}
    log.info(f"5.7 pdf_name lookup: loaded {len(pdf_name_lookup)} entries from {FSR_PDF_REF_VIEW}")
except Exception as e:
    log.warning(f"5.7 pdf_name lookup skipped (fsr_pdf_ref unreachable): {e}")

# (2) Failure-category hint — only the `unknown` bucket should page on-call.
#     The set below is what we've seen in prod so far; expected to grow as
#     SRE/ops triage new patterns and add new branches here.
def _classify_failure(detail: str) -> str:
    if not detail:
        return "unknown"
    d = detail.lower()
    if "no /root" in d or "unexpected eof" in d:
        return "corrupt_source"
    if "no matching row" in d or "no text" in d:
        return "image_only_or_no_text"
    if "code=5" in d or "code=7" in d or "object is not a stream" in d:
        return "pdf_parse_error"
    if "embedding coverage too low" in d:
        return "partial_embed"
    # Gateway / LLM transport errors — KeyError 'content' shape, raw HTTP 5xx
    # server errors from the LiteLLM gateway, and the wrapper message after
    # the in-call retry loop exhausts. All transient; should self-clear.
    if (
        "keyerror" in d
        or "'content'" in d
        or "500 server error" in d
        or "502 server error" in d
        or "503 server error" in d
        or "504 server error" in d
        or "bad gateway" in d
        or "gateway time-out" in d
        or "service temporarily unavailable" in d
        or "internal server error" in d
        or "llm call failed after all retries" in d
    ):
        return "gateway_error"
    return "unknown"

def _resolve_pdf_name(doc_id, current_pdf_name, volume_path):
    if current_pdf_name:
        return current_pdf_name
    if doc_id and doc_id.lower() in pdf_name_lookup:
        return pdf_name_lookup[doc_id.lower()]
    if volume_path:
        # Fallback: basename of the volume path so SRE has *something* to search by
        return volume_path.rsplit("/", 1)[-1]
    return None

failed_docs_rows = meta_df.filter(
    (col("metadata_status") == MetadataStatus.FAILED) | (col("chunk_status") == ChunkStatus.FAILED)
).select("document_id", "pdf_name", "volume_path", "metadata_status", "chunk_status",
         "metadata_error", "chunk_error").collect()

_n_metadata_fail = _n_chunk_fail = _n_skipped_dedup = 0
for r in failed_docs_rows:
    resolved_name = _resolve_pdf_name(r.document_id, r.pdf_name, r.volume_path)
    if r.metadata_status == MetadataStatus.FAILED:
        check_name = "Failed metadata extraction"
        if (r.document_id, check_name) in already_logged_terminal:
            _n_skipped_dedup += 1
        else:
            detail = r.metadata_error or "no error message"
            log_dq(r.document_id, resolved_name, check_name, "FAIL",
                   detail, failure_category=_classify_failure(detail))
            _n_metadata_fail += 1
    if r.chunk_status == ChunkStatus.FAILED:
        check_name = "Failed chunk ingestion"
        if (r.document_id, check_name) in already_logged_terminal:
            _n_skipped_dedup += 1
        else:
            detail = r.chunk_error or "no error message"
            log_dq(r.document_id, resolved_name, check_name, "FAIL",
                   detail, failure_category=_classify_failure(detail))
            _n_chunk_fail += 1
log.info(f"5.7 logged: {_n_metadata_fail} new metadata-fail, {_n_chunk_fail} new chunk-fail; "
         f"skipped {_n_skipped_dedup} already-logged within {DQ_FAIL_DEDUP_DAYS} days")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# WRITE DATA QUALITY FINDINGS TO DQ LOG TABLE
# ═══════════════════════════════════════════════════════════════════════════════
if dq_findings:
    log.info(f"Writing {len(dq_findings)} data quality findings to {DQ_LOG_TABLE}")
    now = datetime.now(timezone.utc)
    dq_rows = []
    for doc_id, pdf_name, check_name, severity, failure_category, detail in dq_findings:
        dq_id = hashlib.md5(
            f"{VALIDATE_RUN_ID}_{doc_id or ''}_{check_name}".encode()
        ).hexdigest()
        dq_rows.append({
            "dq_id": dq_id,
            "run_id": VALIDATE_RUN_ID,
            "document_id": doc_id,
            "pdf_name": pdf_name,
            "check_name": check_name,
            "severity": severity,
            "failure_category": failure_category,
            "detail": (detail or "")[:500],
            "created_at": now,
        })
    try:
        dq_df = spark.createDataFrame(dq_rows, schema=dq_log_schema())
        dq_df.write.mode("append").saveAsTable(DQ_LOG_TABLE)
        log.info(f"DQ findings written: {len(dq_rows)} rows")
    except Exception as e:
        log.warning(f"Failed to write DQ findings: {e}")
else:
    log.info("No data quality issues found — DQ log table not updated")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
total = len(results)
passed = sum(1 for _, p, _ in results if p)
failed = total - passed
warn_count = len(warnings)

log.info("=" * 60)
log.info(f"  TOTAL: {total}  |  PASSED: {passed}  |  FAILED: {failed}  |  WARNINGS: {warn_count}")
log.info("=" * 60)

if failed > 0:
    log.warning("Failed tests:")
    for name, p, detail in results:
        if not p:
            log.warning(f"  [FAIL] {name}  — {detail}")
if warn_count > 0:
    log.warning("Warnings (non-blocking):")
    for name, detail in warnings:
        log.warning(f"  [WARN] {name}  — {detail}")
if failed == 0 and warn_count == 0:
    log.info("All tests passed.")
elif failed == 0:
    log.info("All tests passed (with warnings).")

# Data profile summary
log.info("--- Data Profile ---")
log.info(f"  Metadata rows:     {meta_count}")
log.info(f"  Chunk rows:        {chunk_count}")
log.info(f"  Documents chunked: {len(chunked_docs)}")

if chunk_count > 0:
    stats = chunk_df.withColumn("_len", length(col("chunk_text"))).agg(
        spark_min("_len").alias("min_size"),
        spark_max("_len").alias("max_size"),
        avg("_len").alias("avg_size"),
    ).first()
    log.info(f"  Chunk size: min={stats.min_size}  max={stats.max_size}  avg={stats.avg_size:.0f}")

# Status breakdown
summary_rows = spark.sql(f"""
    SELECT metadata_status, chunk_status, COUNT(*) AS doc_count
    FROM {METADATA_TABLE}
    GROUP BY metadata_status, chunk_status
    ORDER BY 1, 2
""").collect()
for r in summary_rows:
    log.info(f"  {r.metadata_status} / {r.chunk_status}: {r.doc_count}")

# Fail the notebook if any checks failed (so workflow marks task as failed)
if failed > 0:
    raise AssertionError(f"Validation failed: {failed}/{total} checks did not pass")