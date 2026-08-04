# FSR Architecture Slides — Presenter Notes
> Companion to fsr-arch-slides.md | Fill in details before presentation

---

## Slide 1 — The Problem

- Business stakes and why outage planning timing matters
- Manual SME effort — quantify if possible
- Data scale and quality challenges
- Why the MVP scope is 18K and what "designed to scale" means in practice

---

## Slide 2 — Pipeline Overview

- Walk through the step-wise diagram
- Highlight that backfill and incremental are the same code path
- Call out Databricks-specific components (Unity Catalog Volumes, Vector Search, serverless compute)
- Mention daily schedule and job topology

---

## Slide 3 — Parsing

- The two failure modes from multi-equipment FSRs (retrieval miss + wrong label) — use the 17% stat
- Walk through the two-stage flow: deterministic first, LLM only for ambiguous regions
- The one-canonical-region-map design decision and why it matters
- What the output looks like: region list with ESN + equipment type + provenance

---

## Slide 4 — Chunking & Retrieval

- How region attribution carries forward from P1 into P2
- Explain `primary_esn` vs `active_esns` and when each is used at query time
- Show the retrieval filter pattern (equipment-type-scoped query)
- Before/after: what retrieval looked like without per-chunk attribution

---

## Slide 5 — Evaluation Metrics

- What a "probe set" is and why fixed probes matter for fair comparison
- Walk through `avg_retrieved_vs_exists_ratio` with a concrete example
- How a baseline vs candidate comparison run works in practice
- MLflow artifacts — what gets stored per run and how to navigate it
- Current mode (notebook-driven) and the path to scheduled regression runs

---

## Slide 6 — Model Serving

**Why we're doing this (Vince's ask):**
Register RAG pipeline as a versioned MLflow model with eval-gated promotion — log each pipeline configuration (parser, chunker, embedding model) as an MLflow run with retrieval metrics attached at run time. Register promoted configs as versioned models in Unity Catalog — each version maps to a specific set of knob values and its measured accuracy. Deploy to a Databricks Model Serving endpoint; new versions run alongside production with traffic splitting until metrics confirm parity or improvement. Outcome: any parameter change produces a versioned artifact with metrics attached, so the team can show exactly what changed, what moved, and when the cutover happened.

**Points to prep:**
- What the knob system looks like today (runtime params wired through the workflow)
- MLflow PyFunc model boundary — retrieval only vs full chain (confirm before presenting)
- What "champion/challenger" means in a serving endpoint context
- Traffic split granularity and rollback story (TBD — confirm before presenting)

---

## Slide 7 — What's Next

- Re-upload detection — the gap it closes and how `file_last_modified` fixes it
- LLM preprocessor rollout — current state vs what's left
- Scheduled eval runs — what the promotion from notebook to job looks like
- Corpus expansion — unit types and timeline

---
