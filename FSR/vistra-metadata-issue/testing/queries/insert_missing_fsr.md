-- Insert Missing FSR PDFs in dev (metadata + chunk)
-- Scope: vaid.ai_sot_field_service_report.biz_metadata_field_service_report
--        vaid.ai_std_con_field_service_report.vec_field_service_report
-- Method: Use pipeline job PW_SDG_FSR_Ingestion (preferred), not manual SQL row inserts.

Step 1) Build target list (missing PDFs) and map to document_id

```sql
-- Input: PDF names missing in dev from your validation list.
-- Output: document_id values to pass to FSR_TARGET_PDF_NAMES.
-- For these FSRs, document_id is expected from s3_filename.

WITH target_pdfs AS (
	SELECT * FROM VALUES
		('Field_Service_Report_ProjectID_A-1505048_FSP-253386_C-10323897.pdf')
		-- Add remaining missing PDF names here for batch run
	AS t(pdf_name)
)
SELECT
	t.pdf_name,
	r.s3_filename AS document_id,
	r.esn,
	r.report_issued_date
FROM target_pdfs t
LEFT JOIN vgpd.fsr_std_views.fsr_pdf_ref r
	ON lower(r.pdf_name) = lower(t.pdf_name)
ORDER BY t.pdf_name;
```

Step 2) Identify orphaned/incomplete metadata rows (advisory only—no cleanup)

Before running the job, check which of the 15 target document_ids have incomplete metadata rows from prior failed attempts. This is informational; decide on cleanup approach based on findings.

```sql
-- First, map the 15 missing PDF names to document_id
WITH target_15_missing AS (
	SELECT * FROM VALUES
		('Field_Service_Report_ProjectID_A-1505048_FSP-253386_C-10323897.pdf')
		-- Add remaining 14 missing PDF names here
	AS t(pdf_name)
),
mapped_to_docid AS (
	SELECT
		t15.pdf_name,
		r.s3_filename AS document_id
	FROM target_15_missing t15
	INNER JOIN vgpd.fsr_std_views.fsr_pdf_ref r
		ON r.pdf_name = t15.pdf_name
)
-- Check dev metadata for these document_ids
SELECT
	m.document_id,
	m.pdf_name,
	m.metadata_status,
	m.chunk_status,
	CASE WHEN m.pdf_name IS NULL THEN 'ORPHANED (no pdf_name)' ELSE 'COMPLETE' END AS row_status
FROM mapped_to_docid
LEFT JOIN vaid.ai_sot_field_service_report.biz_metadata_field_service_report m
	ON m.document_id = mapped_to_docid.document_id
ORDER BY mapped_to_docid.pdf_name;
```

**Expected findings:**
- Some rows may show `ORPHANED` (pdf_name IS NULL) — incomplete from prior failed P1 extractions.
- Some rows may show `NULL` for all columns — document_id never existed in dev.

**Note:** Job behavior depends on row_status:
- ORPHANED rows: P1 will skip (already in table); P2 may or may not process depending on chunk_status.
- NULL (no row): P1 will create a new row and extract metadata; P2 will process chunks.

Step 3) Single-PDF smoke test (recommended first)

Use one mapped document_id from Step 1.

Job: PW_SDG_FSR_Ingestion

Runtime parameter overrides:

1. FSR_TARGET_PDF_NAMES = <document_id>
2. FSR_MAX_PDFS = 1
3. FORCE_RESET = true  (force re-extraction if orphaned row was deleted)

Example:

1. FSR_TARGET_PDF_NAMES = 71720880-e6c9-437b-b208-80e6c9437b53
2. FSR_MAX_PDFS = 1
3. FORCE_RESET = true

Step 4) Verify single-PDF result in both tables

```sql
WITH target AS (
	SELECT
		'Field_Service_Report_ProjectID_A-1505048_FSP-253386_C-10323897.pdf' AS pdf_name,
		'71720880-e6c9-437b-b208-80e6c9437b53' AS document_id
)
SELECT
	t.pdf_name,
	t.document_id,
	CASE WHEN m.document_id IS NULL THEN 'N' ELSE 'Y' END AS in_metadata,
	CASE WHEN c.document_id IS NULL THEN 'N' ELSE 'Y' END AS in_chunk,
	COALESCE(c.chunk_rows, 0) AS chunk_rows
FROM target t
LEFT JOIN (
	SELECT document_id, max(pdf_name) AS pdf_name
	FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
	GROUP BY document_id
) m ON m.document_id = t.document_id
LEFT JOIN (
	SELECT document_id, count(*) AS chunk_rows
	FROM vaid.ai_std_con_field_service_report.vec_field_service_report
	GROUP BY document_id
) c ON c.document_id = t.document_id;
```

Step 5) Batch run for all 15 missing

After single-PDF succeeds, run same job with all missing document_id values.

Runtime parameter overrides:

1. FSR_TARGET_PDF_NAMES = <comma-separated document_id list>
2. FSR_MAX_PDFS = 15
3. FORCE_RESET = true  (to force re-extraction for any orphaned rows)

Notes:

1. FSR_TARGET_PDF_NAMES accepts document_id values, not full pdf_name.
2. Keep values lowercase where applicable.
3. Set FORCE_RESET=true to re-extract if orphaned rows exist.

Step 6) Post-run verification for full missing set

```sql
-- Replace VALUES with your 15 missing PDF names.
WITH target_pdfs AS (
	SELECT * FROM VALUES
		('Field_Service_Report_ProjectID_A-1505048_FSP-253386_C-10323897.pdf')
		-- Add remaining missing PDF names here
	AS t(pdf_name)
),
dev_chunked AS (
	SELECT DISTINCT pdf_name
	FROM vaid.ai_std_con_field_service_report.vec_field_service_report
),
dev_metadata AS (
	SELECT DISTINCT pdf_name
	FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
)
SELECT
	t.pdf_name,
	CASE WHEN c.pdf_name IS NULL THEN 'N' ELSE 'Y' END AS in_dev_chunk_table,
	CASE WHEN m.pdf_name IS NULL THEN 'N' ELSE 'Y' END AS in_dev_metadata_table
FROM target_pdfs t
LEFT JOIN dev_chunked c ON c.pdf_name = t.pdf_name
LEFT JOIN dev_metadata m ON m.pdf_name = t.pdf_name
ORDER BY t.pdf_name;
```

Expected after successful load:

1. All target rows show in_dev_chunk_table = Y
2. All target rows show in_dev_metadata_table = Y
3. Missing counts drop to 0 for the loaded target set

