-- Deep debug when strict/fuzzy ESN lookups return zero rows but 2024 docs exist.
-- Goal: identify whether the expected 2024 report is missing map rows,
-- has only inactive map rows, or uses an unexpected ESN variant.

-- ==================================================
-- Query 1: Show all 2024 docs with mapping coverage summary
-- ==================================================
WITH docs_2024 AS (
  SELECT
    m.document_id,
    m.pdf_name,
    m.primary_esn,
    m.report_issued_date,
    m.outage_start_date,
    m.metadata_status,
    m.chunk_status
  FROM vaid.ai_sot_field_service_report.fsr_metadata_v2 m
  WHERE year(to_date(m.outage_start_date)) = 2024
),
map_stats AS (
  SELECT
    d.document_id,
    count(*) AS map_rows,
    sum(CASE WHEN d.is_active = true THEN 1 ELSE 0 END) AS active_map_rows,
    concat_ws(', ', slice(sort_array(collect_set(coalesce(d.esn, 'NULL'))), 1, 20)) AS sample_esns
  FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
  GROUP BY d.document_id
)
SELECT
  m.document_id,
  m.pdf_name,
  m.primary_esn,
  m.report_issued_date,
  m.outage_start_date,
  m.metadata_status,
  m.chunk_status,
  coalesce(s.map_rows, 0) AS map_rows,
  coalesce(s.active_map_rows, 0) AS active_map_rows,
  coalesce(s.sample_esns, 'NO_MAPPING_ROWS') AS sample_esns
FROM docs_2024 m
LEFT JOIN map_stats s
  ON m.document_id = s.document_id
ORDER BY to_date(m.outage_start_date) DESC, m.pdf_name;

-- ==================================================
-- Query 2: Find ESN variants in mapping table that could be related to 337X765
-- ==================================================
WITH target AS (
  SELECT upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_target
),
map_norm AS (
  SELECT DISTINCT
    d.esn,
    upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) AS norm_esn
  FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
)
SELECT
  m.esn,
  m.norm_esn,
  CASE
    WHEN m.norm_esn = t.norm_target THEN 'EXACT'
    WHEN m.norm_esn LIKE concat('%', t.norm_target, '%') THEN 'MAP_CONTAINS_TARGET'
    WHEN t.norm_target LIKE concat('%', m.norm_esn, '%') THEN 'TARGET_CONTAINS_MAP'
    WHEN m.norm_esn RLIKE '.*337.*765.*' THEN 'DIGIT_PATTERN_337_765'
    WHEN m.norm_esn LIKE '%X765%' THEN 'HAS_X765'
    WHEN m.norm_esn LIKE '%337X%' THEN 'HAS_337X'
    ELSE 'OTHER'
  END AS match_type
FROM map_norm m
CROSS JOIN target t
WHERE
  m.norm_esn = t.norm_target
  OR m.norm_esn LIKE concat('%', t.norm_target, '%')
  OR t.norm_target LIKE concat('%', m.norm_esn, '%')
  OR m.norm_esn RLIKE '.*337.*765.*'
  OR m.norm_esn LIKE '%X765%'
  OR m.norm_esn LIKE '%337X%'
ORDER BY match_type, m.norm_esn;

-- ==================================================
-- Query 3: If variants exist, show any 2024 docs tied to those ESN variants
-- ==================================================
WITH variants AS (
  SELECT DISTINCT esn
  FROM (
    WITH target AS (
      SELECT upper(regexp_replace('337X765', '[^A-Za-z0-9]', '')) AS norm_target
    )
    SELECT
      d.esn,
      upper(regexp_replace(coalesce(d.esn, ''), '[^A-Za-z0-9]', '')) AS norm_esn,
      t.norm_target
    FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
    CROSS JOIN target t
  ) x
  WHERE
    norm_esn = norm_target
    OR norm_esn LIKE concat('%', norm_target, '%')
    OR norm_target LIKE concat('%', norm_esn, '%')
    OR norm_esn RLIKE '.*337.*765.*'
    OR norm_esn LIKE '%X765%'
    OR norm_esn LIKE '%337X%'
)
SELECT
  d.document_id,
  d.esn,
  d.is_primary_esn,
  d.is_active,
  m.pdf_name,
  m.primary_esn,
  m.report_issued_date,
  m.outage_start_date,
  m.metadata_status,
  m.chunk_status
FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
JOIN variants v
  ON d.esn = v.esn
JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
  ON d.document_id = m.document_id
WHERE year(to_date(m.outage_start_date)) = 2024
ORDER BY to_date(m.outage_start_date) DESC, d.esn;

-- ==================================================
-- Query 4: Data Readiness eligibility check for all 2024 docs (not ESN-specific)
-- Helps confirm if docs are filtered by status/recency regardless of ESN.
-- ==================================================
SELECT
  m.document_id,
  m.pdf_name,
  m.primary_esn,
  m.report_issued_date,
  m.outage_start_date,
  m.metadata_status,
  m.chunk_status,
  CASE
    WHEN m.metadata_status = 'completed'
     AND m.chunk_status = 'completed'
     AND to_date(m.outage_start_date) >= add_months(current_date(), -120)
    THEN 'READY_AT_METADATA_LEVEL'
    ELSE concat_ws(
      '; ',
      CASE WHEN m.metadata_status <> 'completed' THEN concat('metadata_status=', coalesce(m.metadata_status, 'NULL')) END,
      CASE WHEN m.chunk_status <> 'completed' THEN concat('chunk_status=', coalesce(m.chunk_status, 'NULL')) END,
      CASE WHEN to_date(m.outage_start_date) < add_months(current_date(), -120)
             OR m.outage_start_date IS NULL THEN concat('outage_start_date_out_of_window=', coalesce(cast(m.outage_start_date as string), 'NULL')) END
    )
  END AS metadata_level_status
FROM vaid.ai_sot_field_service_report.fsr_metadata_v2 m
WHERE year(to_date(m.outage_start_date)) = 2024
ORDER BY to_date(m.outage_start_date) DESC;
