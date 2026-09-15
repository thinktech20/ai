# Root Cause Analysis

Updated: 2026-09-15
Issue: Mis-qualified ESN retrieval

## Status

RCA not fully completed yet.

## Current understanding

- A document is surfacing for ESN `337X351` when it should not.
- The current note suggests document qualification may be relying too broadly on active ESN membership.

## Working root cause

The likely root cause is a retrieval qualification rule that is too broad at the document level, causing a document to qualify for an ESN even when the region-level evidence does not support that association.

## Open questions

- Should qualification be based on active ESNs, region-level ESNs, or a combination?
- Is the issue limited to non-shared chunks or broader than that?