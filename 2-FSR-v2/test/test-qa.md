# FSR v2 QA Parameters

Use these parameters for the QA validation run. The target list uses the document IDs supplied for the standalone/preprocessor regression notebook.

## Jobs Created By QA Deployment

Deploy the `qa` target from the `pw_sdg_ai_ser_repo` branch. The bundle creates these jobs, configured to run as `service.globalopsfsso@gevernova.com`:

- `PW_SDG_FSR_V2_Metadata`
- `PW_SDG_FSR_V2_DDL`
- `PW_SDG_FSR_V2_Chunking`
- `PW_SDG_FSR_V2_VS_Index`
- `PW_SDG_FSR_V2_Validation`

Run `PW_SDG_FSR_V2_DDL` once before the metadata job if the QA v2 tables do not already exist.

Typical deployment command:

```bash
databricks bundle deploy -t qa
```

Run the DDL job first, then metadata, chunking, vector index, and validation.

## Stage 0: Run QA FSR v2 DDL Job

Run `PW_SDG_FSR_V2_DDL` once before P1/P2/P3. It uses `CREATE TABLE IF NOT EXISTS`.

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("jb_env", "qa")
dbutils.widgets.text("METADATA_TABLE_V2", "vaiq.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("CHUNK_TABLE_V2", "vaiq.ai_std_con_field_service_report.fsr_chunks_v2")
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaiq.ai_sot_field_service_report.fsr_document_equipment_map_v2")
dbutils.widgets.text("RUN_LOG_TABLE_V2", "vaiq.ai_sot_field_service_report.fsr_run_log_v2")
dbutils.widgets.text("DQ_LOG_TABLE_V2", "vaiq.ai_sot_field_service_report.fsr_data_quality_log_v2")
dbutils.widgets.text("VS_INDEX_V2", "vaiq.ai_std_con_field_service_report.fsr_vs_index_v2")
dbutils.widgets.text("VS_ENDPOINT_V2", "pw-ser-sdg-vector-search-qa")
dbutils.widgets.text("FSR_PARSED_DOC_VOLUME_ROOT", "/Volumes/vaiq/ai_sot_field_service_report/fsr_parsed_docs")
```

## Stage 1: Load and Parse FSR PDFs

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("jb_env", "qa")
dbutils.widgets.text("METADATA_TABLE_V2", "vaiq.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("INPUT_MODE", "volume_list")
dbutils.widgets.text("FSR_SOURCE_VOLUME_PATHS", "/Volumes/viud/ing_ud_fieldvision/fv_field_service_report,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports,/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/FSR_manual")
dbutils.widgets.text("FSR_TARGET_PDF_NAMES", "35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report,5b688732-39f2-48d2-a887-3239f258d28b,bdd56c7a-ebe5-4bf7-904a-5bb63091ba20,fcb1511e-596a-4a56-b151-1e596afa569c,9e279e5a-a24e-4ebd-a79e-5aa24efebd04,af693a98-1e5c-499d-aa10-cccc54885c64,796f4d53-a8ad-42e1-af4d-53a8add2e1a4,806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report,b775cf29-8b42-4a83-af21-53075fef0802,cc9fe3d7-87cc-4687-9fe3-d787cc3687b3,27314604-ed52-402f-921f-34737a048841,4597a853-5ffb-40bb-b0be-bd6307b0acdc,cdd0cca4-93ba-43b0-98e5-3d1ea2312c19,11338269-9d7c-4865-bfcf-1a4db9014acf,4a56cb21-fd6b-4300-ac1b-62cf53b868a0,69dfe261-34b0-4740-ab89-498e7d0072df,0be4a3ad-7395-41ea-8ec2-e7669c9c15aa,b7b347fd-0b59-4c67-b609-9ad2c35105cc")
dbutils.widgets.text("FSR_MAX_PDFS", "19")
dbutils.widgets.text("FSR_IBAT_TABLE", "vgpd.prm_std_views.ibat_equipment_mst")
dbutils.widgets.text("FSR_EVENT_VISION_TABLE", "vgpd.fsr_std_views.eventmgmt_event_vision_sot")
dbutils.widgets.text("FSR_PSOT_TABLE", "vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot")
dbutils.widgets.text("DOC_EQUIPMENT_MAP_TABLE_V2", "vaiq.ai_sot_field_service_report.fsr_document_equipment_map_v2")
dbutils.widgets.text("FSR_V2_PARSER_VERSION", "pymupdf_v1.0")
dbutils.widgets.text("FSR_V2_METADATA_PROCESSOR_VERSION", "v2")
dbutils.widgets.text("FSR_PARSED_DOC_VOLUME_ROOT", "/Volumes/vaiq/ai_sot_field_service_report/fsr_parsed_docs")
dbutils.widgets.text("FSR_LLM_MODEL", "gemini-3-flash")
dbutils.widgets.text("FSR_LLM_VERIFY_SSL", "false")
dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY", "sk-aw6f93-Va0jFChhzct5MRQ")
```

## Stage 2: Chunk and Embed

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("jb_env", "qa")
dbutils.widgets.text("METADATA_TABLE_V2", "vaiq.ai_sot_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("CHUNK_TABLE_V2", "vaiq.ai_std_con_field_service_report.fsr_chunks_v2")
dbutils.widgets.text("FSR_P2_BATCH_SIZE", "20")
dbutils.widgets.text("FSR_P2_MAX_ITERATIONS", "0")
dbutils.widgets.text("FSR_P2_MAX_RETRIES", "3")
dbutils.widgets.text("FSR_CHUNK_SIZE", "4000")
dbutils.widgets.text("FSR_CHUNK_OVERLAP", "200")
dbutils.widgets.text("FSR_MIN_CHUNK_SIZE", "100")
dbutils.widgets.text("FSR_CHUNKING_STRATEGY", "section")
dbutils.widgets.text("FSR_EMBEDDING_MODEL", "azure-text-embedding-3-large-1")
dbutils.widgets.text("FSR_LLM_VERIFY_SSL", "false")
dbutils.widgets.text("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
dbutils.widgets.text("LITELLM_API_KEY", "<set-in-notebook>")
dbutils.widgets.text("FSR_MAPPING_MISS_FAIL_THRESHOLD", "0.0")
```

## Stage 3: Vector Index

Create the QA index once:

```python
dbutils.widgets.removeAll()
dbutils.widgets.text("jb_env", "qa")
dbutils.widgets.text("CHUNK_TABLE_V2", "vaiq.ai_std_con_field_service_report.fsr_chunks_v2")
dbutils.widgets.text("VS_INDEX_V2", "vaiq.ai_std_con_field_service_report.fsr_vs_index_v2")
dbutils.widgets.text("VS_ENDPOINT_V2", "pw-ser-sdg-vector-search-qa")
dbutils.widgets.text("INDEX_MODE", "create")
dbutils.widgets.text("FSR_DATABRICKS_VERIFY_SSL", "false")
dbutils.widgets.text("FSR_EMBEDDING_DIMENSION", "3072")
```

For later runs, change only `INDEX_MODE` from `create` to `sync`.

## Important

QA table values come from the `qa` target in `pw_sdg_ai_ser_repo/databricks.yaml`. The upstream IBAT, Event Vision, and PSOT tables are the same as dev. The configured QA source PDF volumes are also currently the same as dev, although the YAML notes that the QA ingestion volume may later change from `viud` to `viuq`; confirm that before running if the QA volume migration has happened.
