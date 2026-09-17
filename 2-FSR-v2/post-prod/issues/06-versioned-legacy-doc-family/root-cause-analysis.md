# Root Cause Analysis

Updated: 2026-09-15
Issue: Versioned and legacy doc family

## Status

RCA not fully completed yet.

## Current understanding

- Legacy and versioned documents appear to form a distinct family from the UUID path.
- Current notes suggest these documents need their own profile and may include pre-2017 cover-page ESN typos.

## Working root cause

The likely root cause is a family-level format mismatch combined with some known ESN-quality issues in older documents.

## Open questions

- Can one combined profile handle both legacy and versioned documents?
- Should ESN typo handling live in preprocessing or in a separate normalization step?