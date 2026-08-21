-- Broad debug for missing 2024 FSR for ESN 337X765
-- Use this when strict primary_esn checks return zero rows.

-- ==================================================
-- Query 1: 2024 docs where equipment-map ESN matches exactly after normalization
-- ==================================================
WITH target AS (
  SELECT upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_esn
)
SELECT
  m.document_id,
  m.pdf_name,
  m.primary_esn,
  d.esn AS mapped_esn,
  d.is_active,
  d.is_primary_esn,
  m.report_issued_date,
  m.outage_start_date,
  m.metadata_status,
  m.chunk_status
FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
  ON d.document_id = m.document_id
CROSS JOIN target t
WHERE year(to_date(m.outage_start_date)) = 2024
  AND upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) = t.norm_esn
ORDER BY to_date(m.outage_start_date) DESC;

-- ==================================================
-- Query 2: 2024 docs with fuzzy ESN match patterns (formatting/partial issues)
-- ==================================================
WITH target AS (
  SELECT
    upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_esn,
    right(upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')), 6) AS target_last6,
    right(upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')), 4) AS target_last4
),
base AS (
  SELECT
    m.document_id,
    m.pdf_name,
    m.primary_esn,
    d.esn AS mapped_esn,
    upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) AS norm_mapped_esn,
    d.is_active,
    d.is_primary_esn,
    m.report_issued_date,
    m.outage_start_date,
    m.metadata_status,
    m.chunk_status
  FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
  JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
    ON d.document_id = m.document_id
  WHERE year(to_date(m.outage_start_date)) = 2024
)
SELECT
  b.*,
  CASE
    WHEN b.norm_mapped_esn = t.norm_esn THEN 'EXACT_NORM'
    WHEN b.norm_mapped_esn LIKE concat('%', t.norm_esn, '%') THEN 'MAP_CONTAINS_TARGET'
    WHEN t.norm_esn LIKE concat('%', b.norm_mapped_esn, '%') THEN 'TARGET_CONTAINS_MAP'
    WHEN right(b.norm_mapped_esn, 6) = t.target_last6 THEN 'LAST6_MATCH'
    WHEN right(b.norm_mapped_esn, 4) = t.target_last4 THEN 'LAST4_MATCH'
    ELSE 'OTHER'
  END AS match_type
FROM base b
CROSS JOIN target t
WHERE
  b.norm_mapped_esn LIKE concat('%', t.norm_esn, '%')
  OR t.norm_esn LIKE concat('%', b.norm_mapped_esn, '%')
  OR right(b.norm_mapped_esn, 6) = t.target_last6
  OR right(b.norm_mapped_esn, 4) = t.target_last4
ORDER BY
  CASE
    WHEN b.norm_mapped_esn = t.norm_esn THEN 1
    WHEN right(b.norm_mapped_esn, 6) = t.target_last6 THEN 2
    WHEN right(b.norm_mapped_esn, 4) = t.target_last4 THEN 3
    ELSE 4
  END,
  to_date(b.outage_start_date) DESC;

-- ==================================================
-- Query 3: 2024 docs where ESN appears in primary_esn or pdf_name text
-- ==================================================
WITH target AS (
  SELECT upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_esn
)
SELECT
  m.document_id,
  m.pdf_name,
  m.primary_esn,
  m.report_issued_date,
  m.outage_start_date,
  m.metadata_status,
  m.chunk_status
FROM vaid.ai_sot_field_service_report.fsr_metadata_v2 m
CROSS JOIN target t
WHERE year(to_date(m.outage_start_date)) = 2024
  AND (
    upper(regexp_replace(coalesce(m.primary_esn, ''), '[^A-Za-z0-9]', '')) LIKE concat('%', t.norm_esn, '%')
    OR upper(regexp_replace(coalesce(m.pdf_name, ''), '[^A-Za-z0-9]', '')) LIKE concat('%', t.norm_esn, '%')
    OR upper(coalesce(m.pdf_name, '')) LIKE '%337%'
    OR upper(coalesce(m.pdf_name, '')) LIKE '%X765%'
  )
ORDER BY to_date(m.outage_start_date) DESC;

-- ==================================================
-- Query 4: Sanity count of 2024 docs in metadata (pipeline presence check)
-- ==================================================
SELECT
  count(*) AS total_2024_docs,
  sum(CASE WHEN metadata_status = 'completed' THEN 1 ELSE 0 END) AS metadata_completed_2024,
  sum(CASE WHEN chunk_status = 'completed' THEN 1 ELSE 0 END) AS chunk_completed_2024
FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE year(to_date(outage_start_date)) = 2024;
