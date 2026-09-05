-- Missing 15 in dev - validation queries
-- Source: Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx
-- Sheet: FSR Tagging Gaps
-- Filter: Gap Confirmed = YES (47 PDFs)

-- Query 0: Build target set once (run this first in your SQL editor session)
CREATE OR REPLACE TEMP VIEW target_pdfs AS
SELECT * FROM VALUES
  ('Field_Service_Report_ProjectID_A-1375356_FSP-293536_C-10349934.pdf'),
  ('Field_Service_Report_ProjectID_A-1376570_EV-113525_C-10350370.pdf'),
  ('Field_Service_Report_ProjectID_A-1376780_FSP-261003_C-10330252.pdf'),
  ('Field_Service_Report_ProjectID_A-1377050_FSP-261004_C-10330490.pdf'),
  ('Field_Service_Report_ProjectID_A-1377308_FSP-260331_C-10329389.pdf'),
  ('Field_Service_Report_ProjectID_A-1377354_EV-121543_C-10350372.pdf'),
  ('Field_Service_Report_ProjectID_A-1425464_FSP-256871_C-10326234.pdf'),
  ('Field_Service_Report_ProjectID_A-1425468_FSP-256875_C-10326237.pdf'),
  ('Field_Service_Report_ProjectID_A-1425758_FSP-256873_C-10326236.pdf'),
  ('Field_Service_Report_ProjectID_A-1426924_EV-107829_C-10333940_EVP-504930.pdf'),
  ('Field_Service_Report_ProjectID_A-1488512_FSP-270381_C-10333878.pdf'),
  ('Field_Service_Report_ProjectID_A-1505048_FSP-253386_C-10323897.pdf'),
  ('Field_Service_Report_ProjectID_A-1586168_FSP-286344_C-10344989.pdf'),
  ('Field_Service_Report_ProjectID_A-1628248_FSP-298346_C-10353097.pdf'),
  ('Field_Service_Report_ProjectID_A-1633202_EV-116831_C-10366904_EVP-515928.pdf'),
  ('Field_Service_Report_ProjectID_A-1633204_EV-124343_C-10366903_EVP-515929.pdf'),
  ('Field_Service_Report_ProjectID_A-1633208_EV-118802_C-10366901_EVP-515932.pdf'),
  ('Field_Service_Report_ProjectID_A-1633210_EV-123983_C-10366888_EVP-515935.pdf'),
  ('Field_Service_Report_ProjectID_A-1633216_EV-106618_EVP-502991.pdf'),
  ('Field_Service_Report_ProjectID_A-1633218_EV-106619_EVP-502992.pdf'),
  ('Field_Service_Report_ProjectID_A-1655918_FSP-305393_C-10358660.pdf'),
  ('Field_Service_Report_ProjectID_A-1656076_FSP-305414_C-10358674.pdf'),
  ('Field_Service_Report_ProjectID_A-1682960_EV-114155_C-10364457.pdf'),
  ('Field_Service_Report_ProjectID_A-1686570_FSP-313453_C-10365083.pdf'),
  ('Field_Service_Report_ProjectID_A-1718410_EV-131641_C-10378975_EVP-521582.pdf'),
  ('Field_Service_Report_ProjectID_A-1734332_EV-136170_C-10370464.pdf'),
  ('Field_Service_Report_ProjectID_A-1737456_EV-136778_C-10370713.pdf'),
  ('Field_Service_Report_ProjectID_A-1828118_EV-156901_EVP-536585.pdf'),
  ('Field_Service_Report_ProjectID_A-1828574_EV-156982_C-10378887_EVP-536642.pdf'),
  ('Field_Service_Report_ProjectID_A-1838482_EV-158764_EVP-538036.pdf'),
  ('Field_Service_Report_ProjectID_A-1881852_EV-168186_EVP-545083.pdf'),
  ('Field_Service_Report_ProjectID_A-1989440_EV-190593_EVP-559293.pdf'),
  ('Field_Service_Report_ProjectID_EV-188520_EVP-557831.pdf'),
  ('GAS_TURBINE_INSPECTION_REPORT_Duke_Fayette_HGP_with_Magic_for_T_R_DUKE_ENERGY_CORPORATION_O_DUKE_ENERGY_NORTH_AMERICA_Unit_GT1_P_Gas_Turbine_298158_2011-03-06'),
  ('GAS_TURBINE_INSPECTION_REPORT_Forced_Major_Inspection_for_DYNEGY_MOSS_LANDING_LLC_Moss_Landing_Unit_GT1_Gas_Turbine_297602_2011-10-31'),
  ('GAS_TURBINE_INSPECTION_REPORT_GAS_TURBINE_MAJOR_INSPECTION_for_DOMINION_RESOURCES_INC_DOMINION_ENERGY_Unit_1B_GT_Gas_Turbine_298177_2011-03-26'),
  ('GAS_TURBINE_INSPECTION_REPORT_GT1_Major_Inspection_and_Generator_MAGIC_for_ODESSA-ECTOR_POWER_PARTNERS_LP_Odessa-Ector_Facility_Unit_GT1_Gas_Turbine_297490_2011-10-03'),
  ('GAS_TURBINE_INSPECTION_REPORT_GT_22_MAJOR_INSPECTION_AND_GENERATOR_MAJOR_INSPECTION_for_LAMAR_POWER_PARTNERS_LP_LAMAR_POWER_PARTNERS_Unit_GT4_Gas_Turbine_297257_2011-10-22'),
  ('GAS_TURBINE_INSPECTION_REPORT_HGPI_and_package_4_enhancement_for_DUKE_ENERGY_CORPORATION_WASHINGTON_ENERGY_FACILITY_Unit_1_Gas_Turbine_297623_2011-10-08'),
  ('GAS_TURBINE_INSPECTION_REPORT_Major_Inspection_for_Excessive_Vibrations_for_DUKE_ENERGY_HANGING_ROCK_LLC_HANGING_ROCK_Unit_2GT1_Gas_Turbine_298127_2011-10-25'),
  ('GAS_TURBINE_INSPECTION_REPORT_Major_Inspection_for_LAMAR_POWER_PARTNERS_LP_LAMAR_POWER_PARTNERS_Unit_GT3_Gas_Turbine_297258_2011-10-28'),
  ('GAS_TURBINE_INSPECTION_REPORT_UNIT_1_COMPRESSOR_UPGRADE_for_CASCO_BAY_ENERGY_COMPANY_LLC_MAINE_INDEPENDENCE_Unit_GT-1_Gas_Turbine_297197_2011-10-01'),
  ('GAS_TURBINE_INSPECTION_REPORT_UNIT_2_COMPRESSOR_UPGRADE_for_CASCO_BAY_ENERGY_COMPANY_LLC_MAINE_INDEPENDENCE_Unit_GT-2_Gas_Turbine_297198_2011-10-01'),
  ('GAS_TURBINE_INSPECTION_REPORT_Unit_2B_Hot_Gas_Path_Inspection_for_DOMINION_ENERGY_Fairless_Unit_2B_GT_Gas_Turbine_298235_2012-03-24'),
  ('STEAM_TURBINE_INSPECTION_REPORT_D11_L-0_bucket_replacement_and_valve_outage_Jan._2011_for_DYNEGY_INC_CASCO_BAY_ENERGY_COMPANY_LLC_Unit_ST_Steam_Turbine_270T432_2011-01-15'),
  ('g_GE_Energy_Services_D11_Major_Inspection_Technical_Direction_for_Dynergy__LS_Power_MAINE_INDEPENDENCE_Unit_1_Steam_Turbine_270T432_2007-04-09'),
  ('g_GE_Energy_Services_Generator_Field_Changeout_for_SITHEINDEPENDENCE_POWER_PARTNERS_Sithe_Northeast_Unit_6_Steam_Turbine_270T259_2006-05-07')
