# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_load_vistra_gap_staging — Loader for Vistra cross-train repair
#
# Reads Jon's enriched workbook (xlsx or csv), normalizes columns, resolves
# pdf_stem -> document_id, validates missing_esn against IBAT, and writes rows
# into the Vistra staging table.
#
# Input file location (operational convention):
#   dev:  /Volumes/vaid/ai_sot_field_service_report/repair_inputs/vistra/<file>.xlsx
#   prod: /Volumes/vaip/ai_sot_field_service_report/repair_inputs/vistra/<file>.xlsx
# Path is passed at runtime via INPUT_PATH; nothing is hardcoded here.
#
# Why a staging table (not "xlsx straight into the repair notebook"):
#   - Validation at load time (document_id resolution, IBAT ESN check) so the
#     repair notebook deals only with rows it can safely process.
#   - Idempotent + resumable: per-row dev_status / prod_status track progress
#     in the same row across reruns.
#   - Confidence-gated rollout: 47 confirmed (gap_confirmed='YES') run first;
#     205 weak rows live in the same table and are processed later.
#   - One audit trail for SME handback and a clean revert input scoped by
#     load_run_id / repair run_id.
#
# Re-load semantics (MERGE on (pdf_stem, missing_esn)):
#   - New rows -> INSERT.
#   - Existing rows where BOTH dev_status and prod_status are still in
#     {pending, invalid, NULL} -> UPDATE lookup + audit columns from the new
#     xlsx (lets corrected sibling_event_id / plant / etc. flow through).
#   - Existing rows where EITHER env shows done/failed -> left untouched.
#   - No flag, no truncate. Re-running the loader is safe by construction.
#     For a hard reset, TRUNCATE the staging table manually.
#
# Column-name decisions (kept 1:1 with Jon's xlsx headers, snake_case):
#   tagged_equipment_type (NOT tagged_esn_type),
#   missing_esn + separate missing_equipment_type (NOT missing_generator_esn),
#   sibling_event_id (NOT sibling_ev_equipment_event_id).
#   sibling_ev_project_id intentionally NOT carried — Jon's workbook has no
#   such column; on the new metadata row the repair notebook inherits
#   ev_project_id from the base row (same FSR engagement). Only
#   ev_equipment_event_id comes from the xlsx Sibling Event ID, falling back
#   to inherit on null.
#
# Extra xlsx columns carried for audit only (not consumed by the repair insert):
#   tagged_event_type, matched_event_date, gap_confirmed.
#
# Confidence derivation here:
#   gap_confirmed == 'YES'  -> confidence = 'confirmed'
#   otherwise               -> confidence = 'weak'
#
# Invalid-row policy:
#   Rows with unresolved document_id or missing_esn not in IBAT are loaded
#   with dev_status='invalid' / prod_status='invalid' and the reason in
#   dev_error / prod_error. They are also appended to DQ_LOG_TABLE with
#   check_name='vistra_gap_staging_validation' for monitoring parity with P1/P2.
#
# Repo placement: ad hoc repair utilities live under etl/repairs/ and
# ddl/repairs/; recurring pipeline notebooks stay flat in etl/ and ddl/.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet openpyxl

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %run ../../../../common/fsr_config

# COMMAND ----------

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.repair.vistra.loader")

# COMMAND ----------

_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]

STAGING_TABLE = get_runtime_param("STAGING_TABLE", f"{_sot_prefix}.staging_vistra_gap")
INPUT_PATH = get_runtime_param("INPUT_PATH", "").strip()
INPUT_SHEET = get_runtime_param("INPUT_SHEET", "FSR Tagging Gaps").strip()
INPUT_FORMAT = get_runtime_param("INPUT_FORMAT", "auto").strip().lower()
SOURCE_TAG = get_runtime_param("SOURCE_TAG", "cross_tag_gap_v1").strip()

LOAD_RUN_ID = uuid.uuid4().hex

