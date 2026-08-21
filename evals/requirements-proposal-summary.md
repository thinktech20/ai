# Evaluation Harness Proposal Summary

## Core Requirements

1. Lightweight loop for fast iteration
Easy to tweak prompts or config and quickly see whether quality improved or regressed.

2. Ability to validate at larger scale
Run on larger datasets so results hold beyond a few manual checks.

3. Periodic and automated runs
Support scheduled or trigger-based checks, not just one-off testing.

## Definitions

1. Lightweight mode
MLflow-based evaluation loop for quick comparison and fast iteration.

2. Heavyweight mode
Production-like validation using Vince's existing SDG test harness.

## Evaluation / Test Case Types

1. Regression checks after agent changes
Measure impact after changes in URA, OSA, or similar flows.

2. Self-serve heatmap experimentation
Upload or modify heatmap inputs directly and compare before vs after.

3. Golden dataset comparison
Run against SME-backed ground truth and track quality over time.

4. Rapid prototyping of new methods
Try alternate approaches quickly and keep what is good enough to operationalize.

## First Implementation

1. Started with `fsr_eval` in lightweight mode.
2. Focused on one simple retrieval metric first: number of FSRs retrieved vs what exists.
3. Logged results in MLflow for quick A/B comparison.