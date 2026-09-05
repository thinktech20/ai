# FSR Retrieval — Detailed Task Plan

Last updated: 2026-04-13
Status: MVP2 prep. No application-side code needed yet. Focus: notebook build + environment familiarity.

Context: Databricks team owns mass migration. We own ad hoc ingestion + query service. This is MVP2 prep work — features were killed in MVP1. Build now so we are ready when the requirement lands.

---

## Phase 0 — Environment Setup & Permission Validation

These must be done first. Everything else depends on knowing what we can actually do in the workspace.

| # | Task | Done when |
|---|---|---|
| 0.1 | Create own schema in `main` catalog (e.g. `main.ms_sdg_dev`) | Schema exists and is visible in Databricks catalog explorer |
| 0.2 | Create a test delta table in `main.ms_sdg_dev` | Table created without error |
| 0.3 | Try creating a Vector Search index on that test table | Index created; confirm if delta sync sink is allowed when we own the table |
| 0.4 | Confirm LiteLLM proxy reachable from notebook (`https://dev-gateway.apps.gevernova.net`) | Can call `azure-text-embedding-3-large-1` and get a 3072-dim vector back |
| 0.5 | Confirm `DatabricksReranker` is importable in notebook environment | `from databricks.sdk.service.catalog import DatabricksReranker` or equivalent works |

---

## Phase 1A — Scraping Program (PDF Metadata Extraction)

Standalone notebook. Reads a PDF from Volume, extracts first-page metadata, writes to a metadata delta table.

| # | Task | Done when |
|---|---|---|
| 1A.1 | Locate one FSR PDF in the Volume path (`/Volumes/vgpd/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/`) | Can read/display the PDF in notebook |
| 1A.2 | Extract first-page metadata: title, report date, ESN candidates, any structured fields | Extraction returns a dict with the key fields |
| 1A.3 | Run ESN identification (4-layer: regex → filename → LLM → SOT ref lookup) | ESN returned or `None` if not found; `esn_assignment_source` field populated |
| 1A.4 | Join to SOT ref (`fsr_pdf_ref`) to backfill/confirm ESN and report date | Join executes; result shows SOT-sourced ESN where available |
| 1A.5 | Write row to metadata delta table in `main.ms_sdg_dev` | Row visible in table; schema: `pdf_name`, `title`, `report_date`, `generator_serial`, `esn_assignment_source`, `raw_first_page_text`, `scraped_at` |
| 1A.6 | Run against 5–10 PDFs; inspect output for quality | Results look correct; note any LLM ESN false positives |

---

## Phase 1B — Chunking + Embedding + Vector Search Sink

Standalone notebook. Reads a PDF, chunks it, generates embeddings, writes to delta, syncs VS index.

| # | Task | Done when |
|---|---|---|
| 1B.1 | Load PDF and chunk using V3 hierarchical recursive chunking | Chunks produced; fields: `chunk_id`, `chunk_text`, `page_number`, `section_metadata` |
|  | Parameters: `chunk_size=4000`, `chunk_overlap=200`, splitters: section → subsection → RecursiveCharacterTextSplitter | |
| 1B.2 | Attach ESN and report date to each chunk | Each chunk has `generator_serial`, `report_date` (from scraping or SOT join) |
| 1B.3 | For multi-ESN PDFs: duplicate chunk row per ESN | Each ESN gets its own row; `chunk_id` suffix differentiated |
| 1B.4 | Generate embeddings for each chunk via LiteLLM (`azure-text-embedding-3-large-1`, 3072-dim) | Embedding vector present per chunk; dimension confirmed as 3072 |
| 1B.5 | Write chunk rows to delta table in `main.ms_sdg_dev` | Table populated; schema: `chunk_id`, `pdf_name`, `page_number`, `generator_serial`, `report_date`, `chunk_text`, `chunk_embedding` (3072-dim array), `created_at`, `uploaded_at` |
| 1B.6 | Create (or update) VS index on chunk delta table | Index created; type: delta sync, embedding source column = `chunk_embedding` |
| 1B.7 | Trigger VS index sync after write | Sync completes without error |
| 1B.8 | Run smoke test query: send query text + ESN filter, get top-k chunks back | Results returned; chunks are relevant to query; ESN filter is working |

---

## Phase 1C — End-to-End Ingestion Notebook

