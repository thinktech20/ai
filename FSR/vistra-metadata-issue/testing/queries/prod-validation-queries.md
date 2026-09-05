# Prod validation queries — Vistra cross-train repair

Use these queries after the prod repair run to validate one PDF or a small set of PDFs end to end.

Scope:
- Catalogs below are for prod: `vaip.ai_sot_field_service_report` and `vaip.ai_std_con_field_service_report`.
- These checks validate both metadata rows and chunk rows for the repaired document family.
- Replace the sample values as needed.

---

## Suggested validation order

Run these first for fast pass/fail validation of a prod run:

1. **Section 7 (count + missing-only):** confirm all completed rows have repaired metadata.
2. **Section 8 (count + missing-only):** confirm all completed rows have repaired chunks.
3. **Section 6:** check base vs repaired chunk parity (`chunk_diff = 0`) for a targeted sample set.
4. **Section 1 + Section 2:** deep-dive one or two sample base documents when needed.

Quick pass criteria:
- metadata missing-only query returns no rows
- chunk missing-only query returns no rows
- chunk parity query shows `chunk_diff = 0` for validated sample PDFs

---

## 1. Metadata family for one base document

Use this to inspect the full metadata family for one base `document_id`, including the repaired Generator row.

Example base document:
- `BASE_DOC_ID = 732f755b-38d3-4e7a-af75-5b38d34e7add`

```sql
SELECT
  document_id,
  pdf_name,
  esn,
  esn_source,
  equipment_type,
  metadata_status,
  chunk_status,
  event_type,
  ev_project_id,
  ev_equipment_event_id
FROM vaip.ai_sot_field_service_report.biz_metadata_field_service_report
WHERE document_id = '732f755b-38d3-4e7a-af75-5b38d34e7add'
   OR document_id LIKE '732f755b-38d3-4e7a-af75-5b38d34e7add_%'
ORDER BY document_id;
```

Expected shape:
- base row present
- repaired Generator row present as `<BASE_DOC_ID>_<MISSING_ESN>`
- repaired row `esn_source = 'cross_tag_gap_v1'`
- repaired row `equipment_type = 'Generator'`

---

## 2. Chunk family for one base document

Use this to inspect chunk counts across the same document family.

```sql
SELECT
  document_id,
  esn,
  COUNT(*) AS chunk_rows,
  MIN(chunk_index) AS min_chunk_index,
  MAX(chunk_index) AS max_chunk_index
FROM vaip.ai_std_con_field_service_report.vec_field_service_report
WHERE document_id = '732f755b-38d3-4e7a-af75-5b38d34e7add'
   OR document_id LIKE '732f755b-38d3-4e7a-af75-5b38d34e7add_%'
GROUP BY document_id, esn
ORDER BY document_id, esn;
```

Expected shape:
- base document chunk rows present
- repaired Generator document chunk rows present
- repaired chunk count should match the base document's relevant chunk count

---

## 3. Combined metadata + chunk count view for one base document

Use this when you want one result set showing metadata attributes plus chunk counts together.

```sql
WITH meta AS (
  SELECT
    document_id,
    pdf_name,
    esn,
    esn_source,
    equipment_type,
    metadata_status,
    chunk_status
  FROM vaip.ai_sot_field_service_report.biz_metadata_field_service_report
  WHERE document_id = '732f755b-38d3-4e7a-af75-5b38d34e7add'
     OR document_id LIKE '732f755b-38d3-4e7a-af75-5b38d34e7add_%'
),
chunks AS (
  SELECT
    document_id,
    esn,
    COUNT(*) AS chunk_rows
  FROM vaip.ai_std_con_field_service_report.vec_field_service_report
  WHERE document_id = '732f755b-38d3-4e7a-af75-5b38d34e7add'
     OR document_id LIKE '732f755b-38d3-4e7a-af75-5b38d34e7add_%'
  GROUP BY document_id, esn
)
SELECT
  m.document_id,
  m.pdf_name,
  m.esn,
  m.esn_source,
  m.equipment_type,
  m.metadata_status,
  m.chunk_status,
  COALESCE(c.chunk_rows, 0) AS chunk_rows
FROM meta m
LEFT JOIN chunks c
  ON c.document_id = m.document_id
 AND c.esn = m.esn
ORDER BY m.document_id, m.esn;
```

---

## 4. Raw chunk-row inspection for one base document

Use this to inspect actual chunk rows and the `metadata` JSON payload.

