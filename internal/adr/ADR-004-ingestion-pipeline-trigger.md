# ADR-004: FSR Ingestion Pipeline Trigger Mechanism

| Field | Value |
|---|---|
| **Status** | DECIDED |
| **Date** | 2026-04-17 (updated from 2026-04-06) |
| **Decision owners** | Databricks team + DEV team |
| **Context** | New FSR PDFs arrive continuously. The ingestion pipeline (chunk → embed → write Delta → sync VS) needs a trigger mechanism. |

---

## Context

Currently there is **no automated production ingestion pipeline**. The existing vector index (`main.gp_services_sdg_poc.field_service_report_gt_litellm`) was populated ad-hoc by the DS team using notebook experiments. There is also a `field_service_report_gt_litellm_reingest_targets_20260323` table tracking a March 2026 re-ingestion batch.

The pipeline steps are:
1. Detect new / updated FSR PDFs
2. Chunk via V3 hierarchical recursive chunking (chunk_size=4000)
3. Extract ESN via LLM + regex
4. Generate embeddings (azure-text-embedding-3-large-1 via LiteLLM)
5. Write to Delta table
6. Sync Databricks Vector Search index

---

## Options Considered

### Option A: Scheduled Databricks Job (batch, periodic)
- Run daily/weekly — scan for new PDFs since last run, process incrementally
- Simple; low operational overhead
- **Con:** Stale index between runs; new FSRs not immediately searchable

### Option B: Event-driven trigger (file arrival)
- Trigger on PDF upload to Databricks Volume or S3
- Near-real-time indexing; new FSRs searchable quickly
- **Con:** More complex; requires event infrastructure (S3 event → Lambda → Databricks Job, or Databricks autoloader)

### Option C: Databricks Autoloader (structured streaming)
- Use Databricks Autoloader to watch the FSR Volume for new files
- Incremental, scalable, handles schema evolution
- Native Databricks pattern; integrates with Delta and VS sync
- **Con:** Streaming pipeline — more complex to operate than batch job

### Option D: Manual / on-demand trigger via REST
- DEV team triggers ingestion via Databricks Jobs API when needed
- Fine for MVP; not suitable for production at scale

### Option E: Ad hoc user-triggered ingestion from the SDG app ← **immediate build target**
- User has a document not yet in the main corpus (new FSR, missing evidence doc)
- From the SDG app UI: upload → scrape metadata → chunk → embed → append to delta table → sync VS index
- Two sub-components: (1) scraping program (extract title, date, ESN from first page), (2) chunking + embedding + VS sink
- Owned by our team (DEV team); Databricks team owns mass migration separately
- This is the ad hoc path Tao confirmed (Apr-10): "for us, we build it like an ad hoc agent"
- **Con:** Need write access to a delta table in `main` (to be verified); VS sync must be triggerable per-doc

---

## Questions for Databricks Team

1. Where do FSR PDFs land in Databricks? **ANSWERED:** Two volumes: `/Volumes/viud/ing_ud_fieldvision/fv_field_service_report` (FieldVision) and `/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports` (manual/box).
2. How frequently do new FSRs arrive, and what is the acceptable staleness window? **OPEN**
3. Is Databricks Autoloader available and recommended in this workspace for ingestion pipelines? **SUPERSEDED:** Serverless compute confirmed; batch job via DBR workflow is the pattern.
4. How is the Vector Search index sync triggered after Delta writes? **OPEN** — current pipeline triggers sync programmatically.
5. Is there already a Foundation Service pipeline processing FSRs upstream — should we hook into that instead of reading PDFs directly? **OPEN**
6. Who owns the re-ingestion tracking table (`..._reingest_targets_20260323`)? Is there a pattern here we should follow? **OPEN**

---

## Decision

> **Option A: Scheduled Databricks Job (batch, periodic)** — via single multi-task DBR workflow triggered by Airflow.
>
> This was confirmed in the Apr 17 walkthrough. The production pattern is:
> 1. DBR workflow with notebook tasks (`fsr_metadata_extraction` → `fsr_chunk_ingestion`)
> 2. Airflow DAG triggers the job via `databricks_connection_module` → Jobs API `run-now`
> 3. Schedule: manual trigger initially, then weekly batch in production
> 4. Compute: serverless (confirmed by Shivam)
>
> Option E (ad hoc from SDG app) remains a separate path for user-uploaded documents, owned by our team. It does not replace the batch pipeline.

---

## Consequences

- Batch job means new FSRs have a staleness window (acceptable for weekly schedule)
- Airflow provides centralized scheduling, monitoring, and alerting across AI + data engineering jobs
- Serverless compute eliminates cluster management overhead
- The ad hoc ingest path (Option E) can be built in parallel as a separate feature of the SDG app