AS t(pdf_name);

-- Query 1: Full presence check (chunks + metadata)
WITH dev_chunked AS (
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

-- Query 2: Missing from chunk table only (with metadata context)
WITH dev_chunked AS (
  SELECT DISTINCT pdf_name
  FROM vaid.ai_std_con_field_service_report.vec_field_service_report
),
missing_pdfs AS (
  SELECT t.pdf_name
  FROM target_pdfs t
  LEFT JOIN dev_chunked d ON d.pdf_name = t.pdf_name
  WHERE d.pdf_name IS NULL
),
mapped AS (
  SELECT
    m.pdf_name,
    r.s3_filename AS document_id
  FROM missing_pdfs m
  LEFT JOIN vgpd.fsr_std_views.fsr_pdf_ref r ON r.pdf_name = m.pdf_name
)
SELECT
  m.pdf_name,
  m.document_id,
  CASE WHEN dev.document_id IS NULL THEN 'NO' ELSE 'YES' END AS in_metadata_table,
  CASE WHEN dev.pdf_name IS NULL THEN 'ORPHANED (NULL pdf_name)' ELSE COALESCE(dev.pdf_name, 'N/A') END AS metadata_row_status,
  COALESCE(dev.metadata_status, 'N/A') AS metadata_status,
  COALESCE(dev.chunk_status, 'N/A') AS chunk_status
FROM mapped m
LEFT JOIN vaid.ai_sot_field_service_report.biz_metadata_field_service_report dev
  ON dev.document_id = m.document_id
ORDER BY m.pdf_name;

-- Query 2b: Missing from metadata table only (expected 11)
WITH dev_metadata AS (
  SELECT DISTINCT pdf_name
  FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
)
SELECT t.pdf_name
FROM target_pdfs t
LEFT JOIN dev_metadata m ON m.pdf_name = t.pdf_name
WHERE m.pdf_name IS NULL
ORDER BY t.pdf_name;

-- Query 3: Summary counts (47 / in chunk / missing chunk / missing both)
WITH dev_chunked AS (
  SELECT DISTINCT pdf_name
  FROM vaid.ai_std_con_field_service_report.vec_field_service_report
),
dev_metadata AS (
  SELECT DISTINCT pdf_name
  FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
),
base AS (
  SELECT
    t.pdf_name,
    CASE WHEN c.pdf_name IS NULL THEN 0 ELSE 1 END AS in_chunks,
    CASE WHEN m.pdf_name IS NULL THEN 0 ELSE 1 END AS in_metadata
  FROM target_pdfs t
  LEFT JOIN dev_chunked c ON c.pdf_name = t.pdf_name
  LEFT JOIN dev_metadata m ON m.pdf_name = t.pdf_name
)
SELECT
  COUNT(*) AS total_target,
  SUM(in_chunks) AS in_chunk_table,
  COUNT(*) - SUM(in_chunks) AS missing_from_chunk_table,
  SUM(CASE WHEN in_chunks = 0 AND in_metadata = 0 THEN 1 ELSE 0 END) AS missing_from_both_tables,
  SUM(in_metadata) AS in_metadata_table,
  COUNT(*) - SUM(in_metadata) AS missing_from_metadata_table
FROM base;

-- Expected sanity checks:
-- total_target = 47
-- missing_from_chunk_table = 15
-- missing_from_both_tables = 11

-- Result (observed from current test run):
-- total_target = 47
-- in_chunk_table = 32
-- missing_from_chunk_table = 15
-- in_metadata_table = 32
-- missing_from_metadata_table = 15
-- missing_from_both_tables = 15
-- Interpretation: in the current dev state, all 15 chunk-missing PDFs are also missing from metadata.
--
-- Findings (from Query 2 and Query 4):
-- 1) Of the 15 missing PDFs, only 1 maps to a document_id in vgpd.fsr_std_views.fsr_pdf_ref.
-- 2) The mapped PDF is:
--    Field_Service_Report_ProjectID_A-1505048_FSP-253386_C-10323897.pdf
--    document_id = 71720880-e6c9-437b-b208-80e6c9437b53
--    metadata_row_status = ORPHANED (NULL pdf_name)
--    metadata_status = failed
--    chunk_status = pending
-- 3) The remaining 14 missing PDFs currently do not map to document_id via vgpd.fsr_std_views.fsr_pdf_ref
--    (document_id is NULL in mapping step), so they cannot be targeted by FSR_TARGET_PDF_NAMES yet.

