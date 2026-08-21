# FSR V2 Preprocessor RCA Plan

## Goal
Identify and fix section-header detection and parent flip-back tagging issues in the new preprocessor flow, using current code as source of truth.

## Confirmed Rule
If a subsection is tagged by subsection-specific context (for example, 2.6 Generator Mechanical Scope under Section 2 Turbine), then after that subsection ends, tagging must flip back to parent section context (for example, 2.7 Unit Rotor should revert to Turbine even without explicit Turbine keywords).

## Scope
In scope:
- Root cause analysis using current implementation.
- Output validation by running standalone preprocessor notebook.
- Code changes after RCA review.

Out of scope for now:
- Test-case design and test-suite expansion.
- Comparison against production outputs.

## Source of Truth
Primary:
- `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`
- `pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py`

Reference context:
- `2-FSR-v2/bug-preprocessor/redesign/root-cause-parent-inherit-bug.md`
- `2-FSR-v2/bug-preprocessor/redesign/proposed-design-changes.md`
- Recent commits from yesterday (reference only, not authoritative for behavior).

## Execution Plan With Review Gates

### Step 1: Plan Finalization (current step)
Actions:
- Record execution plan, rule lock, scope boundaries, and review gates.

Deliverable:
- This plan document.

Stop for review:
- Await your approval before starting RCA.

### Step 2: Root Cause Analysis (no code changes)
Actions:
- Read and map current section/tag state-flow in the two source files.
- Trace header detection and parent/subsection transition logic.
- Run notebook baseline output (before any fix):
  - `pw_sdg_ai_ser_repo/validation/fsr_v2/preprocessor/run-preprocessor-standalone.ipynb`
  - Start with target doc: `af693a98-1e5c-499d-aa10-cccc54885c64`
  - Save this as "before-fix" output for direct comparison later.
- Store results as separate files under a new folder:
  - `2-FSR-v2/bug-preprocessor/new-preprocessor-issues/analysis-output/`
  - For Step 2, at minimum one before-fix file for `af693a98-1e5c-499d-aa10-cccc54885c64`.

Deliverables:
- RCA note with exact failure point(s) and why previous change did not resolve this case.
- Per-document output files in `analysis-output` (with explicit before-fix capture for `af693a98-1e5c-499d-aa10-cccc54885c64`).

Step 2 findings to date:
- `af693a98-1e5c-499d-aa10-cccc54885c64` baseline captured.
  - Before-fix output file: `analysis-output/before-fix/af693a98-1e5c-499d-aa10-cccc54885c64.json`
  - RCA note: `analysis-output/rca-af693-before-fix.md`
  - Confirmed issue: `2.7 Unit Rotor` remains under Generator context because no explicit candidate boundary is created for this untyped numbered subsection.
- `fcb1511e-596a-4a56-b151-1e596afa569c` baseline captured.
  - Before-fix output file: `analysis-output/before-fix/fcb1511e-596a-4a56-b151-1e596afa569c.json`
  - Baseline findings note: `analysis-output/rca-fcb-before-fix.md`
  - Observed pattern: noisy hierarchy paths and repeated Generator/Gas Turbine context flips, making this document a key post-fix regression check target.
- `5b688732-39f2-48d2-a887-3239f258d28b` baseline captured in both parser paths.
  - Before-fix output files:
    - `analysis-output/before-fix/5b688732-39f2-48d2-a887-3239f258d28b.pymupdf_v1_0.json`
    - `analysis-output/before-fix/5b688732-39f2-48d2-a887-3239f258d28b.pypdf2_v1_0.json`
  - Baseline findings note: `analysis-output/rca-5b-before-fix.md`
  - Reproduced the reported behavior in both parsers: large Generator span with `section_path=["Generator"]` and parser-dependent offsets.

Stop for review:
- Await your review and approval before any code edits.

### Step 3: Code Changes (post-RCA approval)
Actions:
- Implement minimal code fix in the source-of-truth files.
- Keep behavior aligned with locked parent flip-back rule.
- Avoid unrelated refactors.

Step 3 implementation status (awaiting review):
- File updated: `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`
- Change summary:
  - Added targeted generic subsection candidate detection for untyped headings (initial rollout was level-1 only; now generalized across subsection levels).
  - Added inference for untyped subsection equipment type from same-root top-level section context (`SECTION_HDR` root map), with fallback to nearest prior same-root typed span.
  - Added strict gating to avoid broad candidate expansion:
    - only for non-Generator top-level roots,
    - only after a Generator subsection has already appeared in that same root,
    - dedupe repeated generic subsection signatures.
- Preliminary outcome snapshots:
  - `af693a98-1e5c-499d-aa10-cccc54885c64`: `2.7 Unit Rotor` now resolves to `Gas Turbine / 297652` (expected flip-back), `2.6` remains `Generator / 337X766`.
  - `fcb1511e-596a-4a56-b151-1e596afa569c`: quick smoke output remains stable shape (region count near baseline).
  - `5b688732-39f2-48d2-a887-3239f258d28b`: quick smoke output remains stable shape in both parser paths.

Deliverables:
- Focused code diff with explanation of behavior change.

Stop for review:
- Await your review before running final validation pass.

### Step 4: Next Activity (validation phase, after fix)
Actions:
- First, run post-fix output for target doc `af693a98-1e5c-499d-aa10-cccc54885c64` and compare with before-fix output from Step 2 to confirm issue resolution.
- Then, run post-fix output checks for the full document set below to verify no regression:
  - `b896cb9f-b70e-48c5-b9b1-477aa18bf03a`
  - `b1cdbc80-364f-4240-8dbc-80364f1240fa`
  - `b25c94da-d954-4283-9c94-dad954a28307`
  - `32689520-afed-4dd4-a895-20afed7dd4d2`
  - `cc9fe3d7-87cc-4687-9fe3-d787cc3687b3`
  - `0be4a3ad-7395-41ea-8ec2-e7669c9c15aa`
  - `bdd56c7a-ebe5-4bf7-904a-5bb63091ba20`
  - `4597a853-5ffb-40bb-b0be-bd6307b0acdc`
  - `27314604-ed52-402f-921f-34737a048841`
  - `4a56cb21-fd6b-4300-ac1b-62cf53b868a0`
  - `11338269-9d7c-4865-bfcf-1a4db9014acf`
  - `af693a98-1e5c-499d-aa10-cccc54885c64`
  - `b775cf29-8b42-4a83-af21-53075fef0802`
  - `9e279e5a-a24e-4ebd-a79e-5aa24efebd04`
  - `cdd0cca4-93ba-43b0-98e5-3d1ea2312c19`
  - `69dfe261-34b0-4740-ab89-498e7d0072df`
  - `d9b6c08b-d098-4939-a549-d113964e3150`
  - `796f4d53-a8ad-42e1-af4d-53a8add2e1a4`
  - `5b688732-39f2-48d2-a887-3239f258d28b`
  - `fcb1511e-596a-4a56-b151-1e596afa569c`
  - `b7b347fd-0b59-4c67-b609-9ad2c35105cc`
  - `35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report`
  - `806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report`
  - `3e91b865-2aaa-4233-ae4a-3e15ba641f96_605007134-180498-270t483-final_master_report`
- Compare before/after outputs and flag any behavior drift outside intended fix scope.

Step 4 status (in progress):
- Local before/after comparison completed for:
  - `af693a98-1e5c-499d-aa10-cccc54885c64`
  - `fcb1511e-596a-4a56-b151-1e596afa569c`
  - `5b688732-39f2-48d2-a887-3239f258d28b` (both parser paths)
- Local summary artifact:
  - `analysis-output/comparisons/local-before-after-summary.json`
- Target behavior check result:
  - `2.6 Generator Mechanical Scope` remains Generator context.
  - `2.7 Unit Rotor` flips from Generator (before) to Gas Turbine (after).
- Pending:
  - Run full regression on Databricks for complete doc set and collect `_batch_summary.json` + per-doc outputs.

Step 4 status (completed):
- Databricks full regression run received and analyzed from:
  - `analysis-output/databricks-results/after-fix-full-regression/`
- Batch result summary:
  - `ok`: 17
  - `skipped_missing_in_volume`: 3
  - `error`: 0
- Detailed report:
  - `analysis-output/comparisons/databricks-regression-report.json`
- Final summary:
  - `analysis-output/comparisons/final-validation-summary.md`

Step 4 follow-up cycle (Bug 2 validation and hardening):
- Standalone notebook output path unified for single-run and batch-run artifacts:
  - `/Workspace/Users/madhurima.saxena@gevernova.com/fsr-preprocessor-v2-output`
- Added standalone Bug 2 verification cells in notebook:
  - synthetic checks for section header detection around page-join boundaries
  - verifies both regex behavior and candidate-collector behavior
- Initial synthetic check result:
  - regex `without_newline` did not detect `2 Turbine`
  - candidate collector also failed in first attempt (before page-offset fix)
- Root cause identified in follow-up implementation:
  - page-aware header detection used `page_offsets[page_idx]` as an integer
  - Databricks payload provides page offsets as dict entries (`{"start": ..., "end": ...}`)
  - this produced runtime errors: `unsupported operand type(s) for +: 'dict' and 'int'`
- Follow-up code fix applied in `preprocessor_v2.py`:
  - page-aware `SECTION_HDR` detection retained
  - page offset extraction now supports both int and dict forms
  - uses dict `start` when entry is object-shaped
- Post-fix synthetic check result:
  - regex `without_newline` remains empty (expected)
  - collector `without_newline` detects `2 Turbine` (pass)

Step 4 rerun result after Bug 2 fix:
- Databricks batch rerun summary (`_batch_summary.json` in output folder):
  - `total_cases`: 23
  - `ok`: 20
  - `skipped_missing_in_volume`: 3
  - `error`: 0
- Skipped docs (source not present in mounted volume roots):
  - `35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report`
  - `806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report`
  - `3e91b865-2aaa-4233-ae4a-3e15ba641f96_605007134-180498-270t483-final_master_report`

Step 4 regression review conclusion (latest rerun):
- No high-impact regression detected from Bug 2 fix.
- Primary metadata remained stable across successful docs:
  - `primary_equip_type`, `primary_esn`, `gt_esn`, `gen_esn`, `st_esn`
- Region counts changed by small margins in some docs (boundary refinement signal), without primary metadata drift.
- Target Bug 1 behavior remains preserved (`2.6` Generator scope, `2.7` flip-back behavior retained).

Regression risk note (latest rerun):
- Boundary/segmentation drift was observed in a subset of documents (including larger region-count increases in `b775cf29-8b42-4a83-af21-53075fef0802` and `fcb1511e-596a-4a56-b151-1e596afa569c`) while primary metadata remained stable.
- Risk: if downstream logic depends on boundary count/shape (chunking, section-level analytics), this may have behavioral impact despite stable top-level ESN/equipment outputs.
- Recommended follow-up: run targeted downstream checks for chunking/section-level consumers on the affected docs before final sign-off.

