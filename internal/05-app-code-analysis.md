# 05 — App Code Analysis (data-service)

Source: `backend/services/data-service/` from `uai3071390-genai-services-demand-generation-usecase`.
Additional prior analysis: `local-scratch/docs/dbx/databricks-layer-findings.md` and `local-scratch/docs/dbx/data-service-databricks-analysis.md` (April 1, 2026).

---

## Backend Structure

```
backend/
├── agents/
│   ├── event-history-assistant/     # OE event history agent
│   ├── narrative-summary-assistant/ # RE/OE narrative agent
│   ├── orchestrator/                # LangGraph orchestrator (graph/nodes/pipeline/state)
│   ├── question-answer-agent/       # RE + OE Q&A agent (has RE+OE system prompts)
│   └── risk-evaluation-assistant/   # RE risk evaluation agent
├── libs/
│   └── commons/                     # Shared: logging, databricks.py
└── services/
    └── data-service/                # THE layer that touches Databricks (focus here)
        ├── databricks_client.py     # Direct SQL via databricks-sql-connector
        ├── client.py                # Naksha HTTP proxy client (alt path)
        ├── services/
        │   ├── retriever_service.py     # FSR vector search (HYBRID, batch mode)
        │   ├── fsr_metadata_service.py  # PDF name resolution
        │   ├── er_service.py            # ER vector search
        │   ├── ibat_service.py          # IBAT SQL queries
        │   ├── prism_service.py         # PRISM SQL queries
        │   ├── heatmap_service.py       # Risk matrix / heatmap
        │   ├── equipment_service.py     # ESN data-readiness counts
        │   └── train_service.py         # IBAT train data
        ├── routes/                  # FastAPI route handlers
        └── mcp/                     # MCP server (server.py + mcp_client.py)
```

---

## Two Databricks Access Paths

| Path | Class | How | When |
|---|---|---|---|
| **Direct SQL** | `DatabricksClient` | `databricks-sql-connector` → SQL Warehouse | Structured SQL queries (IBAT, PRISM, ER, heatmap, event data) |
| **Vector Search** | REST POST | `requests` → `/api/2.0/vector-search/indexes/{index}/query` | FSR + ER semantic retrieval |

**Naksha proxy** (`NakshaClient` in `client.py`) is an alternative/fallback SQL path — some services support both.

### DatabricksClient Config (env vars)

| Var | Default | Purpose |
|---|---|---|
| `DATABRICKS_HOST` | `https://gevernova-nrc-workspace.cloud.databricks.com` | SQL warehouse host |
| `DATABRICKS_TOKEN` | — | PAT token |
| `DATABRICKS_HTTP_PATH` | `/sql/1.0/warehouses/daff57b69fee5745` | Warehouse path |
| `DATABRICKS_SOCKET_TIMEOUT` | `120` | Socket timeout (seconds) |
| `DATABRICKS_SQL_MOCK_MODE` | `false` | Returns empty results without hitting Databricks |

---

## Three Databricks Catalogs

| Catalog | Role | Used for |
|---|---|---|
| `vgpd` | Dev — **default in all app code** | All SOT views (IBAT, ER, FSR, PRISM, Events, Heatmap) |
| `vgpp` | Prod | Only in DS experiment docs. NOT in app code. |
| `main` | Shared AI workspace | Vector search indexes + embedding tables |

Controlled by env var pattern: `CATALOG = os.getenv("CATALOG", "vgpd")`

---

## How FSR Retrieval Works Today (retriever_service.py)

The current implementation has **two modes**:

### Legacy mode (single query)
Simple `similarity_search` — used for backwards compatibility, no longer the primary path.

### Batch mode (primary path used by RE/OE)
Accepts a list of `{issue_id, issue_prompt}` pairs. For each issue:

```
Step 1: Look up pre-computed embedding
  SELECT issue_prompt_embedding
  FROM main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings
  WHERE LOWER(TRIM(issue_prompt)) = LOWER(TRIM(:query))

Step 2: POST to Databricks VS REST API (HYBRID)
  POST {VECTOR_DATABRICKS_WORKSPACE_URL}/api/2.0/vector-search/indexes/{index}/query
  {
    "query_text": issue_prompt,
    "query_vector": embedding_from_step1,
    "filters_json": {"generator_serial": esn},
    "num_results": top_k,
    "query_type": "HYBRID",
    "columns": ["chunk_id", "pdf_name", "page_number", "chunk_text", "generator_serial"]
  }

Step 3: Deduplicate by chunk_id (discard duplicates)

Step 4: Resolve pdf_names (batch SQL via fsr_metadata_service)
  SELECT s3_filename, PDF_name
  FROM vgpd.fsr_std_views.fsr_pdf_ref
  WHERE s3_filename IN (...) OR PDF_name IN (...)
```

**Important difference from full spec:** The current code retrieves **pre-computed embeddings** from `heatmap_issue_prompt_embeddings` — it does NOT generate embeddings on-the-fly. This means only known issue prompts (from the heat map) have embeddings. The full spec calls for on-the-fly embedding generation via LiteLLM.

**Missing from current implementation** (vs full spec):
- No reranking (DatabricksReranker not applied)
- No chunk row hydration (no second-pass Delta table lookup)
- No full 3-view metadata join for response enrichment
- fsr_metadata_service only resolves pdf names — not the full `fsr_report` + `scraped_mapping` join

