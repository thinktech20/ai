# 09. Front-Matter Shared Attribution

Updated: 2026-09-17

## Brief

Priority bucket: `Cross-cutting`

Before the first valid unnumbered equipment boundary, such as `Turbine (...)` or `Generator (...)`, some document text may currently receive equipment attribution. The proposed behavior is to classify this preamble as `shared` until a reliable equipment boundary is detected.

This includes cover-page content, TOC material, report-level summaries, and other text that cannot yet be assigned confidently to Generator or Turbine.

## Relationship to issue 01

This is related to the section-path work because both use `preprocessor_regions`, but it is a separate policy issue:

- issue 01 focuses on section boundaries, labels, and chunk granularity
- this issue focuses on equipment attribution before the first `-1` equipment heading

## Proposed behavior

- retain the text and chunk boundaries
- set `primary_equip_type` to `shared`
- leave `primary_esn` empty unless there is explicit, reliable evidence
- do not inherit the first later equipment context backward into the preamble
- preserve the full text for document-level search and summaries

## Validation status

RCA and implementation proposal are drafted. Corpus-level validation is still needed to confirm whether any users rely on preamble chunks carrying the first equipment's metadata.

Detailed documents:

- `root-cause-analysis.md`
- `solution-proposal.md`
- `implementation-plan.md`
