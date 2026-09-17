# Root Cause Analysis

Updated: 2026-09-15
Issue: Title vs PDF-name mismatch

## Status

RCA not fully completed yet.

## Current understanding

- There is an open question about mismatch between the displayed document title and the PDF filename across FSR v1 and v2.
- No confirmed source of mismatch has been recorded yet.

## Working root cause

The most likely causes are divergence between parsed title fields, stored metadata fields, and UI-facing labels.

## Open questions

- Does the mismatch originate in parsing, metadata normalization, ingestion, or presentation?
- Does the same pattern exist in both v1 and v2?