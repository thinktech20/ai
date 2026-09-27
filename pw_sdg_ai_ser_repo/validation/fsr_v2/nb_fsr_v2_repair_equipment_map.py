# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_v2_repair_equipment_map — rebuild fsr_document_equipment_map_v2 rows
# for documents that are already metadata_status='completed' but have no rows
# in the equipment map.
#
# Why this exists
# ---------------
# P1 used to write the equipment map once, in a single MERGE at the very end of
# the run, from state held in memory. Every doc it had already marked
# 'completed' therefore depended on that last cell running. When a run was
# interrupted (OOM, cancel, cluster loss) the metadata rows survived and the
# equipment-map rows did not — and Stage 1 only re-queues 'pending'/'failed', so
# those docs were never revisited. P1 now writes the map per LLM batch, which
# stops new gaps; this notebook repairs the ones already on disk.
#
# Why it does NOT reset metadata_status back to 'pending'
# ------------------------------------------------------
# Everything the map is built from is already persisted on fsr_metadata_v2:
#   preprocessor_regions (JSON, per-region primary_esn / primary_equip_type /
#   primary_technology_code), primary_esn, primary_equip_type, gt_esn, gen_esn,
#   st_esn, inactive_esns.
# So the map is reconstructable exactly, with no PDF parsing and no LLM calls.
# Re-queueing instead would re-parse and re-LLM every affected doc — days of
# wall clock and LLM spend — and would overwrite metadata that is already
# correct, which is a data-correctness risk, not a fix.
#
# The logic below intentionally mirrors `_build_map_rows` in
# silver/src/etl/nb_sdg_fsr_v2_metadata.py. Keep the two in sync.
#
# Widgets:
#   METADATA_TABLE_V2          — source of truth (read-only here)
#   DOC_EQUIPMENT_MAP_TABLE_V2 — repair target
#   REPAIR_DRY_RUN             — "true" (default) reports only, writes nothing
#   REPAIR_MAX_DOCS            — cap docs per run ("" = all)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    BooleanType, IntegerType, StringType, StructField, StructType, TimestampType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.repair.equipmap")

spark = SparkSession.builder.getOrCreate()

dbutils.widgets.text("METADATA_TABLE_V2", "vaiq.ai_std_con_field_service_report.fsr_metadata_v2")  # noqa: F821
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaiq.ai_std_con_field_service_report.fsr_document_equipment_map_v2")  # noqa: F821
dbutils.widgets.dropdown("REPAIR_DRY_RUN", "true", ["true", "false"])  # noqa: F821
dbutils.widgets.text("REPAIR_MAX_DOCS", "")  # noqa: F821

METADATA_TABLE = dbutils.widgets.get("METADATA_TABLE_V2").strip()  # noqa: F821
MAP_TABLE = dbutils.widgets.get("DOC_EQUIPMENT_MAP_TABLE_V2").strip()  # noqa: F821
DRY_RUN = dbutils.widgets.get("REPAIR_DRY_RUN").strip().lower() != "false"  # noqa: F821
_max_raw = dbutils.widgets.get("REPAIR_MAX_DOCS").strip()  # noqa: F821
MAX_DOCS = int(_max_raw) if _max_raw else 0

if not METADATA_TABLE or not MAP_TABLE:
    raise ValueError("METADATA_TABLE_V2 and DOC_EQUIPMENT_MAP_TABLE_V2 are both required")

log.info("=== FSR V2 equipment-map repair ===")
log.info(f"Metadata table : {METADATA_TABLE}")
log.info(f"Map table      : {MAP_TABLE}")
log.info(f"Dry run        : {DRY_RUN}")
log.info(f"Max docs       : {MAX_DOCS or '(all)'}")

# COMMAND ----------

# ── ASSESS: how bad is it, before changing anything ──────────────────────────

_assess = spark.sql(f"""
    SELECT
        COUNT(*)                                              AS completed_docs,
        COUNT(e.document_id)                                  AS docs_with_map_rows,
        COUNT(*) - COUNT(e.document_id)                       AS docs_missing_map_rows,
        SUM(CASE WHEN e.document_id IS NULL
                  AND COALESCE(m.primary_esn, '') = ''
                  AND COALESCE(m.gt_esn, '')      = ''
                  AND COALESCE(m.gen_esn, '')     = ''
                  AND COALESCE(m.st_esn, '')      = ''
                  AND COALESCE(m.preprocessor_regions, '[]') IN ('', '[]')
             THEN 1 ELSE 0 END)                               AS missing_but_no_esn_at_all
    FROM {METADATA_TABLE} m
    LEFT JOIN (SELECT DISTINCT document_id FROM {MAP_TABLE}) e
           ON m.document_id = e.document_id
    WHERE m.metadata_status = 'completed'
""").first()

log.info(
    "Assessment: completed=%s | with map rows=%s | MISSING=%s | of which genuinely have no ESN=%s",
    _assess.completed_docs, _assess.docs_with_map_rows,
    _assess.docs_missing_map_rows, _assess.missing_but_no_esn_at_all,
)
# `missing_but_no_esn_at_all` is expected and needs no repair — a doc with no ESN
# anywhere correctly has zero map rows. Everything else in MISSING is real loss.

# COMMAND ----------

# ── REBUILD: same logic as _build_map_rows in the P1 notebook ────────────────

_limit_sql = f"LIMIT {MAX_DOCS}" if MAX_DOCS else ""
_rows = spark.sql(f"""
    SELECT m.document_id, m.primary_esn, m.primary_equip_type,
           m.gt_esn, m.gen_esn, m.st_esn,
           m.inactive_esns, m.preprocessor_regions
    FROM {METADATA_TABLE} m
    LEFT ANTI JOIN {MAP_TABLE} e ON m.document_id = e.document_id
    WHERE m.metadata_status = 'completed'
    ORDER BY m.document_id
    {_limit_sql}
""").collect()

