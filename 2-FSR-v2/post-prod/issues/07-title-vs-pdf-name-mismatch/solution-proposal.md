# Solution Proposal

Updated: 2026-09-15
Issue: Title vs PDF-name mismatch

## Proposed direction

Trace the source of truth for title and filename fields before deciding on a fix.

## Proposed actions

- Sample affected documents in v1 and v2.
- Compare filename, parsed title, stored title, and displayed label.
- Normalize the field used for display only after the source mismatch is confirmed.

## Expected outcome

The mismatch should be isolated to the exact layer introducing it, avoiding a superficial rename-only fix.