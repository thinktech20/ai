# POC: hands-on with FSR docs

Companion to [learning-plan.md](learning-plan.md). The plan covers *what* to learn; this note is the *how* — get hands‑on by re‑doing the core RAG steps on real FSR documents in Databricks dev.

> **FSR prod work is the reference, not the thing to rebuild.** Use `pw_sdg_ai_ser_repo` (bronze/silver/gold), `internal/06-pipeline-code-analysis.md`, and the prod‑ops/backfill experience in `fsr-prod-ops/` and `implementation/` to see how each step is actually done in production. Then build a simpler version myself to learn.

## Loop to run

`parse → chunk → embed → index → retrieve → inspect`, plus a metadata extraction step (ESN/serial, model, dates, etc.).

- Run in **Databricks dev**, in a personal/scratch path.
- Free to swap embedding models, chunking strategies, vector libs to learn trade‑offs.
- Out of scope: touching prod pipeline code, prod Vector Search indexes, or shared catalog tables.

## Sample docs

- Start with **1 clean text‑based FSR** to get the loop working.
- Expand to a few FSRs of different shapes as needed: text‑heavy, table/form, scanned/OCR, multi‑serial.
- Reuse what's already in `FSR/ESN-resolution/test-pdfs/` and `fsr-prod-ops/user-reported-issues/user-shared-docs/` before pulling new ones from the volume.

## Outputs

- A runnable Databricks notebook for the loop above (re‑runnable on a different PDF).
- Notes back into [learning-plan.md](learning-plan.md) under each section as concepts get clearer.
- Small comparison sweeps where useful: chunk size/overlap, 2–3 embedding models, top‑k, metadata extraction approaches (regex vs. LLM vs. hybrid).
- Aha‑moments captured for the eventual Slalom presentation.
