# Solution Proposal

Updated: 2026-09-15
Issue: Final master report retrieval

## Proposed direction

Validate retrieval behavior on the flagged samples first, then decide whether the fix belongs in retrieval rules, preprocessing, or both.

## Proposed actions

- Reproduce the retrieval behavior on the two sample documents.
- Compare shared-chunk behavior versus section- or region-specific evidence paths.
- Narrow the fix to the controlling layer once the cause is confirmed.

## Expected outcome

The family-specific retrieval gap should be isolated before any broader retrieval changes are made.