Section path interpretation note:
- `section_path` represents the active parent chain at a given text span, not a running history of all prior sibling sections.
- Expected behavior:
  - when text is inside `2.4.4`, path should look like `2 -> 2.4 -> 2.4.4`.
  - when parser moves to sibling `2.5`, prior `2.4.*` branch should close and path should become `2 -> 2.5`.
- Therefore, path should not retain prior sibling entries like `2.2`, `2.3`, and `2.4` after transitioning into `2.5`.
- If mixed sibling chains appear (for example `2.4.*` and `2.5` together), it indicates hierarchy-recovery fallback due to a local missing/unclear boundary and should be reviewed as a path-quality signal.

### Step 5: Rule Generalization Across All Subsection Levels (current cycle)
Driver:
- Follow-up guidance requires the same span-scoped flip-back rule across all subsection levels, not only level-1.
- Follow-up clarification finalized expected unclear-structure behavior:
  - same-root siblings should preserve root chain (example `2 -> 2.4`).
  - root-change subsections should not inherit prior root branch (example `3.1` should anchor to top equipment header, not under `2.4`).

Implementation update:
- File updated: `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`
- Change applied:
  - generalized untyped subsection heading detection pattern from `x.y` only to `x.y(.z...)+` so deeper headings are included (for example `2.6.1`, `2.6.1.1`) under existing guardrails.
  - updated hierarchy-conflict parent assignment to be root-aware:
    - prefer nearest lower-level parent in the same root when available,
    - if expected parent is missing and root changed, re-anchor to top equipment header,
    - avoid forcing attachment to prior sibling branch when root continuity is not supported.
  - added root-aware correction for normal stack attachment path as well, so root-change subsections (example `3.1`) do not silently attach under prior root branch when no explicit `3` parent header is available.
- Guardrails retained unchanged:
  - top-level root must be non-Generator,
  - a Generator subsection must already have appeared earlier within the same root,
  - explicit equipment-prefixed headings remain excluded,
  - duplicate generic subsection signatures remain deduped.

Validation plan for Step 5:
- Re-run standalone notebook full regression batch after sync.
- Compare current batch summary and key-doc metadata with prior stable run.
- Confirm no new runtime errors and no primary metadata drift.
- Confirm path-quality expectations on unclear structure cases:
  - `2.4` remains on `2 -> 2.4`
  - `3.1` anchors as `Turbine(ESN|SY) -> 3.1` when `3` parent header is missing/unclear.
 - Local synthetic sanity check passed for root-change re-anchoring behavior.

Step 5 validation update (latest run review):
- Batch health (latest export):
  - `total_cases=23`, `ok=20`, `skipped_missing_in_volume=3`, `error=0`.
- af693 edge-case status:
  - confirmed `2 Turbine` is retained before `2.4` (the earlier reset/pop no longer occurs in latest output path).
  - confirmed no mixed `2.4` + `2.5` chain in same path segment.
  - confirmed target behavior remains intact: `2.6` stays Generator and `2.7` flips back to Gas Turbine.
- 796f primary flip review:
  - observed flip from `Gas Turbine/297627` to `Generator/337X755` in latest run.
  - reviewed attached TOC evidence and section coverage in latest output; this document contains large Generator section content after Turbine section.
  - conclusion: this specific flip is treated as expected correction (not regression) for `796f4d53-a8ad-42e1-af4d-53a8add2e1a4`.
- Remaining caution:
  - region-count/segmentation drift remains in some docs and should still be treated as downstream quality risk for chunking/section analytics consumers.

Deliverable:
- Validation summary indicating corrected cases and any residual anomalies.

## Notes
- Commit relocation/revert decisions are deferred until after RCA + fix verification.
- Follow-up design direction captured for future extension:
  - subsection-specific override rules should be span-scoped and end at the next sibling subsection boundary.
  - this applies symmetrically (for example, Turbine parent -> Generator subsection -> flip-back, and Generator parent -> Turbine subsection -> flip-back).

## Latest Work Summary (Short)
- Implemented and validated two fixes:
  - Bug 1: untyped subsection flip-back handling (initially level-1, then generalized to all subsection levels under the same guardrails).
  - Bug 2: section header detection at page joins without newline; added page-aware detection and fixed dict/int page-offset handling.
- Notebook updates:
  - standalone output path unified to `/Workspace/Users/madhurima.saxena@gevernova.com/fsr-preprocessor-v2-output`
  - synthetic Bug 2 verification cells added.
- Latest Databricks rerun result:
  - `total_cases=23`, `ok=20`, `skipped_missing_in_volume=3`, `error=0`.
- Quality signal:
  - top-level metadata remained stable in successful docs.
  - boundary/segmentation drift observed in a subset of docs; downstream chunk/section consumers should be checked before final sign-off.

## Latest Verification Addendum (2026-08-11)
- Export reviewed from `dbx/fsr-preprocessor-v2-output` after the latest hierarchy/suppression hardening cycle.
- Final health check remains stable:
  - `total_cases=23`, `ok=20`, `skipped_missing_in_volume=3`, `error=0`.
- af693 validation reconfirmed:
  - `2 Turbine` retained before `2.4` (no parent-chain pop at the `2.4` boundary).
  - no mixed `2.4` + `2.5` chain observed.
  - target behavior preserved: `2.6` remains Generator and `2.7` flips back to Gas Turbine.
- 796 root-anchoring/path quality check:
  - sampled 3.x paths remain anchored under `3 Generator` chain.
  - strict mixed-root check (`2.*` branch and `3.*` branch in one path) returned `0`.
- Regression posture:
  - no runtime regressions in latest run.
  - remaining differences versus older baseline are primarily region-count/segmentation drift and continue to be tracked as downstream risk for chunking/section-level analytics.

## Bug Summary

- **Bug 1 (flip-back — level-1):** After a subsection is tagged with subsection-specific equipment context (e.g., `2.6 Generator Mechanical Scope` under a Turbine root), the next untyped sibling subsection (e.g., `2.7 Unit Rotor`) incorrectly retained the subsection's equipment context instead of flipping back to the parent section's context.
- **Bug 1 (flip-back — generalization):** The level-1 flip-back fix did not cover deeper untyped subsection headings (`x.y.z`, `x.y.z.w`, etc.), so the same incorrect context retention occurred at deeper nesting levels until the pattern was broadened.
- **Bug 2 (page-join header detection):** Section headers appearing at page boundaries without a preceding newline were not detected because the page-aware offset calculation treated Databricks dict-shaped page offsets (`{"start": ..., "end": ...}`) as integers, producing a runtime type error and silently skipping those headers.

### Bug List Update (2026-08-12)

- Added TOC-gated filtering for unnumbered equipment headers to reduce table-content misdetection as level `-1` section roots.
- Added Generator keyword subsection detection for `Electrical`, `Electrification`, `Electrically`, and `DC leak/leakage` variants under Generator roots.
- Added configurable IBAT candidate-pool preference (`all_esns` then `broad_esns`) so cross-type fallback can be tuned after final confirmation.
- Added guardrailed same-type last-known ESN recovery for unresolved typed spans with a distance threshold to avoid stale long-range carry-over.

## New Intake (2026-08-12) — Customer Reported Issues

Status:
- Intake captured from 2-FSR-v2/bug-preprocessor/new-preprocessor-issues/issue.
- Customer responses received and reviewed on 2026-08-12.

Reference docs/code for this cycle:
- Issue tracker: 2-FSR-v2/bug-preprocessor/new-preprocessor-issues/issue
- RCA tracker: 2-FSR-v2/bug-preprocessor/new-preprocessor-issues/rca-plan.md
- Design context: 2-FSR-v2/bug-preprocessor/redesign/proposed-design-changes.md
- Source code:
  - pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py
  - pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/metadata_processor_v2.py
- Validation assets:
  - pw_sdg_ai_ser_repo/validation/fsr_v2/preprocessor/run-preprocessor-standalone.ipynb
  - pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data
- Bug list CSV:
  - 2-FSR-v2/bug-preprocessor/new-preprocessor-issues/Bugs_prepared_for_0803(Sheet1).csv

New issues in scope (8/12):
- Doc b896cb9f-b70e-48c5-b9b1-477aa18bf03a:
  - Bare heading "1 Turbine" mapped to Gas Turbine under a Steam Turbine parent chain.
  - ESN mismatch observed between section path context and chosen primary_esn.
- Doc b1cdbc80-364f-4240-8dbc-80364f1240fa:
  - Equipment text inside table appears to be interpreted as section header context.
- Doc b25c94da-d954-4283-9c94-dad954a28307:
  - GT ESN missing and downstream spans appear to inherit incorrect/empty context.
- Doc 32689520-afed-4dd4-a895-20afed7dd4d2:
  - Table-derived Gas Turbine likely misdetected as top/root boundary (level -1), preventing expected parent-based fallback and IBAT trigger path.

Working hypothesis:
- Primary failure modes are:
  - generic "Turbine" subsection typing defaults,
  - table-text contamination in heading detection,
  - orphan root-level spans with no ESN anchor and weak recovery.

Customer reply decisions (resolved):
1. b896cb9f-b70e-48c5-b9b1-477aa18bf03a
  - Confirmed: bare subsection titles like "1 Turbine" should inherit equipment type from nearest explicit parent equipment header unless subsection has explicit equipment marker.
2. b896cb9f-b70e-48c5-b9b1-477aa18bf03a
  - Confirmed ESN priority: subsection text first, then parent logic.
  - Parent logic detail: inherit if same type; use IBAT resolution when cross-type and candidate set is not uniquely resolvable.
  - Decision update (2026-08-12): for cross-type fallback candidate filtering, use `broad_esns` first and `all_esns` as secondary.
3. b1cdbc80-364f-4240-8dbc-80364f1240fa
  - Confirmed: table-only equipment text should not become section header by default.
  - Approved direction: keep candidate only if aligned with primary TOC structure; embedded sub-reports and embedded TOCs remain out of scope.
  - Decision update (2026-08-12): allow non-TOC table/equipment header candidate only when ESN or SY exists in the same line.
4. Additional concrete table-contamination examples to validate against:
  - 32689520-afed-4dd4-a895-20afed7dd4d2 (page 6)
  - b25c94da-d954-4283-9c94-dad954a28307 (page 14 and page 307)
