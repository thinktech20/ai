# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_mnd_ingestion — M&D (Monitoring & Diagnostics) Ingestion Pipeline
#
# Single-notebook pipeline:
#   Extract → Preprocess → Boilerplate → PII Redact → Chunk → Embed → Write → VS Sync
#
# Production port of the data-science research notebook (E3_final.py):
#   - Reads from the M&D source view filtered by u_type + u_resolution_category
#   - Applies the 7-step preprocessing (null proxies, drop, numeric, sentinel,
#     date filter, record_origin, handoff schema)
#   - Boilerplate phrase + URL strip on 7 text columns
#   - Presidio + Flair PII redaction (PERSON, EMAIL, PHONE, SSO_ID)
#   - 4-step chunking (timestamp-boundary split → merge<256 → split>512 →
#     merge<200 backward)
#   - Embeds via LiteLLM, writes to Delta, syncs Hybrid Vector Search index
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# ── Runtime library install ────────────────────────────────────────────────
# Presidio + Flair are not present on Databricks Runtime by default.
# Installed here (unpinned, matching the DS research notebook) so the job
# works on any compute type (serverless, job cluster, all-purpose).
# `restartPython()` must run BEFORE any subsequent %run so the new
# packages are picked up when mnd_chunking imports them lazily.

# MAGIC %pip install presidio_analyzer presidio_anonymizer flair
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ../../../common/mnd_config

# COMMAND ----------

# MAGIC %run ../../../common/mnd_chunking

# COMMAND ----------

import json
import logging
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
log = logging.getLogger("mnd.ingestion")

# COMMAND ----------
# ── Preflight: validate config + test embedding API before heavy work ──────────
# Runs a single-string embedding call to catch gateway/auth/routing issues
# immediately — before extraction, preprocessing, PII (which takes hours).

def _preflight_check():
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    sep = "─" * 60
    print(sep)
    print("M&D PIPELINE PREFLIGHT")
    print(sep)

    errors = []

    key_preview = (LITELLM_API_KEY[:8] + "..." + LITELLM_API_KEY[-4:]) if len(LITELLM_API_KEY) > 12 else ("(EMPTY)" if not LITELLM_API_KEY else LITELLM_API_KEY)
    print(f"  LITELLM_BASE_URL            : {LITELLM_BASE_URL!r}")
    print(f"  MND_EMBEDDING_REQUEST_PATH  : {MND_EMBEDDING_REQUEST_PATH!r}")
    print(f"  EMBEDDING_MODEL             : {EMBEDDING_MODEL!r}")
    print(f"  EMBEDDING_DIMENSION         : {EMBEDDING_DIMENSION}")
    print(f"  LITELLM_API_KEY             : {key_preview}")
    print(f"  MND_SOURCE_TABLE            : {MND_SOURCE_TABLE!r}")
    print(f"  MND_PREPROCESSED_TABLE      : {MND_PREPROCESSED_TABLE!r}")
    print(f"  MND_CHUNK_TABLE             : {MND_CHUNK_TABLE!r}")
    print(f"  MND_RUN_LOG_TABLE           : {MND_RUN_LOG_TABLE!r}")
    print(f"  MND_FAILED_RECORDS_TABLE    : {MND_FAILED_RECORDS_TABLE!r}")
    print(f"  MND_VS_ENDPOINT             : {MND_VS_ENDPOINT!r}")
    print(f"  MND_VS_INDEX                : {MND_VS_INDEX!r}")
    print(f"  MND_VS_INDEX_TYPE           : {MND_VS_INDEX_TYPE!r}")
    print(f"  MND_FILTER_U_TYPE           : {MND_FILTER_U_TYPE!r}")
    print(f"  MND_FILTER_U_RESOLUTION_CATEGORY: {MND_FILTER_U_RESOLUTION_CATEGORY!r}")
    print(f"  MND_CUTOFF_DATE             : {MND_CUTOFF_DATE!r}")
    print(f"  Serial filter               : {MND_SERIAL_NUMBERS or 'all'}")
    print(f"  MND_RECORD_BATCH_SIZE       : {MND_RECORD_BATCH_SIZE}")
    print(f"  Chunking thresholds         : min={MND_CHUNK_MIN_TOKENS}, max={MND_CHUNK_MAX_TOKENS}, tiny={MND_CHUNK_TINY_TOKENS}")
    print(f"  MND_FLAIR_MODEL             : {MND_FLAIR_MODEL!r}")
    print(f"  MND_MAX_RECORDS             : {MND_MAX_RECORDS}")
    print(f"  FORCE_RESET                 : {FORCE_RESET}")

    if not LITELLM_API_KEY:
        errors.append("LITELLM_API_KEY is empty — check secret scope or widget")

    base = LITELLM_BASE_URL.rstrip("/")
    session = requests.Session()
    session.trust_env = False
    session.verify = LLM_VERIFY_SSL
    try:
        probe = session.head(base, timeout=10)
        print(f"\n  [gateway probe] HEAD {base} -> HTTP {probe.status_code}")
    except Exception as e:
        print(f"\n  [gateway probe] HEAD {base} -> FAILED: {e}")
        errors.append(f"Gateway unreachable: {e}")

    try:
        print("  [embed smoke]   calling embed_texts_batch(timeout=45s, retries=1) ...")
        vectors = embed_texts_batch(
            ["preflight test"],
            base_url=LITELLM_BASE_URL,
            api_key=LITELLM_API_KEY,
            model=EMBEDDING_MODEL,
            dimension=EMBEDDING_DIMENSION,
            request_path=MND_EMBEDDING_REQUEST_PATH,
            verify_ssl=LLM_VERIFY_SSL,
            max_retries=1,
            request_timeout=45.0,
        )
        print(f"  [embed smoke]   OK — vector dim={len(vectors[0])}")
        print(sep)
        print("PREFLIGHT PASSED")
        print(sep)
        return
    except Exception as e:
        print(f"  [embed smoke]   FAILED: {e}")
        errors.append(str(e))

    print(sep)
    raise RuntimeError(
        "PREFLIGHT FAILED — fix embedding config before running the pipeline.\n"
        + "\n".join(errors)
    )


# NOTE: Preflight runs at notebook load time (Databricks executes cells
# sequentially).  This is intentional — it catches gateway/auth/routing
# issues before the expensive extract+PII+chunk phase.
_preflight_check()

# COMMAND ----------

# ── Watermark / run log helpers ────────────────────────────────────────────

def cleanup_stale_runs() -> int:
    """Mark any in_progress rows that predate this run as 'failed'.

    A run killed by Databricks timeout (or cluster restart) leaves a permanent
    in_progress row.  Without cleanup these accumulate.  Failed rows still
    contribute to the watermark via get_last_watermark.
    """
    if not MND_RUN_LOG_TABLE:
        return 0
    try:
        spark.sql(f"""
            UPDATE {MND_RUN_LOG_TABLE}
            SET status = 'failed',
                run_completed_at = current_timestamp()
            WHERE status = 'in_progress'
        """)
        updated = spark.sql(f"""
            SELECT COUNT(*) AS cnt FROM {MND_RUN_LOG_TABLE}
            WHERE status = 'failed'
              AND run_completed_at >= current_timestamp() - INTERVAL 5 SECONDS
        """).first().cnt
        if updated:
            log.warning(
                f"Cleaned up {updated} stale in_progress run(s) in {MND_RUN_LOG_TABLE}"
            )
        return updated
    except Exception as e:
        log.warning(f"Stale run cleanup failed (non-blocking): {e}")
        return 0


def get_last_watermark():
    """Return MAX watermark_ts from completed/failed runs, or None.

    'failed' rows are included so a crashed run still provides a resume floor.
    """
    if not MND_RUN_LOG_TABLE or FORCE_RESET:
        return None
    try:
        row = spark.sql(f"""
            SELECT CAST(MAX(watermark_ts) AS STRING) AS wm FROM {MND_RUN_LOG_TABLE}
            WHERE status IN ('completed', 'failed')
              AND watermark_ts IS NOT NULL
        """).first()
        wm = row.wm if row and row.wm else None
        if wm:
            log.info(f"Incremental run: using watermark sys_updated_on > '{wm}'")
        else:
            log.info("No previous completed run found — full load from MND_CUTOFF_DATE")
        return wm
    except Exception as e:
        log.warning(f"Could not read run log (non-blocking): {e}")
        return None


def write_run_log(
    run_id: str,
    started_at,
    status: str,
    records_extracted: int,
    chunks_written: int,
    watermark_ts,
) -> None:
    """Upsert a run log row (MERGE by run_id). Non-blocking."""
    if not MND_RUN_LOG_TABLE:
        return
    if status not in ("completed", "failed", "in_progress", "backfill_audit"):
        log.warning(f"Unexpected run log status '{status}' — coercing to 'failed'")
        status = "failed"
    try:
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType, TimestampType,
        )

        completed_at = datetime.now(timezone.utc) if status != "in_progress" else None

        schema = StructType([
            StructField("run_id", StringType(), False),
            StructField("pipeline", StringType(), True),
            StructField("run_started_at", TimestampType(), True),
            StructField("run_completed_at", TimestampType(), True),
            StructField("status", StringType(), True),
            StructField("records_extracted", IntegerType(), True),
            StructField("chunks_written", IntegerType(), True),
            StructField("watermark_ts", StringType(), True),
        ])

        row = [(run_id, "mnd_ingestion", started_at, completed_at,
                status, records_extracted, chunks_written, watermark_ts)]
        log_df = spark.createDataFrame(row, schema)

        tmp_view = f"_mnd_run_log_staging_{int(time.time())}"
        log_df.createOrReplaceTempView(tmp_view)

        spark.sql(f"""
            MERGE INTO {MND_RUN_LOG_TABLE} AS target
            USING {tmp_view} AS source
            ON target.run_id = source.run_id
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """)
        log.info(f"Run log written: run_id={run_id}, status={status}, "
                 f"chunks={chunks_written}, watermark={watermark_ts}")
    except Exception as e:
        log.warning(f"Failed to write run log (non-blocking): {e}")

