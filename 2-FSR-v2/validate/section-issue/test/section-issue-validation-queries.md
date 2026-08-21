# FSR v2 Section Issue — Validation Queries

Use these queries in Databricks SQL after targeted re-ingest.

Tables used:
- Metadata: `vaid.ai_sot_field_service_report.fsr_metadata_v2`
- Chunks: `vaid.ai_std_con_field_service_report.fsr_chunks_v2`
- Doc-equipment map: `vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2`

Target docs included in all queries:
- 5b688732-39f2-48d2-a887-3239f258d28b
- b775cf29-8b42-4a83-af21-53075fef0802
- 27314604-ed52-402f-921f-34737a048841
- fcb1511e-596a-4a56-b151-1e596afa569c
- 35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report
- b7b347fd-0b59-4c67-b609-9ad2c35105cc
- bdd56c7a-ebe5-4bf7-904a-5bb63091ba20
- cdd0cca4-93ba-43b0-98e5-3d1ea2312c19
- 39_v1.0(17)

## Query 1 — Coverage and pipeline status by target doc
```sql
WITH target_docs AS (
  SELECT explode(array(
    '5b688732-39f2-48d2-a887-3239f258d28b',
    'b775cf29-8b42-4a83-af21-53075fef0802',
    '27314604-ed52-402f-921f-34737a048841',
    'fcb1511e-596a-4a56-b151-1e596afa569c',
    '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
    'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
    'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
    'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
    '39_v1.0(17)'
  )) AS document_id
),
meta AS (
  SELECT document_id, metadata_status, chunk_status, updated_at
  FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
),
chunks AS (
  SELECT document_id, count(*) AS chunk_count
  FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2
  GROUP BY document_id
),
emap AS (
  SELECT document_id, count(*) AS map_rows, sum(source_region_count) AS total_region_count
  FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2
  GROUP BY document_id
)
SELECT
  t.document_id,
  m.metadata_status,
  m.chunk_status,
  m.updated_at,
  coalesce(c.chunk_count, 0) AS chunk_count,
  coalesce(e.map_rows, 0) AS map_rows,
  coalesce(e.total_region_count, 0) AS total_region_count
FROM target_docs t
LEFT JOIN meta m ON m.document_id = t.document_id
LEFT JOIN chunks c ON c.document_id = t.document_id
LEFT JOIN emap e ON e.document_id = t.document_id
ORDER BY t.document_id;
```

## Query 2 — Missing targets in each table
```sql
WITH target_docs AS (
  SELECT explode(array(
    '5b688732-39f2-48d2-a887-3239f258d28b',
    'b775cf29-8b42-4a83-af21-53075fef0802',
    '27314604-ed52-402f-921f-34737a048841',
    'fcb1511e-596a-4a56-b151-1e596afa569c',
    '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
    'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
    'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
    'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
    '39_v1.0(17)'
  )) AS document_id
)
SELECT 'metadata' AS table_name, t.document_id
FROM target_docs t
LEFT ANTI JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
  ON m.document_id = t.document_id
UNION ALL
SELECT 'chunks' AS table_name, t.document_id
FROM target_docs t
LEFT ANTI JOIN vaid.ai_std_con_field_service_report.fsr_chunks_v2 c
  ON c.document_id = t.document_id
UNION ALL
SELECT 'doc_equipment_map' AS table_name, t.document_id
FROM target_docs t
LEFT ANTI JOIN vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 e
  ON e.document_id = t.document_id
ORDER BY table_name, document_id;
```

## Query 3 — Section field quality summary
```sql
WITH target_docs AS (
  SELECT explode(array(
    '5b688732-39f2-48d2-a887-3239f258d28b',
    'b775cf29-8b42-4a83-af21-53075fef0802',
    '27314604-ed52-402f-921f-34737a048841',
    'fcb1511e-596a-4a56-b151-1e596afa569c',
    '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
    'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
    'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
    'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
    '39_v1.0(17)'
  )) AS document_id
),
base AS (
  SELECT
    c.document_id,
    c.chunk_index,
    trim(coalesce(get_json_object(c.metadata, '$.section.section_1'), '')) AS section_1
  FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2 c
  INNER JOIN target_docs t ON t.document_id = c.document_id
)
SELECT
  document_id,
  count(*) AS chunks_total,
  sum(CASE WHEN section_1 = '' OR lower(section_1) = 'null' THEN 1 ELSE 0 END) AS section1_missing,
  sum(CASE WHEN lower(section_1) rlike '^(form|page|revision|rev)$' THEN 1 ELSE 0 END) AS section1_noise_form_page,
  sum(CASE WHEN section_1 rlike '^[A-Z0-9\\s\\-]{1,25}$' THEN 1 ELSE 0 END) AS section1_short_allcaps_like
FROM base
GROUP BY document_id
ORDER BY document_id;
```

