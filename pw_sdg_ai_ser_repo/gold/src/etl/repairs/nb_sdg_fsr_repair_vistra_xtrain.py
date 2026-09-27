# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_sdg_fsr_repair_vistra_xtrain — Vistra cross-train Generator repair
#
# Reads pending rows from the Vistra staging table (loaded by
# nb_sdg_fsr_load_vistra_gap_staging) and, per row:
#   1) inherits base metadata for the document_id on the staging row,
#   2) looks up equipment_sys_id / equipment_class_code from IBAT for
#      missing_esn (equipment_type is the literal 'Generator'),
#   3) inserts a new metadata row with
#         document_id = f"{base_document_id}_{missing_esn}",
#         esn = missing_esn,
#         esn_source = 'cross_tag_gap_v1',
#         ev_project_id inherited from base (no sibling project ID in xlsx),
#         ev_equipment_event_id = sibling_event_id (fallback inherit),
#         event_type = sibling_event_type (fallback inherit),
#         metadata_status='completed', chunk_status='completed',
#   4) clones every base chunk into vec_field_service_report with
#         new chunk_id = md5(base_document_id || '_' || chunk_index ||
#                            '__' || missing_esn)  -- matches multi-ESN pattern,
#         top-level esn = missing_esn,
#         metadata JSON keys 'esn' / 'equipment_sys_id' / 'equipment_type' /
#         'equipment_class_code' rewritten to Generator values,
#         same chunk_text, same chunk_embedding, same chunk_index (no re-chunk,
#         no re-embed),
#   5) metadata for all cloned chunks is read from the newly-inserted (or
#      existing) metadata row, ensuring consistency with IBAT-sourced values,
#   6) writes audit rows to fsr_repair_vistra_chunk_inserts and
#      fsr_repair_vistra_metadata_updates (always — even on partial success),
#   6) updates the staging row: {JB_ENV}_status='done',
#      {JB_ENV}_processed_at=now(), {JB_ENV}_run_id=REPAIR_RUN_ID.
#
# Idempotency:
#   - Target metadata document_id already present → skip (audit logged).
#   - Target chunk_id already present → skip that chunk; others still process.
#   - Staging row {JB_ENV}_status='done' → skipped at the filter stage.
#   - REPAIR_RUN_ID already present in audit chunk table → refuse to run.
#
# DRY_RUN=true: no writes anywhere (including no staging-status updates).
#
# Revert: companion notebook nb_sdg_fsr_revert_vistra_xtrain, scoped by
# REPAIR_RUN_ID.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ../../../../common/fsr_config

# COMMAND ----------

import json
import logging
import uuid
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.utils import AnalysisException

spark = SparkSession.builder.getOrCreate()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.repair.vistra.xtrain")

# COMMAND ----------

_sot_prefix = METADATA_TABLE.rsplit(".", 1)[0]
_std_prefix = CHUNK_TABLE.rsplit(".", 1)[0]

STAGING_TABLE = get_runtime_param("STAGING_TABLE", f"{_sot_prefix}.staging_vistra_gap")
AUDIT_CHUNK_TABLE = get_runtime_param(
    "AUDIT_CHUNK_TABLE", f"{_std_prefix}.fsr_repair_vistra_chunk_inserts"
)
AUDIT_META_TABLE = get_runtime_param(
    "AUDIT_META_TABLE", f"{_sot_prefix}.fsr_repair_vistra_metadata_updates"
)

REPAIR_RUN_ID = get_runtime_param("REPAIR_RUN_ID", "").strip() or uuid.uuid4().hex
DRY_RUN = get_runtime_param("DRY_RUN", "true").strip().lower() == "true"
CONFIDENCE_FILTER = get_runtime_param("CONFIDENCE_FILTER", "confirmed").strip().lower()
JB_ENV = get_runtime_param("jb_env", "").strip().lower()

if JB_ENV not in ("dev", "prod"):
    raise ValueError("JB_ENV must be 'dev' or 'prod'.")

