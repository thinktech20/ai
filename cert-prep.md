# Databricks Certified Generative AI Engineer Associate — Cert Prep

**Exam date:** 2026-06-13 (Sat) — **D-27 from today (May 17)**
**Format:** ~45 multiple-choice questions, 90 min, ~70% to pass.
**Source material:**
- **Primary — Udemy course (read online):** full TOC + section list in [`dbx-genai-course/udemy/dbx genai cert.docx`](dbx-genai-course/udemy/dbx%20genai%20cert.docx). Work through the course directly on Udemy; use the docx as the index of what to cover.
- **Local partial download** at [`dbx-genai-course/udemy/ai-arch-main/`](dbx-genai-course/udemy/ai-arch-main/) — only the downloadable slide decks + hands-on notebook repo. Not the full course. Use for offline review of decks already watched, not as a substitute for the videos.
- **Supplements:** **DASF 2.0 ebook** + **Evaluating GenAI Apps whitepaper** (links inside the docx) — needed for §3 Eval and §4 Deploy gaps below.

> Different shape from interview prep:
> - **Interview** = explain trade-offs out loud, tell stories.
> - **Exam** = recognize *exact* product names, defaults, limits, and which Databricks feature solves a given scenario. Precise > eloquent.

---

## Local material inventory (partial — for offline reference)

The Udemy site is the primary source. The folder below has only the pieces Udemy lets you download.

**Slide decks** (`udemy/ai-arch-main/*.pptx`) — useful as a review checklist after watching the videos:

| # | Deck | Cert section |
|---|---|---|
| 1 | `Intro_to_GenAI_and_LLMs.pptx` | Foundations |
| 2 | `Introduction+to+Databricks.pptx` | Foundations |
| 3 | `Introduction_to_Apache_Spark.pptx` | Foundations |
| 4 | `The+Entire+Data+Estate.pptx` | Foundations |
| 5 | `Medallion+Architecture+and+Spark+Declarative+Pipelines+(SDP).pptx` | Foundations |
| 6 | `Intro_to_Prompt_Engineering.pptx` | §1 Design |
| 7 | `Prompt+Engineering+Techniques.pptx` | §1 Design |
| 8 | `Introduction_to_RAG.pptx` | §1 Design |
| 9 | `Chunking+Strategies+in+RAG.pptx` | §1 Design |
| 10 | `Search+and+Ranking+Algos+in+RAG.pptx` (+ `(1)` dup) | §1 Design |
| 11 | `Vector+Indices+in+Databricks+-+Types+and+Properties.pptx` | §1 Design |
| 12 | `Mlflow+and+PyFunc+in+Databricks.pptx` | §2 Build |
| 13 | `LangChain+and+Databricks.pptx` | §2 Build |
| 14 | `Mosaic+AI+Agent+Framework.pptx` | §2 Build |
| 15 | `AI+Agents+and+Compound+AI+Systems.pptx` | §2 Build |
| 16 | `Fine-Tuning+LLMs.pptx` | §2 Build (lite — not heavy on exam) |

**Hands-on notebooks** (`udemy/ai-arch-main/DatabricksGenAIEngineer-main/DatabricksGenAIEngineer-main/`):

| Folder | Notebooks | Cert section |
|---|---|---|
| `Databricks_Fundamentals/` | Module_1–4 + CSV data | Foundations |
| `GenAI_Fundamentals/` | `openai_api`, `Chat_Application`, `LLM_API_DB_SDK`, `SQL_AI_Query` | §1 Design |
| `LangChain/` | `Getting_Started_with_LangChain`, `SequentialChain`, `Unity_Catalog_Hosted_SQL_Function` | §2 Build |
| `RAG/` | `Data_Prep`, `Vector_Embeddings`, `Vector_Index_Creation`, `RAG_Application`, `RAG_Evaluation` | §1 + §3 |

**Gap call-out:** Even the full Udemy course is light on **§3 Evaluate & Govern** (mainly the `RAG_Evaluation` notebook) and **§4 Deploy & Monitor** isn't really covered. Plan to supplement those two sections with the DASF ebook, Eval whitepaper, and Databricks docs (Model Serving, Inference Tables, Lakehouse Monitoring, AI Gateway).

