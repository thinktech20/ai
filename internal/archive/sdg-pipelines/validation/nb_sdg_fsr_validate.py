# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_validate — Post-run validation checks
#
# Runs after Process 1 + Process 2 to verify data quality, schema
# compliance, and cross-process consistency.
#
# Schema v3: document_id is PK. Statuses: pending / completed / failed.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../common/fsr_config

# COMMAND ----------

import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, avg, length, size, when, lower,
    min as spark_min, max as spark_max,
)
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.validate")

results = []  # (test_name, passed, detail)

def check(name, condition, detail=""):
    passed = bool(condition)
    results.append((name, passed, detail))
    status = "PASS" if passed else "FAIL"
    log.info(f"[{status}] {name}" + (f"  — {detail}" if detail else ""))

log.info(f"Validating:")
log.info(f"  Metadata: {METADATA_TABLE}")
log.info(f"  Chunks:   {CHUNK_TABLE}")

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
valid_chunk_statuses = {ChunkStatus.PENDING, ChunkStatus.COMPLETED, ChunkStatus.FAILED}
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
no_title = completed_df.filter(col("title").isNull() | (col("title") == "")).count()
check("1.7 All 'completed' docs have title", no_title == 0,
      f"{no_title} missing title")

# 1.8  Date format check (YYYY-MM-DD)
date_cols = ["report_issued_date", "outage_start_date", "outage_end_date"]
for dc in date_cols:
    bad_dates = completed_df.filter(
        col(dc).isNotNull() & (col(dc) != "") &
        ~col(dc).rlike(r"^\d{4}-\d{2}-\d{2}$")
    ).count()
    check(f"1.8 Date format '{dc}'", bad_dates == 0,
          f"{bad_dates} non-YYYY-MM-DD values")

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

# 2.3  chunk_index is sequential per document (0-based, no gaps)
w = Window.partitionBy("document_id").orderBy("chunk_index")
gap_df = chunk_df.withColumn("expected_idx", row_number().over(w) - 1)
gaps = gap_df.filter(col("chunk_index") != col("expected_idx")).count()
check("2.3 chunk_index sequential (no gaps)", gaps == 0,
      f"{gaps} out-of-sequence chunks")

# 2.4  chunk_text is not empty
empty_text = chunk_df.filter(col("chunk_text").isNull() | (col("chunk_text") == "")).count()
check("2.4 No empty chunk_text", empty_text == 0, f"{empty_text} empty")

# 2.5  chunk_size matches actual text length
size_mismatch = chunk_df.filter(col("chunk_size") != length(col("chunk_text"))).count()
check("2.5 chunk_size matches text length", size_mismatch == 0,
      f"{size_mismatch} mismatches")

# 2.6  Embedding dimension is correct
null_embeddings = chunk_df.filter(col("embedding").isNull()).count()
check("2.6a No null embeddings", null_embeddings == 0, f"{null_embeddings} nulls")

bad_dim = chunk_df.filter(
    col("embedding").isNotNull() & (size(col("embedding")) != EMBEDDING_DIMENSION)
).count()
check(f"2.6b Embedding dim = {EMBEDDING_DIMENSION}", bad_dim == 0,
      f"{bad_dim} wrong dimension")

# 2.7  start_page <= end_page
bad_pages = chunk_df.filter(col("start_page") > col("end_page")).count()
check("2.7 start_page <= end_page", bad_pages == 0, f"{bad_pages} violations")

# 2.8  Chunk sizes within expected bounds
max_expected = CHUNKING_CONFIG.chunk_size + 200
oversized = chunk_df.filter(col("chunk_size") > max_expected).count()
check(f"2.8 Chunk size <= {max_expected}", oversized == 0,
      f"{oversized} oversized chunks")

# 2.9  chunk_count field matches actual count per doc
actual_counts = chunk_df.groupBy("document_id").agg(count("*").alias("actual_count"))
count_check = chunk_df.select("document_id", "chunk_count").distinct().join(
    actual_counts, "document_id"
)
count_mismatch = count_check.filter(col("chunk_count") != col("actual_count")).count()
check("2.9 chunk_count matches actual", count_mismatch == 0,
      f"{count_mismatch} mismatches")

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

# 3.2  No orphan chunks (chunk document_id not in metadata)
meta_doc_ids = set(
    row.document_id for row in meta_df.select("document_id").collect()
)
orphan_chunks = chunked_docs - meta_doc_ids
check("3.2 No orphan chunks", len(orphan_chunks) == 0,
      f"{len(orphan_chunks)} orphan document_ids in chunk table")