### Vector Search Config (env vars)

| Var | Default | Purpose |
|---|---|---|
| `VECTOR_DATABRICKS_WORKSPACE_URL` | `https://gevernova-ai-dev-dbr.cloud.databricks.com` | VS workspace |
| `VECTOR_DATABRICKS_TOKEN` | — | PAT token for VS API |
| `VECTOR_SEARCH_INDEX` | `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm` | Active VS index |
| `EMBEDDING_TABLE_NAME` | `main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings` | Pre-computed embeddings table |

---

## Active Tables (What the App Actually Uses Today)

### FSR
| Object | Name |
|---|---|
| Chunk table (source) | `main.gp_services_sdg_poc.field_service_report_gt_litellm` |
| VS index | `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm` |
| Pre-computed embeddings | `main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings` |
| PDF metadata | `vgpd.fsr_std_views.fsr_pdf_ref` |
| FSR report metadata | `vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot` |

### ER
| Object | Name |
|---|---|
| Chunk table | `main.gp_services_sdg_poc.engineering_report_chunk` |
| Chunk table w/ embeddings | `main.gp_services_sdg_poc.engineering_report_chunk_litellm` |
| VS index | `main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm` |
| SOT table | `vgpd.qlt_std_views.u_pac` |

### Structured Data (SQL-only tools)
| Tool | Table | Schema |
|---|---|---|
| IBAT | `IBAT_EQUIPMENT_MST`, `IBAT_PLANT_MST`, `ibat_train_mst` | `vgpd.prm_std_views` |
| PRISM | `seg_fmea_wo_models_gen_psot` | `vgpd.seg_std_views` |
| Heatmap | `fsr_unit_risk_matrix_view` | `vgpd.fsr_std_views` |
| Events | `eventmgmt_event_vision_sot`, `event_equipment_dtls_event_vision_sot`, `scope_schedule_summary_event_vision_sot` | `vgpd.fsr_std_views` |

### Output Storage (DynamoDB — not Databricks)
| Table | Purpose |
|---|---|
| `app-uai3071390-sdg-ddtable-risk-analysys-output-table-dev` | RE/OE risk assessment output |
| `app-uai3071390-sdg-ddtable-navigation-summary-dev` | Narrative summaries |
| `app-uai3071390-sdg-ddtable-event-history-report-dev` | Event history reports |
| `app-uai3071390-sdg-ddtable-execution-state-store-dev` | Workflow execution state |

---

## [DECIDED] Architecture Boundary

The `query_fsr` (and other retrieval tools) will be **separate services hosted on Databricks**, not extensions of `retriever_service.py`.

```
data-service (AWS ECS)               Databricks (private subnet)
─────────────────────                ──────────────────────────────
retriever_service.py  ──HTTP POST──► query_fsr hosted service
                                       ├── LiteLLM embedding
                                       ├── Vector Search (HYBRID)
                                       ├── DatabricksReranker
                                       ├── Delta hydration
                                       └── SQL metadata joins
```

The existing `retriever_service.py` code shows **what the data-service expects as a caller** — it's useful as reference for the request/response contract, but the logic moves into Databricks.

---

## Key Patterns to Follow

When building new Databricks-layer code, match these conventions from the existing codebase:

1. **Use `DatabricksClient` for SQL** — parameterized `:param` syntax, sync + async methods available
2. **Use REST POST for Vector Search** — not the SDK; direct `requests.post` to the Databricks VS API
3. **Pre-computed embeddings** — look up from `heatmap_issue_prompt_embeddings` first; fall back to on-the-fly only if building new flows
4. **ESN filter always** — always filter by `generator_serial` in VS queries
5. **HYBRID query type** — always pass both `query_text` and `query_vector`
6. **Env var driven config** — all table names, catalog names, and endpoints are env vars with defaults
7. **Mock mode** — `DATABRICKS_SQL_MOCK_MODE=true` returns empty results for local dev/testing
8. **Async wrapper pattern** — sync methods wrapped with `asyncio.to_thread()` for async callers
9. **Batch operations** — resolve PDF names in a single batch SQL call, not per-chunk

---

## Gap Analysis: Current Code vs Full `query_fsr` Spec

| Feature | Current Code | Full Spec (4e tool spec) |
|---|---|---|
| Embedding generation | Pre-computed lookup from Delta table | On-the-fly via LiteLLM at query time |
| Query type | HYBRID | HYBRID (same) |
| Reranking | Not implemented | DatabricksReranker on chunk_text |
| Chunk hydration | Not implemented | Full chunk row reload by chunk_id |
| Metadata joins | PDF name only (fsr_pdf_ref) | 3 views: fsr_pdf_ref + _psot + scraped_mapping |
| Response shape | Flat list per issue | Grouped: chunk + fsr_report + pdf_ref + scraped_mapping |
| Deduplication | chunk_id dedup only | chunk_id dedup + _psot status dedup |
| Input mode | Batch (issue_prompts list) | Single query per call |
| Logging | Structured logger | Full query log (user, ESN, k, duration, errors) |

The **Databricks layer we build** should bridge this gap and deliver the full spec.