log.info("=== Vistra Staging Loader ===")
log.info(f"  INPUT_PATH    : {INPUT_PATH}")
log.info(f"  INPUT_SHEET   : {INPUT_SHEET}")
log.info(f"  INPUT_FORMAT  : {INPUT_FORMAT}")
log.info(f"  STAGING_TABLE : {STAGING_TABLE}")
log.info(f"  LOAD_RUN_ID   : {LOAD_RUN_ID}")

if not INPUT_PATH:
    raise ValueError("INPUT_PATH is required (xlsx or csv).")
if not (INPUT_PATH.startswith("/Volumes/") or INPUT_PATH.startswith("dbfs:/Volumes/")):
    log.warning(
        "INPUT_PATH is not under /Volumes/. Convention is "
        "/Volumes/<vaid|vaip>/ai_sot_field_service_report/repair_inputs/vistra/<file>.xlsx"
    )

# COMMAND ----------

def _pick_col(cols: Iterable[str], options: Iterable[str]) -> Optional[str]:
    norm = {c.strip().lower(): c for c in cols}
    for opt in options:
        hit = norm.get(opt.strip().lower())
        if hit:
            return hit
    return None


def _to_pdf_stem(value: object) -> str:
    text = str(value).strip().lower()
    if text.endswith(".pdf"):
        return text[:-4]
    return text


def _load_input(path: str, fmt: str, sheet: str) -> pd.DataFrame:
    p = path.lower()
    use_fmt = fmt
    if use_fmt == "auto":
        if p.endswith(".xlsx") or p.endswith(".xls"):
            use_fmt = "xlsx"
        elif p.endswith(".csv"):
            use_fmt = "csv"
        else:
            raise ValueError("INPUT_FORMAT=auto failed. Use path ending with .xlsx/.xls/.csv or set INPUT_FORMAT.")

    if use_fmt == "xlsx":
        return pd.read_excel(path, sheet_name=sheet)
    if use_fmt == "csv":
        return pd.read_csv(path)

    raise ValueError("INPUT_FORMAT must be one of: auto, xlsx, csv")


pdf = _load_input(INPUT_PATH, INPUT_FORMAT, INPUT_SHEET)
if pdf.empty:
    raise RuntimeError("Input file has no rows.")

pdf.columns = [str(c).strip() for c in pdf.columns]
log.info(f"Loaded input rows: {len(pdf):,}")
log.info(f"Input columns: {pdf.columns.tolist()}")

# COMMAND ----------

col_pdf_stem = _pick_col(
    pdf.columns,
    [
        "PDF (stem)",
        "PDF Stem",
        "pdf_stem",
        "PDF Name",
        "pdf_name",
        "PDF File Name",
        "pdf_file_name",
    ],
)
col_plant = _pick_col(pdf.columns, ["Plant", "plant"])
col_tagged_esn = _pick_col(pdf.columns, ["Tagged ESN", "tagged_esn"])
col_tagged_eq_type = _pick_col(pdf.columns, ["Tagged Equipment Type", "tagged_equipment_type"])
col_tagged_event_type = _pick_col(pdf.columns, ["Event Type", "tagged_event_type"])
col_matched_event_date = _pick_col(pdf.columns, ["Matched Event Date", "matched_event_date"])
col_missing_esn = _pick_col(pdf.columns, ["Missing ESN", "Missing ESN (Gen)", "missing_esn"])
col_missing_eq_type = _pick_col(pdf.columns, ["Missing Equipment Type", "missing_equipment_type"])
col_sibling_event_type = _pick_col(pdf.columns, ["Sibling Event Type", "sibling_event_type"])
col_sibling_event_id = _pick_col(pdf.columns, ["Sibling Event ID", "sibling_event_id"])
col_keyword_count = _pick_col(pdf.columns, ["Keyword Matches", "keyword_count"])
col_keywords_found = _pick_col(pdf.columns, ["Keywords Found", "keywords_found"])
col_gap_confirmed = _pick_col(pdf.columns, ["Gap Confirmed", "gap_confirmed"])
col_report_date = _pick_col(pdf.columns, ["Report Date", "report_date"])

