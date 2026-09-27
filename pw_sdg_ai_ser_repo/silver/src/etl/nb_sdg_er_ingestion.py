# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_er_ingestion — Engineering Report (ER) Ingestion Pipeline
#
# Single-notebook pipeline: Extract → Chunk → Embed → Write → VS Sync
#
# Reads from the ER source table, combines 13 text fields per record, chunks
# via sliding window, embeds via LiteLLM, writes to Delta, and syncs to
# Vector Search.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../common/er_config

# COMMAND ----------

import hashlib
import json
import logging
import ssl
import time
import urllib.request
import uuid
from datetime import datetime, timezone

import pandas as pd

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("er.ingestion")

# COMMAND ----------
# ── Preflight: validate config + test embedding API before heavy work ──────────
# Runs a single-string embedding call to catch gateway/auth/routing issues
# immediately — before extraction and chunking (which take several minutes).

def _preflight_check():
    import requests
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    sep = "─" * 60
    print(sep)
    print("PREFLIGHT CHECK")
    print(sep)

    errors = []

    # 1. Config sanity
    key_preview = (LITELLM_API_KEY[:8] + "..." + LITELLM_API_KEY[-4:]) if len(LITELLM_API_KEY) > 12 else ("(EMPTY)" if not LITELLM_API_KEY else LITELLM_API_KEY)
    print(f"  LITELLM_BASE_URL  : {LITELLM_BASE_URL!r}")
    print(f"  ER_EMBEDDING_REQUEST_PATH: {ER_EMBEDDING_REQUEST_PATH!r}")
    print(f"  EMBEDDING_MODEL   : {EMBEDDING_MODEL!r}")
    print(f"  EMBEDDING_DIMENSION: {EMBEDDING_DIMENSION}")
    print(f"  LITELLM_API_KEY   : {key_preview}")
    print(f"  ER_SOURCE_TABLE   : {ER_SOURCE_TABLE!r}")
    print(f"  ER_CHUNK_TABLE    : {ER_CHUNK_TABLE!r}")
    print(f"  ER_RUN_LOG_TABLE  : {ER_RUN_LOG_TABLE!r}")
    if not LITELLM_API_KEY:
        errors.append("LITELLM_API_KEY is empty — check secret scope or widget")

    # 2. Gateway connectivity probe
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

    # 3. Single-string embedding smoke test via the real helper.
    # This avoids false negatives from preflight drifting from pipeline logic.
    try:
        print("  [embed smoke]   calling embed_texts_batch(timeout=45s, retries=1) ...")
        vectors = embed_texts_batch(
            ["preflight test"],
            base_url=LITELLM_BASE_URL,
            api_key=LITELLM_API_KEY,
            model=EMBEDDING_MODEL,
            dimension=EMBEDDING_DIMENSION,
            request_path=ER_EMBEDDING_REQUEST_PATH,
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
# issues before the expensive extract+chunk phase.  It does mean you
# cannot %run this notebook purely to import helper functions.
_preflight_check()

# COMMAND ----------

# ── Watermark helpers ──────────────────────────────────────────────────

def cleanup_stale_runs() -> int:
    """Mark any in_progress rows that predate this run as 'failed'.

    A run killed by Databricks timeout (or cluster restart) leaves a permanent
    in_progress row.  Without cleanup these accumulate in the run log and are
    visually misleading.  We mark them 'failed' here so the log reflects reality.
    The watermark they hold is still used via get_last_watermark() (which now
    includes 'failed') so incremental resume is unaffected.

    Returns the number of rows updated.
    """
    if not ER_RUN_LOG_TABLE:
        return 0
    try:
        spark.sql(f"""
            UPDATE {ER_RUN_LOG_TABLE}
            SET status = 'failed',
                run_completed_at = current_timestamp()
            WHERE status = 'in_progress'
        """)
        updated = spark.sql(f"""
            SELECT COUNT(*) AS cnt FROM {ER_RUN_LOG_TABLE}
            WHERE status = 'failed'
              AND run_completed_at >= current_timestamp() - INTERVAL 5 SECONDS
        """).first().cnt
        if updated:
            log.warning(
                f"Cleaned up {updated} stale in_progress run(s) in {ER_RUN_LOG_TABLE} — "
                f"those runs were killed before completing (e.g. job timeout)"
            )
        return updated
    except Exception as e:
        log.warning(f"Stale run cleanup failed (non-blocking): {e}")
        return 0


def get_last_watermark() -> str | None:
    """Return the MAX watermark_ts from the last completed or failed run, or None.

    Includes 'failed' rows so that a run killed mid-way (e.g. by job timeout)
    still provides a valid resume watermark — the watermark reflects how far
    that run actually wrote, so the next run picks up from there rather than
    re-processing everything from ER_CUTOFF_DATE.
    """
    if not ER_RUN_LOG_TABLE or FORCE_RESET:
        return None
    try:
        row = spark.sql(f"""
            SELECT CAST(MAX(watermark_ts) AS STRING) AS wm FROM {ER_RUN_LOG_TABLE}
            WHERE status IN ('completed', 'failed')
              AND watermark_ts IS NOT NULL
        """).first()
        wm = row.wm if row and row.wm else None
        if wm:
            log.info(f"Incremental run: using watermark sys_updated_on > '{wm}'")
        else:
            log.info("No previous completed run found — full load from ER_CUTOFF_DATE")
        return wm
    except Exception as e:
        log.warning(f"Could not read run log (non-blocking): {e}")
        return None


def write_run_log(
    run_id: str,
    started_at: "datetime",
    status: str,
    records_extracted: int,
    chunks_written: int,
    watermark_ts: str | None,
) -> None:
    """Upsert a run log row (MERGE by run_id). Non-blocking — failures logged.

    Called multiple times per run:
      1. At pipeline start with status='in_progress' (gives immediate visibility).
      2. After each micro-batch to persist the latest watermark + chunk count.
      3. At pipeline end with status='completed' or 'failed'.

    Uses MERGE so repeated calls for the same run_id update in place rather
    than inserting duplicate rows.  Uses spark.createDataFrame + SQL to avoid
    SQL injection via string-interpolated values (C1 review item).
    """
    if not ER_RUN_LOG_TABLE:
        return
    # Validate enum value (defense-in-depth).  'backfill_audit' is written by
    # the audit block to mark how far backfill has scanned — it is excluded
    # from get_last_watermark() so it never affects the ingestion floor.
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

        row = [(run_id, "er_ingestion", started_at, completed_at,
                status, records_extracted, chunks_written, watermark_ts)]
        log_df = spark.createDataFrame(row, schema)

        tmp_view = f"_er_run_log_staging_{int(time.time())}"
        log_df.createOrReplaceTempView(tmp_view)

        merge_sql = f"""
            MERGE INTO {ER_RUN_LOG_TABLE} AS target
            USING {tmp_view} AS source
            ON target.run_id = source.run_id
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """
        spark.sql(merge_sql)

        log.info(f"Run log written: run_id={run_id}, status={status}, "
                 f"chunks={chunks_written}, watermark={watermark_ts}")
    except Exception as e:
        log.warning(f"Failed to write run log (non-blocking): {e}")

# COMMAND ----------

# ── Failed-records table helpers ────────────────────────────────────────────
# Per-record failure tracking enables individual retry without freezing the
# watermark.  Successful retries delete rows; persistent failures stay visible.

def read_retry_records() -> set[str]:
    """Return the set of er_case_numbers eligible for retry on this run.

    Eligibility: present in failed-records table AND attempts < ER_MAX_RECORD_ATTEMPTS.
    Returns empty set if the table is unconfigured or empty.
    """
    if not ER_FAILED_RECORDS_TABLE:
        return set()
    try:
        rows = spark.sql(f"""
            SELECT er_case_number FROM {ER_FAILED_RECORDS_TABLE}
            WHERE attempts < {ER_MAX_RECORD_ATTEMPTS}
        """).collect()
        retry_set = {r.er_case_number for r in rows if r.er_case_number}
        if retry_set:
            log.info(f"Retry list: {len(retry_set)} previously-failed records "
                     f"will be re-attempted (attempts < {ER_MAX_RECORD_ATTEMPTS})")
        return retry_set
    except Exception as e:
        log.warning(f"Could not read failed records table (non-blocking): {e}")
        return set()


def write_failed_records(
    failed: list[tuple],
    run_id: str,
) -> None:
    """Upsert failure rows. `failed` is a list of (er_case_number, sys_updated_on, error_msg).

    On INSERT: attempts=1, first_failed_at=now.
    On MATCH:  attempts+=1, last_attempted_at=now, last_error/last_run_id updated.
    """
    if not ER_FAILED_RECORDS_TABLE or not failed:
        return
    try:
        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType, TimestampType,
        )
        now = datetime.now(timezone.utc)

        schema = StructType([
            StructField("er_case_number", StringType(), False),
            StructField("sys_updated_on", TimestampType(), True),
            StructField("first_failed_at", TimestampType(), True),
            StructField("last_attempted_at", TimestampType(), True),
            StructField("attempts", IntegerType(), True),
            StructField("last_error", StringType(), True),
            StructField("last_run_id", StringType(), True),
        ])

        rows = []
        for er_case_number, sys_updated_on, err_msg in failed:
            # Truncate error to keep table compact
            truncated = (err_msg[:500] + "...") if err_msg and len(err_msg) > 500 else err_msg
            # Coerce sys_updated_on (string from extract) to datetime if needed
            sut = sys_updated_on
            if isinstance(sut, str):
                try:
                    sut = pd.to_datetime(sut, utc=True).to_pydatetime()
                except Exception:
                    sut = None
            rows.append((er_case_number, sut, now, now, 1, truncated, run_id))

        df = spark.createDataFrame(rows, schema)
        tmp_view = f"_er_failed_staging_{int(time.time())}"
        df.createOrReplaceTempView(tmp_view)

        # MERGE: increment attempts on existing rows, insert new ones
        merge_sql = f"""
            MERGE INTO {ER_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.er_case_number = source.er_case_number
            WHEN MATCHED THEN UPDATE SET
                target.attempts = target.attempts + 1,
                target.last_attempted_at = source.last_attempted_at,
                target.last_error = source.last_error,
                target.last_run_id = source.last_run_id,
                target.sys_updated_on = source.sys_updated_on
            WHEN NOT MATCHED THEN INSERT *
        """
        spark.sql(merge_sql)
        log.info(f"Failed records table updated: {len(failed)} record(s) tracked")
    except Exception as e:
        log.warning(f"Failed to write failed-records table (non-blocking): {e}")


