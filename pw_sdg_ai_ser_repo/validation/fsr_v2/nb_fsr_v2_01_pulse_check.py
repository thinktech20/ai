# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_v2_01_pulse_check — FSR v2 backfill heartbeat (read-only)
#
# Run every 1-2 hours while a backfill is in flight. Answers: is it moving, is
# it healthy, and are the three tables still consistent with each other.
#
# Read-only. No writes, no LLM calls, no credentials needed — every widget is a
# table name.
#
# Runs on serverless. Nothing here is cached or persisted, and each query is
# executed exactly once and collected — a DataFrame displayed and then re-read
# would run twice and, against a live backfill, return two different snapshots.
#
# Section 3 is the one that matters most: fsr_metadata_v2, fsr_chunks_v2 and
# fsr_document_equipment_map_v2 can each look healthy on their own while being
# inconsistent with each other. Single-table checks miss that.
#
# For the end-of-backfill gate, use nb_fsr_v2_02_data_correctness_full.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../common/fsr_v2/config

# COMMAND ----------

import logging

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.validation.pulse")

# COMMAND ----------

dbutils.widgets.text("METADATA_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_metadata_v2")  # noqa: F821
dbutils.widgets.text("CHUNK_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_chunks_v2")  # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("RUN_LOG_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_run_log_v2")  # noqa: F821
dbutils.widgets.text("DQ_LOG_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_data_quality_log_v2")  # noqa: F821
dbutils.widgets.text("THROUGHPUT_WINDOW_MINUTES", "60")  # noqa: F821
dbutils.widgets.text("STALE_CLAIM_MINUTES", "60")  # noqa: F821

METADATA_TABLE = get_runtime_param("METADATA_TABLE_V2", METADATA_TABLE_V2).strip()
CHUNK_TABLE = get_runtime_param("CHUNK_TABLE_V2", CHUNK_TABLE_V2).strip()
MAP_TABLE = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", DOC_EQUIPMENT_MAP_TABLE_V2).strip()
RUN_LOG_TABLE = get_runtime_param("RUN_LOG_TABLE_V2", RUN_LOG_TABLE_V2).strip()
DQ_LOG_TABLE = get_runtime_param("DQ_LOG_TABLE_V2", DQ_LOG_TABLE_V2).strip()
WINDOW_MIN = int(get_runtime_param("THROUGHPUT_WINDOW_MINUTES", "60"))
STALE_MIN = int(get_runtime_param("STALE_CLAIM_MINUTES", "60"))

if not METADATA_TABLE:
    raise ValueError("METADATA_TABLE_V2 is required")

log.info("=== FSR v2 pulse check ===")
log.info(f"Metadata     : {METADATA_TABLE}")
log.info(f"Chunks       : {CHUNK_TABLE}")
log.info(f"Equipment map: {MAP_TABLE}")
log.info(f"Run log      : {RUN_LOG_TABLE or '(not configured)'}")
log.info(f"DQ log       : {DQ_LOG_TABLE or '(not configured)'}")
log.info(f"Window       : {WINDOW_MIN} min | stale claim after {STALE_MIN} min")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Queue state
# MAGIC
# MAGIC `date_filtered` is a legacy state from the retired year filter. After
# MAGIC the reclaim migration, a drained queue has zero `pending` and zero
# MAGIC `date_filtered`.

# COMMAND ----------

_queue = spark.sql(f"""
    SELECT metadata_status, chunk_status, COUNT(*) AS docs
    FROM {METADATA_TABLE}
    GROUP BY 1, 2
    ORDER BY 1, 2
""")
display(_queue)  # noqa: F821

_totals = spark.sql(f"""
    SELECT
        COUNT(*)                                                                  AS total_docs,
        SUM(CASE WHEN metadata_status = 'pending'        THEN 1 ELSE 0 END)       AS p1_pending,
        SUM(CASE WHEN metadata_status = 'completed'      THEN 1 ELSE 0 END)       AS p1_completed,
        SUM(CASE WHEN metadata_status = 'failed'         THEN 1 ELSE 0 END)       AS p1_failed,
        SUM(CASE WHEN metadata_status = 'date_filtered'  THEN 1 ELSE 0 END)       AS p1_date_filtered,
        SUM(CASE WHEN metadata_status = 'completed'
                  AND chunk_status = 'pending'           THEN 1 ELSE 0 END)       AS p2_pending,
        SUM(CASE WHEN chunk_status = 'in_progress'       THEN 1 ELSE 0 END)       AS p2_in_progress,
        SUM(CASE WHEN chunk_status = 'completed'         THEN 1 ELSE 0 END)       AS p2_completed,
        SUM(CASE WHEN chunk_status = 'failed'            THEN 1 ELSE 0 END)       AS p2_failed
    FROM {METADATA_TABLE}
""").first()
display(spark.createDataFrame([_totals]))  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Throughput and ETA
# MAGIC
# MAGIC ETA assumes the current rate holds and is a rough planning number, not a
# MAGIC commitment. Reclaim legacy `date_filtered` rows before using this ETA.

