# Vince Conversation — Apr 22

## Demo Queries

### Row counts

```sql
SELECT 'metadata' AS tbl, COUNT(*) AS cnt
FROM main.gp_services_sdg_poc.fsr_metadata_registry_backfill
UNION ALL
SELECT 'chunks', COUNT(*)
FROM main.gp_services_sdg_poc.fsr_chunks_backfill;
```

### Status distribution

```sql
SELECT metadata_status, chunk_status, COUNT(*) AS cnt
FROM main.gp_services_sdg_poc.fsr_metadata_registry_backfill
GROUP BY 1, 2
ORDER BY cnt DESC;
```

### Chunk table sample — embeddings + metadata JSON

```sql
SELECT chunk_id, document_id, pdf_name, page_number,
       LEFT(chunk_text, 200) AS chunk_preview,
       SIZE(chunk_embedding) AS embedding_dim,
       LEFT(metadata, 300) AS metadata_preview
FROM main.gp_services_sdg_poc.fsr_chunks_backfill
LIMIT 5;
```

### Document summary coverage (executive_summary from SOT)

```sql
SELECT
  COUNT(*) AS total_docs,
  COUNT(document_summary) AS with_summary,
  ROUND(COUNT(document_summary) * 100.0 / COUNT(*), 1) AS pct
FROM main.gp_services_sdg_poc.fsr_metadata_registry_backfill;
```

### Summary flowing through to chunks

```sql
SELECT chunk_id, pdf_name,
       get_json_object(metadata, '$.document_summary') AS doc_summary
FROM main.gp_services_sdg_poc.fsr_chunks_backfill
WHERE get_json_object(metadata, '$.document_summary') IS NOT NULL
LIMIT 3;
```

### VS index status

```python
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
idx = w.vector_search_indexes.get_index("main.gp_services_sdg_poc.vs_fsr_chunks_backfill")
print(idx.name, idx.status)
```

### Enrichment quality — ESN resolution rate

```sql
SELECT
  COUNT(*) AS total,
  COUNT(NULLIF(esn, '')) AS has_esn,
  ROUND(COUNT(NULLIF(esn, '')) * 100.0 / COUNT(*), 1) AS esn_pct,
  COUNT(NULLIF(event_type, '')) AS has_event_type
FROM main.gp_services_sdg_poc.fsr_metadata_registry_backfill
WHERE metadata_status = 'completed';
```

### Backfill throughput (from run log)

```sql
SELECT run_id, start_time, end_time,
       docs_processed, chunks_created,
       TIMESTAMPDIFF(SECOND, start_time, end_time) AS duration_sec
FROM main.gp_services_sdg_poc.fsr_run_log_backfill
ORDER BY start_time DESC
LIMIT 10;
```

---

## Key things built / highlights

- **Full 4-task pipeline** — DDL → Metadata → Chunks+Embedding → Validation, all on Databricks serverless
- **Schema redesign** — separate metadata registry (silver) + chunk table (gold), document_id as FK, materialized metadata JSON in every chunk
- **Batch drain loop** — P2 processes all pending docs in batches of 50, keeps going until queue empty. Supports parallel job runs via claim-based locking
- **Embedding pipeline** — 3072-dim vectors via LiteLLM gateway, concurrent API calls (8 threads × 32 texts/batch), per-doc failure threshold
- **Enrichment** — IBAT (ESN/equipment), Event Vision (event type/outage dates), PSOT (outage type, technology type), pdf_name from fsr_pdf_ref
- **Document summary** — pulls executive_summary from FSR SOT table (~50% coverage), zero LLM cost. Phase 2 will cover remaining via LLM
- **FORCE_RESET** — drops all tables + deletes VS index for clean schema migrations
- **Operational tables** — run_log (per-batch audit), data_quality_log (per-doc DQ findings)
- **41+ validation checks** — table existence, metadata quality, chunk quality, cross-table joins, backfill safety
- **All config parameterized** — no hardcoded table names or catalog refs in notebooks, everything via job parameters
- **Workspace URL auto-detection** — no hardcoded dev URLs, works across environments
- **Stale claim recovery** — in_progress docs stuck >30 min auto-reset to pending

