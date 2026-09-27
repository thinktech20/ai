# SDG Evals

## Purpose of this repo

This repo contains lightweight evaluation workflows for SDG use cases.
The goal is to measure quality and regressions using repeatable runs, not ad hoc checks.

It currently focuses on three practical eval tracks:
- FSR retrieval coverage
- TIL max-token setting
- TIL profile quality vs gold data

## MLflow in this repo

MLflow is used as the experiment system for all evals.

In this context, MLflow is used to:
- log run parameters (for example knob values, dataset/probe version)
- log metrics (quality/coverage/stability)
- store artifacts (summary and detail reports)
- compare baseline vs candidate runs in one place

This gives an auditable history of what changed and what improved or regressed.

## Three evals

### 1) FSR retrieval eval
Problem:
For each ESN, how many FSRs are retrieved compared to how many are known to exist?

What it measures:
- `avg_retrieved_vs_exists_ratio`
	- How measured: for each probe ESN, `retrieved_known_fsr_count / known_fsr_count`, then averaged across probes.
- `avg_retrieved_known_fsr_count`
	- How measured: overlap count between retrieved doc IDs and known doc IDs per probe, then averaged.
- run stability (`probes_succeeded`, `probes_failed`)
	- How measured: count of successful probe queries vs failed probe queries in the run.

Scope:
- Uses a fixed probe set table for fair baseline vs candidate comparison.
- Tunes retrieval knobs like `top_k` and `max_per_doc`.

Reference:
- `sdg-evals/fsr/README.md`

### 2) TIL max-token eval
Problem:
What max-token setting gives complete, reliable extraction without unnecessary latency/cost?

What it measures:
- completion and parse stability (`completed_rate`, `parse_failed`)
	- How measured: `completed_rate = completed / total`; `parse_failed` is count of outputs that fail JSON parsing.
- extraction quality (`quality_pass_rate`, `avg_quality_score`, `gold_coverage_rate`)
	- How measured: per-run comparison against gold checks; pass rate, average quality score, and gold content coverage are aggregated across the same TIL set.

Current grounded outcome in notes:
- after fixing response-format behavior, gateway default and explicit high token setting both passed quality checks for the tested set
- recommendation captured in notes: use gateway default for production unless new evidence changes that

Reference:
- `sdg-evals/til/eval-max-token/eval-llm-token-settings.md`

### 3) TIL profile quality vs gold dataset
Problem:
How closely does pipeline output match DS/SME-reviewed gold profiles across schema fields?

What it measures:
- per-TIL match rate and identity pass
	- How measured: `match_rate = matched_fields / total_fields` per TIL; `identity_pass` checks critical identity fields (`til_number`, `revision`, `title`).
- per-field pass rate and coverage gaps
	- How measured: for each field across TILs, pass rate is matched/total; coverage gap is when gold has value and prediction is empty.
- overall quality metrics in MLflow (`avg_field_match_rate`, `identity_pass_rate`, `total_coverage_gaps`)
	- How measured: aggregate rollups from the per-TIL and per-field comparisons.

Reference:
- `sdg-evals/til/eval-til-profile-dq/README.md`

## How these evals are used

1. Baseline and candidate comparison
- Run baseline with current settings.
- Run candidate with one controlled knob change.
- Compare in MLflow on the same dataset/probe slice.

2. Fast regression checks after changes
- After retrieval, prompt, or extraction changes, run the relevant eval.
- Confirm no regressions before wider rollout.

3. Decision support
- Use metric deltas to choose settings (for example retrieval caps, token policy).
- Keep run artifacts for review and communication.

4. Path to automation
- Current mode is notebook-driven with MLflow logging.
- Once stable, these evals can be promoted to scheduled job runs for periodic regression monitoring.
