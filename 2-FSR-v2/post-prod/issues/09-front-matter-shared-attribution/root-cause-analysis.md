# Root Cause Analysis

Updated: 2026-09-17
Issue: Front-matter shared attribution

## Finding

Text before the first reliable unnumbered equipment boundary may be assigned equipment context through neighboring-region or document-level inference. This can make cover-page, TOC, and report-level content appear to belong to the first Generator or Turbine section even when the text itself does not identify that equipment.

The desired policy is to keep this content as `shared` until a reliable equipment boundary is detected.

## Why this is separate from issue 01

Issue 01 concerns whether section boundaries and section labels are detected correctly. This issue concerns the metadata policy for text that occurs before the first equipment boundary. It can affect retrieval filters and equipment-qualified results even when section detection is correct.

## Expected behavior

For the preamble before the first valid `-1` equipment heading:

- retain full text coverage and chunkability
- use `primary_equip_type=shared`
- leave `primary_esn` empty unless explicit local evidence is available
- do not back-propagate the first later equipment context
- preserve report-level content for unqualified retrieval and summaries

## Risks to validate

Changing preamble attribution may affect:

- retrieval queries that currently rely on the first equipment tag
- document summaries or cover-page facts
- equipment-filtered search results
- chunk counts only if region boundaries are changed rather than metadata alone

## Falsifiable check

Sample documents with both cover/TOC content and a later Generator/Turbine header. Compare the first regions before and after the policy change and measure:

- number of preamble regions currently attributed to equipment
- number of chunks affected
- retrieval changes for equipment-qualified queries
- whether explicit ESN evidence exists in the preamble

## Recommendation

Treat this as a separate, lower-priority cross-cutting issue. Validate the metadata-only policy first. Rechunk and re-embed only if the region boundaries or persisted chunk metadata change in a way that affects existing chunk rows.
