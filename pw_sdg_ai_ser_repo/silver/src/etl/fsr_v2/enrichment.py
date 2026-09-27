"""Stage 4 — Metadata Enrichment Orchestrator.

Coordinates two sub-steps:
1) LLM normalization (cover-page/admin fields)
2) Merge + deterministic enrichment (IBAT/EV/PSOT) + metadata MERGE
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pyspark.sql import SparkSession

from common.fsr_v2.enums import ExtractorMethod, PreprocessMethod, LLMExtractionPromptVersion
from .llm_normalization import extract_llm_metadata
from .metadata_enrichment import _normalize_date, write_enriched_metadata
from .parsing import ParsedDocument, determine_doc_date

log = logging.getLogger("fsr.v2.enrichment")


def run(
    spark: "SparkSession",
    parsed_doc: ParsedDocument,
    processor_output: dict,
    metadata_table: str,
    *,
    llm_base_url: str,
    llm_api_key: str,
    llm_model: str,
    llm_verify_ssl: Any = True,
    file_size_bytes: int | None = None,
    file_last_modified: Any = None,
    ibat_table: str | None = None,
    ev_sot_table: str | None = None,
    psot_table: str | None = None,
    pdf_ref_table: str | None = None,
    extractor_method: str = ExtractorMethod.PYPDF2_V1_0.value,
    preprocess_method: str = PreprocessMethod.PREPROCESSOR_V2_FINAL.value,
    llm_extraction_prompt_version: str = LLMExtractionPromptVersion.V2_WITH_HINTS.value,
    pipeline_version: str = "fsr_v2.0",
    run_id: str | None = None,
    llm_meta: dict | None = None,
) -> dict:
    """Run Stage 4 for one parsed document and merge into metadata table.

    If llm_meta is provided the LLM call is skipped (used with batch extraction).
    """
    proc_meta = processor_output.get("metadata", {})
    hints = processor_output.get("hints", "")
    regions = processor_output.get("regions", [])

    page1_text = parsed_doc.pages[0] if parsed_doc.pages else ""
    if llm_meta is None:
        llm_meta = extract_llm_metadata(
            page1_text,
            parsed_doc.volume_path,
            hints,
            llm_extraction_prompt_version=llm_extraction_prompt_version,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
            llm_model=llm_model,
            llm_verify_ssl=llm_verify_ssl,
        )

    # Resolve the canonical document date unconditionally — it is persisted for
    # every document, not just when a year bound happens to be configured.
    # Normalize first: the LLM returns formats like '10 Mar 2023', and reading the
    # year off the raw string would silently yield None and skip the filter.
    _date_str, _date_src = determine_doc_date(
        llm_meta.get("outage_start_date"),
        llm_meta.get("job_start_date"),
        llm_meta.get("approved_date"),
        llm_meta.get("report_issued_date"),
    )
    _date_str = _normalize_date(_date_str or "") or None
    _year_match = re.match(r"(\d{4})", _date_str or "")
    _doc_year = int(_year_match.group(1)) if _year_match else None

    return write_enriched_metadata(
        spark,
        parsed_doc,
        metadata_table,
        proc_meta=proc_meta,
        regions=regions,
        llm_meta=llm_meta,
        file_size_bytes=file_size_bytes,
        file_last_modified=file_last_modified,
        ibat_table=ibat_table,
        ev_sot_table=ev_sot_table,
        psot_table=psot_table,
        pdf_ref_table=pdf_ref_table,
        extractor_method=extractor_method,
        preprocess_method=preprocess_method,
        llm_model=llm_model,
        llm_extraction_prompt_version=llm_extraction_prompt_version,
        pipeline_version=pipeline_version,
        run_id=run_id,
        doc_date=_date_str,
        doc_year=_doc_year,
        doc_date_source=_date_src,
    )