5. b25c94da-d954-4283-9c94-dad954a28307 and 32689520-afed-4dd4-a895-20afed7dd4d2
  - Confirmed: if misdetected level -1 span lacks ESN, IBAT fallback should still be allowed via nearest valid context.
  - Practical expectation from the customer: this should become rare once table-header contamination is filtered, since primary TOC level -1 entries generally include ESN/SY.
  - Decision update (2026-08-12): when nearest valid context is stale (many pages away), leave ESN empty to preserve debugging signal.
6. b25c94da-d954-4283-9c94-dad954a28307
  - Confirmed fallback preference: recover from last known valid GT context if missing GT ESN still occurs.
7. Scope priority confirmed:
  - Must-fix now: (a) Turbine inheritance fix (Steam vs Gas), (b) ignore table-only equipment text for hierarchy levels.
  - Next quick fix: add Generator header keywords (Electrical, Electrification, DC leakage).
  - Defer to next round/after QA: shared sections and ambiguous appendix/embedded-report scenarios.
8. Keyword scope decision (2026-08-12):
  - Generator keyword matching should include only `Electrical`, `Electrification`, and `DC leakage`.
  - Additional variants (for example `Electrically`, `DC leak`, `DC leakage current`) are out of scope for now.

Basic plan for today (post-reply update):

Step A — Reproduce and isolate per-doc behavior
- Re-run standalone preprocessor for each new doc id above.
- Save per-doc before-fix outputs under analysis-output/2026-08-12-before-fix/.
- Capture evidence snippets: section_path, primary_equip_type, primary_esn, esn_source, equip_type_source.

Step B — Confirm failure mode mapping in code
- Trace subsection typing path in preprocessor_v2.py for bare "Turbine" headings.
- Trace section candidate creation filters for table-derived text and level assignment.
- Trace no-parent/no-esn branch for IBAT trigger eligibility and early exits.
- Add explicit check of IBAT candidate-set source (`all_esns` vs `broad_esns`) and document recommended behavior.

Step C — Define fix set (no broad refactor)
- Fix 1: bare "Turbine" subsection inherits nearest explicit parent equipment context (Steam/Gas) with guardrails.
- Fix 2: suppress table-only equipment mentions from top-level heading candidate generation unless candidate aligns with primary TOC structure.
- Fix 3: add recovery path for level -1/no-esn spans so fallback can still resolve ESN from nearest valid context when safe.
- Next quick win: extend Generator keyword signals to include Electrical, Electrification, and DC leakage.

Step D — Validate and regression check
- Re-run target docs first, then full 12-doc ESN set from CSV.
- Compare primary metadata stability plus boundary/segmentation drift.
- Produce short pass/fail matrix with deferred items explicitly listed.

Out-of-scope for this cycle (unless reprioritized):
- Shared sections: QCP, PIPO, Coupling, Alignment.
- Ambiguous sections: Appendix and embedded reports.

Implementation update (2026-08-12, completed):
- Code updated in pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py.
- Implemented now:
  - TOC-gated suppression for unnumbered equipment headers (reduces table-text promoted level -1 sections).
  - Generator subsection keyword detection path for Electrical, Electrification, and DC leakage (root-gated to Generator top sections).
  - IBAT candidate-pool preference scaffolding in resolver path with configurable order; updated default order to broad_esns first, then all_esns.
  - Guardrailed last-known same-type context recovery for unresolved typed spans with max distance threshold to avoid stale carry-over.
- pending final policy confirmation from the customer (implemented as configurable toggles for now):
  - none for current 8/12 decision set.

Validation update (2026-08-12, in progress):
- Batch validation started from notebook and completed with summary artifact at:
  - /home/u560060992/dbx/fsr-preprocessor-v2-output/_batch_summary.json
- Current environment result:
  - all cases `skipped_missing_in_volume` because document roots under `/Volumes/...` are not mounted in this local runtime.
- Local synthetic validations completed:
  - Bug 2 page-join section header check: PASS (`2 Turbine` detected by candidate collector with and without newline join).
  - Generator keyword synthetic check: PASS (`Electrical`, `Electrification`, `DC leakage` detected as Generator subsections).
- Awaiting Databricks run artifacts from `/Workspace/Users/madhurima.saxena@gevernova.com/fsr-preprocessor-v2-output` for full doc-level regression verification.

Validation update (2026-08-12, Databricks export reviewed):
- Export folder reviewed: `/home/u560060992/dbx/fsr-preprocessor-v2-output`
- Batch summary (`_batch_summary.json`):
  - `ok`: 20
  - `skipped_missing_in_volume`: 3
  - `error`: 0
- Focus-doc verification:
  - `b1cdbc80-364f-4240-8dbc-80364f1240fa`: no blocking regression signal observed in summary output.
  - `b25c94da-d954-4283-9c94-dad954a28307`: GT ESN propagation present in section spans (no broad missing-ESN cascade observed in sampled output).
  - `32689520-afed-4dd4-a895-20afed7dd4d2`: GT ESN propagation present in section spans (no broad missing-ESN cascade observed in sampled output).
  - `b896cb9f-b70e-48c5-b9b1-477aa18bf03a`: remaining mismatch still observed in sampled output; one span under `STEAM TURBINE (814638 | SY0052637) -> 1 Turbine` is still labeled `Gas Turbine` with ESN `804700`.
- Conclusion:
  - batch health is stable, but the `b896...` inheritance/assignment behavior is not fully resolved yet and needs another targeted fix.

Hold status (2026-08-12):
- For `b896cb9f-b70e-48c5-b9b1-477aa18bf03a`, pause additional code changes until the customer confirms expected behavior for:
  - `N Turbine` inheritance under a Steam Turbine parent chain,
  - fallback behavior when parent context is missing/stale (inherit vs leave empty).
- Current action: waiting for customer clarification before implementing the next targeted fix.

Follow-up decision and implementation (2026-08-12):
- Customer confirmed: a bare `N Turbine` heading under a Steam Turbine parent must inherit Steam Turbine, even when Gas Turbine sections occur earlier in the document.
- Parentless bare `N Turbine` behavior: assign equipment type only when exactly one of GT/ST exists in document inventory; when both exist or neither exists, leave it empty.
- Targeted fix completed in `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`:
  - bare numbered `Turbine` headings are no longer defaulted to Gas Turbine during section-header candidate collection;
  - resolution first inherits explicit Steam/Gas parent type, then applies the single available GT/ST inventory fallback.
- Focused synthetic validation: PASS.
  - `STEAM TURBINE (814638 | SY0052637) -> 1 Turbine` resolves to Steam Turbine / 814638.
  - parentless bare `1 Turbine` resolves to Gas Turbine when GT is the only turbine type present.
- Pending: rerun `b896cb9f-b70e-48c5-b9b1-477aa18bf03a` in Databricks, then rerun full regression batch before final validation sign-off.

5b clarification and implementation update (2026-08-12):
- Customer confirmed `5b688732-39f2-48d2-a887-3239f258d28b` is the parentless-case example: `3.3.1 Turbine Casing` should resolve to Steam Turbine because ST ESN `155360` exists and no GT ESN exists in the document.
- The bare-Turbine rule now applies to all numbered depths (for example, `1 Turbine` and `3.3.1 Turbine Casing`):
  - inherit explicit Steam/Gas parent when available;
  - otherwise use the sole available GT/ST type;
  - otherwise leave equipment type and ESN empty.
- Focused synthetic validation: PASS for `3.3.1 Turbine Casing` with Steam Turbine as the only available turbine type.

Final Databricks validation rerun (2026-08-12):
- Batch result: `ok=20`, `skipped_missing_in_volume=3`, `error=0`.
- `b896cb9f-b70e-48c5-b9b1-477aa18bf03a`: PASS.
  - `STEAM TURBINE (814638 | SY0052637) -> 1 Turbine` now resolves to Steam Turbine / `814638` via parent inheritance.
- `5b688732-39f2-48d2-a887-3239f258d28b`: PASS.
  - `3.3.1 Turbine` now resolves to Steam Turbine / `155360` via sole turbine-type fallback.
- No batch execution errors observed. The three skipped documents remain unavailable in configured volume roots.

Skipped-document discovery follow-up (2026-08-12):
- Root cause identified: batch discovery normalized compound document names to UUID only and checked an extensionless exact path. The three source files exist with compound filenames, capitalization differences, and `.pdf` extensions.
- Notebook discovery hardened in `pw_sdg_ai_ser_repo/validation/fsr_v2/preprocessor/run-preprocessor-standalone.ipynb`:
  - notebook-only discovery override removed; validation should consume the production discovery contract.
- Pipeline discovery hardened in `pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/input.py` target mode:
  - retain exact-path lookup first;
  - then accept a UUID-prefix PDF only when it is unique within a configured volume root;
  - raise an explicit error instead of selecting arbitrarily when multiple PDFs match a UUID prefix.
- Document-ID contract remains unchanged: the UUID remains `document_id`; the unique matched full PDF path is used only for file parsing.
- Standalone validation now delegates single-document and batch file lookup to the same pipeline target-discovery helper, rather than implementing a separate filename policy.
- Pending: validate the production target-discovery path in Databricks for the previously skipped three documents, then rerun the batch.

af693 regression follow-up (2026-08-12):
- Regression observed: `2.7 Unit Rotor` boundary was absent, so `2.6.1 Generator` incorrectly continued until `5.1 Combustion`.
- Root cause:
  - current PyMuPDF output renders `2.7 Unit Rotor` without Markdown `#` markers;
  - generic heading matching was broadened to accept that format, but generic context still used a document-global root-number map;
  - reused root number `2` from later sections overwrote the relevant Turbine context, causing the generic `2.7` candidate to be suppressed.
- Fix completed in `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`:
  - generic numbered subsections accept heading text with or without Markdown markers;
  - generic subsection equipment context is now derived from the nearest preceding explicit equipment/section candidate at that text position, rather than the global root-number map.
- Focused actual-PDF validation: PASS.
  - `2.7 Unit Rotor` boundary restored and resolves to Gas Turbine / `297652`.
- Customer review: approved the current fix direction.
- Guardrail follow-up: first validate for new false-positive section/span boundaries. If noise appears, confirm generic numbered candidates against the primary TOC before retaining them; embedded-report TOCs remain out of scope.
- Pending: Databricks rerun of af693, followed by full regression validation and false-positive boundary review.

Bug 2 GG/SY ESN follow-up (2026-08-12):
- Supplied PDFs reviewed:
  - `0be4a3ad-7395-41ea-8ec2-e7669c9c15aa`: `GG10675` is written in an embedded report as `Equipment ID -> SY1390901 -> Equipment SN -> GG10675`; the existing structured GG pattern required `GG... | SY...`, and title-label scanning did not reach this later page.
  - `cdd0cca4-93ba-43b0-98e5-3d1ea2312c19`: cover-page `GG10525 | SY0499189` is valid Generator ESN evidence; later `338X233` is a nameplate serial and must not replace GG10525.
  - `3f5a1ea8-8f35-4e97-9a1e-a88f358e9768`: `ESN: SY...` values are supporting identifiers only and must not become primary ESNs.
