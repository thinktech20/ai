# Root Cause Analysis

Updated: 2026-09-15
Issue: Final master report format

## Status

RCA not fully completed yet.

## Current understanding

- `final_master_report` appears to be a distinct document family.
- Current notes suggest it shares a common structure large enough to justify its own preprocessing profile.

## Working root cause

The likely issue is format mismatch: the current default processing path was optimized for a different family and is not the best fit for `final_master_report` structure.

## Open questions

- Which heading and TOC signals are consistently available in this family?
- Can one profile handle this family cleanly without affecting other families?