# COMMAND ----------

# ── Failed-records table helpers ────────────────────────────────────────────

def read_retry_records():
    """Return the set of mnd_case_numbers eligible for retry on this run."""
    if not MND_FAILED_RECORDS_TABLE:
        return set()
    try:
        rows = spark.sql(f"""
            SELECT mnd_case_number FROM {MND_FAILED_RECORDS_TABLE}
            WHERE attempts < {MND_MAX_RECORD_ATTEMPTS}
        """).collect()
        retry_set = {r.mnd_case_number for r in rows if r.mnd_case_number}
        if retry_set:
            log.info(f"Retry list: {len(retry_set)} previously-failed records "
                     f"will be re-attempted (attempts < {MND_MAX_RECORD_ATTEMPTS})")
        return retry_set
    except Exception as e:
        log.warning(f"Could not read failed-records table (non-blocking): {e}")
        return set()


def write_failed_records(failed: list, run_id: str) -> None:
    """Upsert failure rows.  `failed` is list of (mnd_case_number, sys_updated_on, error)."""
    if not MND_FAILED_RECORDS_TABLE or not failed:
        return
    try:
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType, TimestampType,
        )
        now = datetime.now(timezone.utc)

        schema = StructType([
            StructField("mnd_case_number", StringType(), False),
            StructField("sys_updated_on", TimestampType(), True),
            StructField("first_failed_at", TimestampType(), True),
            StructField("last_attempted_at", TimestampType(), True),
            StructField("attempts", IntegerType(), True),
            StructField("last_error", StringType(), True),
            StructField("last_run_id", StringType(), True),
        ])

        rows = []
        for mnd_case_number, sys_updated_on, err_msg in failed:
            truncated = (err_msg[:500] + "...") if err_msg and len(err_msg) > 500 else err_msg
            sut = sys_updated_on
            if isinstance(sut, str):
                try:
                    sut = pd.to_datetime(sut, utc=True).to_pydatetime()
                except Exception:
                    sut = None
            rows.append((str(mnd_case_number), sut, now, now, 1, truncated, run_id))

        df = spark.createDataFrame(rows, schema)
        tmp_view = f"_mnd_failed_staging_{int(time.time())}"
        df.createOrReplaceTempView(tmp_view)

        spark.sql(f"""
            MERGE INTO {MND_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.mnd_case_number = source.mnd_case_number
            WHEN MATCHED THEN UPDATE SET
                target.attempts = target.attempts + 1,
                target.last_attempted_at = source.last_attempted_at,
                target.last_error = source.last_error,
                target.last_run_id = source.last_run_id,
                target.sys_updated_on = source.sys_updated_on
            WHEN NOT MATCHED THEN INSERT *
        """)
        log.info(f"Failed records table updated: {len(failed)} record(s) tracked")
    except Exception as e:
        log.warning(f"Failed to write failed-records table (non-blocking): {e}")


def seed_preprocessed_gaps() -> int:
    """Seed records present in the preprocessed table but absent from both the
    chunk table and the failed-records table into failed-records (attempts=0)
    so they are picked up by read_retry_records() on this same run.

    This closes the silent-gap scenario where a prior run wrote to
    MND_PREPROCESSED_TABLE but crashed before chunking/embedding without
    recording the affected records in MND_FAILED_RECORDS_TABLE — leaving them
    invisible to both the watermark and the retry loop.

    Non-blocking: any exception is logged and the pipeline continues.
    """
    if not MND_PREPROCESSED_TABLE or not MND_CHUNK_TABLE or not MND_FAILED_RECORDS_TABLE:
        return 0
    try:
        from pyspark.sql.functions import current_timestamp as _now_gap, lit as _lit_gap

        gap_df = spark.sql(f"""
            WITH pre AS (
                SELECT number_ AS mnd_case_number
                FROM {MND_PREPROCESSED_TABLE}
                WHERE number_ IS NOT NULL
            ),
            chunked AS (
                SELECT DISTINCT mnd_case_number
                FROM {MND_CHUNK_TABLE}
                WHERE mnd_case_number IS NOT NULL
            ),
            already_tracked AS (
                SELECT mnd_case_number
                FROM {MND_FAILED_RECORDS_TABLE}
                WHERE mnd_case_number IS NOT NULL
            )
            SELECT p.mnd_case_number
            FROM pre p
            LEFT ANTI JOIN chunked c       ON p.mnd_case_number = c.mnd_case_number
            LEFT ANTI JOIN already_tracked f ON p.mnd_case_number = f.mnd_case_number
        """)

        gap_count = gap_df.count()
        if gap_count == 0:
            log.info("Preprocessed-gap check: no gaps found")
            return 0

        log.warning(
            f"Preprocessed-gap check: {gap_count} record(s) found in "
            f"{MND_PREPROCESSED_TABLE} with no chunk and no failed-records entry — "
            f"seeding for retry on this run"
        )

        seed_df = (
            gap_df
            .withColumn("sys_updated_on",    _lit_gap(None).cast("timestamp"))
            .withColumn("first_failed_at",    _now_gap())
            .withColumn("last_attempted_at",  _lit_gap(None).cast("timestamp"))
            .withColumn("attempts",           _lit_gap(0))
            .withColumn("last_error",         _lit_gap(
                "GAP_DETECTED: present in preprocessed table but missing "
                "from chunk table and failed_records"
            ))
            .withColumn("last_run_id",        _lit_gap("gap-detection"))
        )

        tmp_view = f"_mnd_gap_seed_{int(time.time())}"
        seed_df.createOrReplaceTempView(tmp_view)
        spark.sql(f"""
            MERGE INTO {MND_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.mnd_case_number = source.mnd_case_number
            WHEN NOT MATCHED THEN INSERT *
        """)
        log.info(
            f"Preprocessed-gap check: seeded {gap_count} record(s) into "
            f"{MND_FAILED_RECORDS_TABLE} for retry"
        )
        return gap_count
    except Exception as e:
        log.warning(f"Preprocessed-gap check failed (non-blocking): {e}")
        return 0

# COMMAND ----------

def clear_succeeded_retries(succeeded: set) -> None:
    """Delete rows from failed-records for records that succeeded this run."""
    if not MND_FAILED_RECORDS_TABLE or not succeeded:
        return
    try:
        from pyspark.sql.types import StructType, StructField, StringType
        schema = StructType([StructField("mnd_case_number", StringType(), False)])
        df = spark.createDataFrame([(str(n),) for n in succeeded], schema)
        tmp_view = f"_mnd_cleared_staging_{int(time.time())}"
        df.createOrReplaceTempView(tmp_view)
        delete_result = spark.sql(f"""
            DELETE FROM {MND_FAILED_RECORDS_TABLE}
            WHERE mnd_case_number IN (SELECT mnd_case_number FROM {tmp_view})
        """)
        num_deleted = 0
        if delete_result:
            first_row = delete_result.first()
            if first_row:
                row_dict = first_row.asDict()
                num_deleted = row_dict.get("num_deleted_rows", row_dict.get("num_affected_rows", 0)) or 0
        if num_deleted:
            log.info(f"Failed records table: cleared {num_deleted} successful retries")
    except Exception as e:
        log.warning(f"Failed to clear succeeded retries (non-blocking): {e}")

# COMMAND ----------

# ── Extract: M&D source records with business filters ──────────────────────

