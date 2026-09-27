# TIL LLM Token Settings Eval

## Problem Statement
Find the max_tokens setting that is best for TIL extraction.

"Best" means:
- JSON is complete and parseable
- extraction quality is stable against DS gold profiles
- latency and cost are still acceptable

## Why This Eval Is Needed
### 1) Too-low max_tokens can truncate JSON
- Example TIL: 1937-R2
- Seen behavior: parse errors like Unterminated string at high character offset
- Meaning: response is cut before JSON completes

### 2) Gateway/default token behavior can vary by run
- Example TILs: 1502-2R1, 1937-R2
- Seen behavior in some runs: no usable content returned
- Meaning: extraction can fail even when prompt is unchanged

## Core Question
Which max_tokens value should we standardize for TIL profile extraction?

## Experiment Setup
Run the same TIL set across multiple max_tokens values.

Suggested first pass:
1. 1024
2. 2048
3. 3072
4. 4096
5. gateway_default (control)

Use consistent labeling in RUN_SPECS so comparison is direct:
- t1024=run_id:<run_id_for_1024>
- t2048=run_id:<run_id_for_2048>
- t3072=run_id:<run_id_for_3072>
- t4096=run_id:<run_id_for_4096>
- gateway=run_id:<run_id_for_gateway_default>

## Metrics To Compare
For each token setting, compare:
1. completed_rate
2. parse_failed
3. content_filtered
4. quality_pass_rate
5. avg_quality_score
6. gold_coverage_rate

Optional secondary metrics (from base pipeline runs):
1. latency
2. token usage/cost

## Selection Rule
Pick the best max_tokens value using this order:
1. Highest completed_rate
2. Highest quality_pass_rate
3. Lowest parse_failed
4. Lowest content_filtered
5. Highest avg_quality_score

If two values are effectively tied, pick the lower max_tokens value for cost/latency efficiency.

## Databricks Notebook Usage
Open notebook:
- /Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals/til/eval_llm_token_settings

Set widgets:
- METADATA_TABLE: your metadata table name
- RUN_SPECS: semicolon-separated label=selector entries
- TILS: comma-separated TIL IDs (for this run: 1502-R1,1937-R2,1945-R2,2284)
- GOLD_ROOT: /Workspace/Users/madhurima.saxena@gevernova.com/sdg-evals/til/til-profile-gold-set
- MLFLOW_EXPERIMENT: /Shared/til-token-setting-eval

Example RUN_SPECS:

```
t1024=run_id:til_p1_20260703_t1024;
t2048=run_id:til_p1_20260703_t2048;
t3072=run_id:til_p1_20260703_t3072;
t4096=run_id:til_p1_20260703_t4096;
gateway=run_id:til_p1_20260703_gateway
```

Alternative selector format:

```
where:<sql expression>
```

## Outputs
The notebook logs:
- summary and detail tables in notebook cells
- MLflow metrics/params in the experiment run
- downloadable artifacts under reports:
  - summary.csv
  - detail.csv
  - run_config.json

---

## Experiment Results (2026-07-04)

### TIL Set
1502-2R1, 1937-R2, 1945-R2, 2284

### Settings Compared
| Setting | pipeline_run_id |
|---|---|
| 32000 tokens | til_p1_20260704_091213_e4003ff0 |
| gateway_default | til_p1_20260704_154439_992cd191 |

### Results Summary

| Setting | completed_rate | quality_pass_rate | avg_quality_score | parse_failed |
|---|---|---|---|---|
| 32000 | 1.0 | 1.0 | 3.0 | 0 |
| gateway_default | 1.0 | 1.0 | 3.0 | 0 |

All 4 TILs passed all 3 quality checks (til_number, title, service_recommendation_line_items) for both settings.

### Key Findings
1. `response_format={"type":"json_object"}` was blocking all completions — removed.
2. With that fix, both settings completed 100% with perfect quality scores.
3. Gateway default extracted full document text (35k chars) vs 12k chars with explicit token caps.
4. Exact recommendation text matching is too strict for free-text fields — loosened to presence-only check.

### Decision

**Use gateway default (blank TIL_LLM_MAX_TOKENS widget) for production.**

Reasons:
- Same quality as 32000 token setting.
- Uses full document input (35k chars) rather than truncated input.
- Avoids maintaining a specific token cap that may need retuning per model version.
- No parse failures observed.

### Production Config
- `TIL_LLM_MAX_TOKENS`: leave blank (gateway default)
- `TIL_LLM_USE_GATEWAY_DEFAULT_MAX_TOKENS`: true (default, no change needed)
- `TIL_MAX_CHARS_PER_PDF`: 40000 (default, no change needed)

## Final Outcome Expected
At the end of this experiment, we should publish one recommended production max_tokens value for TIL extraction, with evidence from MLflow metrics and gold comparison results.

## Next Step (Do This Now)
1. Create five pipeline runs using the same TIL list, only changing max_tokens:
  - 1024
  - 2048
  - 3072
  - 4096
  - gateway default
2. Capture the run_id from each run.
3. Open the Databricks notebook and set widgets:
  - METADATA_TABLE = your metadata table
  - RUN_SPECS = `t1024=run_id:<id>;t2048=run_id:<id>;t3072=run_id:<id>;t4096=run_id:<id>;gateway=run_id:<id>`
  - TILS = same TIL list used in all five runs
  - GOLD_ROOT = existing gold-set path
  - MLFLOW_EXPERIMENT = /Shared/til-token-setting-eval
4. Run all cells in order.
5. In MLflow, compare the five variants using the selection rule in this doc and finalize one production max_tokens value.

## Definition of Done
- One max_tokens value is selected for production.
- Selection is backed by MLflow metrics from the five-way comparison.
- Artifacts (summary.csv, detail.csv, run_config.json) are available in the run for sharing.