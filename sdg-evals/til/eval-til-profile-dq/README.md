# TIL Profile Data Quality Eval

## Problem

The TIL pipeline extracts structured profiles from PDF documents using an LLM.
This eval measures how accurately those extracted profiles match DS/SME-reviewed gold profiles — field by field, across all 39 schema fields.

The goal is to detect:
- Fields that are consistently empty when DS had content (coverage gaps)
- Fields where content differs from the gold (quality mismatches)
- Identity-critical fields (til_number, revision, title) that must match exactly

## Gold Set

DS team reviewed TIL profiles are stored in:
`sdg-evals/til/til-profile-gold-set/data/<TIL_ID>/profile_response.json`

Each file contains `parsed_profile` — the DS/SME-validated extraction result.

Gold set currently covers: 1502-2R1, 1937-R2, 1945-R2, 2284.

The full DS pilot set (25 TILs) is available at:
`1-TILs/analysis/ds-team-til-profile-results/til_profile_pilot_20260609_110447/`

## Metrics

Per TIL:
- `match_rate` — fraction of fields matching gold (0.0–1.0)
- `identity_pass` — True if til_number, revision, title all match

Per field (across all TILs):
- `pass_rate` — fraction of TILs where this field matched gold
- `coverage_gaps` — count of TILs where DS had a value but pipeline returned empty

Overall (logged to MLflow):
- `avg_field_match_rate`
- `identity_pass_rate`
- `total_coverage_gaps`
- `field_<name>_pass_rate` per field
- `field_<name>_coverage_gaps` per field (only when > 0)

### Match Types (in mismatches.csv)

| match_type | Meaning | Action |
|---|---|---|
| `coverage_gap` | DS has value, pipeline is empty | Flag — content is missing |
| `content_differs` | Both have content but differ | Review — may be acceptable wording difference |
| `pred_only` | Pipeline has value, DS is empty | Not a flag — we may extract more |
| `exact_match` / `both_empty` | Agrees | No action |

## How to Use

1. Run the TIL metadata pipeline to generate a pipeline run:
   - Notebook: `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata`
   - Note the `pipeline_run_id` from MLflow params (format: `til_p1_...`)

2. Open the eval notebook in Databricks:
   `/Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals/til/eval-til-profile-dq/eval_profile_quality`

3. Set widgets:
   - `METADATA_TABLE`: `vaid.ai_sot_field_service_report.til_metadata`
   - `RUN_SPEC`: `run_id:<your_til_p1_run_id>`
   - `TILS`: `1502-2R1,1937-R2,1945-R2,2284`
   - `DS_GOLD_ROOT`: `/Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals/til/til-profile-gold-set`
   - `MLFLOW_EXPERIMENT`: `/Shared/til-profile-quality-eval`

4. Run all cells.

5. Review outputs:
   - Cell display: per-TIL summary and per-field pass rates sorted by worst first
   - MLflow: field-level metrics and overall match rates
   - Artifacts under `reports/`:
     - `summary.csv` — per-TIL match rates
     - `field_pass_rates.csv` — per-field pass rates and coverage gap counts
     - `mismatches.csv` — full field values for every mismatch (untruncated)