def extract_mnd_records(watermark=None):
    """Query M&D source view with watermark + business filters; return Spark DF.

    Filters applied at the SQL level:
      - u_type IN MND_FILTER_U_TYPE (e.g. ['Ops Center', 'Op Center- Trips'])
      - u_resolution_category IN MND_FILTER_U_RESOLUTION_CATEGORY (4 values)
      - u_ccap_alarm_name IS NOT NULL AND NOT IN MND_NULL_PROXIES
      - sys_updated_on > watermark  (or opened_at >= MND_CUTOFF_DATE on first run)

    User-supplied filter values (MND_SERIAL_NUMBERS) are applied via Spark
    DataFrame .filter().isin() to avoid SQL injection through job parameters.

    Returns a Spark DataFrame ordered by sys_updated_on ASC.
    """
    where_clauses = []

    if watermark:
        where_clauses.append(f"sys_updated_on > CAST('{watermark}' AS TIMESTAMP)")
    elif MND_CUTOFF_DATE:
        where_clauses.append(f"opened_at >= '{MND_CUTOFF_DATE}'")

    types = ", ".join(f"'{t}'" for t in MND_FILTER_U_TYPE)
    where_clauses.append(f"u_type IN ({types})")

    cats = ", ".join(f"'{c}'" for c in MND_FILTER_U_RESOLUTION_CATEGORY) \
        if MND_FILTER_U_RESOLUTION_CATEGORY else ""
    if cats:
        where_clauses.append(f"u_resolution_category IN ({cats})")

    where_clauses.append("u_serial_number IS NOT NULL")
    where_clauses.append("u_serial_number <> ''")
    where_clauses.append("u_ccap_alarm_name IS NOT NULL")
    proxies = ", ".join(f"'{p}'" for p in MND_NULL_PROXIES) if MND_NULL_PROXIES else ""
    if proxies:
        where_clauses.append(f"u_ccap_alarm_name NOT IN ({proxies})")

    where = "WHERE " + " AND ".join(where_clauses)

    # NOTE: LIMIT is applied AFTER serial-number filter (below) so the cap
    # is not wasted on records that would be filtered out anyway.
    sql = f"SELECT * FROM {MND_SOURCE_TABLE} {where} ORDER BY sys_updated_on ASC"
    log.info(f"Extracting M&D records: {sql[:300]}...")
    sdf = spark.sql(sql)

    if MND_SERIAL_NUMBERS:
        from pyspark.sql.functions import col as _col
        sdf = sdf.filter(_col("u_serial_number").isin(MND_SERIAL_NUMBERS))
        log.info(f"  Applied serial number filter: {len(MND_SERIAL_NUMBERS)} values")

    if MND_MAX_RECORDS and MND_MAX_RECORDS > 0:
        sdf = sdf.limit(MND_MAX_RECORDS)
        log.info(f"  Safety limit: capping extract at {MND_MAX_RECORDS} records")

    initial_count = sdf.count()
    log.info(f"Extracted {initial_count} raw record(s) from {MND_SOURCE_TABLE}")

    # Union retry candidates from failed-records table
    retry_set = read_retry_records()
    if retry_set:
        from pyspark.sql.functions import col as _col2
        # Re-extract those rows from the source, ignoring watermark.
        # u_serial_number guard matches extract_mnd_records — records without
        # a valid ESN cannot be chunked (record_id / chunk_id would be NULL).
        retry_types = ", ".join(f"'{t}'" for t in MND_FILTER_U_TYPE)
        retry_cat_clause = f"AND u_resolution_category IN ({cats})" if cats else ""
        retry_proxy_clause = f"AND u_ccap_alarm_name NOT IN ({proxies})" if proxies else ""
        retry_sdf = (
            spark.sql(
                f"SELECT * FROM {MND_SOURCE_TABLE} "
                f"WHERE u_type IN ({retry_types}) "
                f"  AND u_serial_number IS NOT NULL "
                f"  AND u_serial_number <> '' "
                f"  AND u_ccap_alarm_name IS NOT NULL "
                f"  {retry_cat_clause} "
                f"  {retry_proxy_clause}"
            )
            .filter(_col2("number_").cast("string").isin([str(x) for x in retry_set]))
        )
        retry_count = retry_sdf.count()
        log.info(f"  Retry source: pulled {retry_count} record(s) "
                 f"(of {len(retry_set)} requested) from source table")

        if retry_count > 0:
            # Union, dedup on number_, preserve sort
            sdf = sdf.unionByName(retry_sdf, allowMissingColumns=True)
            from pyspark.sql.window import Window as _W
            from pyspark.sql.functions import row_number as _rn, desc as _desc
            w = _W.partitionBy("number_").orderBy(_desc("sys_updated_on"))
            sdf = (
                sdf.withColumn("_rn", _rn().over(w))
                   .filter("_rn = 1")
                   .drop("_rn")
                   .orderBy("sys_updated_on")
            )

    return sdf

# COMMAND ----------

# ── Preprocess → PII → Chunk → Embed (per micro-batch) ─────────────────────

def preprocess_batch(sdf):
    """Apply preprocessing steps 1, 2, 4, 5, 6, 12 + boilerplate strip.

    Mirrors E3_final.py:Cells 4-13 + Cell 15.  Pure Spark transforms — no
    driver materialisation.
    """
    sdf = apply_null_proxies(sdf, MND_NULL_PROXIES)            # Step 1
    sdf = drop_excluded_fields(sdf, MND_FIELDS_TO_EXCLUDE)     # Step 2
    sdf = add_numeric_clean_columns(sdf)                       # Step 4
    sdf = replace_sentinel_values(sdf)                         # Step 5
    sdf = filter_invalid_dates(sdf)                            # Step 6
    sdf = add_record_origin(sdf)                               # Step 12 part 1
    sdf = select_handoff_fields(sdf, MND_HANDOFF_FIELDS)       # Step 12 part 2
    sdf = clean_boilerplate(                                   # Step 10
        sdf, MND_TEXT_COLS, MND_BOILERPLATE_PHRASES, MND_URL_PATTERN,
    )
    return sdf


def redact_batch(sdf):
    """Apply Presidio + Flair PII redaction on the 7 text columns.

    Bridge: Spark → Pandas (driver) → apply_presidio_to_pdf → Spark.  Uses
    a synthetic `__row_id` to preserve ordering across the boundary.

    Bounded by MND_RECORD_BATCH_SIZE upstream so driver memory is bounded.
    """
    from pyspark.sql.functions import lit as _lit_pii, row_number as _rn_pii
    from pyspark.sql.window import Window as _W_pii

    if not _PRESIDIO_INITIALISED:
        log.warning("Presidio not initialised — skipping PII redaction (DEV ONLY)")
        return sdf

    # Use row_number() over a stable natural key (number_) so that row ordering
    # is deterministic across runs on Databricks Serverless / Spark Connect.
    # monotonically_increasing_id() is non-deterministic on Spark Connect and
    # could assign different integers to the same rows on different executions.
    # Note: sys_updated_on is dropped by select_handoff_fields() in preprocess_batch()
    # before redact_batch() is called, so number_ (always in HANDOFF_FIELDS) is used.
    sdf_with_id = sdf.withColumn(
        "__row_id",
        _rn_pii().over(_W_pii.partitionBy(_lit_pii(0)).orderBy("number_"))
    )
    pandas_df = sdf_with_id.toPandas()

    if pandas_df.empty:
        return sdf

    pandas_df_redacted = apply_presidio_to_pdf(pandas_df, MND_TEXT_COLS, MND_PII_ENTITIES)

    schema = sdf_with_id.schema
    sdf_out = spark.createDataFrame(pandas_df_redacted, schema=schema)
    return sdf_out.orderBy("__row_id").drop("__row_id")


def chunk_and_embed_batch(sdf_redacted):
    """Build merged_free_text → 4-step chunk pipeline → embed → cast meta to STRING.

    Returns (chunk_df, failed_map) where chunk_df is a Spark DataFrame ready
    for MERGE into MND_CHUNK_TABLE, and failed_map is {mnd_case_number: error}.
    """
    sdf_with_text = build_merged_free_text(sdf_redacted, MND_CHUNK_TEXT_FIELDS)

    # Step 1: timestamp-boundary split (Spark) → record_id/chunk_id/chunk_text/tokens
    chunks1 = chunk_by_timestamp_case(
        sdf_with_text, text_col="merged_free_text",
        boundary_pattern=MND_CHUNK_TS_BOUNDARY,
    )
    step1_count = chunks1.count()
    if step1_count == 0:
        log.info("  Chunk step 1: 0 chunks (likely all merged_free_text empty)")
        return None, {}
    log.info(f"  Chunk step 1 (timestamp split): {step1_count} initial chunks")

    # Step 2: merge under MIN_TOKENS
    chunks2 = merge_chunks_by_datetime(chunks1, MND_CHUNK_MIN_TOKENS)
    log.info(f"  Chunk step 2 (merge < {MND_CHUNK_MIN_TOKENS}): {chunks2.count()} chunks")

    # Step 3: split over MAX_TOKENS
    chunks3 = split_large_chunks_python(chunks2, MND_CHUNK_MAX_TOKENS)
    log.info(f"  Chunk step 3 (split > {MND_CHUNK_MAX_TOKENS}): {chunks3.count()} chunks")

    # Step 4: merge tiny backward under TINY_TOKENS
    chunks4 = merge_tiny_chunks_backward(chunks3, MND_CHUNK_TINY_TOKENS)
    log.info(f"  Chunk step 4 (merge < {MND_CHUNK_TINY_TOKENS} backward): "
             f"{chunks4.count()} final chunks")

    # Finalise: deterministic chunk_id, metadata join, SOT names
    chunks_final = finalise_chunks(chunks4, sdf_redacted)

    # Prepend per-case metadata header to chunk_text.
    # Runs after finalise_chunks so chunk_id stays keyed on the body text.
    chunks_final = apply_chunk_prefix(chunks_final, sdf_redacted)

    # ── Embedding ─────────────────────────────────────────────────────────
    # Pull chunks to driver in small bites: collect (chunk_id, chunk_text)
    # for embedding, then join the resulting vectors back via chunk_id.
    chunk_rows = chunks_final.select("chunk_id", "chunk_text", "mnd_case_number").collect()
    n_chunks = len(chunk_rows)
    if n_chunks == 0:
        return None, {}

    log.info(f"  Embedding {n_chunks} chunks in batches of {MND_EMBEDDING_BATCH_SIZE} "
             f"with {MND_EMBEDDING_CONCURRENCY} workers")

    from concurrent.futures import ThreadPoolExecutor, as_completed

    embeddings = {}                # chunk_id -> vector
    failed_map = {}                # mnd_case_number -> error message

    def _embed_one_batch(batch):
        texts = [r["chunk_text"] for r in batch]
        try:
            vectors = embed_texts_batch(
                texts,
                base_url=LITELLM_BASE_URL,
                api_key=LITELLM_API_KEY,
                model=EMBEDDING_MODEL,
                dimension=EMBEDDING_DIMENSION,
                request_path=MND_EMBEDDING_REQUEST_PATH,
                verify_ssl=LLM_VERIFY_SSL,
                max_retries=MND_MAX_RETRIES,
            )
            return batch, vectors, None
        except Exception as exc:    # noqa: BLE001
            return batch, None, f"{type(exc).__name__}: {exc}"

    batches = [
        chunk_rows[i : i + MND_EMBEDDING_BATCH_SIZE]
        for i in range(0, n_chunks, MND_EMBEDDING_BATCH_SIZE)
    ]

    with ThreadPoolExecutor(max_workers=MND_EMBEDDING_CONCURRENCY) as pool:
        futures = {pool.submit(_embed_one_batch, b): b for b in batches}
        for fut in as_completed(futures):
            batch, vectors, err = fut.result()
            if err:
                log.error(f"Embedding batch failed: {err}")
                for r in batch:
                    failed_map.setdefault(str(r["mnd_case_number"]), err)
                continue
            for r, vec in zip(batch, vectors):
                embeddings[r["chunk_id"]] = vec

            # Detect partial API response: if the API returned fewer vectors
            # than chunks sent, zip() silently drops the unmatched tail.
            # Mark those chunks' records as failed so they are retried.
            if len(vectors) < len(batch):
                partial_err = (
                    f"Partial embedding response: API returned {len(vectors)} "
                    f"vector(s) for {len(batch)} chunk(s) in this batch"
                )
                log.error(f"Embedding batch: {partial_err}")
                for r in batch[len(vectors):]:
                    failed_map.setdefault(str(r["mnd_case_number"]), partial_err)

    if not embeddings:
        log.error("  Embedding produced zero successful vectors for this batch")
        return None, failed_map

    log.info(f"  Embedding complete: {len(embeddings)}/{n_chunks} succeeded")

    # Attach vectors via a Spark join.  Build a tiny DF of (chunk_id, embedding).
    from pyspark.sql.types import (
        ArrayType, DoubleType, StringType, StructField, StructType,
    )

    emb_schema = StructType([
        StructField("chunk_id", StringType(), False),
        StructField("embedding", ArrayType(DoubleType()), True),
    ])
    emb_df = spark.createDataFrame(
        [(cid, vec) for cid, vec in embeddings.items()], emb_schema,
    )
    chunks_with_emb = chunks_final.join(emb_df, on="chunk_id", how="inner")

    # Detect any mnd_case_numbers silently dropped by the inner join
    # (their chunks had no embedding vector for any reason).
    # Add them to failed_map so they are retried on the next run.
    dropped_cases = (
        chunks_final.select("mnd_case_number").distinct()
        .join(
            chunks_with_emb.select("mnd_case_number").distinct(),
            on="mnd_case_number",
            how="left_anti",
        )
        .collect()
    )
    if dropped_cases:
        drop_err = "EMBEDDING_DROPPED: all chunks for this record had no embedding vector"
        for r in dropped_cases:
            failed_map.setdefault(str(r["mnd_case_number"]), drop_err)
        log.warning(
            f"  {len(dropped_cases)} mnd_case_number(s) fully dropped by embedding join "
            f"— added to failed_map for retry"
        )

    # ── Cast every metadata column to STRING (VS index requirement) ──────
    # VS rejects `void`/`null` column types.  We force STRING on all
    # non-array, non-timestamp metadata columns so the schema is stable.
    # Also drop `record_id` (working composite key, not in DDL) and ensure
    # the `metadata` column declared in the DDL is present (NULL ok).
    from pyspark.sql.functions import col as _col, current_timestamp as _now, lit as _lit

    chunks_with_emb = chunks_with_emb.drop("record_id")

    # Select only the required columns (schema reduced to match requirements)
    _CHUNK_FINAL_COLS = [
        "chunk_id", "serial_number", "mnd_case_number", "chunk_index",
        "chunk_text", "u_ccap_alarm_name", "u_component",
        "u_resolution_category", "u_major_equipment_association",
        "created_at", "embedding",
    ]
    # Columns that must keep their native type (not cast to STRING).
    _NON_STRING_COLS = {"embedding", "chunk_index", "created_at"}

    chunks_out = chunks_with_emb.select(
        *[
            _col(c)
            if c in _NON_STRING_COLS
            else _col(c).cast("string").alias(c)
            if c in chunks_with_emb.columns
            else _lit(None).cast("string").alias(c)
            for c in _CHUNK_FINAL_COLS
        ]
    ).withColumn("updated_time", _now())

    return chunks_out, failed_map

