# Meeting Prep — FSR Metadata Tagging (Jon + Tao)

> **Date:** 2026-05-27
> **Invite from:** Jon → Tao, me added
> **Trigger:** Jon's morning conversation with Vince. Jon has "thoughts on keyword search + semantic search on some key things."

---

## Context walking in

- **Jon** = customer-side; channel to Vince.
- **Tao** = internal architect / GE side; likely to defend current design and ask scoping questions.
- **"Keyword + semantic on some key things"** sounds like a hybrid-search ask, but **the app already runs hybrid** (see §2). The real ask is almost certainly something else — see §6 for likely interpretations.

---

## 1. What's tagged on FSR chunks today

**Filterable columns on the VS index:**

- `esn` (single string — `primary_esn` post multi-ESN design)
- `esns` (`ARRAY<STRING>` — multi-ESN, when v2 lands)
- `equipment_sys_id`, `equipment_type`, `equipment_class_code`
- `outage_type`, `technology_type` (PSOT enrichment)
- `document_id`, `chunk_id`, `page_number`
- `generator_serial` — what the app actually filters on today (= `esn`)

**In chunk `metadata` JSON (retrievable, not filterable):**

- `doc_summary` (TOC extraction — verbatim per chunk)
- `executive_summary` status flags
- `esn_details` struct array (multi-ESN, when v2)
- Other PSOT fields

**Embedding (semantic side):** chunk text via `databricks-gte-large-en`. Index supports hybrid BM25 + vector natively.

---

## 2. Consumer app retrieval today (Unit-Risk Agent)

**Source:** [reference/app-consumer/app_code/uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/retriever_service.py](../../reference/app-consumer/app_code/uai3071390-genai-services-demand-generation-usecase/backend/services/data-service/src/data_service/services/retriever_service.py)

**Endpoint:** `POST /dataservices/api/v1/retriever/retrieve` — takes `issue_prompts[]` + `esn`.

**Per issue prompt:**

1. **Look up pre-computed embedding** from `main.gp_services_sdg_poc.heatmap_issue_prompt_embeddings` (exact match, lower+trim on `issue_prompt`). If not in table → empty result. *Implies a curated canned-prompt set, not arbitrary free text.*
2. **Direct REST call** to VS index `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm`:
   ```json
   {
     "query_text": "<issue_prompt>",
     "query_vector": "<precomputed embedding>",
     "filters_json": "{\"generator_serial\": \"<esn>\"}",
     "num_results": 10,
     "query_type": "HYBRID",
     "columns": ["chunk_id", "pdf_name", "page_number", "chunk_text", "generator_serial"]
   }
   ```
3. **Dedupe** by `chunk_id`, cap at top-10, resolve `pdf_name` via `fsr_metadata_service.resolve_pdf_names`.

**What's already on:**

- ✅ Hybrid (BM25 + vector)
- ✅ Single ESN filter (`generator_serial`)
- ✅ Pre-computed embeddings for canned prompts

**What's NOT used:**

- ❌ No equipment_type / outage_type / component / date filters
- ❌ No multi-ESN / train expansion
- ❌ No reranking
- ❌ No score threshold (always returns top-10)
- ❌ No filter operators (`>=`, `LIKE`, `NOT`, `OR`) on date/range fields

---

## 3. Databricks Vector Search — the full menu

| Mode | What it does | Use when | Current app uses? |
|---|---|---|---|
| **Vector / ANN** (`query_type="ANN"`) | Pure semantic (cosine on embeddings) | Concept-level matching, paraphrases | No |
| **Hybrid** (`query_type="HYBRID"`) | BM25 + vector, score-fused | Best general default — catches exact terms + paraphrases | **Yes** |
| **Filters** (`filters_json`) | Pre-filter on column values before search | Hard scoping (ESN, equipment, date) | Yes — only `generator_serial` |
| **Filter operators** | `<`, `>`, `<=`, `>=`, `NOT`, `LIKE`, `OR` | Date ranges, prefix matches, exclusions | Not used |
| **Array containment** | `{"esns": "ESN-123"}` matches if `ESN-123` ∈ `esns` array | Multi-ESN filtering (when v2) | Not used |
| **Reranking** | Re-score top-N with a second model (built-in or BYO) | Top-10 ordering matters more than recall | Not used |
| **Direct vector** (`query_vector` only) | Skip query embedding, use a precomputed one | Curated prompt libraries, batch | **Yes** (heatmap table) |
| **Column projection** | Pick which columns come back | Reduce payload, surface metadata | Yes — 5 columns today |

---

## 4. Knobs available today with no pipeline work

Anything that's **already a column on the index** can become a filter — app-side change only.

- `equipment_type`, `equipment_class_code`, `technology_type` — filter by GT / Gen / ST / aux directly instead of relying on ESN alone.
- `outage_type` — filter by MI / HGPI / CI.
- `report_date` — date-range filter (e.g., last 5 years) via filter operators.
- `esns` (array) — when multi-ESN v2 lands, switch from single `generator_serial` to array containment.

