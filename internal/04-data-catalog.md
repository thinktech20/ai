# 04 — Data Catalog

All Databricks tables, views, indexes, and endpoints used by the SDG use case.

---

## Environments

| Env | URL | Purpose |
|---|---|---|
| Dev | `https://gevernova-ai-dev-dbr.cloud.databricks.com` | Development workspace |
| Production | `https://gevernova-ai-dbr.cloud.databricks.com` | Production workspace |
| POC | `https://gevernova-nrc-workspace.cloud.databricks.com` | POC / experimentation workspace |

---

## Unity Catalog Structure

Four catalogs govern the data lifecycle:

| Catalog | Full Name | Role |
|---|---|---|
| **VIUD** | Unstructured Ingestion | Raw documents (Bronze) |
| **VIUP** | Processed Unstructured | OCR output, normalized metadata (Silver) |
| **VAID** | AI Curated | Vector embeddings, AI-ready datasets (Gold — RAG input) |
| **VAIP** | AI Consumption | Downstream outputs, pre-computed profiles (Gold — app consumption) |

**Unstructured Data Schema (VIUD/VIUP):**

| Table | Catalog | Content |
|---|---|---|
| `ing_ud_fieldvision.fv_field_service_report` | VIUD | FieldVision FSR PDFs |
| `ing_ud_spec.spec_boroscope_insp_field_service_report` | VIUD | Borescope spec PDFs |
| `ing_ud_fsr_manual.manual_field_service_report` | VIUD | Manually uploaded FSRs |
| `ai_sot_field_service_report.ocr_field_service_report` | VAID | OCR output Volume |
| `ai_sot_field_service_report.biz_metadata_field_service_report` | VAID | Business metadata table |
| `ai_std_con_field_service_report.vec_field_service_report` | VAID | Vectorized content (chunk + embedding) |

**S3 Backing Paths:**

| Path | Content |
|---|---|
| `s3://ge-vaid/ocr_field_service_report` | OCR output |
| `s3://ge-viud/fv_field_service_report` | FieldVision PDFs |
| `s3://ge-viud/manual_field_service_report` | Manual uploads |
| `s3://ge-viud/spec_boroscope_insp_field_service_report` | Borescope specs |

**Experiment catalogs:**

| Env | Catalog/Schema | Purpose |
|---|---|---|
| Experiment (full corpus) | `main.gp_services_sdg_poc` | DS experimentation — full FSR corpus |
| Experiment (30-ESN GT subset) | `main.gp_services_sdg_poc` | DS experimentation — ground truth subset |

> **Production tables (`vaid.*`) do not exist yet** — confirmed by Tao (2026-04-07). All current work is against the experiment catalog (`main.gp_services_sdg_poc`). Building the production pipeline is part of MVP2 scope.

---

## FSR — Primary Tables

### `vaid.ai_std_con_field_service_report.field_service_report`
**Production chunk + embedding table (Vector Search source)**

| Column | Type | Notes |
|---|---|---|
| `chunk_id` | STRING | PK — `{pdf_name}_{chunk_index}` or `{pdf_name}_{chunk_index}__{esn}` for multi-ESN |
| `pdf_name` | STRING | Source PDF GUID — join key to `fsr_pdf_ref` |
| `page_number` | INT | Chunk start page (not chunk ordinal) |
| `generator_serial` | STRING | ESN (nullable). Row duplicated per ESN for multi-ESN chunks |
| `report_date` | DATE | Extracted at ingestion (nullable) |
| `chunk_text` | STRING | Chunked text (~4,000 tokens max) |
| `metadata` | STRING | JSON blob — section hierarchy (section_1..5), chunk stats, ESN labels |
| `created_at` | TIMESTAMP | Row creation time |
| `uploaded_at` | TIMESTAMP | Row upload time |

> **No embedding column in Delta**: The ingestion pipeline does NOT write embeddings. Databricks Vector Search auto-generates embeddings from `chunk_text` during index sync (model: `azure-text-embedding-3-large-1`, configured on the VS index side).

