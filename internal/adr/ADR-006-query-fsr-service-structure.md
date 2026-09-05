# ADR-006: query_fsr Service Internal Structure

| Field | Value |
|---|---|
| **Status** | PENDING (blocked on ADR-001) |
| **Date** | 2026-04-06 |
| **Decision owners** | DEV team |
| **Depends on** | ADR-001 (hosting mechanism), ADR-002 (embedding), ADR-003 (reranking), ADR-005 (auth) |

---

## Context

Once the hosting mechanism is decided (ADR-001), we need to settle the internal structure of the `query_fsr` service — how it is packaged, what framework it uses, and how the retrieval pipeline steps are organized.

---

## Options Considered

### Option A: FastAPI app (Databricks Apps or Model Serving pyfunc wrapper)
- Single FastAPI application with POST `/query_fsr` endpoint
- Same framework used in the existing data-service — familiar patterns
- Clean separation: `router.py`, `service.py` (pipeline logic), `config.py`
- Works well with Databricks Apps; can also be wrapped in a `pyfunc` for Model Serving

### Option B: Databricks notebook-backed endpoint
- Notebook with defined input/output — served via Model Serving
- Easier for DS team to iterate on; no packaging required
- **Con:** Harder to test, version, and CI/CD; notebook is not a proper service boundary

### Option C: Shared library + thin endpoint per tool
- Core retrieval logic in a shared `sdg_retrieval` Python package
- Each tool (`query_fsr`, `query_er`) is a thin wrapper around the shared lib
- Avoids duplication between FSR and ER pipelines (both are HYBRID + rerank + metadata join)
- **Con:** More upfront design work

---

## Proposed Structure (Option A — FastAPI, pending ADR-001)

```
databricks_layer/
├── services/
│   └── query_fsr/
│       ├── src/
│       │   └── query_fsr/
│       │       ├── main.py          # FastAPI app entrypoint
│       │       ├── config.py        # Env vars, table names, endpoints
│       │       ├── router.py        # POST /query_fsr route
│       │       ├── schemas.py       # Request/response Pydantic models
│       │       ├── pipeline/
│       │       │   ├── embed.py     # Query embedding via LiteLLM
│       │       │   ├── search.py    # HYBRID Vector Search
│       │       │   ├── rerank.py    # DatabricksReranker
│       │       │   ├── hydrate.py   # Chunk row hydration from Delta
│       │       │   └── enrich.py    # 3-view metadata joins
│       │       └── logging_utils.py # Query logging (timestamp, user, esn, k, duration)
│       ├── tests/
│       ├── Dockerfile               # (if Databricks Apps)
│       └── pyproject.toml
└── notebooks/
    └── ingestion/
        └── fsr_ingestion_pipeline.py  # Chunking → embedding → Delta → VS
```

---

## Questions to Resolve (pending other ADRs)

1. **ADR-001:** Is it FastAPI on Databricks Apps, or a pyfunc on Model Serving? This determines `main.py` structure and Dockerfile.
2. **ADR-002:** Does `embed.py` call LiteLLM directly, or look up from `heatmap_issue_prompt_embeddings`?
3. **ADR-003:** Is `rerank.py` always in the pipeline, or conditional?
4. Should `query_fsr` and `query_er` share a library, or be fully independent services? (ER pipeline is similar but different metadata joins)
5. What Python version and runtime constraints does the target Databricks environment impose?

---

## Decision

> **[PENDING]** — Blocked on ADR-001. Will be drafted once hosting mechanism is confirmed.

---

## Consequences (once decided)

- Determines folder structure under `databricks_layer/`
- Determines packaging (pyproject.toml, Dockerfile, or notebook)
- Determines how we write and run tests against the service
