# FSR Mapping Evaluation

This is a separate evaluation from retrieval scoring. It measures whether FSR
region metadata is mapped to the correct ESN and equipment type. Its labels are
used to validate the filtering inputs consumed by the retrieval evaluation.

## Current scope

- Keep only 4 simple seed rows for initial review.
- Use stable label keys based on:
  - `document_id`
  - `region_start_char`
  - `region_end_char`
- Avoid chunk-id based keys because chunk IDs can change across chunking variants.

## Files

- `gold-set-template.csv`: starter gold labels (4 rows)
- `predictions-template.csv`: starter predictions file keyed by `record_id`
- `mapping_eval_runner.py`: CSV validator plus simple exact-match scorer for gold + optional predictions CSV

## Run locally

From `dbx/sdg-evals`:

```bash
python fsr/mapping-eval/mapping_eval_runner.py
```

With separate predictions CSV:

```bash
python fsr/mapping-eval/mapping_eval_runner.py \
  --gold-csv fsr/mapping-eval/gold-set-template.csv \
  --predictions-csv fsr/mapping-eval/predictions-template.csv
```

With row-level scoring export:

```bash
python fsr/mapping-eval/mapping_eval_runner.py \
  --gold-csv fsr/mapping-eval/gold-set-template.csv \
  --predictions-csv fsr/mapping-eval/predictions-template.csv \
  --row-results-csv fsr/mapping-eval/row-results.csv
```

Strict mode (non-zero exit on validation errors):

```bash
python fsr/mapping-eval/mapping_eval_runner.py --strict
```

## Optional prediction columns

The runner supports either of these two patterns:

- keep `predicted_primary_esn` and `predicted_primary_equip_type` in the gold CSV for quick local testing
- or provide a separate predictions CSV keyed by `record_id`

The runner reports simple exact-match metrics for ESN, equipment type, and joint ESN+equipment correctness.

It also reports per-true-equipment-type slices so Phase D review can see whether errors are concentrated in one equipment family.

If `--row-results-csv` is provided, the runner also writes one row per `record_id` with prediction values, match flags, and a compact `score_status` for manual review.

## Next after review

1. Review the 4 seed rows and confirm the selected regions are label-worthy.
2. Expand to 10-20 rows with mixed single-ESN and multi-ESN documents.
3. Wire real prediction outputs into the optional `predicted_*` columns.