def clear_succeeded_retries(succeeded_er_numbers: set[str]) -> None:
    """Delete rows from failed-records table for records that succeeded this run."""
    if not ER_FAILED_RECORDS_TABLE or not succeeded_er_numbers:
        return
    try:
        from pyspark.sql.types import StructType, StructField, StringType
        schema = StructType([StructField("er_case_number", StringType(), False)])
        df = spark.createDataFrame([(n,) for n in succeeded_er_numbers], schema)
        tmp_view = f"_er_cleared_staging_{int(time.time())}"
        df.createOrReplaceTempView(tmp_view)
        spark.sql(f"""
            DELETE FROM {ER_FAILED_RECORDS_TABLE}
            WHERE er_case_number IN (SELECT er_case_number FROM {tmp_view})
        """)
        log.info(f"Failed records table: cleared {len(succeeded_er_numbers)} successful retries")
    except Exception as e:
        log.warning(f"Failed to clear succeeded retries (non-blocking): {e}")

# COMMAND ----------

# ── Step 1: Extract from ER source table ──────────────────────────────────────

def extract_er_records(watermark: str | None = None) -> pd.DataFrame:
    """Query ER source table and return preprocessed DataFrame.

    If watermark is set, only returns records with sys_updated_on > watermark
    (incremental mode).  Falls back to ER_CUTOFF_DATE on first run or FORCE_RESET.

    Additionally unions in any records flagged for retry in
    ER_FAILED_RECORDS_TABLE (those previously failed embedding and have
    attempts < ER_MAX_RECORD_ATTEMPTS).  This lets individual records be
    retried independently of the watermark.

    User-supplied filter values (ER_SERIAL_NUMBERS) are applied via Spark
    DataFrame .filter().isin() to avoid SQL injection through job parameters.
    """
    where_clauses = []

    if watermark:
        # Incremental: only new/changed records since last successful run
        where_clauses.append(f"sys_updated_on > CAST('{watermark}' AS TIMESTAMP)")
    elif ER_CUTOFF_DATE:
        # Full load with date floor (first run or FORCE_RESET)
        where_clauses.append(f"opened_at >= '{ER_CUTOFF_DATE}'")

    where = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    limit_clause = ""
    if ER_MAX_RECORDS and ER_MAX_RECORDS > 0:
        limit_clause = f" LIMIT {ER_MAX_RECORDS}"
        log.info(f"  Safety limit: capping extract at {ER_MAX_RECORDS} records")

    # ORDER BY sys_updated_on is critical for watermark correctness.
    # Micro-batches are positional slices (iloc[0:5000], etc.), so the
    # watermark (MAX sys_updated_on of processed batches) only safely
    # represents a resume point if records are sorted by that column.
    # Without ordering, batch N could contain records with an earlier
    # sys_updated_on than batch N-1 — causing them to be silently skipped
    # on a crash-resume run.
    sql = f"SELECT * FROM {ER_SOURCE_TABLE} {where} ORDER BY sys_updated_on ASC{limit_clause}"

    log.info(f"Extracting ER records: {sql[:200]}...")
    sdf = spark.sql(sql)

    # Apply user-supplied filter values via DataFrame API (not f-string SQL)
    if ER_SERIAL_NUMBERS:
        from pyspark.sql.functions import col as _col
        sdf = sdf.filter(_col("u_serial_number").isin(ER_SERIAL_NUMBERS))
        log.info(f"  Applied serial number filter: {len(ER_SERIAL_NUMBERS)} values")

    df = sdf.toPandas()
    log.info(f"Extracted {len(df)} raw records from {ER_SOURCE_TABLE}")

    # ── Union retry candidates from failed-records table ────────────────────
    # These are records that previously failed embedding.  We re-extract them
    # by er_case_number.  De-dup against the incremental set (a record might
    # be in both: failed previously AND updated since watermark).
    retry_set = read_retry_records()
    if retry_set:
        # Filter out those already present in incremental extract to avoid
        # the larger query when not needed.
        existing = set()
        if "number" in df.columns:
            existing = set(df["number"].dropna().astype(str))
        elif not df.empty:
            existing = set(df.index.astype(str))
        missing_retry = retry_set - existing
        if missing_retry:
            # Spark IN clause has limits — use DataFrame API for safety
            from pyspark.sql.functions import col as _col2
            retry_sdf = (
                spark.sql(f"SELECT * FROM {ER_SOURCE_TABLE}")
                .filter(_col2("number").isin(list(missing_retry)))
            )
            retry_df = retry_sdf.toPandas()
            log.info(f"  Retry source: pulled {len(retry_df)} record(s) "
                     f"(of {len(missing_retry)} requested) from source table")
            if not retry_df.empty:
                df = pd.concat([df, retry_df], ignore_index=True)
                # Preserve sort order so micro-batches remain time-ordered
                if "sys_updated_on" in df.columns:
                    df = df.sort_values("sys_updated_on", kind="mergesort").reset_index(drop=True)
        else:
            log.info(f"  All {len(retry_set)} retry records already present in incremental extract")

    # Track high-watermark of this batch for run log
    df["_watermark_ts"] = None
    if "sys_updated_on" in df.columns:
        df["_watermark_ts"] = df["sys_updated_on"].apply(
            lambda v: str(v) if pd.notna(v) else None
        )

    # Preprocess: map columns, filter blanks
    if "u_serial_number" in df.columns:
        df["serial_number"] = df["u_serial_number"].apply(
            lambda v: str(v).strip() if pd.notna(v) and str(v).strip().upper() not in ("", "MISSING", "BLANK") else None
        )
    else:
        df["serial_number"] = None

    if "number" in df.columns:
        df["er_case_number"] = df["number"]
    else:
        df["er_case_number"] = df.index.astype(str)

    return df


