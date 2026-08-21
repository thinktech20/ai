# Bug 3337X75 - ESN/Document Mapping Analysis

## Scope

Compared expected mapping in `ground-truth` with current state from:
- `table-data-in-dev/fsr_metadata_v2.csv`
- `table-data-in-dev/fsr_document_equipment_map_v2.csv`

Reviewed notes from `Bugs_prepared_by_Xujin.csv` and traced mapping logic in `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py`.

## Current State Derived From Table Snapshots

### Expected set from ground-truth

1. `9e279e5a-a24e-4ebd-a79e-5aa24efebd04` -> (`337X766`, sibling `337X766`)
2. `af693a98-1e5c-499d-aa10-cccc54885c64` -> (`337X766`, sibling `337X766`)
3. `796f4d53-a8ad-42e1-af4d-53a8add2e1a4` -> (`337X766`, sibling `297627`)
4. `806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report` -> (`337X766`, sibling `297652`)
5. `b775cf29-8b42-4a83-af21-53075fef0802` -> (`337X765`, sibling `337X765`)
6. `cc9fe3d7-87cc-4687-9fe3-d787cc3687b3` -> (`337X765`, sibling `297651`)

### Current table state highlights

- `b775cf29-8b42-4a83-af21-53075fef0802`
  - metadata: `primary_esn=297651`, `primary_equip_type=Gas Turbine`, `gen_esn=337X766`
  - map rows: `297651/Gas Turbine (primary=true)`, `337X766/Generator (primary=false)`
  - expected set includes `337X765`, but current generator ESN is `337X766`

- `af693a98-1e5c-499d-aa10-cccc54885c64`
  - metadata: `primary_esn=297652`, `primary_equip_type=Gas Turbine`, `gen_esn=337X766`
  - map rows: `297652/Gas Turbine (primary=true)`, `337X766/Generator (primary=false)`

- `cc9fe3d7-87cc-4687-9fe3-d787cc3687b3`
  - metadata: `primary_esn=297651`, `primary_equip_type=Gas Turbine`, `gen_esn=337X765`
  - map rows: `297651/Gas Turbine (primary=true)`, `337X765/Generator (primary=false)`

## Xujin Notes Relevant to This Issue

From `Bugs_prepared_by_Xujin.csv`:

- For `b775cf29-8b42-4a83-af21-53075fef0802`:
  - "The generator section is detected, but assigned to another wrong Gen ESN that appears in the body context"

This matches what we see in current tables (`gen_esn=337X766` instead of expected `337X765` for this bug case).

## Root Cause in Preprocessor

### Observed logic issue

In `preprocessor.py`, when multiple active ESNs exist for the same equipment type, ESN selection could fall back to lexical sorting (first item in `sorted(active)` for that type). That can select a wrong ESN that happens to appear in body text.

This is especially risky for reports that mention a sibling or nearby unit ESN in body sections.

### Why this causes the bug

For the affected doc, both generator-like ESNs can appear in parsed text, but only one should be the generator anchor for section mapping in that document. Lexical fallback is not context-aware and can pick the wrong generator ESN.

The Databricks run for Case 1 showed the more specific failure mode:

- `337X765` is present in parsed body text as `Equipment Generator No.: 337X765`
- that text shape was not recognized by the existing Generator ESN label patterns
- because `337X765` never became a typed Generator ESN candidate, the preprocessor kept `337X766` as the only recognized Generator anchor
- as a result, the Generator region covering the `337X765` content was still tagged with `337X766`

## Fix Applied

Updated `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py` to recognize the missing Generator ESN body-text pattern:

- added Generator label detection for `Equipment Generator No.: 337X765`
- this is the change that fixed the reported document

Also improved per-type ESN anchor selection using evidence precedence:

1. If only one active ESN exists for a type -> use it.
2. If multiple active ESNs for a type:
   - prefer ESN candidates seen in title context (first pages / title labels)
   - then prefer most frequent + earliest ESN from explicit boundary header matches
   - only then fallback to lexical sort for determinism

This anchor-selection change is a broader safeguard for other multi-ESN cases. It was not the decisive fix for this document, because `337X765` does not appear in the title or section headers here.

## Regression Safety Assessment

Why this is low-risk:

- Single-ESN-per-type docs: behavior unchanged.
- Multi-ESN same-type docs: now based on stronger contextual evidence (title/header frequency) instead of string ordering.
- Final lexical fallback is still retained for deterministic behavior in rare ties.
- No changes to region slicing math, signature scoring, or output schema.

Potential edge case to monitor:

- If title metadata itself is incorrect/noisy, title-priority may still mislead. Boundary-frequency fallback should reduce this risk, but run validation on a mixed sample set.

## Notebook Updated for Databricks Repro

Updated:
- `pw_sdg_ai_ser_repo/validation/fsr_v2/preprocessor/run-preprocessor-standalone.ipynb`

