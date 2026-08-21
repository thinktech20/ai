# Final Validation Summary (Current Candidate Guardrail)

## Scope Executed
- Local before/after validation:
  - `af693a98-1e5c-499d-aa10-cccc54885c64`
  - `fcb1511e-596a-4a56-b151-1e596afa569c`
  - `5b688732-39f2-48d2-a887-3239f258d28b` (pymupdf + pypdf2)
- Databricks full batch regression:
  - 20 requested IDs processed through batch runner.

## Databricks Batch Outcome
- Summary file:
  - `analysis-output/databricks-results/after-fix-full-regression/_batch_summary.json`
- Status counts:
  - `ok`: 17
  - `skipped_missing_in_volume`: 3
  - `error`: 0
- Skipped (missing in volume roots):
  - `35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270t483-final_master_report`
  - `3e91b865-2aaa-4233-ae4a-3e15ba641f96_605007134-180498-270t483-final_master_report`
  - `806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report`

## Target Behavior Check (af693)
- `2.6 Generator Mechanical Scope`
  - Before: `Generator / 337X766`
  - After: `Generator / 337X766`
- `2.7 Unit Rotor`
  - Before: `Generator / 337X766` (`parent_inherit`)
  - After: `Gas Turbine / 297652` (`single_type`)

Result: target flip-back behavior is corrected as intended.

## Regression Signal
- No runtime errors in the 17 executed Databricks docs.
- Local companion docs (`fcb`, `5b`) retained stable primary metadata, with no catastrophic drift.
- Remaining risk is limited to the 3 skipped docs due to source availability in mounted volume roots (not logic failure).

## Artifacts
- Local comparison summary:
  - `analysis-output/comparisons/local-before-after-summary.json`
- Databricks regression report:
  - `analysis-output/comparisons/databricks-regression-report.json`
- This summary:
  - `analysis-output/comparisons/final-validation-summary.md`

## Recommendation
Proceed with this guardrail as the candidate fix. If needed, run a follow-up batch once the 3 skipped documents are available in Databricks volume roots.