---

## What changed from the DS experimentation code

The DS team had a working prototype that proved the concept. We kept the core chunking strategy (RecursiveCharacterTextSplitter, same params) and embedding model, but restructured pretty much everything else for production:

**Architecture**
- DS code had metadata extraction + chunking + embedding all in one notebook, tightly coupled — we split into separate P1 (metadata) and P2 (chunks) tasks with clear boundaries
- DS code ran as a single monolithic pass — we built a batch loop with claim-based locking so multiple jobs can run in parallel safely
- No workflow orchestration in DS code — we have a Databricks workflow with task dependencies (DDL → P1 → P2 → Validate)

**Schema / data model**
- DS code had one flat table — we have separate metadata registry (silver) and chunk table (gold) with document_id FK
- Added document_id (UUID) as the primary key throughout, replacing reliance on pdf_name
- Added chunk_status state machine (pending → in_progress → completed/failed) for tracking and parallel safety
- Materialized all metadata fields into a JSON blob on every chunk row for RAG retrieval

**Enrichment**
- DS code did ESN resolution during chunking — we moved it to P1 metadata extraction where it belongs
- Added IBAT, Event Vision, PSOT, and fsr_pdf_ref enrichment joins (DS had limited enrichment)
- Added pdf_name derivation from fsr_pdf_ref with fallback to volume path

**LLM integration**
- DS code used a fixed set of ~15 LiteLLM models — we consolidated to the gateway with configurable model names
- Added structured normalization prompt for metadata fields with batched LLM calls
- Added document_summary from SOT executive_summary (new)

**Operational readiness**
- No failure handling in DS code — we have per-doc error tracking, retry logic, stale claim recovery
- No audit trail — we added run_log and data_quality_log tables
- No validation — we have 41+ automated checks
- No parameterization — DS had hardcoded table names, we have full config via job parameters
- No idempotency — our MERGE operations are idempotent, safe to re-run

---

## Meeting summary

- Walked Vince and Tao through the end-to-end ingestion flow: metadata extraction, chunking, embeddings, vector search sync, and the backfill approach for the current corpus of roughly 17k FSRs.
- Reviewed the new table design: metadata registry plus chunk table keyed by document_id, with chunk-level metadata JSON to support retrieval and app integration.
- Confirmed the first-pass strategy for document summaries: populate from existing executive_summary where available, avoid LLM cost in the initial backfill, and handle a later targeted enrichment pass only for missing cases.
- Discussed operational controls for backfill: batch processing, parallel execution, retry handling, run logging, and a data-quality log for nulls, low-enrichment records, and failures.
- Vince emphasized getting a fast, usable first pass into UAT, even if some metadata fields are incomplete, as long as lineage, document traceability, and follow-up remediation are clear.
- The discussion then shifted to downstream app changes, environment coordination, possible additional Box-folder sources, and readiness for related work such as the heat map update and 7F gas turbine support.

## Vince open questions / asks

- Can we produce first-pass quality statistics after backfill, especially counts or percentages for missing key fields such as ESN and other important metadata?
- Will the first pass process all current FSRs in the active landing-zone volumes so that chunks, vector-search entries, and all extractable metadata are available across the corpus?
- Is there another UAT or Box folder outside the currently configured source volumes that also needs to be diffed and ingested?
- If another Box source exists, will the current de-duplication logic still prevent double ingestion, or does document_id handling need to change for multi-source ingestion?
- Which Databricks tables and environments are the real source of truth for rollout, and what is the concrete plan to avoid another dev-versus-prod mismatch?
- How should the app change so the resource list reflects the metadata and chunks actually used in analysis, while still making it visible if a possible source FSR was present but not used?
- Has app-change planning with Binayak's team started, and who is coordinating the implementation plan across teams?
- What is the status of the heat map update for UAT, and has that work already started?
- Are we in a good state on ER coverage and related inputs for the next 7F gas turbine phase, or is additional work still needed before that extension can proceed?