# COMMAND ----------

# ── Write to Delta + orphan cleanup ─────────────────────────────────────────

def write_chunks_to_delta(chunks_df) -> int:
    """MERGE chunks into MND_CHUNK_TABLE keyed on chunk_id.

    Orphan cleanup: deletes higher-index chunks for any mnd_case_number in
    the batch that no longer exist (case re-chunked into fewer pieces).
    """
    if chunks_df is None:
        log.warning("No chunks to write")
        return 0

    n = chunks_df.count()
    if n == 0:
        log.warning("Chunk DataFrame is empty")
        return 0

    tmp_view = f"_mnd_chunks_staging_{int(time.time())}"
    chunks_df.createOrReplaceTempView(tmp_view)

    spark.sql(f"""
        MERGE INTO {MND_CHUNK_TABLE} AS target
        USING {tmp_view} AS source
        ON target.chunk_id = source.chunk_id
        WHEN MATCHED THEN UPDATE SET
            serial_number                 = source.serial_number,
            mnd_case_number               = source.mnd_case_number,
            chunk_index                   = source.chunk_index,
            chunk_text                    = source.chunk_text,
            u_ccap_alarm_name             = source.u_ccap_alarm_name,
            u_component                   = source.u_component,
            u_resolution_category         = source.u_resolution_category,
            u_major_equipment_association = source.u_major_equipment_association,
            created_at                     = source.created_at,
            embedding                     = source.embedding,
            updated_time                  = source.updated_time
        WHEN NOT MATCHED THEN INSERT (chunk_id, serial_number, mnd_case_number, chunk_index,
            chunk_text, u_ccap_alarm_name, u_component, u_resolution_category,
            u_major_equipment_association, created_at, embedding, updated_time)
        VALUES (source.chunk_id, source.serial_number, source.mnd_case_number, source.chunk_index,
            source.chunk_text, source.u_ccap_alarm_name, source.u_component, source.u_resolution_category,
            source.u_major_equipment_association, source.created_at, source.embedding, source.updated_time)
    """)
    log.info(f"Merged {n} chunks into {MND_CHUNK_TABLE}")

    # ── Orphan cleanup ────────────────────────────────────────────────────────
    # Remove stale chunks for cases in this batch that were not produced by the
    # current chunking run (e.g. a case was re-processed and now has fewer chunks).
    #
    # Uses Spark joins to identify orphan chunk_ids, then deletes by literal list.
    # This avoids subqueries in DELETE which Databricks Serverless rejects with
    # INVALID_NON_DETERMINISTIC_EXPRESSIONS (SQLSTATE 42K0E).
    # Orphan count is typically 0; only non-zero when a case re-chunks smaller.
    try:
        new_case_ids  = chunks_df.select("mnd_case_number").distinct()
        new_chunk_ids = chunks_df.select("chunk_id")
        orphan_ids = (
            spark.table(MND_CHUNK_TABLE)
            .join(new_case_ids, on="mnd_case_number", how="inner")
            .join(new_chunk_ids, on="chunk_id", how="left_anti")
            .select("chunk_id")
            .collect()
        )
        if orphan_ids:
            ids_lit = ", ".join(f"'{r.chunk_id}'" for r in orphan_ids)
            spark.sql(f"DELETE FROM {MND_CHUNK_TABLE} WHERE chunk_id IN ({ids_lit})")
            log.info(f"Orphan cleanup: removed {len(orphan_ids)} stale chunk(s)")
    except Exception as e:
        log.warning(f"Orphan cleanup failed (non-blocking): {e}")
    return n

# COMMAND ----------

# ── VS Index — Ensure Exists + Sync ─────────────────────────────────────────

def ensure_vs_index():
    """Verify VS index exists or create it (Hybrid + managed embedding endpoint).

    Called early so permission/endpoint errors fail before the multi-hour
    PII + chunking phase.
    """
    if not MND_VS_INDEX or not MND_VS_ENDPOINT:
        log.warning("VS index/endpoint not configured — skipping VS index check.  "
                    f"MND_VS_INDEX={MND_VS_INDEX!r}, MND_VS_ENDPOINT={MND_VS_ENDPOINT!r}")
        return

    log.info(f"Ensuring VS index exists: {MND_VS_INDEX} on endpoint {MND_VS_ENDPOINT}")

    ws_url, token = get_dbr_auth()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # 1. Endpoint health
    try:
        ep_url = f"{ws_url}/api/2.0/vector-search/endpoints/{MND_VS_ENDPOINT}"
        ep_req = urllib.request.Request(ep_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(ep_req, context=ctx, timeout=30) as resp:  # noqa: S310
            ep_info = json.loads(resp.read())
        ep_status = ep_info.get("endpoint_status", {}).get("state", "UNKNOWN")
        log.info(f"  VS endpoint '{MND_VS_ENDPOINT}' state: {ep_status}")
        if ep_status != "ONLINE":
            log.warning(f"  VS endpoint NOT ONLINE (state={ep_status})")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        log.error(f"  VS endpoint check failed: HTTP {e.code} — {body}")
        if e.code == 403:
            log.error(f"  → SP likely lacks CAN_USE on endpoint '{MND_VS_ENDPOINT}'")
        raise

    # 2. Index existence
    index_exists = False
    try:
        status = check_vs_index_status(ws_url, token, MND_VS_INDEX)
        idx_status = status.get("status", "UNKNOWN")
        log.info(f"  VS index '{MND_VS_INDEX}' exists — status: {idx_status}")
        index_exists = True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.info(f"  VS index '{MND_VS_INDEX}' does not exist (404) — will create")
        elif e.code == 403:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"  VS index check returned 403 — {body}")
            raise PermissionError(
                f"403 on VS index {MND_VS_INDEX}.  Grant CAN_USE on endpoint "
                f"'{MND_VS_ENDPOINT}'."
            ) from e
        else:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"  VS index check failed: HTTP {e.code} — {body}")
            raise

    # 3. Create if missing — HYBRID with managed embedding endpoint
    if not index_exists:
        create_url = f"{ws_url}/api/2.0/vector-search/indexes"
        create_payload = {
            "name": MND_VS_INDEX,
            "endpoint_name": MND_VS_ENDPOINT,
            "primary_key": "chunk_id",
            "index_type": "DELTA_SYNC",
            "delta_sync_index_spec": {
                "source_table": MND_CHUNK_TABLE,
                "pipeline_type": "TRIGGERED",
                "embedding_vector_columns": [
                    {
                        "name": "embedding",
                        "embedding_dimension": EMBEDDING_DIMENSION,
                        "embedding_model_endpoint_name": MND_VS_EMBEDDING_MODEL_ENDPOINT,
                    }
                ],
            },
        }
        log.info(f"  Creating VS index: {json.dumps(create_payload)}")
        try:
            req = urllib.request.Request(
                create_url,
                data=json.dumps(create_payload).encode(),
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:  # noqa: S310
                resp_body = json.loads(resp.read())
            log.info(f"  VS index created: {resp_body}")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"  VS index creation failed: HTTP {e.code} — {body}")
            raise RuntimeError(
                f"Failed to create VS index '{MND_VS_INDEX}': HTTP {e.code} — {body}"
            ) from e


