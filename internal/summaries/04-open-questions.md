# 04 — Open Questions

**Status:** Draft — updated Apr 17 with walkthrough findings

These are the decisions and clarifications needed before the production build can start. Organized by priority.

**Closed since last update (Apr 17 walkthrough):**
- Airflow integration pattern: Pattern A confirmed (single multi-task DBR job, Airflow triggers)
- Compute model: Serverless confirmed
- Auth from Airflow→DBR: Functional SSO → PAT via AWS Secrets Manager
- Deployment: Databricks Asset Bundles via CI/CD to CICD user folder
- Repo: Existing GPFSR repo, bronze/silver/gold structure
- Secrets: Databricks secret scopes (named after FSSO), admin ticket to provision
- Airflow hosting: Separate MWAA instance for AI (Shivam creating)
- See [09-airflow-pipeline-design.md](../internal/09-airflow-pipeline-design.md) for full details.

---

## P0 — Blocking Everything

### Q1: How is the `query_fsr` service currently hosted on Databricks?

**Why it matters:** The query service is already implemented. Understanding the current hosting mechanism is needed to confirm whether modifications from gap decisions (Q2, Q3, Q9) can be applied in-place or require repackaging.

**Options to confirm:**
- Databricks Apps (FastAPI) — preferred per ADR-006
- Model Serving (MLflow pyfunc wrapper)
- Other — [TBD]

**Decision needed from:** [Databricks team]
**Status:** [OPEN]

---

### Q2: Which embedding model for production?

**Why it matters:** Ingest and query MUST use the same model. The full-corpus POC has a confirmed mismatch (different vector spaces — retrieval results unreliable). This decision also affects VS index configuration.

**Options:**
- LiteLLM (`azure-text-embedding-3-large-1`, 3072-dim) — used by `fsr_pipeline_gt_direct`, consistent, better eval results
- Databricks-managed GTE (`databricks-gte-large-en`, 768-dim) — simpler, no LiteLLM key needed at ingest
- Other — [TBD]

**Decision needed from:** [DS / architecture team]
**Status:** [OPEN]

---

## P1 — High Priority

### Q3: Is reranking mandatory or configurable?

**Why it matters:** Eval data shows reranking reduces R@1 by ~30% (0.432 → 0.303). Spec mandates unconditional reranking. These conflict.

**Options:**
- Reranking off by default, available as option (recommended based on eval data)
- Reranking on, accept R@1 tradeoff
- Reranking on for Q&A agent (less R@1 sensitive), off for RE flow (R@1 critical)

**Decision needed from:** [Architecture / product team]
**Status:** [OPEN]

---

### Q4: How is document type classification handled?

**Why it matters:** Gap 1 — FSRs, TILs, manuals all in the same index. Need to either classify at ingest or segment the index.

**Options:**
- LLM classification on first-page content at ingest
- Upstream document type registry (linked to Volume GUIDs by the team that uploads PDFs)
- Heuristic filter (page count)
- Separate VS indexes per document type

**Decision needed from:** [Architecture team + data team (who uploads to Volume)]
**Status:** [OPEN]

---

---

### Q6: What is the production Unity Catalog structure?

**Why it matters:** All POC code uses `main.gp_services_sdg_poc`. Production must use `vaid.*`. Schema decisions (new columns for document_type, ESN source) need to be locked before the production table is created.

**Partial update (Apr 17):** The Databricks team uses `databricks.yml` variables to switch catalogs between environments — `vgpd` (Dev) / `vgpp` (Prod). This mechanism is confirmed and we should follow the same pattern. The exact schema and table names for production FSR tables are still TBD.

**Decision needed from:** [Databricks architect]
**Status:** [PARTIALLY ADDRESSED — mechanism confirmed, target names TBD]

---

## P2 — Need Before Build Starts


### Q8: Which pipeline variant is the production path?

**Why it matters:** Two DS pipelines exist:
- `fsr_pipeline` — full corpus, more complete infrastructure, but has embedding mismatch
- `fsr_pipeline_gt_direct` — 30-ESN subset, consistent LiteLLM embeddings, full eval harness, different column names

**Decision needed from:** [DS team]
**Status:** [OPEN]

---

### Q9: Is `fsr_scraped_file_mapping_ref` stable enough to wire up?

**Why it matters:** This table provides the 15-field structured metadata needed for Step 6 of the query spec. It exists in `main.gp_services_sdg_poc` but is not connected to retrieval. Before wiring up, need to confirm the data is production-quality and who owns promoting it to `vgpd.*`.

**Decision needed from:** [DS team / data team]
**Status:** [OPEN]

