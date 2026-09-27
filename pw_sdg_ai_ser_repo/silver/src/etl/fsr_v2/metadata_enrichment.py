"""Stage 4B — Merge & Enrich.

Combines preprocessor + LLM metadata, performs IBAT/EV/PSOT deterministic
enrichment, and writes the result to fsr_metadata_v2.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

from .parsing import ParsedDocument

# Self-sufficient rather than relying on the calling notebook having done it:
# common/ holds the Delta retry shared with P2, which is a separate package.
_REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../../../"))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from common.fsr_v2.delta_retry import (  # noqa: E402
    CONCURRENCY_ERROR_MARKERS as _CONCURRENCY_ERROR_MARKERS,
    MERGE_MAX_ATTEMPTS as _MERGE_MAX_ATTEMPTS,
    is_concurrency_error as _is_concurrency_error,
    run_with_retry,
)

log = logging.getLogger("fsr.v2.metadata_enrichment")

_DATE_FORMATS = [
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{2}-\d{2}$")),
    ("%m/%d/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
    ("%d/%m/%Y", None),  # tried only if month-first fails
    ("%d %b %Y", re.compile(r"^\d{1,2}\s+[A-Za-z]{3}\s+\d{4}$")),
    ("%d-%b-%Y", re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$")),
    ("%d-%B-%Y", re.compile(r"^\d{1,2}-[A-Za-z]{4,}-\d{4}$")),
    ("%B %d, %Y", re.compile(r"^[A-Za-z]+\s+\d{1,2},\s+\d{4}$")),
    ("%B %d %Y", None),
]


def _normalize_date(value: str) -> str:
    """Convert any common date format to YYYY-MM-DD; return original if unparseable."""
    from datetime import datetime  # noqa: PLC0415
    v = (value or "").strip().rstrip(".").strip()
    if not v:
        return v
    if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        return v  # already correct
    for fmt, pattern in _DATE_FORMATS:
        if pattern and not pattern.match(v):
            continue
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return v  # return as-is if nothing matched

_INVALID_ESN_PATTERNS = frozenset({
    "XXXXXX", "XXXXXXX", "XXXXXXXX",
    "UNKNOWN", "N/A", "NA", "TBD", "NONE", "NULL",
    "{UK_NATIONAL_INSURANCE_NUMBER}",
})

# P1 issues these MERGEs sequentially from the main thread, so the conflict source
# is another writer on the table — most likely Delta autoOptimize/optimizeWrite
# committing in the background, which is enabled on fsr_metadata_v2. Retrying is
# the supported handling for optimistic-concurrency conflicts; without it a doc
# lands in metadata_status='failed' purely from commit timing.


def _run_merge_with_retry(spark: "SparkSession", sql: str, doc_id: str) -> None:
    """Execute a MERGE, retrying with jittered backoff on Delta write conflicts."""
    run_with_retry(spark, sql, doc_id)


_PREPROC_AUTHORITATIVE_KEYS = {
    "primary_esn",
    "primary_equip_type",
    "primary_technology_code",
    "inactive_esns",
    "gt_esn",
    "gen_esn",
    "st_esn",
    "document_name",
}


def _merge_llm_and_preprocessor(llm_meta: dict, proc_meta: dict) -> dict:
    preproc_non_empty = {k: v for k, v in (proc_meta or {}).items() if v}
    merged = dict(llm_meta or {})
    for key, value in preproc_non_empty.items():
        if key in _PREPROC_AUTHORITATIVE_KEYS:
            merged[key] = value
        elif not merged.get(key):
            merged[key] = value
    return merged


def write_enriched_metadata(
    spark: "SparkSession",
    parsed_doc: ParsedDocument,
    metadata_table: str,
    *,
    proc_meta: dict,
    regions: list,
    llm_meta: dict,
    file_size_bytes: int | None = None,
    file_last_modified: Any = None,
    ibat_table: str | None = None,
    ev_sot_table: str | None = None,
    psot_table: str | None = None,
    pdf_ref_table: str | None = None,
    extractor_method: str,
    preprocess_method: str,
    llm_model: str,
    llm_extraction_prompt_version: str,
    pipeline_version: str,
    run_id: str | None,
    doc_date: str | None = None,
    doc_year: int | None = None,
    doc_date_source: str | None = None,
) -> None:
    """Write one enriched document row into metadata_table via MERGE."""
    doc_id = parsed_doc.document_id
    merged = _merge_llm_and_preprocessor(llm_meta, proc_meta)

    primary_esn = (merged.get("primary_esn") or "").strip().upper()
    if primary_esn in _INVALID_ESN_PATTERNS:
        log.info(f"  [ESN-INVALID] {doc_id[:40]}: rejecting '{primary_esn}'")
        primary_esn = ""

    if not primary_esn:
        # Chunking already falls back gt -> gen when building active_esns; mirror
        # that here so the doc keeps a usable doc-level ESN instead of dropping
        # out of the equipment map and every ESN-filtered join.
        # st_esn is last: the preprocessor emits it but fsr_metadata_v2 has no
        # column for it, so this is the only path by which a steam-turbine-only
        # doc reaches the map and chunk-level active_esns.
        for source in ("gt_esn", "gen_esn", "st_esn"):
            candidate = (merged.get(source) or "").strip().upper()
            if candidate and candidate not in _INVALID_ESN_PATTERNS:
                primary_esn = candidate
                log.info(f"  [ESN-FALLBACK] {doc_id[:40]}: primary_esn <- {source} '{candidate}'")
                break

    primary_equip_type = (merged.get("primary_equip_type") or "").strip()

    primary_equip_sys_id = ""
    primary_equip_class_code = ""
    if ibat_table and primary_esn and re.fullmatch(r"[A-Z0-9]{4,10}", primary_esn):
        try:
            ibat_row = spark.sql(f"""
                SELECT equipment_sys_id, equipment_sub_class
                FROM {ibat_table}
                WHERE UPPER(TRIM(equip_serial_number)) = '{primary_esn}'
                LIMIT 1
            """).first()
            if ibat_row:
                primary_equip_sys_id = ibat_row.equipment_sys_id or ""
                primary_equip_class_code = ibat_row.equipment_sub_class or ""
        except Exception as e:
            log.warning(f"  [IBAT-SKIP] {doc_id[:40]}: {e}")

    ev_project_id = (merged.get("ev_project_id") or "").strip()
    ev_equipment_event_id = (merged.get("ev_equipment_event_id") or "").strip()
    ofs_event_id = (merged.get("ofs_event_id") or "").strip()
    fsp_project_id = (merged.get("fsp_project_id") or "").strip()
    event_type = (merged.get("event_type") or "").strip()

    outage_start_date = _normalize_date((merged.get("outage_start_date") or "").strip())
    outage_end_date = _normalize_date((merged.get("outage_end_date") or "").strip())
    report_issued_date = _normalize_date((merged.get("report_issued_date") or "").strip())
    outage_type = ""
    technology_type = ""

    if ev_sot_table and any([ev_project_id, ev_equipment_event_id, ofs_event_id, fsp_project_id]):
        try:
            evp = ev_project_id.replace("EVP-", "") if ev_project_id else ""
            ev_id = ev_equipment_event_id.replace("EV-", "") if ev_equipment_event_id else ""
            fsp = fsp_project_id.replace("FSP-", "") if fsp_project_id else ""
            
            where_clauses = []
            if evp:
                where_clauses.append(f"ev_project_id = '{evp}'")
            if ev_id:
                where_clauses.append(f"ev_equipment_event_id = '{ev_id}'")
            if ofs_event_id:
                where_clauses.append(f"ev_gtm_id = '{ofs_event_id}'")
            if fsp:
                where_clauses.append(f"fsp_project_id = '{fsp}'")
            
            if where_clauses:
                where_sql = " OR ".join(where_clauses)
                ev_row = spark.sql(f"""
                    SELECT ev_event_type, p6_outage_start_date, p6_outage_end_date
                    FROM {ev_sot_table}
                    WHERE {where_sql}
                    LIMIT 1
                """).first()
                if ev_row:
                    event_type = event_type or (ev_row.ev_event_type or "")
                    outage_start_date = outage_start_date or (ev_row.p6_outage_start_date or "")
                    outage_end_date = outage_end_date or (ev_row.p6_outage_end_date or "")
        except Exception as e:
            log.warning(f"  [EV-SKIP] {doc_id[:40]}: {e}")

    if psot_table and ev_equipment_event_id:
        try:
            ev_id = ev_equipment_event_id.replace("EV-", "")
            psot_row = spark.sql(f"""
                SELECT outage_type, technology_type
                FROM {psot_table}
                WHERE ev_equipment_event_id = '{ev_id}'
                LIMIT 1
            """).first()
            if psot_row:
                outage_type = psot_row.outage_type or ""
                technology_type = psot_row.technology_type or ""
        except Exception as e:
            log.warning(f"  [PSOT-SKIP] {doc_id[:40]}: {e}")

    preprocessor_regions = json.dumps(regions) if regions else None
    inactive_raw = (proc_meta or {}).get("inactive_esns")
    inactive_esns = (
        json.dumps(sorted(e.strip() for e in inactive_raw.split(",") if e.strip()))
        if inactive_raw else None
    )

    rec = {
        "document_id": doc_id,
        "pdf_name": parsed_doc.filename,
        "volume_path": parsed_doc.volume_path,
        "title": merged.get("document_name") or "",
        "customer": merged.get("customer") or "",
        "primary_esn": primary_esn,
        "primary_equip_type": primary_equip_type,
        "gt_esn": merged.get("gt_esn") or "",
        "gen_esn": merged.get("gen_esn") or "",
        "st_esn": merged.get("st_esn") or "",
        "primary_equip_sys_id": primary_equip_sys_id,
        "primary_equip_class_code": primary_equip_class_code,
        "event_type": event_type,
        "ev_project_id": ev_project_id,
        "ev_equipment_event_id": ev_equipment_event_id,
        "ofs_event_id": ofs_event_id,
        "fsp_project_id": fsp_project_id,
        "xxx_project_id": merged.get("xxx_project_id") or "",
        "fsr_number": merged.get("fsr_number") or "",
        "report_issued_date": report_issued_date,
        "outage_start_date": outage_start_date,
        "outage_end_date": outage_end_date,
        "job_start_date": _normalize_date((merged.get("job_start_date") or "").strip()) or None,
        "approved_date": _normalize_date((merged.get("approved_date") or "").strip()) or None,
        "doc_date": _normalize_date((doc_date or "").strip()) or None,
        "doc_year": doc_year,
        "doc_date_source": doc_date_source or None,
        "outage_type": outage_type,
        "technology_type": technology_type,
        "prepared_by": merged.get("prepared_by") or "",
        "approved_by": merged.get("approved_by") or "",
        "document_summary": merged.get("document_summary"),
        "page_count": len(parsed_doc.pages),
        "file_size_bytes": file_size_bytes,
        "file_last_modified": str(file_last_modified) if file_last_modified else None,
        "parsed_volume_path": parsed_doc.parsed_volume_path or None,
        "parsed_parser_version": parsed_doc.parser_version or None,
        "preprocessor_regions": preprocessor_regions,
        "inactive_esns": inactive_esns,
        "extractor_method": extractor_method,
        "preprocess_method": preprocess_method,
        "llm_model_extraction": llm_model,
        "llm_extraction_prompt_version": llm_extraction_prompt_version,
        "pipeline_version": pipeline_version,
        "run_id": run_id,
    }

    # Derive human-readable pdf_name — mirrors v1 priority cascade:
    # (1) fsr_pdf_ref curated name, (2) contextual composite, (3) volume filename fallback.
    def _sanitize_name_part(v: str) -> str:
        t = str(v).strip()
        if not t:
            return ""
        t = re.sub(r"\s+", " ", t)
        t = re.sub(r"[^A-Za-z0-9._ -]", "", t)
        return t.replace(" ", "_").strip("_")

    _pdf_name_resolved = False

    # Priority 1: fsr_pdf_ref curated name (match on filename stem, case-insensitive)
    if pdf_ref_table:
        try:
            _safe_doc_id = doc_id.replace("'", "''")
            _ref_row = spark.sql(f"""
                SELECT PDF_name
                FROM {pdf_ref_table}
                WHERE LOWER(REGEXP_REPLACE(TRIM(s3_filename), '(?i)\\.pdf$', '')) = '{_safe_doc_id}'
                LIMIT 1
            """).first()
            if _ref_row and _ref_row.PDF_name and str(_ref_row.PDF_name).strip():
                rec["pdf_name"] = str(_ref_row.PDF_name).strip()
                _pdf_name_resolved = True
                log.info(f"  [PDF-REF] {doc_id[:40]}: pdf_name from fsr_pdf_ref")
        except Exception as _e:
            log.warning(f"  [PDF-REF-SKIP] {doc_id[:40]}: {_e}")

    # Priority 2: contextual composite from enriched fields
    if not _pdf_name_resolved:
        _name_parts = [
            _sanitize_name_part(rec.get("customer") or ""),
            _sanitize_name_part(rec.get("primary_equip_type") or ""),
            _sanitize_name_part(rec.get("primary_esn") or ""),
            _sanitize_name_part(rec.get("outage_start_date") or ""),
        ]
        _contextual_pdf_name = "_".join(p for p in _name_parts if p)
        if _contextual_pdf_name:
            rec["pdf_name"] = _contextual_pdf_name
        # else: keep parsed_doc.filename (volume path stem) as fallback

    import pandas as pd  # noqa: PLC0415

    sdf = spark.createDataFrame(pd.DataFrame([rec]))
    sdf.createOrReplaceTempView("_fsr_v2_enriched")

    _merge_sql = f"""
        MERGE INTO {metadata_table} AS tgt
        USING _fsr_v2_enriched AS src
        ON tgt.document_id = src.document_id
        WHEN MATCHED THEN UPDATE SET
            tgt.pdf_name                 = src.pdf_name,
            tgt.title                    = src.title,
            tgt.customer                 = src.customer,
            tgt.primary_esn              = src.primary_esn,
            tgt.primary_equip_type       = src.primary_equip_type,
            tgt.gt_esn                   = src.gt_esn,
            tgt.gen_esn                  = src.gen_esn,
            tgt.st_esn                   = src.st_esn,
            tgt.primary_equip_sys_id     = src.primary_equip_sys_id,
            tgt.primary_equip_class_code = src.primary_equip_class_code,
            tgt.event_type               = src.event_type,
            tgt.ev_project_id            = src.ev_project_id,
            tgt.ev_equipment_event_id    = src.ev_equipment_event_id,
            tgt.ofs_event_id             = src.ofs_event_id,
            tgt.fsp_project_id           = src.fsp_project_id,
            tgt.xxx_project_id           = src.xxx_project_id,
            tgt.fsr_number               = src.fsr_number,
            tgt.report_issued_date       = src.report_issued_date,
            tgt.outage_start_date        = src.outage_start_date,
            tgt.outage_end_date          = src.outage_end_date,
            tgt.job_start_date           = src.job_start_date,
            tgt.approved_date            = src.approved_date,
            tgt.doc_date                 = src.doc_date,
            tgt.doc_year                 = src.doc_year,
            tgt.doc_date_source          = src.doc_date_source,
            tgt.outage_type              = src.outage_type,
            tgt.technology_type          = src.technology_type,
            tgt.prepared_by              = src.prepared_by,
            tgt.approved_by              = src.approved_by,
            tgt.document_summary         = src.document_summary,
            tgt.page_count               = src.page_count,
            tgt.parsed_volume_path       = src.parsed_volume_path,
            tgt.parsed_parser_version    = src.parsed_parser_version,
            tgt.preprocessor_regions     = src.preprocessor_regions,
            tgt.inactive_esns            = src.inactive_esns,
            tgt.extractor_method         = src.extractor_method,
            tgt.preprocess_method        = src.preprocess_method,
            tgt.llm_model_extraction     = src.llm_model_extraction,
            tgt.llm_extraction_prompt_version = src.llm_extraction_prompt_version,
            tgt.pipeline_version         = src.pipeline_version,
            tgt.run_id                   = src.run_id,
            tgt.metadata_status          = 'completed',
            tgt.metadata_error           = NULL,
            tgt.metadata_retry_count     = 0,
            tgt.chunk_status             = 'pending',
            tgt.chunk_error              = NULL,
            tgt.chunk_retry_count        = 0,
            tgt.scraped_at               = current_timestamp(),
            tgt.updated_at               = current_timestamp()
        WHEN NOT MATCHED THEN INSERT (
            document_id, pdf_name, volume_path, title, customer,
            primary_esn, primary_equip_type, gt_esn, gen_esn, st_esn, primary_equip_sys_id, primary_equip_class_code,
            event_type, ev_project_id, ev_equipment_event_id, ofs_event_id,
            fsp_project_id, xxx_project_id, fsr_number,
            report_issued_date, outage_start_date, outage_end_date, job_start_date, approved_date,
            doc_date, doc_year, doc_date_source,
            outage_type, technology_type, prepared_by, approved_by,
            document_summary,
            page_count, file_size_bytes, file_last_modified,
            parsed_volume_path, parsed_parser_version,
            preprocessor_regions, inactive_esns,
            extractor_method, preprocess_method, llm_model_extraction, llm_extraction_prompt_version,
            pipeline_version, run_id,
            metadata_status, metadata_retry_count, chunk_status, ingested_at, scraped_at, updated_at
        ) VALUES (
            src.document_id, src.pdf_name, src.volume_path, src.title, src.customer,
            src.primary_esn, src.primary_equip_type, src.gt_esn, src.gen_esn, src.st_esn, src.primary_equip_sys_id, src.primary_equip_class_code,
            src.event_type, src.ev_project_id, src.ev_equipment_event_id, src.ofs_event_id,
            src.fsp_project_id, src.xxx_project_id, src.fsr_number,
            src.report_issued_date, src.outage_start_date, src.outage_end_date, src.job_start_date, src.approved_date,
            src.doc_date, src.doc_year, src.doc_date_source,
            src.outage_type, src.technology_type, src.prepared_by, src.approved_by,
            src.document_summary,
            src.page_count, src.file_size_bytes, src.file_last_modified,
            src.parsed_volume_path, src.parsed_parser_version,
            src.preprocessor_regions, src.inactive_esns,
            src.extractor_method, src.preprocess_method, src.llm_model_extraction, src.llm_extraction_prompt_version,
            src.pipeline_version, src.run_id,
            'completed', 0, 'pending', current_timestamp(), current_timestamp(), current_timestamp()
        )
    """
    _run_merge_with_retry(spark, _merge_sql, doc_id)
    log.info(f"  [MERGED] {doc_id[:40]}  primary_esn={primary_esn}  equip_type={primary_equip_type}")
    return rec
