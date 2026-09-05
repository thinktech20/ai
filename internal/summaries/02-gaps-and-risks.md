# 02 — Gaps and Risks

**Status:** Draft — pending review

---

## Overview

This document captures known gaps in the current FSR retrieval POC. These need to be resolved before MVP2 production build. Gaps are grouped by source — some were identified in the team discussion, others surfaced from the code review.

---

## Gaps Identified in Team Discussion (Apr-7)

### Gap 1 — Document Type Mixing (Most Critical)

**What:** The Databricks Volume contains all PDF types — FSRs, TILs, technical manuals, Engineering Reports. The processing pipeline processes every PDF without knowing its type. Non-FSR documents that mention an ESN get tagged to that unit and end up in the FSR chunk table.

**Impact:** At query time, the retrieval pipeline surfaces TIL guidance, manual procedures, and unrelated technical content mixed in with real FSR service findings. The LLM receives confused context and may present procedural instructions as evidence of a service event.

**Noted in review:** *"It's not FSR, it's TIL or something else — you cannot treat them as FSR."*

**Example:** A 19-page TIL with an ESN mentioned was tagged to that unit and chunked alongside 800-page real FSR documents.

**Root cause:** PDF filenames in the Volume are bare GUIDs — no metadata in the filename. First-page scraping extracts metadata fields but does not classify document type.

**Fix options:**
- [ ] Option A: LLM classification on first-page content ("is this FSR, TIL, or manual?")
- [ ] Option B: Document type registry maintained upstream (linked to Volume GUIDs)
- [ ] Option C: Heuristic filter (real FSRs are long — TILs are 10-20 pages)
- [ ] Regardless: add `document_type` column to chunk table; filter in `query_fsr`

---

### Gap 2 — SOT Completeness

**What:** The `fsr_pdf_ref` SOT table has 1,812 PDFs with null ESN. Some ESNs in the 30-ESN GT set have 0 SOT links even though reports exist.

**Impact:** Without the LLM-based document discovery, ~1,800 PDFs are invisible to any unit's retrieval pipeline. With the LLM approach (Gap 3), they are recovered — but with quality caveats.

**Root cause:** SOT links depend on a registration step (field engineer or automated system linking PDF → ESN in FieldVision). If that step is missed, the PDF exists in the Volume but is not linked.

**Fix:** Understand the SOT build process with the data team. Determine whether null-ESN PDFs are recoverable or structurally unlinked.

---

### Gap 3 — LLM-Discovered ESN Links Not Validated

**What:** The ESN identifier pipeline uses an LLM to link PDFs to ESNs based on mention frequency (≥1 mention, ≥10% of all ESN mentions). These 967 recovered links have never been validated against ground truth.

**Impact:** False positives — documents tagged to a unit because they mention that ESN in passing (e.g. a TIL referencing a known problem unit). Combined with Gap 1, some LLM-discovered links are non-FSR documents. Wrong documents are harder to catch than missing ones.

**Fix:**
- [ ] Sample validation: manually inspect 20-30 LLM-only links
- [ ] Surface `esn_assignment_source` in API response so callers can filter

---

### Gap 4 — Production Tables Do Not Exist

**What:** All current work runs against the experiment catalog (`main.gp_services_sdg_poc`). The production Unity Catalog tables (`vaid.*`) have not been created.

**Impact:** Blocks any production deployment. Schema decisions (document_type column, ESN validation flags) must be finalized before production table creation.

**Fix:** Coordinate with the Databricks architect team on production table creation and schema sign-off.

---

### Gap 5 — No Document Type Segmentation for Retrieval

**What:** The Q&A agent needs to retrieve from multiple document types with different semantics: FSRs (service event facts), ERs (structured event reports), TILs (technical instructions), manuals (procedural guidelines). Currently all types are mixed in one chunk table.

**Impact:** The agent cannot target FSR content for factual service history questions vs TIL content for procedural guidance. Retrieval results conflate the two.

**Fix:** Each document type should be segmented and labeled. Either separate VS indexes per type, or a `document_type` filter on a single index. [Approach to be decided — see Open Questions]

---

## Gaps from DS Pipeline Review (Apr-9)

### Gap 6 — Embedding Model Mismatch (Critical)

**What:** The full-corpus `fsr_pipeline` uses `databricks-gte-large-en` (768-dim) at ingest time (VS auto-embed) and `azure-text-embedding-3-large-1` (3072-dim) at query time (LiteLLM). These are incompatible vector spaces.

**Impact:** The dense retrieval leg compares vectors that were never trained against each other. Cosine similarity scores are meaningless. The eval results from `fsr_pipeline` are unreliable. The GT-direct pipeline (`fsr_pipeline_gt_direct`) uses LiteLLM at both ends and is the correct baseline.

**Fix:** Decide on production embedding model and ensure ingest and query use the same model. Options: (a) LiteLLM at both ends (as in GT-direct), or (b) Databricks-managed GTE at both ends. See Open Questions doc.

---

### Gap 7 — Reranking Hurts Top-1 Recall

**What:** Eval data shows reranking reduces R@1 from 0.432 → 0.303 (~30% drop). The current spec mandates unconditional reranking.

**Impact:** If the spec is followed as-is, top-1 retrieval performance will be worse than without reranking. This affects RE flow which needs a single best chunk.

**Fix:** Decision needed — should reranking be optional/configurable rather than mandatory? See Open Questions doc.

---

### Gap 8 — Metadata Extraction Output Not Connected to Retrieval

**What:** The `fsr_scraped_file_mapping_ref` table is populated (by the 3-stage scraping pipeline) but is not read by any retrieval code. Step 6 of the spec (3-view metadata join at query time) is unbuilt in the DS pipeline.

**Impact:** Query results lack the 15-field structured metadata (event type, outage dates, project IDs, equipment info) that the LLM needs to reason about service history. This step is deferred to the service wrapper.

**Fix:**
- [ ] Confirm scraping output is stable enough to wire up
- [ ] Resolve catalog promotion: table is in `main.*`, needs to reach `vgpd.*` for production
- [ ] Service wrapper must implement Steps 5–6 (chunk hydration + 3-view join)

---

## Risk Summary

| Gap | Severity | Blocks |
|---|---|---|
| Gap 1 — Document type mixing | High | Query correctness |
| Gap 6 — Embedding mismatch | High | Dense retrieval reliability |
| Gap 4 — Production tables don't exist | High | Any production deployment |
| Gap 7 — Reranking hurts R@1 | Medium | Spec decision needed |
| Gap 8 — Metadata join unbuilt | Medium | Full query spec compliance |
| Gap 2 — SOT completeness | Medium | Document coverage |
| Gap 3 — LLM links unvalidated | Medium | Retrieval precision |
| Gap 5 — No doc type segmentation | Medium | Multi-doc-type Q&A |

---

## [PLACEHOLDER] — Items to Validate

- [ ] Gap 1: Which fix option for document type classification? [Decision required]
- [ ] Gap 6: Which embedding model for production?
- [ ] Gap 7: Is reranking mandatory or configurable?
- [ ] Gap 8: Who owns the catalog promotion and Step 6 implementation?
