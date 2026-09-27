# Databricks notebook source
# FSR v2 scope-table repair: P1 reprocess only, dry-run by default.
# P2 is run separately with FSR_V2_REPAIR_SCOPE_TABLE and FSR_V2_REPAIR_RUN_ID.

import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("fsr.v2.repair")
spark = SparkSession.builder.getOrCreate()

# Make repo packages importable in deployed workspace runs.
_ETL_ROOT = os.path.normpath(os.path.join(os.getcwd(), "../../../silver/src/etl"))
if _ETL_ROOT not in sys.path:
    sys.path.insert(0, _ETL_ROOT)
_REPO_ROOT = os.path.normpath(os.path.join(_ETL_ROOT, "../../.."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fsr_v2 import enrichment, metadata_processor, parsing  # noqa: E402
from common.fsr_v2.enums import ExtractorMethod  # noqa: E402


def _param(name: str, default: str = "") -> str:
    return dbutils.widgets.get(name).strip()  # noqa: F821


def _sql(value: str) -> str:
    return value.replace("'", "''")


for name, default in {
    "REPAIR_SCOPE_TABLE": "",
    "REPAIR_RUN_ID": "",
    "METADATA_TABLE_V2": "",
    "FSR_SOURCE_VOLUME_PATHS": "",
    "FSR_PARSED_DOC_VOLUME_ROOT": "",
    "REPAIR_DRY_RUN": "true",
    "REPAIR_MAX_DOCS": "",
    "LITELLM_BASE_URL": "",
    "LITELLM_API_KEY": "",
    "FSR_LLM_MODEL": "azure-gpt-5-2",
    "FSR_LLM_VERIFY_SSL": "false",
    "FSR_IBAT_TABLE": "",
    "FSR_EVENT_VISION_TABLE": "",
    "FSR_PSOT_TABLE": "",
    "FSR_PDF_REF_VIEW": "",
}.items():
    dbutils.widgets.text(name, default)  # noqa: F821

SCOPE_TABLE = _param("REPAIR_SCOPE_TABLE")
RUN_ID = _param("REPAIR_RUN_ID")
METADATA_TABLE = _param("METADATA_TABLE_V2")
DRY_RUN = _param("REPAIR_DRY_RUN", "true").lower() != "false"
MAX_DOCS = int(_param("REPAIR_MAX_DOCS") or "0")
P1_RUN_ID = uuid.uuid4().hex

if not SCOPE_TABLE or not RUN_ID or not METADATA_TABLE:
    raise ValueError("REPAIR_SCOPE_TABLE, REPAIR_RUN_ID, and METADATA_TABLE_V2 are required")

scope_run = _sql(RUN_ID)
limit_sql = f"LIMIT {MAX_DOCS}" if MAX_DOCS else ""
rows = spark.sql(f"""
    SELECT s.document_id, m.volume_path, m.file_size_bytes, m.file_last_modified,
           s.attempt_count
    FROM {SCOPE_TABLE} s
    LEFT JOIN {METADATA_TABLE} m ON lower(m.document_id) = lower(s.document_id)
    WHERE s.run_id = '{scope_run}'
      AND s.p1_status IN ('pending', 'failed')
    ORDER BY s.document_id
    {limit_sql}
""").collect()

log.info("Repair run=%s p1_run=%s dry_run=%s docs=%d", RUN_ID, P1_RUN_ID, DRY_RUN, len(rows))
if not rows:
    raise ValueError("No pending repair scope rows found")

if DRY_RUN:
    log.info("DRY RUN: no metadata or scope rows will be changed")
    for row in rows[:10]:
        log.info("DRY RUN candidate: %s path=%s", row.document_id, row.volume_path)
else:
    ids = ", ".join("'" + _sql(row.document_id.lower()) + "'" for row in rows)
    spark.sql(f"""
        UPDATE {SCOPE_TABLE}
        SET p1_status = 'in_progress',
            attempt_count = coalesce(attempt_count, 0) + 1,
            started_at = current_timestamp(),
            p1_run_id = '{_sql(P1_RUN_ID)}',
            error_message = NULL
        WHERE run_id = '{scope_run}' AND lower(document_id) IN ({ids})
    """)

for row in rows:
    doc_id = row.document_id
    try:
        if not row.volume_path:
            raise ValueError("scope document has no volume_path in metadata table")
        parsed = parsing.parse_pymupdf({
            "document_id": doc_id,
            "volume_path": row.volume_path,
        })
        if _param("FSR_PARSED_DOC_VOLUME_ROOT"):
            parsed = parsing.save_parsed_document(
                parsed,
                _param("FSR_PARSED_DOC_VOLUME_ROOT"),
                "pymupdf_v1.0",
            )
        processor_output = metadata_processor.run(
            parsed,
            spark=spark,
            ibat_table=_param("FSR_IBAT_TABLE") or None,
        )
        if DRY_RUN:
            log.info("DRY RUN: %s candidates=%d", doc_id, len(processor_output.get("regions", [])))
            continue

        enrichment.run(
            spark=spark,
            parsed_doc=parsed,
            processor_output=processor_output,
            metadata_table=METADATA_TABLE,
            llm_base_url=_param("LITELLM_BASE_URL"),
            llm_api_key=_param("LITELLM_API_KEY"),
            llm_model=_param("FSR_LLM_MODEL", "azure-gpt-5-2"),
            llm_verify_ssl=_param("FSR_LLM_VERIFY_SSL", "false").lower() != "false",
            file_size_bytes=row.file_size_bytes,
            file_last_modified=row.file_last_modified,
            ibat_table=_param("FSR_IBAT_TABLE") or None,
            ev_sot_table=_param("FSR_EVENT_VISION_TABLE") or None,
            psot_table=_param("FSR_PSOT_TABLE") or None,
            pdf_ref_table=_param("FSR_PDF_REF_VIEW") or None,
            extractor_method=ExtractorMethod.PYMUPDF_V1_0.value,
            run_id=P1_RUN_ID,
        )
        spark.sql(f"""
            UPDATE {SCOPE_TABLE}
            SET p1_status = 'completed', p2_status = 'pending',
                completed_at = NULL, error_message = NULL
            WHERE run_id = '{scope_run}' AND lower(document_id) = '{_sql(doc_id.lower())}'
        """)
        log.info("P1 repair completed: %s", doc_id)
    except Exception as exc:
        message = str(exc)[:1000]
        log.exception("P1 repair failed: %s", doc_id)
        if not DRY_RUN:
            spark.sql(f"""
                UPDATE {SCOPE_TABLE}
                SET p1_status = 'failed', error_message = '{_sql(message)}'
                WHERE run_id = '{scope_run}' AND lower(document_id) = '{_sql(doc_id.lower())}'
            """)

log.info("Repair P1 run finished: %s", P1_RUN_ID)