STATUS_COL = f"{JB_ENV}_status"
RUN_ID_COL = f"{JB_ENV}_run_id"
PROCESSED_AT_COL = f"{JB_ENV}_processed_at"
ERROR_COL = f"{JB_ENV}_error"

log.info("=== Vistra Cross-Train Repair ===")
log.info(f"  STAGING_TABLE     : {STAGING_TABLE}")
log.info(f"  METADATA_TABLE    : {METADATA_TABLE}")
log.info(f"  CHUNK_TABLE       : {CHUNK_TABLE}")
log.info(f"  IBAT_TABLE        : {IBAT_EQUIPMENT_TABLE}")
log.info(f"  AUDIT_CHUNK_TABLE : {AUDIT_CHUNK_TABLE}")
log.info(f"  AUDIT_META_TABLE  : {AUDIT_META_TABLE}")
log.info(f"  REPAIR_RUN_ID     : {REPAIR_RUN_ID}")
log.info(f"  CONFIDENCE_FILTER : {CONFIDENCE_FILTER}")
log.info(f"  JB_ENV           : {JB_ENV}  (status col: {STATUS_COL})")
log.info(f"  DRY_RUN           : {DRY_RUN}")

# COMMAND ----------

def _sql_str(v) -> str:
    """Quote a value for safe embedding in a SQL literal; NULL for None/NaN."""
    if v is None:
        return "NULL"
    s = str(v)
    if s.lower() in ("nan", "nat", "none", ""):
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def _sql_lit(v) -> str:
    """Like _sql_str but raises on empty (use for required identifiers)."""
    if v is None or str(v).strip() == "":
        raise ValueError("_sql_lit got empty value")
    return "'" + str(v).replace("'", "''") + "'"


def _clean_opt_str(v):
    """Normalize optional staging values (None/NaN/blank -> None)."""
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in ("", "nan", "nat", "none", "null"):
        return None
    return s


# COMMAND ----------

# ── Idempotency guard: refuse to reuse a REPAIR_RUN_ID ──────────────────────
_existing = spark.sql(
    f"SELECT COUNT(*) AS cnt FROM {AUDIT_CHUNK_TABLE} WHERE repair_run_id = {_sql_str(REPAIR_RUN_ID)}"
).first().cnt
if _existing > 0:
    raise RuntimeError(
        f"REPAIR_RUN_ID {REPAIR_RUN_ID} already exists in {AUDIT_CHUNK_TABLE} "
        f"({_existing} rows). Refuse to run. Use a new REPAIR_RUN_ID or revert first."
    )

# COMMAND ----------

# ── Load pending staging rows ───────────────────────────────────────────────
pending = spark.sql(
    f"""
    SELECT *
    FROM {STAGING_TABLE}
    WHERE LOWER(confidence) = {_sql_str(CONFIDENCE_FILTER)}
      AND LOWER({STATUS_COL}) = 'pending'
    """
).toPandas()

log.info(f"Pending rows to process: {len(pending):,}")
if len(pending) == 0:
    dbutils.notebook.exit(  # noqa: F821
        f"NOOP: no pending rows (confidence={CONFIDENCE_FILTER}, env={JB_ENV}). "
        f"run_id={REPAIR_RUN_ID}"
    )

# COMMAND ----------

def _ibat_lookup(esn: str):
    """Return (equipment_sys_id, equipment_class_code) for an ESN, or (None, None)."""
    if not esn:
        return (None, None)
    row = spark.sql(
        f"""
        SELECT equipment_sys_id, equipment_sub_class AS equipment_class_code
        FROM {IBAT_EQUIPMENT_TABLE}
        WHERE UPPER(TRIM(equip_serial_number)) = UPPER(TRIM({_sql_str(esn)}))
        LIMIT 1
        """
    ).collect()
    if not row:
        return (None, None)
    return (row[0]["equipment_sys_id"], row[0]["equipment_class_code"])


def _load_base_meta(document_id: str):
    rows = spark.sql(
        f"SELECT * FROM {METADATA_TABLE} WHERE document_id = {_sql_str(document_id)} LIMIT 1"
    ).collect()
    return rows[0].asDict() if rows else None


