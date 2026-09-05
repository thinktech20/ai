# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_metadata — Process 1: Metadata Extraction & Registration (Silver)
#
# Discovers new PDFs in source volumes, extracts page-1 metadata via
# pdfplumber, normalizes fields via LLM, enriches with IBAT + Event Vision,
# and writes results to the metadata registry table.
#
# Schema v3: document_id (UUID stem) is PK, pdf_name is derived. Statuses: pending / completed / failed.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pdfplumber

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../common/fsr_config

# COMMAND ----------

import json, time, re, logging
from pathlib import Path
from datetime import datetime, timezone

import requests
import urllib3
import pdfplumber
import pandas as pd

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, trim, concat, lit, upper,
    regexp_replace, current_timestamp,
)
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType,
    TimestampType, IntegerType,
)

urllib3.disable_warnings()
spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.p1.metadata")

# COMMAND ----------

log.info("=== Process 1 — Metadata Extraction ===")
log.info(f"  Metadata table : {METADATA_TABLE}")
log.info(f"  Volumes        : {PDF_VOLUME_PATHS}")
log.info(f"  LLM model      : {LLM_MODEL}")
log.info(f"  Batch size     : {P1_BATCH_SIZE}")
log.info(f"  Max PDFs       : {P1_MAX_PDFS or 'unlimited'}")
log.info(f"  Target PDFs    : {len(TARGET_PDF_NAMES) if TARGET_PDF_NAMES else 'all'}")
log.info(f"  Max retries    : {P1_MAX_RETRIES}")
log.info(f"  FORCE_RESET    : {FORCE_RESET}")
log.info(f"  LLM base URL   : {LITELLM_BASE_URL}")
log.info(f"  API key set    : {bool(LITELLM_API_KEY)}")

target_pdf_names = set(TARGET_PDF_NAMES or [])

# COMMAND ----------

# ── Read watermark (skip if FORCE_RESET) ────────────────────────────────────
watermark_ms = 0
if not FORCE_RESET:
    row = spark.sql(f"SELECT MAX(ingested_at) AS wm FROM {METADATA_TABLE}").first()
    if row and row.wm:
        watermark_ms = int(row.wm.timestamp() * 1000)
        log.info(f"Watermark: {row.wm} ({watermark_ms} ms)")
    else:
        log.info("Watermark: None (first run — scanning all files)")
else:
    spark.sql(f"TRUNCATE TABLE {METADATA_TABLE}")
    log.info("FORCE_RESET: table truncated, scanning all files")

# ── Scan volumes for new PDFs ───────────────────────────────────────────────
new_files = []
for vol in PDF_VOLUME_PATHS:
    log.info(f"Scanning: {vol}")
    try:
        all_entries = dbutils.fs.ls(vol)  # noqa: F821
    except Exception as e:
        log.warning(f"Cannot list volume {vol}: {e}")
        continue

    vol_count = 0
    for f in all_entries:
        if f.path.endswith("/"):
            continue
        path = f.path.replace("dbfs:", "") if f.path.startswith("dbfs:") else f.path
        document_id = Path(path).stem.lower()
        suffix = Path(path).suffix.lower()
        if suffix in SKIP_SUFFIXES:
            continue
        if target_pdf_names and document_id not in target_pdf_names:
            continue
        if not target_pdf_names and f.modificationTime <= watermark_ms:
            continue
        new_files.append({
            "path": path,
            "name": f.name,
            "size": f.size,
            "mod_time": f.modificationTime,
        })
        vol_count += 1
    log.info(f"  Found {vol_count} new files in {vol}")

if target_pdf_names:
    found_pdf_names = {Path(nf["path"]).stem for nf in new_files}
    missing_pdf_names = sorted(target_pdf_names - found_pdf_names)
    if missing_pdf_names:
        log.warning(f"Target PDFs not found in configured volumes: {missing_pdf_names}")

# ── Cap at P1_MAX_PDFS if set ───────────────────────────────────────────────
if P1_MAX_PDFS and len(new_files) > P1_MAX_PDFS:
    new_files = new_files[:P1_MAX_PDFS]

log.info(f"{len(new_files)} files to process (cap={P1_MAX_PDFS or 'unlimited'})")
for nf in new_files[:5]:
    ts = datetime.fromtimestamp(nf["mod_time"] / 1000, tz=timezone.utc).isoformat()
    log.info(f"  {ts}  {nf['name'][:60]}  ({nf['size']} bytes)")
