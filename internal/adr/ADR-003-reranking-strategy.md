# ADR-003: Reranking — When and How

| Field | Value |
|---|---|
| **Status** | PENDING |
| **Date** | 2026-04-06 |
| **Decision owners** | DS team + DEV team |
| **Context** | DS experiments showed reranking improves Recall@20 but adds latency and slightly hurts low-k results. |

---

## Context

From DS retrieval experiments (4e):

| Mode | Recall@1 | Recall@5 | Recall@10 | Recall@20 |
|---|---|---|---|---|
| DBR HYBRID + criteria | 45.5 | 67.4 | 78.8 | 84.8 |
| DBR Reranked + criteria | 19.7 | 56.1 | 73.5 | **86.4** |

Reranking (DatabricksReranker on `chunk_text`) **hurts** low-k recall but **helps** at k=20. The tool spec says to apply it — but criteria text was not universally beneficial for reranked variants either.

The current data-service implementation does **not** rerank.

---

## Options Considered

### Option A: Always rerank (per tool spec)
- Apply `DatabricksReranker` on `chunk_text` after HYBRID retrieval
- Consistent behavior; simpler logic
- **Con:** Adds latency; may hurt Recall@1 for risk evaluation chains that rely on top-1 result

### Option B: Never rerank
- HYBRID only — simpler, faster
- Best for low-k use cases (risk evaluation, k=5–10)
- **Con:** Loses the Recall@20 benefit needed for narrative summaries

### Option C: Configurable per call (via `query_type` or separate flag)
- Callers opt in to reranking via a request parameter (e.g. `enable_rerank=true`)
- Risk evaluation: no rerank (k=5–10, latency sensitive)
- Narrative summary: rerank (k=20, quality sensitive)
- **Con:** Caller must know when to ask for reranking; more API surface

### Option D: Rerank only above a k threshold
- If `k <= 10`: skip reranking
- If `k > 10`: apply reranking
- No extra API surface; behaviour driven by k
- **Con:** Heuristic-based; not directly tied to use-case intent

---

## Questions for DS / DEV Team

1. What k values will each consumer use?
   - RE Risk Evaluation Chain: k = ?
   - RE Narrative Summary: k = ?
   - OE Event History: k = ?
   - Q&A Agent: k = ?
2. Is `DatabricksReranker` available in the target hosting environment (Model Serving / Apps)?
3. Is the latency overhead of reranking acceptable for risk evaluation (synchronous, user-facing)?
4. Does the tool spec's reranking requirement apply uniformly to all callers, or can it be optional?

---

## Decision

> **[PENDING]** — Need k values per consumer and latency budget to decide.

---

## Consequences (once decided)

- If always rerank: simpler service, but RE risk evaluation may see lower Recall@1
- If configurable: richer API; data-service must pass correct flag per use-case
- Determines whether `DatabricksReranker` import is a hard dependency in the service
