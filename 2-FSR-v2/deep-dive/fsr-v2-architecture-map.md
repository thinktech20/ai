# GE Vernova — FSR v2 RAG Pipeline + URA Retrieval: Architecture Map

> Interview deep dive (Senior SA). One page: the map, then one row per stage with **Why · Alternative · Failure mode · Result**.

## The business problem (30-second version)

The URA risk analyser gives a per-unit (ESN) risk view. The risk view uses Field Service Report (FSR) evidence. That evidence feeds service recommendations and outage planning.

- **Missed evidence:** Generator work was filed under the Gas Turbine ESN about 95% of the time. Only 235 FSRs were tagged to Generator ESNs, while 827 GT-tagged FSRs mentioned generators. A Generator ESN query returned **zero FSRs** for about **17% of affected units**.
- **Wrong label:** Generator content labeled "Gas Turbine" led the LLM to name the wrong equipment and suggest the wrong fix. That hurts trust in front of the customer.
- **Scale:** 50K PDFs in the queue. About 22K are in scope (2016+). 22,579 trains have both a GT and a Generator, so every one of them was exposed.

**North-star decision:** ESN/equipment attribution moved from *document-level* to *chunk-level*, and it is **deterministic** (not LLM-guessed), so the equipment a chunk belongs to is decided locally for each chunk.

