# sdg-autotest Summary

## Purpose

sdg-autotest is a risk-eval quality harness that makes prompt and retrieval tuning measurable, repeatable, and reviewable before rollout.

## Problem it is solving

After a team fixes one failing case, there is no quick confidence check that the same change did not hurt other ESN and issue combinations.

In practical terms, it solves this gap:

1. Tune a setting for a local failure.
2. Re-run enough iterations for stability.
3. Compare outcomes and retrieval behavior.
4. Verify against SME-backed expectations.
5. Detect regressions before production deployment.

## Vince's specific pain point

A local tuning change can improve one issue but regress broader behavior.

Example he gave:

1. Top-k returned chunks from a single chatty FSR for a failing issue.
2. Raising top-k globally might help that one case.
3. But global top-k change can increase latency and produce side effects elsewhere.
4. So he needs a wider regression sweep after local tuning.

## What sdg-autotest currently provides

1. Probe Runner
   - Repeated run-single calls for a target case with persisted per-iteration outputs.

2. Prompt Lab (A/B/C)
   - Controlled variant comparison with replay-style setup and per-variant settings.

3. Ground Truth scoring
   - Compare run outputs against SME labels and expected severity.

4. Retrieval Inspector
   - Inspect FSR and ER chunks and compare chunk overlap across iterations.

5. Test Reports and Analyzer
   - Save frozen run snapshots and generate structured LLM analysis for review.

## Relationship to retrieval harness work

Vince described the two tools as complementary:

1. sdg-autotest evaluates end-to-end risk-eval behavior and prompt quality.
2. Our retrieval harness focuses on retrieval data quality and scaling across wider samples.

## One-line reusable summary

sdg-autotest is a regression-focused risk-eval harness for validating that prompt and retrieval changes improve targeted failures without introducing wider regressions.