- Fix completed in `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`:
  - added a narrowly scoped multiline Generator pattern for `Equipment ID (SY)` followed by `Equipment SN (GG)` anywhere in document text.
- Focused actual-PDF validation: PASS.
  - GG10675 discovered and emitted as `gen_esn`.
  - GG10525 retained; 338X233 not added to discovered ESNs.
  - SY-only values not added to discovered ESNs.
- Impact assessment: isolated to ESN inventory discovery. It does not change section candidate collection, hierarchy/TOC rules, bare-Turbine attribution, or source-file discovery.

Latest standalone full regression rerun (2026-08-12):
- Batch health: `ok=27`, `skipped_missing_in_volume=0`, `error=0`.
- Production-style UUID-prefix discovery resolved all three previously skipped compound filenames and retained UUID-based output IDs.
- Verified target outcomes:
  - `af693a98-1e5c-499d-aa10-cccc54885c64`: `2.7 Unit Rotor` boundary present and attributed to Gas Turbine / `297652`.
  - `b896cb9f-b70e-48c5-b9b1-477aa18bf03a`: `STEAM TURBINE -> 1 Turbine` attributed to Steam Turbine / `814638`.
  - `5b688732-39f2-48d2-a887-3239f258d28b`: `3.3.1 Turbine` attributed to Steam Turbine / `155360`.
  - `0be4a3ad-7395-41ea-8ec2-e7669c9c15aa`: `GG10675` emitted as `gen_esn` and included in `all_esns`.
  - `cdd0cca4-93ba-43b0-98e5-3d1ea2312c19`: `GG10525` retained as Generator ESN; `338X233` not promoted.
  - `3f5a1ea8-8f35-4e97-9a1e-a88f358e9768`: SY-only identifiers remain unassigned as primary ESNs.
- Remaining regression-review signal:
  - `b775cf29-8b42-4a83-af21-53075fef0802` region count increased from 21 in the prior standalone rerun to 52. Primary metadata remains Gas Turbine / `297651`, but the boundary increase should be inspected before ingest sign-off.


## 2026-08-13 Root Cause Addendum

FSR V2 Preprocessor - 2026-08-13 Root Cause Audit

Scope:
- Source issue note: 2-FSR-v2/bug-preprocessor/new-preprocessor-issues/8-13-issues
- Primary focus: Issue 1 (b775cf29-8b42-4a83-af21-53075fef0802)
- Code reviewed: pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py
- Output reviewed: dbx/fsr-preprocessor-v2-output/b775cf29-8b42-4a83-af21-53075fef0802.json

------------------------------------------------------------
Issue 1 (b775cf29-8b42-4a83-af21-53075fef0802)
Reported:
- No Generator ESN assigned at "3.1.1 Generator"
- Did not cleanly flip back around "3.1.2"
- Weird section_path entries like "3.0\n8350"

Observed evidence from current output:
1) Generator span with no ESN
- Span [19897, 20930] is tagged as:
	- primary_equip_type = Generator
	- esn_source = none
	- section_path includes "### 3.1.1 Generator"

2) Noisy section_path entries from numeric/table text
- section_path includes values like:
	- "3.8 PI plus ..."
	- "3.0\n8350"
	- "3.0\n10"

3) Flip-back appears but under polluted hierarchy
- Around "### 3.1.2 Turbine", equipment resolves back to Gas Turbine in some spans,
	but path chain is already noisy because false subsection headings were inserted.

Root cause split (important):

A) Rigid/premissive generic matching behavior (regex + promotion path)
- SUBSEC_GENERIC is broad:
	- r'(?m)^(?:#{1,3}\s+)?(\d{1,2}(?:\.\d{1,2})+)\s+([^\n]+)$'
- This pattern can match many numbered lines that are not true headings
	(for example numeric table/value lines).

B) Yesterday's change path is the main trigger for this doc's failure mode
- The generic subsection promotion block now actively converts those generic matches
	into subsection candidates under specific guardrails:
	- non-Generator context inferred from prior typed headers,
	- same root has seen Generator subsection start,
	- title not matching explicit equipment prefixes.
- In this doc, that logic promotes noisy lines (for example "3.0\n8350", "3.0\n10")
	into heading candidates.
- Those false candidates distort hierarchy and section boundaries, producing weird
	section_path chains and unstable flip behavior.

Conclusion for "regex vs yesterday changes":
- It is both, but weighted toward yesterday's behavior change.
- The broad regex existed as a latent risk.
- The new promotion logic made that risk operational in this document by turning
	generic numeric lines into active subsection nodes.

Why "No Generator ESN" appears at 3.1.1:
- This is expected from current ESN fallback chain for unresolved typed spans:
	local -> parent(same type) -> single_type -> ibat_train -> none.
- In b775, document-level ESN inventory is GT-only (297651) and there is no unique
	Generator ESN candidate available for the 3.1.1 Generator span.
- So the resolver lands on esn_source=none.
- This is likely a symptom amplified by false heading promotion; if the heading/span
	were not created (or were better bounded), the exposure would be reduced.

Risk assessment:
- High risk to path quality and boundary stability when numeric body/table lines look
	like numbered headings.
- Medium risk to ESN attribution quality via secondary effects (extra spans, wrong
	parent chain, and more unresolved typed spans).

Related example mentioned in issue note (fcb1511e-596a-4a56-b151-1e596afa569c):
- Similar pattern appears (Generator subsection followed by Turbine-return sections).
- Before/after artifacts show this pattern existed across cycles; issue severity now is
	mainly from hierarchy pollution and path quality drift, not a single missing flip rule.

Bottom line:
- Issue 1 is not only a rigid regex problem.
- The current failure is primarily caused by interaction between broad generic subsection
	matching and yesterday's generalized promotion/inference logic.
- Existing ESN fallback behavior then surfaces "Generator + no ESN" where the hierarchy
	has already been polluted.

------------------------------------------------------------
Addendum (for communication and next-step decisions)

1) Slack-ready summary (no code links)

Quick RCA update for today:
- I confirmed issue 1 is real and reproducible on b775.
- The main failure is not a single bad rule; it is a rule interaction problem.
- A broad generic subsection detector is promoting non-heading numeric lines (for example table/value lines) into section boundaries.
- Once those false boundaries are created, section path becomes noisy and flip-back behavior looks inconsistent.
- "Generator with no ESN" is mostly a downstream symptom: the span is typed as Generator, but doc-level context does not provide a resolvable Generator ESN in that location.
- Net: yesterday's fixes solved target bugs, but they also increased sensitivity to format noise in some docs.

2) Do I agree deterministic logic can work for some cases but fail for others?

Yes, I agree.

Why this happens in detail:
- Deterministic parsing assumes consistent structure (heading styles, spacing, numbering, line breaks).
- FSR documents are not structurally uniform:
	- TOC style varies by plant/report template.
	- OCR/page join artifacts can merge or split lines.
	- Numeric table rows can look exactly like subsection headings.
	- Embedded sub-reports may reuse numbering differently.
- When I tighten for one pattern, recall drops (miss real headings).
- When I loosen for one pattern, precision drops (accept false headings).
- So deterministic quality is always a precision/recall tradeoff across document families, not a one-time "fix all" state.

3) Why generic subsection regex works in many docs, but fails in others

Why it works:
- Most true subsection headings do follow numbered-prefix patterns like x.y or x.y.z plus title text.
- This gives high coverage quickly with low implementation complexity.
- It is especially useful when explicit equipment words are missing in subsection titles.

Why it fails:
- The same visual pattern appears in non-heading lines:
	- table rows,
	- measured values,
	- list fragments,
	- OCR-broken lines.
- Regex cannot understand document intent; it only sees string shape.
- After promotion into hierarchy, a false match is high impact:
	- introduces wrong boundaries,
	- changes parent chain,
	- influences equipment inheritance,
	- can cascade into ESN resolution errors.

4) Suggested solution and risk

Proposed solution (practical, staged):
- Keep generic subsection detection, but move to score-based acceptance instead of direct promotion.
- For each generic candidate, compute a confidence score from multiple signals:
	- strong positive: appears in TOC-consistent numbering path, typography/line-shape like headings, reasonable title tokens.
	- strong negative: dense numeric ratio, unit-heavy strings, table-column alignment pattern, repeated value rows near same page area.
	- context positive: valid parent root continuity, nearby true typed subsection anchors.
- Only promote candidates above threshold; keep borderline candidates as "non-structural hints" instead of hierarchy nodes.
- Add post-build sanity checks:
	- reject impossible jumps and duplicate oscillations,
	- collapse low-confidence micro-sections,
	- preserve root-level stability when confidence is weak.

Risk of this solution:
- Added complexity and more parameters (threshold tuning required).
- Potential recall drop for short but valid headings in unusual templates.
- Cross-doc calibration cost: a threshold good for one family may underperform on another.
- More validation burden: I will need per-family regression slices, not only one blended batch metric.

Risk mitigation:
- Roll out behind a config flag.
- Start with conservative threshold and compare precision/recall on known bug docs + stable docs.
- Track two metrics separately: heading precision and ESN attribution accuracy, so I do not hide structure regressions behind metadata stability.

------------------------------------------------------------
Doc Examples (requested first)

Example 1: b775cf29-8b42-4a83-af21-53075fef0802
- Reported concern:
	- "3.1.1 Generator" has no Generator ESN.
	- Path quality looks wrong in nearby spans.
- Output evidence:
	- Span [19897, 20930]
		- primary_equip_type = Generator
		- esn_source = none
		- section_path = GAS TURBINE (297651 | SY0070884) -> 3 Turbine -> ### 3.1.1 Generator
	- Nearby spans contain section_path entries that look like table/value lines instead of real headings:
		- "3.8 PI plus ..."
		- "3.8\\nPosition"
		- "3.0\\n8350"
		- "3.0\\n10"
- Interpretation:
	- These are strong indicators of false generic subsection promotion.
	- Once those false headings enter hierarchy, boundary/path quality degrades and flip behavior appears inconsistent.

Example 2: fcb1511e-596a-4a56-b151-1e596afa569c
- Reported concern:
	- Generator subsection should flip back to Turbine in following subsection.
- Output evidence:
	- Span [59386, 69345]
		- primary_esn = 337X581
		- primary_equip_type = Generator
		- section_path = 3 Turbine -> ## 3.4 Turbine -> ### 3.8.6 Generator
	- Next span [69345, 71683]
		- primary_esn = 298464
		- primary_equip_type = Gas Turbine
		- section_path = 3 Turbine -> ## 3.4 Turbine -> ### 3.9.6 Inlet