def _meta_exists(document_id: str) -> bool:
    return (
        spark.sql(
            f"SELECT COUNT(*) AS cnt FROM {METADATA_TABLE} WHERE document_id = {_sql_str(document_id)}"
        ).first().cnt
        > 0
    )


def _chunk_count_for_doc(document_id: str) -> int:
    return int(
        spark.sql(
            f"SELECT COUNT(*) AS cnt FROM {CHUNK_TABLE} WHERE document_id = {_sql_str(document_id)}"
        ).first().cnt
    )


# COMMAND ----------

# ── Per-row processing ──────────────────────────────────────────────────────
results = []  # (pdf_stem, document_id, missing_esn, status, error, new_doc_id, chunks_inserted)
_t_run = datetime.now(timezone.utc)

for _, srow in pending.iterrows():
    pdf_stem = srow["pdf_stem"]
    base_doc_id = srow["document_id"]
    tagged_esn = _clean_opt_str(srow["tagged_esn"])
    missing_esn = (_clean_opt_str(srow["missing_esn"]) or "").upper()
    sibling_event_id = _clean_opt_str(srow["sibling_event_id"])
    sibling_event_type = _clean_opt_str(srow["sibling_event_type"])

    if not base_doc_id or not missing_esn:
        results.append((pdf_stem, base_doc_id, missing_esn, "failed",
                        "missing base_doc_id or missing_esn", None, 0))
        continue

    new_doc_id = f"{base_doc_id}_{missing_esn}"
    insert_meta_row = True

    try:
        base = _load_base_meta(base_doc_id)
        if base is None:
            results.append((pdf_stem, base_doc_id, missing_esn, "failed",
                            "base metadata row not found", new_doc_id, 0))
            continue

        # Idempotency with partial-state recovery:
        # - metadata exists + chunks exist -> skip (already complete)
        # - metadata exists + chunks missing -> recover missing chunks only
        if _meta_exists(new_doc_id):
            existing_chunk_cnt = _chunk_count_for_doc(new_doc_id)
            if existing_chunk_cnt > 0:
                if not DRY_RUN:
                    spark.sql(
                        f"""
                        UPDATE {STAGING_TABLE}
                        SET {STATUS_COL} = 'skipped',
                            {PROCESSED_AT_COL} = current_timestamp(),
                            {RUN_ID_COL} = {_sql_lit(REPAIR_RUN_ID)},
                            {ERROR_COL} = NULL
                        WHERE pdf_stem = {_sql_lit(pdf_stem)} AND missing_esn = {_sql_lit(missing_esn)}
                        """
                    )
                results.append((pdf_stem, base_doc_id, missing_esn, "skipped",
                                f"target document_id already complete (existing_chunks={existing_chunk_cnt})", new_doc_id, 0))
                continue

            log.warning(
                "Partial state detected: target metadata exists but chunk rows are missing. "
                f"Proceeding with chunk recovery for document_id={new_doc_id}"
            )
            insert_meta_row = False

        equip_sys_id, equip_class_code = _ibat_lookup(missing_esn)

        new_event_type = sibling_event_type or base.get("event_type")
        new_ev_eq_event_id = sibling_event_id or base.get("ev_equipment_event_id")

        # Build the metadata JSON the same way the chunk job does: construct from
        # known fields so chunk rows always have correct, IBAT-sourced values.
        # chunk-specific fields (page_number, section_*, etc.) are inherited from
        # each base chunk in the SELECT; only the ESN/equipment fields change here.
        _new_meta_base = {
            "pdf_name": base.get("pdf_name"),
            "title": base.get("title"),
            "customer": base.get("customer"),
            "esn": missing_esn,
            "equipment_sys_id": equip_sys_id,
            "equipment_type": "Generator",
            "equipment_class_code": equip_class_code,
            "event_type": new_event_type,
            "ev_project_id": base.get("ev_project_id"),
            "ev_equipment_event_id": new_ev_eq_event_id,
            "ofs_event_id": base.get("ofs_event_id"),
            "fsp_project_id": base.get("fsp_project_id"),
            "xxx_project_id": base.get("xxx_project_id"),
            "fsr_number": base.get("fsr_number"),
            "report_issued_date": base.get("report_issued_date"),
            "outage_start_date": base.get("outage_start_date"),
            "outage_end_date": base.get("outage_end_date"),
            "outage_type": base.get("outage_type"),
            "technology_type": base.get("technology_type"),
            "prepared_by": base.get("prepared_by"),
            "approved_by": base.get("approved_by"),
            "document_summary": base.get("document_summary"),
        }
        _new_meta_base_sql = _sql_str(json.dumps(_new_meta_base, default=str))

        chunk_source_filter = (
            f" AND UPPER(TRIM(c.esn)) = UPPER(TRIM({_sql_lit(tagged_esn)}))"
            if tagged_esn
            else ""
        )
        chunk_count_filter = (
            f" AND UPPER(TRIM(esn)) = UPPER(TRIM({_sql_lit(tagged_esn)}))"
            if tagged_esn
            else ""
        )

        source_chunk_cnt = spark.sql(
            f"""
            SELECT COUNT(DISTINCT chunk_index) AS cnt
            FROM {CHUNK_TABLE}
            WHERE document_id = {_sql_str(base_doc_id)}{chunk_count_filter}
            """
        ).first().cnt

        if source_chunk_cnt == 0:
            err_msg = (
                f"no source chunks found for tagged_esn={tagged_esn}"
                if tagged_esn
                else "no source chunks found for base document"
            )
            results.append((pdf_stem, base_doc_id, missing_esn, "failed",
                            err_msg, new_doc_id, 0))
            continue

        if DRY_RUN:
            results.append((pdf_stem, base_doc_id, missing_esn, "planned",
                            f"would insert 1 meta + {source_chunk_cnt} chunks", new_doc_id, source_chunk_cnt))
            continue

        # ── 1) INSERT new metadata row (inherit from base, override per plan §4) ─
        if insert_meta_row:
            spark.sql(
                f"""
                INSERT INTO {METADATA_TABLE} (
                    document_id, pdf_name, volume_path, title, customer,
                    esn, esn_source, equipment_sys_id, equipment_type, equipment_class_code,
                    event_type, ev_project_id, ev_equipment_event_id,
                    ofs_event_id, fsp_project_id, xxx_project_id,
                    fsr_number, report_issued_date, outage_start_date, outage_end_date,
                    outage_type, technology_type, prepared_by, approved_by,
                    document_summary, page_count, file_size_bytes, file_last_modified,
                    metadata_status, chunk_status,
                    ingested_at, scraped_at, chunked_at
                )
                SELECT
                    {_sql_lit(new_doc_id)},
                    pdf_name, volume_path, title, customer,
                    {_sql_lit(missing_esn)}, 'cross_tag_gap_v1',
                    {_sql_str(equip_sys_id)}, 'Generator', {_sql_str(equip_class_code)},
                    {_sql_str(new_event_type)}, ev_project_id, {_sql_str(new_ev_eq_event_id)},
                    ofs_event_id, fsp_project_id, xxx_project_id,
                    fsr_number, report_issued_date, outage_start_date, outage_end_date,
                    outage_type, technology_type, prepared_by, approved_by,
                    document_summary, page_count, file_size_bytes, file_last_modified,
                    'completed', 'completed',
                    current_timestamp(), current_timestamp(), current_timestamp()
                FROM {METADATA_TABLE}
                WHERE document_id = {_sql_lit(base_doc_id)}
                """
            )

        # ── 2) Build deterministic chunk clone set (materialized once) ─────────
        # We dedupe by chunk_index before cloning to avoid duplicate target
        # chunk_ids when the base doc has multiple ESN variants for same chunk.
        # Metadata JSON is built from known fields (same pattern as nb_sdg_fsr_chunks),
        # so chunk rows always get the correct IBAT-sourced equipment values.
        # chunk-level fields (page_number, section_*, etc.) come from the base chunk.
        spark.sql(
            f"""
            CREATE OR REPLACE TEMP VIEW _v_clone_chunks_plan AS
            SELECT
                MD5(CONCAT(c.document_id, '_', CAST(c.chunk_index AS STRING),
                           '__', {_sql_lit(missing_esn)})) AS chunk_id,
                c.chunk_index,
                {_sql_lit(new_doc_id)} AS document_id,
                c.pdf_name,
                c.page_number,
                c.chunk_text,
                {_sql_lit(missing_esn)} AS esn,
                c.report_date,
                c.chunk_embedding,
                {_new_meta_base_sql} AS metadata,
                current_timestamp() AS created_at,
                c.chunk_id AS base_chunk_id
            FROM (
                SELECT *
                FROM (
                    SELECT
                        c.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY c.chunk_index
                            ORDER BY c.chunk_id
                        ) AS _rn
                    FROM {CHUNK_TABLE} c
                    WHERE c.document_id = {_sql_lit(base_doc_id)}
                            {chunk_source_filter}
                ) s
                WHERE s._rn = 1
            ) c
            WHERE NOT EXISTS (
                SELECT 1 FROM {CHUNK_TABLE} x
                WHERE x.chunk_id = MD5(CONCAT(
                    c.document_id, '_', CAST(c.chunk_index AS STRING),
                    '__', {_sql_lit(missing_esn)}))
            )
            """
        )

        # Materialize once so chunk insert and audit read the same exact rows.
        # Avoid DataFrame cache/persist because serverless compute blocks it.
        _tmp_suffix = uuid.uuid4().hex[:8]
        _tmp_clone_table = f"{_std_prefix}.__tmp_vistra_clone_chunks_{REPAIR_RUN_ID}_{_tmp_suffix}"
        spark.sql(
            f"""
            CREATE OR REPLACE TABLE {_tmp_clone_table}
            USING DELTA
            AS SELECT * FROM _v_clone_chunks_plan
            """
        )
        planned_insert_cnt = spark.sql(
            f"SELECT COUNT(*) AS cnt FROM {_tmp_clone_table}"
        ).first().cnt
        try:
            spark.sql(
                f"""
                INSERT INTO {CHUNK_TABLE} (
                    chunk_id, chunk_index, document_id, pdf_name, page_number,
                    chunk_text, esn, report_date, chunk_embedding, metadata, created_at
                )
                SELECT chunk_id, chunk_index, document_id, pdf_name, page_number,
                       chunk_text, esn, report_date, chunk_embedding, metadata, created_at
                FROM {_tmp_clone_table}
                """
            )

            # ── 3) Audit: chunk inserts (one row per chunk_id actually inserted) ───
            spark.sql(
                f"""
                INSERT INTO {AUDIT_CHUNK_TABLE} (
                    repair_run_id, document_id, base_document_id, chunk_id,
                    base_chunk_id, esn, chunk_index, inserted_at
                )
                SELECT {_sql_lit(REPAIR_RUN_ID)}, document_id, {_sql_lit(base_doc_id)},
                       chunk_id, base_chunk_id, esn, chunk_index, current_timestamp()
                FROM {_tmp_clone_table}
                """
            )
        finally:
            spark.sql(f"DROP TABLE IF EXISTS {_tmp_clone_table}")

        inserted_cnt = planned_insert_cnt

        # ── 4) Audit: metadata touch/insert ────────────────────────────────────
        spark.sql(
            f"""
            INSERT INTO {AUDIT_META_TABLE} (
                repair_run_id, document_id, base_document_id, inserted_esn, inserted_at
            )
            VALUES (
                {_sql_lit(REPAIR_RUN_ID)}, {_sql_lit(new_doc_id)}, {_sql_lit(base_doc_id)},
                {_sql_lit(missing_esn)}, current_timestamp()
            )
            """
        )

        # ── 5) Update staging row ──────────────────────────────────────────────
        spark.sql(
            f"""
            UPDATE {STAGING_TABLE}
            SET {STATUS_COL} = 'done',
                {PROCESSED_AT_COL} = current_timestamp(),
                {RUN_ID_COL} = {_sql_lit(REPAIR_RUN_ID)},
                {ERROR_COL} = NULL
            WHERE pdf_stem = {_sql_lit(pdf_stem)} AND missing_esn = {_sql_lit(missing_esn)}
            """
        )

        results.append((pdf_stem, base_doc_id, missing_esn, "done",
                        None, new_doc_id, inserted_cnt))

    except (AnalysisException, Exception) as exc:  # noqa: BLE001
        err = str(exc)[:500]
        log.warning(f"Row failed: pdf_stem={pdf_stem} missing_esn={missing_esn}: {err}")
        if not DRY_RUN:
            try:
                spark.sql(
                    f"""
                    UPDATE {STAGING_TABLE}
                    SET {STATUS_COL} = 'failed',
                        {PROCESSED_AT_COL} = current_timestamp(),
                        {RUN_ID_COL} = {_sql_lit(REPAIR_RUN_ID)},
                        {ERROR_COL} = {_sql_str(err)}
                    WHERE pdf_stem = {_sql_lit(pdf_stem)} AND missing_esn = {_sql_lit(missing_esn)}
                    """
                )
            except Exception as exc2:  # noqa: BLE001
                log.warning(f"Also failed to mark staging row failed: {exc2}")
        results.append((pdf_stem, base_doc_id, missing_esn, "failed",
                        err, new_doc_id if base_doc_id and missing_esn else None, 0))