required = {
    "PDF (stem) or PDF Name": col_pdf_stem,
    "Tagged ESN": col_tagged_esn,
    "Missing ESN": col_missing_esn,
}
missing_required = [k for k, v in required.items() if not v]
if missing_required:
    raise RuntimeError(f"Input file missing required columns: {missing_required}")

if not col_missing_eq_type:
    log.warning("Missing Equipment Type not found in input; defaulting to 'Generator'.")
if not col_gap_confirmed:
    log.warning("Gap Confirmed not found; confidence will default to 'weak'.")

rows = []
for _, r in pdf.iterrows():
    gap_confirmed = str(r[col_gap_confirmed]).strip() if col_gap_confirmed else ""
    confidence = "confirmed" if gap_confirmed.upper() == "YES" else "weak"

    missing_eq_type = (
        str(r[col_missing_eq_type]).strip() if col_missing_eq_type else "Generator"
    )
    if not missing_eq_type:
        missing_eq_type = "Generator"

    rows.append(
        {
            "pdf_stem": _to_pdf_stem(r[col_pdf_stem]),
            "document_id": None,
            "plant": str(r[col_plant]).strip() if col_plant else None,
            "tagged_esn": str(r[col_tagged_esn]).strip() if col_tagged_esn else None,
            "tagged_equipment_type": str(r[col_tagged_eq_type]).strip() if col_tagged_eq_type else None,
            "tagged_event_type": str(r[col_tagged_event_type]).strip() if col_tagged_event_type else None,
            "matched_event_date": str(r[col_matched_event_date]).strip() if col_matched_event_date else None,
            "missing_esn": str(r[col_missing_esn]).strip(),
            "missing_equipment_type": missing_eq_type,
            "sibling_event_type": str(r[col_sibling_event_type]).strip() if col_sibling_event_type else None,
            "sibling_event_id": str(r[col_sibling_event_id]).strip() if col_sibling_event_id else None,
            "keyword_count": int(r[col_keyword_count]) if col_keyword_count and pd.notna(r[col_keyword_count]) else None,
            "keywords_found": str(r[col_keywords_found]).strip() if col_keywords_found else None,
            "gap_confirmed": gap_confirmed if gap_confirmed else None,
            "report_date": str(r[col_report_date]).strip() if col_report_date else None,
            "confidence": confidence,
            "source": SOURCE_TAG,
            "dev_status": None,
            "dev_processed_at": None,
            "dev_run_id": None,
            "dev_error": None,
            "prod_status": None,
            "prod_processed_at": None,
            "prod_run_id": None,
            "prod_error": None,
        }
    )

staging_df = spark.createDataFrame(pd.DataFrame(rows))

# COMMAND ----------

meta_map = (
    spark.table(METADATA_TABLE)
    .where(F.col("metadata_status") == F.lit("completed"))
    .select(
        F.lower(F.trim(F.regexp_replace(F.col("pdf_name"), "\\.pdf$", ""))).alias("pdf_stem_key"),
        F.col("document_id").alias("resolved_document_id"),
    )
)

meta_map = (
    meta_map.withColumn(
        "rn",
        F.row_number().over(
            Window.partitionBy("pdf_stem_key").orderBy(
                F.when(F.lower(F.col("resolved_document_id")) == F.col("pdf_stem_key"), F.lit(0)).otherwise(F.lit(1)),
                F.col("resolved_document_id").asc(),
            )
        ),
    )
    .where(F.col("rn") == 1)
    .drop("rn")
)

ibat_map = (
    spark.table(IBAT_EQUIPMENT_TABLE)
    .select(F.lower(F.trim(F.col("equip_serial_number"))).alias("missing_esn_key"))
    .where(F.col("missing_esn_key").isNotNull() & (F.col("missing_esn_key") != F.lit("")))
    .dropDuplicates(["missing_esn_key"])
)

