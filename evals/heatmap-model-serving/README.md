# Heatmap Model Serving Test Instructions

This runbook is for testing the Case 2 heatmap eval serving endpoint.

## Preconditions

1. Endpoint is in Ready state.
2. Endpoint points to the latest registered model version.
3. Endpoint environment variables are set:
   - DATABRICKS_HOST: workspace host only (no https://)
   - DATABRICKS_TOKEN: PAT token value (or secret reference)
   - DATABRICKS_SQL_HTTP_PATH: SQL warehouse HTTP path
4. Baseline table exists:
   - vaid.ai_std_con_field_service_report.vec_risk_matrix

## Request format

The serving API expects one top-level input wrapper.
Use dataframe_records.

```json
{
  "dataframe_records": [
    {
      "candidate_table": "vaid.ai_std_con_field_service_report.vec_risk_matrix",
      "baseline_table": "vaid.ai_std_con_field_service_report.vec_risk_matrix",
      "experiment_name": "/Shared/heatmap_case2_eval",
      "equipment_types": "GEN,GT",
      "personas": "REL,OE",
      "sample_size": 10,
      "tags": {
        "trigger": "smoke_test",
        "case": "case2"
      }
    }
  ]
}
```

## Smoke test payload (same table)

Use this first to validate endpoint wiring.
Expected metrics: overlap_precision = 1.0, overlap_recall = 1.0, overlap_jaccard = 1.0.

```json
{
  "dataframe_records": [
    {
      "candidate_table": "vaid.ai_std_con_field_service_report.vec_risk_matrix",
      "baseline_table": "vaid.ai_std_con_field_service_report.vec_risk_matrix",
      "experiment_name": "/Shared/heatmap_case2_eval",
      "equipment_types": "GEN,GT",
      "personas": "REL,OE",
      "sample_size": 10,
      "tags": {
        "trigger": "smoke_test",
        "case": "case2"
      }
    }
  ]
}
```

## Compare test payload (candidate vs baseline)

Use this when you have a real candidate table.

```json
{
  "dataframe_records": [
    {
      "candidate_table": "vaid.ai_std_con_field_service_report.vec_risk_matrix_candidate",
      "baseline_table": "vaid.ai_std_con_field_service_report.vec_risk_matrix",
      "experiment_name": "/Shared/heatmap_case2_eval",
      "equipment_types": "GEN,GT",
      "personas": "REL,OE",
      "sample_size": 100,
      "tags": {
        "trigger": "manual_compare",
        "case": "case2"
      }
    }
  ]
}
```

If vec_risk_matrix_candidate does not exist yet, create it first:

```sql
CREATE TABLE IF NOT EXISTS vaid.ai_std_con_field_service_report.vec_risk_matrix_candidate AS
SELECT *
FROM vaid.ai_std_con_field_service_report.vec_risk_matrix;
```

## Expected response shape

```json
{
  "predictions": [
    {
      "run_id": "<mlflow-run-id>",
      "experiment_name": "/Shared/heatmap_case2_eval",
      "candidate_table": "<candidate>",
      "baseline_table": "<baseline>",
      "metrics": {
        "candidate_rows": 0,
        "baseline_rows": 0,
        "overlap_rows": 0,
        "added_rows": 0,
        "removed_rows": 0,
        "overlap_precision": 0.0,
        "overlap_recall": 0.0,
        "overlap_jaccard": 0.0,
        "elapsed_ms": 0
      }
    }
  ]
}
```

## Validate in MLflow

1. Open experiment /Shared/heatmap_case2_eval.
2. Search for returned run_id.
3. Check:
   - Params: candidate_table, baseline_table, equipment_types, personas
   - Metrics: overlap and row count metrics
   - Tags: compute_engine (spark or sql_warehouse_fallback)
   - Artifacts: case2 JSON output

## Common errors and fixes

1. Invalid JSON input
   - Fix tags object quoting, or send tags as a JSON object.

2. Input wrapper error
   - Use dataframe_records at top level.

3. SQL warehouse fallback requires host/token/http path
   - Set DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_SQL_HTTP_PATH on endpoint.

4. Invalid access token or unsupported credential
   - Use PAT token value (not token ID), same workspace as host and warehouse.

5. Table not found
   - Verify candidate and baseline table names in UC schema.

6. issue_name unresolved
   - Use latest model version with schema-aware SQL fallback logic.

## Semantic checks (quality beyond overlap)

Current checks are structural overlap checks. Semantic checks answer whether results are correct in meaning.

### What to add

1. Golden dataset
  - Create SME-backed rows with expected semantic outcomes (issue category, component, risk label, optional rationale).

2. Embedding similarity checks
  - Compare candidate output text vs expected text using cosine similarity.
  - Track average and percentile similarity.

3. Label-level correctness checks
  - For categorical outputs, log precision, recall, and F1 for labels (issue type, component, risk bucket).

4. Ranking quality checks
  - If output is ranked, log Recall@K, MRR, and nDCG@K.

5. LLM-as-judge checks
  - Use a fixed rubric and deterministic prompt to score relevance, factual consistency, completeness, and actionability.

6. Failure taxonomy
  - Tag errors (wrong component, missing key risk, generic answer, unsupported claim) so regressions are diagnosable.

### Recommended rollout

1. Start with one semantic metric
  - Embedding similarity plus one label metric.

2. Add LLM judge on sampled rows
  - Start sampled to control cost.

3. Add promotion gates
  - Example: block rollout if semantic pass rate drops below threshold.

### How this fits current Case 2 flow

1. Keep existing overlap metrics as retrieval-coverage checks.
2. Add semantic metrics side-by-side in the same MLflow run.
3. Use both signals for go/no-go: structural consistency plus semantic correctness.

### Important limitation today

Current implementation logs structural overlap metrics only. Semantic scoring is a planned extension.