# COMMAND ----------

# ── Summary ─────────────────────────────────────────────────────────────────
from collections import Counter
status_counts = Counter(r[3] for r in results)
log.info("")
log.info("=" * 60)
log.info("  Vistra Repair Summary")
log.info("=" * 60)
log.info(f"  REPAIR_RUN_ID : {REPAIR_RUN_ID}")
log.info(f"  JB_ENV       : {JB_ENV}")
log.info(f"  DRY_RUN       : {DRY_RUN}")
log.info(f"  Total rows    : {len(results)}")
for k, v in sorted(status_counts.items()):
    log.info(f"    {k:<10}: {v}")
log.info("")

if status_counts.get("failed", 0) > 0:
    log.warning("Failed rows (first 20):")
    for r in [x for x in results if x[3] == "failed"][:20]:
        log.warning(f"  pdf_stem={r[0]} missing_esn={r[2]} error={r[4]}")

# COMMAND ----------

# ── Verification (skipped in DRY_RUN) ───────────────────────────────────────
if not DRY_RUN:
    processed_doc_ids = [r[5] for r in results if r[3] == "done" and r[5]]
    base_doc_ids = [r[1] for r in results if r[3] == "done" and r[1]]
    if processed_doc_ids:
        _ids_csv = ",".join(f"'{d}'" for d in (processed_doc_ids + base_doc_ids))
        log.info("Metadata catalog view (new + base rows):")
        spark.sql(
            f"""
            SELECT document_id, pdf_name, esn, esn_source, equipment_type
            FROM {METADATA_TABLE}
            WHERE document_id IN ({_ids_csv})
            ORDER BY pdf_name, esn
            """
        ).show(200, truncate=False)

        log.info("Chunk distribution per (pdf_name, esn):")
        spark.sql(
            f"""
            SELECT pdf_name, esn, COUNT(*) AS chunk_rows
            FROM {CHUNK_TABLE}
            WHERE document_id IN ({_ids_csv})
            GROUP BY pdf_name, esn
            ORDER BY pdf_name, esn
            """
        ).show(200, truncate=False)

# COMMAND ----------

dbutils.notebook.exit(  # noqa: F821
    f"Repair {('DRY_RUN' if DRY_RUN else 'DONE')} "
    f"(env={JB_ENV}, run_id={REPAIR_RUN_ID}): "
    f"total={len(results)}, "
    + ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
)
