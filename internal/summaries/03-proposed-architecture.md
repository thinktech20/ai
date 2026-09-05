# 03 — Proposed Architecture

**Status:** Draft — pending review
**Note:** This is a proposal based on our current understanding. Details depend on open decisions in the Open Questions doc.

---

## Overview

The FSR retrieval system has two tracks:

| Track | What it does | Owner (proposed) |
|---|---|---|
| **Track A — Processing pipeline** | PDF → chunk → ESN tagging → Delta → VS index sync | DEV team |
| **Track B — Query service** | REST endpoint: ESN + query → ranked chunks with metadata | **Implemented** — minor modifications may be needed based on gap decisions |

The data-service (AWS ECS) calls Track B over HTTP. Track A feeds the data that Track B queries.

---

## Track A — Processing Pipeline (Production)

### Proposed Flow

```
Volume (PDFs from FieldVision submissions)
  ↓
[NEW] Step 0: Document type classification
       — Classify each PDF: FSR / TIL / Technical Manual / ER / Other
       — Method: TBD (LLM on first-page content, or upstream registry)
       — Only FSRs proceed to the FSR chunk table
  ↓
Step 1: Load PDF — PyMuPDF
  ↓
Step 2: ESN identification (4-layer)
       — Layer 1: Regex on first 2 pages
       — Layer 2: Filename parsing
       — Layer 3: LLM (GPT-4o) full-doc scan
       — Layer 4: SOT ref view (fsr_pdf_ref) — takes priority
  ↓
Step 3: Recursive hierarchical chunking (V3, 4000 chars / 200 overlap)
  ↓
Step 4: Write to Delta table (one row per ESN per chunk)
         + join fsr_pdf_ref for ESN + report_date at write time
  ↓
Step 5: VS delta-sync → auto-embed with [TBD embedding model]
  ↓
Step 6: Metadata extraction (3-stage scraping pipeline — runs separately)
         → fsr_scraped_file_mapping_ref table
```

### Key Decisions Needed

- Document type classification method (Gap 1)
- Embedding model for production (Gap 6)
- ~~Processing trigger mechanism (scheduled vs file-arrival event) — ADR-004~~ **DECIDED (Apr 17):** Scheduled batch via DBR workflow + Airflow trigger. See ADR-004.
- Who owns running and maintaining this pipeline in production?

### Orchestration (Confirmed Apr 17)

The processing pipeline runs as a **single multi-task Databricks workflow** triggered by Airflow:
- **Compute:** Serverless
- **Trigger:** Airflow DAG calls Databricks Jobs API `run-now`
- **Task graph:** `fsr_metadata_extraction` → `fsr_chunk_ingestion` (→ optional `fsr_vs_sync_validation`)
- **Schedule:** Manual initially, weekly batch in production
- **Deployment:** Databricks Asset Bundles, CI/CD to workspace, bronze/silver/gold git structure

---

## Track B — Query Service (Existing Implementation)

> The query service is already implemented. The flow below reflects the current design. Modifications may be needed based on decisions around embedding model (Q2), reranking policy (Q3), and metadata join readiness (Q9).

### Current Flow

```
Input: { equipment_serial_number, query, top_k }
  ↓
Step 1: Embed query via LiteLLM gateway
         Model: [TBD — must match ingest embedding model]
  ↓
Step 2: HYBRID Vector Search
         Filter: generator_serial = equipment_serial_number
         Type: dense + BM25 keyword
  ↓
Step 3: Reranker — [DECISION NEEDED: mandatory vs optional]
         DatabricksReranker on chunk_text
  ↓
Step 4: Chunk hydration
         Secondary Delta SQL lookup by chunk_id
         Retrieves full chunk_text + metadata column
  ↓
Step 5: 3-view metadata join
         — fsr_pdf_ref: PDF filename ↔ report ID, ESN, report_date
         — fsr_scraped_file_mapping_ref: 15-field structured metadata
         — fsr_field_vision_psot: event details, outage type, status
           (dedup: prefer Completed > Started > Hold per event_id + ESN)
  ↓
Output: { chunks: [...], metadata: {...}, source_pdfs: [...] }
```

### Hosting

| Option | Description | Status |
|---|---|---|
| Databricks Apps | FastAPI app deployed as Databricks App | **Preferred — ADR-006** |
| Model Serving (pyfunc) | Wrapped as MLflow pyfunc endpoint | Alternative |
| Other | TBD by Databricks team | [PLACEHOLDER] |

> Hosting mechanism details to be confirmed. See Open Questions doc (Q1).

---

## Catalog Structure (Proposed Production)

| Layer | Catalog | Tables |
|---|---|---|
| Source / SOT | `vgpd.fsr_std_views` | `fsr_pdf_ref` (data team owns) |
| POC / experiment | `main.gp_services_sdg_poc` | `field_service_report`, `fsr_scraped_file_mapping_ref` |
| Production | `vaid.ai_std_con_field_service_report.*` | [To be created — pending confirmation] |

---

---

## [PLACEHOLDER] — Items to Confirm

- [ ] Is the two-track split (processing vs query service) the right framing?
- [ ] Confirm production catalog structure (resolves Q6)
- [ ] Confirm hosting mechanism for Track B (resolves Q1)
- [ ] Which gap decisions (Q2, Q3, Q9) require modifications to the existing query service?