---

## Cert syllabus → topic map

### 1. Design — Retrieval, Context, Prompts
- **Material:** decks #6–11 + `GenAI_Fundamentals/*` + `RAG/Data_Prep`, `Vector_Embeddings`, `Vector_Index_Creation`, `RAG_Application`.
- **Maps to plan §**: 2 (RAG), 3 (Parsing), 4 (Chunking), 5 (Embeddings), 6 (Vector search).
- **Cert‑specific must‑knows:**
  - `ai_parse_document` SQL function — what it returns.
  - **Mosaic AI Vector Search** index types: *Delta Sync* (managed embeddings vs. self-managed embeddings) vs. *Direct Vector Access*.
  - **Vector Search endpoint** vs. **index** — which is the compute, which is the data.
  - **Embedding endpoint types**: Foundation Model API (pay‑per‑token), provisioned throughput, custom served model.
  - **Hybrid search** support (yes — dense + keyword).
  - **Filter** syntax for metadata pre‑filtering.
  - Default similarity metric (cosine for FM API embedding endpoints).

### 2. Build — Agents, Tools, MLflow
- **Material:** decks #12–15 + `LangChain/*` + Mosaic AI Agent Framework deck.
- **Maps to plan §**: nothing yet — biggest gap. Agent stuff was in §11 only as vocabulary.
- **Cert‑specific must‑knows:**
  - **Agent Framework** vs. **Agent Bricks** — when to pick which (code‑first vs. low‑code). *Agent Bricks not in Udemy — supplement with Databricks docs.*
  - **`mlflow.langchain.log_model` / `mlflow.pyfunc.log_model`** — wrapping a chain/agent for serving.
  - **MLflow Tracing** — `mlflow.<flavor>.autolog()`, `@mlflow.trace`, viewing spans.
  - **MLflow Model Registry** + **Unity Catalog** as the registry backend.
  - **`ChatAgent` / `ChatModel`** interface, message format, tool call shape.
  - **Unity Catalog Functions** (Python or SQL) → exposed as tools to an agent.
  - **Agent Bricks Knowledge Assistant** — what it auto‑builds (parse → chunk → embed → index → review app).
  - **Review App** — how to collect human feedback / labels.
  - **Genie spaces** vs. agents — when each fits.

### 3. Evaluate & Govern
- **Material:** `RAG/RAG_Evaluation.ipynb` (the only Udemy asset here) + **DASF 2.0 ebook** + **Eval whitepaper** (supplement required).
- **Maps to plan §**: 8 (Evaluation), 10 (Safety/Governance).
- **Cert‑specific must‑knows:**
  - **Mosaic AI Agent Evaluation** — built‑in judges: *correctness*, *groundedness*, *relevance*, *safety*, *retrieval relevance*.
  - **`mlflow.evaluate(...)` with `model_type="databricks-agent"`** — the canonical eval pattern.
  - **Custom judges** via `mlflow.metrics.genai.make_genai_metric`.
  - **Evaluation dataset schema** — `request`, `response`, `expected_response`, `retrieved_context`, `expected_retrieved_context`.
  - **AI Gateway**: rate limits, payload logging, PII detection, usage tracking.
  - **DASF 2.0 risks** — categories (12 risks across data, model, deployment).
  - **Unity Catalog** as the single governance plane — entities: *catalogs, schemas, tables, volumes, models, functions, vector indexes*.

### 4. Deploy & Monitor
- **Material:** **Not in Udemy bundle** — supplement entirely with Databricks docs on Model Serving + Inference Tables + Lakehouse Monitoring.
- **Maps to plan §**: 9 (Productionization).
- **Cert‑specific must‑knows:**
  - **Model Serving endpoint types**: *FM APIs (pay‑per‑token)*, *provisioned throughput*, *custom models*, *external models* (OpenAI/Anthropic via Databricks).
  - **Scale‑to‑zero** behavior + cold start.
  - **CPU vs. GPU** serving — when each is required.
  - **Inference Tables** — auto‑logged request/response Delta tables.
  - **Lakehouse Monitoring** on Inference Tables — drift, quality.
  - **Batch inference** patterns: `ai_query` SQL function vs. Spark UDF wrapping a model.
  - **A/B traffic splits** on a serving endpoint.
  - **Route optimization** — network egress.
  - **MLOps vs LLMOps** differences — prompts as artifacts, eval‑driven CI, registry for prompts/agents not just weights.

