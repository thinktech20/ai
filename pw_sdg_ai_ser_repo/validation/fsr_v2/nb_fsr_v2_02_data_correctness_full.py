# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_v2_02_data_correctness_full — FSR v2 end-to-end correctness gate
#
# Run at the END of a backfill, before declaring it complete. Not during — some
# checks (queue drained, no in-progress) only make sense once jobs are stopped.
#
# Read-only. No writes, no LLM calls, no credentials needed — every widget is a
# table name or a threshold.
#
# Runs on serverless. Nothing here is cached or persisted; every check issues a
# single aggregate query and keeps the scalar, so results cannot drift between
# what is reported and what the verdict is computed from.
#
# Every check returns PASS / FAIL / SKIP. The last cell fails the notebook if
# any check failed, so this can be wired into a job as a real gate rather than
# something a human reads and forgets.
#
# Widgets worth setting per run:
#   EXPECTED_COMPLETED_DOCS — expected completed count; blank skips that check
#   MAX_FAILED_DOC_PCT      — failure-rate ceiling, default 5%
#   STRICT_QUEUE_DRAINED    — "true" only when the backfill is meant to be done
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../common/fsr_v2/config

# COMMAND ----------

import logging

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.validation.correctness")

# COMMAND ----------

dbutils.widgets.text("METADATA_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_metadata_v2")  # noqa: F821
dbutils.widgets.text("CHUNK_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_chunks_v2")  # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.text("RUN_LOG_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_run_log_v2")  # noqa: F821
dbutils.widgets.text("EXPECTED_COMPLETED_DOCS", "")  # noqa: F821
dbutils.widgets.text("MAX_FAILED_DOC_PCT", "5.0")  # noqa: F821
dbutils.widgets.text("EMBEDDING_DIMENSION", "3072")  # noqa: F821
dbutils.widgets.dropdown("STRICT_QUEUE_DRAINED", "true", ["true", "false"])  # noqa: F821

METADATA_TABLE = get_runtime_param("METADATA_TABLE_V2", METADATA_TABLE_V2).strip()
CHUNK_TABLE = get_runtime_param("CHUNK_TABLE_V2", CHUNK_TABLE_V2).strip()
MAP_TABLE = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", DOC_EQUIPMENT_MAP_TABLE_V2).strip()
RUN_LOG_TABLE = get_runtime_param("RUN_LOG_TABLE_V2", RUN_LOG_TABLE_V2).strip()

_expected_raw = get_runtime_param("EXPECTED_COMPLETED_DOCS", "").strip()
EXPECTED_COMPLETED = int(_expected_raw) if _expected_raw else 0
MAX_FAILED_PCT = float(get_runtime_param("MAX_FAILED_DOC_PCT", "5.0"))
EMBEDDING_DIM = int(get_runtime_param("EMBEDDING_DIMENSION", "3072"))
STRICT_DRAINED = get_runtime_param("STRICT_QUEUE_DRAINED", "true").strip().lower() != "false"

if not METADATA_TABLE or not CHUNK_TABLE or not MAP_TABLE:
    raise ValueError("METADATA_TABLE_V2, CHUNK_TABLE_V2 and DOC_EQUIPMENT_MAP_TABLE_V2 are all required")

# COMMAND ----------

RESULTS = []


def _scalar(sql: str):
    return spark.sql(sql).first()[0]


def record(name: str, passed, detail: str) -> None:
    """passed True=PASS, False=FAIL, None=SKIP (check not applicable this run)."""
    RESULTS.append({"check": name, "result": {True: "PASS", False: "FAIL", None: "SKIP"}[passed], "detail": detail})
    _log = {True: log.info, False: log.error, None: log.warning}[passed]
    _log("[%s] %s — %s", {True: "PASS", False: "FAIL", None: "SKIP"}[passed], name, detail)