```sql
SELECT
  document_id,
  chunk_id,
  chunk_index,
  esn,
  metadata
FROM vaip.ai_std_con_field_service_report.vec_field_service_report
WHERE document_id = '732f755b-38d3-4e7a-af75-5b38d34e7add'
   OR document_id LIKE '732f755b-38d3-4e7a-af75-5b38d34e7add_%'
ORDER BY document_id, chunk_index
LIMIT 200;
```

What to inspect in `metadata` for the repaired Generator rows:
- `esn`
- `equipment_sys_id`
- `equipment_type = 'Generator'`
- `equipment_class_code`

---

## 5. Verification for an array of PDFs from staging

Use this when validating a small set of PDFs by `pdf_stem` from the staging table.

Replace the `VALUES` block with the target `pdf_stem` values.

```sql
WITH target_pdfs AS (
  SELECT * FROM VALUES
    ('field_service_report_projectid_a-1376570_ev-113525_c-10350370'),
    ('field_service_report_projectid_a-1376780_fsp-261003_c-10330252')
  AS t(pdf_stem)
)
SELECT
  s.pdf_stem,
  s.document_id AS base_document_id,
  s.missing_esn,
  s.prod_status,
  m.document_id AS repaired_document_id,
  m.esn AS repaired_esn,
  m.esn_source,
  m.equipment_type,
  COUNT(c.chunk_id) AS repaired_chunk_rows
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
LEFT JOIN vaip.ai_sot_field_service_report.biz_metadata_field_service_report m
  ON m.document_id = CONCAT(s.document_id, '_', s.missing_esn)
LEFT JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
  ON c.document_id = CONCAT(s.document_id, '_', s.missing_esn)
 AND UPPER(TRIM(c.esn)) = UPPER(TRIM(s.missing_esn))
JOIN target_pdfs t
  ON t.pdf_stem = s.pdf_stem
WHERE LOWER(s.confidence) = 'confirmed'
GROUP BY
  s.pdf_stem,
  s.document_id,
  s.missing_esn,
  s.prod_status,
  m.document_id,
  m.esn,
  m.esn_source,
  m.equipment_type
ORDER BY s.pdf_stem;
```

Expected shape:
- `prod_status = 'done'` for completed rows
- repaired `document_id` present
- repaired `esn_source = 'cross_tag_gap_v1'`
- repaired `equipment_type = 'Generator'`
- repaired chunk count `> 0`

---

## 6. Base vs repaired chunk parity for an array of PDFs

Use this to compare base and repaired chunk counts side by side for a small set of PDFs.

```sql
WITH target_pdfs AS (
  SELECT * FROM VALUES
    ('field_service_report_projectid_a-1376570_ev-113525_c-10350370'),
    ('field_service_report_projectid_a-1376780_fsp-261003_c-10330252')
  AS t(pdf_stem)
),
base_counts AS (
  SELECT
    s.pdf_stem,
    s.document_id AS base_document_id,
    COUNT(*) AS base_chunk_rows
  FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
  JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
    ON c.document_id = s.document_id
  JOIN target_pdfs t
    ON t.pdf_stem = s.pdf_stem
  WHERE LOWER(s.confidence) = 'confirmed'
  GROUP BY s.pdf_stem, s.document_id
),
repair_counts AS (
  SELECT
    s.pdf_stem,
    CONCAT(s.document_id, '_', s.missing_esn) AS repaired_document_id,
    s.missing_esn,
    COUNT(*) AS repaired_chunk_rows
  FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
  JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
    ON c.document_id = CONCAT(s.document_id, '_', s.missing_esn)
   AND UPPER(TRIM(c.esn)) = UPPER(TRIM(s.missing_esn))
  JOIN target_pdfs t
    ON t.pdf_stem = s.pdf_stem
  WHERE LOWER(s.confidence) = 'confirmed'
  GROUP BY
    s.pdf_stem,
    CONCAT(s.document_id, '_', s.missing_esn),
    s.missing_esn
)
SELECT
  s.pdf_stem,
  s.document_id AS base_document_id,
  CONCAT(s.document_id, '_', s.missing_esn) AS repaired_document_id,
  s.missing_esn,
  s.prod_status,
  b.base_chunk_rows,
  r.repaired_chunk_rows,
  (b.base_chunk_rows - r.repaired_chunk_rows) AS chunk_diff
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
LEFT JOIN base_counts b
  ON b.pdf_stem = s.pdf_stem AND b.base_document_id = s.document_id
LEFT JOIN repair_counts r
  ON r.pdf_stem = s.pdf_stem
 AND r.repaired_document_id = CONCAT(s.document_id, '_', s.missing_esn)
 AND r.missing_esn = s.missing_esn
JOIN target_pdfs t
  ON t.pdf_stem = s.pdf_stem
WHERE LOWER(s.confidence) = 'confirmed'
ORDER BY s.pdf_stem;
```