---

## Study plan — D-27 → exam day

Aligned to the [velocity.md](velocity.md) weekly capacity: **~6h/week May 17–30, ~12h/week May 31–Jun 13.** Total budget ~42h.

**Vehicle:** the **8-section Udemy course** in [`dbx-genai-course/udemy/dbx genai cert.docx`](dbx-genai-course/udemy/dbx%20genai%20cert.docx) drives the weekly plan. Local decks + the hands-on notebook repo are used in parallel for hands-on practice. Cert-blueprint coverage map below.

### Udemy section → cert blueprint map

| Udemy section | Course time | Cert blueprint coverage |
|---|---|---|
| S1 Introduction | 2 min | — (orientation) |
| S2 Discord community | 41 min | — (skip from study plan) |
| S3 Databricks Fundamentals | 45 min | foundation — platform context |
| S4 Data Engineering & Analytics Fundamentals | 1h 31m | foundation — Spark, Delta, medallion |
| S5 GenAI Primer & Fundamentals | 1h 58m | §1 Design (prompts, LLM basics) |
| **S6 RAG — Using your Enterprise Data** | **2h 27m** | **§1 Design** + parts of §2 Build (largest section, 41 lessons) |
| S7 AI Agents using LangChain | 54 min | §2 Build (agents, tools) |
| S8 Practice Tests | n/a | cross-cuts §1–§4 — use weekly from Wk 22 |

**Gap call-outs vs full blueprint:** Udemy course light on §3 Evaluate & Govern (DASF 2.0, MLflow eval judges, Review App, Genie) and §4 Deploy & Monitor (Model Serving endpoint types, Inference Tables, Lakehouse Monitoring, AI Gateway). Cover these from local decks + Databricks docs in Weeks 22–23.

### Week 19 wrap (Sun May 17) — 2h
- D-0 study block today: **Udemy S1 Intro + S3 Databricks Fundamentals** (≈45 min video). Skim local decks #1–2 (`Intro_to_GenAI_and_LLMs`, `Introduction+to+Databricks`) in parallel. Take ½ page notes in `notes/udemy-s3.md`. **Skip S2 Discord.**

### Week 20 (May 18–24) — 6h — Udemy S4 + S5 + start S6
| Day | Focus | Asset | Deliverable |
|---|---|---|---|
| Mon | **S4 DE & Analytics Fundamentals** (1.5h video) + local deck #3 (`Apache_Spark`) | Udemy S4 | Spark / Delta / medallion notes |
| Tue | **S5 GenAI Primer** (2h video) + local decks #1 + #6 (prompting) | Udemy S5 | Prompt patterns cheat-sheet |
| Wed | **S6 RAG — first batch** (lessons 1–10, ~30 min): intro + chunking + embeddings | Udemy S6 | Chunking trade-offs table |
| Thu | **S6 RAG — second batch** (lessons 11–20, ~40 min): vector search + indexing | Udemy S6 + local deck #11 | Delta Sync vs. Direct Access summary |
| Sat | Hands-on: run local `RAG/Data_Prep` + `Vector_Embeddings` + `Vector_Index_Creation` notebooks | Local notebooks | Index built end-to-end |

### Week 21 (May 25–31) — 6h — finish S6 + S7
| Day | Focus | Asset | Deliverable |
|---|---|---|---|
| Mon | **S6 RAG — third batch** (lessons 21–30): retrieval strategies + reranking | Udemy S6 | Retrieval-pattern notes |
| Tue | **S6 RAG — final batch** (lessons 31–41): RAG eval + production patterns | Udemy S6 | RAG-eval one-pager |
| Wed | Hands-on: run local `RAG/RAG_Application` | Local notebook | End-to-end RAG app run |
| Thu | **S7 AI Agents with LangChain** (54 min video) | Udemy S7 + local `LangChain/Getting_Started_with_LangChain` | LangChain on DB notebook run |
| Sat | Hands-on: run `LangChain/Unity_Catalog_Hosted_SQL_Function` + skim local decks #14 (Agent Framework) + #15 (Compound AI) | Local | Agent Framework vs Bricks crisp |

