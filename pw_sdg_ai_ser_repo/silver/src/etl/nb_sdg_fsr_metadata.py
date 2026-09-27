# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_metadata — Process 1: Metadata Extraction & Registration (Silver)
#
# Discovers new PDFs in source volumes, extracts page-1 metadata via
# pdfplumber, normalizes fields via LLM, enriches with IBAT + Event Vision,
# and writes results to the metadata registry table.
#
# document_id (UUID stem) is PK, pdf_name is derived. Statuses: pending / completed / failed.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pdfplumber

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../common/fsr_config

# COMMAND ----------

import json, time, re, logging, hashlib
from collections import defaultdict, Counter
from pathlib import Path
from datetime import datetime, timezone

import requests
import pdfplumber
import pandas as pd

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, trim, concat, lit, upper, expr,
    regexp_replace, current_timestamp,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType,
    TimestampType, IntegerType,
)

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.p1.metadata")

# COMMAND ----------

log.info("=== Process 1 — Metadata Extraction ===")
log.info(f"  Metadata table : {METADATA_TABLE}")
log.info(f"  Volumes        : {PDF_VOLUME_PATHS}")
if not PDF_VOLUME_PATHS:
    raise ValueError(
        "FSR_SOURCE_VOLUME_PATHS job parameter is required "
        "(comma-separated full /Volumes/... paths)"
    )
log.info(f"  LLM model      : {LLM_MODEL}")
log.info(f"  Batch size     : {P1_BATCH_SIZE}")
log.info(f"  Max PDFs       : {P1_MAX_PDFS or 'unlimited (production)'}")
log.info(f"  Commit batch   : {P1_COMMIT_BATCH or 'all-at-once'}")
if TARGET_PDF_NAMES:
    log.info(f"  Target PDFs    : {len(TARGET_PDF_NAMES)} (DEBUG OVERRIDE — only these docs will be processed)")
else:
    log.info(f"  Target PDFs    : all eligible")
log.info(f"  Max retries    : {P1_MAX_RETRIES}")
log.info(f"  FORCE_RESET    : {FORCE_RESET}")
log.info(f"  LLM base URL   : {LITELLM_BASE_URL}")
log.info(f"  API key set    : {bool(LITELLM_API_KEY)}")
log.info(f"  jb_env         : {JB_ENV or 'unset'}")
log.info(f"  Multi-ESN      : enabled={FSR_MULTI_ESN_ENABLED}, dry_run={FSR_MULTI_ESN_DRY_RUN}")
if LLM_VERIFY_SSL is False:
    log.warning("TLS certificate verification is DISABLED for LLM calls (FSR_LLM_VERIFY_SSL=false)")
elif isinstance(LLM_VERIFY_SSL, str):
    log.info(f"Using custom CA bundle for LLM calls: {LLM_VERIFY_SSL}")

target_pdf_names = set(TARGET_PDF_NAMES or [])

# COMMAND ----------

# ── Identify already-known documents (skip if FORCE_RESET) ──────────────────
existing_doc_ids = set()
if not FORCE_RESET:
    existing_df = spark.sql(f"SELECT DISTINCT document_id FROM {METADATA_TABLE}")
    existing_doc_ids = {row.document_id for row in existing_df.collect()}
    log.info(f"Existing docs in table: {len(existing_doc_ids)} (will be skipped)")
else:
    if JB_ENV == "prod":
        raise ValueError("FORCE_RESET is not allowed when jb_env=prod")
    spark.sql(f"TRUNCATE TABLE {METADATA_TABLE}")
    log.info("FORCE_RESET: table truncated, scanning all files")

# ── Scan volumes for new PDFs ───────────────────────────────────────────────
# Two discovery paths (discovery is now additive — runs regardless of backlog):
#   1. TARGET mode — FSR_TARGET_PDF_NAMES set: direct path stat, no volume scan
#   2. DISCOVERY mode — Spark SQL LIST (parallelized, handles large volumes);
#      always runs when not in TARGET or FORCE_RESET mode, even with backlog

from pyspark.sql.functions import (
    lower as _lower,
    regexp_extract as _regexp_extract,
    regexp_replace as _regexp_replace,
)

def _normalize_list_df(df):
    """LIST '<volume>' returns either `modificationTime` (Timestamp) on older
    DBR runtimes or `modification_time` (bigint epoch ms) on DBR 18+. Normalize
    to a single `mod_time_ms` bigint column so downstream code is uniform."""
    from pyspark.sql.functions import col as _col, unix_millis as _unix_millis
    cols = set(df.columns)
    if "modificationTime" in cols:
        return df.withColumn("mod_time_ms", _unix_millis(_col("modificationTime")))
    if "modification_time" in cols:
        return df.withColumn("mod_time_ms", _col("modification_time").cast("long"))
    raise ValueError(f"LIST output missing modification time column; got {df.columns}")

new_files = []  # TARGET mode only; DISCOVERY/FORCE_RESET use discovered_df below
discovered_df = None  # Spark DataFrame with stub schema (DISCOVERY/FORCE_RESET)
_pending_count = 0
_discovery_mode = "unknown"
_discovery_start = time.time()
_existing_target_hits = set()

if target_pdf_names and not FORCE_RESET:
    # ── Path 1: TARGET mode — direct lookup, O(n) where n = target count ──
    _discovery_mode = "target"
    log.info(f"Target mode: looking up {len(target_pdf_names)} specific doc(s)")
    for doc_id in target_pdf_names:
        if doc_id in existing_doc_ids:
            log.info(f"  {doc_id}: already in table, skipping")
            _existing_target_hits.add(doc_id)
            continue
        found = False
        # Volume files may be stored with or without `.pdf` extension:
        #   - FieldVision (`fv_field_service_report`): no extension (UUID = filename)
        #   - Manual reports (`ecrt_reports`): legacy `.pdf` suffix
        # Try the no-extension form first (most common in prod), then fall back.
        for vol in PDF_VOLUME_PATHS:
            for candidate in (f"{vol}/{doc_id}", f"{vol}/{doc_id}.pdf"):
                try:
                    info = dbutils.fs.ls(candidate)  # noqa: F821  — single-file stat, instant
                    path = info[0].path.replace("dbfs:", "") if info[0].path.startswith("dbfs:") else info[0].path
                    new_files.append({
                        "path": path,
                        "name": info[0].name,
                        "size": info[0].size,
                        "mod_time": info[0].modificationTime,
                    })
                    found = True
                    break
                except Exception:
                    continue
            if found:
                break
        if not found:
            log.warning(f"  {doc_id}: not found in any configured volume")

elif not FORCE_RESET:
    # ── DISCOVERY mode — additive Spark SQL LIST (parallelized) ──────────
    # Always runs, even when backlog exists. The prior "backlog gate" caused
    # newly landed files to remain invisible until the queue drained.
    _discovery_mode = "discovery"
    _pending_count = spark.sql(f"""
        SELECT COUNT(*) AS n FROM {METADATA_TABLE}
        WHERE metadata_status IN ('{MetadataStatus.PENDING}', '{MetadataStatus.FAILED}')
    """).first().n
    if _pending_count > 0:
        log.info(f"Existing backlog: {_pending_count} pending/failed rows (discovery runs additively)")

    existing_ids_df = spark.sql(f"SELECT document_id FROM {METADATA_TABLE}")
    skip_suffixes_pattern = "|".join(
        s.replace(".", r"\.") for s in SKIP_SUFFIXES
    )

    _per_vol_dfs = []
    for vol in PDF_VOLUME_PATHS:
        log.info(f"Scanning (LIST): {vol}")
        try:
            list_df = _normalize_list_df(spark.sql(f"LIST '{vol}'"))
            vol_stub_df = (
                list_df
                .filter(~_lower("name").rlike(f"({skip_suffixes_pattern})$"))
                .filter(~_lower("name").rlike(r"/$"))
                # document_id = lowercase filename with `.pdf` stripped if present.
                # FieldVision files have no extension; manual reports (.pdf) lose suffix.
                .withColumn("document_id", _lower(_regexp_replace("name", r"(?i)\.pdf$", "")))
                .join(existing_ids_df, "document_id", "left_anti")
                .select(
                    col("document_id"),
                    concat(lit(f"{vol}/"), col("name")).alias("volume_path"),
                    col("size").cast("long").alias("file_size_bytes"),
                    expr("timestamp_millis(mod_time_ms)").alias("file_last_modified"),
                    lit(MetadataStatus.PENDING).alias("metadata_status"),
                    lit(ChunkStatus.PENDING).alias("chunk_status"),
                )
            )
            _per_vol_dfs.append(vol_stub_df)
        except Exception as e:
            log.warning(f"Cannot list volume {vol}: {e}")
            continue

    if _per_vol_dfs:
        from functools import reduce as _reduce
        from pyspark.sql.window import Window as _Window
        from pyspark.sql.functions import row_number as _row_number, desc as _desc, count as _count
        discovered_df = _reduce(lambda a, b: a.unionByName(b), _per_vol_dfs)
        # Dedupe same document_id appearing in multiple volumes. Keep the most
        # recently modified copy (tie-break: largest size, then volume_path).
        _dedupe_w = _Window.partitionBy("document_id").orderBy(
            _desc("file_last_modified"), _desc("file_size_bytes"), col("volume_path")
        )
        _dup_w = _Window.partitionBy("document_id")
        discovered_df = (
            discovered_df
            .withColumn("_dup_count", _count(lit(1)).over(_dup_w))
            .withColumn("_rn", _row_number().over(_dedupe_w))
        )
        _total_rows = discovered_df.count()
        _dup_rows = discovered_df.filter(col("_dup_count") > 1).count()
        log.info(f"Cross-volume dedup (discovery): scanned {_total_rows} row(s), {_dup_rows} duplicate(s) to drop")
        if _dup_rows > 0:
            _sample = (
                discovered_df.filter(col("_dup_count") > 1)
                .select("document_id", "volume_path", "file_last_modified",
                        "file_size_bytes", col("_rn"))
                .orderBy("document_id", "_rn")
                .limit(20)
                .collect()
            )
            for r in _sample:
                decision = "KEEP" if r["_rn"] == 1 else "DROP"
                log.info(f"  [{decision}] {r['document_id']}  ←  {r['volume_path']}  "
                         f"(mtime={r['file_last_modified']}, size={r['file_size_bytes']})")
        discovered_df = discovered_df.filter(col("_rn") == 1).drop("_rn", "_dup_count")