Expected shape:
- `chunk_diff = 0` for clean fan-out parity
- `prod_status = 'done'` for completed rows

---

## 7. Final validation — all completed rows have repaired metadata

Use this to confirm every completed confirmed row has its repaired metadata row present.

```sql
SELECT
  s.pdf_stem,
  s.document_id AS base_document_id,
  s.missing_esn,
  m.document_id AS repaired_document_id,
  m.esn,
  m.esn_source,
  m.equipment_type
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
JOIN vaip.ai_sot_field_service_report.biz_metadata_field_service_report m
  ON m.document_id = CONCAT(s.document_id, '_', s.missing_esn)
WHERE LOWER(s.confidence) = 'confirmed'
  AND s.prod_status = 'done'
ORDER BY s.pdf_stem;
```

Count version:

```sql
SELECT COUNT(*) AS repaired_pdfs_with_metadata
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
JOIN vaip.ai_sot_field_service_report.biz_metadata_field_service_report m
  ON m.document_id = CONCAT(s.document_id, '_', s.missing_esn)
WHERE LOWER(s.confidence) = 'confirmed'
  AND s.prod_status = 'done';
```

Strict missing-only view:

```sql
SELECT
  s.pdf_stem,
  s.document_id AS base_document_id,
  s.missing_esn
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
LEFT JOIN vaip.ai_sot_field_service_report.biz_metadata_field_service_report m
  ON m.document_id = CONCAT(s.document_id, '_', s.missing_esn)
WHERE LOWER(s.confidence) = 'confirmed'
  AND s.prod_status = 'done'
  AND m.document_id IS NULL
ORDER BY s.pdf_stem;
```

Expected shape:
- count query returns the total number of completed repaired rows
- missing-only query returns no rows

---

## 8. Final validation — all completed rows have repaired chunks

Use this to confirm every completed confirmed row has chunk rows under the repaired `document_id` for the missing ESN.

```sql
SELECT
  s.pdf_stem,
  s.document_id AS base_document_id,
  s.missing_esn,
  c.document_id AS repaired_document_id,
  c.esn,
  COUNT(*) AS chunk_rows
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
  ON c.document_id = CONCAT(s.document_id, '_', s.missing_esn)
 AND UPPER(TRIM(c.esn)) = UPPER(TRIM(s.missing_esn))
WHERE LOWER(s.confidence) = 'confirmed'
  AND s.prod_status = 'done'
GROUP BY
  s.pdf_stem,
  s.document_id,
  s.missing_esn,
  c.document_id,
  c.esn
ORDER BY s.pdf_stem;
```

Count version:

```sql
SELECT COUNT(*) AS repaired_pdfs_with_chunks
FROM (
  SELECT
    s.pdf_stem,
    s.missing_esn
  FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
  JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
    ON c.document_id = CONCAT(s.document_id, '_', s.missing_esn)
   AND UPPER(TRIM(c.esn)) = UPPER(TRIM(s.missing_esn))
  WHERE LOWER(s.confidence) = 'confirmed'
    AND s.prod_status = 'done'
  GROUP BY s.pdf_stem, s.missing_esn
) q;
```

Strict missing-only view:

```sql
SELECT
  s.pdf_stem,
  s.document_id AS base_document_id,
  s.missing_esn
FROM vaip.ai_sot_field_service_report.staging_vistra_gap s
LEFT JOIN vaip.ai_std_con_field_service_report.vec_field_service_report c
  ON c.document_id = CONCAT(s.document_id, '_', s.missing_esn)
 AND UPPER(TRIM(c.esn)) = UPPER(TRIM(s.missing_esn))
WHERE LOWER(s.confidence) = 'confirmed'
  AND s.prod_status = 'done'
GROUP BY s.pdf_stem, s.document_id, s.missing_esn
HAVING COUNT(c.chunk_id) = 0
ORDER BY s.pdf_stem;
```

Expected shape:
- count query returns the total number of completed repaired rows
- missing-only query returns no rows