log.info("=== FSR v2 data correctness gate ===")
log.info(f"Metadata     : {METADATA_TABLE}")
log.info(f"Chunks       : {CHUNK_TABLE}")
log.info(f"Equipment map: {MAP_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Queue completeness

# COMMAND ----------

_counts = spark.sql(f"""
    SELECT
        COUNT(*)                                                            AS total,
        SUM(CASE WHEN metadata_status = 'completed'     THEN 1 ELSE 0 END)  AS p1_completed,
        SUM(CASE WHEN metadata_status = 'pending'       THEN 1 ELSE 0 END)  AS p1_pending,
        SUM(CASE WHEN metadata_status = 'failed'        THEN 1 ELSE 0 END)  AS p1_failed,
        SUM(CASE WHEN metadata_status = 'date_filtered' THEN 1 ELSE 0 END)  AS p1_date_filtered,
        SUM(CASE WHEN chunk_status = 'in_progress'      THEN 1 ELSE 0 END)  AS p2_in_progress,
        SUM(CASE WHEN metadata_status = 'completed'
                  AND chunk_status = 'pending'          THEN 1 ELSE 0 END)  AS p2_pending,
        SUM(CASE WHEN chunk_status = 'failed'           THEN 1 ELSE 0 END)  AS p2_failed
    FROM {METADATA_TABLE}
""").first()

if EXPECTED_COMPLETED:
    record(
        "expected completed doc count",
        _counts.p1_completed >= EXPECTED_COMPLETED,
        f"{_counts.p1_completed} completed, expected >= {EXPECTED_COMPLETED}",
    )
else:
    record("expected completed doc count", None, "EXPECTED_COMPLETED_DOCS not set")

if STRICT_DRAINED:
    record("P1 queue drained", _counts.p1_pending == 0, f"{_counts.p1_pending} still pending")
    record("P2 queue drained", _counts.p2_pending == 0, f"{_counts.p2_pending} completed docs not yet chunked")
else:
    record("P1 queue drained", None, "STRICT_QUEUE_DRAINED=false")
    record("P2 queue drained", None, "STRICT_QUEUE_DRAINED=false")

record("no stuck in_progress claims", _counts.p2_in_progress == 0, f"{_counts.p2_in_progress} in_progress")

_attempted = (_counts.p1_completed or 0) + (_counts.p1_failed or 0)
_fail_pct = (100.0 * _counts.p1_failed / _attempted) if _attempted else 0.0
record(
    f"P1 failure rate <= {MAX_FAILED_PCT}%",
    _fail_pct <= MAX_FAILED_PCT,
    f"{_counts.p1_failed}/{_attempted} = {_fail_pct:.2f}%",
)

_p2_attempted = (_counts.p2_failed or 0) + _scalar(
    f"SELECT COUNT(*) FROM {METADATA_TABLE} WHERE chunk_status = 'completed'"
)
_p2_fail_pct = (100.0 * _counts.p2_failed / _p2_attempted) if _p2_attempted else 0.0
record(
    f"P2 failure rate <= {MAX_FAILED_PCT}%",
    _p2_fail_pct <= MAX_FAILED_PCT,
    f"{_counts.p2_failed}/{_p2_attempted} = {_p2_fail_pct:.2f}%",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Metadata field quality

# COMMAND ----------

_no_esn = _scalar(f"""
    SELECT COUNT(*) FROM {METADATA_TABLE}
    WHERE metadata_status = 'completed'
      AND COALESCE(primary_esn, '') = ''
      AND COALESCE(gt_esn, '')      = ''
      AND COALESCE(gen_esn, '')     = ''
      AND COALESCE(st_esn, '')      = ''
""")
# Not a failure on its own — some reports genuinely carry no serial number. It is
# recorded because it sets the floor for the equipment-map check in section C.
record(
    "completed docs with at least one ESN",
    None,
    f"{_no_esn} of {_counts.p1_completed} completed docs have no ESN at all (informational; sets the map-check floor)",
)

_no_parsed_path = _scalar(f"""
    SELECT COUNT(*) FROM {METADATA_TABLE}
    WHERE metadata_status = 'completed' AND COALESCE(parsed_volume_path, '') = ''
""")
record(
    "parsed_volume_path set on completed docs",
    _no_parsed_path == 0,
    f"{_no_parsed_path} completed docs with no parsed artifact — P2 will re-parse these",
)

record(
    "legacy date-filtered queue reclaimed",
    _counts.p1_date_filtered == 0,
    f"{_counts.p1_date_filtered} date_filtered docs remain",
)

_dup_docs = _scalar(f"""
    SELECT COUNT(*) FROM (
        SELECT document_id FROM {METADATA_TABLE} GROUP BY document_id HAVING COUNT(*) > 1
    )
""")
record("document_id unique in metadata", _dup_docs == 0, f"{_dup_docs} duplicated document_id(s)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Equipment map integrity
# MAGIC
# MAGIC The map is written per LLM batch by P1, alongside that batch's metadata.
# MAGIC A completed document with a known ESN and no map row means a run was
# MAGIC interrupted before its map write — and the pipeline will not heal it,
# MAGIC because Stage 1 only re-queues `pending` and `failed` documents.
# MAGIC Repair with `nb_fsr_v2_repair_equipment_map`.

# COMMAND ----------

_map_gap = _scalar(f"""
    SELECT COUNT(*)
    FROM {METADATA_TABLE} m
    LEFT ANTI JOIN {MAP_TABLE} e ON m.document_id = e.document_id
    WHERE m.metadata_status = 'completed'
      AND (COALESCE(m.primary_esn, '') <> ''
        OR COALESCE(m.gt_esn, '')      <> ''
        OR COALESCE(m.gen_esn, '')     <> ''
        OR COALESCE(m.st_esn, '')      <> '')
""")
record(
    "equipment-map row for every completed doc with a known ESN",
    _map_gap == 0,
    f"{_map_gap} doc(s) missing — repair with nb_fsr_v2_repair_equipment_map",
)

_map_orphans = _scalar(f"""
    SELECT COUNT(*) FROM {MAP_TABLE} e
    LEFT ANTI JOIN {METADATA_TABLE} m ON e.document_id = m.document_id
""")
record("no orphan equipment-map rows", _map_orphans == 0, f"{_map_orphans} rows with no metadata row")

_map_blank_esn = _scalar(f"SELECT COUNT(*) FROM {MAP_TABLE} WHERE COALESCE(TRIM(esn), '') = ''")
record("no blank ESN in equipment map", _map_blank_esn == 0, f"{_map_blank_esn} blank ESN rows")

_map_dupes = _scalar(f"""
    SELECT COUNT(*) FROM (
        SELECT document_id, esn FROM {MAP_TABLE} GROUP BY document_id, esn HAVING COUNT(*) > 1
    )
""")
record("(document_id, esn) unique in equipment map", _map_dupes == 0, f"{_map_dupes} duplicated pair(s)")

_multi_primary = _scalar(f"""
    SELECT COUNT(*) FROM (
        SELECT document_id FROM {MAP_TABLE}
        WHERE is_primary_esn GROUP BY document_id HAVING COUNT(*) > 1
    )
""")
record("at most one primary ESN per document", _multi_primary == 0, f"{_multi_primary} doc(s) with multiple primaries")

_map_esn_mismatch = _scalar(f"""
    SELECT COUNT(*)
    FROM {MAP_TABLE} e
    JOIN {METADATA_TABLE} m ON e.document_id = m.document_id
    WHERE e.is_primary_esn AND UPPER(TRIM(COALESCE(m.primary_esn, ''))) <> e.esn
""")
record(
    "map primary ESN matches metadata primary_esn",
    _map_esn_mismatch == 0,
    f"{_map_esn_mismatch} mismatched row(s)",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## D. Chunk and embedding integrity

# COMMAND ----------

_missing_chunks = _scalar(f"""
    SELECT COUNT(*) FROM {METADATA_TABLE} m
    LEFT ANTI JOIN {CHUNK_TABLE} c ON m.document_id = c.document_id
    WHERE m.chunk_status = 'completed'
""")
record("chunks exist for every chunked doc", _missing_chunks == 0, f"{_missing_chunks} doc(s) with no chunks")

_orphan_chunks = _scalar(f"""
    SELECT COUNT(*) FROM {CHUNK_TABLE} c
    LEFT ANTI JOIN {METADATA_TABLE} m ON c.document_id = m.document_id
""")
record("no orphan chunks", _orphan_chunks == 0, f"{_orphan_chunks} chunk row(s) with no metadata row")

_dup_chunks = _scalar(f"""
    SELECT COUNT(*) FROM (
        SELECT chunk_id FROM {CHUNK_TABLE} GROUP BY chunk_id HAVING COUNT(*) > 1
    )
""")
record("chunk_id unique", _dup_chunks == 0, f"{_dup_chunks} duplicated chunk_id(s)")

_empty_text = _scalar(f"SELECT COUNT(*) FROM {CHUNK_TABLE} WHERE chunk_text IS NULL OR TRIM(chunk_text) = ''")
record("no empty chunk_text", _empty_text == 0, f"{_empty_text} empty chunk(s)")

_chunk_total = _scalar(f"SELECT COUNT(*) FROM {CHUNK_TABLE}")
if _chunk_total == 0:
    record(f"embedding dimension == {EMBEDDING_DIM}", None, "no chunk rows yet")
    record("no null embeddings", None, "no chunk rows yet")
else:
    _bad_dim = _scalar(f"""
        SELECT COUNT(*) FROM {CHUNK_TABLE}
        WHERE SIZE(chunk_embedding) <> {EMBEDDING_DIM}
           OR COALESCE(embedding_dimension, -1) <> {EMBEDDING_DIM}
    """)
    record(f"embedding dimension == {EMBEDDING_DIM}", _bad_dim == 0, f"{_bad_dim} chunk(s) with wrong dimension")

    _null_emb = _scalar(f"SELECT COUNT(*) FROM {CHUNK_TABLE} WHERE chunk_embedding IS NULL")
    record("no null embeddings", _null_emb == 0, f"{_null_emb} chunk(s) with null embedding")

# COMMAND ----------

# MAGIC %md
# MAGIC ## E. Run log
# MAGIC
# MAGIC Serverless does not return driver stdout, so the run log is the only
# MAGIC evidence a run's concurrency and batching settings took effect. An empty
# MAGIC run log usually means schema drift — an INSERT failing against a table
# MAGIC missing newer columns, swallowed by a non-blocking try/except.

# COMMAND ----------

if not RUN_LOG_TABLE:
    record("run log populated", None, "RUN_LOG_TABLE_V2 not configured")
else:
    try:
        _run_rows = spark.sql(f"""
            SELECT job_name, p1_workers, llm_batch_count, docs_claimed, docs_succeeded
            FROM {RUN_LOG_TABLE}
            WHERE job_name = 'PW_SDG_FSR_V2_Metadata'
            ORDER BY start_time DESC LIMIT 1
        """).collect()
        if not _run_rows:
            record("run log populated", False, "no P1 rows — check for schema drift on the run log table")
        else:
            _r = _run_rows[0]
            record(
                "run log populated",
                (_r.llm_batch_count or 0) > 0,
                f"workers={_r.p1_workers} batches={_r.llm_batch_count} "
                f"claimed={_r.docs_claimed} succeeded={_r.docs_succeeded}",
            )
    except Exception as _e:
        record("run log populated", False, f"query failed: {str(_e)[:200]}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verdict

# COMMAND ----------

_report = spark.createDataFrame(RESULTS)
display(_report)  # noqa: F821

_failed = [r for r in RESULTS if r["result"] == "FAIL"]
_skipped = [r for r in RESULTS if r["result"] == "SKIP"]

print(f"\n{'=' * 70}")
print(f"FSR v2 correctness gate — {METADATA_TABLE.split('.')[0]}")
print(f"  PASS {len([r for r in RESULTS if r['result'] == 'PASS'])}"
      f"  FAIL {len(_failed)}"
      f"  SKIP {len(_skipped)}")
print(f"{'=' * 70}")
for _r in _failed:
    print(f"  FAIL  {_r['check']}: {_r['detail']}")
for _r in _skipped:
    print(f"  SKIP  {_r['check']}: {_r['detail']}")

if _failed:
    raise AssertionError(
        f"{len(_failed)} correctness check(s) failed: " + "; ".join(r["check"] for r in _failed)
    )
print("\nAll applicable checks passed.")