**Business outcomes at a glance** (details in [Business value](#business-value--one-ingestion-many-consumers)):

| Outcome | What changed for the business |
|---|---|
| **Right evidence for the right unit** | Attribution 79% → 92%, wrong-unit noise < 1.5%. About 1 in 6 affected Generator units go from zero evidence to evidence. |
| **One ingestion, many consumers** | Raw PDFs, parsed text, metadata, equipment map and chunks are kept as governed UC assets. Risk assessment, Q&A, readiness/report listing, evals and DS experiments all read the same data instead of re-processing PDFs. |
| **Cheaper to change** | New chunking or embedding ideas re-run only P2 from the saved parse. No PDF re-read and no LLM re-run, so days of P1 are skipped per experiment. |
| **Lower run cost** | About 90% of the queue is screened out before any LLM call. |
| **Safe rollout** | Flags + legacy fallback: v2 was switched on per ESN with no downtime and no user-facing regression. |

---

## The map

```mermaid
flowchart LR
  subgraph SRC["Sources · Bronze (UC Volumes)"]
    V1[FieldVision PDFs]
    V2[Manual eCRT PDFs]
    REF[(IBAT · EventVision · PSOT<br/>reference tables)]
  end

  subgraph DBX["Databricks Serverless Jobs · Asset Bundles · daily 06:00 + backfill jobs"]
    P1A[P1-a Discover<br/>left_anti on document_id<br/>date gate 2016+]
    P1B[P1-b Parse<br/>pypdf2 + heading markers<br/>persist parsed artifact]
    P1C[P1-c Deterministic preprocessor<br/>hierarchical spans · ESN chain<br/>regions with char offsets]
    P1D[P1-d LLM normalize<br/>admin fields only · page 1<br/>via LiteLLM gateway]
    P1E[P1-e Enrich IBAT/EV/PSOT<br/>+ write equipment map per batch]
    P2A[P2 Region-first chunk<br/>4-level metadata cascade]
    P2B[P2 Embed 3072-d]
    P3[P3 VS Delta-Sync<br/>TRIGGERED]
  end

  subgraph DELTA["Delta Lake · Unity Catalog (Silver/Gold)"]
    M[(fsr_metadata_v2<br/>status queue + regions)]
    MAP[(fsr_document_equipment_map_v2<br/>doc x ESN x is_active)]
    C[(fsr_chunks_v2<br/>region_primary_esn)]
    VS{{Mosaic AI Vector Search<br/>fsr_vs_index_v2 · HYBRID}}
  end

  subgraph AWS["AWS · URA app (ECS Fargate)"]
    ALB[ALB + PingID OIDC]
    DS[data-service<br/>retriever_service]
    ORC[orchestrator LangGraph<br/>risk-eval · narrative · event-history]
    DDB[(DynamoDB<br/>state · checkpoints · outputs)]
    GW[Naksha SQL proxy<br/>API Gateway]
  end

  V1 & V2 --> P1A --> P1B --> P1C --> P1D --> P1E --> M
  REF --> P1E
  P1E --> MAP
  M --> P2A --> P2B --> C --> P3 --> VS
  ALB --> ORC --> DS
  DS -- "1 eligibility SQL" --> GW --> MAP
  DS -- "2 hybrid query + filters" --> VS
  ORC --> DDB
```

---

## Stage by stage

| # | Stage | **Why this choice** | **Alternative considered** | **Failure mode (seen or designed for)** | **Result** |
|---|---|---|---|---|---|
| 0 | **Platform: Databricks serverless + Delta + UC** | Data gravity: PDFs, IBAT, EventVision and PSOT already live in UC. Governance (grants, lineage) comes with it. No clusters to manage. | AWS-native: S3 + Step Functions + Lambda/Glue + OpenSearch. Rejected for this team because it copies governed data out of UC and adds a second security model. | Serverless driver memory and wall clock on big runs. | Runs capped at **5K docs (~17h)** instead of one 7-day run. A re-run *continues* instead of starting over. |
| 1 | **Queue = status columns on the Delta metadata table** (`pending → in_progress → completed/failed`, retry caps) | Idempotent `MERGE`. Backfill and incremental share **one code path**. The audit trail sits next to the data. | SQS or Step Functions state. Rejected: it's a second source of truth that has to be reconciled with the table. | BACKLOG mode starved DISCOVERY: failed docs that had used up their retries kept the backlog mode on. Also, `FORCE_RESET` is one flag away from wiping ~30h of work. | Retry cap plus `metadata_retry_count`. Destructive reset is now a separate job. Running the same work twice gives the same result. |
| 2 | **Date gate before any LLM call** | Cheapest filter comes first. About 90% of the queue is out of scope. | Process everything and filter at query time. That pays LLM + embedding cost on dead data. | Wrong date parse means a doc is wrongly excluded. | Screening **~2,195 docs/hr** vs **~217–359 docs/hr** through the LLM path. **0** pre-2016 violations. |
| 3 | **Parse once, persist the artifact** (pypdf2 + heading-marker injection) | P1 and P2 **must share the same text** because region char offsets are the contract between them. | Re-parse in P2 with a different parser (v1 did this: pdfplumber in P1, PyMuPDF in P2). | Parser drift makes offsets point at the wrong text, so chunks get the wrong ESN. We found this during implementation. | `parsed_volume_path` persisted. P2 loads the same artifact and only falls back to re-parsing when it is missing. The same artifact also feeds re-chunk experiments, RCA replay and gold labeling, so it's used well beyond P2. |
| 4 | **Deterministic preprocessor owns ESN/equipment** (multi-signal headings → hierarchical spans → local ESN chain: header → parent → single-type → IBAT train → neighbor → doc) | Under 1 s/doc and zero token cost. **Auditable**: every region carries `esn_source`, `esn_confidence`, `fallback_chain`. The LLM cannot make up a serial number. | LLM per section or per page for ESN tagging. Rejected: cost grows with page count (docs run to 600+ pages), results vary run to run, and there's no provenance. | Unnumbered headings (`GENERATOR`) were missed. A flat boundary list had no "flip-back" to the parent section. One ESN per type collapsed same-type multi-unit docs. | Rewrote it as a **section-span hierarchy**. Flip-back comes from the structure, so no special detection is needed. Unresolved ESNs stay empty and are **not** promoted to the doc primary (precision over recall). |
| 5 | **LLM for admin fields only** (customer, event type, FSR #) with preprocessor hints injected as "known facts" | Use the LLM where text is messy and a mistake is cheap. Use deterministic code where a mistake is expensive. Page 1 only, 6K chars. | Full-doc LLM extraction (v1 style). | LiteLLM 5xx or throttling during backfill. LLM output contradicting the preprocessor. | Merge rule: **preprocessor overrides LLM** on overlapping fields. Tiered retry. Concurrency ramps up gradually (3 → 6). |
| 6 | **Equipment map table** (doc × ESN, `is_active`) written **per batch** | Vector filters can't join. A small SQL table answers "which docs mention ESN X, as primary *or* secondary?" | Put `active_esns[]` on every chunk and filter only in VS. That duplicates data and makes "is this doc ready?" hard to answer. | Writing the map at the end of the run left completed docs **without map rows** when a run was interrupted (84% map coverage). Those docs couldn't be found. | Moved to a per-batch `MERGE` with stale-row delete, plus a repair job and an hourly completed-vs-mapped check. |
| 7 | **Region-first chunking + 4-level cascade** (upload < doc < section < **region**) | A chunk never crosses equipment boundaries, so the region's ESN wins. | v1: fixed-size chunks tagged with the doc ESN (fan-out/duplication across ESNs). | Coverage gaps: front matter or a whole doc in one untagged region. | Synthetic gap regions give full coverage. `region_primary_esn` on each chunk. Chunks made for **~89%** of completed docs in QA, with a known backlog in progress. |
| 8 | **Embeddings 3072-d via LiteLLM** | Better recall on dense technical text. The gateway gives central keys, quotas and model swaps. | 1536-d: half the storage and cheaper. Worth an eval before scaling to the full corpus. | Query and index embedding models don't match, which silently ruins ranking. | Model and dimension are recorded on every chunk and are required when creating the index. |
| 9 | **Mosaic AI Vector Search, Delta-Sync, TRIGGERED** | The index follows the Delta table and uses UC permissions. No separate ETL into a vector DB. | Continuous sync costs more and isn't needed for 8–10 new docs/day. The other option was OpenSearch / pgvector. | TRIGGERED doesn't sync on its own, so the index goes stale if P3 is skipped. | Explicit P3 sync step. Stale-index risk goes onto the ops checklist. |
| 10 | **URA retrieval: SQL eligibility gate → HYBRID vector search** | Step 1 (SQL on map + status) only returns docs that are **fully ingested and active** for the ESN, including secondary ESNs. Step 2 filters `region_primary_esn = ESN AND document_id IN (...)`. HYBRID because serials and part numbers are *lexical* while symptoms are *semantic*. | Pure ANN with no gate: half-ingested docs would leak in. Pure keyword search: misses "oil ingress" ≈ "lube contamination". | Eligible doc but zero VS hits: there is **no** second call to the legacy index (by design). Dedup without overfetch can return fewer than `top_k`. | **Filter fidelity 1.0**, **doc recall 0.94** on the probe set, p95 ~1.8–4.2 s. The secondary-ESN path fixes the 17% zero-result units. |
| 11 | **Feature-flagged rollout** (`FSR_MULTI_ESN_APPLIED`, `FSR_LOOKBACK_SET`) with legacy fallback | No regression: if v2 has no docs for an ESN, the legacy index serves it. Flags let us flip back without a redeploy. | Big-bang cutover to the v2 index. | Two paths drift apart. The legacy path lacks the secondary-ESN guarantee. | v2 served where it's ready. Legacy is kept as a safety net until v2 coverage is complete. |
| 12 | **Precomputed issue-prompt embeddings** (catalog table). The Q&A agent embeds live. | The issue catalog is fixed, so the embedding call and its cost drop out of the hot path and results are repeatable. | Embed every request. | The catalog embedding model differs from the index model. A missing catalog row returns empty results. | Deterministic, cheaper retrieval for the risk heatmap. Free-form Q&A still works. |
| 13 | **Evals as a promotion gate** (attribution gold set + retrieval probe set, MLflow) | Proves the redesign with numbers and stops regressions when the preprocessor changes. | Spot-checking a few PDFs by hand, or LLM-as-judge. | A small or unbalanced gold set hides regressions in rare layouts. | Attribution **79% → 92%** (96% in core sections), misattribution **< 1.5%**. Every field bug becomes a gold row. |

---

## Tradeoffs I'd defend in the room

| Decision | Gave up | Got | Why it was right *for this problem* |
|---|---|---|---|
| Deterministic ESN attribution over LLM | Some recall on messy layouts | Auditability, zero hallucinated serials, <1 s/doc | A wrong serial is worse than a missing one. The output drives customer-facing recommendations. |
| Precision-first (leave ESN empty instead of guessing) | Unattributed "shared" chunks are hidden | Filter fidelity 1.0 | The eval showed adding shared regions did **not** improve doc recall and lowered filter fidelity to 0.85–0.98, so the change was held back based on data. |
| Two-step retrieval (SQL gate + VS) | One extra round trip | Readiness guarantee + secondary-ESN recall | Readiness has to be *correct*. Half-ingested docs must never show up as evidence. |
| Lakehouse-native over AWS-native data plane | AWS-native services for the data plane | One governance model, no data copies | The data already lives in UC. Moving it adds risk and cost with no clear gain. |
| Flags + legacy fallback | Two paths to run for a while | Zero-regression cutover | Uptime for the business matters more than architecture purity. |
| Human-labeled gold set over LLM-as-judge for attribution | Labeling time (DS + field SME) | Ground truth you can defend in a review | The claim was "this chunk belongs to that serial". An LLM judge would share the same blind spots as the system being tested. |

---

## Evals — how we proved it

> Illustrative framing for the interview. Sample sizes and slice numbers are placeholders — align them with the real MLflow runs before presenting.

**Two eval tracks, one harness** (`sdg-evals`, runs logged to MLflow with the probe/gold-set version, knobs and code commit):

| Track | Question it answers | Ground truth | Key metrics |
|---|---|---|---|
| **A. Attribution eval** (ingest quality) | Is each region/chunk tagged with the right ESN and equipment type? | Stratified gold set, labeled at **region level** by DS + field SME: `document_id`, span offsets, `true_primary_esn`, `true_equip_type`, `true_active_esns` | Attribution accuracy, **misattribution rate** (wrong ESN), unresolved rate (empty ESN), per-slice accuracy, confusion matrix GT ↔ Gen ↔ ST |
| **B. Retrieval eval** (serving quality) | For an ESN + issue, do we return the right docs and pages, and only for that unit? | Probe set: ESN + issue query → expected docs and cited pages | `doc_recall@k`, cited page hit, `filter_match` (fidelity), p95 latency; k sweep 5/10/20/40; HYBRID vs vector |

**Gold-set design (Track A):** ~60 FSRs / ~400 labeled regions, stratified so the hard cases aren't drowned out:
- single-equipment docs (control group),
- GT + Generator on the same FSR (the core bug),
- same-type multi-unit (two GTs in one report),
- combined-cycle trains (GT + Gen + ST),
- messy layouts: unnumbered headings, TOC-only structure, long appendices.

**Results — v1 (doc-level tagging) vs v2 (region-level, deterministic):**

| Metric | v1 | v2 | Why it moved |
|---|---:|---:|---|
| Equipment attribution accuracy (all regions) | **79%** | **92%** | Region-first chunks + local ESN chain instead of one doc-level ESN |
| Accuracy in core equipment sections (GT / Gen / ST blocks) | ~81% | **96%** | Hierarchical spans + flip-back back to the parent section |
| Misattribution (tagged to the *wrong* unit) | ~19% | **< 1.5%** | Precision-first: unresolved stays empty instead of defaulting to the doc primary |
| Unresolved / shared (empty ESN) | ~2% | ~6.5% | The deliberate trade: move errors from "wrong" to "unknown" |
| Retrieval filter fidelity (Track B) | n/a | **1.0** | `region_primary_esn` filter + eligibility gate |
| Retrieval doc recall@10 (Track B) | — | **0.94** | Secondary-ESN path via the equipment map |

**How to read it:** most of the gain came from turning *wrong* answers into either *right* or *unknown*. For an engineer that difference matters a lot — a missing chunk is a gap you can see; a wrong-unit chunk is a finding you might act on.

### How scoring works (technical detail)

**Track A — attribution scorer**
- **Join key:** gold rows are keyed by `document_id + span_start_char + span_end_char` on the *persisted parsed text*, so labels stay valid across re-runs. Without the saved parse, offsets would drift and every label would need redoing.
- **Match rule:** a predicted chunk or region is scored against the gold region it overlaps most (`char_offset_max_overlap`, the same rule P2 uses). Overlap under 50% counts as *unscored* and is reported on its own, not hidden.
- **Normalization:** ESNs are upper-cased and trimmed, and the `SY…` system IDs are mapped to the unit ESN through IBAT before comparing, so format noise isn't counted as an error.
- **Three outcomes per region:** `correct` (ESN and type match), `wrong` (non-empty and different), `unresolved` (empty or shared). These give:
  - accuracy = correct / scored
  - misattribution = wrong / scored
  - unresolved rate = unresolved / scored
- **Slices:** accuracy is reported per equipment type, per doc profile (single, GT+Gen, same-type multi-unit, CC train) and per region source (`HEADER`, `SECTION_HDR`, `UNNUMBERED`, fallback). A GT ↔ Gen ↔ ST confusion matrix is saved as an artifact.

**Track B — retrieval scorer**
- Calls the **same code path as the app**: SQL eligibility gate → HYBRID query with the `region_primary_esn` + `document_id` filter. The eval tests what users actually get, not a simplified copy.
- Metrics:
  - `doc_recall@k` = expected docs found / expected docs
  - `cited_page_hit` = expected `(doc, page)` pairs found
  - `page_f1`
  - `filter_match` = returned chunks whose ESN equals the requested ESN / returned chunks
  - p50 and p95 latency
- Sweeps K over 5, 10, 20, 40, and compares HYBRID vs vector and the current filter vs the filter with shared regions.

**Harness and run lineage**
- One Databricks notebook job per track (`nb_fsr_v2_topk_eval`, mapping scorer) using the shared `harness.run_eval_detailed()`.
- Each run is an **MLflow run** that logs:
  - params: gold/probe set version, parser, preprocessor and prompt versions, chunk strategy, embedding model, K, query mode, git commit;
  - metrics: overall and per slice;
  - artifacts: per-probe / per-region JSONL, confusion matrix, summary table.
- Gold and probe sets are versioned CSVs in `sdg-evals`, loaded into Delta. Updating the gold set bumps its version, so an old and a new run are only compared when they use the same set.

### Promotion gate

A change to the parser, preprocessor, chunking, embedding or retrieval filter reaches prod only after passing the gate. Thresholds live in `gating-thresholds.json`, next to the harness, so changing a threshold is itself a reviewed change.

```mermaid
flowchart LR
  PR[PR: preprocessor / chunking /<br/>retrieval change] --> FG{Fast gate<br/>2-5% stratified subset<br/>+ anchor docs}
  FG -- fail --> X[Block + per-region diff<br/>in MLflow]
  FG -- pass --> FULL{Full gate<br/>whole gold set + probe set<br/>candidate vs baseline}
  FULL -- fail --> X
  FULL -- pass --> QA[QA backfill sample<br/>DQ checks green]
  QA --> FLAG[Enable in prod behind flag<br/>legacy index as fallback]
  FLAG --> MON[Daily rotating regression<br/>weekly full run]
  MON -- drift --> X
```

| Gate check | Threshold | Why this check |
|---|---|---|
| Attribution accuracy (all) | ≥ 90% and not below baseline minus 1 pt | Overall quality floor |
| Core equipment sections | ≥ 95% | These sections drive risk findings |
| **Misattribution** | **≤ 2% (hard block)** | Wrong-unit evidence is the costliest error. It is gated separately so a gain in accuracy can't hide it. |
| Any slice vs baseline | No drop > 2 pts | Stops "better on average, worse on Generators" |
| Retrieval `filter_match` | ≥ 0.98 | Only the requested unit's evidence is returned |
| Retrieval `doc_recall@10` | ≥ baseline | No loss of coverage |
| p95 retrieval latency | ≤ 5 s | Agent UX budget |
| Anchor docs (known past bugs) | 100% pass | Old bugs can't come back |

**Regression cadence:** fast gate on every PR (minutes) · daily 15–30% rotating sample + anchors · weekly full gold set · **bug → gold row**: every field-reported misattribution is labeled and added to the anchors.

### What value the evals added

| Without evals | With evals | Business effect |
|---|---|---|
| "The new preprocessor looks better on the PDFs I tried" | 79% → 92% on a stratified set, with the error type split into wrong vs unknown | A number stakeholders could sign off on. v2 was approved for prod on evidence. |
| Accuracy and misattribution mixed into one score | Misattribution tracked and gated on its own | The design became **precision-first**: we chose "unknown" over "wrong", which protects customer-facing recommendations. |
| Fixes for one layout quietly break another | Per-slice checks + anchor docs | Fixes for unnumbered headings and same-type multi-unit docs shipped without breaking single-equipment docs. |
| Retrieval knobs set by guesswork | K sweep showed no gain beyond K=10 with the current filter | K fixed at 10: no extra tokens or latency for zero recall gain. |
| "Add shared regions, more context is better" | No doc-recall gain, and fidelity dropped to 0.85–0.98 | Change **held back**. We avoided adding noise to every risk assessment. |
| "Retrieval finds the right document, so it's fine" | Cited-page hit ≈ 0.04, and several misses were one page off | Pointed at the real next fix (page attribution at chunk boundaries + re-ranking) instead of swapping the embedding model. |
| Post-prod report: "section missing from chunks" | Replay against the saved parse + scorer | Showed the content was present and the check itself was wrong. No hotfix, no re-backfill. |

**In one line:** the evals turned quality from an opinion into a release gate. That let us ship faster with less risk, and showed us which change to make next.

### Soundbite: accuracy, adoption, reuse

> "The redesign paid off across three dimensions — accuracy, adoption and reuse.
>
> On my evaluated sample, equipment attribution improved from **79% to 92%**, reaching **96% in core equipment sections**, while misattributed noise fell **below 1.5%**. That mattered because an engineer searching for a specific generator or turbine could find evidence associated with the right equipment, rather than risk basing an assessment on another unit's findings.
>
> **Adoption:** the same retriever now serves both the risk-assessment flow and the Q&A agent, behind flags, with the legacy index as a safety net — so teams switched without a cutover weekend.
>
> **Reuse:** the eval harness (MLflow, gold set, promotion gates) was reused for the TIL extraction evals, and the region-metadata cascade follows the same pattern as our document-preprocessing service — one pattern, several products."

**Likely follow-ups and short answers:**
- *"Who labeled, and how did you check the labels?"* — DS labeled, field SME reviewed a sample; disagreements became labeling rules.
- *"Why not LLM-as-judge?"* — Fine for fluency, weak for "is this serial correct". Kept it for answer-quality evals only.
- *"Is 400 regions enough?"* — Enough to see a 13-pt shift with confidence on the main slices; thin on rare layouts, which is why every field bug becomes a new gold row.

---

## Infrastructure view

| Layer | Component | Notes / hardening |
|---|---|---|
| Ingest compute | Databricks serverless jobs (Asset Bundles, `dev`/`qa`/`prod` targets) | Daily incremental job at 06:00. Separate backfill jobs for P1 and P2 run in parallel (P1 `MERGE`s metadata columns, P2 `UPDATE`s chunk columns, so they don't conflict). DQ validation is a **separate job** so a data-quality failure doesn't turn ingestion red. |
| Storage | UC Volumes (bronze) → Delta Silver `ai_sot_*` → Gold `ai_std_con_*` | Chunk IDs are deterministic (`md5(doc_id+idx)`), so re-ingestion is a `MERGE`, not an append. |
| Retrieval | Mosaic AI Vector Search endpoint `pw-ser-sdg-vector-search` | HYBRID queries. TRIGGERED sync. |
| LLM | LiteLLM gateway | Central keys, quotas and model routing. Ingest and agents share it. |
| App | ECS Fargate services behind ALB with PingID OIDC. nginx routes to data-service and qna-agent. | The orchestrator (LangGraph) runs the risk-eval, narrative and event-history agents. DynamoDB (on-demand) holds execution state and checkpoints. |
| Network | data-service → Databricks through Naksha SQL proxy (API Gateway), plus the VS REST API | **Gaps I'd close:** move the workspace token to Secrets Manager or OAuth M2M, remove `verify=False` from the older VS call path, and switch the readiness SQL from `sql_literal` escaping to bound parameters. |
| Observability | `fsr_run_log` (P1 and P2 per batch), `fsr_data_quality_log` (39+ checks, `failure_category`) | Next: alert on completed docs without map rows, index staleness, and p95 retrieval latency. |

---

## Business value — one ingestion, many consumers

The key architecture choice for the business: **every stage writes a durable, governed asset** instead of throwing away its output after one step. Each asset then serves more than one use case.

```mermaid
flowchart LR
  subgraph ASSETS["Persisted FSR assets · Unity Catalog"]
    R[(Raw PDFs<br/>UC Volumes, immutable)]
    P[(Parsed text artifact<br/>parser version tagged)]
    M[(Metadata + summary<br/>fsr_metadata_v2)]
    E[(Equipment map<br/>doc x ESN)]
    C[(Chunks + embeddings<br/>+ vector index)]
  end

  R --> U1[Citation: open the source PDF<br/>at the cited page]
  R --> U2[Parser bake-offs<br/>Textract / AI Parser on the same files]
  P --> U3[Re-chunk / re-embed experiments<br/>P2 only, no PDF or LLM re-run]
  P --> U4[Support + RCA<br/>replay exactly what the pipeline saw]
  P --> U5[Gold-set labeling<br/>stable char offsets]
  M --> U6[FSR report listing +<br/>data readiness in URA]
  M --> U7[Cheap doc summaries for agents<br/>and other DS teams]
  E --> U6
  E --> U8[Secondary-ESN lookup<br/>Generator evidence on GT reports]
  C --> U9[Risk assessment agent<br/>RE + OE personas]
  C --> U10[Q&A agent<br/>query_fsr tool via MCP]
  C --> U11[Retrieval evals<br/>top-k sweeps in MLflow]
```

| Decision | Use cases it serves | Business value | Proof point |
|---|---|---|---|
| **Keep raw PDFs in UC Volumes as the immutable source** | Citations back to the source page, parser bake-offs, audits, full re-builds | Engineers can check the original page behind any claim, which builds trust. The source is never lost when the pipeline changes. | Volume is read-only for the pipeline. The QA environment reads the same volumes as dev (50,177 docs matched exactly). |
| **Persist the parsed text artifact** (`parsed_volume_path`, parser version) | Chunking, validation, re-chunk experiments, RCA, gold labeling | A chunking or embedding change re-runs only P2. That skips re-parsing and the LLM step (~217–359 docs/hr), so **days of P1 compute are skipped per experiment**. Support can replay the exact text the pipeline saw. | A post-prod issue about a "missing" section was closed in hours: the saved artifact showed the content was present, and the check itself was wrong. |
| **Metadata table as a product** (one row per doc, status, summary, provenance) | URA report listing, data-readiness counts, agents that need a quick doc overview, other DS teams | One source of truth for "what FSRs exist for this unit and are they ready?". Agents can read a summary instead of pulling many chunks, which saves tokens and time. | Readiness and report listing both run on plain SQL. No vector search is needed. |
| **Equipment map table** (doc × ESN, active flag) | Readiness, retrieval gate, fleet/train analysis | Generator work filed under a GT report becomes findable from the Generator ESN, which unlocks evidence for about 17% of affected units. | Train-expansion study: 84 of 500 GT units rescued from zero FSRs. |
| **Chunks + index with chunk-level ESN** | Risk assessment (RE + OE), Q&A agent, retrieval evals | Evidence is about the right machine, so recommendations and service scope match the real equipment. Fewer wrong-unit findings reach customer reviews. | Attribution 79% → 92%, core sections 96%, misattribution < 1.5%, filter fidelity 1.0. |
| **Governed access (UC grants)** | Multiple consumer groups in QA/prod | New teams get `SELECT` on curated tables with no copies and no new pipeline. Access is audited in one place. | QA grants `SELECT` to two consumer groups on the same tables. |
| **Status queue + flags + fallback** | Daily ingestion, backfill, app cutover | Re-runs continue instead of starting over, and users never saw a gap during the switch. | 5K-doc runs (~17h) resumable. Legacy index serves any ESN not yet in v2. |
| **Eval harness + promotion gates** | FSR attribution, FSR retrieval, TIL extraction | Changes ship on evidence, not opinion. The same harness served a second product (TIL). | Shared-region change held back based on eval data. |

**What I'd say:** "The main result wasn't a better embedding model. It was two choices. First, changing **where attribution happens**: moving the ESN decision to the chunk took attribution accuracy from 79% to 92% and cut wrong-unit noise below 1.5%. Second, **persisting every stage as a governed asset**: the raw PDFs, the parsed text, the metadata and the equipment map each serve several teams. Risk assessment, Q&A, report listing, evals and DS experiments all build on the same ingestion instead of each re-reading 22K PDFs. That's what made the platform cheap to change and easy to adopt."

---

## Honest gaps + next moves

1. **Page-level evidence hit is low (≈0.04)**. We get the right doc (0.94 recall) but often not the cited page. Next: re-ranker, overfetch then dedup, and a check on page attribution at chunk boundaries (several misses are off by one page).
2. **Shared regions**: the one-call OR filter is on hold until an eval shows it improves recall.
3. **Re-upload detection**: `file_last_modified` isn't tracked yet, so a PDF overwritten under the same ID keeps stale chunks.
4. **Retrieval probe set is small** (8 probes). Grow it with SME-labeled probes before tuning `top_k` or chunk size.

### If I rebuilt it AWS-native
S3 (raw PDFs) → Step Functions (with the status queue kept in DynamoDB or Aurora) → Textract layout plus the same deterministic preprocessor on Lambda/Fargate → Bedrock (Claude for admin fields, Titan/Cohere embeddings) → OpenSearch Serverless hybrid search (or Bedrock Knowledge Bases with metadata filters for a quick start) → Lake Formation for governance. **The design wouldn't change**: region-level attribution, a readiness gate, precision-first filters, and a flagged cutover. Only the services behind it would.