resolved = (
    staging_df
    .withColumn("pdf_stem_key", F.lower(F.trim(F.col("pdf_stem"))))
    .withColumn("missing_esn_key", F.lower(F.trim(F.col("missing_esn"))))
    .join(meta_map, on="pdf_stem_key", how="left")
    .join(ibat_map.withColumn("missing_esn_exists", F.lit(True)), on="missing_esn_key", how="left")
    .withColumn("document_id", F.col("resolved_document_id"))
    .drop("resolved_document_id")
)

resolved = resolved.withColumn(
    "_validation_error",
    F.when(F.col("document_id").isNull(), F.lit("document_id_not_found_in_metadata"))
    .when(F.col("missing_esn_exists").isNull(), F.lit("missing_esn_not_found_in_ibat"))
    .otherwise(F.lit(None).cast("string")),
)

resolved = (
    resolved
    .withColumn("dev_status", F.when(F.col("_validation_error").isNull(), F.lit("pending")).otherwise(F.lit("invalid")))
    .withColumn("prod_status", F.when(F.col("_validation_error").isNull(), F.lit("pending")).otherwise(F.lit("invalid")))
    .withColumn("dev_error", F.when(F.col("_validation_error").isNull(), F.lit(None).cast("string")).otherwise(F.col("_validation_error")))
    .withColumn("prod_error", F.when(F.col("_validation_error").isNull(), F.lit(None).cast("string")).otherwise(F.col("_validation_error")))
    .withColumn("loaded_at", F.current_timestamp())
)

final_df = resolved.select(
    "pdf_stem",
    "document_id",
    "plant",
    "tagged_esn",
    "tagged_equipment_type",
    "tagged_event_type",
    "matched_event_date",
    "missing_esn",
    "missing_equipment_type",
    "sibling_event_type",
    "sibling_event_id",
    "keyword_count",
    "keywords_found",
    "gap_confirmed",
    "report_date",
    "confidence",
    "source",
    "dev_status",
    "dev_processed_at",
    "dev_run_id",
    "dev_error",
    "prod_status",
    "prod_processed_at",
    "prod_run_id",
    "prod_error",
    "loaded_at",
)

# COMMAND ----------

total_rows = final_df.count()
pending_rows = final_df.where(F.col("dev_status") == "pending").count()
invalid_rows = final_df.where(F.col("dev_status") == "invalid").count()

log.info(f"Prepared rows  : {total_rows:,}")
log.info(f"Pending rows   : {pending_rows:,}")
log.info(f"Invalid rows   : {invalid_rows:,}")

STAGING_COLS = [
    "pdf_stem", "document_id", "plant",
    "tagged_esn", "tagged_equipment_type", "tagged_event_type", "matched_event_date",
    "missing_esn", "missing_equipment_type",
    "sibling_event_type", "sibling_event_id",
    "keyword_count", "keywords_found", "gap_confirmed", "report_date",
    "confidence", "source",
    "dev_status", "dev_processed_at", "dev_run_id", "dev_error",
    "prod_status", "prod_processed_at", "prod_run_id", "prod_error",
    "loaded_at",
]

final_df.select(*STAGING_COLS).createOrReplaceTempView("v_vistra_staging_loader")

