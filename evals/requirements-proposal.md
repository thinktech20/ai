# Requirements Proposal: Evaluation and Test Harness

## Core Requirements

1. Lightweight loop for fast iteration.
Easy to tweak prompts/config and quickly see whether output quality improved or regressed.

2. Ability to validate at larger scale.
Support larger datasets so improvements hold beyond a few manual checks.

3. Periodic and automated runs.
Support scheduled runs and trigger-based runs after meaningful changes, not just one-off manual checks.

## Definitions

1. Lightweight mode.
MLflow-based evaluation loop with quick setup and fast compare cycles.

2. Heavyweight mode.
Production-like flow using the existing SDG test harness app (Vince's app) for high-fidelity end-to-end checks.

## Test and Evaluation Case Types

1. Regression checks after agent changes.
Make changes in URA/OSA (or similar flows) and quickly measure impact.

2. Self-serve heatmap experimentation.
Use a model serving endpoint backed by MLflow to run controlled heatmap evaluations, compare before vs after, and avoid changing the current app read path.

3. Golden dataset comparison.
Run against SME-backed ground truth and track match quality over time.

4. Rapid prototyping of new methods.
Try alternate evaluation or prompting methods quickly, and keep what is good enough to operationalize.

## Proposed Approach by Requirement

1. Req 1 (Lightweight loop).
Use MLflow experiments as the primary lightweight path.

2. Req 2 (Scale validation).
Use MLflow experiments with dataset versions (small, medium, large), compare baseline vs candidate, and track key metrics per run.

3. Req 3 (Automation).
Define standard experiment jobs and schedule selected jobs for periodic regression checks.

## Direct Answers to Open Questions

1. How req 2 can happen with MLflow experiments.
Use one experiment per use case, version datasets, run baseline and candidate under the same conditions, and compare metrics over time.

2. Can retriever call real Unit Risk API like Vince's flow.
Yes. Support two retriever modes:
- live_api mode for production fidelity (calls real data service/risk API)
- snapshot mode for fast and stable iteration using stored chunks

## Proposed Approach by Case Type

1. Case 1: Regression checks after agent changes.
Two paths:
- Lightweight path:
	- Reuse current retriever logic from URA (FSR and ER)
	- Run against snapshot data (FSR and ER chunks)
	- Execute MLflow evaluators: fsr_eval, er_eval
- Heavyweight path:
	- Use the existing SDG test harness app for end-to-end validation

2. Case 2: Self-serve heatmap experimentation.
- Current-state constraint:
	- URA app heatmap path reads the risk-matrix view and does not use heatmap vector-search index today.
	- Therefore, Case 2 should be additive and must not break or replace the existing read path.
- Proposed serving design (MLflow-first):
	- Package a small evaluator model as an MLflow pyfunc (or equivalent MLflow model flavor).
	- Deploy it as a Databricks Model Serving endpoint dedicated to heatmap eval.
	- Endpoint responsibility is evaluation orchestration, not production heatmap serving.
- Endpoint contract (minimum):
	- Input: candidate configuration, baseline reference (optional), dataset/version id, run metadata.
	- Output: MLflow run id, key metrics summary, artifact links (detailed diffs, failure slices).
- Data path for Case 2 runs:
	- Read heatmap candidate and baseline from approved Delta/view sources.
	- Compute metrics via heatmap_eval logic.
	- Log full run, params, metrics, and artifacts to MLflow.
- Rollout plan:
	- Phase 1: Offline MLflow job only (no endpoint), validate metrics and schemas.
	- Phase 2: Expose serving endpoint that triggers the same evaluator and returns run summary.
	- Phase 3: Add lightweight UI/CLI trigger for self-serve usage.
- Guardrails:
	- Keep serving endpoint isolated from URA runtime APIs.
	- Enforce dataset/version pinning and environment tags for reproducibility.
	- Define strict timeout, input validation, and cost caps for on-demand runs.

3. Case 3: Golden dataset comparison.
- Run MLflow evaluators against SME-backed ground truth
- Proposed evaluators: fsr_eval_goldset_comparison, er_eval_goldset_compare, heatmap_eval_goldset_compare

4. Case 4: Rapid prototyping of methods.
- Use MLflow for ad hoc experiments as needed
- Promote only methods that show consistent gains on target metrics

## Minimum Metric Set (Initial)

1. Ground-truth match rate
2. Parse success rate
3. Drift/consistency across repeated runs
4. Latency (p50/p95)
5. Cost per run

## Open Items to Finalize

1. Dataset size bands for small/medium/large validation
2. Trigger policy for automated runs (schedule, PR, release)
3. Pass/fail thresholds for promotion from lightweight to heavyweight validation