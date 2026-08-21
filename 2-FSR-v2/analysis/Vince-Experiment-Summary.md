# Vince's FSR Retrieval Fix Experiment — Summary

**Date:** 2026-07-13  
**Status:** POC validation in progress (end of week)  
**Source docs:** `sdg-autotest/docs/FSR_Retrieval_Fix_Plan.md`, `ds-guru/FSR_PREPROCESSOR.md`, `FSR-v2/analysis/Vince-POC/ASSESSMENT_REPORT_*.md`

---

## The Problem

Multi-equipment FSRs (Gas Turbine + Generator on same document) have **two failure modes**:

1. **Retrieval miss** — User queries Generator ESN (e.g., `338X447`), but chunks are tagged with GT ESN → zero results. Affects ~17% of cross-ESN queries.
2. **Wrong label** — Generator content (stator, rotor, field) is labeled "Gas Turbine" because the FSR listed the GT ESN first → LLM risk assessment confuses equipment type → wrong remediation recommendation.

**Impact:** 7 confirmed failing documents show 82.6% baseline accuracy on equipment tagging.

---

## The Solution (Vince's Experiment)

A **~350-line Python preprocessor** that runs once per PDF **before** ingestion:

- Pure regex/pattern matching — no AI, no API calls, runs < 1 second per document.
- Scans page-1 for ESN labels + section headers (`## GENERATOR (337X766)`, etc.).
- Maps each page/chunk to the correct equipment by:
  - Identifying section header boundaries (Gas Turbine vs Generator regions).
  - Detecting field labels (`Gas Turbine ESN:`, `Generator ESN:`).
  - Falling back to GE form numbers and keyword density if no clear boundary.
- Output: metadata hints + per-section region tags → chunks inherit the correct equipment label.

---

## Three Fixes to the Same Function (Path to 93–95% Accuracy)

All fixes are patches to the **same 350-line preprocessor** — not three separate systems.

### Fix 1 — Default ESN in fallback (VALIDATED ✓)

**Problem:** When no section header found, preprocessor picks first ESN alphabetically. Generator ESN (338X447) > GT ESN (298250) → wrongly tags Gen pages as GT.

**Fix:** Use doc-level primary ESN instead.

**Result:** **+4.0 pp** (82.6% → 86.7%), zero regressions. **Verified on 7 test FSRs.**

### Fix 2 — Nested header detection (IN PROGRESS)

**Problem:** Some reports have embedded `## GENERATOR (...)` mid-document without a top-level header in TOC. Preprocessor misses it → all 145 Gen pages stay labeled GT.

**Fix:** Extend boundary-detection logic to handle nested headers.

**Result:** Estimated **+4–6 pp**.

### Fix 3 — Content override (NOT STARTED)

**Problem:** Chunk near a boundary contradicts its region label (e.g., 5+ generator keywords but labeled GT). Region tag always wins.

**Fix:** Override when content signal is overwhelming (5+ one side, 0 other).

**Result:** Estimated **+2–3 pp**.

---

## Iteration Results

| Iteration | Strategy | Accuracy | Note |
|---|---|---|---|
| Iter 1 | Recursive chunking (4KB, overlap 200) | **82.6%** | Baseline |
| Iter 2 | Recursive + Fix 1 applied | **86.7%** | Validated (+4.0 pp) |
| Iter 3 | Section-based chunking (no Fix 2/3) | **93.0%** | Page-range scorer; but includes chunking strategy change |

**Key finding:** Section-based chunking alone raises accuracy to 93% (page-range scorer), but exposes latent boundary issues. Fixes 2–3 are still needed for stable 93–95%.

---

## What the Fix Actually Is (For Deployment)

The fix is **not** a full re-ingestion or system rebuild:

- **NOT:** Re-ingest all documents, rebuild vector store, change embedding model, rewrite risk LLM.
- **YES:** Run validated preprocessor on affected FSRs → get page-range attributions → UPDATE `primary_equip_type` metadata on existing chunk rows.

**Scope:** ~458 multi-equipment FSRs in the corpus.  
**Risk:** Low — reversible UPDATE, not destructive.  
**Time:** Days (metadata update), not weeks (re-ingestion).

---

## Production Readiness (ds-guru App)

Vince's **SAGE UI tool** (ds-guru) is valuable for experimentation but not production-ready in current form. To go production:

- Production-grade sandbox: AST validation + child process + memory limits.
- Page-by-page ingest mode: handle 400+ page PDFs without loading entire PDF into memory.
- Non-developer UI: form-based preprocessor testing for operators.

---

## Next Steps

**By end of week (July 18):**
- Validate Fix 1 + Fix 2 on extended test set.
- Quantify content-override rule (Fix 3).
- Estimate deployment timeline.
- Measure regression on single-equipment (clean) FSRs.

**After POC:**
- Targeted metadata UPDATE on priority documents.
- Broader rollout if no regressions.
- (Optionally) productionize ds-guru UI for ongoing preprocessor tuning.

---

## References

- **FSR Retrieval Fix Plan:** `sdg-autotest/docs/FSR_Retrieval_Fix_Plan.md` (overall strategy, problem decomposition)
- **Preprocessor Code & Design:** `ds-guru/FSR_PREPROCESSOR.md` (sandboxed Python, contract, signal types)
- **Assessment Reports:**
  - Iter 1: `FSR-v2/analysis/Vince-POC/ASSESSMENT_REPORT_ITER1.md` — baseline 82.6%, error patterns
  - Iter 2: `ASSESSMENT_REPORT_ITER2.md` — Fix 1 validated, +4.0 pp
  - Iter 3: `ASSESSMENT_REPORT_ITER3.md` — section chunking + page-range scoring, 93.0% accuracy