# ── MERGE on (pdf_stem, missing_esn) ─────────────────────────────────────
# - New rows -> INSERT
# - Existing rows still pending/invalid -> UPDATE lookup + audit fields
#   (lets a corrected xlsx flow fixes into unprocessed rows without ever
#    touching rows that any env has already processed).
# - Existing rows where ANY env shows done/failed -> left alone.
spark.sql(
    f"""
    MERGE INTO {STAGING_TABLE} AS tgt
    USING v_vistra_staging_loader AS src
      ON tgt.pdf_stem = src.pdf_stem AND tgt.missing_esn = src.missing_esn
    WHEN MATCHED AND (COALESCE(tgt.dev_status, 'pending') IN ('pending','invalid'))
                 AND (COALESCE(tgt.prod_status,'pending') IN ('pending','invalid'))
      THEN UPDATE SET
        tgt.document_id            = src.document_id,
        tgt.plant                  = src.plant,
        tgt.tagged_esn             = src.tagged_esn,
        tgt.tagged_equipment_type  = src.tagged_equipment_type,
        tgt.tagged_event_type      = src.tagged_event_type,
        tgt.matched_event_date     = src.matched_event_date,
        tgt.missing_equipment_type = src.missing_equipment_type,
        tgt.sibling_event_type     = src.sibling_event_type,
        tgt.sibling_event_id       = src.sibling_event_id,
        tgt.keyword_count          = src.keyword_count,
        tgt.keywords_found         = src.keywords_found,
        tgt.gap_confirmed          = src.gap_confirmed,
        tgt.report_date            = src.report_date,
        tgt.confidence             = src.confidence,
        tgt.source                 = src.source,
        tgt.dev_status             = src.dev_status,
        tgt.dev_error              = src.dev_error,
        tgt.prod_status            = src.prod_status,
        tgt.prod_error             = src.prod_error,
        tgt.loaded_at              = src.loaded_at
    WHEN NOT MATCHED THEN INSERT (
        pdf_stem, document_id, plant,
        tagged_esn, tagged_equipment_type, tagged_event_type, matched_event_date,
        missing_esn, missing_equipment_type,
        sibling_event_type, sibling_event_id,
        keyword_count, keywords_found, gap_confirmed, report_date,
        confidence, source,
        dev_status, dev_processed_at, dev_run_id, dev_error,
        prod_status, prod_processed_at, prod_run_id, prod_error,
        loaded_at
    ) VALUES (
        src.pdf_stem, src.document_id, src.plant,
        src.tagged_esn, src.tagged_equipment_type, src.tagged_event_type, src.matched_event_date,
        src.missing_esn, src.missing_equipment_type,
        src.sibling_event_type, src.sibling_event_id,
        src.keyword_count, src.keywords_found, src.gap_confirmed, src.report_date,
        src.confidence, src.source,
        src.dev_status, src.dev_processed_at, src.dev_run_id, src.dev_error,
        src.prod_status, src.prod_processed_at, src.prod_run_id, src.prod_error,
        src.loaded_at
    )
    """
)

log.info(f"MERGED into: {STAGING_TABLE}")

# ── Route invalid rows to DQ log for monitoring parity with P1/P2 ─────────
if invalid_rows > 0 and DQ_LOG_TABLE:
    try:
        invalid_pdf = (
            resolved.where(F.col("_validation_error").isNotNull())
            .select("pdf_stem", "document_id", "missing_esn", "_validation_error")
            .toPandas()
        )
        _now = datetime.now(timezone.utc)
        _dq_rows = []
        for _, r in invalid_pdf.iterrows():
            _key = f"{LOAD_RUN_ID}|{r['pdf_stem']}|{r['missing_esn']}"
            _dq_rows.append({
                "dq_id": hashlib.md5(_key.encode()).hexdigest(),
                "run_id": LOAD_RUN_ID,
                "document_id": (r["document_id"] or r["pdf_stem"]),
                "pdf_name": r["pdf_stem"],
                "check_name": "vistra_gap_staging_validation",
                "severity": "WARN",
                "failure_category": r["_validation_error"],
                "detail": f"missing_esn={r['missing_esn']}"[:500],
                "created_at": _now,
            })
        spark.createDataFrame(_dq_rows, schema=dq_log_schema()) \
             .write.mode("append").saveAsTable(DQ_LOG_TABLE)
        log.info(f"DQ log: wrote {len(_dq_rows)} WARN row(s) to {DQ_LOG_TABLE}")
    except Exception as _e:
        log.warning(f"DQ log write failed (non-blocking): {_e}")

# COMMAND ----------

spark.sql(
    f"""
    SELECT confidence, dev_status, COUNT(*) AS rows
    FROM {STAGING_TABLE}
    GROUP BY confidence, dev_status
    ORDER BY confidence, dev_status
    """
).show(200, truncate=False)

# COMMAND ----------

dbutils.notebook.exit(  # noqa: F821
    f"Loader OK: table={STAGING_TABLE}, total={total_rows}, pending={pending_rows}, "
    f"invalid={invalid_rows}, load_run_id={LOAD_RUN_ID}"
)
