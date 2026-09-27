"""Stage 3 — Metadata Extraction Processor (v2 redesign adapter).

Runs the FSR v2 redesign preprocessor against a ParsedDocument and returns
structured metadata, hints, and region boundaries.

This module intentionally stays thin: it builds context and delegates all
section/summary/region logic to common.fsr_v2.preprocessor_v2.
"""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

from .parsing import ParsedDocument

log = logging.getLogger("fsr.v2.metadata_processor_v2")

# Import shared FSR v2 helpers via the repo-root package path to avoid
# colliding with silver/src/etl/fsr_v2 when Databricks imports this module.
_REPO_ROOT = str(Path(__file__).resolve().parents[4])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from common.fsr_v2 import preprocessor_v2 as _preprocessor  # noqa: E402
from common.fsr_v2 import final_master_report_profile as _final_master_report  # noqa: E402

# Fields we ask the preprocessor to emit.
_FIELDS = [
    {"name": "primary_esn"},
    {"name": "primary_equip_type"},
    {"name": "primary_technology_code"},
    {"name": "inactive_esns"},
    {"name": "gt_esn"},
    {"name": "gen_esn"},
    {"name": "st_esn"},
    {"name": "all_esns"},
    {"name": "outage_start_date"},
    {"name": "outage_end_date"},
    {"name": "report_issued_date"},
    {"name": "document_name"},
]

# Guard SQL string interpolation against unexpected ESN payloads (defence in depth).
_SAFE_ESN_RE = re.compile(r"^[A-Z0-9]{4,10}$")


def _make_ibat_resolver(
    spark: "SparkSession",
    ibat_table: str,
) -> "Any":
    # Deterministic train-scoped lookup. If the preprocessor supplies a
    # current_turbine_esn in context, restrict candidates to the equipment
    # sharing train_sys_id_fk with that turbine. When context is missing,
    # fall back to the wider type-only query so the resolver still contributes
    # something for docs without an anchor turbine.
    _train_scoped_sql = f"""
        SELECT UPPER(TRIM(equip_serial_number)) AS candidate_esn
        FROM {ibat_table}
        WHERE UPPER(TRIM(equipment_type)) = UPPER(TRIM('{{equip_type}}'))
          AND UPPER(TRIM(equip_serial_number)) NOT RLIKE '^SY[0-9]{{{{7}}}}$'
          AND equipment_status = 'InService'
          AND record_status = 'Active'
          AND UPPER(TRIM(active_lineage_indicator)) = 'TRUE'
          AND train_sys_id_fk IN (
              SELECT train_sys_id_fk
              FROM {ibat_table}
              WHERE UPPER(TRIM(equip_serial_number)) = UPPER(TRIM('{{turbine_esn}}'))
                AND train_sys_id_fk IS NOT NULL
          )
        ORDER BY candidate_esn
    """
    _type_only_sql = f"""
        SELECT UPPER(TRIM(equip_serial_number)) AS candidate_esn
        FROM {ibat_table}
        WHERE UPPER(TRIM(equipment_type)) = UPPER(TRIM('{{equip_type}}'))
          AND UPPER(TRIM(equip_serial_number)) NOT RLIKE '^SY[0-9]{{{{7}}}}$'
          AND equipment_status = 'InService'
          AND record_status = 'Active'
          AND UPPER(TRIM(active_lineage_indicator)) = 'TRUE'
        ORDER BY candidate_esn
    """

    def ibat_resolver(equip_type: str, context: dict[str, Any]) -> list[str]:
        raw_turbine_esn = str(context.get("current_turbine_esn") or "").strip().upper()
        safe_turbine_esn = raw_turbine_esn if _SAFE_ESN_RE.match(raw_turbine_esn) else ""
        try:
            if safe_turbine_esn:
                query = _train_scoped_sql.format(
                    equip_type=equip_type,
                    turbine_esn=safe_turbine_esn,
                )
            else:
                query = _type_only_sql.format(equip_type=equip_type)
            rows = spark.sql(query).collect()
            return [r.candidate_esn for r in rows if r.candidate_esn]
        except Exception as e:
            log.warning(f"[IBAT-RESOLVER] query failed for type '{equip_type}': {e}")
            return []

    return ibat_resolver


def run(
    parsed_doc: ParsedDocument,
    *,
    spark: "SparkSession | None" = None,
    ibat_table: str | None = None,
) -> dict:
    """Run the redesign preprocessor on a parsed document.

    Args:
        parsed_doc: ParsedDocument from Stage 2.
        spark: SparkSession — required when ibat_table is set.
        ibat_table: catalog path for IBAT equipment table; enables Phase 3
            type-constrained ESN resolution when local/parent resolution fails.

    Returns:
        dict with:
            metadata  — {primary_esn, primary_equip_type, inactive_esns, dates, ...}
            hints     — str, context for downstream normalization
            regions   — list of {start, end, metadata} char-offset region dicts
    """
    ctx = SimpleNamespace(
        pages=parsed_doc.pages,
        raw_pages=parsed_doc.raw_pages or parsed_doc.pages,
        page_offsets=parsed_doc.page_offsets,
        full_text=parsed_doc.full_text,
        fields=_FIELDS,
        filename=parsed_doc.filename,
    )
    ibat_resolver = (
        _make_ibat_resolver(spark, ibat_table)
        if spark is not None and ibat_table
        else None
    )
    if _final_master_report.is_final_master_report(ctx):
        return _final_master_report.preprocess(ctx, ibat_resolver=ibat_resolver)
    return _preprocessor.preprocess(ctx, ibat_resolver=ibat_resolver)
