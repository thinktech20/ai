# FSR v2 Section-Issue Retest Plan

Date: 2026-07-27

## Goal
Re-test the section/chunking fixes on a focused set of docs that includes:
- likely failure cases
- control docs that were likely stable before

This plan avoids full table reset by default and only deletes targeted records.

## Target document_id set
Use this exact set for delete + re-ingest:

1. 5b688732-39f2-48d2-a887-3239f258d28b
2. b775cf29-8b42-4a83-af21-53075fef0802
3. 27314604-ed52-402f-921f-34737a048841
4. fcb1511e-596a-4a56-b151-1e596afa569c
5. 35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report
6. b7b347fd-0b59-4c67-b609-9ad2c35105cc
7. bdd56c7a-ebe5-4bf7-904a-5bb63091ba20
8. cdd0cca4-93ba-43b0-98e5-3d1ea2312c19
9. 39_v1.0(17)

## Delete step (targeted only)
Run these SQL statements first.

```sql
-- 1) Delete target chunks
DELETE FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2
WHERE document_id IN (
  '5b688732-39f2-48d2-a887-3239f258d28b',
  'b775cf29-8b42-4a83-af21-53075fef0802',
  '27314604-ed52-402f-921f-34737a048841',
  'fcb1511e-596a-4a56-b151-1e596afa569c',
  '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
  'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
  'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
  'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
  '39_v1.0(17)'
);

-- 2) Delete target map rows
DELETE FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2
WHERE document_id IN (
  '5b688732-39f2-48d2-a887-3239f258d28b',
  'b775cf29-8b42-4a83-af21-53075fef0802',
  '27314604-ed52-402f-921f-34737a048841',
  'fcb1511e-596a-4a56-b151-1e596afa569c',
  '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
  'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
  'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
  'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
  '39_v1.0(17)'
);

-- 3) Delete target metadata rows
DELETE FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE document_id IN (
  '5b688732-39f2-48d2-a887-3239f258d28b',
  'b775cf29-8b42-4a83-af21-53075fef0802',
  '27314604-ed52-402f-921f-34737a048841',
  'fcb1511e-596a-4a56-b151-1e596afa569c',
  '35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report',
  'b7b347fd-0b59-4c67-b609-9ad2c35105cc',
  'bdd56c7a-ebe5-4bf7-904a-5bb63091ba20',
  'cdd0cca4-93ba-43b0-98e5-3d1ea2312c19',
  '39_v1.0(17)'
);
```

## Re-ingest notebook and exact parameters
Notebook to run:
- pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py

Use these widget values:

- TARGET_PDF_NAMES:
  5b688732-39f2-48d2-a887-3239f258d28b,b775cf29-8b42-4a83-af21-53075fef0802,27314604-ed52-402f-921f-34737a048841,fcb1511e-596a-4a56-b151-1e596afa569c,35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report,b7b347fd-0b59-4c67-b609-9ad2c35105cc,bdd56c7a-ebe5-4bf7-904a-5bb63091ba20,cdd0cca4-93ba-43b0-98e5-3d1ea2312c19,39_v1.0(17)
- FSR_SOURCE_VOLUME_PATHS:
  /Volumes/viud/ing_ud_fieldvision/fv_field_service_report,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/FSR_manual
- METADATA_TABLE_V2:
  vaid.ai_sot_field_service_report.fsr_metadata_v2
- CHUNK_TABLE_V2:
  vaid.ai_std_con_field_service_report.fsr_chunks_v2
- DOC_EQUIPMENT_MAP_TABLE_V2:
  vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2
- VS_INDEX_V2:
  vaid.ai_std_con_field_service_report.fsr_vs_index_v2
- VS_ENDPOINT_V2:
  pw-ser-sdg-vector-search
- LITELLM_BASE_URL:
  https://dev-gateway.apps.gevernova.net
- LITELLM_API_KEY:
  <your key>
- FSR_CHUNKING_STRATEGY:
  section
- DROP_TABLES_AND_INDEX:
  false

## Why DROP_TABLES_AND_INDEX should be false here
With targeted deletes already done, false keeps non-test docs intact and only rebuilds selected docs.

## Optional clean-slate mode
If you intentionally want full reset of all fsr_v2 dev data and index:
- set DROP_TABLES_AND_INDEX to true
- do not run targeted delete SQL first

## Post-ingest validation checklist
1. Section fields should be cleaner (less FORM/boilerplate as dominant headings).
2. Cross-section continuation chunks should keep section metadata on the newer section.
3. Footer/legal lines should be reduced in chunk text.
4. Control docs should still have expected mapping/chunk quality.