# COMMAND ----------

_tput = spark.sql(f"""
    SELECT
        SUM(CASE WHEN metadata_status = 'completed' THEN 1 ELSE 0 END) AS p1_completed_in_window,
        SUM(CASE WHEN metadata_status = 'failed'    THEN 1 ELSE 0 END) AS p1_failed_in_window
    FROM {METADATA_TABLE}
    WHERE scraped_at > current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES
""").first()

_chunk_tput = spark.sql(f"""
    SELECT COUNT(*) AS p2_completed_in_window
    FROM {METADATA_TABLE}
    WHERE chunk_status = 'completed'
      AND chunked_at > current_timestamp() - INTERVAL {WINDOW_MIN} MINUTES
""").first()

_p1_rate = (_tput.p1_completed_in_window or 0) * 60.0 / WINDOW_MIN
_p2_rate = (_chunk_tput.p2_completed_in_window or 0) * 60.0 / WINDOW_MIN

log.info(
    "P1 last %dmin: completed=%s failed=%s  (~%.0f docs/hr)",
    WINDOW_MIN, _tput.p1_completed_in_window, _tput.p1_failed_in_window, _p1_rate,
)
log.info(
    "P2 last %dmin: completed=%s  (~%.0f docs/hr)",
    WINDOW_MIN, _chunk_tput.p2_completed_in_window, _p2_rate,
)
if _p1_rate > 0 and _totals.p1_pending:
    log.info("P1 ETA to drain %s pending: ~%.1f hours", _totals.p1_pending, _totals.p1_pending / _p1_rate)
elif _totals.p1_pending:
    log.warning("P1 has %s pending but zero completions in the window — stalled or not running", _totals.p1_pending)
if _p2_rate > 0 and _totals.p2_pending:
    log.info("P2 ETA to drain %s pending: ~%.1f hours", _totals.p2_pending, _totals.p2_pending / _p2_rate)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Cross-table consistency — the gate
# MAGIC
# MAGIC A document is only correct when metadata, chunks and the equipment map
# MAGIC agree. Each table can look fine alone while the set is inconsistent.
# MAGIC
# MAGIC A document with no ESN anywhere is *legitimately* absent from the
# MAGIC equipment map, so the raw "completed with no map row" count has a
# MAGIC non-zero floor. `missing_map_rows_real` subtracts that floor and is the
# MAGIC number to act on.

# COMMAND ----------

_consistency = spark.sql(f"""
    WITH mapped AS (SELECT DISTINCT document_id FROM {MAP_TABLE})
    SELECT
        COUNT(*)                                                      AS completed_docs,
        COUNT(e.document_id)                                          AS with_map_rows,
        COUNT(*) - COUNT(e.document_id)                               AS missing_map_rows_raw,
        SUM(CASE WHEN e.document_id IS NULL
                  AND COALESCE(m.primary_esn, '') = ''
                  AND COALESCE(m.gt_esn, '')      = ''
                  AND COALESCE(m.gen_esn, '')     = ''
                  AND COALESCE(m.st_esn, '')      = ''
             THEN 1 ELSE 0 END)                                       AS missing_but_no_esn,
        SUM(CASE WHEN e.document_id IS NULL
                  AND (COALESCE(m.primary_esn, '') <> ''
                    OR COALESCE(m.gt_esn, '')      <> ''
                    OR COALESCE(m.gen_esn, '')     <> ''
                    OR COALESCE(m.st_esn, '')      <> '')
             THEN 1 ELSE 0 END)                                       AS missing_map_rows_real
    FROM {METADATA_TABLE} m
    LEFT JOIN mapped e ON m.document_id = e.document_id
    WHERE m.metadata_status = 'completed'
""").first()
display(spark.createDataFrame([_consistency]))  # noqa: F821

_missing_chunks = spark.sql(f"""
    SELECT COUNT(*) AS n
    FROM {METADATA_TABLE} m
    LEFT ANTI JOIN {CHUNK_TABLE} c ON m.document_id = c.document_id
    WHERE m.chunk_status = 'completed'
""").first().n

_orphan_rows = spark.sql(f"""
    SELECT 'equipment_map' AS tbl, COUNT(*) AS orphan_rows
    FROM {MAP_TABLE} e
    LEFT ANTI JOIN {METADATA_TABLE} m ON e.document_id = m.document_id
    UNION ALL
    SELECT 'chunks', COUNT(*)
    FROM {CHUNK_TABLE} c
    LEFT ANTI JOIN {METADATA_TABLE} m ON c.document_id = m.document_id
""").collect()
display(spark.createDataFrame(_orphan_rows))  # noqa: F821

_orphan_total = sum(r.orphan_rows for r in _orphan_rows)

# COMMAND ----------

