# FSR V2 Rollout Plan

## Problem

Multi-equipment FSRs (Gas Turbine + Generator on the same document) have two failure modes: **Retrieval miss** and **Wrong label**.

---

## Approach

### Iteration 1 — Preprocessor (DS Guru) for ESN-to-Equipment-Type Mapping

1. **Update FSR metadata extraction and chunking/vectorization pipeline** — [Madhurima / Tao]
   a - Metadata extraction: include preprocessor
   b - Chunking: add enriched ESN details to the `metadata` JSON column in the chunk table
   c - Build a standalone backfill job (separate orchestrator): updates records in the *existing* metadata and chunk tables (not v2 tables) for the 458 multi-ESN FSRs. Reuses the same tested stage files from the v2 pipeline (parsing, metadata_processor, enrichment) — different orchestrator, same logic, different target tables. No re-chunking/embedding unless chunk metadata needs updating.
      - TODO: decide if backfill needs Stage 2 (pdfplumber re-parse) or can read existing stored fields from old metadata table

2. **Update app to test from new tables (schema) in dev/qa.** [Abhinaya & Team]
   Once testing with the new tables is complete, the app should be able to switch back to the old tables.

3. **Have a validation plan** [Xujin & team] — compare against baseline and measure accuracy.
   Use sdg-test / ds-guru for this. The validation setup should be able to switch between new and old tables.

4. **Roll out and validate in Dev and QA** [Team]
   - a. Populate data into new tables: `fsr_metadata_v2`, `fsr_chunk_v2`, and `fsr_vs_index_v2`
   - b. Validate against the 7 confirmed failing documents and ESNs with known production issues
   - d. Validate the updates in the existing metadata and chunk tables
   - e. Run the update job for all 458 multi-equipment FSRs *(where is this list?)*
   - f. Run regression test for the updated 458 FSRs

5. **SME Validation in QA**

6. **Based on the results, decide the next knob/iteration.**

---

## Preprocessor

**Reference:** [Vince-Experiment-Summary.md](../analysis/Vince-Experiment-Summary.md)

Open Questions:
Golden set of data - we need to test against?

7- Vince + 5 ESN - Abhinaya (map to 30 or 40 FSR) +5 (Tao uploaded in drive)
458 -?