- Interpretation:
	- Flip-back behavior is present here (Generator to Gas Turbine).
	- Main remaining risk is numbering/path continuity quality, not a total absence of flip.

------------------------------------------------------------
Additional Issues Added On 2026-08-13 (RCA Update)

Issue 2: 0be4a3ad-7395-41ea-8ec2-e7669c9c15aa
Reported:
- "5 Electrical System" is not detected as expected Generator context.

What current output shows:
- Generator does appear in part of section 5 (for example "## 5.1 Generator" with Generator ESN GG10675).
- Other electrical-looking spans remain under Gas Turbine path (for example "## 5.9 Rotor Electrical Inspection").

Root cause analysis:
- Current keyword-based Generator promotion for Electrical/Electrification/DC Leakage is intentionally root-gated.
- That rule only promotes when the root section is already known as Generator.
- In mixed Turbine roots, Electrical-named headings can stay Turbine by design.
- Result: this is not a complete miss of Generator detection, but a mixed-classification behavior from a conservative guardrail.

Conclusion:
- Partial detection exists; inconsistency comes from root-gated policy, not from regex absence alone.
- If business expectation is "Electrical under Turbine root should still flip to Generator," current rule is too strict.

Issue 3: b1cdbc80-364f-4240-8dbc-80364f1240fa
Reported:
- First "GAS TURBINE (297191 | SY0070261)" in TOC is not detected.

What current output shows:
- The GAS TURBINE header is detected in content and used for section attribution.
- Primary GT attribution remains stable in output.

Root cause analysis:
- The TOC extractor relies on line-shape patterns (title + trailing page number / dot leaders) and limited candidate-page scanning.
- If the first TOC row formatting is irregular (OCR split, spacing artifact, non-standard separator), that specific TOC item may be skipped.
- This is a TOC-line parsing limitation, not a core section-attribution failure in this case.

Conclusion:
- Low impact for this doc's metadata/region outputs today.
- Still a valid quality gap for TOC completeness and should be tracked for next round.

Issue 4: 27314604-ed52-402f-921f-34737a048841
Reported:
- Some spans are assigned Generator even though section_path and parent look Turbine.

What current output shows:
- Under path
	GAS TURBINE (298250 | SY0084018) -> 3 Turbine -> 3.4 Turbine -> 3.4.x Turbine,
	multiple spans are tagged:
	- primary_equip_type = Generator
	- primary_esn = 338X447

Root cause analysis:
- This is a root-number reuse problem with global type inference for untyped subsections.
- Untyped "... Turbine" subsection candidates depend on inferred equipment type by top-level root number.
- The same root number (for example root "3") appears in multiple report segments (Generator and Gas Turbine) in the same document.
- Because root-type inference is global and not position-scoped, later/other root-3 context can leak into earlier Turbine subsection spans.
- Then ESN resolver deterministically assigns Generator ESN (single_type / parent_inherit), creating the observed mismatch.

Conclusion:
- This is a deterministic cross-segment leakage bug, not random behavior.
- It is consistent with known risk: global root-number maps are unsafe when a document contains multiple embedded reports with reused numbering.

Priority recommendation for next fix batch:
1. Make untyped subsection equipment inference position-scoped (nearest valid ancestor window), not global-by-root.
2. Add segment boundary awareness (new equipment header should reset local root inference scope).
3. Keep current guardrails for table contamination, but lower trust for generic subsection candidates in high-numeric-density regions.

Risks of the recommended fix:
- If scope windows are too tight, valid long-range parent links may be missed (recall drop).
- If segment reset rules are too aggressive, cross-page continuity can fragment.
- Requires targeted regression checks on mixed-report docs to avoid over-correction.

------------------------------------------------------------
Comparison Against Earlier RCA Plan + Pass-Set Safety Validation

Objective of this check:
- Compare new fix ideas in this note against already validated outcomes in
	`2-FSR-v2/bug-preprocessor/new-preprocessor-issues/rca-plan.md`.
- Validate whether the new fixes are likely to reopen previously passing cases.

What was previously validated as passing (from earlier RCA/validation cycle):
- af693: `2.6` stays Generator and `2.7 Unit Rotor` flips back to Gas Turbine.
- b896: `STEAM TURBINE -> 1 Turbine` inherits Steam Turbine context.
- 5b: parentless `3.3.1 Turbine` resolves to Steam Turbine when ST is the only turbine type.
- 0be: GG10675 is discovered as Generator ESN; mixed section-5 behavior is currently allowed by policy.
- cdd: GG10525 retained as Generator ESN (no contamination by later 338X233 mention).
- 3f5: SY-only identifiers are not promoted to ESNs.
- Batch health in prior cycle reached stable `ok=20` then `ok=27` with zero runtime errors in final rerun.

Compatibility assessment of proposed new fixes:

Fix proposal A: position-scoped untyped subsection inference (instead of global root map)
- Compatibility with pass set: HIGH (expected to improve safety).
- Why:
	- Directly addresses 273 cross-segment leakage without conflicting with af693/b896/5b expectations.
	- Earlier RCA already documented global root-map reuse as a known risk point.
- Main risk:
	- If scope window is too narrow, af693-like flip-back boundaries can be lost.

Fix proposal B: segment boundary reset when a new explicit equipment header starts
- Compatibility with pass set: MEDIUM-HIGH (safe if reset is local and typed-header driven).
- Why:
	- Prevents root-number collisions across embedded report segments (issue 4 pattern).
- Main risk:
	- Over-aggressive resets can fragment legitimate long spans and increase region churn
		(known sensitivity already seen in b775/fcb boundary counts).

Fix proposal C: lower trust for generic numbered candidates in numeric-dense/table-like zones
- Compatibility with pass set: MEDIUM (needs careful thresholding).
- Why:
	- Needed for b775-style noisy `3.0\\n####` path pollution.
- Main risk:
	- If too strict, true generic headings can be dropped and af693-like boundary restoration can regress.

Fix proposal D: loosen Electrical handling under Turbine roots
- Compatibility with pass set: MEDIUM-LOW unless policy is explicit.
- Why:
	- Current passing behavior in 0be is mixed by design (root-gated Generator keywords).
	- Changing this without a strict rule can unintentionally relabel GT electrical sections.
- Main risk:
	- Reclassifying valid GT electrical content to Generator.

Validation verdict for "will this reopen passing cases?"
- I cannot claim zero-regression guarantee before rerun because these fixes are not implemented yet.
- I can validate design-level compatibility as follows:
	- A + B are aligned with earlier RCA direction and are unlikely to reopen known passes if implemented conservatively.
	- C is beneficial but threshold-sensitive; must be gated by regression checks.
	- D is policy-sensitive and most likely to create behavior drift if changed broadly.

Required no-regression gate before sign-off:
1. af693 must keep: `2.6` Generator and `2.7` Gas Turbine flip-back.
2. b896 must keep: Steam parent inheritance for `1 Turbine`.
3. 5b must keep: parentless sole-ST fallback for `3.3.1 Turbine`.
4. 0be must keep: GG10675 discovery; no broad forced Generator reclassification of GT section 5.
5. cdd must keep: GG10525 retained and no 338X233 takeover.
6. 3f5 must keep: no SY-only ESN promotion.
7. b775/fcb/273 must improve path quality without new runtime errors.

Practical conclusion:
- The new fix set can be made safe for existing passing cases, but only with conservative implementation of A/B,
	thresholded rollout of C, and explicit policy decision before D.

Rollback control (2026-08-13):
- Repo: /home/u560060992/dbx/pw_sdg_ai_ser_repo
- Branch: fsr_v2
- Rollback pointer commit: 771ffca83a3550b29408fd0f81e9f0d773bc97a4
- Operational note: hold current state. Do not rollback and do not push unless explicitly requested by the owner.

## Finding (2026-08-19) — `_gt_flipback` allow-list in SUBSEC_GENERIC is a survival gate, not a Turbine-evidence rule

Context:
- Customer flagged the regex at ~line 818 of `preprocessor_v2.py`:
  `r'^(rotor|turbine|compressor|combustion|inlet|hot\s+gas|exhaust|bearing)\b'`
  and asked why `rotor` is used as Turbine evidence, since Rotor (field) also appears in Generator sections.

What the regex actually does:
- It is used only in a filter guardrail, not in equipment-type assignment.
- The equipment type of a SUBSEC_GENERIC candidate is always set from the nearest prior HEADER or SECTION_HDR (i.e. the parent section chain like `2 Turbine` or `4 Generator` / `GAS TURBINE (…)` / `GENERATOR (…)`).
- The default behavior of SUBSEC_GENERIC is: when the nearest parent context resolves to Generator, drop the candidate (conservative filter).
- The regex overrides that drop for titles starting with rotor / turbine / compressor / combustion / inlet / hot gas / exhaust / bearing. When it fires, the candidate is kept and typed with the parent context (Generator stays Generator; Gas Turbine stays Gas Turbine).

Empirical evidence:
- Setup: `GENERATOR (337X581) → 2 Generator → 2.1 Generator Field Winding Test → 2.2 Rotor Inspection`.
- With `rotor` in the list (current code): `2.2 Rotor Inspection` is emitted as its own region, tagged Generator / 337X581. Matches the customer's rule that Rotor (field) belongs to Generator when parent is Generator.
- Without `rotor` in the list: `2.2 Rotor Inspection` is dropped; content is absorbed into the preceding `2.1` region. The Generator rotor section is lost entirely.
- Turbine case (af693a98-style, `2 Turbine → 2.6 Generator → 2.7 Unit Rotor`): `2.7 Unit Rotor` is tagged Gas Turbine because the parent chain leads back to `2 Turbine`. The `rotor` word in the list plays no part in that decision.

Decision:
- Keep `rotor` in the allow-list; removing it would drop legitimate Generator rotor subsections.
- The inline comment above the regex currently reads "return to GT context", which is misleading and was the source of confusion. Rewrite the comment to describe the actual behavior (a keep-alive allow-list for component-named subsections; typing follows the parent chain either way).
- Open item: subsection equipment attribution in ambiguous cases (Rotor / Generator field vs Turbine rotor, cross-parent situations) is a good candidate for an LLM-based classifier layered on top of the current regex-based logic. Track this as a future enhancement rather than trying to extend the allow-list.

Regression guardrails to preserve:
- af693a98: `2.6` Generator, `2.7` Gas Turbine flip-back.
- Any Generator-parent doc with `x.y Rotor` subsections: Rotor subsections must be emitted as their own regions and tagged Generator.



## Plan (2026-08-19) — TOC cross-check to replace blanket `toc_cutoff` guard on SECTION_HDR

