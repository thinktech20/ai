-- Confirm ESN mapping mismatch for 2024 Data Readiness
-- Compares doc coverage for 337X765 vs 337X766 in 2024

WITH base AS (
  SELECT
    upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) AS norm_esn,
    d.esn,
    d.is_active,
    d.document_id,
    m.pdf_name,
    m.outage_start_date,
    m.report_issued_date,
    m.metadata_status,
    m.chunk_status
  FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
  JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
    ON d.document_id = m.document_id
  WHERE year(to_date(m.outage_start_date)) = 2024
)
SELECT
  CASE
    WHEN norm_esn = '337X765' THEN 'TARGET_337X765'
    WHEN norm_esn = '337X766' THEN 'NEARBY_337X766'
    ELSE 'OTHER'
  END AS esn_bucket,
  esn,
  document_id,
  pdf_name,
  is_active,
  outage_start_date,
  report_issued_date,
  metadata_status,
  chunk_status
FROM base
WHERE norm_esn IN ('337X765', '337X766')
ORDER BY esn_bucket, to_date(outage_start_date) DESC, document_id;

-- Optional summary count
WITH base AS (
  SELECT
    upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) AS norm_esn,
    d.document_id
  FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
  JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
    ON d.document_id = m.document_id
  WHERE year(to_date(m.outage_start_date)) = 2024
    AND d.is_active = true
    AND m.metadata_status = 'completed'
    AND m.chunk_status = 'completed'
)
SELECT
  norm_esn,
  count(DISTINCT document_id) AS active_completed_docs_2024
FROM base
WHERE norm_esn IN ('337X765', '337X766')
GROUP BY norm_esn
ORDER BY norm_esn;