# COMMAND ----------

# ── Step 2: Combine text fields + Chunk ─────────────────────────────────────

def combine_fields(row: pd.Series) -> str:
    """Join non-empty text fields with [FIELD_NAME] headers."""
    parts = []
    for f in ER_TEXT_FIELDS:
        if f in row.index and pd.notna(row[f]) and str(row[f]).strip():
            parts.append(f"[{f.upper()}]\n{row[f]}")
    return "\n\n".join(parts) if parts else ""


def estimate_tokens(text: str) -> int:
    """Rough token count — uses the HIGHER of word-based and char-based estimates.

    Word-based: word_count * 1.33 (good for normal prose).
    Char-based: char_count / 3.5  (catches long-word edge cases like URLs,
    base64 blobs, and no-space text that have few whitespace-delimited words
    but many BPE tokens).
    """
    if not text:
        return 0
    word_est = int(len(text.split()) * 1.33)
    char_est = int(len(text) / 3.5)
    return max(1, word_est, char_est)


# Character-based safety cap per chunk.  The embedding model
# (text-embedding-3-large) has an 8 191-token input limit.
# Dense technical text (serial numbers, hex, base64) can tokenize at
# ~2 chars/token, so 15 000 chars ≈ 7 500 tokens — safe headroom.
_MAX_CHUNK_CHARS = 15_000


def sliding_window_chunk(text: str, token_limit: int, overlap_pct: float) -> list[str]:
    """Split text into overlapping chunks by word boundaries.

    Each chunk is additionally capped at *_MAX_CHUNK_CHARS* characters
    to prevent token-limit errors from long technical words/codes.
    """
    if not text or not text.strip():
        return []

    if estimate_tokens(text) <= token_limit:
        return [text]

    max_words = int(token_limit / 1.33)
    overlap_words = int(max_words * overlap_pct)
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = min(start + max_words, len(words))
        chunk_text = " ".join(words[start:end])
        # Trim trailing words until char length is within the
        # embedding model's token budget (long-word safety net).
        while len(chunk_text) > _MAX_CHUNK_CHARS and end > start + 1:
            end -= 1
            chunk_text = " ".join(words[start:end])
        chunks.append(chunk_text)
        if end >= len(words):
            break
        start = end - overlap_words

    return chunks


def chunk_all_records(df: pd.DataFrame) -> list[dict]:
    """Chunk all ER records and return list of chunk dicts."""
    all_chunks = []
    skipped = 0

    for _, row in df.iterrows():
        combined = combine_fields(row)
        if not combined.strip():
            skipped += 1
            continue

        er_case_number = str(row.get("er_case_number", ""))
        serial = row.get("serial_number")
        text_chunks = sliding_window_chunk(combined, ER_CHUNK_SIZE, ER_CHUNK_OVERLAP_PCT)
        total_chunks = len(text_chunks)

        for idx, chunk_text in enumerate(text_chunks):
            chunk_id = hashlib.md5(f"{er_case_number}_{idx}".encode()).hexdigest()

            # Build metadata JSON with remaining source context
            meta = {}
            for col in ["short_description", "u_desired_deliverable",
                         "u_feedback_comments", "u_resolve_notes",
                         "u_immediate_response_explanati", "close_notes"]:
                val = row.get(col)
                if pd.notna(val) and str(val).strip():
                    meta[col] = str(val).strip()

            all_chunks.append({
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "total_chunks": total_chunks,
                "er_case_number": er_case_number,
                "serial_number": str(serial) if pd.notna(serial) else None,
                "opened_at": str(row.get("opened_at", "")) if pd.notna(row.get("opened_at")) else None,
                "status": str(row.get("u_status", "")) if pd.notna(row.get("u_status")) else None,
                "u_component": str(row.get("u_component", "")) if pd.notna(row.get("u_component")) else None,
                "u_field_action_taken": str(row.get("u_field_action_taken", "")) if pd.notna(row.get("u_field_action_taken")) else None,
                "equipment": str(row.get("u_equipment", "")) if pd.notna(row.get("u_equipment")) else None,
                "equipment_id": str(row.get("equipment_id", "")) if pd.notna(row.get("equipment_id")) else None,
                "chunk_text": chunk_text,
                "chunk_embedding": None,  # filled by embedding step
                "metadata": json.dumps(meta),
                "created_at": datetime.now(timezone.utc),
            })

    log.info(f"Chunked {len(df)} records → {len(all_chunks)} chunks (skipped {skipped} empty)")
    return all_chunks