### `vaid.ai_std_con_field_service_report.vs_field_service_report`
**Production Vector Search index** (Delta Sync index — VS auto-embeds)
- VS Endpoint: `pw-ser-sdg-vector-search`
- Embedding model: `azure-text-embedding-3-large-1` (3072-dim) — configured on VS index, called by VS during sync (NOT by the ingestion pipeline)
- Source: syncs from `field_service_report.chunk_text`

---

## FSR — Metadata Views (3 tables joined at query time)

### 1. `vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot`
Alias: `fsr_report`

Comprehensive FSR business/operational data from FieldVision. ~35,251 rows.

Key columns: `id`, `event_id`, `esn`, `report_name`, `site`, `site_name`, `customer_name`, `technology_type`, `outage_type`, `start_date`, `end_date`, `executive_summary`, `total_fired_hours`, `total_starts`, `report_unit_status`

> **Deduplication rule**: `(event_id, esn)` is not unique. Prefer row with most advanced `report_unit_status`: `Completed > Started > Not Started > Hold`. Tiebreak: latest `end_date`, then `start_date`, then `report_name`.

### 2. `vgpd.fsr_std_views.fsr_pdf_ref`
Alias: `pdf_ref`

Maps FSR documents to physical PDF filenames, with enriched metadata from the 3-stage extraction pipeline.

Confirmed columns (from DESCRIBE):

| Column | Type |
|---|---|
| `esn` | string |
| `ev_equipment_system_id` | string |
| `ev_equipment_type` | string |
| `ev_equipment_class` | string |
| `ev_event_type` | string |
| `ev_project_id` | string |
| `ev_equipment_event_id` | string |
| `ev_ofs_event_id` | string |
| `fsp_project_id` | string |
| `erp_project_id` | string |
| `fsr_number` | string |
| `report_issued_date` | string |
| `outage_start_date` | string |
| `outage_end_date` | string |
| `s3_filename` | string | Bare GUID (e.g. `00576c50-5466-41a7-af6d-070c903e5cbd`) — direct join key to `field_service_report.pdf_name` in chunk table |
| `PDF_name` | string | Human-readable filename (e.g. `Field_Service_Report_ProjectID_EV-170893_...pdf`) |

> **Filename column**: `PDF_name` (not `filename`) — queries must use this exact case.
> **Selection rule**: when multiple rows exist for same PDF, prefer exact `(PDF_name, esn)` match over filename-only before downstream `_psot` enrichment.
> **Filename normalization**: join on normalized PDF stem (strip `.pdf`, path prefix) — raw string equality fails due to `guid` vs `guid.pdf` vs path-qualified variants.

### 3. `vgpd.fsr_std_views.fsr_scraped_file_mapping_ref`
Alias: `scraped_mapping`

Supplementary metadata extracted from FSR PDFs via text scraping (see `07-fsr-metadata-extraction.md` for the pipeline that produces this). Provides file-level metadata not available in FieldVision.

This table is the output of a 3-stage pipeline: PDF text extraction → LLM normalization → IBAT+EventVision enrichment.

Key columns (15 normalized fields):

| Column | Notes |
|---|---|
| `filename` / `pdf_name` | Source PDF path — join key |
| `esn` | Equipment Serial Number (may be null for 2016-era FSRs) |
| `equipment_sys_id` | Equipment system ID |
| `equipment_type` | Equipment type (from IBAT if not in PDF) |
| `equipment_sub_class` | Equipment class/code (from IBAT if not in PDF) |
| `event_type` | Controlled vocabulary (40+ values, e.g. Major Inspection (MI), CI, HGPI) |
| `ev_project_id` | EVP-prefixed Event Vision project ID |
| `ev_equipment_event_id` | EV-prefixed Event Vision equipment event ID |
| `ofs_event_id` | Oracle Project / OFS event ID |
| `fsp_project_id` | FSP-prefixed project ID |
| `xxx_project_id` | Other prefix-based project IDs (A-, C-, etc.) |
| `fsr_number` | FSR # field (often null in pre-2016 documents) |
| `report_issued_date` | Normalized date from PDF |
| `outage_start_date` | From PDF or filled from Event Vision SOT |
| `outage_end_date` | From PDF or filled from Event Vision SOT |

