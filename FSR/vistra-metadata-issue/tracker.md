## 2026-06-04 Progress Update

1. Validated target set from Vistra workbook (47 PDFs with Gap Confirmed = YES).
2. Confirmed current dev state:
	- 32 present in chunk + metadata
	- 15 missing from chunk
	- same 15 also missing by pdf_name in metadata
3. Ran deeper check for the 15 missing:
	- only 1 PDF maps to a document_id in `vgpd.fsr_std_views.fsr_pdf_ref`
	- mapped PDF: Field_Service_Report_ProjectID_A-1505048_FSP-253386_C-10323897.pdf
	- document_id: 71720880-e6c9-437b-b208-80e6c9437b53
	- dev metadata row exists as orphaned (pdf_name = NULL), metadata_status = failed, chunk_status = pending
4. Remaining 14 missing PDFs currently do not map to document_id (NULL mapping), so they are not targetable via `FSR_TARGET_PDF_NAMES` yet.

## Current Blocker

- Ingestion target mode depends on document_id mapping.
- For the 14 unmapped reports, mapping is missing in reference table.
- For the 1 mapped report, metadata row is incomplete/orphaned.

## Why Metadata Step Kept Running

- This is not only discovery mode. P1 processes a work queue built from metadata rows with status `pending` plus `failed` under retry cap.
- In this run, discovery found 0 new files, but target filtering still picked the existing row for document_id `71720880-e6c9-437b-b208-80e6c9437b53` (status `failed`).
- That row has a valid `volume_path`, so PDF extraction ran (`pages=730`) and then called LLM normalization.
- Runtime looked "forever" because LLM call retries are expensive when gateway is timing out (multiple attempts with 120s request timeout plus backoff).

## Immediate Next Step

1. Do not keep re-running P1 for this same doc while LLM gateway timeouts continue.
2. Raise as pipeline behavior bug/improvement: when target discovery returns 0 and only retry-eligible failed rows remain, log an explicit warning and allow skip mode for LLM retries.
3. Continue reporting-only path for the 15 docs (no cleanup), and wait for mapping/gateway decisions.

## Next Steps

1. Share findings summary with team for reference-table/mapping confirmation of the 14 unmapped reports.
2. Decide handling approach for orphaned mapped row (observe-only vs remediation in dev).
3. After mapping decisions, re-run targeted ingestion for only valid mapped document_ids.