log.info(f"Fetched {len(_rows)} completed doc(s) with no equipment-map row")


def _build_map_rows_from_metadata(row) -> list[dict]:
    """Rebuild one document's map rows from its persisted metadata columns."""
    doc_primary_esn = (row.primary_esn or "").strip().upper()

    inactive_set: set[str] = set()
    if row.inactive_esns:
        try:
            inactive_set = {e.strip().upper() for e in json.loads(row.inactive_esns) if e.strip()}
        except (ValueError, TypeError):
            pass

    try:
        regions = json.loads(row.preprocessor_regions) if row.preprocessor_regions else []
    except (ValueError, TypeError):
        regions = []

    agg: dict = defaultdict(lambda: {"equip_type": None, "technology_code": None, "count": 0})
    for region in regions or []:
        meta = region.get("metadata") or {}
        esn = (meta.get("primary_esn") or "").strip().upper()
        if not esn:
            continue
        agg[esn]["count"] += 1
        if meta.get("primary_equip_type") and not agg[esn]["equip_type"]:
            agg[esn]["equip_type"] = meta["primary_equip_type"].strip()
        if meta.get("primary_technology_code") and not agg[esn]["technology_code"]:
            agg[esn]["technology_code"] = meta["primary_technology_code"].strip()

    for esn, equip_type in (
        (doc_primary_esn, (row.primary_equip_type or "").strip() or None),
        ((row.gt_esn or "").strip().upper(), "Gas Turbine"),
        ((row.gen_esn or "").strip().upper(), "Generator"),
        ((row.st_esn or "").strip().upper(), "Steam Turbine"),
    ):
        if esn and esn not in agg:
            agg[esn]["equip_type"] = equip_type

    now = datetime.now(timezone.utc)
    return [
        {
            "document_id": row.document_id,
            "esn": esn,
            "equip_type": data["equip_type"],
            "technology_code": data["technology_code"],
            "is_primary_esn": (esn == doc_primary_esn),
            "is_active": (esn not in inactive_set),
            "source_region_count": data["count"],
            "created_at": now,
            "updated_at": now,
        }
        for esn, data in agg.items()
    ]


_map_rows: list[dict] = []
_docs_with_rows = 0
_docs_no_esn = 0
for _row in _rows:
    _built = _build_map_rows_from_metadata(_row)
    if _built:
        _docs_with_rows += 1
        _map_rows.extend(_built)
    else:
        _docs_no_esn += 1

log.info(
    "Rebuild: %d row(s) for %d doc(s); %d doc(s) legitimately have no ESN and stay unmapped",
    len(_map_rows), _docs_with_rows, _docs_no_esn,
)

# COMMAND ----------

# ── WRITE ────────────────────────────────────────────────────────────────────
# Insert-only: every doc here was selected by LEFT ANTI JOIN, so it has no
# existing rows to update or delete. Deliberately not a full MERGE with
# NOT MATCHED BY SOURCE ... DELETE — this notebook must never remove map rows.

_MAP_SCHEMA = StructType([
    StructField("document_id",         StringType(),    False),
    StructField("esn",                 StringType(),    False),
    StructField("equip_type",          StringType(),    True),
    StructField("technology_code",     StringType(),    True),
    StructField("is_primary_esn",      BooleanType(),   True),
    StructField("is_active",           BooleanType(),   True),
    StructField("source_region_count", IntegerType(),   True),
    StructField("created_at",          TimestampType(), True),
    StructField("updated_at",          TimestampType(), True),
])

if not _map_rows:
    log.info("Nothing to write — no missing map rows found.")
elif DRY_RUN:
    log.info(
        "DRY RUN — would insert %d row(s) for %d doc(s). Sample: %s",
        len(_map_rows), _docs_with_rows, _map_rows[:5],
    )
    log.info("Set REPAIR_DRY_RUN=false to apply.")
else:
    spark.createDataFrame(_map_rows, schema=_MAP_SCHEMA) \
        .createOrReplaceTempView("_fsr_v2_equipment_map_repair")
    spark.sql(f"""
        MERGE INTO {MAP_TABLE} AS tgt
        USING _fsr_v2_equipment_map_repair AS src
        ON tgt.document_id = src.document_id AND tgt.esn = src.esn
        WHEN NOT MATCHED THEN INSERT *
    """)
    log.info(f"Repair applied: inserted up to {len(_map_rows)} row(s) into {MAP_TABLE}")

# COMMAND ----------

# ── VERIFY ───────────────────────────────────────────────────────────────────

_after = spark.sql(f"""
    SELECT COUNT(*) AS still_missing
    FROM {METADATA_TABLE} m
    LEFT ANTI JOIN {MAP_TABLE} e ON m.document_id = e.document_id
    WHERE m.metadata_status = 'completed'
      AND (COALESCE(m.primary_esn, '') <> ''
        OR COALESCE(m.gt_esn, '')      <> ''
        OR COALESCE(m.gen_esn, '')     <> ''
        OR COALESCE(m.st_esn, '')      <> '')
""").first()

log.info(
    "Post-repair: %s completed doc(s) with a known ESN still have no map row%s",
    _after.still_missing, " (dry run — expected)" if DRY_RUN else "",
)
if not DRY_RUN and _after.still_missing:
    log.warning(
        "Some docs remain unmapped. Re-run with a larger REPAIR_MAX_DOCS, or "
        "investigate those document_ids individually."
    )