# 3.3  Materialized metadata matches source
join_df = chunk_df.alias("c").join(
    meta_df.alias("m"), col("c.document_id") == col("m.document_id")
).select(
    col("c.document_id"),
    (col("c.pdf_name") != col("m.pdf_name")).alias("pdf_name_mismatch"),
    (col("c.esn") != col("m.esn")).alias("esn_mismatch"),
    (col("c.title") != col("m.title")).alias("title_mismatch"),
    (col("c.equipment_sys_id") != col("m.equipment_sys_id")).alias("equip_sys_id_mismatch"),
    (col("c.equipment_type") != col("m.equipment_type")).alias("equip_type_mismatch"),
    (col("c.event_type") != col("m.event_type")).alias("event_type_mismatch"),
    (col("c.ev_equipment_event_id") != col("m.ev_equipment_event_id")).alias("ev_equip_event_mismatch"),
    (col("c.fsp_project_id") != col("m.fsp_project_id")).alias("fsp_project_mismatch"),
    (col("c.report_issued_date") != col("m.report_issued_date")).alias("report_date_mismatch"),
    (col("c.outage_start_date") != col("m.outage_start_date")).alias("outage_start_mismatch"),
    (col("c.outage_end_date") != col("m.outage_end_date")).alias("outage_end_mismatch"),
    (col("c.page_count") != col("m.page_count")).alias("page_mismatch"),
)
for field_name, col_name in [
    ("pdf_name", "pdf_name_mismatch"),
    ("esn", "esn_mismatch"),
    ("title", "title_mismatch"),
    ("equipment_sys_id", "equip_sys_id_mismatch"),
    ("equipment_type", "equip_type_mismatch"),
    ("event_type", "event_type_mismatch"),
    ("ev_equipment_event_id", "ev_equip_event_mismatch"),
    ("fsp_project_id", "fsp_project_mismatch"),
    ("report_issued_date", "report_date_mismatch"),
    ("outage_start_date", "outage_start_mismatch"),
    ("outage_end_date", "outage_end_mismatch"),
    ("page_count", "page_mismatch"),
]:
    mismatches = join_df.filter(col(col_name) == True).select("document_id").distinct().count()
    check(f"3.3 {field_name} matches metadata", mismatches == 0,
          f"{mismatches} docs with mismatch")

# 3.4  No stale pending chunks for completed metadata
stale = meta_df.filter(
    (col("metadata_status") == MetadataStatus.COMPLETED) &
    (col("chunk_status") == ChunkStatus.PENDING)
).count()
check("3.4 No stale pending chunks for completed metadata", stale == 0,
      f"{stale} docs still pending after both processes ran")

# 3.5  pdf_name derivation coverage
completed_meta = meta_df.filter(col("metadata_status") == MetadataStatus.COMPLETED)
completed_total = completed_meta.count()
no_pdf_name = completed_meta.filter(col("pdf_name").isNull() | (col("pdf_name") == "")).count()
check("3.5 Completed docs have pdf_name derived", no_pdf_name == 0,
      f"{no_pdf_name}/{completed_total} completed docs missing pdf_name")

# 3.6  document_id is lowercase normalized (no .pdf suffix)
bad_doc_ids = meta_df.filter(
    col("document_id").rlike(r"\.(pdf|PDF)$") | (col("document_id") != lower(col("document_id")))
).count()
check("3.6 document_id normalized (lowercase, no .pdf)", bad_doc_ids == 0,
      f"{bad_doc_ids} non-normalized document_ids")

# COMMAND ----------

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
total = len(results)
passed = sum(1 for _, p, _ in results if p)
failed = total - passed

log.info("=" * 60)
log.info(f"  TOTAL: {total}  |  PASSED: {passed}  |  FAILED: {failed}")
log.info("=" * 60)

if failed > 0:
    log.warning("Failed tests:")
    for name, p, detail in results:
        if not p:
            log.warning(f"  [FAIL] {name}  — {detail}")
else:
    log.info("All tests passed.")

# Data profile summary
log.info("--- Data Profile ---")
log.info(f"  Metadata rows:     {meta_count}")
log.info(f"  Chunk rows:        {chunk_count}")
log.info(f"  Documents chunked: {len(chunked_docs)}")

if chunk_count > 0:
    stats = chunk_df.agg(
        spark_min("chunk_size").alias("min_size"),
        spark_max("chunk_size").alias("max_size"),
        avg("chunk_size").alias("avg_size"),
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