def sync_vector_search():
    """Trigger VS index sync and poll until complete.  Non-fatal on failure."""
    if not MND_VS_INDEX or not MND_VS_ENDPOINT:
        log.info("VS index/endpoint not configured — skipping sync")
        return

    ws_url, token = get_dbr_auth()
    log.info(f"Triggering VS sync for {MND_VS_INDEX}...")

    try:
        result = trigger_vs_sync(ws_url, token, MND_VS_ENDPOINT, MND_VS_INDEX)
        log.info(f"VS sync triggered: {result}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        log.error(f"VS sync trigger failed: HTTP {e.code} — {body}")
        raise

    _MAX_POLLS = 12
    _POLL_INTERVAL = 30
    for i in range(1, _MAX_POLLS + 1):
        time.sleep(_POLL_INTERVAL)
        try:
            st = check_vs_index_status(ws_url, token, MND_VS_INDEX)
            idx_status = st.get("status", "UNKNOWN")
            log.info(f"  VS sync poll {i}/{_MAX_POLLS}: status={idx_status}")
            if idx_status in ("ONLINE", "ONLINE_NO_PENDING_UPDATE"):
                log.info("VS sync complete")
                return
        except Exception as e:
            log.warning(f"  VS sync poll {i}/{_MAX_POLLS} failed: {e}")
    log.warning(f"VS sync still in progress after {_MAX_POLLS * _POLL_INTERVAL}s")

# COMMAND ----------

# ── Main pipeline ───────────────────────────────────────────────────────────

ensure_spark_session()

log.info("=" * 60)
log.info("M&D Ingestion Pipeline — START")
log.info(f"  Source: {MND_SOURCE_TABLE}")
log.info(f"  Target: {MND_CHUNK_TABLE}")
log.info(f"  VS Index: {MND_VS_INDEX or '(not configured)'}")
log.info(f"  Run log: {MND_RUN_LOG_TABLE or '(disabled)'}")
log.info(f"  Filter: u_type={MND_FILTER_U_TYPE}, "
         f"u_resolution_category={MND_FILTER_U_RESOLUTION_CATEGORY}")
log.info(f"  Cutoff date: {MND_CUTOFF_DATE}")
log.info(f"  Serial filter: {MND_SERIAL_NUMBERS or 'all'}")
log.info(f"  Record batch size: {MND_RECORD_BATCH_SIZE}")
log.info(f"  Chunking: min={MND_CHUNK_MIN_TOKENS}, max={MND_CHUNK_MAX_TOKENS}, "
         f"tiny={MND_CHUNK_TINY_TOKENS}")
log.info(f"  FORCE_RESET: {FORCE_RESET}")
log.info("=" * 60)

# ── Optional: Backfill audit mode ──────────────────────────────────────────
# When MND_BACKFILL_AUDIT=true, find source records below the current
# watermark that have no chunks in MND_CHUNK_TABLE, seed them into
# MND_FAILED_RECORDS_TABLE with attempts=0, and exit.  Three exclusive
# paths: A) explicit IDs, C) date range, B) incremental gap scan.

if MND_BACKFILL_AUDIT:
    log.info("=" * 60)
    log.info("BACKFILL AUDIT MODE")
    log.info("=" * 60)

    if not MND_FAILED_RECORDS_TABLE:
        raise RuntimeError(
            "MND_BACKFILL_AUDIT=true but MND_FAILED_RECORDS_TABLE not configured"
        )
    if not MND_RUN_LOG_TABLE:
        raise RuntimeError(
            "MND_BACKFILL_AUDIT=true but MND_RUN_LOG_TABLE not configured"
        )

    ensure_spark_session()

    audit_run_id = f"backfill-audit-{int(time.time())}"

    from pyspark.sql.functions import lit, current_timestamp
    from pyspark.sql.types import StructType, StructField, StringType, TimestampType

    # ── Path A: explicit record-ID override ──────────────────────────────
    if MND_BACKFILL_RECORD_IDS:
        log.info(f"  Override mode: seeding {len(MND_BACKFILL_RECORD_IDS)} explicit record IDs")

        seed_schema = StructType([
            StructField("mnd_case_number", StringType(), False),
            StructField("sys_updated_on", TimestampType(), True),
        ])
        seed_rows = [(str(rid), None) for rid in MND_BACKFILL_RECORD_IDS]
        seed_df = (
            spark.createDataFrame(seed_rows, seed_schema)
            .withColumn("first_failed_at", current_timestamp())
            .withColumn("last_attempted_at", lit(None).cast("timestamp"))
            .withColumn("attempts", lit(0))
            .withColumn("last_error", lit("BACKFILL_AUDIT_OVERRIDE: explicit record id"))
            .withColumn("last_run_id", lit(audit_run_id))
        )
        tmp_view = f"_mnd_backfill_seed_{int(time.time())}"
        seed_df.createOrReplaceTempView(tmp_view)
        spark.sql(f"""
            MERGE INTO {MND_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.mnd_case_number = source.mnd_case_number
            WHEN NOT MATCHED THEN INSERT *
        """)
        log.info(f"BACKFILL AUDIT (override) — seeded {len(MND_BACKFILL_RECORD_IDS)} record(s)")
        dbutils.notebook.exit(f"BACKFILL_OVERRIDE_SEEDED:{len(MND_BACKFILL_RECORD_IDS)}")  # noqa: F821

    # ── Path C: date-range re-ingestion ──────────────────────────────────
    if MND_BACKFILL_DATE_FROM and MND_BACKFILL_DATE_TO:
        log.info(f"  Date-range mode: {MND_BACKFILL_DATE_FROM} → {MND_BACKFILL_DATE_TO}")

        _has_text_expr = " OR ".join(
            f"(TRIM(COALESCE(CAST({f} AS STRING), '')) <> '')"
            for f in MND_CHUNK_TEXT_FIELDS
        )

        range_types = ", ".join(f"'{t}'" for t in MND_FILTER_U_TYPE)
        range_df = spark.sql(f"""
            SELECT
                CAST(number_ AS STRING) AS mnd_case_number,
                MIN(sys_updated_on)    AS sys_updated_on
            FROM {MND_SOURCE_TABLE}
            WHERE sys_updated_on IS NOT NULL
              AND sys_updated_on >= CAST('{MND_BACKFILL_DATE_FROM}' AS TIMESTAMP)
              AND sys_updated_on <= CAST('{MND_BACKFILL_DATE_TO}' AS TIMESTAMP)
              AND u_type IN ({range_types})
              AND u_serial_number IS NOT NULL
              AND u_serial_number <> ''
              AND ({_has_text_expr})
            GROUP BY CAST(number_ AS STRING)
        """)

        range_count = range_df.count()
        log.info(f"  Records in date range: {range_count}")

        if range_count == 0:
            dbutils.notebook.exit("BACKFILL_RANGE_EMPTY")  # noqa: F821

        seed_df = (
            range_df
            .withColumn("first_failed_at", current_timestamp())
            .withColumn("last_attempted_at", lit(None).cast("timestamp"))
            .withColumn("attempts", lit(0))
            .withColumn("last_error",
                        lit(f"BACKFILL_DATE_RANGE: {MND_BACKFILL_DATE_FROM} to {MND_BACKFILL_DATE_TO}"))
            .withColumn("last_run_id", lit(audit_run_id))
            .select("mnd_case_number", "sys_updated_on", "first_failed_at",
                    "last_attempted_at", "attempts", "last_error", "last_run_id")
        )

        tmp_view = f"_mnd_backfill_range_{int(time.time())}"
        seed_df.createOrReplaceTempView(tmp_view)
        spark.sql(f"""
            MERGE INTO {MND_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.mnd_case_number = source.mnd_case_number
            WHEN MATCHED THEN UPDATE SET
                attempts = 0,
                last_error = source.last_error,
                last_run_id = source.last_run_id,
                last_attempted_at = NULL
            WHEN NOT MATCHED THEN INSERT *
        """)
        log.info(f"BACKFILL AUDIT (date-range) — seeded {range_count} record(s)")
        dbutils.notebook.exit(f"BACKFILL_RANGE_SEEDED:{range_count}")  # noqa: F821

    # ── Path B: full scan below the current watermark ceiling ───────────
    _has_text_expr = " OR ".join(
        f"(TRIM(COALESCE(CAST({f} AS STRING), '')) <> '')"
        for f in MND_CHUNK_TEXT_FIELDS
    )

    ceiling_row = spark.sql(f"""
        SELECT CAST(MAX(watermark_ts) AS STRING) AS ceiling_wm
        FROM {MND_RUN_LOG_TABLE}
        WHERE status IN ('completed', 'in_progress') AND watermark_ts IS NOT NULL
    """).first()
    audit_ceiling = ceiling_row.ceiling_wm if ceiling_row else None

    if not audit_ceiling:
        log.warning("No ingestion watermark found yet — skipping backfill audit for this run")
        missing_df = None
        missing_count = 0
    else:
        log.info(f"  Audit ceiling: {audit_ceiling} (no floor — full scan below ceiling every run)")

        ceiling_clause = f"AND sys_updated_on <= CAST('{audit_ceiling}' AS TIMESTAMP)"
        cutoff_clause = f"AND opened_at >= '{MND_CUTOFF_DATE}'" if MND_CUTOFF_DATE else ""
        cats = ", ".join(f"'{c}'" for c in MND_FILTER_U_RESOLUTION_CATEGORY) \
            if MND_FILTER_U_RESOLUTION_CATEGORY else ""
        cat_clause = f"AND u_resolution_category IN ({cats})" if cats else ""
        proxies = ", ".join(f"'{p}'" for p in MND_NULL_PROXIES) if MND_NULL_PROXIES else ""
        proxy_clause = f"AND u_ccap_alarm_name NOT IN ({proxies})" if proxies else ""
        audit_types = ", ".join(f"'{t}'" for t in MND_FILTER_U_TYPE)

        missing_df = spark.sql(f"""
            WITH src AS (
                SELECT
                    CAST(number_ AS STRING) AS mnd_case_number,
                    MIN(sys_updated_on)    AS sys_updated_on
                FROM {MND_SOURCE_TABLE}
                WHERE sys_updated_on IS NOT NULL
                  {ceiling_clause}
                  AND u_type IN ({audit_types})
                  AND u_serial_number IS NOT NULL
                  AND u_serial_number <> ''
                  {cat_clause}
                  AND u_ccap_alarm_name IS NOT NULL
                  {proxy_clause}
                  AND ({_has_text_expr})
                  {cutoff_clause}
                GROUP BY CAST(number_ AS STRING)
            ),
            chunked AS (
                SELECT DISTINCT mnd_case_number
                FROM {MND_CHUNK_TABLE}
                WHERE mnd_case_number IS NOT NULL
            )
            SELECT s.mnd_case_number, s.sys_updated_on
            FROM src s
            LEFT ANTI JOIN chunked c ON s.mnd_case_number = c.mnd_case_number
        """)

        # Cap seeding per run — oldest-first so multi-run backfills make
        # steady forward progress instead of an arbitrary subset each time.
        if MND_MAX_RECORDS and MND_MAX_RECORDS > 0:
            missing_df = missing_df.orderBy("sys_updated_on").limit(MND_MAX_RECORDS)
            log.info(f"  Safety limit: capping backfill audit at {MND_MAX_RECORDS} records")

        missing_count = missing_df.count()

    if missing_df is not None:
        log.info(f"  Missing records (below ceiling, no chunks): {missing_count}")

        if missing_count == 0:
            log.info("BACKFILL AUDIT — no gaps found")

        seed_df = (
            missing_df
            .withColumn("first_failed_at", current_timestamp())
            .withColumn("last_attempted_at", lit(None).cast("timestamp"))
            .withColumn("attempts", lit(0))
            .withColumn("last_error", lit("BACKFILL_AUDIT: source record had no chunks"))
            .withColumn("last_run_id", lit(audit_run_id))
            .select("mnd_case_number", "sys_updated_on", "first_failed_at",
                    "last_attempted_at", "attempts", "last_error", "last_run_id")
        )

        tmp_view = f"_mnd_backfill_seed_{int(time.time())}"
        seed_df.createOrReplaceTempView(tmp_view)
        spark.sql(f"""
            MERGE INTO {MND_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.mnd_case_number = source.mnd_case_number
            WHEN NOT MATCHED THEN INSERT *
        """)

        log.info(f"BACKFILL AUDIT — seeded {missing_count} record(s) into {MND_FAILED_RECORDS_TABLE}")
    # falls through into the normal ingestion run below — no exit here,
    # so seeded retries are picked up and processed in this same execution.

# COMMAND ----------

# ── Normal ingestion run ───────────────────────────────────────────────────

cleanup_stale_runs()

# Verify/create the VS index up front — fail early on permission errors
try:
    ensure_vs_index()
except Exception as vs_init_err:
    log.error(f"VS index setup failed: {vs_init_err}")
    log.error("Pipeline will continue — VS sync at end will likely fail.")

run_id = str(uuid.uuid4())
start_time = time.time()
run_started_at = datetime.now(timezone.utc)
rows_written = 0
total_records = 0
new_watermark = None
all_failed_records = set()

# Initialise Presidio + Flair ONCE before the batch loop (heavy: ~1.5GB model)
log.info("Initialising Presidio + Flair (this may take 30-90s on first run)...")
init_presidio(
    system_emails=MND_SYSTEM_EMAILS,
    pii_entities=MND_PII_ENTITIES,
    flair_model=MND_FLAIR_MODEL,
    sso_pattern=MND_SSO_PATTERN,
)
log.info("Presidio + Flair initialised")

# ── Presidio synthetic smoke test (mirrors E3_final.py sample test) ─────────
# Runs a 1-row synthetic PII test immediately after init_presidio() to catch
# silent Presidio/Flair failures before any real data is processed.
# E3_final.py verifies: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, SSO_ID are all
# redacted on known fake PII. Raises RuntimeError if any entity is missed.
log.info("Running Presidio synthetic smoke test...")
try:
    import pandas as _pd
    _smoke_input = _pd.DataFrame([{
        "short_description" : "Issue reported by John Smith",
        "description"       : "Email john.smith@ge.com Call 987654321 SSO 123456789",
        "u_resolve_notes"   : "Handled by Ben Yoo",
        "close_notes"       : "Resolved by Sarah Connor",
        "comments"          : "Contact gepowerpac@service-now.com SSO 123456789",
        "work_notes"        : "Phone (678) 844-4126",
        "comments_and_work_notes": "Case logged by Michael Brown.",
    }])
    _smoke_output = apply_presidio_to_pdf(
        _smoke_input, MND_TEXT_COLS, MND_PII_ENTITIES
    )
    _combined = " ".join(
        str(_smoke_output.iloc[0][c]) for c in MND_TEXT_COLS
        if c in _smoke_output.columns
    )
    _missing = [
        entity for entity in MND_PII_ENTITIES
        if f"[REDACTED_{entity}]" not in _combined
    ]
    if _missing:
        raise RuntimeError(
            f"Presidio smoke test FAILED — entities not redacted: {_missing}.\n"
            f"  Output sample: {_combined[:300]}"
        )
    log.info(f"Presidio smoke test PASSED — all {len(MND_PII_ENTITIES)} "
             f"entities redacted: {MND_PII_ENTITIES}")
except RuntimeError:
    raise
except Exception as _smoke_err:
    raise RuntimeError(
        f"Presidio smoke test raised unexpected error: {_smoke_err}"
    ) from _smoke_err

# On FORCE_RESET, clear the failed-records table
if FORCE_RESET and MND_FAILED_RECORDS_TABLE:
    try:
        spark.sql(f"DELETE FROM {MND_FAILED_RECORDS_TABLE}")
        log.info(f"FORCE_RESET: cleared {MND_FAILED_RECORDS_TABLE}")
    except Exception as e:
        log.warning(f"FORCE_RESET: could not clear failed-records table: {e}")

write_run_log(run_id, run_started_at, "in_progress", 0, 0, None)

try:
    watermark = get_last_watermark()

    # Detect records that landed in the preprocessed table in a prior run but
    # never made it to the chunk table (and were not logged as failures).
    # Seeding them here ensures read_retry_records() inside extract_mnd_records()
    # picks them up on this run — before the watermark filter would skip them.
    if not FORCE_RESET:
        seed_preprocessed_gaps()

    sdf = extract_mnd_records(watermark=watermark)
    total_records = sdf.count()

    # ── ESN Validation (mirrors E3_final.py Cells 2, 3, 4, 5) ──────────────
    # 1. Duplicate check on MND_SERIAL_NUMBERS (E3 Cell 2)
    # 2. Per-ESN record count + distinct alarm count + pass/fail (E3 Cell 3)
    # 3. Removed ESNs report — ESNs with 0 filtered records (E3 Cell 5)
    # Non-blocking: logs findings but never stops the pipeline.
    try:
        from pyspark.sql import functions as _F

        sep = "─" * 70
        log.info(sep)
        log.info("ESN VALIDATION (E3_final.py parity — Cells 2/3/4/5)")
        log.info(sep)

        # ── 1. Duplicate check in MND_SERIAL_NUMBERS ─────────────────────
        if MND_SERIAL_NUMBERS:
            seen_esns = set()
            dup_esns  = []
            for _esn in MND_SERIAL_NUMBERS:
                if _esn in seen_esns:
                    dup_esns.append(_esn)
                seen_esns.add(_esn)
            if dup_esns:
                log.warning(f"  DUPLICATES found in MND_SERIAL_NUMBERS "
                            f"({len(set(dup_esns))} ESN(s)):")
                for _d in sorted(set(dup_esns)):
                    log.warning(f"    '{_d}' appears "
                                f"{MND_SERIAL_NUMBERS.count(_d)} times")
            else:
                log.info(f"  No duplicates in MND_SERIAL_NUMBERS "
                         f"({len(MND_SERIAL_NUMBERS)} ESNs)")
        else:
            log.info("  MND_SERIAL_NUMBERS not set — processing all ESNs "
                     "(no duplicate check needed)")

        # ── 2. Per-ESN validation report ─────────────────────────────────
        # Loads source directly (not watermarked sdf) so counts reflect
        # the full population — same as E3 Cell 3 which queries df_mnd.
        _src_sdf = spark.table(MND_SOURCE_TABLE)

        # Determine which ESNs to check
        _check_esns = (
            list(set(MND_SERIAL_NUMBERS))
            if MND_SERIAL_NUMBERS
            else [
                r["u_serial_number"]
                for r in _src_sdf
                .select("u_serial_number")
                .distinct()
                .limit(50)          # cap to avoid logging thousands of ESNs
                .collect()
                if r["u_serial_number"]
            ]
        )

        log.info(f"  Checking {len(_check_esns)} ESN(s):")
        log.info(f"  {'ESN':<15} {'Total':>8} {'Filtered':>10} "
                 f"{'Distinct Alarms':>16} {'Status':>8}")
        log.info("  " + "─" * 62)

        _esns_passing  = []
        _esns_failing  = []
        _null_proxies_filter = MND_NULL_PROXIES or []

        for _esn in sorted(_check_esns):

            _total = _src_sdf.filter(
                _F.col("u_serial_number") == _esn
            ).count()

            _filtered = _src_sdf.filter(
                (_F.col("u_serial_number") == _esn) &
                (_F.col("u_type").isin(MND_FILTER_U_TYPE)) &
                (_F.col("u_resolution_category").isin(
                    MND_FILTER_U_RESOLUTION_CATEGORY)) &
                _F.col("u_ccap_alarm_name").isNotNull() &
                (~_F.col("u_ccap_alarm_name").isin(_null_proxies_filter))
            ).count()

            _distinct_alarms = _src_sdf.filter(
                (_F.col("u_serial_number") == _esn) &
                _F.col("u_ccap_alarm_name").isNotNull() &
                (~_F.col("u_ccap_alarm_name").isin(_null_proxies_filter))
            ).select("u_ccap_alarm_name").distinct().count()

            _status = "PASS" if _filtered > 0 else "FAIL"

            if _filtered > 0:
                _esns_passing.append(_esn)
            else:
                _esns_failing.append(_esn)

            log.info(f"  {_esn:<15} {_total:>8,} {_filtered:>10,} "
                     f"{_distinct_alarms:>16,} {_status:>8}")

        # ── 3. Removed ESNs summary (E3 Cell 5) ─────────────────────────
        log.info(sep)
        log.info(f"  ESN FILTER SUMMARY")
        log.info(f"  Input ESNs checked      : {len(_check_esns)}")
        log.info(f"  Passing (filtered > 0)  : {len(_esns_passing)}")
        log.info(f"  Removed (no records)    : {len(_esns_failing)}")

        if _esns_failing:
            log.warning("  Removed ESNs "
                        "(no records matching u_type / res_cat filters):")
            for _f in sorted(_esns_failing):
                log.warning(f"    '{_f}' → not matching "
                            f"u_type/resolution_category filters")
        else:
            log.info("  All ESNs passed filters — none removed")

        log.info(sep)

    except Exception as _esn_val_err:
        log.warning(f"ESN validation skipped (non-blocking): {_esn_val_err}")

    # ── End ESN Validation ───────────────────────────────────────────────

    if total_records == 0:
        log.info("No records to process — pipeline complete")
        write_run_log(run_id, run_started_at, "completed", 0, 0, watermark)
        dbutils.notebook.exit("NO_DATA")  # noqa: F821

    log.info(f"Total records to process: {total_records}")

    # ── Micro-batch loop ─────────────────────────────────────────────────
    # Spark DataFrames don't slice well; we attach a row_number, then filter
    # ranges per batch.  This keeps the source query lazy (no full pull
    # into the driver) while still bounding each batch's PII Pandas bridge.
    from pyspark.sql.functions import lit, row_number
    from pyspark.sql.window import Window

    w_seq = Window.partitionBy(lit(0)).orderBy("sys_updated_on", "number_")
    sdf_with_seq = sdf.withColumn("_seq", row_number().over(w_seq))

    batch_size = MND_RECORD_BATCH_SIZE if MND_RECORD_BATCH_SIZE > 0 else total_records
    n_batches = (total_records + batch_size - 1) // batch_size
    log.info(f"Micro-batching: {total_records} records in {n_batches} batch(es) "
             f"of up to {batch_size} records each")

    for batch_num in range(1, n_batches + 1):
        seq_lo = (batch_num - 1) * batch_size + 1
        seq_hi = batch_num * batch_size

        batch_sdf = sdf_with_seq.filter(
            (sdf_with_seq["_seq"] >= seq_lo) & (sdf_with_seq["_seq"] <= seq_hi)
        ).drop("_seq")

        actual_n = batch_sdf.count()
        log.info(f"  Batch {batch_num}/{n_batches}: rows {seq_lo}–{seq_lo + actual_n - 1} "
                 f"({actual_n} records)")
        if actual_n == 0:
            continue

        # Track which records were attempted (for retry-clearing)
        attempted_rows = batch_sdf.select("number_").collect()
        batch_attempted = {str(r["number_"]) for r in attempted_rows if r["number_"]}

        # Capture sys_updated_on lookup for failure rows
        sut_rows = batch_sdf.select("number_", "sys_updated_on").collect()
        sut_lookup = {str(r["number_"]): r["sys_updated_on"] for r in sut_rows}

        # 1. Preprocessing (Step 1, 2, 4, 5, 6, 12 + boilerplate)
        log.info(f"  Batch {batch_num}: step 1 — preprocessing started")
        _t1 = time.time()
        try:
            batch_pre = preprocess_batch(batch_sdf)
            log.info(f"  Batch {batch_num}: step 1 — preprocessing complete ({time.time()-_t1:.1f}s)")
        except Exception as e:
            log.error(f"  Batch {batch_num}: preprocessing failed — {e}")
            failure_rows = [(c, sut_lookup.get(c), str(e)) for c in batch_attempted]
            write_failed_records(failure_rows, run_id)
            all_failed_records |= batch_attempted
            continue

        # 2. PII redaction (Presidio + Flair on the 7 text columns)
        log.info(f"  Batch {batch_num}: step 2 — PII redaction started (Presidio + Flair)")
        _t2 = time.time()
        try:
            batch_redacted = redact_batch(batch_pre)
            log.info(f"  Batch {batch_num}: step 2 — PII redaction complete ({time.time()-_t2:.1f}s)")
        except Exception as e:
            log.error(f"  Batch {batch_num}: PII redaction failed — {e}")
            failure_rows = [(c, sut_lookup.get(c), str(e)) for c in batch_attempted]
            write_failed_records(failure_rows, run_id)
            all_failed_records |= batch_attempted
            continue

        # 2b. Write PII-redacted record-level data to preprocessed table
        # Mirrors E3_final.py saving df_presidio → mnd_presidio_cleaned (hard write).
        # BLOCKING: if this write fails the batch fails and records go to
        # mnd_failed_records for retry — same behaviour as E3_final.py.
        if MND_PREPROCESSED_TABLE:
            try:
                from pyspark.sql.functions import col as _pcol
                _PREPROCESSED_COLS = [
                    "number_", "active", "assignment_group", "close_notes",
                    "closed_at", "comments_and_work_notes", "description",
                    "opened_at", "priority", "short_description", "sys_created_on",
                    "sys_mod_count_clean", "u_ccap_alarm_name", "u_component",
                    "u_equipment_name", "u_immediate_response_needed",
                    "u_load_at_trip_event_mw_clean", "u_potential_safety_issue",
                    "u_resolution_category", "u_resolution_date", "u_resolve_notes",
                    "u_section", "u_serial_number", "u_site_customer_name",
                    "u_site_station_name", "u_speed_at_trip_event_clean",
                    "u_status", "u_type", "record_origin",
                    "u_major_equipment_association",
                ]
                _avail = [c for c in _PREPROCESSED_COLS if c in batch_redacted.columns]
                _pre_df = batch_redacted.select(*_avail)
                # Deduplicate on number_ — MERGE key must be unique in source.
                # Source view may have duplicate number_ rows; keep most recent
                # sys_updated_on (same dedup strategy as extract_mnd_records).
                if "sys_updated_on" in _pre_df.columns:
                    from pyspark.sql.window import Window as _Wpre
                    from pyspark.sql.functions import row_number as _rnpre, desc as _descpre
                    _wpre = _Wpre.partitionBy("number_").orderBy(_descpre("sys_updated_on"))
                    _pre_df = (
                        _pre_df
                        .withColumn("_pre_rn", _rnpre().over(_wpre))
                        .filter("_pre_rn = 1")
                        .drop("_pre_rn")
                    )
                else:
                    _pre_df = _pre_df.dropDuplicates(["number_"])
                # Rename _clean columns to SOT names (matching Excel schema)
                _rename = {
                    "sys_mod_count_clean"          : "sys_mod_count",
                    "u_load_at_trip_event_mw_clean": "u_load_at_trip_event_mw_",
                    "u_speed_at_trip_event_clean"  : "u_speed_at_trip_event",
                }
                for _old, _new in _rename.items():
                    if _old in _pre_df.columns:
                        _pre_df = _pre_df.withColumnRenamed(_old, _new)
                # Add NULL for any columns absent from source (e.g. u_major_equipment_association
                # not present in vgpd.qlt_std_views.u_mandd).
                # Required so MERGE UPDATE SET * resolves all target columns.
                _final_cols = [_rename.get(c, c) for c in _PREPROCESSED_COLS]
                from pyspark.sql.functions import lit as _lit_pre, current_timestamp as _now_pre
                for _missing_col in _final_cols:
                    if _missing_col not in _pre_df.columns:
                        _pre_df = _pre_df.withColumn(_missing_col, _lit_pre(None).cast("string"))
                        log.info(f"  {_missing_col} not in source — added as NULL")
                _pre_df = _pre_df.withColumn("updated_time", _now_pre())
                _pre_df = _pre_df.withColumn("created_at", _now_pre())
                _pre_row_count = _pre_df.count()
                _pre_tmp = f"_mnd_preprocessed_staging_{int(time.time())}"
                _pre_df.createOrReplaceTempView(_pre_tmp)
                spark.sql(f"""
                    MERGE INTO {MND_PREPROCESSED_TABLE} AS target
                    USING {_pre_tmp} AS source
                    ON target.number_ = source.number_
                    WHEN MATCHED THEN UPDATE SET
                        active = source.active,
                        assignment_group = source.assignment_group,
                        close_notes = source.close_notes,
                        closed_at = source.closed_at,
                        comments_and_work_notes = source.comments_and_work_notes,
                        description = source.description,
                        opened_at = source.opened_at,
                        priority = source.priority,
                        short_description = source.short_description,
                        sys_created_on = source.sys_created_on,
                        sys_mod_count = source.sys_mod_count,
                        u_ccap_alarm_name = source.u_ccap_alarm_name,
                        u_component = source.u_component,
                        u_equipment_name = source.u_equipment_name,
                        u_immediate_response_needed = source.u_immediate_response_needed,
                        u_load_at_trip_event_mw_ = source.u_load_at_trip_event_mw_,
                        u_potential_safety_issue = source.u_potential_safety_issue,
                        u_resolution_category = source.u_resolution_category,
                        u_resolution_date = source.u_resolution_date,
                        u_resolve_notes = source.u_resolve_notes,
                        u_section = source.u_section,
                        u_serial_number = source.u_serial_number,
                        u_site_customer_name = source.u_site_customer_name,
                        u_site_station_name = source.u_site_station_name,
                        u_speed_at_trip_event = source.u_speed_at_trip_event,
                        u_status = source.u_status,
                        u_type = source.u_type,
                        record_origin = source.record_origin,
                        u_major_equipment_association = source.u_major_equipment_association,
                        updated_time = source.updated_time
                    WHEN NOT MATCHED THEN INSERT *
                """)
                log.info(f"  Batch {batch_num}: wrote {_pre_row_count} rows to {MND_PREPROCESSED_TABLE}")
            except Exception as _pre_err:
                log.error(f"  Batch {batch_num}: preprocessed table write failed — {_pre_err}")
                failure_rows = [(c, sut_lookup.get(c), str(_pre_err)) for c in batch_attempted]
                write_failed_records(failure_rows, run_id)
                all_failed_records |= batch_attempted
                continue

        # 3. Chunk + embed
        log.info(f"  Batch {batch_num}: step 3 — chunk + embed started")
        _t3 = time.time()
        try:
            chunks_df, failed_map = chunk_and_embed_batch(batch_redacted)
            log.info(f"  Batch {batch_num}: step 3 — chunk + embed complete ({time.time()-_t3:.1f}s)")
        except Exception as e:
            log.error(f"  Batch {batch_num}: chunk/embed failed — {e}")
            failure_rows = [(c, sut_lookup.get(c), str(e)) for c in batch_attempted]
            write_failed_records(failure_rows, run_id)
            all_failed_records |= batch_attempted
            continue

        if failed_map:
            failure_rows = [
                (c, sut_lookup.get(c), err) for c, err in failed_map.items()
            ]
            write_failed_records(failure_rows, run_id)
            all_failed_records |= set(failed_map.keys())

        if chunks_df is None:
            log.warning(f"  Batch {batch_num}: no embeddable chunks — skipping write")
            continue

        # 4. Write to Delta + orphan cleanup
        log.info(f"  Batch {batch_num}: step 4 — writing chunks to Delta")
        _t4 = time.time()
        ensure_spark_session()
        batch_written = write_chunks_to_delta(chunks_df)
        rows_written += batch_written
        log.info(f"  Batch {batch_num}: step 4 — Delta write complete ({time.time()-_t4:.1f}s)")

        # 5. Clear succeeded retries
        succeeded_in_batch = batch_attempted - set(failed_map.keys())
        if succeeded_in_batch:
            clear_succeeded_retries(succeeded_in_batch)

        # 6. Advance watermark to the highest sys_updated_on in this batch.
        # IMPORTANT: exclude retry records (pulled from mnd_failed_records with
        # old sys_updated_on) from watermark calculation — otherwise a retry-only
        # run would roll the watermark back to the retry records' original date,
        # causing the next incremental run to re-extract years of data.
        # Only records strictly newer than the incoming watermark are eligible.
        from pyspark.sql.functions import col as _col_wm, lit as _lit_wm
        _wm_eligible_sdf = (
            batch_sdf.filter(
                _col_wm("sys_updated_on").cast("timestamp") > _lit_wm(watermark).cast("timestamp")
            ) if watermark else batch_sdf
        )
        wm_row = _wm_eligible_sdf.agg({"sys_updated_on": "max"}).first()
        batch_wm = str(wm_row[0]) if wm_row and wm_row[0] is not None else None
        if batch_wm and (new_watermark is None or batch_wm > new_watermark):
            new_watermark = batch_wm
            log.info(f"  Batch {batch_num}: watermark advanced to {new_watermark}")

        # 7. Checkpoint after every batch
        write_run_log(run_id, run_started_at, "in_progress",
                      total_records, rows_written, new_watermark)

    if rows_written == 0 and not all_failed_records:
        log.info("No chunks produced across all batches — pipeline complete")
        write_run_log(run_id, run_started_at, "completed", total_records, 0, watermark)
        dbutils.notebook.exit("NO_CHUNKS")  # noqa: F821

    if rows_written == 0 and all_failed_records:
        log.error("All embeddings failed across all batches — pipeline aborting")
        write_run_log(run_id, run_started_at, "failed", total_records, 0, watermark)
        raise RuntimeError("All embeddings failed")

    if not new_watermark:
        new_watermark = watermark

    # ── MND_MAX_RECORDS cap: protect watermark boundary ───────────────────
    # When MND_MAX_RECORDS is active and the extract was capped at exactly that
    # limit, some records at the final sys_updated_on timestamp may have been
    # excluded by the LIMIT (e.g. 9,000 records share the same timestamp but
    # only 4,000 fit within the cap).  Advancing the watermark to
    # MAX(sys_updated_on) of the capped batch would cause the next incremental
    # run's `sys_updated_on > watermark` filter to silently skip those excluded
    # records.
    # Safe approach: roll back to the second-to-last distinct sys_updated_on
    # so all records at the boundary timestamp are re-queried next run.
    # Already-processed records are handled idempotently by MERGE.
    if MND_MAX_RECORDS and MND_MAX_RECORDS > 0 and total_records >= MND_MAX_RECORDS:
        try:
            distinct_ts = (
                sdf_with_seq
                .select("sys_updated_on")
                .where("sys_updated_on IS NOT NULL")
                .distinct()
                .orderBy("sys_updated_on", ascending=False)
                .limit(2)
                .collect()
            )
            if len(distinct_ts) >= 2:
                safe_wm = str(distinct_ts[1][0])
                log.warning(
                    f"MND_MAX_RECORDS cap ({MND_MAX_RECORDS}) reached "
                    f"(total_records={total_records}) — rolling watermark back "
                    f"from {new_watermark!r} to second-to-last distinct "
                    f"sys_updated_on ({safe_wm!r}) to prevent boundary-record loss"
                )
                new_watermark = safe_wm
            else:
                log.warning(
                    f"MND_MAX_RECORDS cap ({MND_MAX_RECORDS}) reached with only one "
                    f"distinct sys_updated_on in batch — watermark NOT advanced "
                    f"(preserving {watermark!r})"
                )
                new_watermark = watermark
        except Exception as _wm_cap_err:
            log.warning(
                f"MND_MAX_RECORDS watermark-cap adjustment failed ({_wm_cap_err}) "
                f"— preserving incoming watermark {watermark!r} as safe fallback"
            )
            new_watermark = watermark

    # ── ESN-scoped run: never advance the global watermark ────────────────
    # The watermark semantically means "all records across the ENTIRE dataset
    # up to this timestamp have been fully processed."  An ESN-scoped run only
    # processes one ESN and cannot make that guarantee, so we preserve the
    # incoming watermark unchanged.  The next full incremental run will still
    # pick up every record since the last full-run watermark.
    if MND_SERIAL_NUMBERS:
        log.info(
            f"ESN-scoped run — watermark NOT advanced "
            f"(preserving {watermark!r} to protect full-load coverage)"
        )
        new_watermark = watermark

    # VS Sync — best-effort
    try:
        sync_vector_search()
    except Exception as vs_err:
        log.error(f"Vector Search sync failed (non-fatal): {vs_err}")
        log.warning("Delta data was written successfully — VS can be synced manually next run")

    write_run_log(run_id, run_started_at, "completed",
                  total_records, rows_written, new_watermark)

except Exception as exc:
    log.error(f"Pipeline failed: {exc}")
    try:
        write_run_log(run_id, run_started_at, "failed",
                      total_records, rows_written,
                      new_watermark if new_watermark else watermark if "watermark" in dir() else None)
    except Exception as log_err:
        log.warning(f"Failed to write run log on error path: {log_err}")
    raise

elapsed = time.time() - start_time
log.info("=" * 60)
log.info(f"M&D Ingestion Pipeline — DONE in {elapsed:.1f}s")
log.info(f"  Records: {total_records}, Chunks written: {rows_written}, "
         f"Failed records: {len(all_failed_records)}")
log.info("=" * 60)

# COMMAND ----------

dbutils.notebook.exit(json.dumps({  # noqa: F821
    "records": total_records,
    "rows_written": rows_written,
    "failed_records": len(all_failed_records),
    "watermark": new_watermark,
    "elapsed_seconds": round(elapsed, 1),
}))
