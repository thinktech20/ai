# Verify Whether `ds-experimentation-code` Aligns to `reference/ds-team/ds-team-docs/Data Engineering & Ingestion.pdf`

## Finding

`ds-experimentation-code` is **partially aligned** to the reference `Data Engineering & Ingestion.pdf`.

It aligns well with the **FSR-specific ingestion and retrieval path** described in the reference:
- reads FSR PDFs from Databricks Volumes
- extracts and enriches FSR metadata into a Delta table
- chunks FSR content and syncs it to Databricks Vector Search

It does **not** fully implement the broader reference architecture end to end.

## What Aligns

1. `fsr_scraping` matches the metadata-extraction part of the design.
2. `fsr_pipeline` matches the chunking plus vector-search part of the design.
3. The repo uses the same general Databricks pattern described in the PDF: volumes, Delta tables, and Vector Search.
4. The retrieval pipeline preserves source traceability through fields like `chunk_id`, `pdf_name`, and `page_number`.

## What Is Only Partially Aligned

1. The code behaves roughly like Bronze, Silver, Gold, but it does not implement the exact named target objects described in the PDF.
2. The implemented pipelines rely on direct PDF text extraction using `pdfplumber` and PyMuPDF, not a clearly defined persisted OCR layer.
3. The metadata output and the retrieval pipeline exist as separate flows, but they are not fully integrated into one canonical architecture.

## What Does Not Align Yet

1. The reference PDF covers a broader multi-source ingestion design, while this repo is mainly focused on the FSR slice.
2. The code writes to POC tables under `main.gp_services_sdg_poc.*`, not the canonical AI-side objects named in the reference.
3. The repo does not implement the full governance, environment, and operational workflow model described in the PDF.

## Conclusion

If the question is whether the repo follows the same **direction** as the reference for FSR ingestion, the answer is **yes**.

If the question is whether it fully implements the documented **Data Engineering & Ingestion** architecture, the answer is **no**.

This repo is best understood as an **FSR-focused POC** that covers metadata extraction and vector retrieval, but not the full target architecture from the reference document.

## Detailed Note

Detailed comparison is captured in:

- `implementation/fsr-processing/design/01-data-engineering-ingestion-alignment.md`

---

## Metadata Flow Diagram Review

Reviewed diagram: `internal/architecture-assets/fsr-processing/metdata-flow.png`

### Interpretation of the Colors

**Green boxes** appear to represent the main pipeline blocks or confirmed sections:
- `Landing zone/DBR Volumes`
- `Scraping Process`
- `Chunks ingestion Pipeline (chunking and embeddings)`

**Yellow box** appears to represent an open question or assumption under review:
- `Enrich it with meta data? so scraping process would be happening here`

### What the Diagram Gets Right

1. It correctly shows that FSR PDFs land in Databricks volumes first.
2. It correctly shows the scraping pipeline as a 3-stage flow:
	- PDF field extraction
	- LLM normalisation
	- IBAT + Event Vision enrichment
3. It correctly treats metadata extraction and chunk ingestion as separate flows.
4. It correctly suggests that both flows originate from the same FSR document set.

### What Needs Correction

1. The current code does **not** default to `vgpd.fsr_std_views.fsr_scraped_file_mapping_ref`.
	The actual default output in the DS experimentation code is:
	`main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`
2. The yellow-box assumption is not correct as currently written.
	The scraping process should **not** be shown as happening inside the chunk ingestion pipeline.
3. The current repo behavior is:
	- one separate FSR metadata pipeline
	- one separate chunking/vector pipeline
	- intended integration later through joins, especially in the `query_fsr` path

### Assessment

The diagram is **mostly correct structurally**, but it should be adjusted in one important way:

- keep the scraping pipeline separate from the chunk ingestion pipeline
- show the combination point as a later join or downstream enrichment step, not as chunk-ingestion-internal logic

### Suggested Cleaner Flow

1. `Landing zone / DBR Volumes`
2. `Scraping process` -> `FSR metadata table`
3. `Chunk ingestion pipeline` -> `FSR chunk table / Vector Search source`
4. `query_fsr` or downstream enrichment step joins:
	- chunk table
	- `fsr_pdf_ref`
	- `fsr_scraped_file_mapping_ref`
	- `fsr_field_vision_field_services_report_psot`

### Reusable Reply

You can send this back to your colleague:

"I checked the flow. The green boxes look like the main confirmed pipeline blocks, and the yellow box looks like an open design question. The overall structure is mostly right: raw FSR PDFs land in Databricks volumes, there is a separate 3-stage scraping pipeline for FSR metadata, and there is a separate chunking/embedding pipeline for retrieval. The main correction is that the scraping process should not be shown as happening inside the chunk ingestion pipeline. In the current repo, they are separate flows and are intended to be combined later by joins, especially in the `query_fsr` path. Also, the current POC write target is `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`, not `vgpd.fsr_std_views.fsr_scraped_file_mapping_ref` by default." 
