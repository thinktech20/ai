-- Debug why 2024 outage report is not appearing for ESN 337X765
-- This script checks:
-- 1) Whether 2024 metadata exists for the unit (normalized ESN match)
-- 2) Whether that document is mapped in equipment_map
-- 3) Whether mapping/status/recency filters exclude it

-- =============================
-- Query 1: Candidate 2024 docs from metadata
-- =============================
WITH target AS (
  SELECT upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_esn
)
SELECT
  m.document_id,
  m.pdf_name,
  m.primary_esn,
  m.primary_equip_type,
  m.report_issued_date,
  m.outage_start_date,
  m.outage_end_date,
  m.metadata_status,
  m.chunk_status,
  m.customer,
  m.event_type,
  m.outage_type
FROM vaid.ai_sot_field_service_report.fsr_metadata_v2 m
CROSS JOIN target t
WHERE year(to_date(m.outage_start_date)) = 2024
  AND upper(regexp_replace(coalesce(m.primary_esn, ''), '[^A-Za-z0-9]', '')) = t.norm_esn
ORDER BY to_date(m.outage_start_date) DESC;

-- =============================
-- Query 2: For candidate docs, inspect all ESN mappings
-- =============================
WITH target AS (
  SELECT upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_esn
),
candidate_docs AS (
  SELECT m.document_id
  FROM vaid.ai_sot_field_service_report.fsr_metadata_v2 m
  CROSS JOIN target t
  WHERE year(to_date(m.outage_start_date)) = 2024
    AND upper(regexp_replace(coalesce(m.primary_esn, ''), '[^A-Za-z0-9]', '')) = t.norm_esn
)
SELECT
  d.document_id,
  d.esn,
  d.equip_type,
  d.is_primary_esn,
  d.is_active,
  m.pdf_name,
  m.primary_esn,
  m.report_issued_date,
  m.outage_start_date,
  m.metadata_status,
  m.chunk_status
FROM candidate_docs c
LEFT JOIN vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
  ON c.document_id = d.document_id
LEFT JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
  ON c.document_id = m.document_id
ORDER BY m.outage_start_date DESC, d.esn;

-- =============================
-- Query 3: Exact Data Readiness eligibility check for 2024 candidates
-- =============================
WITH target AS (
  SELECT upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_esn
),
candidate_docs AS (
  SELECT m.document_id
  FROM vaid.ai_sot_field_service_report.fsr_metadata_v2 m
  CROSS JOIN target t
  WHERE year(to_date(m.outage_start_date)) = 2024
    AND upper(regexp_replace(coalesce(m.primary_esn, ''), '[^A-Za-z0-9]', '')) = t.norm_esn
),
check_rows AS (
  SELECT
    c.document_id,
    d.esn,
    d.is_active,
    m.pdf_name,
    m.report_issued_date,
    m.outage_start_date,
    m.metadata_status,
    m.chunk_status,
    CASE
      WHEN upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) = (SELECT norm_esn FROM target)
       AND d.is_active = true
       AND m.metadata_status = 'completed'
       AND m.chunk_status = 'completed'
       AND to_date(m.outage_start_date) >= add_months(current_date(), -120)
      THEN 'INCLUDED_IN_DATA_READINESS'
      ELSE concat_ws(
        '; ',
        CASE WHEN upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) <> (SELECT norm_esn FROM target) THEN concat('esn_mismatch=', coalesce(d.esn, 'NULL')) END,
        CASE WHEN d.is_active <> true THEN 'inactive mapping' END,
        CASE WHEN m.metadata_status <> 'completed' THEN concat('metadata_status=', coalesce(m.metadata_status, 'NULL')) END,
        CASE WHEN m.chunk_status <> 'completed' THEN concat('chunk_status=', coalesce(m.chunk_status, 'NULL')) END,
        CASE WHEN to_date(m.outage_start_date) < add_months(current_date(), -120)
               OR m.outage_start_date IS NULL THEN concat('outage_start_date_out_of_window=', coalesce(cast(m.outage_start_date as string), 'NULL')) END
      )
    END AS inclusion_result
  FROM candidate_docs c
  LEFT JOIN vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
    ON c.document_id = d.document_id
  LEFT JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
    ON c.document_id = m.document_id
)
SELECT *
FROM check_rows
ORDER BY to_date(outage_start_date) DESC, document_id, esn;
