# FSR v2 Evals Work Tracker

Last updated: 2026-08-05

## Scope

This tracker is for FSR v2 evals only.
Focus areas:
- 1) Top-k retrieval evals
- 2) ESN -> equipment-type mapping evals

## Working mode

- We work step by step.
- After each change, pause for review.
- No commit/push unless explicitly approved.

## Status legend

- [ ] Not started
- [~] In progress
- [x] Done
- [!] Blocked

## Phase A - Foundations

- [x] Create initial design notes for MLflow/model serving + eval approach
  - Ref: 2-FSR-v2/evals/mlflow-model-serving-design-notes.md
- [x] Clarify probe/weak-label vs gold-set usage
- [x] Add larger-corpus regression strategy
- [~] Confirm final repo split strategy (code repo vs sdg-evals)
  - Current decision: hybrid (logic in code repo, datasets/reports in sdg-evals)

## Phase B - Retrieval validation cleanup + replacement

- [x] Create consolidated retrieval validation notebook (V2 index only)
  - Ref: pw_sdg_ai_ser_repo/validation/fsr_v2/nb_fsr_v2_retrieval.py
- [x] Review and approve consolidated notebook behavior
- [x] Align retrieval notebook with app retrieval behavior
  - Added QUERY_MODE (hybrid/vector), default=hybrid
  - Added metadata_status='completed' in retrieval eligibility gate
- [x] Delete stale notebook: validation/fsr_v2/retrieval/nb_fsr_v2_retrieval_uc1.py
- [x] Delete stale notebook: validation/fsr_v2/retrieval/nb_fsr_v2_retrieval_uc2_current.py
- [x] Delete stale notebook: validation/fsr_v2/retrieval/nb_fsr_v2_retrieval_uc2_future.py
- [x] Update/remove stale workflow: workflows/fsr_v2/pw_sdg_fsr_v2_p4_validation.yml
- [x] Validate that workflow points to consolidated notebook only

## Phase C - Top-k eval implementation (Point 1)

- [x] Define fixed probe/weak-label dataset schema and storage location
  - `sdg-evals/fsr/v2-retrieval-eval/probe-set-template.csv`
- [x] Prepare first probe set (small) for dry-run
  - 3 starter probes seeded in `sdg-evals/fsr/v2-retrieval-eval/probe-set-template.csv`
- [x] Build retrieval eval runner (k sweep: 5, 10, 20, 40)
  - `sdg-evals/fsr/notebooks/nb_fsr_v2_topk_eval.py`
- [~] Run HYBRID vs vector comparison on the same probe set and log delta report
  - Comparison and delta report generation implemented in notebook; run pending in Databricks
- [x] Log run params/metrics/artifacts to MLflow
  - Implemented via `fsr/harness.py` (`run_eval_detailed`) with per-probe + summary artifacts
- [~] Define gating thresholds for retrieval metrics
  - Draft in `sdg-evals/fsr/v2-retrieval-eval/gating-thresholds.json`; final sign-off pending
- [~] Run baseline vs candidate comparison
  - Baseline/candidate flow implemented as mode+k sweep; execution results pending
- [ ] Publish first retrieval eval summary report

## Phase D - ESN mapping eval implementation (Point 2)

- [x] Define gold dataset schema (region/chunk-level)
  - Ref: 2-FSR-v2/evals/mapping-gold-set-template.csv
- [ ] Build gold set sampling strategy (stratified)
- [~] Create first labeled gold set batch
  - 4 simple seed candidates prepared with initial region offsets
- [~] Build ESN/equipment attribution eval runner
  - Starter scorer now supports gold validation, optional predictions merge, row-level export, and per-equipment-type slice metrics
- [ ] Log mapping metrics and confusion matrix artifacts to MLflow
- [ ] Define pass/fail thresholds by critical slice
- [ ] Run baseline vs candidate comparison
- [ ] Publish first mapping eval summary report

## Phase E - Regression automation

- [ ] Implement fast gate run (2-5% stratified subset)
- [ ] Implement daily rotating regression run (15-30% + anchor set)
- [ ] Implement weekly full-corpus benchmark run
- [ ] Add MLflow dashboard/query for trend tracking
- [ ] Add rollback recommendation logic from thresholds

## Open decisions

- [ ] Final location of probe and gold datasets in sdg-evals (paths/naming)
- [ ] Final experiment naming conventions in MLflow
- [ ] Final threshold values for promotion gates
- [ ] Who signs off each phase (DS, data eng, product)

## Standup summary (today)

- Built the Top-k retrieval eval foundation: consolidated validation path, aligned hybrid/vector behavior, and finalized probe + scoring spec.
- Built the ESN -> equipment-type mapping eval foundation: stable gold-label schema and starter runner in sdg-evals.
- Created a clean baseline for Phase C/Phase D comparisons so we can now move from setup to measurable runs.
- Need help from Xujin: review and confirm the first gold-label batch (region offsets + labeling criteria) before we scale labeling and lock thresholds.

## Progress log

- 2026-08-04: Created tracker.
- 2026-08-04: Added FSR-only eval notes with dataset guidance.
- 2026-08-04: Added larger-corpus regression strategy.
- 2026-08-04: Added consolidated retrieval validation notebook for V2 index.
- 2026-08-04: Approved retrieval notebook behavior; aligned with app-style HYBRID mode and metadata_status completed gate.
- 2026-08-04: Removed stale retrieval notebooks (UC1/UC2 current/UC2 future).
- 2026-08-04: Aligned FSR validation workflow parameters to consolidated notebook inputs.
- 2026-08-04: Completed workflow-to-notebook parameter mapping check; no missing widget parameters.
- 2026-08-04: Committed and pushed retrieval cleanup/alignment checkpoint to pw_sdg_ai_ser_repo.
  - Branch: fsr_v2
  - Commit: 10e6863
- 2026-08-04: Started Phase D by creating mapping gold-set schema template.
- 2026-08-04: Created retrieval probe template and retrieval scoring spec for Phase C baseline metrics.
- 2026-08-04: Initialized `sdg-evals/fsr/v2-mapping-eval` (gold template, validator runner, README) and pushed to `main`.
  - Commits: `e9a2b16`, `572c998`
- 2026-08-05: Prepared first simple Phase D review batch with 4 single-ESN candidates and seed region offsets.
- 2026-08-05: Added `sdg-evals/fsr/notebooks/nb_fsr_v2_retrieval.py` so retrieval validation also lives in the eval repo.
- 2026-08-05: Extended Phase D starter with predictions template, exact-match scorer, row-level export, and per-equipment-type slice metrics.
- 2026-08-05: Committed and pushed latest `sdg-evals` Phase C/Phase D scaffolding to `main`.
  - Commit: `2b18df4`
- 2026-08-05: Implemented Phase C retrieval eval execution path in `sdg-evals`:
  - Fixed local `fsr` import paths in harness notebooks/modules.
  - Added hybrid/vector support and configurable ESN/equipment/text fields in retriever.
  - Added probe CSV loader and weak-label scoring metrics (doc hit/recall, evidence terms, filter fidelity).
  - Added top-k sweep notebook (`nb_fsr_v2_topk_eval.py`) with hybrid-vs-vector delta summary.
  - Added draft threshold config (`gating-thresholds.json`).

## Next step (single change)

- Run `nb_fsr_v2_topk_eval.py` once in Databricks on the starter probe set and publish the first hybrid-vs-vector summary table with run IDs.
