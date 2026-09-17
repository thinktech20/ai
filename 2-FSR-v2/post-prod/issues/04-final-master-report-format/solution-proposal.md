# Solution Proposal

Updated: 2026-09-15
Issue: Final master report format

## Proposed direction

Treat `final_master_report` as an explicit document family with its own preprocessing profile.

## Proposed actions

- Define a dedicated profile for this family.
- Validate the profile on representative samples from the family.
- Route only matching documents through this profile.

## Expected outcome

Format-specific handling should improve section detection and downstream chunk quality without destabilizing the default path.