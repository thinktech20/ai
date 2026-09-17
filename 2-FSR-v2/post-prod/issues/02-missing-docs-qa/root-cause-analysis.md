# Root Cause Analysis

Updated: 2026-09-15
Issue: Missing docs in QA

## Status

RCA not fully completed yet.

## Current understanding

- Two documents were reviewed in the QA post-2016 check.
- One document is present in QA metadata with `chunk_status='pending'`, which indicates queueing rather than a chunk-generation failure.
- One document is a dev-only test artifact and should not have been expected in QA.

## Working root cause

This does not currently look like one single ingestion defect. The current evidence points to:

- one expectation mismatch about environment scope
- one valid QA document still waiting for downstream chunk processing

## Open questions

- Is there any remaining QA source-path mismatch beyond the identified dev-only artifact?
- Did the pending document later get picked up by P2 as expected?