else:
    # ── FORCE_RESET — full discovery via Spark LIST (table just truncated) ───
    _discovery_mode = "force_reset"
    skip_suffixes_pattern = "|".join(
        s.replace(".", r"\.") for s in SKIP_SUFFIXES
    )

    _per_vol_dfs = []
    for vol in PDF_VOLUME_PATHS:
        log.info(f"Scanning (LIST, FORCE_RESET): {vol}")
        try:
            list_df = _normalize_list_df(spark.sql(f"LIST '{vol}'"))
            vol_stub_df = (
                list_df
                .filter(~_lower("name").rlike(f"({skip_suffixes_pattern})$"))
                .filter(~_lower("name").rlike(r"/$"))
                .withColumn("document_id", _lower(_regexp_replace("name", r"(?i)\.pdf$", "")))
                .select(
                    col("document_id"),
                    concat(lit(f"{vol}/"), col("name")).alias("volume_path"),
                    col("size").cast("long").alias("file_size_bytes"),
                    expr("timestamp_millis(mod_time_ms)").alias("file_last_modified"),
                    lit(MetadataStatus.PENDING).alias("metadata_status"),
                    lit(ChunkStatus.PENDING).alias("chunk_status"),
                )
            )
            _per_vol_dfs.append(vol_stub_df)
        except Exception as e:
            log.warning(f"Cannot list volume {vol}: {e}")
            continue

    if _per_vol_dfs:
        from functools import reduce as _reduce
        from pyspark.sql.window import Window as _Window
        from pyspark.sql.functions import row_number as _row_number, desc as _desc, count as _count
        discovered_df = _reduce(lambda a, b: a.unionByName(b), _per_vol_dfs)
        # Dedupe same document_id appearing in multiple volumes (FORCE_RESET path).
        _dedupe_w = _Window.partitionBy("document_id").orderBy(
            _desc("file_last_modified"), _desc("file_size_bytes"), col("volume_path")
        )
        _dup_w = _Window.partitionBy("document_id")
        discovered_df = (
            discovered_df
            .withColumn("_dup_count", _count(lit(1)).over(_dup_w))
            .withColumn("_rn", _row_number().over(_dedupe_w))
        )
        _total_rows = discovered_df.count()
        _dup_rows = discovered_df.filter(col("_dup_count") > 1).count()
        log.info(f"Cross-volume dedup (FORCE_RESET): scanned {_total_rows} row(s), {_dup_rows} duplicate(s) to drop")
        if _dup_rows > 0:
            _sample = (
                discovered_df.filter(col("_dup_count") > 1)
                .select("document_id", "volume_path", "file_last_modified",
                        "file_size_bytes", col("_rn"))
                .orderBy("document_id", "_rn")
                .limit(20)
                .collect()
            )
            for r in _sample:
                decision = "KEEP" if r["_rn"] == 1 else "DROP"
                log.info(f"  [{decision}] {r['document_id']}  ←  {r['volume_path']}  "
                         f"(mtime={r['file_last_modified']}, size={r['file_size_bytes']})")
        discovered_df = discovered_df.filter(col("_rn") == 1).drop("_rn", "_dup_count")

_discovery_elapsed = time.time() - _discovery_start

if target_pdf_names:
    found_pdf_names = {Path(nf["path"]).stem.lower() for nf in new_files}
    # Exclude targets that were intentionally skipped because they already
    # exist in the table; they are not "missing" from volumes.
    missing_pdf_names = sorted(target_pdf_names - found_pdf_names - _existing_target_hits)
    if missing_pdf_names:
        log.warning(f"Target PDFs not found in configured volumes: {missing_pdf_names}")

# COMMAND ----------

# ── Unify discovery output into a single Spark stub DataFrame ──────────────
# TARGET mode populates `new_files` driver-side (small N, per-doc warnings).
# DISCOVERY/FORCE_RESET populate `discovered_df` Spark-side (avoids collect at scale).
stub_schema = StructType([
    StructField("document_id", StringType(), False),
    StructField("volume_path", StringType(), False),
    StructField("file_size_bytes", LongType(), True),
    StructField("file_last_modified", TimestampType(), True),
    StructField("metadata_status", StringType(), False),
    StructField("chunk_status", StringType(), False),
])

stub_df = None
if target_pdf_names and new_files:
    stub_rows = []
    for nf in new_files:
        document_id = Path(nf["path"]).stem.lower()
        mod_ts = datetime.fromtimestamp(nf["mod_time"] / 1000, tz=timezone.utc)
        stub_rows.append({
            "document_id": document_id,
            "volume_path": nf["path"],
            "file_size_bytes": nf["size"],
            "file_last_modified": mod_ts,
            "metadata_status": MetadataStatus.PENDING,
            "chunk_status": ChunkStatus.PENDING,
        })
    stub_df = spark.createDataFrame(stub_rows, schema=stub_schema)
elif discovered_df is not None:
    stub_df = discovered_df

# Apply P1_MAX_PDFS cap on Spark side to avoid materializing the full set.
if stub_df is not None and P1_MAX_PDFS:
    stub_df = stub_df.limit(P1_MAX_PDFS)

if stub_df is None:
    log.info(f"Discovery mode: {_discovery_mode} — 0 files found in {_discovery_elapsed:.1f}s")
    log.info("No new files discovered — skipping stub MERGE")
else:
    # Avoid pre-MERGE count() / peek — both would re-trigger the full LIST
    # scan on serverless (where .cache() is unreliable). Counts are logged
    # from the metadata table after the MERGE instead.
    log.info(f"Discovery mode: {_discovery_mode} — scan completed in {_discovery_elapsed:.1f}s (counts emitted after MERGE)")
    log.info(f"P1_MAX_PDFS cap: {P1_MAX_PDFS or 'unlimited'}")

    stub_df.createOrReplaceTempView("_fsr_stubs")

    # ── MERGE stub rows into metadata table ─────────────────────────────────────
    # WHEN MATCHED guard: only refresh file mtime/size for rows still in
    # flight (e.g. status='pending'). Skip rows already 'completed' (don't
    # re-process) and 'failed' (let the retry cap decide). Without this
    # guard, the discovery re-stub would reset completed rows back to
    # pending on every run.
    merge_sql = f"""
    MERGE INTO {METADATA_TABLE} AS tgt
    USING _fsr_stubs AS src
    ON tgt.document_id = src.document_id
    WHEN MATCHED AND tgt.metadata_status NOT IN ('{MetadataStatus.COMPLETED}', '{MetadataStatus.FAILED}') THEN UPDATE SET
        tgt.file_last_modified = src.file_last_modified,
        tgt.file_size_bytes    = src.file_size_bytes
    WHEN NOT MATCHED THEN INSERT (
        document_id, volume_path,
        file_size_bytes, file_last_modified,
        metadata_status, chunk_status,
        ingested_at
    ) VALUES (
        src.document_id, src.volume_path,
        src.file_size_bytes, src.file_last_modified,
        src.metadata_status, src.chunk_status,
        current_timestamp()
    )
    """
    spark.sql(merge_sql)

count = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_TABLE}").first().n
pending = spark.sql(f"""
    SELECT COUNT(*) AS n FROM {METADATA_TABLE}
    WHERE metadata_status = '{MetadataStatus.PENDING}'
""").first().n
log.info(f"Table state — Total rows: {count}, Pending: {pending}")

# COMMAND ----------

# ── Load pending rows for extraction ────────────────────────────────────────
# Always process all 'pending' rows. Re-process 'failed' rows only while
# their lifetime metadata_retry_count is below P1_MAX_RETRIES — docs that
# exhaust the cap stay in metadata_status='failed' permanently and consume
# zero compute on subsequent runs (mirrors P2's chunk_retry_count gate).
pending_rows = spark.sql(f"""
    SELECT document_id, volume_path
    FROM {METADATA_TABLE}
    WHERE metadata_status = '{MetadataStatus.PENDING}'
""").collect()

failed_rows = spark.sql(f"""
    SELECT document_id, volume_path
    FROM {METADATA_TABLE}
    WHERE metadata_status = '{MetadataStatus.FAILED}'
      AND COALESCE(metadata_retry_count, 0) < {P1_MAX_RETRIES}
""").collect()

pending_rows = pending_rows + failed_rows

# When FSR_TARGET_PDF_NAMES is set, restrict the work queue to just those docs.
# Without this filter, TARGET only scopes the volume *discovery* step — the
# work queue would still pick up the entire pending + retry-eligible backlog,
# which surprises operators trying to validate a small cohort.
if target_pdf_names:
    _before = len(pending_rows)
    pending_rows = [r for r in pending_rows if r.document_id in target_pdf_names]
    log.info(f"Target mode: filtered work queue from {_before} to {len(pending_rows)} doc(s) matching FSR_TARGET_PDF_NAMES")

# Apply FSR_MAX_PDFS cap to the total processing queue (not just discovery)
if P1_MAX_PDFS and len(pending_rows) > P1_MAX_PDFS:
    pending_rows = pending_rows[:P1_MAX_PDFS]

log.info(f"{len(pending_rows)} documents to process (pending + failed under retry cap of {P1_MAX_RETRIES}, cap={P1_MAX_PDFS or 'unlimited'})")

# Generate a run_id used for per-commit-batch audit rows in the run log table.
import uuid as _uuid
P1_RUN_ID = _uuid.uuid4().hex
log.info(f"  P1 run_id      : {P1_RUN_ID}")

# Split into commit batches so progress is saved incrementally.
# Each batch: extract → LLM → enrich → MERGE.
commit_size = P1_COMMIT_BATCH if P1_COMMIT_BATCH else len(pending_rows)
total_batches = (len(pending_rows) + commit_size - 1) // commit_size if commit_size else 1
log.info(f"Processing in {total_batches} commit batch(es) of {commit_size}")

grand_success = 0
grand_fail = 0

# COMMAND ----------

# ── LLM prompts & helper (from DS reference pipeline) ──────────────────────

SYSTEM_PROMPT = (
    "You are an expert in structuring technical data. "
    "Your task is to process the provided input json and output a structured/normalized "
    "JSON format according to user instructions. Focus on clarity, completeness, and "
    "following the JSON schema provided. Do not include any internal reasoning or system "
    "details in the output. Ensure all responses are fact-based, and safe. "
    "Follow responsible AI principles without over-restricting harmless tasks."
)

NORMALIZATION_PROMPT_SUFFIX = """Your task is to process JSON input and output a normalized JSON format
with the following fields only:

ESN, Equipment Sys ID, Equipment Type, Equipment Class / Code, Event Type,
EV Project ID, EV Equipment Event ID, OFS Event ID, FSP project ID, Project ID, PDF Name / path / identifier,
FSR Number (#), Report Issued Date, Outage Start Date, Outage End Date.

If the PDF field contains an Oracle Project Id, map it to OFS Event ID only. But do not include field values that start with "EV" and "EVP" under OFS Event ID.
Map the PDF field containing "EV-" to EV Equipment Event ID only.
Map the PDF field containing "EVP-" to EV Project ID only.
Map the PDF field containing "SY" to Equipment Sys ID only.
If the PDF field contains a Field Service Project Id or "FSP-", map it to FSP project ID only.
If the PDF field contains a project id that starts with "XXX" (i.e. A-, C-, etc.), map it to Project ID only.

**Strictly adhere to the following instructions while extracting and normalizing data**:
Do not miss any information that is present in the input and try to be as much accurate as possible in retrieving the values for the above fields.
**When extracting data, if a record contains multiple distinct values across ESN and Equipment Sys ID fields, split the record into separate rows by pairing values positionally (first with first, second with second, etc.), while duplicating all other field values unchanged (except for Equipment Type and Equipment Class / Code). Set the Equipment Type and Equipment Class / Code field values to empty strings in the split rows. Do not split or omit any parts for other field values even if multiple distinct values are present.**
If no exact match is found for a field, see if you can infer it from similar labels or context.
If no relevant information is found, output it as an empty string.
Consider as many records as provided in the input batch. Do not omit any records.
Do not include any reasoning or commentary, only valid JSON output.
All dates must be normalized to YYYY-MM-DD format.

For the field Event Type, only use values from the following allowed list:
Training Cost Accumulation, Unusual, Training Open Enrollment - Costs, TX Repairs,
Major Inspection (Field Rewind), Major Inspection (MI), Tooling(GE), C Inspection,
null, Training On Site Training, A Inspection, Services Warranty,
Borescope Inspection (BI), Major Inspection (Robotic), Performance Testing,
Upgrade - PMO Billing only, Digital, Non CSA-MMP Billing,
Hot Gas Path Inspection (HGPI), Initial Spares, Combustion Inspection (CI),
Training Open Enrollment - Billing, Stand Alone Small Upgrade, Large Call-Out,
On Site Services, Call-Out, TX Parts, B Inspection, Training Simulation,
Post COD New Unit Warranty, Major Inspection (Rotor Out), Stand Alone Large Upgrade,
OP Spares, Remote Diagnostics, Minor Inspection, Onsite Services SP,
Major Inspection (Stator Rewind)
"""