> **Multi-ESN records**: When a PDF covers multiple ESNs, the pipeline splits into one row per ESN (positional pairing). `equipment_type` and `equipment_sub_class` are left empty in split rows.

---

## Reference / Enrichment Tables

These tables are read-only reference sources used during metadata enrichment. Not owned by the SDG pipeline.

### `vgpd.prm_std_views.ibat_equipment_mst`
**IBAT Equipment Master** — source of truth for equipment attributes.

Key columns: `ibat_equipment_sys_id`, `ibat_equip_serial_number`, `ibat_equipment_type`, `ibat_equipment_sub_class`

Used in: Stage 3 of FSR metadata extraction pipeline; `read_ibat` tool.

Join: FSR records join on `equipment_sys_id == ibat_equipment_sys_id` OR `esn == ibat_equip_serial_number`.

### `vgpd.fsr_std_views.eventmgmt_event_vision_sot`
**Event Vision Source of Truth** — source of truth for outage events, project IDs, and dates.

Key columns: `sot_ev_project_id`, `sot_ev_equipment_event_id`, `sot_ev_gtm_id` (OFS), `sot_fsp_project_id`, `sot_ev_event_type`, `sot_outage_start_date`, `sot_outage_end_date`

Used in: Stage 3 of FSR metadata extraction pipeline; `read_event_master` tool.

Join (multi-key): match any of EVP ID → EV Equipment Event ID → OFS/GTM ID → FSP ID.

---

## Join Relationships

```
field_service_report (chunk table)
  └── pdf_name
        └── fsr_pdf_ref.PDF_name          (normalized stem match)
              ├── PDF_name → fsr_scraped_file_mapping_ref.pdf_name
              └── (esn, ev_equipment_event_id) → fsr_field_vision_...psot.(esn, event_id)
```

| Join | From | To | Key |
|---|---|---|---|
| 1 | `field_service_report.pdf_name` | `fsr_pdf_ref.s3_filename` | Bare GUID — direct equality match (confirmed) |
| 2 | `fsr_pdf_ref.PDF_name` | `fsr_scraped_file_mapping_ref.pdf_name` | PDF filename |
| 3 | `fsr_pdf_ref.(esn, ev_equipment_event_id)` | `fsr_field_vision_...psot.(esn, event_id)` | Equipment serial + event |

---

## Experiment Tables (DS use — not production targets)

| Table | Purpose |
|---|---|
| `main.gp_services_sdg_poc.field_service_report` | Full FSR corpus (chunks + embeddings) |
| `main.gp_services_sdg_poc.field_service_report_gt_litellm` | 30-ESN ground truth subset |
| `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm` | VS index for 30-ESN GT subset |

---

## Embedding Configuration

| Setting | Value |
|---|---|
| Model | `azure-text-embedding-3-large-1` |
| Dimensions | 3072 |
| Proxy | LiteLLM Enterprise Proxy |
| Batch size | 32 |
| Max batch tokens | 7,000 |
| Persistence | Stored in Delta table at ingestion; indexed in VS; generated fresh at query time |

---

## Infrastructure

| Component | Value |
|---|---|
| VS Endpoint | `pw-ser-sdg-vector-search` |
| Databricks account | Private subnet in Databricks AWS account |
| Inbound from app layer | HTTPS (443) via GEV VPN |
| Outbound to LiteLLM | Via shared AWS account proxy |

---

## To Be Added

- ER (Engineering Report) tables and VS index (4d)
- Risk Matrix volume path
- PRISM gold table schema (4b)
- RE/OE output table schemas