### Week 22 (Jun 1–7) — 12h — §3 Eval & Govern gap-fill + ★ Mock #1 (Sat Jun 6)
| Day | Focus | Asset | Deliverable |
|---|---|---|---|
| Mon | Local deck #12 (MLflow + PyFunc) + `mlflow.evaluate` | Local | `mlflow.evaluate` + log_model patterns |
| Tue | Local `RAG/RAG_Evaluation` notebook + eval judge whitepaper | Local | Judge list memorized |
| Wed | DASF 2.0 ebook part 1 (data + model risks) | DASF PDF | 12-risk table |
| Thu | DASF 2.0 ebook part 2 (deployment risks) + AI Gateway docs | DASF PDF + Databricks docs | Gateway feature list |
| Fri | UC governance entities + Genie + Review App | Databricks docs | UC entity list, Review App flow |
| ★ Sat Jun 6 | **Mock #1** — Udemy **S8 Practice Tests** (first pass) | Udemy S8 | **Score recorded — go/no-go gate** |
| Sun | Review wrong answers | — | Gap list → adjust Week 23 |

**Go/no-go rule:** Mock #1 < 65% → push exam to Jun 21 (one-week slip).

### Week 23 (Jun 8–14) — 12h — §4 Deploy gap-fill + ★ Mock #2 (Wed) + ★ EXAM (Sat Jun 13)
| Day | Focus | Asset | Deliverable |
|---|---|---|---|
| Mon | Model Serving endpoint types | Databricks docs | 4 endpoint types crisp |
| Tue | Inference Tables + Lakehouse Monitoring | Databricks docs | Auto-logging flow understood |
| ★ Wed Jun 10 | **Mock #2** — Udemy **S8 Practice Tests** (second set) | Udemy S8 | Score recorded |
| Thu | Targeted re-read of weakest topic from Mock #2 | — | — |
| Fri | Final vocabulary cheat-sheet skim + sleep early | — | — |
| ★ **Sat Jun 13** | **EXAM** | — | — |

---

## Cert‑specific vocabulary cheat sheet

The exam loves precise product names. Pre‑load these:

- **Mosaic AI Agent Framework** — code‑first agent building with `ChatAgent`/`ChatModel`.
- **Mosaic AI Agent Evaluation** — eval judges + datasets, called via `mlflow.evaluate`.
- **Agent Bricks** — low‑code; **Knowledge Assistant**, single‑agent, multi‑agent variants.
- **Mosaic AI Vector Search** — Delta Sync vs. Direct Vector Access indexes.
- **Mosaic AI Model Serving** — endpoints (FM APIs, provisioned throughput, custom, external).
- **Mosaic AI Gateway** — guardrails, rate limit, payload logging, PII detection, usage tracking.
- **Foundation Model APIs** — pay‑per‑token serving of common OSS + Databricks models.
- **AI Functions** (SQL): `ai_query`, `ai_extract`, `ai_classify`, `ai_summarize`, `ai_translate`, `ai_parse_document`, `ai_similarity`.
- **Unity Catalog** — governs catalogs/schemas/tables/**volumes**/**models**/**functions**/**vector indexes**.
- **MLflow Tracing**, **MLflow Evaluate**, **MLflow Model Registry (UC‑backed)**.
- **Inference Tables**, **Lakehouse Monitoring**, **Review App**, **Genie**.
- **DASF 2.0** — Databricks AI Security Framework; 12‑risk taxonomy.

## How this relates to the FSR work

The FSR pipeline already touches: Vector Search (Delta Sync index), embedding model via gateway, Unity Catalog tables/volumes, Workflows. Reuse the FSR architecture as your mental model for *most* exam scenarios — but the exam will lean on **Agent Bricks**, **Mosaic AI Agent Framework**, and **MLflow Tracing/Evaluate** which our prod pipeline does **not** use. Spend extra time on those three.

## Notes / running log

- _2026-05-17_ — Plan rebuilt against Jun 13 exam date. Udemy materials inventoried. Today's block = Foundations decks #1–5.