def _strip_json_fences(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _sanitize_pdf_name_part(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    # Keep a filesystem-safe human-readable fallback token.
    text = re.sub(r"[^A-Za-z0-9._ -]", "", text)
    text = text.replace(" ", "_")
    return text.strip("_")


def _build_contextual_pdf_name(rec):
    parts = [
        _sanitize_pdf_name_part(rec.get("title")),
        _sanitize_pdf_name_part(rec.get("customer")),
        _sanitize_pdf_name_part(rec.get("equipment_type")),
        _sanitize_pdf_name_part(rec.get("esn")),
        _sanitize_pdf_name_part(rec.get("outage_start_date")),
    ]
    parts = [p for p in parts if p]
    return "_".join(parts) if parts else None


def _extract_esn_from_page1_text(text):
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text)
    patterns = [
        r"(?i)\bESN(?:\s*/\s*SY)?\s*[:#-]?\s*([A-Z0-9-]{4,})",
        r"(?i)\bEQUIP(?:MENT)?\s+SERIAL\s+(?:NO|NUMBER)?\s*[:#-]?\s*([A-Z0-9-]{4,})",
    ]
    for pat in patterns:
        m = re.search(pat, cleaned)
        if m:
            return m.group(1).strip()
    return ""


# ── TOC-based document summary extraction helpers ───────────────────────────
DOC_SUMMARY_PATTERN = re.compile(r"\bexecutive\s+summary\b|\binspection\s+summary\b|\bsummary\b", re.IGNORECASE)
DOC_SUMMARY_NOISE_PATTERN = re.compile(
    r"^[\s_\-\.\|]*$"
    r"|^table\s+of\s+contents?$"
    r"|^contents?$",
    re.IGNORECASE,
)
DOC_SUMMARY_ROW_TOLERANCE = 3
DOC_SUMMARY_FOOTER_CROP_RATIO = 0.90
DOC_SUMMARY_HEADER_ZONE_RATIO = 0.10
DOC_SUMMARY_FOOTER_ZONE_RATIO = 0.10


def _is_doc_summary(title: str) -> bool:
    return bool(DOC_SUMMARY_PATTERN.search((title or "").strip()))


def _build_doc_summary_sections(toc_entries, total_pages):
    sections = []
    for i, (title, start_page) in enumerate(toc_entries):
        if _is_doc_summary(title):
            end_page = toc_entries[i + 1][1] - 1 if i + 1 < len(toc_entries) else total_pages
            sections.append({"title": title, "start_page": start_page, "end_page": end_page})
    return sections


def _extract_words_as_rows(page):
    words = page.extract_words(
        x_tolerance=3,
        y_tolerance=3,
        keep_blank_chars=False,
        use_text_flow=False,
    )
    if not words:
        return []

    rows = defaultdict(list)
    for w in words:
        rows[round(w["top"] / DOC_SUMMARY_ROW_TOLERANCE)].append(w)
    return [sorted(rows[k], key=lambda w: w["x0"]) for k in sorted(rows)]


def _detect_page_offset(pdf):
    offsets = []
    for i in range(min(10, len(pdf.pages))):
        page = pdf.pages[i]
        h = page.height
        for bbox in (
            (0, 0, page.width, h * DOC_SUMMARY_HEADER_ZONE_RATIO),
            (0, h * (1 - DOC_SUMMARY_FOOTER_ZONE_RATIO), page.width, h),
        ):
            text = page.within_bbox(bbox).extract_text() or ""
            for token in text.split():
                token = token.strip(".,|-()")
                if re.fullmatch(r"\d{1,4}", token):
                    printed = int(token)
                    if printed > 0:
                        offsets.append((i + 1) - printed)
    return Counter(offsets).most_common(1)[0][0] if offsets else 0


def _extract_toc_entries(pdf) -> tuple:
    """Returns (toc_entries, total_pages). Accepts an already-open pdfplumber PDF object."""
    entries, seen = [], set()
    TOC_HEADING = re.compile(r"table\s+of\s+contents?", re.IGNORECASE)

    total_pages = len(pdf.pages)

    # Find pages that carry a "TABLE OF CONTENTS" heading.
    # Fall back to first 3 pages if none found.
    candidate_pages = [
        i for i in range(min(5, total_pages))
        if TOC_HEADING.search(pdf.pages[i].extract_text() or "")
    ]
    if not candidate_pages:
        candidate_pages = list(range(min(3, total_pages)))

    for page_num in candidate_pages:
        page    = pdf.pages[page_num]
        split_x = page.width * 0.75
        cropped = page.within_bbox((0, 0, page.width, page.height * DOC_SUMMARY_FOOTER_CROP_RATIO))
        for row in _extract_words_as_rows(cropped):
            left  = [w["text"] for w in row if w["x0"] <  split_x]
            right = [w["text"] for w in row if w["x0"] >= split_x]
            title       = " ".join(left).strip()
            right_clean = re.sub(r"^[\s_\.]+", "", " ".join(right).strip())

            # Fallback: if nothing landed in the right bucket, the page number
            # may be closer to the centre than split_x. Peel the last token
            # off the title if it is a pure number.
            if not right_clean and title:
                tokens = title.split()
                if re.fullmatch(r"\d+", tokens[-1]):
                    right_clean = tokens[-1]
                    title       = " ".join(tokens[:-1]).strip()

            if not title or DOC_SUMMARY_NOISE_PATTERN.match(title):
                continue
            if not re.fullmatch(r"\d+", right_clean):
                continue
            key = (title, int(right_clean))
            if key not in seen:
                seen.add(key)
                entries.append(key)
    return entries, total_pages


def _extract_section_text(pdf, start_page, end_page, offset):
    total = len(pdf.pages)
    parts = []
    for p in range(start_page, end_page + 1):
        idx = p - 1 + offset
        if 0 <= idx < total:
            cropped = pdf.pages[idx].within_bbox(
                (0, 0, pdf.pages[idx].width, pdf.pages[idx].height * DOC_SUMMARY_FOOTER_CROP_RATIO)
            )
            text = (cropped.extract_text() or "").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def get_combined_summary_from_pdf(pdf):
    """Returns (summary_text_or_empty, status) for the opened PDF object."""
    try:
        toc_entries, total_pages = _extract_toc_entries(pdf)
        if not toc_entries:
            return "", "no_toc"

        sections = _build_doc_summary_sections(toc_entries, total_pages)
        if not sections:
            return "", "no_summary_section"

        offset = _detect_page_offset(pdf)
        for section in sections:
            section["text"] = _extract_section_text(pdf, section["start_page"], section["end_page"], offset)

        combined = "\n\n".join(section["text"] for section in sections if section.get("text"))
        if combined.strip():
            return combined, "extracted"
        return "", "empty_after_extraction"
    except Exception:
        return "", "failed"


def call_llm(prompt):
    base = LITELLM_BASE_URL.rstrip("/")
    urls = [f"{base}/chat/completions", f"{base}/v1/chat/completions"]
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {LITELLM_API_KEY}",
        "Content-Type": "application/json",
    }
    # Approx prompt size for diagnostics (chars; bytes ~= chars for ASCII)
    prompt_chars = len(prompt) + len(SYSTEM_PROMPT)
    last_err = None
    for attempt in range(1, 4):
        for url in urls:
            try:
                resp = requests.post(url, headers=headers, json=payload,
                                     timeout=120, verify=LLM_VERIFY_SSL)
                if resp.status_code == 404:
                    continue
                if not resp.ok:
                    # Capture LiteLLM/upstream error body so we can see the real reason
                    body_snippet = (resp.text or "")[:2000]
                    req_id = (
                        resp.headers.get("x-request-id")
                        or resp.headers.get("x-litellm-call-id")
                        or resp.headers.get("x-litellm-request-id")
                        or ""
                    )
                    log.error(
                        f"LLM HTTP {resp.status_code} from {url} "
                        f"(model={LLM_MODEL}, prompt_chars={prompt_chars}, "
                        f"req_id={req_id}) body={body_snippet}"
                    )
                    # Fall back to the alternate URL for any gateway/ingress error
                    # (5xx with no x-litellm-* headers indicates request never
                    # reached LiteLLM — likely wrong path on prod gateway).
                    if 500 <= resp.status_code < 600 and not req_id:
                        last_err = requests.HTTPError(
                            f"{resp.status_code} {resp.reason} url={url} body={body_snippet}"
                        )
                        continue
                    raise requests.HTTPError(
                        f"{resp.status_code} {resp.reason} url={url} "
                        f"model={LLM_MODEL} prompt_chars={prompt_chars} "
                        f"req_id={req_id} body={body_snippet}"
                    )
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                last_err = e
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    continue
                if attempt == 3:
                    raise
                wait = 5 * (2 ** (attempt - 1))
                log.warning(f"LLM attempt {attempt} failed ({e}); retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"LLM call failed after all retries: {last_err}")


COLUMN_MAP = {
    "ESN": "esn",
    "Equipment Sys ID": "equipment_sys_id",
    "Equipment Type": "equipment_type",
    "Equipment Class / Code": "equipment_class_code",
    "Event Type": "event_type",
    "EV Project ID": "ev_project_id",
    "EV Equipment Event ID": "ev_equipment_event_id",
    "OFS Event ID": "ofs_event_id",
    "FSP project ID": "fsp_project_id",
    "Project ID": "xxx_project_id",
    "PDF Name / path / identifier": "_volume_path",
    "FSR Number (#)": "fsr_number",
    "Report Issued Date": "report_issued_date",
    "Outage Start Date": "outage_start_date",
    "Outage End Date": "outage_end_date",
}

# COMMAND ----------

# ── Load enrichment reference tables (once, before commit-batch loop) ───────
from pyspark.sql.types import StringType

enrichment_enabled = True
ibat_df = None
ev_sot_df = None

try:
    ibat_df = spark.read.table(IBAT_EQUIPMENT_TABLE).select(
        upper(trim(col("equipment_sys_id"))).cast(StringType()).alias("ibat_equipment_sys_id"),
        upper(trim(col("equip_serial_number"))).cast(StringType()).alias("ibat_equip_serial_number"),
        col("equipment_type").cast(StringType()).alias("ibat_equipment_type"),
        col("equipment_sub_class").cast(StringType()).alias("ibat_equipment_code"),
    )
    ibat_df.limit(1).count()
    log.info(f"IBAT loaded: {IBAT_EQUIPMENT_TABLE}")
except Exception as e:
    log.warning(f"IBAT not accessible ({e}). Continuing without IBAT enrichment.")
    enrichment_enabled = False

try:
    ev_sot_df = spark.read.table(EVENT_VISION_SOT_TABLE).select(
        col("ev_project_id").cast(StringType()).alias("sot_ev_project_id"),
        col("ev_equipment_event_id").cast(StringType()).alias("sot_ev_equipment_event_id"),
        col("ev_gtm_id").cast(StringType()).alias("sot_ev_gtm_id"),
        col("fsp_project_id").cast(StringType()).alias("sot_fsp_project_id"),
        col("ev_event_type").cast(StringType()).alias("sot_event_type"),
        col("p6_outage_start_date").cast(StringType()).alias("sot_outage_start_date"),
        col("p6_outage_end_date").cast(StringType()).alias("sot_outage_end_date"),
    )
    ev_sot_df.limit(1).count()
    log.info(f"Event Vision loaded: {EVENT_VISION_SOT_TABLE}")
except Exception as e:
    log.warning(f"Event Vision not accessible ({e}). Continuing without EV enrichment.")
    if not ibat_df:
        enrichment_enabled = False

# Pre-load pdf_ref for pdf_name derivation (once)
_pdf_ref_loaded = False
_pdf_ref_esn_map = {}  # doc_id (lowercase, no ext) → set of ESNs from fsr_pdf_ref
try:
    pdf_ref_df = spark.read.table(FSR_PDF_REF_VIEW).select(
        col("s3_filename").alias("ref_s3_filename"),
        col("PDF_name").alias("ref_pdf_name"),
    ).dropDuplicates(["ref_s3_filename"])
    pdf_ref_df.createOrReplaceTempView("_fsr_pdf_ref_deduped")
    _pdf_ref_loaded = True
    log.info(f"PDF ref loaded: {FSR_PDF_REF_VIEW}")

    # Build ESN map: doc_id → {esn1, esn2, ...} for multi-ESN validation
    _esn_rows = spark.sql(f"""
        SELECT LOWER(TRIM(s3_filename)) AS doc_id, esn
        FROM {FSR_PDF_REF_VIEW}
        WHERE esn IS NOT NULL AND TRIM(esn) != ''
    """).collect()
    for row in _esn_rows:
        _pdf_ref_esn_map.setdefault(row.doc_id, set()).add(row.esn.strip())
    log.info(f"PDF ref ESN map: {len(_pdf_ref_esn_map)} docs with ESN entries")
except Exception as e:
    log.warning(f"PDF ref not accessible ({e}). Will use volume_path fallback for pdf_name.")

# COMMAND ----------

# ── Extract first-page fields + page count from each PDF ───────────────────
# Outer loop processes commit_size docs at a time
for cb_idx in range(total_batches):
    cb_start = cb_idx * commit_size
    cb_end = min(cb_start + commit_size, len(pending_rows))
    batch_rows = pending_rows[cb_start:cb_end]
    log.info(f"\n{'='*60}")
    log.info(f"COMMIT BATCH {cb_idx+1}/{total_batches}: docs {cb_start+1}–{cb_end} ({len(batch_rows)} docs)")
    log.info(f"{'='*60}")

    _cb_wallclock_start = time.time()    # stable batch-level timer for run-log audit row
    extractions = {}  # document_id -> {title, llm_fields, page_count}
    failures = {}     # document_id -> error_msg
    doc_summary_failures = []  # list of (document_id, volume_path, status) for DQ log
    _phase_start = time.time()

    for row in batch_rows:
        document_id = row.document_id
        vol_path = row.volume_path
        try:
            with pdfplumber.open(vol_path) as pdf:
                page_count = len(pdf.pages)
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""

                lines = text.splitlines()

                # Title = lines before the first colon-delimited field
                title_lines = []
                for line in lines:
                    if ":" in line:
                        break
                    title_lines.append(line.strip())
                title = " ".join(title_lines).strip() or None

                # Key:value pairs for LLM normalization
                llm_fields = {"PDF Name / path / identifier": vol_path}
                current_key = None
                for line in lines:
                    if ":" in line:
                        parts = line.split(":", 1)
                        key = parts[0].strip()
                        value = parts[1].strip()
                        current_key = key
                        if key in llm_fields:
                            llm_fields[key] = f"{llm_fields[key]} | {value}"
                        else:
                            llm_fields[key] = value
                    elif current_key:
                        llm_fields[current_key] += " " + line.strip()

                extractions[document_id] = {
                    "title": title,
                    "llm_fields": llm_fields,
                    "page_count": page_count,
                    "page1_text": text,
                    "document_summary": None,
                }

                # Use TOC-based summary extraction flow for incremental docs.
                summary_text, summary_status = get_combined_summary_from_pdf(pdf)
                if summary_status == "extracted":
                    extractions[document_id]["document_summary"] = summary_text
                else:
                    log.info(f"  [DOC-SUMMARY] {document_id[:40]}: {summary_status}")
                    doc_summary_failures.append((document_id, vol_path, summary_status))

                log.info(f"  [OK] {document_id[:40]}  pages={page_count}  fields={len(llm_fields)}")

        except Exception as e:
            failures[document_id] = str(e)[:500]
            log.warning(f"  [FAIL] {document_id[:40]}: {e}")

    log.info(f"PDF extraction: {len(extractions)} ok, {len(failures)} failed in {time.time() - _phase_start:.1f}s")

    # ── Route doc-summary failures to DQ log (parity with backfill) ─────────
    # Backfill writes to fsr_data_quality_log with check_name='doc_summary_extraction'.
    # Incremental P1 mirrors that so monitoring queries see both code paths.
    if doc_summary_failures and DQ_LOG_TABLE:
        try:
            _now = datetime.now(timezone.utc)
            _dq_rows = []
            for _did, _vp, _status in doc_summary_failures:
                _dq_id = hashlib.md5(
                    f"{P1_RUN_ID}|{_did}|doc_summary_extraction".encode()
                ).hexdigest()
                _dq_rows.append({
                    "dq_id": _dq_id,
                    "run_id": P1_RUN_ID,
                    "document_id": _did,
                    "pdf_name": _vp,
                    "check_name": "doc_summary_extraction",
                    "severity": "WARN",
                    "failure_category": _status,
                    "detail": f"status={_status}"[:500],
                    "created_at": _now,
                })
            spark.createDataFrame(_dq_rows, schema=dq_log_schema()) \
                 .write.mode("append").saveAsTable(DQ_LOG_TABLE)
            log.info(f"DQ log: wrote {len(_dq_rows)} doc_summary_extraction WARN row(s) to {DQ_LOG_TABLE}")
        except Exception as _e:
            log.warning(f"DQ log write failed (non-blocking): {_e}")

    # ── Send extractions to LLM in batches ──────────────────────────────────
    _phase_start = time.time()
    doc_ids_ordered = list(extractions.keys())
    all_llm_fields = [extractions[did]["llm_fields"] for did in doc_ids_ordered]

    normalized_by_doc = {}  # document_id -> normalized dict
    llm_failures = {}       # document_id -> error

    for i in range(0, len(all_llm_fields), P1_BATCH_SIZE):
        batch_fields = all_llm_fields[i:i + P1_BATCH_SIZE]
        batch_doc_ids = doc_ids_ordered[i:i + P1_BATCH_SIZE]
        batch_num = (i // P1_BATCH_SIZE) + 1

        if i > 0 and P1_LLM_DELAY > 0:  # throttle between LLM batches if configured
            time.sleep(P1_LLM_DELAY)

        prompt = (
            f"Here is a JSON list of PDF fields:\n{json.dumps(batch_fields, indent=2)}\n\n"
            + NORMALIZATION_PROMPT_SUFFIX
        )

        try:
            log.info(f"[B{batch_num}] Sending {len(batch_fields)} records to LLM...")
            raw = call_llm(prompt)
            cleaned = _strip_json_fences(raw)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "FSR_data" in parsed:
                parsed = parsed["FSR_data"]
            if not isinstance(parsed, list):
                parsed = [parsed]
            log.info(f"[B{batch_num}] Got {len(parsed)} normalized rows")

            # Map LLM rows back to document_ids via volume_path
            path_to_doc = {}
            for did in batch_doc_ids:
                vol_path = extractions[did]["llm_fields"]["PDF Name / path / identifier"]
                path_to_doc[vol_path] = did

            for row in parsed:
                row_mapped = {COLUMN_MAP.get(k, k): v for k, v in row.items() if k in COLUMN_MAP}
                vol_path = row_mapped.pop("_volume_path", "")
                did = path_to_doc.get(vol_path)
                if did and did not in normalized_by_doc:
                    normalized_by_doc[did] = row_mapped

            for did in batch_doc_ids:
                if did not in normalized_by_doc and did not in llm_failures:
                    llm_failures[did] = "LLM returned no matching row for this document"

        except Exception as e:
            log.error(
                f"[B{batch_num}] LLM FAILED: {e} | "
                f"docs={len(batch_doc_ids)} prompt_chars={len(prompt)} "
                f"doc_ids={[d[:40] for d in batch_doc_ids]}"
            )
            for did in batch_doc_ids:
                llm_failures[did] = str(e)[:500]

    log.info(f"LLM normalization: {len(normalized_by_doc)} ok, {len(llm_failures)} failed in {time.time() - _phase_start:.1f}s")

    # ── Build success records ───────────────────────────────────────────────
    success_records = []
    for did, norm in normalized_by_doc.items():
        ext = extractions.get(did, {})
        llm_esn = (norm.get("esn") or "").strip()
        page1_esn = _extract_esn_from_page1_text(ext.get("page1_text", ""))
        resolved_esn = llm_esn or page1_esn
        if page1_esn and not llm_esn:
            log.info(f"  [ESN-FALLBACK] {did[:40]}: filled ESN from page-1 text")

        # ── ESN validation against deny-list + fsr_pdf_ref override ─────────
        esn_source = "llm" if resolved_esn else None
        ref_esns = _pdf_ref_esn_map.get(did.lower(), set())

        # Reject known-bad ESNs (XXXXXX, UNKNOWN, etc.)
        if resolved_esn and resolved_esn.upper() in INVALID_ESN_PATTERNS:
            log.info(f"  [ESN-INVALID] {did[:40]}: rejecting '{resolved_esn}' (deny-list)")
            resolved_esn = ""

        # If pipeline ESN is empty or not in fsr_pdf_ref, override with first ref ESN
        if ref_esns:
            if not resolved_esn or resolved_esn not in ref_esns:
                override_esn = sorted(ref_esns)[0]
                if resolved_esn:
                    log.info(f"  [ESN-OVERRIDE] {did[:40]}: '{resolved_esn}' → '{override_esn}' (not in fsr_pdf_ref)")
                else:
                    log.info(f"  [ESN-REF] {did[:40]}: filled from fsr_pdf_ref → '{override_esn}'")
                resolved_esn = override_esn
                esn_source = "fsr_pdf_ref"

        # Build all_esns: union of ref ESNs + resolved ESN
        all_esns_set = set(ref_esns)
        if resolved_esn:
            all_esns_set.add(resolved_esn)
        all_esns_json = json.dumps(sorted(all_esns_set)) if all_esns_set else None

        rec = {
            "document_id": did,
            "volume_path": ext.get("llm_fields", {}).get("PDF Name / path / identifier", ""),
            "title": ext.get("title"),
            "page_count": ext.get("page_count"),
            "esn": resolved_esn,
            "equipment_sys_id": norm.get("equipment_sys_id", ""),
            "equipment_type": norm.get("equipment_type", ""),
            "equipment_class_code": norm.get("equipment_class_code", ""),
            "event_type": norm.get("event_type", ""),
            "ev_project_id": norm.get("ev_project_id", ""),
            "ev_equipment_event_id": norm.get("ev_equipment_event_id", ""),
            "ofs_event_id": norm.get("ofs_event_id", ""),
            "fsp_project_id": norm.get("fsp_project_id", ""),
            "xxx_project_id": norm.get("xxx_project_id", ""),
            "fsr_number": norm.get("fsr_number", ""),
            "report_issued_date": norm.get("report_issued_date", ""),
            "outage_start_date": norm.get("outage_start_date", ""),
            "outage_end_date": norm.get("outage_end_date", ""),
            "esn_source": esn_source,
            "all_esns": all_esns_json,
            "document_summary": ext.get("document_summary"),
            "outage_type": None,
            "technology_type": None,
        }
        success_records.append(rec)

    # ── Enrich with IBAT + EV if available ──────────────────────────────────
    _phase_start = time.time()
    if enrichment_enabled and ibat_df and success_records:
        pdf = pd.DataFrame(success_records)
        fsr_df = spark.createDataFrame(pdf)
        fsr_df = fsr_df.select([col(c).cast(StringType()).alias(c) if c != "page_count"
                                else col(c) for c in fsr_df.columns])

        fsr_df = fsr_df.withColumn("_pre_ibat_esn", col("esn"))

        fsr_df = (fsr_df
            .withColumn("fsp_project_id_stripped", regexp_replace(col("fsp_project_id"), "FSP-", ""))
            .withColumn("ev_project_id_stripped", regexp_replace(col("ev_project_id"), "EVP-", ""))
            .withColumn("ev_equipment_event_id_stripped", regexp_replace(col("ev_equipment_event_id"), "EV-", ""))
        )

        # IBAT join
        enriched = fsr_df.join(
            ibat_df,
            (upper(trim(fsr_df["equipment_sys_id"])) == ibat_df["ibat_equipment_sys_id"])
            | (upper(trim(fsr_df["esn"])) == ibat_df["ibat_equip_serial_number"]),
            "left",
        )
        enriched = (enriched
            .withColumn("esn", when((col("esn").isNull()) | (col("esn") == ""), col("ibat_equip_serial_number")).otherwise(col("esn")))
            .withColumn("equipment_sys_id", when((col("equipment_sys_id").isNull()) | (col("equipment_sys_id") == ""), col("ibat_equipment_sys_id")).otherwise(col("equipment_sys_id")))
            .withColumn("equipment_type", when((col("equipment_type").isNull()) | (col("equipment_type") == ""), col("ibat_equipment_type")).otherwise(col("equipment_type")))
            .withColumn("equipment_class_code", when((col("equipment_class_code").isNull()) | (col("equipment_class_code") == ""), col("ibat_equipment_code")).otherwise(col("equipment_class_code")))
        )

        # EV join
        if ev_sot_df:
            enriched = enriched.join(
                ev_sot_df,
                (enriched["ev_project_id_stripped"] == ev_sot_df["sot_ev_project_id"])
                | (enriched["ev_equipment_event_id_stripped"] == ev_sot_df["sot_ev_equipment_event_id"])
                | (enriched["ofs_event_id"] == ev_sot_df["sot_ev_gtm_id"])
                | (enriched["fsp_project_id_stripped"] == ev_sot_df["sot_fsp_project_id"]),
                "left",
            )
            enriched = (enriched
                .withColumn("event_type", when((col("event_type").isNull()) | (col("event_type") == ""), col("sot_event_type")).otherwise(col("event_type")))
                .withColumn("outage_start_date", when((col("outage_start_date").isNull()) | (col("outage_start_date") == ""), col("sot_outage_start_date")).otherwise(col("outage_start_date")))
                .withColumn("outage_end_date", when((col("outage_end_date").isNull()) | (col("outage_end_date") == ""), col("sot_outage_end_date")).otherwise(col("outage_end_date")))
            )

        # ESN source tracking — preserve fsr_pdf_ref if already set
        enriched = enriched.withColumn("esn_source",
            when(col("esn_source") == "fsr_pdf_ref", lit("fsr_pdf_ref"))
            .when(col("_pre_ibat_esn").isNotNull() & (col("_pre_ibat_esn") != ""), lit("llm"))
            .when(col("esn").isNotNull() & (col("esn") != ""), lit("ibat"))
            .otherwise(lit(None))
        )

        # PSOT enrichment (outage_type, technology_type)
        try:
            psot_df = spark.read.table(PSOT_TABLE).select(
                col("ev_equipment_event_id").cast(StringType()).alias("psot_ev_equipment_event_id"),
                col("outage_type").cast(StringType()).alias("psot_outage_type"),
                col("technology_type").cast(StringType()).alias("psot_technology_type"),
            ).dropDuplicates(["psot_ev_equipment_event_id"])

            enriched = enriched.join(
                psot_df,
                enriched["ev_equipment_event_id_stripped"] == psot_df["psot_ev_equipment_event_id"],
                "left",
            )
            enriched = (enriched
                .withColumn("outage_type", col("psot_outage_type"))
                .withColumn("technology_type", col("psot_technology_type"))
            )
            log.info(f"PSOT enrichment complete: {PSOT_TABLE}")
        except Exception as e:
            log.warning(f"PSOT not accessible ({e}). Continuing without PSOT enrichment.")
            enriched = (enriched
                .withColumn("outage_type", lit(None))
                .withColumn("technology_type", lit(None)))

        # Dedup by document_id (IBAT join can multiply rows)
        enriched = enriched.dropDuplicates(["document_id"])

        keep_cols = ["document_id", "volume_path", "title", "page_count", "esn", "esn_source",
                     "equipment_sys_id", "equipment_type", "equipment_class_code",
                     "event_type", "ev_project_id", "ev_equipment_event_id",
                     "ofs_event_id", "fsp_project_id", "xxx_project_id",
                     "fsr_number", "report_issued_date", "outage_start_date", "outage_end_date",
                     "outage_type", "technology_type", "document_summary", "all_esns"]
        result_pdf = enriched.select(keep_cols).toPandas()
        success_records = result_pdf.where(result_pdf.notna(), None).to_dict("records")
        log.info(f"Enrichment complete: {len(success_records)} records in {time.time() - _phase_start:.1f}s")
    else:
        log.info("Skipping enrichment — using LLM-only results")
        for rec in success_records:
            rec.setdefault("document_summary", None)
            rec.setdefault("outage_type", None)
            rec.setdefault("technology_type", None)

    # ── Derive pdf_name from fsr_pdf_ref ────────────────────────────────────
    if success_records:
        sdf_pre = spark.createDataFrame(pd.DataFrame(success_records))
        sdf_pre.createOrReplaceTempView("_fsr_pre_pdfname")

        if _pdf_ref_loaded:
            try:
                derived_df = spark.sql("""
                    SELECT
                        s.document_id,
                        r.ref_pdf_name AS pdf_name
                    FROM _fsr_pre_pdfname s
                    LEFT JOIN _fsr_pdf_ref_deduped r
                        ON lower(regexp_replace(trim(r.ref_s3_filename), '\\.(pdf|PDF)$', ''))
                         = s.document_id
                """)
                pdf_name_map = {row.document_id: row.pdf_name for row in derived_df.collect()}
                contextual_count = 0
                stem_count = 0
                for rec in success_records:
                    ref_name = pdf_name_map.get(rec["document_id"])
                    if ref_name and str(ref_name).strip():
                        rec["pdf_name"] = str(ref_name).strip()
                        continue
                    generated_name = _build_contextual_pdf_name(rec)
                    if generated_name:
                        rec["pdf_name"] = generated_name
                        contextual_count += 1
                    else:
                        rec["pdf_name"] = Path(rec.get("volume_path", "")).stem or None
                        stem_count += 1
                matched = sum(1 for v in pdf_name_map.values() if v and str(v).strip())
                log.info(
                    f"pdf_name derivation: {matched}/{len(pdf_name_map)} matched fsr_pdf_ref; "
                    f"contextual fallback={contextual_count}, stem fallback={stem_count}"
                )
            except Exception as e:
                log.warning(f"pdf_name derivation failed ({e}). Using contextual/stem fallback.")
                for rec in success_records:
                    generated_name = _build_contextual_pdf_name(rec)
                    if generated_name:
                        rec["pdf_name"] = generated_name
                    else:
                        rec["pdf_name"] = Path(rec.get("volume_path", "")).stem or None
        else:
            log.info("pdf_ref not loaded — using contextual fallback for pdf_name")
            for rec in success_records:
                generated_name = _build_contextual_pdf_name(rec)
                if generated_name:
                    rec["pdf_name"] = generated_name
                else:
                    rec["pdf_name"] = Path(rec.get("volume_path", "")).stem or None
    else:
        log.info("No success records — skipping pdf_name derivation")

    # ── Multi-ESN fan-out: duplicate records per ESN ────────────────────────
    # Aligns metadata table with chunks table which already fans out per ESN.
    # For each document with multiple ESNs (in all_esns), create one metadata
    # row per ESN with correct IBAT equipment fields for that ESN.
    if success_records:
        # Build IBAT lookup dict for equipment field resolution per ESN
        _ibat_lookup = {}
        if enrichment_enabled and ibat_df:
            try:
                _ibat_rows = ibat_df.dropDuplicates(["ibat_equip_serial_number"]).collect()
                _ibat_lookup = {
                    row.ibat_equip_serial_number: {
                        "equipment_sys_id": row.ibat_equipment_sys_id or "",
                        "equipment_type": row.ibat_equipment_type or "",
                        "equipment_class_code": row.ibat_equipment_code or "",
                    }
                    for row in _ibat_rows
                    if row.ibat_equip_serial_number
                }
                log.info(f"IBAT lookup for multi-ESN fan-out: {len(_ibat_lookup)} ESNs")
            except Exception as e:
                log.warning(f"IBAT lookup build failed ({e}). Secondary ESNs will inherit primary equipment fields.")

        multi_esn_records = []
        for rec in success_records:
            all_esns_raw = rec.get("all_esns")
            try:
                all_esns_list = json.loads(all_esns_raw) if all_esns_raw else []
            except (json.JSONDecodeError, TypeError):
                all_esns_list = []

            # Ensure primary ESN is in the set
            primary_esn = (rec.get("esn") or "").strip()
            if primary_esn and primary_esn not in all_esns_list:
                all_esns_list.append(primary_esn)

            if not all_esns_list:
                # No ESNs at all — keep original record as-is
                multi_esn_records.append(rec)
                continue

            base_doc_id = rec["document_id"]
            for esn in sorted(set(all_esns_list)):
                if not esn or not esn.strip():
                    continue
                esn_val = esn.strip()
                new_rec = {**rec, "esn": esn_val}
                # Primary ESN keeps original document_id; secondary gets doc_id + "_" + esn
                if esn_val == primary_esn:
                    new_rec["document_id"] = base_doc_id
                    new_rec["_is_secondary"] = False
                else:
                    new_rec["document_id"] = f"{base_doc_id}_{esn_val}"
                    new_rec["_is_secondary"] = True
                # Resolve equipment fields from IBAT for this specific ESN
                if esn_val.upper() != (primary_esn or "").upper() and _ibat_lookup:
                    ibat_equip = _ibat_lookup.get(esn_val.upper())
                    if ibat_equip:
                        new_rec["equipment_sys_id"] = ibat_equip["equipment_sys_id"]
                        new_rec["equipment_type"] = ibat_equip["equipment_type"]
                        new_rec["equipment_class_code"] = ibat_equip["equipment_class_code"]
                new_rec["esn_source"] = "fsr_pdf_ref" if esn_val in _pdf_ref_esn_map.get(base_doc_id.lower(), set()) else rec.get("esn_source")
                multi_esn_records.append(new_rec)

        _pre_count = len(success_records)
        success_records = multi_esn_records
        log.info(f"Multi-ESN fan-out: {_pre_count} docs → {len(success_records)} rows")

        # ── Post-fan-out dedup ──────────────────────────────────────────────
        # Secondary doc_ids are built as f"{base_doc_id}_{esn_val}". Because
        # base_doc_id can itself contain underscores (e.g. "9_v1.0(11)"),
        # the synthesized key can collide with another doc's primary or with
        # another doc's secondary. The downstream success MERGE keys on
        # document_id and Delta raises DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE
        # when the source frame has duplicates. On collision keep the primary
        # row and drop the colliding secondary.
        _seen = {}
        _collisions = []
        for r in success_records:
            did = r["document_id"]
            existing = _seen.get(did)
            if existing is None:
                _seen[did] = r
                continue
            if existing.get("_is_secondary", False) and not r.get("_is_secondary", False):
                _collisions.append((did, f"replaced secondary (esn={existing.get('esn')}) with primary (esn={r.get('esn')})"))
                _seen[did] = r
            else:
                _collisions.append((did, f"dropped secondary (esn={r.get('esn')}); kept (esn={existing.get('esn')})"))
        if _collisions:
            _before = len(success_records)
            success_records = list(_seen.values())
            log.warning(
                f"Multi-ESN fan-out post-dedup: dropped {_before - len(success_records)} "
                f"colliding row(s) (base_doc_id+ESN synthesis ambiguous)"
            )
            for did, reason in _collisions[:20]:
                log.warning(f"  [FANOUT-DEDUP] {did}: {reason}")

        # ── DRY_RUN reporting ───────────────────────────────────────────────
        if FSR_MULTI_ESN_DRY_RUN:
            _secondary = [r for r in success_records if "_" in r["document_id"] and r["document_id"] != r.get("_base_doc_id", r["document_id"])]
            log.info("=" * 70)
            log.info("  MULTI-ESN DRY RUN — NO WRITES WILL BE PERFORMED")
            log.info("=" * 70)
            log.info(f"  Total rows that would be written : {len(success_records)}")
            log.info(f"  Primary ESN rows (update)        : {_pre_count}")
            log.info(f"  Secondary ESN rows (new inserts) : {len(success_records) - _pre_count}")
            log.info("")
            log.info("  Sample rows (first 20):")
            for r in success_records[:20]:
                log.info(f"    document_id={r['document_id'][:50]}  esn={r.get('esn', '')}  "
                         f"esn_source={r.get('esn_source', '')}  equip_type={r.get('equipment_type', '')}")
            if len(success_records) > 20:
                log.info(f"    ... and {len(success_records) - 20} more")
            log.info("")
            # Group by base document to show fan-out distribution
            _fanout_dist = {}
            for r in success_records:
                base = r["document_id"].split("_")[0] if "_" in r["document_id"] else r["document_id"]
                _fanout_dist.setdefault(base, []).append(r.get("esn", ""))
            _multi_docs = {k: v for k, v in _fanout_dist.items() if len(v) > 1}
            log.info(f"  Documents with multiple ESN rows: {len(_multi_docs)}")
            for doc_id, esns in list(_multi_docs.items())[:10]:
                log.info(f"    {doc_id[:40]} → {esns}")
            if len(_multi_docs) > 10:
                log.info(f"    ... and {len(_multi_docs) - 10} more")
            log.info("=" * 70)
            log.info("*** DRY_RUN=true — Set FSR_MULTI_ESN_DRY_RUN=false to execute writes. ***")
            # Skip MERGE — fall through to failure handling only
            success_records = []

    # ── MERGE success results into metadata table ───────────────────────────
    if success_records:
        # _is_secondary flag determines chunk_status at INSERT time:
        # secondary rows get 'completed' (P2 creates their chunks via primary row)
        for rec in success_records:
            rec.setdefault("_is_secondary", False)

        # Invariant guard: success_records MUST be unique on document_id before
        # the MERGE, otherwise Delta raises DELTA_MULTIPLE_SOURCE_ROW_MATCHING_TARGET_ROW_IN_MERGE.
        # The post-fan-out dedup above should guarantee this; fail loudly with
        # the colliding doc_ids if anything slips through.
        _pre_merge_ids = [r["document_id"] for r in success_records]
        _pre_merge_dups = {k: v for k, v in Counter(_pre_merge_ids).items() if v > 1}
        if _pre_merge_dups:
            raise RuntimeError(
                "INVARIANT VIOLATION: _fsr_success has duplicate document_id(s) before MERGE; "
                f"sample: {list(_pre_merge_dups.items())[:10]}"
            )

        sdf = spark.createDataFrame(pd.DataFrame(success_records))
        sdf.createOrReplaceTempView("_fsr_success")

        spark.sql(f"""
            MERGE INTO {METADATA_TABLE} AS tgt
            USING _fsr_success AS src
            ON tgt.document_id = src.document_id
            WHEN MATCHED THEN UPDATE SET
                tgt.pdf_name = src.pdf_name,
                tgt.title = src.title,
                tgt.esn = src.esn,
                tgt.esn_source = src.esn_source,
                tgt.equipment_sys_id = src.equipment_sys_id,
                tgt.equipment_type = src.equipment_type,
                tgt.equipment_class_code = src.equipment_class_code,
                tgt.event_type = src.event_type,
                tgt.ev_project_id = src.ev_project_id,
                tgt.ev_equipment_event_id = src.ev_equipment_event_id,
                tgt.ofs_event_id = src.ofs_event_id,
                tgt.fsp_project_id = src.fsp_project_id,
                tgt.xxx_project_id = src.xxx_project_id,
                tgt.fsr_number = src.fsr_number,
                tgt.report_issued_date = src.report_issued_date,
                tgt.outage_start_date = src.outage_start_date,
                tgt.outage_end_date = src.outage_end_date,
                tgt.outage_type = src.outage_type,
                tgt.technology_type = src.technology_type,
                tgt.page_count = src.page_count,
                tgt.document_summary = src.document_summary,
                tgt.all_esns = src.all_esns,
                tgt.metadata_status = '{MetadataStatus.COMPLETED}',
                tgt.metadata_error = NULL,
                tgt.metadata_retry_count = 0,
                tgt.scraped_at = current_timestamp()
            WHEN NOT MATCHED THEN INSERT (
                document_id, volume_path, pdf_name, title, page_count,
                esn, esn_source, equipment_sys_id, equipment_type, equipment_class_code,
                event_type, ev_project_id, ev_equipment_event_id,
                ofs_event_id, fsp_project_id, xxx_project_id,
                fsr_number, report_issued_date, outage_start_date, outage_end_date,
                outage_type, technology_type, document_summary, all_esns,
                metadata_status, chunk_status, ingested_at, scraped_at
            ) VALUES (
                src.document_id, src.volume_path, src.pdf_name, src.title, src.page_count,
                src.esn, src.esn_source, src.equipment_sys_id, src.equipment_type, src.equipment_class_code,
                src.event_type, src.ev_project_id, src.ev_equipment_event_id,
                src.ofs_event_id, src.fsp_project_id, src.xxx_project_id,
                src.fsr_number, src.report_issued_date, src.outage_start_date, src.outage_end_date,
                src.outage_type, src.technology_type, src.document_summary, src.all_esns,
                '{MetadataStatus.COMPLETED}',
                CASE WHEN src._is_secondary = true THEN '{ChunkStatus.COMPLETED}'
                     ELSE '{ChunkStatus.PENDING}' END,
                current_timestamp(), current_timestamp()
            )
        """)
        log.info(f"Merged {len(success_records)} rows → metadata_status=completed")

        # Clean up stub rows (esn=NULL) that were created during discovery
        # but are now replaced by ESN-specific rows
        _cleaned = spark.sql(f"""
            DELETE FROM {METADATA_TABLE}
            WHERE (esn IS NULL OR TRIM(esn) = '')
              AND metadata_status = '{MetadataStatus.PENDING}'
              AND document_id IN (SELECT DISTINCT document_id FROM _fsr_success)
        """)
        log.info("Cleaned up NULL-ESN stub rows for processed documents")

    # ── Handle failures ─────────────────────────────────────────────────────
    all_failures = {**failures, **llm_failures}
    if all_failures:
        failure_rows = [{
            "document_id": did,
            "metadata_error": (err or "")[:200],
        } for did, err in all_failures.items()]
        spark.createDataFrame(pd.DataFrame(failure_rows)).createOrReplaceTempView("_fsr_failures")
        spark.sql(f"""
            MERGE INTO {METADATA_TABLE} AS tgt
            USING _fsr_failures AS src
            ON tgt.document_id = src.document_id
               AND (tgt.esn IS NULL OR TRIM(tgt.esn) = '')
            WHEN MATCHED THEN UPDATE SET
                tgt.metadata_status = '{MetadataStatus.FAILED}',
                tgt.metadata_error = src.metadata_error,
                tgt.metadata_retry_count = COALESCE(tgt.metadata_retry_count, 0) + 1,
                tgt.scraped_at = current_timestamp()
        """)
        log.info(f"Updated {len(all_failures)} rows → metadata_status=failed")

    # Per-batch progress summary
    _batch_elapsed = time.time() - _cb_wallclock_start
    grand_success += len(success_records)
    grand_fail += len(all_failures)
    log.info(f"[COMMIT BATCH {cb_idx+1}] Done — {len(success_records)} succeeded, "
             f"{len(all_failures)} failed in {_batch_elapsed:.1f}s. Running total: {grand_success} succeeded, {grand_fail} failed.")

    # ── Per-commit-batch audit row in run log table ──────────────────────────
    # One row per commit batch (mirrors what P2 writes from process_one_batch).
    # Aggregate counts only — per-doc detail lives in DQ log + metadata table.
    try:
        from datetime import datetime as _dt, timezone as _tz
        _batch_end_dt = _dt.now(_tz.utc)
        _batch_start_dt = _dt.fromtimestamp(_cb_wallclock_start, _tz.utc)
        _err_summary = "; ".join(
            f"{did[:30]}: {(err or '')[:80]}" for did, err in list(all_failures.items())[:10]
        ) if all_failures else None
        _err_sql = (
            f"'{_err_summary[:500].replace(chr(39), chr(39)*2)}'"
            if _err_summary else "NULL"
        )
        spark.sql(f"""
            INSERT INTO {RUN_LOG_TABLE} VALUES (
                '{P1_RUN_ID}',
                'PW_SDG_FSR_Metadata',
                '{_batch_start_dt.strftime('%Y-%m-%dT%H:%M:%S')}',
                '{_batch_end_dt.strftime('%Y-%m-%dT%H:%M:%S')}',
                {_batch_elapsed:.1f},
                {len(batch_rows)},
                {len(success_records)},
                {len(all_failures)},
                NULL,
                {_err_sql},
                current_timestamp()
            )
        """)
    except Exception as _e:
        log.warning(f"Failed to write P1 run audit log: {_e}")

# COMMAND ----------

# ── Final summary ───────────────────────────────────────────────────────────
summary = spark.sql(f"""
    SELECT metadata_status, COUNT(*) AS cnt
    FROM {METADATA_TABLE}
    GROUP BY metadata_status
    ORDER BY metadata_status
""").collect()
for row in summary:
    log.info(f"  {row.metadata_status}: {row.cnt}")
log.info(f"=== Process 1 complete — {grand_success} succeeded, {grand_fail} failed ===")