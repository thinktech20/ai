# 01. Section Path / UUID Chunking

Updated: 2026-09-15

## Brief

Priority bucket: `1`

Current summary:

- UUID-format docs are the main priority-1 chunking issue within a broader population of roughly `50K+` documents.
- The current target fix is chunk granularity and full section-label preservation, not Generator/Turbine boundary or ESN logic changes.
- Current known scope from the note: about `18,340` UUID docs, `29` bad-TOC outliers, and `4` materially important/manual-exception docs after the 2026-09-16 addition.
- Latest direction: use one shared preprocessor path, with stronger normalized structural guardrails only when TOC quality is reliable; handle the four meaningful no-TOC UUID docs as observable exceptions for now.
- Relevant earlier preprocessor findings remain in scope: TOC detection can start too late, and page-join/OCR noise can leak into headings if the filter is not applied before region metadata is written.

Primary source:

- `../../section-path-issue-discussion.md`
- `root-cause-analysis.md`
- `solution-proposal.md`
- `implementation-plan.md`
- `operationalization-plan.md`

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

- Keep one shared path for the broader population. UUID documents may enable stronger numbered-TOC validation when the input contract and TOC quality support it.
- Fix the section-based chunking path first.
- Treat the four meaningful no-TOC UUID outliers as controlled manual exceptions for now, with fallback reasons recorded.
- Newly added manual exception: `92387bdc-55df-41ab-8db3-f7fec0b15fa5`.
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
- do not expand scope into a separate UUID parser or raw exact-match policy

Review status:

- RCA drafted
- solution proposal drafted
- implementation plan drafted
- targeted preprocessor changes implemented and locally validated against the uploaded 575-page PDF
- broader rollout remains pending QA and downstream chunking validation
- operationalization plan drafted for scope-table driven overwrite and batch reprocessing
- follow-up fixes planned from Xujin review: Quality Checkpoint detection, guarded Generator generic subsections, sub-report hierarchy context, and optional regression-gated long-label preservation

Latest document-level validation:

- `1.2 Gas Turbine Executive Summary` now creates its own region and chunk ownership instead of remaining inside the `1.1` region.
- Body sections `3.1` and `3.2` are retained; their earlier apparent absence was TOC-page leakage caused by the fixed character cutoff ending partway through a multi-page TOC.
- `7.1`, `7.2`, and `7.3` each appear once in the uploaded document after page-aware TOC exclusion.
- Front matter before the first valid equipment boundary remains `shared` by design. This preserves full coverage without assigning cover/TOC text to an equipment section.

Next implementation slices:

- detect `Quality Checkpoint (QCP)` as a valid root section
- extend generic subsection detection under Generator `-1` headers only with structural confidence signals
- retain sub-report content while separating reused local numbering from the main-report hierarchy
- add local attachment/appendix/sub-report context; use ambiguity metadata rather than hard-discarding content when ownership is unclear
- investigate long-label truncation; defer the change if regression risk is material

## Components impacted

- Preprocessor and section-label construction: this is part of the change surface only to the extent needed to preserve full section labels in metadata.
- Metadata processor / P1 flow: this layer will carry the corrected section metadata into document metadata, so affected docs must be reprocessed through P1.
- Metadata enrichment: no root-cause change identified here. It should continue merging and persisting the corrected section metadata.
- Chunking / P2: this is a primary logic-change area because chunk granularity needs to move to the smallest intended section level.
- Embeddings / P3 index: regenerated chunks will require re-embedding and index sync for the affected docs.
- Retrieval validation: retrieval logic is not the root cause for this issue, but retrieval output should be rechecked after rechunking because corrected section metadata and chunk boundaries may change evidence surfaced for queries.

## Structural matching decision

Use exact section-number matching and normalized title/token checks as heading guardrails when a TOC is reliable. Do not use raw full-string equality as the sole rule, and do not make an incomplete TOC authoritative. This distinction applies to preprocessing structure validation, not user-query retrieval.

## Future LLM boundary

Keep high-confidence section parsing deterministic. For ambiguous or low-confidence cases, consider a separately evaluated LLM classifier or review signal rather than adding more document-specific parser rules. Any LLM-assisted result must be versioned, auditable, regression-tested, and prevented from silently changing authoritative spans or ESN attribution in the primary path.

The initial implementation persists heading diagnostics inside the existing `preprocessor_regions` JSON. It updates the shared JSON parsing schema but does not add a new relational column. A separate diagnostics table should be considered only after measuring the diagnostic volume and operational reporting needs.