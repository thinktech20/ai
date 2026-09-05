# Verification: ds-experimentation-code vs Data Engineering & Ingestion

**Date:** 2026-04-15
**Scope:** Verify whether `ds-experimentation-code` aligns with `reference/ds-team/ds-team-docs/Data Engineering & Ingestion.pdf`

---

## Bottom Line

`ds-experimentation-code` is **partially aligned** with the reference PDF.

It aligns well with the **FSR-specific unstructured ingestion path** described in the reference:
- raw FSR PDFs are read from Databricks Volumes
- metadata is extracted and enriched into a Delta table
- PDF content is chunked and pushed into Databricks Vector Search for RAG-style retrieval

It does **not** implement the full reference architecture end to end. The codebase is a focused POC for the FSR slice, not a full realization of the broader data-engineering strategy in the PDF.

---

## What Aligns

### 1. Databricks-native ingestion pattern is present

The reference PDF describes a Databricks Lakehouse flow using Unity Catalog volumes, Delta tables, and Vector Search.

That is reflected in the code:
- `fsr_scraping/run_scraping_pipeline.py` reads FSR PDFs from Databricks Volume paths under `viud` and `vgpd`
- `fsr_pipeline/src/config.py` reads the same FSR source volumes
- `fsr_pipeline/src/pipeline.py` writes chunk rows to Delta and syncs a Databricks Vector Search index

This is a direct match to the reference document's stated storage and serving approach for unstructured FSR data.

### 2. The code separates metadata extraction from vectorized retrieval

The reference PDF distinguishes between:
- a business metadata layer for field service reports
- a vectorized content layer for semantic search

The codebase has the same split:
- `fsr_scraping/run_scraping_pipeline.py` implements a metadata pipeline
- `fsr_pipeline/src/pipeline.py` implements chunking, Delta storage, and Vector Search sync

This is the strongest architectural alignment in the repo.

### 3. Metadata extraction matches the FSR business-metadata intent

The metadata pipeline in `fsr_scraping/run_scraping_pipeline.py` follows the same broad shape described in the reference:
- Stage 1 extracts fields from FSR PDFs
- Stage 2 normalizes them with an LLM into a fixed schema
- Stage 3 enriches them using IBAT and Event Vision
- Stage 4 appends the results to a Delta table

This aligns with the reference PDF's idea of a cleansed and enriched FSR metadata layer.

### 4. Vectorized content generation matches the agent-ready layer

The reference PDF says the gold layer should produce vectorized content for semantic retrieval.

`fsr_pipeline` does that:
- reads FSR PDFs from volumes
- chunks content with PDF-aware logic
- writes chunk rows to Delta
- syncs a Databricks Vector Search index
- retrieves by hybrid search in `fsr_pipeline/src/retrieval.py`

This aligns with the document's agent-ready retrieval target.

### 5. Traceability is implemented reasonably well for retrieval

The reference PDF stresses traceability back to source documents and pages.

The retrieval pipeline preserves this with fields such as:
- `chunk_id`
- `pdf_name`
- `page_number`
- serialized chunk metadata

That behavior is implemented in `fsr_pipeline/src/delta_store.py` and consumed through `fsr_pipeline/src/retrieval.py`.

---

## What Only Partially Aligns

### 1. The medallion model is implicit, not implemented as the reference names it

The reference PDF explicitly frames the design as Bronze, Silver, and Gold.

The code behaves roughly like that, but it does not implement the named target objects from the PDF:
- raw files stay in source volumes, but there is no explicit Bronze pipeline layer in code
- metadata is written to `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`, not the canonical `biz_metadata_field_service_report` target described in the PDF
- vectorized chunks are written to `main.gp_services_sdg_poc.field_service_report`, not the `vec_field_service_report` target named in the PDF

So the architecture shape is similar, but the object model and catalog placement do not match the reference exactly.

### 2. OCR is not the main mechanism in the implemented pipelines

The reference PDF calls out OCR output as part of the silver layer.

The current code does not center on OCR output:
- `fsr_scraping/run_scraping_pipeline.py` uses `pdfplumber` on the first page
- `fsr_pipeline/src/pdf_processor.py` uses PyMuPDF-based parsing and chunking