**Status: implemented and pushed — commit `7ec453a` on branch `fsr_v2`.**

Trigger:
- Customer flagged a regression on `4597a853-5ffb-40bb-b0be-bd6307b0acdc`: the whole 693-page doc collapses into a single synthetic `shared` region because `3 Generator` at page 11 is not detected as a SECTION_HDR. Doc-level `primary_esn` / `primary_equip_type` come out as `None`.
- Customer proposed: verify detected section headers against the TOC; if a candidate has no similar entry in the TOC, ignore it. This would also filter OCR artifacts like `3.8\nPosition` in `b775cf29`.

Root cause of 4597a853 regression:
- Commit `39e1b6d` added a `match.start() <= toc_cutoff` guard to both SECTION_HDR loops (main and page-aware fallback), where `toc_cutoff = len(full_text) // 20` (first 5% of the doc).
- For `4597a853` (701,177 chars total), `toc_cutoff` = 35,058.
- `3 Generator` in the body starts at char 12,324 (page 11), which is inside the cutoff window. The guard drops it, no SECTION_HDR candidates survive, and the region emitter falls back to a single synthetic `shared` region.
- Comparison snapshots confirm the regression pre-dates our `c6fbd30` fix:
  - `fsr-preprocessor-v2-output-8-17/` (after `39e1b6d`, before `c6fbd30`): 1 shared region.
  - `fsr-preprocessor-v2-output-8-18/` (after `c6fbd30`, current branch): 1 shared region (identical).
  - `databricks-results/after-fix-full-regression/` (earlier good baseline): 17 regions, `primary_esn=338X447`, `primary_equip_type=Generator`.
- The `toc_cutoff` heuristic is too coarse. On long FSR docs (~700 pages) the first 5% can legitimately contain body sections that begin right after front matter.

Plan for fix (implementation-ready, no further design questions):

1. Remove the blanket `match.start() <= toc_cutoff` guard from the two SECTION_HDR loops (main `full_text` scan and page-aware fallback).
2. Add a post-collection TOC cross-check filter for SECTION_HDR candidates:
   - Normalize both TOC titles and candidate titles: lowercase, collapse whitespace, strip trailing page-number tails and separators.
   - Match a candidate against TOC entries by:
     - section number equality (e.g. candidate `3 Generator` → TOC entry starting with `3` at level `-1` or `0`), AND
     - fuzzy title overlap on the remaining tokens (e.g. token-set ratio ≥ 0.6, or contains-check on the equipment/component keyword).
   - Keep the candidate if any TOC entry matches; drop otherwise.
