# 01. Section Path / UUID Chunking

Updated: 2026-09-15

## Brief

Priority bucket: `1`

Current summary:

- UUID-format docs are the main priority-1 chunking issue.
- The current target fix is chunk granularity and full section-label preservation, not Generator/Turbine boundary or ESN logic changes.
- Current known scope from the note: about `18,340` UUID docs, `29` bad-TOC outliers, and `3` materially important docs.
- Latest direction: do not add a separate UUID no-TOC fallback now; fix the section-based chunking path first and handle the three meaningful no-TOC UUID docs manually if needed.

Primary source:

- `../../section-path-issue-discussion.md`
- `root-cause-analysis.md`
- `solution-proposal.md`
- `implementation-plan.md`

## Root cause analysis

Current conclusion:

- The current equipment span and ESN logic should remain unchanged.
- The fix target is to make each smallest section its own chunking unit.
- The section metadata should preserve the full section label, not a shortened prefix such as `3.2.1 Generator` when the full heading is longer.
- This is a narrower fix than changing Generator/Turbine boundary generation.

Detailed write-up:

- `root-cause-analysis.md`

## Implementation

Proposed direction:

- Keep the current UUID path as the default for the normal `36UUID` population.
- Fix the section-based chunking path first.
- Treat the three meaningful no-TOC UUID outliers as manual exceptions for now.
- Preserve current Generator/Turbine span and ESN logic while making chunking finer-grained and section labels more complete.

Proposed documents:

- `solution-proposal.md`
- `implementation-plan.md`

## Validation

Planned validation:

- confirm current Generator/Turbine span and ESN behavior stays unchanged
- verify one chunk unit per smallest intended section on an affected sample
- verify full section labels in `section_path` and `section_1` through `section_5`
- add a unit test for the affected heading pattern
- compare before/after section metadata and chunk granularity on a narrow regression set
- reprocess only the affected docs after QA validation
- do not expand scope into a separate UUID no-TOC fallback unless the main fix proves insufficient

Review status:

- RCA drafted
- solution proposal drafted
- implementation plan drafted
- code changes not started

## Components impacted

- Preprocessor and section-label construction: this is part of the change surface only to the extent needed to preserve full section labels in metadata.
- Metadata processor / P1 flow: this layer will carry the corrected section metadata into document metadata, so affected docs must be reprocessed through P1.
- Metadata enrichment: no root-cause change identified here. It should continue merging and persisting the corrected section metadata.
- Chunking / P2: this is a primary logic-change area because chunk granularity needs to move to the smallest intended section level.
- Embeddings / P3 index: regenerated chunks will require re-embedding and index sync for the affected docs.
- Retrieval validation: retrieval logic is not the root cause for this issue, but retrieval output should be rechecked after rechunking because corrected section metadata and chunk boundaries may change evidence surfaced for queries.