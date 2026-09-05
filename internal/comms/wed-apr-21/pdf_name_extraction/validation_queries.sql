-- PDF name derivation validation
-- Goal:
-- 1. determine whether fsr_pdf_ref or psot should be the winning source for pdf_name
-- 2. determine the safest join key for deriving pdf_name

-- Working hypothesis from repo evidence:
-- - fsr_pdf_ref should be the primary source for pdf_name because it appears to carry
--   the direct file mapping from s3_filename/document UUID -> human-readable PDF_name.
-- - psot should be treated as a downstream business metadata source, not the first-choice
--   source for pdf_name, unless data shows fsr_pdf_ref has material coverage gaps.
-- - The primary join key should be normalized document_id = normalized s3_filename,
--   not esn-only and not report-date-only.


-- 0) Inspect candidate columns on both source tables
SHOW COLUMNS IN vgpp.fsr_std_views.fsr_pdf_ref;
SHOW COLUMNS IN vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot;


-- 1) Sample direct mapping candidates from fsr_pdf_ref
-- Expectation: this table exposes both the UUID-like key and the human-readable PDF name.
SELECT
    s3_filename,
    PDF_name,
    esn,
    ev_ofs_event_id
FROM vgpp.fsr_std_views.fsr_pdf_ref
WHERE s3_filename IS NOT NULL
LIMIT 50;


-- 2) Find candidate filename columns on psot
-- Replace the selected columns below after reviewing SHOW COLUMNS output if names differ.
SELECT *
FROM vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot
LIMIT 10;


-- 3) Check whether fsr_pdf_ref gives a one-to-one mapping from UUID -> PDF_name
-- This is the main test for whether it can be the authoritative pdf_name source.
WITH ref AS (
    SELECT
        lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', '')) AS document_id_norm,
        trim(PDF_name) AS pdf_name_candidate
    FROM vgpp.fsr_std_views.fsr_pdf_ref
    WHERE s3_filename IS NOT NULL
)
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT document_id_norm) AS distinct_document_ids,
    COUNT(DISTINCT CASE WHEN pdf_name_candidate IS NOT NULL AND pdf_name_candidate <> '' THEN document_id_norm END) AS document_ids_with_pdf_name,
    COUNT(*) - COUNT(DISTINCT document_id_norm) AS duplicate_rows
FROM ref;


-- 4) Detect UUIDs that map to more than one distinct PDF_name in fsr_pdf_ref
-- If this returns very few rows, ref remains the best source.
WITH ref AS (
    SELECT
        lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', '')) AS document_id_norm,
        trim(PDF_name) AS pdf_name_candidate
    FROM vgpp.fsr_std_views.fsr_pdf_ref
    WHERE s3_filename IS NOT NULL
      AND PDF_name IS NOT NULL
      AND trim(PDF_name) <> ''
)
SELECT
    document_id_norm,
    COUNT(DISTINCT pdf_name_candidate) AS distinct_pdf_names,
    collect_set(pdf_name_candidate) AS pdf_names
FROM ref
GROUP BY document_id_norm
HAVING COUNT(DISTINCT pdf_name_candidate) > 1
ORDER BY distinct_pdf_names DESC, document_id_norm
LIMIT 100;


-- 5) Measure how much of fsr_pdf_ref has usable PDF_name coverage
WITH ref AS (
    SELECT
        lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', '')) AS document_id_norm,
        trim(PDF_name) AS pdf_name_candidate
    FROM vgpp.fsr_std_views.fsr_pdf_ref
    WHERE s3_filename IS NOT NULL
)
SELECT
    COUNT(DISTINCT document_id_norm) AS total_document_ids,
    COUNT(DISTINCT CASE WHEN pdf_name_candidate IS NOT NULL AND pdf_name_candidate <> '' THEN document_id_norm END) AS document_ids_with_pdf_name,
    COUNT(DISTINCT CASE WHEN pdf_name_candidate IS NULL OR pdf_name_candidate = '' THEN document_id_norm END) AS document_ids_without_pdf_name
FROM ref;


-- 6) Compare candidate joins using document UUID vs ESN
-- Replace main.gp_services_sdg_poc.fsr_metadata_registry_test with the current working metadata table if needed.
-- The table should contain the current UUID-like identifier from the file stem.
WITH base AS (
    SELECT DISTINCT
        lower(regexp_replace(trim(pdf_name), '\\.(pdf|PDF)$', '')) AS current_uuid_norm,
        upper(trim(esn)) AS esn
    FROM main.gp_services_sdg_poc.fsr_metadata_registry_test
    WHERE pdf_name IS NOT NULL
),
ref AS (
    SELECT DISTINCT
        lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', '')) AS document_id_norm,
        upper(trim(esn)) AS esn,
        trim(PDF_name) AS pdf_name_candidate,
        ev_ofs_event_id
    FROM vgpp.fsr_std_views.fsr_pdf_ref
    WHERE s3_filename IS NOT NULL
)
SELECT
    COUNT(DISTINCT b.current_uuid_norm) AS base_docs,
    COUNT(DISTINCT CASE WHEN r_uuid.document_id_norm IS NOT NULL THEN b.current_uuid_norm END) AS matched_by_uuid,
    COUNT(DISTINCT CASE WHEN r_esn.esn IS NOT NULL THEN b.current_uuid_norm END) AS matched_by_esn
FROM base b
LEFT JOIN ref r_uuid
    ON b.current_uuid_norm = r_uuid.document_id_norm
LEFT JOIN ref r_esn
    ON b.esn = r_esn.esn;