# COMMAND ----------

# ── Step 3: Embed chunks via LiteLLM ───────────────────────────────────────

def embed_chunks(chunks: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Generate embeddings for all chunks using concurrent batch LiteLLM calls.

    Returns (embedded_chunks, failed_er_numbers_with_errors) where the latter
    is a dict mapping er_case_number -> error message for records that had
    any chunk fail to embed.  The caller writes these to the failed-records
    table for individual retry on subsequent runs.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total = len(chunks)
    embedded = 0
    failed = 0
    failed_er_numbers: dict[str, str] = {}

    def _embed_batch(batch: list[dict]) -> list[dict] | None:
        texts = [c["chunk_text"] for c in batch]
        vectors = embed_texts_batch(
            texts,
            base_url=LITELLM_BASE_URL,
            api_key=LITELLM_API_KEY,
            model=EMBEDDING_MODEL,
            dimension=EMBEDDING_DIMENSION,
            request_path=ER_EMBEDDING_REQUEST_PATH,
            verify_ssl=LLM_VERIFY_SSL,
            max_retries=ER_MAX_RETRIES,
            max_input_chars=_MAX_CHUNK_CHARS,
        )
        for chunk, vec in zip(batch, vectors):
            chunk["chunk_embedding"] = vec
        return batch

    batches = [
        chunks[i : i + ER_EMBEDDING_BATCH_SIZE]
        for i in range(0, total, ER_EMBEDDING_BATCH_SIZE)
    ]
    log.info(f"Embedding {total} chunks in {len(batches)} batches "
             f"(batch_size={ER_EMBEDDING_BATCH_SIZE}, workers={ER_EMBEDDING_CONCURRENCY})")

    with ThreadPoolExecutor(max_workers=ER_EMBEDDING_CONCURRENCY) as pool:
        future_to_batch = {
            pool.submit(_embed_batch, batch): batch for batch in batches
        }
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            try:
                future.result()
                embedded += len(batch)
            except Exception as e:
                err_msg = f"{type(e).__name__}: {e}"
                log.error(f"Embedding batch failed: {err_msg}")
                failed += len(batch)
                for c in batch:
                    # Keep first error per record (subsequent same-batch failures share it)
                    failed_er_numbers.setdefault(c["er_case_number"], err_msg)

    log.info(f"Embedding complete: {embedded} succeeded, {failed} failed out of {total}")
    if failed_er_numbers:
        log.warning(f"  {len(failed_er_numbers)} ER records had embedding failures — "
                    f"will be tracked in failed-records table for retry next run")

    # Filter out chunks that failed to embed
    ok_chunks = [c for c in chunks if c["chunk_embedding"] is not None]
    return ok_chunks, failed_er_numbers


# COMMAND ----------

# ── Step 4: Write to Delta table ───────────────────────────────────────────

def write_chunks_to_delta(chunks: list[dict]):
    """Write chunk rows to the ER Delta table via MERGE."""
    if not chunks:
        log.warning("No chunks to write")
        return 0

    from pyspark.sql.types import (
        StructType, StructField, StringType, IntegerType,
        ArrayType, DoubleType, TimestampType,
    )

    schema = StructType([
        StructField("chunk_id", StringType(), False),
        StructField("chunk_index", IntegerType(), True),
        StructField("total_chunks", IntegerType(), True),
        StructField("er_case_number", StringType(), False),
        StructField("serial_number", StringType(), True),
        StructField("opened_at", StringType(), True),
        StructField("status", StringType(), True),
        StructField("u_component", StringType(), True),
        StructField("u_field_action_taken", StringType(), True),
        StructField("equipment", StringType(), True),
        StructField("equipment_id", StringType(), True),
        StructField("chunk_text", StringType(), False),
        StructField("chunk_embedding", ArrayType(DoubleType()), True),
        StructField("metadata", StringType(), True),
        StructField("created_at", TimestampType(), True),
    ])

    # Convert to Spark DataFrame
    rows = []
    for c in chunks:
        rows.append((
            c["chunk_id"],
            c["chunk_index"],
            c["total_chunks"],
            c["er_case_number"],
            c["serial_number"],
            c["opened_at"],
            c["status"],
            c["u_component"],
            c["u_field_action_taken"],
            c["equipment"],
            c["equipment_id"],
            c["chunk_text"],
            c["chunk_embedding"],
            c["metadata"],
            c["created_at"],
        ))

    df = spark.createDataFrame(rows, schema)

    tmp_view = f"_er_chunks_staging_{int(time.time())}"
    df.createOrReplaceTempView(tmp_view)

    merge_sql = f"""
        MERGE INTO {ER_CHUNK_TABLE} AS target
        USING {tmp_view} AS source
        ON target.chunk_id = source.chunk_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """
    spark.sql(merge_sql)
    log.info(f"Merged {len(chunks)} chunks into {ER_CHUNK_TABLE}")

    # Remove orphaned chunks: if a source record produced fewer chunks than
    # before (e.g., text was trimmed or chunk config changed), old chunks at
    # higher indices linger with stale content.  Delete them.
    er_cases_in_batch = set(c["er_case_number"] for c in chunks)
    if er_cases_in_batch:
        orphan_sql = f"""
            DELETE FROM {ER_CHUNK_TABLE}
            WHERE er_case_number IN (SELECT DISTINCT er_case_number FROM {tmp_view})
              AND chunk_id NOT IN (SELECT chunk_id FROM {tmp_view})
        """
        spark.sql(orphan_sql)
        log.info(f"Removed orphaned chunks for {len(er_cases_in_batch)} ER records")

    return len(chunks)


# COMMAND ----------

# ── Step 5: VS Index — Ensure Exists + Sync ────────────────────────────────

def ensure_vs_index():
    """Verify the VS index exists, or create it.  Called early in the pipeline
    so the index is ready before any data is written.  Logs all details on
    failure to help diagnose permission / endpoint issues."""
    if not ER_VS_INDEX or not ER_VS_ENDPOINT:
        log.warning("VS index or endpoint not configured — skipping VS index check.  "
                     f"ER_VS_INDEX={ER_VS_INDEX!r}, ER_VS_ENDPOINT={ER_VS_ENDPOINT!r}")
        return

    log.info(f"Ensuring VS index exists: {ER_VS_INDEX} on endpoint {ER_VS_ENDPOINT}")

    ws_url, token = get_dbr_auth()
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # ── 1. Check endpoint health ────────────────────────────────────────
    try:
        ep_url = f"{ws_url}/api/2.0/vector-search/endpoints/{ER_VS_ENDPOINT}"
        ep_req = urllib.request.Request(ep_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(ep_req, context=ctx, timeout=30) as resp:  # noqa: S310
            ep_info = json.loads(resp.read())
        ep_status = ep_info.get("endpoint_status", {}).get("state", "UNKNOWN")
        log.info(f"  VS endpoint '{ER_VS_ENDPOINT}' state: {ep_status}")
        if ep_status != "ONLINE":
            log.warning(f"  VS endpoint is NOT ONLINE (state={ep_status}) — "
                        "index creation / sync may fail")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        log.error(f"  VS endpoint check failed: HTTP {e.code} — {body}")
        log.error(f"  Endpoint URL attempted: {ep_url}")
        if e.code == 403:
            log.error("  → The service principal likely lacks CAN_USE on the "
                      f"endpoint '{ER_VS_ENDPOINT}'.  Grant access via the "
                      "Databricks admin console.")
        raise
    except Exception as e:
        log.error(f"  VS endpoint check failed (unexpected): {e}")
        raise

    # ── 2. Check if index exists ────────────────────────────────────────
    index_exists = False
    try:
        status = check_vs_index_status(ws_url, token, ER_VS_INDEX)
        idx_status = status.get("status", "UNKNOWN")
        log.info(f"  VS index '{ER_VS_INDEX}' exists — status: {idx_status}")
        index_exists = True

        # Log additional detail if the index is in a bad state
        if idx_status not in ("ONLINE", "ONLINE_NO_PENDING_UPDATE", "PROVISIONING"):
            log.warning(f"  VS index status is '{idx_status}' — may need manual attention.  "
                        f"Full status: {json.dumps(status, default=str)[:500]}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.info(f"  VS index '{ER_VS_INDEX}' does not exist (404) — will create")
        elif e.code == 403:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"  VS index check returned 403 Forbidden — {body}")
            log.error(f"  → Grant CAN_USE on endpoint '{ER_VS_ENDPOINT}' to the service principal")
            raise PermissionError(
                f"403 Forbidden on VS index {ER_VS_INDEX}. "
                f"Grant CAN_USE on endpoint '{ER_VS_ENDPOINT}' to the service principal."
            ) from e
        else:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"  VS index check failed: HTTP {e.code} — {body}")
            raise

    # ── 3. Create index if missing ──────────────────────────────────────
    if not index_exists:
        create_url = f"{ws_url}/api/2.0/vector-search/indexes"
        create_payload = {
            "name": ER_VS_INDEX,
            "endpoint_name": ER_VS_ENDPOINT,
            "primary_key": "chunk_id",
            "index_type": "DELTA_SYNC",
            "delta_sync_index_spec": {
                "source_table": ER_CHUNK_TABLE,
                "pipeline_type": "TRIGGERED",
                "embedding_vector_columns": [
                    {
                        "name": "chunk_embedding",
                        "embedding_dimension": EMBEDDING_DIMENSION,
                    }
                ],
            },
        }
        log.info(f"  Creating VS index with payload: {json.dumps(create_payload)}")
        try:
            req = urllib.request.Request(
                create_url,
                data=json.dumps(create_payload).encode(),
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:  # noqa: S310
                resp_body = json.loads(resp.read())
            log.info(f"  VS index created successfully: {resp_body}")
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:500]
            log.error(f"  VS index creation failed: HTTP {e.code} — {body}")
            log.error(f"  Create URL: {create_url}")
            log.error(f"  Source table: {ER_CHUNK_TABLE}")
            log.error(f"  Endpoint: {ER_VS_ENDPOINT}")
            raise RuntimeError(
                f"Failed to create VS index '{ER_VS_INDEX}': HTTP {e.code} — {body}"
            ) from e

    log.info(f"  VS index '{ER_VS_INDEX}' is ready")


def sync_vector_search():
    """Trigger a VS index sync and poll until complete."""
    if not ER_VS_INDEX or not ER_VS_ENDPOINT:
        log.info("VS index or endpoint not configured — skipping sync")
        return

    ws_url, token = get_dbr_auth()

    # Trigger sync on existing index
    log.info(f"Triggering VS sync for {ER_VS_INDEX}...")
    try:
        result = trigger_vs_sync(ws_url, token, ER_VS_ENDPOINT, ER_VS_INDEX)
        log.info(f"VS sync triggered: {result}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        log.error(f"VS sync trigger failed: HTTP {e.code} — {body}")
        log.error(f"  Index: {ER_VS_INDEX}, Endpoint: {ER_VS_ENDPOINT}")
        raise
    except Exception as e:
        log.error(f"VS sync trigger failed (unexpected): {e}")
        raise

    # Poll until sync is no longer in progress (best-effort, non-blocking)
    _MAX_POLLS = 12
    _POLL_INTERVAL = 30  # seconds
    for i in range(1, _MAX_POLLS + 1):
        time.sleep(_POLL_INTERVAL)
        try:
            st = check_vs_index_status(ws_url, token, ER_VS_INDEX)
            idx_status = st.get("status", "UNKNOWN")
            log.info(f"  VS sync poll {i}/{_MAX_POLLS}: status={idx_status}")
            if idx_status in ("ONLINE", "ONLINE_NO_PENDING_UPDATE"):
                log.info("VS sync complete")
                return
        except Exception as e:
            log.warning(f"  VS sync poll {i}/{_MAX_POLLS} failed: {e}")
    log.warning(f"VS sync still in progress after {_MAX_POLLS * _POLL_INTERVAL}s — continuing")


# COMMAND ----------

# ── Main Pipeline ───────────────────────────────────────────────────────────

# Recover Spark session if it expired while the notebook was idle or during
# config cell execution.  Also called again after embedding (below).
ensure_spark_session()

log.info("=" * 60)
log.info("ER Ingestion Pipeline — START")
log.info(f"  Source: {ER_SOURCE_TABLE}")
log.info(f"  Target: {ER_CHUNK_TABLE}")
log.info(f"  VS Index: {ER_VS_INDEX or '(not configured)'}")
log.info(f"  Run log: {ER_RUN_LOG_TABLE or '(disabled)'}")
log.info(f"  Chunk size: {ER_CHUNK_SIZE}, overlap: {ER_CHUNK_OVERLAP_PCT*100:.0f}%")
log.info(f"  Cutoff date: {ER_CUTOFF_DATE}")
log.info(f"  Serial filter: {ER_SERIAL_NUMBERS or 'all'}")
log.info(f"  FORCE_RESET: {FORCE_RESET}")
log.info(f"  Record batch size: {ER_RECORD_BATCH_SIZE if ER_RECORD_BATCH_SIZE > 0 else 'all-at-once (disabled)'}")
log.info("=" * 60)

# ── Optional: Backfill audit mode ──────────────────────────────────────────
# When ER_BACKFILL_AUDIT=true, find source records below the current watermark
# that have no chunks in ER_CHUNK_TABLE, seed them into ER_FAILED_RECORDS_TABLE
# with attempts=0, and exit.  The next normal run picks them up via the
# Pattern 2 retry path.  Pure read + small insert — does NOT extract/embed/write.
#
# Backfill marker:
#   After each successful audit, we MERGE a row into ER_RUN_LOG_TABLE with
#   status='backfill_audit' and watermark_ts = the ceiling of that audit.
#   Subsequent audit runs use MAX(watermark_ts WHERE status='backfill_audit')
#   as a FLOOR — the same range is never re-scanned automatically.
#
# Manual override:
#   ER_BACKFILL_RECORD_IDS (comma-separated) bypasses the source-vs-chunks
#   query entirely and seeds only the supplied IDs.  The marker is ignored
#   in this path, enabling targeted re-audit of records below the marker.
if ER_BACKFILL_AUDIT:
    log.info("=" * 60)
    log.info("BACKFILL AUDIT MODE")
    log.info("=" * 60)

    if not ER_FAILED_RECORDS_TABLE:
        raise RuntimeError(
            "ER_BACKFILL_AUDIT=true but ER_FAILED_RECORDS_TABLE is not configured — "
            "cannot seed missing records for retry."
        )
    if not ER_RUN_LOG_TABLE:
        raise RuntimeError(
            "ER_BACKFILL_AUDIT=true but ER_RUN_LOG_TABLE is not configured — "
            "cannot determine the audit watermark / marker."
        )

    ensure_spark_session()

    audit_run_id = f"backfill-audit-{int(time.time())}"
    audit_now = datetime.now(timezone.utc)

    from pyspark.sql.functions import lit, current_timestamp
    from pyspark.sql.types import StructType, StructField, StringType, TimestampType

    # ── Path A: explicit record-ID override (bypasses marker + source query) ──
    if ER_BACKFILL_RECORD_IDS:
        log.info(f"  Override mode: seeding {len(ER_BACKFILL_RECORD_IDS)} explicit record ID(s)")
        log.info("  Backfill marker IGNORED (manual override path)")

        seed_schema = StructType([
            StructField("er_case_number", StringType(), False),
            StructField("sys_updated_on", TimestampType(), True),
        ])
        seed_rows = [(str(rid), None) for rid in ER_BACKFILL_RECORD_IDS]
        seed_df = (
            spark.createDataFrame(seed_rows, seed_schema)
            .withColumn("first_failed_at", current_timestamp())
            .withColumn("last_attempted_at", lit(None).cast("timestamp"))
            .withColumn("attempts", lit(0))
            .withColumn("last_error", lit("BACKFILL_AUDIT_OVERRIDE: explicit record id"))
            .withColumn("last_run_id", lit(audit_run_id))
        )
        tmp_view = f"_er_backfill_seed_{int(time.time())}"
        seed_df.createOrReplaceTempView(tmp_view)
        spark.sql(f"""
            MERGE INTO {ER_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.er_case_number = source.er_case_number
            WHEN NOT MATCHED THEN INSERT *
        """)
        log.info(f"BACKFILL AUDIT (override) — seeded {len(ER_BACKFILL_RECORD_IDS)} record(s)")
        log.info("  NOTE: backfill marker NOT advanced (override path).")
        dbutils.notebook.exit(f"BACKFILL_OVERRIDE_SEEDED:{len(ER_BACKFILL_RECORD_IDS)}")  # noqa: F821

    # ── Path C: date-range re-ingestion (bypasses marker, ignores gap check) ──
    # Seeds ALL source records in the date range into er_failed_records.
    # Chunk MERGE dedup (on chunk_id = md5(er_case_number_idx)) ensures that
    # records which already have correct chunks get overwritten in place — no
    # duplicates.  Marker is NOT advanced (operator-chosen range).
    if ER_BACKFILL_DATE_FROM and ER_BACKFILL_DATE_TO:
        log.info(f"  Date-range mode: {ER_BACKFILL_DATE_FROM} → {ER_BACKFILL_DATE_TO}")
        log.info("  Backfill marker IGNORED (date-range path)")
        log.info("  Seeding ALL source records in range (dedup handled at chunk write)")

        _has_text_expr = " OR ".join(
            f"(TRIM(COALESCE(CAST({f} AS STRING), '')) <> '')"
            for f in ER_TEXT_FIELDS
        )

        range_df = spark.sql(f"""
            SELECT
                CAST(number AS STRING) AS er_case_number,
                MIN(sys_updated_on)    AS sys_updated_on
            FROM {ER_SOURCE_TABLE}
            WHERE sys_updated_on IS NOT NULL
              AND sys_updated_on >= CAST('{ER_BACKFILL_DATE_FROM}' AS TIMESTAMP)
              AND sys_updated_on <= CAST('{ER_BACKFILL_DATE_TO}' AS TIMESTAMP)
              AND ({_has_text_expr})
            GROUP BY CAST(number AS STRING)
        """)

        range_count = range_df.count()
        log.info(f"  Records in date range: {range_count}")

        if range_count == 0:
            log.info("BACKFILL AUDIT (date-range) — no source records in specified range")
            dbutils.notebook.exit("BACKFILL_RANGE_EMPTY")  # noqa: F821

        seed_df = (
            range_df
            .withColumn("first_failed_at", current_timestamp())
            .withColumn("last_attempted_at", lit(None).cast("timestamp"))
            .withColumn("attempts", lit(0))
            .withColumn("last_error", lit(f"BACKFILL_DATE_RANGE: {ER_BACKFILL_DATE_FROM} to {ER_BACKFILL_DATE_TO}"))
            .withColumn("last_run_id", lit(audit_run_id))
            .select(
                "er_case_number",
                "sys_updated_on",
                "first_failed_at",
                "last_attempted_at",
                "attempts",
                "last_error",
                "last_run_id",
            )
        )

        tmp_view = f"_er_backfill_range_{int(time.time())}"
        seed_df.createOrReplaceTempView(tmp_view)

        # MERGE: insert new, reset attempts on existing (force re-process)
        spark.sql(f"""
            MERGE INTO {ER_FAILED_RECORDS_TABLE} AS target
            USING {tmp_view} AS source
            ON target.er_case_number = source.er_case_number
            WHEN MATCHED THEN UPDATE SET
                attempts = 0,
                last_error = source.last_error,
                last_run_id = source.last_run_id,
                last_attempted_at = NULL
            WHEN NOT MATCHED THEN INSERT *
        """)

        log.info(f"BACKFILL AUDIT (date-range) — seeded {range_count} record(s) into {ER_FAILED_RECORDS_TABLE}")
        log.info("  NOTE: backfill marker NOT advanced (date-range path).")
        log.info("  Next normal run will re-process these; chunk MERGE handles dedup.")
        dbutils.notebook.exit(f"BACKFILL_RANGE_SEEDED:{range_count}")  # noqa: F821

    # ── Path B: incremental scan against marker ──
    # Build a SQL expression that is TRUE only when at least one of the 13
    # ER text fields has non-empty content.  Records where all text fields are
    # null/blank produce zero chunks by design — they must not be flagged as
    # missing or seeded into the failed-records table.
    _has_text_expr = " OR ".join(
        f"(TRIM(COALESCE(CAST({f} AS STRING), '')) <> '')"
        for f in ER_TEXT_FIELDS
    )

    wm_row = spark.sql(f"""
        SELECT
            CAST(MAX(CASE WHEN status IN ('completed','in_progress') THEN watermark_ts END) AS STRING) AS ceiling_wm,
            CAST(MAX(CASE WHEN status = 'backfill_audit' THEN watermark_ts END) AS STRING) AS marker_wm
        FROM {ER_RUN_LOG_TABLE}
        WHERE watermark_ts IS NOT NULL
    """).first()
    audit_ceiling = wm_row.ceiling_wm if wm_row else None
    audit_floor = wm_row.marker_wm if wm_row else None

    if not audit_ceiling:
        log.warning("No ingestion watermark found — nothing to audit yet")
        dbutils.notebook.exit("BACKFILL_NO_WATERMARK")  # noqa: F821

    if audit_floor and audit_floor >= audit_ceiling:
        log.info(f"  Backfill marker ({audit_floor}) >= ingestion watermark ({audit_ceiling}) — already audited")
        log.info("  Use ER_BACKFILL_RECORD_IDS to re-audit specific records below the marker.")
        dbutils.notebook.exit("BACKFILL_UP_TO_DATE")  # noqa: F821

    log.info(f"  Audit ceiling (ingestion watermark): {audit_ceiling}")
    log.info(f"  Audit floor   (backfill marker)    : {audit_floor or '(none — first audit)'}")
    log.info(f"  Source: {ER_SOURCE_TABLE}")
    log.info(f"  Chunk table: {ER_CHUNK_TABLE}")

    # Source uses `number`; chunk table uses `er_case_number`.  Floor by
    # ER_CUTOFF_DATE (matches the original full-load filter on opened_at)
    # so we don't surface ancient pre-cutoff rows that were never in scope.
    cutoff_clause = f"AND opened_at >= '{ER_CUTOFF_DATE}'" if ER_CUTOFF_DATE else ""
    floor_clause = (
        f"AND sys_updated_on > CAST('{audit_floor}' AS TIMESTAMP)"
        if audit_floor else ""
    )

    missing_df = spark.sql(f"""
        WITH src AS (
            SELECT
                CAST(number AS STRING)        AS er_case_number,
                MIN(sys_updated_on)           AS sys_updated_on
            FROM {ER_SOURCE_TABLE}
            WHERE sys_updated_on IS NOT NULL
              AND sys_updated_on <= CAST('{audit_ceiling}' AS TIMESTAMP)
              AND ({_has_text_expr})
              {floor_clause}
              {cutoff_clause}
            GROUP BY CAST(number AS STRING)
        ),
        chunked AS (
            SELECT DISTINCT er_case_number
            FROM {ER_CHUNK_TABLE}
            WHERE er_case_number IS NOT NULL
        )
        SELECT s.er_case_number, s.sys_updated_on
        FROM src s
        LEFT ANTI JOIN chunked c ON s.er_case_number = c.er_case_number
    """)

    missing_count = missing_df.count()
    log.info(f"  Missing records (in source range, no chunks): {missing_count}")

    # Always advance the backfill marker after a successful scan — even if
    # zero gaps were found — so we don't re-scan the same range next time.
    def _advance_marker():
        write_run_log(
            run_id=audit_run_id,
            started_at=audit_now,
            status="backfill_audit",
            records_extracted=missing_count,
            chunks_written=0,
            watermark_ts=audit_ceiling,
        )
        log.info(f"  Backfill marker advanced to {audit_ceiling}")

    if missing_count == 0:
        log.info("BACKFILL AUDIT — no gaps found in this range")
        _advance_marker()
        dbutils.notebook.exit("BACKFILL_CLEAN")  # noqa: F821

    # Seed into ER_FAILED_RECORDS_TABLE with attempts=0 so Pattern 2 picks
    # them up on the next normal run.  MERGE so re-running the audit is
    # idempotent (won't reset attempts on records already being retried).
    seed_df = (
        missing_df
        .withColumn("first_failed_at", current_timestamp())
        .withColumn("last_attempted_at", lit(None).cast("timestamp"))
        .withColumn("attempts", lit(0))
        .withColumn("last_error", lit("BACKFILL_AUDIT: source record had no chunks below watermark"))
        .withColumn("last_run_id", lit(audit_run_id))
        .select(
            "er_case_number",
            "sys_updated_on",
            "first_failed_at",
            "last_attempted_at",
            "attempts",
            "last_error",
            "last_run_id",
        )
    )

    tmp_view = f"_er_backfill_seed_{int(time.time())}"
    seed_df.createOrReplaceTempView(tmp_view)

    spark.sql(f"""
        MERGE INTO {ER_FAILED_RECORDS_TABLE} AS target
        USING {tmp_view} AS source
        ON target.er_case_number = source.er_case_number
        WHEN NOT MATCHED THEN INSERT *
    """)

    log.info(f"BACKFILL AUDIT — seeded {missing_count} record(s) into {ER_FAILED_RECORDS_TABLE}")
    _advance_marker()
    log.info("Next normal pipeline run (ER_BACKFILL_AUDIT=false) will retry them.")
    dbutils.notebook.exit(f"BACKFILL_SEEDED:{missing_count}")  # noqa: F821

# Mark any stale in_progress rows (from previously killed runs) as failed
# before writing the new in_progress row for this run.
cleanup_stale_runs()

# Verify/create the VS index up front — fail early on permission or config
# errors rather than discovering them after a multi-hour embedding run.
try:
    ensure_vs_index()
except Exception as vs_init_err:
    log.error(f"VS index setup failed: {vs_init_err}")
    log.error("Pipeline will continue — data will be written to Delta, but VS sync will fail at the end.")

run_id = str(uuid.uuid4())
start_time = time.time()
run_started_at = datetime.now(timezone.utc)
rows_written = 0
_pipeline_failed = False

# On FORCE_RESET, clear the failed-records table so Pattern 2 doesn't
# re-extract records that will be processed anyway during the full reload.
if FORCE_RESET and ER_FAILED_RECORDS_TABLE:
    try:
        spark.sql(f"DELETE FROM {ER_FAILED_RECORDS_TABLE}")
        log.info(f"FORCE_RESET: cleared {ER_FAILED_RECORDS_TABLE}")
    except Exception as e:
        log.warning(f"FORCE_RESET: could not clear failed-records table (non-blocking): {e}")

# Write an immediate "in_progress" row so the run is visible from the start.
write_run_log(run_id, run_started_at, "in_progress", 0, 0, None)

try:
    # Determine watermark for incremental extract
    watermark = get_last_watermark()

    # Extract
    df = extract_er_records(watermark=watermark)
    if df.empty:
        log.info("No records to process — pipeline complete")
        write_run_log(run_id, run_started_at, "completed", 0, 0, watermark)
        dbutils.notebook.exit("NO_DATA")  # noqa: F821

    total_records = len(df)
    all_failed_er_numbers: set[str] = set()
    new_watermark: str | None = None
    # Watermark advances freely — failed records are tracked individually in
    # ER_FAILED_RECORDS_TABLE and re-extracted by er_case_number on the next
    # run (see read_retry_records / extract_er_records).  No freeze needed.

    # Build a quick lookup of er_case_number -> sys_updated_on for failure rows
    _sys_updated_lookup: dict[str, object] = {}
    if "er_case_number" in df.columns and "sys_updated_on" in df.columns:
        for _, _r in df[["er_case_number", "sys_updated_on"]].iterrows():
            _sys_updated_lookup[str(_r["er_case_number"])] = _r["sys_updated_on"]

    # ── Micro-batch loop: chunk → embed → write → free memory ────────────────
    # Processes ER_RECORD_BATCH_SIZE records at a time so that peak driver
    # memory stays proportional to the batch size rather than the full extract
    # volume. This prevents OOM on long date-range / full-load runs.
    # When ER_RECORD_BATCH_SIZE <= 0, fall back to processing all at once.
    batch_size = ER_RECORD_BATCH_SIZE if ER_RECORD_BATCH_SIZE > 0 else total_records
    record_offsets = list(range(0, total_records, batch_size))
    log.info(f"Micro-batching: {total_records} records in {len(record_offsets)} batch(es) "
             f"of up to {batch_size} records each")

    for batch_num, batch_start in enumerate(record_offsets, start=1):
        batch_df = df.iloc[batch_start : batch_start + batch_size]
        log.info(f"  Batch {batch_num}/{len(record_offsets)}: "
                 f"records {batch_start}–{batch_start + len(batch_df) - 1} "
                 f"({len(batch_df)} records)")

        # Track which records were attempted in this batch (for retry-clearing)
        batch_attempted = set(batch_df["er_case_number"].astype(str)) if "er_case_number" in batch_df.columns else set()

        # Chunk
        chunks = chunk_all_records(batch_df)
        if not chunks:
            log.info(f"  Batch {batch_num}: no chunks produced — skipping")
            continue

        # Embed — failed_er_errors maps er_case_number -> error message
        chunks, failed_er_errors = embed_chunks(chunks)
        all_failed_er_numbers |= set(failed_er_errors.keys())

        # Update failed-records table for this batch's failures
        if failed_er_errors:
            failure_rows = [
                (er, _sys_updated_lookup.get(er), msg)
                for er, msg in failed_er_errors.items()
            ]
            write_failed_records(failure_rows, run_id)

        if not chunks:
            log.warning(f"  Batch {batch_num}: all embeddings failed — skipping write")
            continue

        # Re-establish Spark session — embedding takes minutes of HTTP calls with
        # no Spark activity, which can trigger INACTIVITY_TIMEOUT on serverless.
        ensure_spark_session()

        # Write
        batch_written = write_chunks_to_delta(chunks)
        rows_written += batch_written

        # Clear succeeded retries: any record attempted this batch that did NOT
        # fail is now successfully embedded — remove from failed-records table
        # so it isn't retried again.
        succeeded_in_batch = batch_attempted - set(failed_er_errors.keys())
        if succeeded_in_batch:
            clear_succeeded_retries(succeeded_in_batch)

        # Watermark advances based on the highest sys_updated_on seen in any
        # successfully-written batch.  Failed records are tracked separately
        # in ER_FAILED_RECORDS_TABLE — no freeze required.
        if "_watermark_ts" in batch_df.columns:
            wm_vals = batch_df["_watermark_ts"].dropna()
            if not wm_vals.empty:
                batch_wm = str(wm_vals.max())
                if new_watermark is None or batch_wm > new_watermark:
                    new_watermark = batch_wm

        # Persist progress after every batch — if the pipeline crashes later,
        # the next run picks up from this watermark instead of re-doing everything.
        write_run_log(run_id, run_started_at, "in_progress",
                      total_records, rows_written, new_watermark)

        # Explicitly release batch memory before next iteration
        del chunks
        del batch_df

    if rows_written == 0 and not all_failed_er_numbers:
        log.info("No chunks produced across all batches — pipeline complete")
        write_run_log(run_id, run_started_at, "completed", total_records, 0, watermark)
        dbutils.notebook.exit("NO_CHUNKS")  # noqa: F821

    if rows_written == 0 and all_failed_er_numbers:
        log.error("All embeddings failed across all batches — pipeline aborting")
        write_run_log(run_id, run_started_at, "failed", total_records, 0, watermark)
        raise RuntimeError("All embeddings failed")

    if not new_watermark:
        new_watermark = watermark  # no change if source has no sys_updated_on

    # VS Sync — best-effort: Delta data is already persisted, so a VS failure
    # should not prevent the run log from being written or the job from
    # reporting success.  The next run (or a manual sync) will pick it up.
    try:
        sync_vector_search()
    except Exception as vs_err:
        log.error(f"Vector Search sync failed (non-fatal): {vs_err}")
        log.warning("Delta data was written successfully — VS index can be synced manually or on next run")

    # Write run log
    write_run_log(run_id, run_started_at, "completed", len(df), rows_written, new_watermark)

except Exception as exc:
    _pipeline_failed = True
    log.error(f"Pipeline failed: {exc}")
    try:
        _n_records = len(df) if "df" in dir() else 0
        _wm = watermark if "watermark" in dir() else None
        write_run_log(run_id, run_started_at, "failed", _n_records, rows_written, _wm)
    except Exception as log_err:
        log.warning(f"Failed to write run log on error path: {log_err}")
    raise

elapsed = time.time() - start_time
log.info("=" * 60)
log.info(f"ER Ingestion Pipeline — DONE in {elapsed:.1f}s")
log.info(f"  Records: {total_records if 'total_records' in dir() else len(df)}, Written: {rows_written}")
log.info("=" * 60)

dbutils.notebook.exit(json.dumps({  # noqa: F821
    "records": total_records if "total_records" in dir() else len(df),
    "rows_written": rows_written,
    "elapsed_seconds": round(elapsed, 1),
}))
