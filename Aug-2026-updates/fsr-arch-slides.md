# FSR Pipeline — Architecture Series Slides
> Aug 2026

---

## Slide 1 — The Problem

**Why this matters**

Outage planning for power-plant equipment runs roughly two years ahead. Taking a unit offline affects the whole grid — missed risk signals mean unplanned downtime, safety exposure, and broken service commitments.

**What SMEs are dealing with today**

- Assets running up to 40 years. Decades of field service reports across scattered sources.
- Risk indicators live in unstructured PDFs — mixed scan quality, no standard format.
- Today, SMEs do this risk assessment manually, report by report.

**The data scope**

MVP: ~18K FSR documents from 2010 onward, built to scale to the full multi-decade corpus and additional unit types.

**Why RAG**

The question isn't keyword search — it's "what has historically gone wrong with this specific unit?" That requires semantic retrieval over long-tail, domain-specific text. RAG grounds the LLM in the actual historical record rather than relying on model pretraining, and it keeps the evidence traceable back to source documents.

---

## Slide 2 — Pipeline Overview

**Ingestion → Processing → Chunking & Embedding → Vector Index → LLM Response**

```
PDFs (Unity Catalog Volume)
    │
    ▼
[P1: Metadata Extraction]
    Parse PDF text
    Deterministic + LLM-based preprocessing
    ESN / equipment-type attribution per region
    Store: metadata table + document-equipment map
    │
    ▼
[P2: Chunking & Embedding]
    Chunk text by document structure
    Tag each chunk with ESN + equipment type
    Embed (3072-dim vectors)
    Store: chunk table
    │
    ▼
[P3: Vector Index Sync]
    Delta table → Databricks Vector Search index
    │
    ▼
[Retrieval + Inference]
    Query → vector search → top-k relevant chunks
    Chunks + user query → LLM prompt
    Output: risk analysis, flagged FSRs, data readiness signal
```

The pipeline runs as a scheduled Databricks workflow (daily incremental). Backfill and incremental share the same code path — only the work-set size differs.

---

## Slide 3 — Parsing: Getting ESN Attribution Right

**The challenge**

FSR documents don't follow a fixed structure. One report can cover multiple equipment types — a Gas Turbine and a Generator on the same PDF, each with its own ESN. Before this work, chunks were tagged with whatever ESN appeared first in the document, causing two failures:

- Retrieval miss: querying a Generator ESN returned zero results because all chunks were labeled with the GT ESN (~17% of cross-ESN queries affected).
- Wrong label: Generator content tagged as Gas Turbine → LLM produced the wrong risk recommendation.

**How it's solved**

A two-stage preprocessing flow:

1. **Deterministic pass** — parse the document, build a canonical region inventory (section headers, character offsets, region IDs). Run rule-based attribution on every region. Most documents resolve cleanly here.

2. **LLM pass for ambiguous regions** — regions the deterministic pass can't confidently assign are sent to the LLM with their region ID and text. The LLM returns attribution decisions keyed to region IDs (no free-form offset generation). IBAT equipment hierarchy lookup fills any remaining gaps.

The key design choice: one authoritative region map, not two independent maps merged by offset. The deterministic pass owns segmentation; the LLM pass owns ambiguity resolution. This avoids the hardest merge problem.

**Result**

Each document produces a merged region list with per-region ESN + equipment type, and provenance tracking (what assigned each region and why). This feeds directly into chunk attribution in P2.

---

## Slide 4 — Chunking & Retrieval: Per-Chunk Equipment Attribution

**The challenge**

Retrieving the right evidence for a specific unit means filtering at the chunk level — not just the document level. A single document has 20+ chunks, and only a subset are relevant to a given equipment type.

**How it's solved**

Each chunk inherits attribution from the preprocessing regions:

- `primary_esn` / `primary_equip_type` — determined by max character-offset overlap between the chunk boundary and the preprocessor regions. One ESN per chunk, deterministic.
- `active_esns` — all ESNs mentioned anywhere within the chunk's span, stored as a pipe-delimited field. Supports broader cross-ESN queries without losing precision on the primary tag.