# Consistency verdict. Non-zero here means stop and repair before running more
# jobs — the pipeline will not heal these on its own, because Stage 1 only
# re-queues 'pending' and 'failed' documents, never 'completed' ones.
_issues = []
if _consistency.missing_map_rows_real:
    _issues.append(
        f"{_consistency.missing_map_rows_real} completed doc(s) with a known ESN have no "
        f"equipment-map row — repair with nb_fsr_v2_repair_equipment_map"
    )
if _missing_chunks:
    _issues.append(f"{_missing_chunks} doc(s) at chunk_status='completed' have no chunk rows")
if _orphan_total:
    _issues.append(f"{_orphan_total} orphan row(s) referencing documents not in the metadata table")

if _issues:
    for _i in _issues:
        log.error("CONSISTENCY FAIL: %s", _i)
else:
    log.info(
        "CONSISTENCY OK — map, chunks and metadata agree "
        f"({_consistency.missing_but_no_esn} completed doc(s) have no ESN at all and are correctly unmapped)"
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Run log
# MAGIC
# MAGIC Serverless does not return driver stdout, so the run log is the durable
# MAGIC evidence of worker count and LLM batching. `docs_date_filtered` is kept
# MAGIC for historical compatibility and must be zero on new runs.

# COMMAND ----------

if RUN_LOG_TABLE:
    display(spark.sql(f"""
        SELECT job_name, start_time, end_time, duration_seconds,
               p1_workers, llm_batch_count, docs_date_filtered,
               docs_claimed, docs_succeeded, docs_failed, chunks_written,
               substr(error_summary, 1, 200) AS error_summary
        FROM {RUN_LOG_TABLE}
        ORDER BY start_time DESC
        LIMIT 10
    """))  # noqa: F821
else:
    log.info("Run log not configured — skipped")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Data quality log
# MAGIC
# MAGIC FAIL rows should track the failed-doc count. WARN rows are informational
# MAGIC — `no_text_layer_suspected_scan` is the OCR backlog, not a pipeline bug.

# COMMAND ----------

if DQ_LOG_TABLE:
    display(spark.sql(f"""
        SELECT severity, failure_category, COUNT(*) AS n
        FROM {DQ_LOG_TABLE}
        GROUP BY 1, 2
        ORDER BY n DESC
    """))  # noqa: F821
else:
    log.info("DQ log not configured — skipped")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Stale claims
# MAGIC
# MAGIC `chunk_status='in_progress'` older than the threshold means P2 claimed a
# MAGIC document and died before releasing it. Expect zero.

# COMMAND ----------

_stale_rows = spark.sql(f"""
    SELECT document_id, pdf_name, chunked_at, chunk_retry_count
    FROM {METADATA_TABLE}
    WHERE chunk_status = 'in_progress'
      AND chunked_at < current_timestamp() - INTERVAL {STALE_MIN} MINUTES
    ORDER BY chunked_at
    LIMIT 50
""").collect()
_stale_n = len(_stale_rows)
if _stale_n:
    log.warning("%d stale claim(s) older than %d min (capped at 50)", _stale_n, STALE_MIN)
    display(spark.createDataFrame(_stale_rows))  # noqa: F821
else:
    log.info("No stale claims")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Recent failures
# MAGIC
# MAGIC Failures arriving in groups the size of `FSR_V2_P1_LLM_BATCH_SIZE` with
# MAGIC the same error text are one bad LLM batch, not N independent bad PDFs.

# COMMAND ----------

display(spark.sql(f"""
    SELECT 'P1' AS stage, document_id, pdf_name, scraped_at AS at,
           metadata_retry_count AS retries, substr(metadata_error, 1, 200) AS error
    FROM {METADATA_TABLE} WHERE metadata_status = 'failed'
    UNION ALL
    SELECT 'P2', document_id, pdf_name, chunked_at,
           chunk_retry_count, substr(chunk_error, 1, 200)
    FROM {METADATA_TABLE} WHERE chunk_status = 'failed'
    ORDER BY at DESC
    LIMIT 25
"""))  # noqa: F821

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Summary
# MAGIC
# MAGIC Copy into the pulse log / status thread.

# COMMAND ----------

_summary = f"""
FSR v2 pulse — {METADATA_TABLE.split('.')[0]}
  Queue      : completed={_totals.p1_completed} pending={_totals.p1_pending} failed={_totals.p1_failed} date_filtered={_totals.p1_date_filtered}
  Chunking   : completed={_totals.p2_completed} pending={_totals.p2_pending} in_progress={_totals.p2_in_progress} failed={_totals.p2_failed}
  Throughput : P1 ~{_p1_rate:.0f} docs/hr, P2 ~{_p2_rate:.0f} docs/hr (last {WINDOW_MIN} min)
  Consistency: {'OK' if not _issues else 'FAIL — ' + '; '.join(_issues)}
  Stale claims: {_stale_n}
""".strip()
print(_summary)