Combine 1A and 1B into a single runnable notebook. This is the ad hoc ingestion prototype.

| # | Task | Done when |
|---|---|---|
| 1C.1 | Combine scraping + chunking + embedding into one notebook | Single notebook: PDF in → delta table row + chunk rows + VS sync out |
| 1C.2 | Run against 3–5 different FSR PDFs (mix of long and short) | All succeed; inspect for ESN tagging quality and chunk count |
| 1C.3 | Verify metadata retrieval at query time: chunk row hydration works | Full row (incl. `report_date`, `created_at`) returned at query time, not just VS-minimal columns |
| 1C.4 | Add document type check (basic): reject or flag non-FSR documents | Simple classifier or page-count heuristic; note false accept/reject rate |
| 1C.5 | Write notebook summary: what worked, what needs access/decisions | 1-page summary for Tao / Aaron review |

---

## Phase 2 — Query Service Fixes

Updates to the existing `query_fsr` retrieval code. Do after Phase 1 so you understand the data shape.

| # | Task | Done when |
|---|---|---|
| 2.1 | Fix embedding model at query time: confirm using `azure-text-embedding-3-large-1` (3072-dim), not GTE (768-dim) | Single embedding model used at both ingest and query; dimensions match |
| 2.2 | Add chunk row hydration: after VS returns chunk_ids, reload full rows from delta table | `report_date`, `created_at`, `uploaded_at` present in query response |
| 2.3 | Connect scraping table to query response: join `fsr_scraped_file_mapping_ref` metadata into response | `scraped_mapping` object in response is populated (not empty `{}`) |
| 2.4 | Enforce ESN filter: `generator_serial` filter applied on every query; no results returned for chunks without matching ESN | Query without ESN returns 400; query with ESN only returns that ESN's chunks |
| 2.5 | Test updated query against own tables from Phase 1 | End-to-end: ingest PDF → query → correct chunks returned with full metadata |

---

## Phase 3 — Architecture Decisions (external dependencies)

These require input from Aaron / Shivam / DS team. Unblock them in the architect meeting after UAT.

| # | Task | Blocked on | ADR |
|---|---|---|---|
| 3.1 | Decide hosting mechanism: Model Serving vs Databricks Apps | Aaron | ADR-001 |
| 3.2 | Decide reranking: always on / configurable / k-threshold | DS team (k values per consumer) | ADR-003 |
| 3.3 | Confirm embedding strategy: Option A (on-the-fly LiteLLM) — near-decided, just need LiteLLM reachability confirmed | Shivam / Phase 0.4 | ADR-002 |
| 3.4 | Decide document type classification approach: LLM classifier vs upstream registry vs page-count heuristic | Tao + data team | Gap 1 |
| 3.5 | Clarify ingestion pipeline ownership: who runs it when Databricks team and DS team move on? | Aaron (architect meeting) | ADR-004 |
| 3.6 | Confirm production Unity Catalog schema for `vaid.*` tables | Aaron | Gap 3 |

---

## Phase 4 — Production Build (future, when MVP2 is scoped)

Do not start until Phase 3 decisions are locked and MVP2 requirements are confirmed.

| # | Task | Depends on |
|---|---|---|
| 4.1 | Create production delta tables in `vaid.ai_std_con_field_service_report.*` | ADR-001, 3.6, write access confirmed |
| 4.2 | Create production VS index on production delta table | 4.1 |
| 4.3 | Package query service per ADR-001 decision (FastAPI on Databricks Apps, or pyfunc on Model Serving) | ADR-001, ADR-006 |
| 4.4 | Integrate ad hoc ingestion into SDG app (user uploads doc → triggers notebook pipeline) | Phase 1C complete, ADR-004 decided |
| 4.5 | Mass migration: hand off batch ingestion notebook to Databricks team | Phase 1B complete, ownership decided |
| 4.6 | Wire `data-service` retriever_service.py to call new Databricks-hosted `query_fsr` endpoint | ADR-001, ADR-005 (auth) |
| 4.7 | Query logging implementation (per spec: timestamp, user, ESN, query, k, result count, duration) | Phase 4.3 |

---

## Immediate Next Step

**Start with Phase 0** — create own schema in `main`, confirm permissions, confirm LiteLLM reachable. This takes 30–60 minutes in the Databricks notebook and unblocks everything in Phase 1.