Plus app-side wins:

- **Reranking** — layer a built-in rerank on top of the top-10; tightens ordering when hybrid is noisy.
- **Score threshold** — cut below a similarity floor instead of always taking top-10.
- **Multi-pass retrieval** — issue multiple queries with different filter shapes, merge results.

---

## 5. Things that DO need pipeline work (new metadata + re-index)

These need extraction in P1 + new columns + re-index + backfill:

- `components ARRAY<STRING>` — combustor, stator, exciter, collector ring, hot gas path, blade row, etc. Needs LLM or regex against a component lexicon.
- `severity` / `criticality` — needs LLM extraction.
- `work_type` (inspect / repair / replace / borescope) — LLM or keyword extraction.
- `train_id` / `train_sys_id_fk` — denormalized from IBAT (tracked as ESN-28).
- `til_references ARRAY<STRING>` — `TIL-NNNN` patterns; regex is reliable.

---

## 6. Likely re-readings of Jon's ask (since hybrid is already on)

1. **Too many irrelevant chunks** — hybrid is on but weights / boilerplate are dragging non-related FSRs in. Wants tighter scoping or rerank.
2. **New filterable fields** (component, equipment, outage type, date) so the agent can pre-filter before semantic.
3. **Field-scoped keyword search** — e.g., "find FSRs where `component=stator` AND semantic matches issue prompt".
4. **Curated issue-prompt set expansion** — Vince may want new canned prompts that don't have embeddings in the heatmap table.
5. **Gen-content-filed-under-GT problem** — Vince noticing generator-relevant FSRs missing because they're tagged with the GT ESN (see [../ESN-resolution/train/FSR_IBAT_Investigation_2026-05-26.md](../ESN-resolution/train/FSR_IBAT_Investigation_2026-05-26.md), 458 mis-tagged FSRs). Train expansion (ESN-28) addresses this.

---

## 7. Questions to drive in the meeting

1. **Name 3–5 concrete failing queries from Vince.** Without examples, this stays abstract.
2. **What did Vince expect to see vs what came back?** Recall (missing docs), precision (wrong docs), or ranking (right docs, wrong order)?
3. **Filter vs rank?** Exclude non-matching chunks (filter) or boost matching ones (hybrid weight / rerank)?
4. **Does Vince know the app already runs hybrid?** Important to set the level; otherwise the meeting talks past each other.
5. **Are the failing queries on canned issue prompts or new ones not in the heatmap table?** Different root cause.
6. **Timeline expectation from Vince?** Sprint vs roadmap.
7. **Overlap with multi-ESN / train-expansion (ESN-28)?** Bring up if Jon describes Gen-filed-under-GT symptoms.

---

## 8. Bucketing template for the keywords Jon will name

Sort each example into one of:

| Bucket | What it means | Effort |
|---|---|---|
| **A. Already in hybrid body match** | Term appears in chunk text; hybrid should catch it | Investigate why it's not — boilerplate? rank weighting? |
| **B. Existing filterable column** | `equipment_type`, `outage_type`, `report_date`, etc. | App-side only — add to `filters_json` |
| **C. Needs new filterable column** | Component, severity, work_type, train_id | Pipeline change — extraction + re-index + backfill |
| **D. Out of scope here** | Different track (multi-ESN v2, scraping coverage) | Cross-ref tracker; don't open in this meeting |

---

## 9. Things to NOT volunteer

- Don't open the multi-ESN v2 tables conversation unless Jon brings up retrieval recall directly.
- Don't commit to new extracted tags (component, severity) without a scoping pass — LLM cost + re-index + backfill, not cheap.
- Don't claim hybrid is the easy fix — **it's already on**. Saying "let's turn on hybrid" in the meeting would be a credibility hit.

---

## 10. One-liner to lead with

> "The app already runs hybrid search — semantic + BM25 — with an ESN filter. So whatever Vince is hitting isn't solved by turning hybrid on. The leverage is in: (a) fields the index already has that the app could filter on but doesn't yet (equipment, outage type, date) — app-side change; (b) new extracted tags like component or severity — pipeline change; (c) the Gen-filed-under-GT problem we already have evidence on — train-expansion work in flight. If you can share 2–3 example queries that aren't working for Vince today, I can sort each into one of those buckets."

---

## 11. Post-meeting placeholders

- [ ] Concrete keyword / query list captured from Jon
- [ ] Each item bucketed (A / B / C / D per §8)
- [ ] Decision on who owns the consumer-app filter additions
- [ ] Decision on whether any new pipeline extraction is in scope this quarter
- [ ] Follow-up actions logged in [../ESN-resolution/tracker.md](../ESN-resolution/tracker.md) intake or a separate FSR retrieval tracker