if len(new_files) > 5:
    log.info(f"  ... and {len(new_files) - 5} more")

# COMMAND ----------

# ── Build stub rows for discovered files (ADR-007) ─────────────────────────
stub_rows = []
for nf in new_files:
    vol_path = nf["path"]
    document_id = Path(vol_path).stem.lower()  # UUID stem for FieldVision, filename for manual
    mod_ts = datetime.fromtimestamp(nf["mod_time"] / 1000, tz=timezone.utc)
    stub_rows.append({
        "document_id": document_id,
        "volume_path": vol_path,
        "file_size_bytes": nf["size"],
        "file_last_modified": mod_ts,
        "metadata_status": MetadataStatus.PENDING,
        "chunk_status": ChunkStatus.PENDING,
        "metadata_retry_count": 0,
        "metadata_version": 1,
    })

schema = StructType([
    StructField("document_id", StringType(), False),
    StructField("volume_path", StringType(), False),
    StructField("file_size_bytes", LongType(), True),
    StructField("file_last_modified", TimestampType(), True),
    StructField("metadata_status", StringType(), False),
    StructField("chunk_status", StringType(), False),
    StructField("metadata_retry_count", IntegerType(), True),
    StructField("metadata_version", IntegerType(), True),
])

stub_df = spark.createDataFrame(stub_rows, schema=schema)
stub_df.createOrReplaceTempView("_fsr_stubs")

# ── MERGE stub rows into metadata table ─────────────────────────────────────
merge_sql = f"""
MERGE INTO {METADATA_TABLE} AS tgt
USING _fsr_stubs AS src
ON tgt.document_id = src.document_id
WHEN MATCHED THEN UPDATE SET
    tgt.metadata_status = '{MetadataStatus.PENDING}',
    tgt.chunk_status = '{ChunkStatus.PENDING}',
    tgt.file_last_modified = src.file_last_modified,
    tgt.file_size_bytes = src.file_size_bytes,
    tgt.updated_at = current_timestamp()
WHEN NOT MATCHED THEN INSERT (
    document_id, volume_path,
    file_size_bytes, file_last_modified,
    metadata_status, chunk_status,
    metadata_retry_count, metadata_version,
    ingested_at, updated_at
) VALUES (
    src.document_id, src.volume_path,
    src.file_size_bytes, src.file_last_modified,
    src.metadata_status, src.chunk_status,
    src.metadata_retry_count, src.metadata_version,
    current_timestamp(), current_timestamp()
)
"""
spark.sql(merge_sql)

count = spark.sql(f"SELECT COUNT(*) AS n FROM {METADATA_TABLE}").first().n
pending = spark.sql(f"""
    SELECT COUNT(*) AS n FROM {METADATA_TABLE}
    WHERE metadata_status = '{MetadataStatus.PENDING}'
""").first().n
log.info(f"MERGE complete — Total rows: {count}, Pending: {pending}")

# COMMAND ----------

# ── Load pending rows for extraction ────────────────────────────────────────
pending_rows = spark.sql(f"""
    SELECT document_id, volume_path, metadata_retry_count
    FROM {METADATA_TABLE}
    WHERE metadata_status IN ('{MetadataStatus.PENDING}', '{MetadataStatus.FAILED}')
      AND (metadata_retry_count IS NULL OR metadata_retry_count < {P1_MAX_RETRIES})
""").collect()

log.info(f"{len(pending_rows)} documents to process")

# ── Extract first-page fields + page count from each PDF ───────────────────
extractions = {}  # document_id -> {title, llm_fields, page_count}
failures = {}     # document_id -> error_msg

for row in pending_rows:
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
            }
            log.info(f"  [OK] {document_id[:40]}  pages={page_count}  fields={len(llm_fields)}")

    except Exception as e:
        failures[document_id] = str(e)[:500]
        log.warning(f"  [FAIL] {document_id[:40]}: {e}")