Changes:
- Added two bug-focused test cases:
  - Case A: `af693a98-1e5c-499d-aa10-cccc54885c64`
  - Case B: `b775cf29-8b42-4a83-af21-53075fef0802`
- Added `selected_case_index` switch (`0` or `1`)
- Added expected ESN list per case for easier manual verification snippets

## Databricks Validation Result - Case 0

Case 0 run details:

- document: `af693a98-1e5c-499d-aa10-cccc54885c64`
- metadata:
  - `primary_esn=297652`
  - `primary_equip_type=Gas Turbine`
  - `gt_esn=297652`
  - `gen_esn=337X766`
  - `all_esns=297652, 337X766`
- regions: 34

Interpretation:

- This case still resolves to a mixed GT + Generator document, with GT as the document primary and Generator sections assigned to `337X766`.
- The title-page snippets confirm both ESNs are present near the start of the document, and the region list shows multiple Generator ranges explicitly assigned to `337X766`.
- That means the current change did not regress this case.
- This case does **not** reproduce the wrong-generator-anchor problem described by Xujin for document `b775cf29-8b42-4a83-af21-53075fef0802`.

Working conclusion after Case 0:

- Case 0 looks behaviorally consistent with the current table snapshot.
- The remaining critical validation is Case 1, where the bug report specifically says the Generator section is assigned to the wrong Generator ESN from body context.
- If Case 1 now emits `gen_esn=337X765`, that would confirm the targeted fix is working without regressing Case 0.

## Databricks Validation Result - Case 1

Case 1 run details before the follow-up fix:

- document: `b775cf29-8b42-4a83-af21-53075fef0802`
- metadata:
  - `primary_esn=297651`
  - `primary_equip_type=Gas Turbine`
  - `gt_esn=297651`
  - `gen_esn=337X766`
  - `all_esns=297651, 337X765, 337X766`
- regions: 32

Interpretation:

- `337X765` is visible in the parsed document and appears inside the Generator-assigned region.
- That region is still tagged with `primary_esn=337X766`, which confirms the Generator section detection is present but the Generator ESN anchor is wrong.
- `337X765` already appears in `all_esns`, so the issue is not broad ESN visibility. The issue is missing Generator label classification for that body-text format.

Follow-up change applied after this validation:

- Added explicit Generator ESN regex support for `Equipment Generator No.: <ESN>` in `preprocessor.py`
- Synced the updated preprocessor module to Databricks

Expected result on rerun:

- `gen_esn` should switch from `337X766` to `337X765`
- the Generator region covering the `337X765` snippet should be tagged with `primary_esn=337X765`

## Final Validation Result

Post-sync and post-reload rerun for Case 1 now shows the expected behavior:

- `gen_esn=337X765`
- `all_esns=297651, 337X765`
- active equipment emitted as `297651 (Gas Turbine), 337X765 (Generator)`
- the region covering the `337X765` snippet is now tagged with `primary_esn=337X765`

Conclusion:

- The bug is fixed for the reported failing document `b775cf29-8b42-4a83-af21-53075fef0802`.
- Case 0 remained stable, so the targeted change did not show a regression on the comparison case.
- The notebook rerun also confirms that Databricks picked up the synced code once the module reload path was added.

Additional confirmation from the final Case 0 rerun:

- `primary_esn=297652`
- `gen_esn=337X766`
- `all_esns=297652, 337X766`
- Generator regions remained assigned to `337X766`
- Gas Turbine regions remained assigned to `297652`

This confirms the final fix preserved the expected mixed-document behavior for `af693a98-1e5c-499d-aa10-cccc54885c64` while correcting the failing Case 1 document.

## PR Summary

Fixes incorrect Generator ESN assignment in FSR v2 preprocessor for documents where the Generator ESN appears in body text as `Equipment Generator No.`.

Changes included:

- improved same-type ESN anchor selection so typed title/header evidence is preferred over lexical fallback
- added Generator ESN detection for `Equipment Generator No.: <ESN>` body-text format
- updated the standalone validation notebook to run the exact bug cases and reload the synced preprocessor in Databricks sessions

Validation completed:

- failing document `b775cf29-8b42-4a83-af21-53075fef0802` now emits `gen_esn=337X765` and assigns the Generator region correctly
- comparison document `af693a98-1e5c-499d-aa10-cccc54885c64` remains stable with expected GT/Generator mapping

## What to Run in Databricks

1. Open the notebook and set `selected_case_index`.
2. Run all cells top-to-bottom.
3. Capture these outputs:
   - `metadata` block (`primary_esn`, `gt_esn`, `gen_esn`, `all_esns`)
   - region list count and region metadata samples
   - optional token snippet outputs for expected ESNs

Once those outputs are shared, we can confirm whether data-readiness mapping now aligns with expected document-to-ESN mapping before promoting.