-- 7) Show ambiguity when joining only by ESN
-- If this produces many rows with multiple candidate filenames per doc, ESN-only is not safe.
WITH base AS (
    SELECT DISTINCT
        lower(regexp_replace(trim(pdf_name), '\\.(pdf|PDF)$', '')) AS current_uuid_norm,
        upper(trim(esn)) AS esn
    FROM main.gp_services_sdg_poc.fsr_metadata_registry_test
    WHERE pdf_name IS NOT NULL
      AND esn IS NOT NULL
),
ref AS (
    SELECT DISTINCT
        upper(trim(esn)) AS esn,
        trim(PDF_name) AS pdf_name_candidate
    FROM vgpp.fsr_std_views.fsr_pdf_ref
    WHERE esn IS NOT NULL
      AND PDF_name IS NOT NULL
      AND trim(PDF_name) <> ''
)
SELECT
    b.current_uuid_norm,
    b.esn,
    COUNT(DISTINCT r.pdf_name_candidate) AS candidate_pdf_names,
    collect_set(r.pdf_name_candidate) AS pdf_names
FROM base b
JOIN ref r
    ON b.esn = r.esn
GROUP BY b.current_uuid_norm, b.esn
HAVING COUNT(DISTINCT r.pdf_name_candidate) > 1
ORDER BY candidate_pdf_names DESC, b.current_uuid_norm
LIMIT 100;


-- 8) Test which event bridge actually reaches psot after file identity is established.
-- Current evidence says psot is not the source of pdf_name.
-- This query is only for downstream enrichment-key validation.
WITH ref AS (
    SELECT DISTINCT
        lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', '')) AS document_id_norm,
        upper(trim(esn)) AS esn,
        ev_equipment_event_id,
        ev_ofs_event_id,
        trim(PDF_name) AS pdf_name_candidate
    FROM vgpp.fsr_std_views.fsr_pdf_ref
    WHERE s3_filename IS NOT NULL
),
psot AS (
    SELECT *
    FROM vgpp.fsr_std_views.fsr_field_vision_field_services_report_psot
),
equipment_event_bridge AS (
    SELECT
        'ev_equipment_event_id -> psot.event_id' AS bridge_name,
        COUNT(*) AS joined_rows,
        COUNT(DISTINCT ref.document_id_norm) AS joined_documents,
        COUNT(DISTINCT concat_ws('||', ref.esn, cast(ref.ev_equipment_event_id AS STRING))) AS distinct_ref_pairs
    FROM ref
    JOIN psot
        ON upper(trim(ref.esn)) = upper(trim(psot.esn))
       AND cast(ref.ev_equipment_event_id AS STRING) = cast(psot.event_id AS STRING)
    WHERE ref.ev_equipment_event_id IS NOT NULL
),
ofs_event_bridge AS (
    SELECT
        'ev_ofs_event_id -> psot.event_id' AS bridge_name,
        COUNT(*) AS joined_rows,
        COUNT(DISTINCT ref.document_id_norm) AS joined_documents,
        COUNT(DISTINCT concat_ws('||', ref.esn, cast(ref.ev_ofs_event_id AS STRING))) AS distinct_ref_pairs
    FROM ref
    JOIN psot
        ON upper(trim(ref.esn)) = upper(trim(psot.esn))
       AND cast(ref.ev_ofs_event_id AS STRING) = cast(psot.event_id AS STRING)
    WHERE ref.ev_ofs_event_id IS NOT NULL
)
SELECT * FROM equipment_event_bridge
UNION ALL
SELECT * FROM ofs_event_bridge;


-- 9) Decision query: source precedence summary
-- Read this result as:
-- - if ref_uuid_hit_rate is high and ref_conflicts is low, fsr_pdf_ref should win for pdf_name
-- - if ESN ambiguity is high, ESN should not be used as the primary join key
WITH ref_cov AS (
    SELECT
        COUNT(DISTINCT lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', ''))) AS ref_docs,
        COUNT(DISTINCT CASE WHEN PDF_name IS NOT NULL AND trim(PDF_name) <> ''
            THEN lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', '')) END) AS ref_docs_with_pdf_name
    FROM vgpp.fsr_std_views.fsr_pdf_ref
    WHERE s3_filename IS NOT NULL
),
ref_conflicts AS (
    SELECT COUNT(*) AS conflict_docs
    FROM (
        SELECT
            lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', '')) AS document_id_norm
        FROM vgpp.fsr_std_views.fsr_pdf_ref
        WHERE s3_filename IS NOT NULL
          AND PDF_name IS NOT NULL
          AND trim(PDF_name) <> ''
        GROUP BY lower(regexp_replace(trim(s3_filename), '\\.(pdf|PDF)$', ''))
        HAVING COUNT(DISTINCT trim(PDF_name)) > 1
    ) x
),
esn_ambiguity AS (
    SELECT COUNT(*) AS ambiguous_esn_rows
    FROM (
        SELECT upper(trim(esn)) AS esn
        FROM vgpp.fsr_std_views.fsr_pdf_ref
        WHERE esn IS NOT NULL
          AND PDF_name IS NOT NULL
          AND trim(PDF_name) <> ''
        GROUP BY upper(trim(esn))
        HAVING COUNT(DISTINCT trim(PDF_name)) > 1
    ) y
)
SELECT
    ref_docs,
    ref_docs_with_pdf_name,
    conflict_docs AS ref_uuid_conflicts,
    ambiguous_esn_rows AS ref_esn_ambiguity_rows
FROM ref_cov, ref_conflicts, esn_ambiguity;


-- Expected decision unless the data disproves it:
-- - Winning source for pdf_name: fsr_pdf_ref.PDF_name
-- - Winning join key for deriving pdf_name: normalized document_id = normalized fsr_pdf_ref.s3_filename
-- - Role of psot: enrich after file identity is established, likely through ESN plus an event key