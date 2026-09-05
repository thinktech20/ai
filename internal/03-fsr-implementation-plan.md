# 03 — FSR Implementation Plan

Status: DRAFT — architecture decision locked, implementation details TBD.

This describes what the DEV team (with DS guidance) needs to build on Databricks to deliver the `query_fsr` REST tool.

## [DECIDED] Architecture: Separate Databricks-Hosted Service

The `query_fsr` tool will be a **standalone service hosted on Databricks**, NOT an extension of `retriever_service.py` in the data-service.

```
data-service (AWS ECS)
  └── retriever_service.py
        └── HTTP POST ──────────────────► query_fsr service (Databricks-hosted)
                                              ├── generates query embedding (LiteLLM)
                                              ├── HYBRID Vector Search
                                              ├── DatabricksReranker
                                              ├── chunk hydration (Delta)
                                              └── 3-view metadata joins
```

**Why separate:**
- Runs inside Databricks — direct access to Vector Search, Delta tables, and the reranker without network hops
- Clean ownership boundary: Databricks layer owns all retrieval logic; data-service owns routing/orchestration
- Matches the tool spec: "REST endpoint, DEV team determines URL path and auth"
- Consistent with how all other tools are designed (REST-first)

**What stays in data-service:** The existing `retriever_service.py` batch path may remain temporarily (for backwards compat) but the new `query_fsr` calls will go to the Databricks-hosted endpoint.

**Hosting options (DEV team to decide):**
- Databricks Model Serving (custom endpoint — fits the REST pattern well)
- Databricks Apps (newer, built-in web app hosting)
- Databricks Job + REST trigger (less ideal for low-latency retrieval)

---

## Two Phases

### Phase 1 — Ingestion Pipeline
Chunk FSR PDFs → generate embeddings → store in Delta → index in Vector Search.

### Phase 2 — Retrieval Service
Accept query + ESN → HYBRID search → rerank → enrich with metadata → return grouped JSON.

---

## Phase 1: Ingestion Pipeline

### Entry Point
`fsr_pipeline_dbr_final` (Databricks notebook package, reference implementation from DS team)

### Steps

```
Input: FSR PDFs (from FieldVision / Foundation Service)
  │
  ▼
1. PDF Parsing
   - Use recursive hierarchical chunking (V3 logic)
   - chunk_size=4000, chunk_overlap=200
   - Splits: section → subsection → sub-subsection → RecursiveCharacterTextSplitter
   - Output: JSON per document with chunk_id, chunk_text, page_number, section metadata
  │
  ▼
2. ESN Extraction
   - LLM + regex identification of generator_serial from chunk_text
   - Multi-ESN chunks: duplicate row per ESN
   - Join vgpd.fsr_std_views.fsr_pdf_ref to backfill generator_serial and report_date
     (use merge_ref_view_metadata() for repair)
  │
  ▼
3. Delta Table Write
   Target: vaid.ai_std_con_field_service_report.field_service_report
   Schema: chunk_id, pdf_name, page_number, generator_serial, report_date,
           chunk_text, chunk_embedding (vector, 3072-dim), metadata (JSON blob), created_at, uploaded_at
   Note: Per spec and Tao (Apr-10), embeddings MUST be persisted in the delta table.
         Reason: delta sync index auto-management can silently change the embedding model over time.
         The chunk_embedding column is written here; VS index is built on top of it (not auto-generated).
  │
  ▼
4. Vector Search Index Sync
   Index: vaid.ai_std_con_field_service_report.vs_field_service_report
   Type: Delta Sync index — VS reads chunk_text from Delta, calls embedding model automatically
   VS Endpoint: pw-ser-sdg-vector-search
   Embedding model: azure-text-embedding-3-large-1 (3072-dim) — configured on the VS index, not the pipeline
   Note: Pipeline triggers sync after Delta write; VS handles embedding generation internally
```

### Pre-flight Validation (before each run)
- Count total rows in embeddings table
- Count NULL `generator_serial` rows → attempt repair via `merge_ref_view_metadata()`
- List distinct ESNs in index vs ground truth ESNs
- Confirm VS index is queryable

---

## Phase 2: Retrieval Service (`query_fsr`)

### Interface
- **Type**: REST API (POST)
- **Spec owner**: DS team | **Impl owner**: DEV team
- DEV team owns URL path, auth mechanism

### Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `equipment_serial_number` | string | Yes | ESN to scope retrieval |
| `query` | string | Yes | Natural language search query |
| `k` | integer | Yes | Number of top results to return |
| `query_type` | string | No (default: HYBRID) | HYBRID or ANN |

> Caller does NOT pass `query_vector` — service generates it internally.

### Retrieval Pipeline

```
Step 1 — ESN scope
  Filter VS to generator_serial = equipment_serial_number

Step 2 — Generate query vector
  Embed query using azure-text-embedding-3-large-1 via LiteLLM
  (same model used at ingestion)

Step 3 — Databricks HYBRID Vector Search
  Pass: query_text, query_vector, filters_json={generator_serial: esn}, num_results=k
  Return (minimal cols only): chunk_id, pdf_name, page_number, chunk_text, generator_serial
  Fusion: RRF (dense + BM25), scores 0-1

Step 4 — Reranking
  Apply DatabricksReranker on chunk_text
  Return top k

Step 5 — Chunk row hydration
  Reload full chunk rows by chunk_id from Delta table
  (exposes report_date, created_at, uploaded_at)
  Fallback: use first-pass VS row if chunk_id not found in Delta

Step 6 — Metadata enrichment (parallelizable)
  JOIN to 3 views using chunk_id and pdf_name sets:
    a. fsr_pdf_ref via normalized pdf_name (prefer (pdf_name, esn) match)
    b. fsr_field_vision_...psot via (esn, event_id) — deduplicate by status priority
    c. fsr_scraped_file_mapping_ref via normalized filename
```

### Response Shape

```json
{
  "results": [
    {
      "rank": 1,
      "rerank_score": 0.847,
      "chunk": {
        "chunk_id": "...",
        "pdf_name": "...",
        "page_number": 3,
        "generator_serial": "297104",
        "report_date": "2023-04-15",
        "chunk_text": "...",
        "created_at": "...",
        "uploaded_at": "..."
      },
      "fsr_report": { "...": "all columns from _psot" },
      "pdf_ref": { "...": "all columns from fsr_pdf_ref" },
      "scraped_mapping": { "...": "all columns from fsr_scraped_file_mapping_ref" }
    }
  ],
  "metadata": {
    "equipment_serial_number": "297104",
    "query": "vibration issues during startup",
    "k": 5,
    "query_type": "HYBRID",
    "total_chunks_for_esn": 142,
    "result_count": 5,
    "duration_ms": 1230
  }
}
```

**Output rules:**
- All 4 grouped objects always present (empty `{}` if join misses, never omitted)
- `embedding` / `chunk_embedding` columns excluded from response
- `null` for blank/null cells; `"n/a"` kept as string

### Error Responses

| Status | Condition |
|---|---|
| 400 | Missing required field |
| 404 | No FSR chunks found for given ESN |
| 500 | Internal retrieval or join failure |
| 503 | Vector Search endpoint unavailable |

### Query Logging (required per spec)
Every call must log: Timestamp, User (JWT/Ping ID), ESN, Query, k, Result count, Duration (ms), Errors

---

## Open Questions / Decisions Needed

| # | Question | Status |
|---|---|---|
| 1 | What does app_code/data_services look like? How do other tools call Databricks today? | [BLOCKED] — waiting on code |
| 2 | Is reranking always on, or configurable per call? | [OPEN] |
| 3 | Should `query_type` be exposed to callers or fixed to HYBRID? | [OPEN] — DS spec says production may fix to HYBRID |
| 4 | What is the `PAGE_WINDOW` value used for hit evaluation? | [OPEN] |
| 5 | How are FSR PDFs delivered to the ingestion pipeline? (pull from FieldVision/Foundation Service API, or batch upload?) | [OPEN] |
| 6 | Incremental vs full re-ingestion strategy for new FSRs? | [OPEN] |
| 7 | Auth mechanism for the REST endpoint (JWT, Databricks token, Ping ID passthrough)? | [OPEN] — DEV team decides |

---

## Reference Code (from DS team)
- Ingestion: `fsr_pipeline_dbr_final` notebook package
- Retrieval validation: `query_fsr_with_metadata.py`
- Evaluation: `run_evaluation.py` + `src/evaluate_retrieval.py`
- Ground truth: `Heat Map - Unified Structure v0.1.xlsx`, `FSR_citations_processed_20260305_135321.xlsx`
