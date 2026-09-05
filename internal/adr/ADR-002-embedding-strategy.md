# ADR-002: Query Embedding Generation Strategy

| Field | Value |
|---|---|
| **Status** | PENDING |
| **Date** | 2026-04-06 |
| **Decision owners** | DS team + DEV team |
| **Context** | At query time, the service needs a vector for the user's query. Two strategies exist. |

---

## Context

FSR retrieval uses HYBRID search — both `query_text` (keyword) and `query_vector` (dense) are supplied to Databricks Vector Search. The question is how the `query_vector` is generated at request time.

**Key finding from DS reference code (doc 06):** The ingestion pipeline does **not** call LiteLLM to generate embeddings. Databricks Vector Search auto-generates embeddings from `chunk_text` during index sync. Only the query path calls LiteLLM.

Embedding flow:
- Ingestion: `chunk_text` → Delta table (no embedding vector written) → VS sync → VS auto-embeds
- Query: user query text → LiteLLM REST call (`azure-text-embedding-3-large-1`) → `query_vector` for HYBRID

Current state in data-service: embeddings are **pre-computed** for known issue prompts (from the heat map) and stored in `main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings`. The service looks them up by exact text match.

The full `query_fsr` tool spec and the DS reference code (`REChain_final/REChainExperiment/fsr.py`, `query_fsr_with_metadata.py`) both use **on-the-fly embedding generation** via LiteLLM at request time, with `lru_cache(maxsize=512)` to avoid redundant calls for repeated queries.

---

## Options Considered

### Option A: On-the-fly via LiteLLM (per tool spec)
- Call the LiteLLM proxy at request time: `azure-text-embedding-3-large-1` (3072-dim)
- Same model used during ingestion → consistent embedding space
- Works for any free-text query, not just known issue prompts
- **Con:** Adds latency per request; depends on LiteLLM proxy availability
- **Con:** Requires network path from Databricks-hosted service → LiteLLM proxy

### Option B: Pre-computed lookup (current approach)
- Embed known issue prompts in advance; store in Delta table
- Zero latency for known prompts; no LiteLLM dependency at query time
- **Con:** Only works for prompts that exist in the embedding table — arbitrary queries return no vector
- **Con:** Table must be kept in sync as issue prompts change (heat map updates)
- **Con:** Falls back to text-only search for unknown prompts (lower recall)

### Option C: Hybrid — pre-computed with on-the-fly fallback
- Look up pre-computed embedding first
- If not found, generate on-the-fly via LiteLLM
- Best of both: low latency for known prompts, full coverage for free-text queries
- **Con:** More complex; two code paths to maintain

---

## Questions for Databricks / DS Team

1. Is the LiteLLM proxy (`https://dev-gateway.apps.gevernova.net`) reachable from a Databricks-hosted service at query time?
2. What is the acceptable latency budget for a single `query_fsr` call? (Embedding generation adds ~200–500ms)
3. Will `query_fsr` ever be called with free-text queries (not from the heat map issue list), e.g. from the Q&A agent?
4. How often does the heat map issue prompt list change? Is keeping `heatmap_issue_prompt_embeddings` in sync manageable?

---

## Recommendation (DS team view per tool spec + reference code)

Option A (on-the-fly) — confirmed by both the tool spec and the DS reference implementation (`fsr.py`, `query_fsr_with_metadata.py`). Ensures the service handles arbitrary queries, not just heat map prompts. The `lru_cache(512)` in the reference code mitigates latency for repeated queries.

---

## Decision

> **[PENDING — near-decided]** Option A is strongly indicated by DS reference code. Remaining blocker: confirm LiteLLM proxy is reachable from the Databricks-hosted service environment. If reachable, this ADR can be closed as **DECIDED: Option A**.

---

## Consequences (once decided)

- If Option A: need LiteLLM client in the Databricks service; latency SLA must account for embedding call
- If Option B: `heatmap_issue_prompt_embeddings` must be kept current; Q&A agent gets degraded retrieval for novel queries
- If Option C: most robust but adds code complexity