This enables equipment-type-scoped retrieval at query time:

```
Query: "What issues has this Generator ESN seen?"
→ Vector search + filter: primary_equip_type = 'generator' AND primary_esn = '<ESN>'
→ Returns only chunks attributed to that unit
```

A document-equipment map table is also maintained as a fast lookup layer for upstream services.

**Result**

Retrieval precision improved significantly for multi-equipment documents. The 17% cross-ESN miss rate is addressed at the data layer, not by retrieval heuristics.

---

## Slide 5 — Evaluation: MLflow-Tracked Pipeline Metrics

**The ask**

Changes to the pipeline — new parser, different embedding model, tighter chunking — should be validated before they reach production. Eyeballing output doesn't scale.

**How evals are structured**

A lightweight eval framework using MLflow as the experiment system:

- Fixed probe sets per eval type (same probes across baseline and candidate runs, ensuring fair comparison)
- Key metric for retrieval: `avg_retrieved_vs_exists_ratio` — for each probe ESN, how many of the known FSRs are actually retrieved, averaged across the probe set
- Secondary metrics: retrieved count, probe stability (success/failure rate per run)

**Workflow**

```
Baseline run (current config) → log params + metrics → MLflow run A
Candidate run (one knob changed) → log params + metrics → MLflow run B
Compare A vs B in MLflow UI → promote or reject
```

Artifacts (summary and detail reports) are stored per run, giving a full audit trail of what changed and what moved.

**Current state**

Evals are notebook-driven with MLflow logging. The path to scheduled regression runs is defined — same eval, promoted to a Databricks job with its own SLO.

---

## Slide 6 — Model Serving: Versioned RAG Endpoint

**The customer ask**

"We want to change methods in the RAG pipeline — swap the chunking strategy, update the embedding model, try a different prompt — and see the impact without a risky production cutover."

**How this is designed**

The pipeline exposes all tunable choices as named runtime knobs: parser version, embedding model, embedding dimension, chunking strategy, processor version, merge strategy. Each configuration is a specific set of knob values.

A versioned serving pattern on Databricks makes this auditable and switchable:

1. The RAG chain (retrieval + prompt assembly + LLM call) is registered as an MLflow PyFunc model in Unity Catalog.
2. Each pipeline configuration variant is logged as a separate MLflow run with its eval metrics attached.
3. Promoted versions are deployed to a Databricks Model Serving endpoint.
4. The endpoint supports traffic splitting — new version takes a percentage of traffic alongside the current production version (champion/challenger). Metrics from both are tracked in parallel before full cutover.

This means: changing a retrieval strategy or embedding model produces a versioned model artifact, backed by eval metrics, deployed with zero-downtime traffic shifting. The customer can see exactly what changed, when, and what the measured impact was.

**TBD**

- Confirm which parts of the chain are registered as the MLflow model boundary (retrieval-only vs full chain)
- Traffic split granularity and rollback SLO in the serving config

---

## Slide 7 — What's Next

The pipeline is production-ready for the MVP scope. Active work areas:

**Re-upload detection**
If a PDF is replaced in the volume with corrected content, the pipeline currently keeps the old metadata and chunks. Adding `file_last_modified` tracking to the discovery step closes this gap — corrected documents will be reprocessed automatically.

**Full LLM preprocessor rollout**
The two-stage preprocessing design is fully specified. The remaining work is integrating LLM-based ambiguous-region resolution into the production P1 flow, which handles the tail of documents where deterministic attribution falls short.

**Scheduled eval regression runs**
Evals are currently run on-demand before changes. The next step is promoting them to a scheduled Databricks job — continuous coverage so regressions surface before they reach users.

**Corpus expansion**
MVP covers ~18K reports from 2010 onward. The pipeline is designed to scale — expanding to the full multi-decade corpus and additional unit types (steam turbines, cooling systems) is on the roadmap.

---