log.info(f"Extracted: {len(extractions)}, Failed: {len(failures)}")

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
    for attempt in range(1, 4):
        for url in urls:
            try:
                resp = requests.post(url, headers=headers, json=payload,
                                     timeout=120, verify=LLM_VERIFY_SSL)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                if "CERTIFICATE_VERIFY_FAILED" in str(e):
                    continue
                if attempt == 3:
                    raise
                wait = 5 * (2 ** (attempt - 1))
                log.warning(f"LLM attempt {attempt} failed ({e}); retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError("LLM call failed after all retries")

# COMMAND ----------

# ── Send extractions to LLM in batches ──────────────────────────────────────

COLUMN_MAP = {
    "ESN": "esn",
    "Equipment Sys ID": "equipment_sys_id",
    "Equipment Type": "equipment_type",
    "Equipment Class / Code": "equipment_code",
    "Event Type": "event_type",
    "EV Project ID": "ev_project_id",
    "EV Equipment Event ID": "ev_equipment_event_id",
    "OFS Event ID": "ofs_event_id",
    "FSP project ID": "fsp_project_id",
    "Project ID": "project_id",
    "PDF Name / path / identifier": "_volume_path",
    "FSR Number (#)": "fsr_number",
    "Report Issued Date": "report_issued_date",
    "Outage Start Date": "outage_start_date",
    "Outage End Date": "outage_end_date",
}

doc_ids_ordered = list(extractions.keys())
all_llm_fields = [extractions[did]["llm_fields"] for did in doc_ids_ordered]

normalized_by_doc = {}  # document_id -> normalized dict
llm_failures = {}       # document_id -> error

for i in range(0, len(all_llm_fields), P1_BATCH_SIZE):
    batch_fields = all_llm_fields[i:i + P1_BATCH_SIZE]
    batch_doc_ids = doc_ids_ordered[i:i + P1_BATCH_SIZE]
    batch_num = (i // P1_BATCH_SIZE) + 1

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
        log.error(f"[B{batch_num}] LLM FAILED: {e}")
        for did in batch_doc_ids:
            llm_failures[did] = str(e)[:500]

log.info(f"Normalized: {len(normalized_by_doc)}, LLM failures: {len(llm_failures)}")

# COMMAND ----------

# ── Build success records ───────────────────────────────────────────────────
success_records = []
for did, norm in normalized_by_doc.items():
    ext = extractions.get(did, {})
    rec = {
        "document_id": did,
        "title": ext.get("title"),
        "page_count": ext.get("page_count"),
        "esn": norm.get("esn", ""),
        "equipment_sys_id": norm.get("equipment_sys_id", ""),
        "equipment_type": norm.get("equipment_type", ""),
        "equipment_code": norm.get("equipment_code", ""),
        "event_type": norm.get("event_type", ""),
        "ev_project_id": norm.get("ev_project_id", ""),
        "ev_equipment_event_id": norm.get("ev_equipment_event_id", ""),
        "ofs_event_id": norm.get("ofs_event_id", ""),
        "fsp_project_id": norm.get("fsp_project_id", ""),
        "project_id": norm.get("project_id", ""),
        "fsr_number": norm.get("fsr_number", ""),
        "report_issued_date": norm.get("report_issued_date", ""),
        "outage_start_date": norm.get("outage_start_date", ""),
        "outage_end_date": norm.get("outage_end_date", ""),
        "esn_source": "llm" if norm.get("esn") else None,
    }
    success_records.append(rec)

# ── Load IBAT and Event Vision lookup tables ────────────────────────────────
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

# ── Enrich with IBAT + EV if available ──────────────────────────────────────
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
        .withColumn("equipment_code", when((col("equipment_code").isNull()) | (col("equipment_code") == ""), col("ibat_equipment_code")).otherwise(col("equipment_code")))
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

    # ESN source tracking
    enriched = enriched.withColumn("esn_source",
        when(col("_pre_ibat_esn").isNotNull() & (col("_pre_ibat_esn") != ""), lit("llm"))
        .when(col("esn").isNotNull() & (col("esn") != ""), lit("ibat"))
        .otherwise(lit(None))
    )

    # Dedup by document_id (IBAT join can multiply rows)
    enriched = enriched.dropDuplicates(["document_id"])

    keep_cols = ["document_id", "title", "page_count", "esn", "esn_source",
                 "equipment_sys_id", "equipment_type", "equipment_code",
                 "event_type", "ev_project_id", "ev_equipment_event_id",
                 "ofs_event_id", "fsp_project_id", "project_id",
                 "fsr_number", "report_issued_date", "outage_start_date", "outage_end_date"]
    result_pdf = enriched.select(keep_cols).toPandas()
    success_records = result_pdf.where(result_pdf.notna(), None).to_dict("records")
    log.info(f"Enrichment complete: {len(success_records)} records")
else:
    log.info("Skipping enrichment — using LLM-only results")

# COMMAND ----------

# ── Derive pdf_name from fsr_pdf_ref (human-readable filename) ──────────────
# Join document_id → fsr_pdf_ref.s3_filename to get PDF_name.
# Fallback: use basename from volume_path if the document isn't in fsr_pdf_ref.

if success_records:
    sdf_pre = spark.createDataFrame(pd.DataFrame(success_records))
    sdf_pre.createOrReplaceTempView("_fsr_pre_pdfname")

    try:
        pdf_ref_df = spark.read.table(FSR_PDF_REF_VIEW).select(
            col("s3_filename").alias("ref_s3_filename"),
            col("PDF_name").alias("ref_pdf_name"),
        ).dropDuplicates(["ref_s3_filename"])
        pdf_ref_df.createOrReplaceTempView("_fsr_pdf_ref_deduped")

        derived_df = spark.sql("""
            SELECT
                s.document_id,
                COALESCE(
                    r.ref_pdf_name,
                    regexp_extract(s.volume_path, '([^/]+)\\.pdf$', 1)
                ) AS pdf_name
            FROM _fsr_pre_pdfname s
            LEFT JOIN _fsr_pdf_ref_deduped r
                ON lower(regexp_replace(trim(r.ref_s3_filename), '\\.(pdf|PDF)$', ''))
                 = s.document_id
        """)
        pdf_name_map = {row.document_id: row.pdf_name for row in derived_df.collect()}
        for rec in success_records:
            rec["pdf_name"] = pdf_name_map.get(rec["document_id"])
        matched = sum(1 for v in pdf_name_map.values() if v and not v.startswith("_"))
        log.info(f"pdf_name derivation: {matched}/{len(pdf_name_map)} matched fsr_pdf_ref")
    except Exception as e:
        log.warning(f"pdf_name derivation failed ({e}). Using volume_path fallback.")
        for rec in success_records:
            from pathlib import Path as _P
            rec["pdf_name"] = _P(rec.get("volume_path", "")).stem or None
else:
    log.info("No success records — skipping pdf_name derivation")

# COMMAND ----------

# ── MERGE success results into metadata table ───────────────────────────────
if success_records:
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
            tgt.equipment_code = src.equipment_code,
            tgt.event_type = src.event_type,
            tgt.ev_project_id = src.ev_project_id,
            tgt.ev_equipment_event_id = src.ev_equipment_event_id,
            tgt.ofs_event_id = src.ofs_event_id,
            tgt.fsp_project_id = src.fsp_project_id,
            tgt.project_id = src.project_id,
            tgt.fsr_number = src.fsr_number,
            tgt.report_issued_date = src.report_issued_date,
            tgt.outage_start_date = src.outage_start_date,
            tgt.outage_end_date = src.outage_end_date,
            tgt.page_count = src.page_count,
            tgt.metadata_status = '{MetadataStatus.COMPLETED}',
            tgt.metadata_error = NULL,
            tgt.scraped_at = current_timestamp(),
            tgt.updated_at = current_timestamp()
    """)
    log.info(f"Updated {len(success_records)} rows → metadata_status=completed")

# ── Handle failures ─────────────────────────────────────────────────────────
all_failures = {**failures, **llm_failures}
for did, err in all_failures.items():
    safe_err = err[:200].replace("'", "''")
    spark.sql(f"""
        UPDATE {METADATA_TABLE}
        SET metadata_status = '{MetadataStatus.FAILED}',
            metadata_error = '{safe_err}',
            metadata_retry_count = COALESCE(metadata_retry_count, 0) + 1,
            updated_at = current_timestamp()
        WHERE document_id = '{did}'
    """)
if all_failures:
    log.info(f"Updated {len(all_failures)} rows → metadata_status=failed")

# ── Final summary ───────────────────────────────────────────────────────────
summary = spark.sql(f"""
    SELECT metadata_status, COUNT(*) AS cnt
    FROM {METADATA_TABLE}
    GROUP BY metadata_status
    ORDER BY metadata_status
""").collect()
for row in summary:
    log.info(f"  {row.metadata_status}: {row.cnt}")
log.info("=== Process 1 complete ===")
