Step 1 – Discovery

- Discover work in one of three modes: target-doc mode, processing the existing pending/failed backlog already in the metadata table, or full volume discovery.
- If there are already pending or retry-eligible failed documents in the metadata table, the run processes that existing backlog first and skips fresh volume discovery for that run.
- For full discovery, list configured volume paths and derive document_id from filename stem, then anti-join against existing metadata document_ids.
- MERGE stub rows for newly discovered docs into the metadata table with metadata_status='pending' and chunk_status='pending'.
- If FORCE_RESET=true in non-prod, truncate the metadata table first and then rescan all files.

Step 2 – PDF Extraction

- Build the work queue from metadata_status='pending' plus retry-eligible failed rows under the retry cap.
- Failed documents are not retried indefinitely; a failed document is retried only while metadata_retry_count is below P1_MAX_RETRIES, after which it remains failed until manually addressed.
- Open each PDF with pdfplumber, extract page-1 text and title heuristically, and capture page_count.
- Carry file_size_bytes and file_last_modified from the discovery stub/listing metadata.

Step 3 – LLM Normalisation

- Send page-1 extracted key/value text to the LLM, default model gemini-3-flash.
- Normalize the core metadata fields such as esn, equipment_sys_id, event/project IDs, FSR number, and outage/report dates.
- Title is not produced by the LLM here; it is extracted before the LLM step.

Step 4 – Enrichment

- fsr_pdf_ref: resolve pdf_name, validate/override ESN when needed, and build all_esns.
- Multiple ESNs are identified in the metadata step from fsr_pdf_ref plus the resolved primary ESN; if all_esns contains more than one ESN for a document, that set is carried forward into the write step.
- ibat_equipment_mst: match on equipment_sys_id or esn to fill equipment_type, equipment_class_code, and backfill esn / equipment_sys_id if blank.
- eventmgmt_event_vision_sot: use available event/project identifiers to fill event_type, outage_start_date, and outage_end_date.
- PSOT: match on ev_equipment_event_id to set outage_type and technology_type.

Step 5 – Write

- MERGE successful metadata results into the metadata table.
- On success, set metadata_status='completed', clear metadata_error, reset metadata_retry_count, and stamp scraped_at.
- On failure, set metadata_status='failed', write metadata_error, increment metadata_retry_count, and stamp scraped_at.
- If a PDF is associated with multiple ESNs, the metadata step keeps the primary row for the main ESN and can insert additional metadata rows for the secondary ESNs in the same write step.


## Process 2 – Chunking & Vector Embedding

### Purpose

- Read eligible documents from the Process 1 metadata table.
- Load the full PDF content from `volume_path` using PyMuPDF.
- Apply hierarchical/section-aware chunking to the full document text.
- Generate embeddings via LiteLLM using the configured embedding model (default: `azure-text-embedding-3-large-1`) and write chunk rows to the Delta chunk table.
- Trigger Databricks Vector Search sync at the end of the run.

### Input

- **Source table:** `vaid/vaiq/vaip.ai_sot_field_service_report.biz_metadata_field_service_report`
- Process 2 does not scan volumes directly; it reads from the metadata table and uses `volume_path` on each row to load the physical PDF.
- The processing queue is limited to rows where:
	- `metadata_status = 'completed'`
	- `chunk_status IN ('pending', 'failed')`
	- `chunk_retry_count < P2_MAX_RETRIES`
- Before claiming new work, the notebook also recovers stale `in_progress` rows back to `pending` if they were left behind by an earlier crashed run.

### Processing Steps

- Claim a batch of eligible documents by setting `chunk_status = 'in_progress'`.
- For each claimed row, use `volume_path` to load the PDF from the Unity Catalog volume.
- Extract full text with PyMuPDF and run hierarchical semantic chunking.
- Optionally run Tier 2 ESN detection on full document text if `FSR_ESN_DETECT_ENABLED=true`.
- Build chunk rows by denormalizing metadata from the source metadata row onto each chunk.
- For multi-ESN documents, expand chunk rows across ESNs using `fsr_pdf_ref`, the metadata ESN, and optional Tier 2 ESN detection.
- Generate embeddings via LiteLLM using the configured embedding model (default: `azure-text-embedding-3-large-1`).
- MERGE chunk rows into the Delta chunk table.
- On success, set source-row `chunk_status = 'completed'`, clear `chunk_error`, reset `chunk_retry_count`, and stamp `chunked_at`.
- On failure, set source-row `chunk_status = 'failed'`, populate `chunk_error`, increment `chunk_retry_count`, and stamp `chunked_at`.
- Trigger Databricks Vector Search sync once after the batch loop completes.

### Output

- **Output Delta table:** `vaid/vaiq/vaip.ai_std_con_field_service_report.vec_field_service_report`
- **Output Vector Search index:** `vaid/vaiq/vaip.ai_std_con_field_service_report.vs_vec_field_service_report`


## Open Items

- P1 discovery / BACKLOG trigger still counts all failed rows when deciding whether to skip fresh volume discovery, even though Process 1 Step 2 (PDF Extraction / work-queue build) already retries only failed rows under `P1_MAX_RETRIES`; retry-exhausted failures can therefore still keep discovery from picking up new PDFs.
- P2 claim flow should be made atomic so parallel chunking jobs cannot race on the same documents.
- Vector Search sync should be decoupled from the end of the P2 drain loop so long backfills do not leave the index far behind the chunk table.
- `FORCE_RESET` should be moved out of the normal ingestion path into a separate destructive/admin flow.
- Re-upload handling is only partially implemented: the pipeline now stores source-file metadata such as `file_last_modified`, but if an existing PDF is replaced with newer content under the same `document_id`, the pipeline does not yet automatically detect that change and re-run metadata extraction / chunking for that document.
- Tier 2 ESN detection should move from P2 into P1 before broad enablement so metadata ownership stays in one place.
- Multi-ESN train-sibling expansion is still open; the current standard path uses `fsr_pdf_ref` plus optional Tier 2 LLM detection, but it does not yet add Generator / GT / ST sibling ESNs from IBAT train relationships as a general rule.
- The additive schema change to store all ESNs as an `esns ARRAY<STRING>` on metadata / chunk tables, and expose that field for Vector Search filtering, is still open; current code still uses `all_esns` on metadata and a single top-level `esn` on chunk rows.