3. Safety fallback:
   - If TOC extraction returned fewer than 5 entries, skip the cross-check entirely (fall back to today's behavior minus the `toc_cutoff` guard). Prevents catastrophic drops on docs where the TOC parser itself fails (fcb1511e returned only 1 TOC entry in a prior run).
4. Optional extension in the same PR (guarded by the same "≥ 5 TOC entries" gate): apply the same cross-check to SUBSEC_GENERIC candidates. This is where OCR artifacts like `3.8\nPosition` originate; TOC does not contain `3.8 Position`, so the artifact would be filtered.
5. Cosmetic follow-up (separate small change): rewrite the misleading comment above `_gt_flipback` in SUBSEC_GENERIC per the 2026-08-19 finding above. Keep the regex list as-is.

What we are NOT reverting:
- `c6fbd30` doc-inventory bare `N Turbine` typing stays. This is the actual `fcb1511e` fix aligned with the customer's own root-cause diagnosis. Reverting it would re-open `fcb1511e`.
- Reverts of `Rotor` in `SUBSEC_TURBINE` and Rotor-specific `_GT_FLIPBACK` from `c6fbd30` stay reverted.
- The `_gt_flipback` allow-list in SUBSEC_GENERIC stays (empirical evidence in the 2026-08-19 finding shows removing `rotor` drops legitimate Generator field rotor subsections).

Second concern from the customer (`b775cf29` `3.1.1 Generator` no ESN):
- Current branch (`8-18`) already resolves it via IBAT: `primary_esn=337X765`, `esn_source=ibat_train`, `esn_confidence=low`.
- Snippet the customer shared showing `esn_source: none` matches the older baseline or standalone-notebook output pre-IBAT wiring. The customer has agreed to double-check after lunch. No code change planned here beyond the TOC cross-check above (which will also help clean up any stale OCR-artifact regions in this doc).

Regression guardrails to preserve after this change:
- `fcb1511e`: `3 Turbine → Gas Turbine`, `3.8.6 Generator → Generator/337X581`, `3.8.7 Rotor → Gas Turbine/298464`.
- `af693a98`: `2.6 Generator`, `2.7` flip-back to Gas Turbine.
- `b896cb9f`: bare `1 Turbine` inheritance under Steam parent.
- `4597a853`: `3 Generator` at page 11 detected as SECTION_HDR; doc-level `primary_equip_type=Generator`, `primary_esn=337X765`.
- `b775cf29`: OCR artifact `3.8\nPosition` no longer appears as its own section (once SUBSEC_GENERIC cross-check is applied).

Validation:
- Add a unit test reproducing the 4597a853 scenario: bare `3 Generator` in a long doc where the char offset lands inside the previous 5% cutoff; assert the candidate survives when the TOC contains a matching entry.
- Re-run the local per-doc regression on all parsed docs in `2-FSR-v2/bug-preprocessor/new-preprocessor-issues/` and compare region counts / primary metadata against `databricks-results/after-fix-full-regression/`.

Implementation summary (2026-08-19, commit `7ec453a`):

- Added module-level helpers in `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`:
  - `_TOC_CROSSCHECK_MIN_ENTRIES = 5` — gate below which the cross-check short-circuits to True. Preserves prior behavior on docs where the TOC parser itself returns very few entries (e.g., fcb1511e returned 1 entry).
  - `_section_hdr_matches_toc(equipment_label, toc_entries, toc_equipment_anchors)` — accepts the candidate when its equipment label maps to an anchor found in the TOC. Bare `Turbine` accepted when any Turbine anchor is present.
  - `_subsec_generic_matches_toc(section_num, title, toc_entries)` — accepts the candidate when a TOC entry shares the same section branch AND overlaps title tokens on ≥ 3-char words.
- Removed the `match.start() <= toc_cutoff` guard from both SECTION_HDR loops (main `full_text` scan and page-aware fallback) and from the SUBSEC_GENERIC loop. Each is replaced with the corresponding cross-check.
- Rewrote the misleading `_gt_flipback` comment inside SUBSEC_GENERIC (per the 2026-08-19 finding). List of allowed titles kept as-is; removing `rotor` would drop legitimate Generator field rotor subsections.

Tests added (`pw_sdg_ai_ser_repo/tests/fsr_v2/test_preprocessor_v2.py`):

- `test_section_hdr_early_body_survives_via_toc_crosscheck` — synthetic 4597a853 reproduction. `3 Generator` at char ~2% (inside the old 5% cutoff) survives via TOC cross-check; asserts doc-level `primary_equip_type = Generator` and `primary_esn = 338X447` and a region anchored on `3 Generator`.
- `test_subsec_generic_ocr_artifact_filtered_when_toc_available` — b775cf29-style `3.8\nPosition` artifact where the TOC's `3.8` entry is unrelated (`3.8 Turbine Section`). Asserts no region carries a `position` element in its `section_path`.

Regression checks:

- fcb1511e (parsed_doc.json in workspace): identical to c6fbd30 output. `3 Turbine → Gas Turbine`, `3.8.6 Generator → Generator / 337X581`, `3.8.7 Rotor → Gas Turbine / 298464`. TOC has only 1 entry, so the safety fallback keeps behavior identical.
- af693a98 synthetic reproduction (`2 Turbine → 2.6 Generator subsec → 2.7 Unit Rotor`): flip-back to Gas Turbine preserved.
- Full test file: 16 pass (was 14). Same 3 pre-existing failures unchanged.

Follow-ups (open):

- Post-deploy Databricks batch rerun on the full 23-doc set from Step 4. Focus targets: `4597a853` (should restore `primary_esn=338X447, primary_equip_type=Generator` and ~17 regions per the earlier `databricks-results/after-fix-full-regression` baseline), and `b775cf29` (should no longer emit a `3.8\nPosition` artifact section; existing `3.1.1 Generator` IBAT resolution unchanged).
- customer double-check for `b775cf29 3.1.1 Generator` after lunch. Current-branch output already resolves via `ibat_train / 337X765`; the `esn_source=none` snapshot the customer shared appears to be from an older ds_test_v2 populate.

## Plan (2026-08-19, second cycle) — Options A + B follow-up on TOC cross-check

**Status: implemented locally, pending push.**

Context:
- Post-`7ec453a` regression run on Databricks showed two residual issues:
  - `4597a853-5ffb-40bb-b0be-bd6307b0acdc`: doc-level primary was restored (`Generator / 338X447`) but only 2 regions vs baseline 17, and the `3 Generator` region started at char 1227 (front-matter TOC line) instead of the body offset ~12324.
  - `b775cf29-8b42-4a83-af21-53075fef0802`: `3.8\nPosition` OCR artifact still appeared in 4 regions; SUBSEC_GENERIC TOC filter did not fire.
- Root cause of both: `_extract_toc_entries_from_pages` is too weak for real FSR TOCs. Most docs return fewer than the `_TOC_CROSSCHECK_MIN_ENTRIES = 5` threshold, so the safety fallback in the new helpers short-circuits to True and no filtering happens. Meanwhile the old `toc_cutoff` guard is gone from those loops, so front-matter TOC lines and multi-line OCR joins slip through as body candidates.

Fixes applied (this cycle):

**Option A — drop SUBSEC_GENERIC candidates whose text contains `\n`.**
Real headings never span lines. `3.8\nPosition` is definitionally a page-join OCR artifact. Adding `if '\n' in match.group(0).strip(): continue` in the SUBSEC_GENERIC loop drops the artifact regardless of TOC parsing quality. Doc-independent, no false-positive risk.

**Option B — reinstate a much smaller `toc_cutoff` as a base filter under the TOC cross-check.**
Old formula was `len(full_text) // 20` (first 5%), which trapped legitimate body sections in long docs (that's exactly why we removed it in `7ec453a`). New formula:
```python
toc_cutoff = min(len(full_text) // 50, 5000)
```
That's the first 2% of the doc, capped at 5000 chars. On `4597a853` (701K chars) that's 5000 chars, so the front-matter `3 Generator` at char 1227 is dropped while the body one at char 12324 survives. On a normal-size 200K-char doc that's 4000 chars, still comfortably before body content. Layer this guard back onto:
- both SECTION_HDR loops (main + page-aware)
- SUBSEC_GENERIC

Not restored on UNNUMBERED_EQUIP_HDR / UNNUMBERED_TITLED_HDR — those already keep their existing (larger) guard via the `REQUIRE_PRIMARY_TOC_MATCH_FOR_UNNUMBERED_EQUIP` gating.

Behavior on target docs (verified locally):

| Doc | Concern | After A + B |
|---|---|---|
| `4597a853` | `3 Generator` region started at char 1227 | Filtered by 5K guard; body candidate at ~12K survives via TOC cross-check |
| `b775cf29` | `3.8\nPosition` in 4 regions | Dropped by multi-line filter regardless of TOC parse quality |
| `fcb1511e` | Prior fix (`3.8.7 Rotor → Gas Turbine`) | Preserved (verified) |
| `af693a98` | Flip-back rule (`2.7 Rotor → Gas Turbine`) | Preserved |

Tests added (`pw_sdg_ai_ser_repo/tests/fsr_v2/test_preprocessor_v2.py`):
- `test_subsec_generic_drops_multiline_ocr_artifact_even_without_toc` — no-TOC scenario with a `3.8\nPosition` artifact. Asserts no region carries a `position` element in `section_path`.
- `test_section_hdr_toc_cutoff_still_filters_true_front_matter` — a long doc with a TOC-line `3 Generator ........... 11` inside the 5K guard and a body `3 Generator` past it. Asserts every SECTION_HDR candidate lands past the guard and a Generator SECTION_HDR is still emitted.

Notebook validation added (Validation 11 in `run-preprocessor-standalone.ipynb`):
- `4597a853` — asserts primary metadata + minimum region count + no `3 Generator` region starting inside the 5K guard.
- `b775cf29` — asserts primary metadata + no `section_path` element containing `position` or `\n`.

Full test suite: 18 pass (was 16). Same 3 pre-existing failures unchanged.

## Future work — Option C: rewrite `_extract_toc_entries_from_pages`

Deferred to a separate cycle because it is a larger, higher-risk change and needs its own validation set. Not blocking the A + B fixes above.

Motivation:
- The current extractor requires strict `title  page` or `title ..... page` line formatting and only scans pages that literally contain "Table of Contents" (falling back to pages 0-2). Real FSR TOCs are irregular: multi-column, dot-leader-free, wrapped titles, embedded sub-report TOCs, ESN-tagged section headings, etc.
- Empirical: `fcb1511e` returned 1 TOC entry, and Databricks 8-19 rerun shows most real docs fall under the `_TOC_CROSSCHECK_MIN_ENTRIES = 5` threshold. That means the TOC cross-check safety fallback is what carries most docs today — the actual filter almost never runs.

Proposed scope for the Option C cycle:
1. Detect TOC pages by leaders (rows of dots), column layouts, or dense "N Title" line patterns, not just the literal "Table of Contents" heading.
2. Handle wrapped titles (title spans two lines, page number on the second).
3. Accept dot-leader-free formats (space + right-aligned page number).
4. Filter obvious non-TOC noise (page-number-only rows, running headers).
5. Return a structured record per entry: `(section_number, normalized_title, page)` — makes cross-checks less brittle than the current `(title, page)` tuple.
6. Wire the improved extractor through the existing helpers and drop the `_TOC_CROSSCHECK_MIN_ENTRIES` safety fallback (or raise the threshold significantly) so cross-checks reliably fire.

Regression guardrails to preserve after Option C:
- `4597a853`: `3 Generator` at page 11 detected as SECTION_HDR; primary `Generator / 338X447`; ideally back to baseline 17 regions.
- `b775cf29`: no `3.8\nPosition` artifact regardless of doc-independent filters.
- `fcb1511e`: `3 Turbine → Gas Turbine`, `3.8.7 Rotor → Gas Turbine / 298464`.
- `af693a98`: `2.7 Rotor` flip-back to Gas Turbine.

## Finding (2026-08-19) — IBAT resolver is non-deterministic; over-long Generator region on `b775cf29`

Trigger:
- Customer reviewed `ESN_metadata_check_results_12ESN_0819.xlsx` (12 docs, 2109 rows, 5 mismatches total). All 5 mismatches concentrate on two docs: `4597a853` (3 rows) and `b775cf29` (2 rows).
- Follow-up the customer raised in Slack pointed at two blocks in `fsr-preprocessor-v2-output-8-19/b775cf29-8b42-4a83-af21-53075fef0802.json`:
  - Line 83 block (region `19897–55129`, `### 3.1.1 Generator`, `primary_equip_type = Generator`, `primary_esn = 337X765`, `section_path` top = `GAS TURBINE (297651 | SY0070884)`). The customer asked why the leaf equipment is Generator while the parent chain is Gas Turbine.
  - Line 61 block (region `19730–19897`, `3 Turbine`, `Gas Turbine / 297651`). The customer noted the chunk table has blank `region_primary_esn` for content in this area.

Cross-checked against three sources:
- Standalone preprocessor JSON on disk (`fsr-preprocessor-v2-output-8-19/…`, run 10:33 today).
- Pipeline metadata `ds_test_fsr_metadata_v2.preprocessor_regions` (`ingested_at` 18:58 today).
- Pipeline chunk table for `b775` (`ds_test_chunks_802.csv`, 76 rows).

### What the data actually shows

Both issues collapse to the same underlying cause plus one separate boundary bug.

**1. `3.1.1 Generator` typed as Generator is by design and matches ground truth.**
- Heading text is `Generator`; SUBSEC_GEN types it Generator; `section_path` shows the parent chain (Gas Turbine outage → `3 Turbine` → sub-inspection `3.1.1 Generator`).
- the customer's own expected labels in the ESN check spreadsheet mark pages 25–81 as `Generator / 337X765`, which is exactly what this region produces on the standalone run.

**2. Same code, same doc, different IBAT result across runs (the real defect).**
- Standalone JSON (10:33): `3.1.1 Generator` region `primary_esn = 337X765`, `esn_source = ibat_train`, `esn_confidence = low`.
- Pipeline `ds_test` (18:58): same region `primary_esn = None`, `esn_source = none`.
- All 11 Generator chunks in `ds_test_chunks_802.csv` therefore carry `region_primary_esn = ''` (blank). Not a chunker bug — `attribute_esn` in `common/fsr_v2/region_utils.py` faithfully copies whatever ESN the preprocessor stored on the region, and the region has `None`.

**3. Root cause: `_make_ibat_resolver` in `silver/src/etl/fsr_v2/metadata_processor_v2.py`.**
The SQL is:
```sql
SELECT UPPER(TRIM(equip_serial_number)) AS candidate_esn
FROM {ibat_table}
WHERE candidate_type = UPPER(TRIM('{equip_type}'))
  AND candidate_esn NOT RLIKE '^SY[0-9]{7}$'
```
It returns every Generator ESN in the reference table — thousands. `_resolve_span_esn_with_ibat_train` in the preprocessor then intersects this list with the doc's `broad_esns` (tokens matching `\d{3}[A-Z]\d{3}` that appear ≥ 3 times in the extracted text). If the intersection is a single ESN, that ESN wins. If it's zero or ambiguous, IBAT returns None.

Failure mode: if pymupdf drops one occurrence of `337X765` between two runs (or if the pipeline text scan produces slightly different token frequencies from the standalone), `broad_esns` no longer contains `337X765` and IBAT can't disambiguate. The 8-19 pipeline run is one such case.

**4. Region `3 Turbine` at line 61 is only 167 chars.**
- Chunks are ~3800 chars; `char_offset_max_overlap` always picks the adjacent 35 K-char `3.1.1 Generator` region instead. No chunk is ever attributed to `3 Turbine`. the customer's blank-ESN observation on the chunks is not about this region — it is the same 11 Generator chunks described above.

**5. Separate boundary bug on the same doc.**
- Region `3.1.1 Generator` spans 19 897–55 129 = 35 232 chars ≈ 55 pages. The next detected heading is `3.1.2 Turbine` at char 55 129 (~page 89).
- the customer's ground truth marks page 89 as Gas Turbine. The Generator region is pulling the last few pages that should have flipped back into Gas Turbine content.
- This is a heading-detection problem (missing or mis-positioned boundary before `3.1.2 Turbine`), independent of the IBAT defect.

### Cross-doc summary

- `12 docs, 2109 rows, 5 mismatches` (< 0.25 %). No broad regression.
- `4597a853` — 3 mismatches, all pages inside the front-matter guard window (`min(len // 50, 5000) = 5 000` chars for this 701 K-char doc). Marginal.
- `b775cf29` — 2 mismatches, both explained by the two items above.

### Planned fixes

**Fix 1 — Train-scoped IBAT SQL (real fix for Issue 2 and equivalents).**
Replace the "return every Generator ESN" query with a train-scoped join so the resolver deterministically returns the Generator ESN sitting on the same train as the doc's Gas/Steam Turbine ESN. Removes the dependency on `broad_esns` text-scan intersection.

Needs (from customer / Databricks team):
- IBAT table schema for `vgpd.prm_std_views.ibat_equipment_mst` — column names for train / unit / site / equipment-group linkage.
- A handful of sample rows for a mixed train that includes both `297651` (Gas Turbine) and `337X765` (Generator), so the SQL join can be validated end-to-end.

Once schema is known, target SQL shape:
```sql
SELECT UPPER(TRIM(equip_serial_number)) AS candidate_esn
FROM {ibat_table}
WHERE UPPER(TRIM(equipment_type)) = UPPER(TRIM('{equip_type}'))
  AND {train_join_column} = (
      SELECT {train_join_column}
      FROM {ibat_table}
      WHERE UPPER(TRIM(equip_serial_number)) = UPPER(TRIM('{current_turbine_esn}'))
  )
  AND UPPER(TRIM(equip_serial_number)) NOT RLIKE '^SY[0-9]{7}$'
```
Preprocessor already passes `current_turbine_esn` into the IBAT `context`; the resolver just needs to consume it in the SQL.

**Fix 2 — Boundary detection for the tail of `3.1.1 Generator` on b775cf29.**
Investigate what's between pages 82 and 89 in the pymupdf-extracted text. Options:
- A page-join OCR artifact that hides `3.1.2 Turbine` from the SECTION_HDR / SUBSEC path (similar to `3.8\nPosition` on the same doc).
- A TOC-style leader that our patterns aren't catching.
- Deferred until Fix 1 lands so we can isolate this from the IBAT noise.

**Fix 3 — 4597a853 front-matter mismatches (3 rows).**
Pages 4, 6, 7 marked expected `Generator / 338X447` sit inside the current `toc_cutoff = min(len // 50, 5000)` guard. Marginal (3 of 205 rows for this doc, 3 of 2109 overall). No plan to widen the guard yet — that would risk re-opening 4597a853's original `3 Generator` early-body regression from the previous cycle.

### Regression guardrails to preserve after Fix 1

- `b775cf29`: `3.1.1 Generator` region emitted as Generator with `primary_esn = 337X765` under both standalone and pipeline runs (deterministic).
- `fcb1511e`: `3.8.6 Generator → Generator / 337X581`; `3.8.7 Rotor → Gas Turbine / 298464`.
- `af693a98`: `2.7` flip-back to Gas Turbine.
- No new spurious ESNs on Gas-Turbine-only or Steam-Turbine-only docs.

### Status

- Waiting on the customer for IBAT table schema + sample rows on a mixed train.
- No code change committed for this finding yet.

### Fix 1 status update (2026-08-19) — train-scoped IBAT SQL implemented

Confirmed train linkage from the customer's sample rows (`2-FSR-v2/data/table-data/ibat_sample_297651_train.csv`):
- Gas Turbine `297651` and Generator `337X765` share `train_sys_id_fk = UNI036489`, same `block_sys_id_fk = BLC036453`, same `plant_sys_id_fk = 13170` — site `THOMAS A SMITH CC 2 GT-1`.
- Same pairing pattern holds for GT/Generator pairs on other trains (e.g. GT `297627` ↔ Generator `337X755` on `UNI036486`; GT `297652` ↔ Generator `337X766` on `UNI036490` — covers `af693a98` and `796f4d53` too).
- Block-level and plant-level joins are too wide (each block has 2 GT trains + 1 ST train + Generators + HRSGs). Train-level scope is exactly the right granularity.

Code changes:
- `silver/src/etl/fsr_v2/metadata_processor_v2.py`:
  - `_make_ibat_resolver` rewritten. When `context['current_turbine_esn']` is present and matches `^[A-Z0-9]{4,10}$`, resolver issues a train-scoped SQL:
    ```sql
    SELECT UPPER(TRIM(equip_serial_number)) AS candidate_esn
    FROM {ibat_table}
    WHERE UPPER(TRIM(equipment_type)) = UPPER(TRIM('<equip_type>'))
      AND UPPER(TRIM(equip_serial_number)) NOT RLIKE '^SY[0-9]{7}$'
      AND equipment_status = 'InService'
      AND record_status = 'Active'
      AND UPPER(TRIM(active_lineage_indicator)) = 'TRUE'
      AND train_sys_id_fk IN (
          SELECT train_sys_id_fk
          FROM {ibat_table}
          WHERE UPPER(TRIM(equip_serial_number)) = UPPER(TRIM('<current_turbine_esn>'))
            AND train_sys_id_fk IS NOT NULL
      )
    ORDER BY candidate_esn
    ```
  - Fallback: when the anchor turbine ESN is missing or malformed, resolver runs the wider type-only query so docs with no discoverable turbine still get a candidate list. Lifecycle filters (`InService`, `Active`, `TRUE`) apply in both branches so decommissioned equipment can never be returned.
  - Added an `^[A-Z0-9]{4,10}$` regex guard on the turbine ESN before SQL interpolation (defence in depth against unexpected payloads from doc text).

Tests added (`pw_sdg_ai_ser_repo/tests/fsr_v2/test_preprocessor_v2.py`):
- `test_ibat_resolver_issues_train_scoped_sql_with_turbine_esn` — asserts the train subquery is emitted and the anchor ESN is interpolated when context supplies it.
- `test_ibat_resolver_falls_back_when_turbine_esn_missing` — asserts the wider type-only query runs when the anchor ESN is absent.
- `test_ibat_resolver_guards_against_malformed_turbine_esn` — asserts a payload containing `DROP TABLE` does not reach the SQL and the resolver falls back to the wider query.

Local suite: 21 pass (was 18); the same 3 pre-existing failures remain unchanged.

Expected pipeline behaviour after redeploy:
- `b775cf29` — `3.1.1 Generator` region resolves deterministically to `337X765` under both standalone and pipeline runs. Chunks table `region_primary_esn` populates for all 11 Generator chunks.
- `af693a98` — Generator subsection under Gas Turbine parent resolves to `337X766`.
- `796f4d53` — flip observed by the customer becomes deterministic (Generator on train `UNI036486` = `337X755`).
- Gas-Turbine-only or Steam-Turbine-only docs are unaffected (no Generator span → resolver not called).

Status: **committed and pushed (commit `e33e92c` on `origin/fsr_v2`); validated on Databricks — `3.1.1 Generator → 337X765` via `ibat_train`, deterministic across standalone and pipeline runs.**


## Per-doc tracker — `b775cf29-8b42-4a83-af21-53075fef0802`

Single view of every finding raised for this document across the RCA cycles. Details and evidence live in the dated sections above; this table is only the pointer + status.

| # | Finding | Root cause | Fix | Status | Section reference |
|---|---|---|---|---|---|
| 1 | No Generator ESN at `3.1.1 Generator`; noisy `section_path` entries like `3.0\n8350`, `3.0\n10`; flip-back around `3.1.2` under polluted hierarchy | Broad `SUBSEC_GENERIC` regex + aggressive generic-subsection promotion converts numeric/table lines into heading candidates | Path-quality follow-ups (position-scoped inference, segment reset, numeric-density guardrails) | Design captured; deprioritized after the two doc-independent filters in Finding 2 removed most of the pollution | `## 2026-08-13 Root Cause Addendum` → Issue 1 |
| 2 | `3.8\nPosition` OCR artifact emitted as its own section in 4 regions | Page-join OCR artifact matched by `SUBSEC_GENERIC`; TOC cross-check couldn't filter because `_extract_toc_entries_from_pages` returned fewer entries than the safety threshold | (A) Drop `SUBSEC_GENERIC` candidates whose text contains `\n`; (B) reinstate a much smaller `toc_cutoff = min(len // 50, 5000)` as a base filter | **Fixed** (commit `7ec453a` for TOC cross-check + Options A/B follow-up) | `## Plan (2026-08-19) — TOC cross-check…` and `## Plan (2026-08-19, second cycle) — Options A + B follow-up…` |
| 3 | `3.1.1 Generator` region `primary_esn` non-deterministic across runs (standalone: `337X765`; pipeline: `None`) → 11 blank `region_primary_esn` rows in chunk table | `_make_ibat_resolver` returned every Generator ESN; `_resolve_span_esn_with_ibat_train` intersected with `broad_esns` which is sensitive to pymupdf token-frequency drift | Train-scoped IBAT SQL joining `ibat_equipment_mst` on `train_sys_id_fk`, with regex-guarded turbine ESN and type-only fallback; `InService`/`Active`/`active_lineage_indicator` lifecycle filters | **Fixed** — committed and validated on Databricks (`3.1.1 Generator → 337X765` via `ibat_train`, deterministic) | `## Finding (2026-08-19) — IBAT resolver is non-deterministic…` → Fix 1 |
| 4 | `3.1.1 Generator` region spans char 19 897–55 129 (~35 K chars) and reportedly pulls Gas Turbine content up to page 89 into the Generator span | Original suspects (page-join OCR artifact hiding `3.1.2 Turbine`, TOC-style leader) not confirmed. Raw pymupdf scan of the disputed range shows the entire span is Generator test content (RTD readings, insulation resistance, hipot, dielectric absorption) with no missing `3.1.x Turbine` heading. Likely a page-number mismatch between the customer's PDF viewer and the extracted-text page mapping | Pending customer clarification — need the exact page-89 excerpt (screenshot or line of text) to locate it in the extracted text before scoping a fix | **Blocked on clarification** — waiting on customer excerpt; original Fix 2 premise does not hold on the current extracted text | `## Finding (2026-08-19) — IBAT resolver is non-deterministic; over-long Generator region on b775cf29` → item **5. Separate boundary bug on the same doc** and planned **Fix 2 — Boundary detection for the tail of `3.1.1 Generator` on b775cf29** |
| 5 | `3 Turbine` region only 167 chars (19 730–19 897) → no chunk is ever attributed to it (adjacent 35 K-char Generator region always wins under `char_offset_max_overlap`) | Not a boundary bug — `3 Turbine` is a parent heading whose entire body is the immediately-following `3.1.1` subsection, so the emitter produces a region with only the heading + trace intro | (A) Suppress atomic regions for parent headings whose body is a single following subsection (merge upward into shared/nav or forward into first child); or (B) change chunk attribution to prefer nearest typed parent when tightest-overlap region has effectively-no body | **Open** — unblocked; Option A is the safer, localized fix in the region emitter | `## Finding (2026-08-19) — IBAT resolver is non-deterministic; over-long Generator region on b775cf29` → item **4. Region `3 Turbine` at line 61 is only 167 chars** |

Cross-refs:
- Cycle-1 hierarchy pollution details and evidence: [Section: `## 2026-08-13 Root Cause Addendum` → Issue 1](2-FSR-v2/bug-preprocessor/new-preprocessor-issues/rca-plan.md).
- TOC cross-check + A/B doc-independent filters: [Section: `## Plan (2026-08-19) — TOC cross-check…`](2-FSR-v2/bug-preprocessor/new-preprocessor-issues/rca-plan.md).
- IBAT resolver train-scoped SQL: [Section: `## Finding (2026-08-19) — IBAT resolver is non-deterministic…`](2-FSR-v2/bug-preprocessor/new-preprocessor-issues/rca-plan.md).

### Diagnostic note (2026-08-20) — rows 4 and 5 re-checked against the raw PDF

- Extracted-text totals via pymupdf: 244 719 chars across 325 PDF pages; the `3.1.1 Generator` region (extracted chars 19 897–55 129) covers extracted-pages 27–60.
- Scan for numbered `x.y[.z] <keyword>` headings in extracted-pages 21–65 returns only `3.1 Auxiliaries` and `3.1.1 Generator Stator/Field Tests with Borescope Inspection` (both on extracted-page 26). Everything else the raw-text regex matches inside the span is numeric table content (RTD readings, insulation resistance, hipot / dielectric absorption tables).
- No hidden `3.1.x Turbine` heading exists in the extracted text for that range — the original Fix 2 suspects (page-join OCR artifact, TOC-style leader, SUBSEC filter drop) are not the cause on the current extracted text.
- Row 5 is architectural, not a boundary bug: `3 Turbine` (chars 19 730–19 897, 167 chars) sits immediately before `3.1.1 Generator` with essentially no body of its own — the emitter is producing an atomic region for a parent heading whose entire body is the first subsection.
- Next step for row 4: obtain the customer's page-89 excerpt and search the extracted text; if a Gas Turbine line is genuinely present in the span, we'll have a concrete boundary to detect. Until then, no code change scoped.