## Query 4 — Footer/legal leakage check in chunk text
```sql
WITH target_docs AS (
  SELECT explode(array(
    '5b688732-39f2-48d2-a887-3239f258d28b',
    'b775cf29-8b42-4a83-af21-53075fef0802',
    '27314604-ed52-402f-921f-34737a048841',
    'fcb1511e-596a-4a56-b151-1e596afa569c',
    '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
    'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
    'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
    'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
    '39_v1.0(17)'
  )) AS document_id
),
base AS (
  SELECT c.document_id, c.chunk_index, c.chunk_text
  FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2 c
  INNER JOIN target_docs t ON t.document_id = c.document_id
)
SELECT
  document_id,
  count(*) AS chunks_total,
  sum(CASE WHEN lower(chunk_text) rlike 'proprietary and confidential|all rights reserved|no part of this document may be|shall not be used or disclosed|general electric company' THEN 1 ELSE 0 END) AS legal_footer_hits,
  sum(CASE WHEN lower(chunk_text) rlike '\\bpage\\s*[0-9]+\\s*(of|/)\\s*[0-9]+\\b' THEN 1 ELSE 0 END) AS page_number_hits
FROM base
GROUP BY document_id
ORDER BY document_id;
```

## Query 5 — Potential sentence-break regression check across adjacent chunks
```sql
WITH target_docs AS (
  SELECT explode(array(
    '5b688732-39f2-48d2-a887-3239f258d28b',
    'b775cf29-8b42-4a83-af21-53075fef0802',
    '27314604-ed52-402f-921f-34737a048841',
    'fcb1511e-596a-4a56-b151-1e596afa569c',
    '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
    'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
    'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
    'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
    '39_v1.0(17)'
  )) AS document_id
),
ordered AS (
  SELECT
    c.document_id,
    c.chunk_index,
    c.chunk_text,
    lag(c.chunk_text) OVER (PARTITION BY c.document_id ORDER BY c.chunk_index) AS prev_chunk_text
  FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2 c
  INNER JOIN target_docs t ON t.document_id = c.document_id
),
flags AS (
  SELECT
    document_id,
    chunk_index,
    CASE
      WHEN prev_chunk_text IS NULL THEN 0
      WHEN trim(prev_chunk_text) rlike '[.!?]["''\\)\\]]?$' THEN 0
      WHEN trim(chunk_text) rlike '^[a-z0-9\\(\\["'']' THEN 1
      ELSE 0
    END AS potential_mid_sentence_boundary,
    substr(regexp_replace(coalesce(prev_chunk_text, ''), '\\s+', ' '), greatest(length(regexp_replace(coalesce(prev_chunk_text, ''), '\\s+', ' ')) - 120, 1), 120) AS prev_tail,
    substr(regexp_replace(coalesce(chunk_text, ''), '\\s+', ' '), 1, 120) AS curr_head
  FROM ordered
)
SELECT
  document_id,
  sum(potential_mid_sentence_boundary) AS flagged_boundaries,
  count(*) AS chunk_rows
FROM flags
GROUP BY document_id
ORDER BY document_id;
```

## Query 6 — Drill-down sample for manual inspection
```sql
WITH target_docs AS (
  SELECT explode(array(
    '5b688732-39f2-48d2-a887-3239f258d28b',
    'b775cf29-8b42-4a83-af21-53075fef0802',
    '27314604-ed52-402f-921f-34737a048841',
    'fcb1511e-596a-4a56-b151-1e596afa569c',
    '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
    'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
    'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
    'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
    '39_v1.0(17)'
  )) AS document_id
)
SELECT
  c.document_id,
  c.chunk_index,
  get_json_object(c.metadata, '$.section.section_1') AS section_1,
  get_json_object(c.metadata, '$.section.section_2') AS section_2,
  get_json_object(c.metadata, '$.section.section_3') AS section_3,
  substr(regexp_replace(c.chunk_text, '\\s+', ' '), 1, 220) AS chunk_head
FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2 c
INNER JOIN target_docs t ON t.document_id = c.document_id
ORDER BY c.document_id, c.chunk_index
LIMIT 400;
```

## Optional Query 7 — Raw rows for one doc deep-dive (replace doc_id)
```sql
SELECT
  document_id,
  chunk_index,
  primary_esn,
  primary_equip_type,
  get_json_object(metadata, '$.section.section_1') AS section_1,
  get_json_object(metadata, '$.section.section_2') AS section_2,
  get_json_object(metadata, '$.section.section_3') AS section_3,
  get_json_object(metadata, '$.section.section_4') AS section_4,
  get_json_object(metadata, '$.section.section_5') AS section_5,
  chunk_text
FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2
WHERE document_id = '5b688732-39f2-48d2-a887-3239f258d28b'
ORDER BY chunk_index;
```