-- Query 4: Detailed status of all 15 missing PDFs in dev metadata
-- Shows: document_id, whether row exists in dev, and any issues
WITH target_15_missing AS (
  SELECT t.pdf_name
  FROM target_pdfs t
  LEFT JOIN (SELECT DISTINCT pdf_name FROM vaid.ai_std_con_field_service_report.vec_field_service_report) c
    ON c.pdf_name = t.pdf_name
  WHERE c.pdf_name IS NULL
),
mapped_to_docid AS (
  SELECT
    t15.pdf_name,
    r.s3_filename AS document_id
  FROM target_15_missing t15
  INNER JOIN vgpd.fsr_std_views.fsr_pdf_ref r
    ON r.pdf_name = t15.pdf_name
),
dev_metadata_check AS (
  SELECT
    m.pdf_name,
    m.document_id,
    dev.document_id AS dev_document_id,
    dev.pdf_name AS dev_pdf_name,
    dev.metadata_status,
    dev.chunk_status
  FROM mapped_to_docid m
  LEFT JOIN vaid.ai_sot_field_service_report.biz_metadata_field_service_report dev
    ON dev.document_id = m.document_id
)
SELECT
  pdf_name,
  document_id,
  CASE
    WHEN dev_document_id IS NULL THEN 'NO_ROW_IN_DEV'
    WHEN dev_pdf_name IS NULL THEN 'ORPHANED (NULL pdf_name)'
    ELSE 'ROW_EXISTS'
  END AS metadata_row_status,
  dev_pdf_name,
  metadata_status,
  chunk_status
FROM dev_metadata_check
ORDER BY pdf_name;

-- Query 5: Cleanup orphaned rows before batch ingestion
-- DELETE FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report
-- WHERE document_id IN (
--   SELECT document_id FROM (
--     WITH mapped_15 AS (
--       SELECT t.pdf_name FROM target_pdfs t
--       LEFT JOIN (SELECT DISTINCT pdf_name FROM vaid.ai_std_con_field_service_report.vec_field_service_report) c
--         ON c.pdf_name = t.pdf_name
--       WHERE c.pdf_name IS NULL
--     )
--     SELECT r.s3_filename FROM mapped_15 m15
--     INNER JOIN vgpd.fsr_std_views.fsr_pdf_ref r ON r.pdf_name = m15.pdf_name
--   )
-- ) AND pdf_name IS NULL;
