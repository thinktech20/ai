# FSR v2 Test Scenarios (Dev)

## Jobs Created By Dev Deployment

Deploy the `dev` target from the `pw_sdg_ai_ser_repo` branch. The bundle creates these jobs, configured to run as `service.globalopsfsso@gevernova.com`:

- `PW_SDG_FSR_V2_Metadata`
- `PW_SDG_FSR_V2_DDL`
- `PW_SDG_FSR_V2_Chunking`
- `PW_SDG_FSR_V2_VS_Index`
- `PW_SDG_FSR_V2_Validation`

Run `PW_SDG_FSR_V2_DDL` once before the metadata job if the dev v2 tables do not already exist.

Typical deployment command:

```bash
databricks bundle deploy -t dev
```

Run the DDL job first, then metadata, chunking, vector index, and validation.

## Setup: Load & Parse FSR PDF

### Params

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("jb_env", "dev")
dbutils.widgets.text("METADATA_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("INPUT_MODE", "volume_list")
dbutils.widgets.text("FSR_SOURCE_VOLUME_PATHS", "/Volumes/viud/ing_ud_fieldvision/fv_field_service_report,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/FSR_manual,/Volumes/vaid/ai_std_con_field_service_report/fsr_v2_test")
dbutils.widgets.text("FSR_TARGET_PDF_NAMES", "35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report,5b688732-39f2-48d2-a887-3239f258d28b,bdd56c7a-ebe5-4bf7-904a-5bb63091ba20,fcb1511e-596a-4a56-b151-1e596afa569c,9e279e5a-a24e-4ebd-a79e-5aa24efebd04,af693a98-1e5c-499d-aa10-cccc54885c64,796f4d53-a8ad-42e1-af4d-53a8add2e1a4,806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report,b775cf29-8b42-4a83-af21-53075fef0802,cc9fe3d7-87cc-4687-9fe3-d787cc3687b3,27314604-ed52-402f-921f-34737a048841,4597a853-5ffb-40bb-b0be-bd6307b0acdc,cdd0cca4-93ba-43b0-98e5-3d1ea2312c19,11338269-9d7c-4865-bfcf-1a4db9014acf,4a56cb21-fd6b-4300-ac1b-62cf53b868a0,69dfe261-34b0-4740-ab89-498e7d0072df,0be4a3ad-7395-41ea-8ec2-e7669c9c15aa,b7b347fd-0b59-4c67-b609-9ad2c35105cc")
dbutils.widgets.text("FSR_MAX_PDFS", "3")
dbutils.widgets.text("FSR_IBAT_TABLE", "vgpd.prm_std_views.ibat_equipment_mst")
dbutils.widgets.text("FSR_EVENT_VISION_TABLE", "vgpd.fsr_std_views.eventmgmt_event_vision_sot")
dbutils.widgets.text("FSR_PSOT_TABLE", "vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot")
dbutils.widgets.text("FSR_PDF_REF_VIEW", "vgpp.fsr_std_views.fsr_pdf_ref")
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2")
dbutils.widgets.text("FSR_V2_PARSER_VERSION", "pymupdf_v1.0")
dbutils.widgets.text("FSR_V2_METADATA_PROCESSOR_VERSION", "v2")
dbutils.widgets.text("FSR_PARSED_DOC_VOLUME_ROOT", "/Volumes/vaid/ai_sot_field_service_report/fsr_parsed_docs")
dbutils.widgets.text("FSR_LLM_MODEL", "gemini-3-flash")
dbutils.widgets.text("FSR_LLM_VERIFY_SSL", "false")
dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY", "sk-cjRRha3Ejczz8AmnJKyQxA")
```

After P1 succeeds, check helper table for equipment map:

```sql
SELECT * FROM vaid.ai_std_con_field_service_report.fsr_document_equipment_map_v2
WHERE document_id = '<document_id from P1>';
```

Expected: one row per unique ESN found in the document's `preprocessor_regions`.
For `337X510 2018-03-13 Borescope.pdf` you should see at least one row with `esn = '337X510'` and `is_active = true`.

---

## Stage 2: Chunk & Embed

### Params

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("jb_env", "dev")
dbutils.widgets.text("METADATA_TABLE_V2", "vaid.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("CHUNK_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_chunks_v2")  # change per strategy
dbutils.widgets.text("FSR_P2_BATCH_SIZE", "20")
dbutils.widgets.text("FSR_P2_MAX_ITERATIONS", "0")
dbutils.widgets.text("FSR_P2_MAX_RETRIES", "3")
dbutils.widgets.text("FSR_CHUNK_SIZE", "4000")
dbutils.widgets.text("FSR_CHUNK_OVERLAP", "200")
dbutils.widgets.text("FSR_MIN_CHUNK_SIZE", "100")
dbutils.widgets.text("FSR_CHUNKING_STRATEGY", "section")  # default to latest corrected strategy; change per strategy if needed
dbutils.widgets.text("FSR_EMBEDDING_MODEL", "azure-text-embedding-3-large-1")
dbutils.widgets.text("FSR_LLM_VERIFY_SSL", "false")
dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY", "sk-cjRRha3Ejczz8AmnJKyQxA")
dbutils.widgets.text("FSR_MAPPING_MISS_FAIL_THRESHOLD", "0.0")
```

---

## Stage 3: Vector Index

### P3 Initial Setup (Create Index)

Run **once** to create the vector search index:

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("CHUNK_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_chunks_v2")
dbutils.widgets.text("VS_INDEX_V2", "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")
dbutils.widgets.text("VS_ENDPOINT_V2", "pw-ser-sdg-vector-search")
dbutils.widgets.text("INDEX_MODE", "sync")
dbutils.widgets.text("FSR_DATABRICKS_VERIFY_SSL", "false")
dbutils.widgets.text("FSR_EMBEDDING_DIMENSION", "3072")
```

### P3 Sync (Update Index)

Run on subsequent executions to sync new chunks:

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("CHUNK_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_chunks_v2")
dbutils.widgets.text("VS_INDEX_V2", "vaid.ai_std_con_field_service_report.fsr_vs_index_v2")
dbutils.widgets.text("VS_ENDPOINT_V2", "pw-ser-sdg-vector-search")
dbutils.widgets.text("INDEX_MODE", "sync")
dbutils.widgets.text("FSR_DATABRICKS_VERIFY_SSL", "false")
dbutils.widgets.text("FSR_EMBEDDING_DIMENSION", "3072")
```

**Note:** After P2 generates new chunks, run with `INDEX_MODE: sync` to refresh the index.

====

Accuracy - Test - Dev:

Data from `fsr_metadata_v2` (document_id CSV for reinsert after table drop):

`4597a853-5ffb-40bb-b0be-bd6307b0acdc,796f4d53-a8ad-42e1-af4d-53a8add2e1a4,5b688732-39f2-48d2-a887-3239f258d28b,fcb1511e-596a-4a56-b151-1e596afa569c,0be4a3ad-7395-41ea-8ec2-e7669c9c15aa,bdd56c7a-ebe5-4bf7-904a-5bb63091ba20,27314604-ed52-402f-921f-34737a048841,11338269-9d7c-4865-bfcf-1a4db9014acf,ea57c362-cfe4-4b78-b70f-f0292c5f0fa3,b25c94da-d954-4283-9c94-dad954a28307,32689520-afed-4dd4-a895-20afed7dd4d2,111adf26-dcec-4b33-9adf-26dcec6b334e,af693a98-1e5c-499d-aa10-cccc54885c64,b775cf29-8b42-4a83-af21-53075fef0802,9e279e5a-a24e-4ebd-a79e-5aa24efebd04,cc9fe3d7-87cc-4687-9fe3-d787cc3687b3,cdd0cca4-93ba-43b0-98e5-3d1ea2312c19,4a56cb21-fd6b-4300-ac1b-62cf53b868a0,69dfe261-34b0-4740-ab89-498e7d0072df,b7b347fd-0b59-4c67-b609-9ad2c35105cc,d9b6c08b-d098-4939-a549-d113964e3150,b1cdbc80-364f-4240-8dbc-80364f1240fa,d3b1da8a-03b4-4ea6-aa7b-0482edb532ce,bddc3379-f29f-4665-9c33-79f29f1665be,3f5a1ea8-8f35-4e97-9a1e-a88f358e9768,a1f6ca9b-f5db-4f22-b6ca-9bf5db7f227a`

Data from `fsr_metadata_v2` (document_id CSV for reinsert after table drop):

`4597a853-5ffb-40bb-b0be-bd6307b0acdc,796f4d53-a8ad-42e1-af4d-53a8add2e1a4,35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report,5b688732-39f2-48d2-a887-3239f258d28b,fcb1511e-596a-4a56-b151-1e596afa569c,af693a98-1e5c-499d-aa10-cccc54885c64,b775cf29-8b42-4a83-af21-53075fef0802,9e279e5a-a24e-4ebd-a79e-5aa24efebd04,cc9fe3d7-87cc-4687-9fe3-d787cc3687b3,0be4a3ad-7395-41ea-8ec2-e7669c9c15aa,bdd56c7a-ebe5-4bf7-904a-5bb63091ba20,27314604-ed52-402f-921f-34737a048841,4a56cb21-fd6b-4300-ac1b-62cf53b868a0,11338269-9d7c-4865-bfcf-1a4db9014acf,68a99784-2d10-4ae0-8497-9799a6580849_605013098-37762-298250-final_master_report,cdd0cca4-93ba-43b0-98e5-3d1ea2312c19,69dfe261-34b0-4740-ab89-498e7d0072df,d9b6c08b-d098-4939-a549-d113964e3150,806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report,b7b347fd-0b59-4c67-b609-9ad2c35105cc`


=====

35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270T483-Final_Master_Report.pdf
806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-Final_Master_Report.pdf
3e91b865-2aaa-4233-ae4a-3e15ba641f96_605007134-180498-270T483-Final_Master_Report.pdf

=============

dev fsr list

cc9fe3d7-87cc-4687-9fe3-d787cc3687b3,0be4a3ad-7395-41ea-8ec2-e7669c9c15aa,bdd56c7a-ebe5-4bf7-904a-5bb63091ba20,4597a853-5ffb-40bb-b0be-bd6307b0acdc,27314604-ed52-402f-921f-34737a048841,4a56cb21-fd6b-4300-ac1b-62cf53b868a0,11338269-9d7c-4865-bfcf-1a4db9014acf,af693a98-1e5c-499d-aa10-cccc54885c64,b775cf29-8b42-4a83-af21-53075fef0802,9e279e5a-a24e-4ebd-a79e-5aa24efebd04,cdd0cca4-93ba-43b0-98e5-3d1ea2312c19,69dfe261-34b0-4740-ab89-498e7d0072df,d9b6c08b-d098-4939-a549-d113964e3150,796f4d53-a8ad-42e1-af4d-53a8add2e1a4,5b688732-39f2-48d2-a887-3239f258d28b,fcb1511e-596a-4a56-b151-1e596afa569c,b7b347fd-0b59-4c67-b609-9ad2c35105cc,35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report,806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report,3e91b865-2aaa-4233-ae4a-3e15ba641f96_605007134-180498-270t483-final_master_report,b1cdbc80-364f-4240-8dbc-80364f1240fa,3f5a1ea8-8f35-4e97-9a1e-a88f358e9768,32689520-afed-4dd4-a895-20afed7dd4d2,b25c94da-d954-4283-9c94-dad954a28307,d3b1da8a-03b4-4ea6-aa7b-0482edb532ce,111adf26-dcec-4b33-9adf-26dcec6b334e,Unit_10B_Borescope_Inspection_Spring_2026_,3d156a24-2bb9-4ccd-a81e-c122c39aa3ac,
a1f6ca9b-f5db-4f22-b6ca-9bf5db7f227a,dd49968b-f9f3-4190-8996-8bf9f3b190a4,a7d1eb20-01c4-4d3a-91eb-2001c4bd3a42,7bd46ac1-a114-45df-bbd1-9232920f34a6,4638f199-976b-4b59-b8f1-99976beb5920,5a80e76a-3286-45bb-80e7-6a328655bba8,2e99bef9-224d-4980-99be-f9224d698022,2e985aa3-4262-4a92-985a-a34262ca9215,d633b55c-0a89-4448-b945-4d5c3e5ecedc,c067602d-4b8f-4dd9-99e4-670db03c6d06,09aee7cd-b42f-40c5-aee7-cdb42f60c5ec,5f1ac3d0-eed1-4135-9ac3-d0eed11135f7,90d2b6a7-0f1e-4b2c-98c1-d7d9f254a5c7, 5a82aa03-e7dd-45c4-b226-460c508a4889, a9d4cff6-3586-4d8c-a26b-09754468d833_605013480-50051-298340-final_master_report, d82afaae-8979-436c-bb4e-92aaa8b48f62_605012157-52123-298340-final_master_report, be53e9a9-a3be-457b-a04f-2ed5d0387a1e, 65f6535e-e26a-4e7a-bd41-6cdf4eaf1efa, d1348ae1-b54c-418f-9833-b0ce99bcc899_605012157-52122-298339-Final_Master_Report.pdf, 2b66a60e-8501-4560-adf8-192af8d7a04d, 0208ea9c-327a-40fc-88ea-9c327a90fc5c, f93401b3-da8a-4e45-b401-b3da8a5e4552, 7a977117-fe94-4387-bac0-de48a2e45f5c, bab97474-e2af-4f40-8251-346a69bb5619_605012901-526-298006-final_master_report, 8675f3cf-c109-461b-b7b2-70d5f45adf87