That means the implementation assumes readable PDFs and direct text extraction, not a formal OCR-first pipeline writing into the `ocr_field_service_report` volume named in the reference.

### 3. The metadata table is present as a POC output, not as the canonical AI SOT object

The reference PDF describes curated AI-side objects under `VAID`/`VAIQ` schemas.

The DS code writes the metadata output to a POC table:
- `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`

This is functionally aligned, but not aligned in final target schema/catalog placement.

### 4. The retrieval pipeline does not consume the scraping output as a first-class layer

The reference PDF presents an end-to-end lifecycle where cleansed metadata and vectorized content sit inside one broader architecture.

In the current codebase, those two flows exist, but they are not tightly integrated:
- `fsr_scraping` writes metadata output
- `fsr_pipeline` enriches from `vgpd.fsr_std_views.fsr_pdf_ref`
- `fsr_pipeline` does not read `fsr_scraped_file_mapping_ref` as part of retrieval-time enrichment

So the two layers are adjacent, but not yet wired together as one cohesive architecture.

---

## What Does Not Align Yet

### 1. The reference PDF is broader than FSR-only ingestion

The reference covers multiple source systems, including:
- ER database
- PRISM
- OSA Word documents
- process documents/manuals
- Event Vision
- IBAT

`ds-experimentation-code` is mostly centered on the FSR workflow, with supporting use of IBAT and Event Vision. It does not implement the full multi-source ingestion strategy described in the PDF.

### 2. The named AI catalog targets from the reference are not the runtime targets in code

The PDF names targets such as:
- `ai_sot_field_service_report.biz_metadata_field_service_report`
- `ai_std_con_field_service_report.vec_field_service_report`

The code instead uses POC tables under `main.gp_services_sdg_poc`.

That is a concrete mismatch between the documented target architecture and the current implementation.

### 3. Governance and operational pieces from the PDF are mostly outside this codebase

The reference also covers:
- catalog and workspace access model
- distribution lists
- environment separation
- scheduling and workflow strategy
- feedback loop for missing data

Those concerns are not materially implemented in `ds-experimentation-code`. The repo is focused on data-processing logic, not the full operational platform model.

---

## Repo Mapping to the Reference

| Reference concept | Closest implementation in repo | Alignment |
|---|---|---|
| Raw FSR ingestion from Databricks volumes | `fsr_scraping/run_scraping_pipeline.py`, `fsr_pipeline/src/config.py` | Strong |
| FSR business metadata extraction | `fsr_scraping/run_scraping_pipeline.py` | Strong |
| AI-ready vectorized FSR content | `fsr_pipeline/src/pipeline.py` + `fsr_pipeline/src/retrieval.py` | Strong |
| OCR silver layer | Not explicitly implemented as a persistent OCR output layer | Weak |
| Canonical VAID/VAIQ target tables | Not implemented; POC uses `main.gp_services_sdg_poc.*` | Weak |
| Unified end-to-end architecture across all source systems in the PDF | Not implemented in this repo | Weak |

---

## Conclusion

If the question is, "Does `ds-experimentation-code` follow the same FSR ingestion and retrieval direction as the reference PDF?" the answer is **yes, mostly**.

If the question is, "Does it fully implement the reference Data Engineering & Ingestion architecture as documented?" the answer is **no**.

The codebase is best understood as a **working FSR-focused POC** that covers:
- FSR document ingestion from volumes
- metadata extraction and enrichment
- chunking and vector search

The main gaps versus the reference are:
- no explicit OCR-backed silver layer
- no canonical `VAID`/`VAIQ` target objects
- no full multi-source ingestion implementation
- no tight integration yet between the scraping output and the retrieval pipeline

---

## Recommended Next Checks

1. Verify whether `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref` is intended to be promoted into the canonical AI metadata table named in the reference.
2. Verify whether the intended production design requires an OCR persistence layer before chunking.
3. Verify whether retrieval should join against the scraping metadata output, not only `fsr_pdf_ref`.
4. Review the metadata extraction logic in detail against `databricks_layer/docs/07-fsr-metadata-extraction.md`.