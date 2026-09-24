# Solution Proposal

Updated: 2026-09-15
Issue: Section path / UUID chunking

## Proposed direction

Fix section-based chunking and heading quality in the shared preprocessor path, with a confidence-gated structural guardrail for document families that have a reliable numbered TOC. Do not create a separate brittle parser for UUID documents.

## Why this is the right scope

The system needs to operate across roughly `50K+` documents, so the design must improve UUID documents without making every document depend on an exact TOC string match.

The working facts are:

- the UUID family is large, about `18,340` docs and is part of a broader `50K+` document population
- only `29` are currently called out as bad-TOC or undetectable-TOC cases
- `4` are now tracked as materially important/manual exceptions after the 2026-09-16 addition

That means the safest solution is:

- fix the shared section-based chunking and artifact filtering behavior first
- use normalized structural matching as a stronger guardrail only when TOC quality is sufficient
- keep a conservative fallback when TOC extraction is incomplete or unreliable
- handle the four meaningful no-TOC UUID outliers manually if needed
- preserve the current Generator/Turbine span and ESN logic while making chunking finer-grained

## Proposed fix shape

### 1. Use confidence-gated structural validation

For documents with a reliable numbered TOC, validate headings using exact section-number agreement, normalized title comparison, token overlap, and rejection of multiline, table-like, and page-join artifacts. Known unnumbered UUID exceptions such as `OUTAGE DETAIL` and the three equipment headers should be explicit allowlist cases.

This is document-structure validation, not retrieval exact matching. Exact section numbers are valuable, but raw title equality must not be the only signal. If the TOC has too few entries, no usable numbering, or signs of extraction failure, it must not become authoritative; use conservative heading rules instead.

This policy is shared across the `50K+` population. UUID-specific behavior should be a profile or input-contract setting, not a separate parser implementation.

### 2. Fix section-based chunking in the main path

The working priority is to correct how real section boundaries are emitted for the standard path, so sections like `2 Technical` become their own semantic regions when the document structure supports it.

This fix should also cover the earlier preprocessor findings captured in the bug-preprocessor RCA plan: the same document family can lose early numbered sections when TOC detection starts too late, and page-join/OCR artifacts can leak into the section tree if not filtered before `section_path` is written.

Recommended implementation assumptions for this proposal:

- treat the smallest intended section as the deepest heading level that has its own body content
- merge very short sections with an appropriate neighboring section instead of forcing every short section to remain standalone
- preserve the full section heading text in normalized form, without markdown markers or OCR formatting noise
- keep the same full normalized label in both `section_path` and `section_1` through `section_5`
- apply the same corrected full labels to persisted preprocessing region metadata so downstream stages stay aligned

The fix should:

- make each smallest intended section its own section-to-chunk unit
- allow very short sections to be merged with a neighboring section when needed for chunk quality
- preserve full section labels in `section_path` and `section_1` through `section_5`
- keep current Generator/Turbine boundary generation unchanged
- keep current ESN logic unchanged
- preserve the current protections against TOC contamination, OCR artifacts, and table-like false positives
- avoid broad behavioral changes outside chunk granularity and label preservation

### 3. Address the remaining reviewed cases with separate guardrails

The next implementation cycle will accommodate the remaining reviewed behaviors without globally relaxing numbered-heading detection:

- recognize root headings such as `6 Quality Checkpoint (QCP)` through a narrow normalized keyword rule
- expand generic subsection detection under Generator `-1` equipment headers only when structural signals support the candidate, such as single-line shape, valid numbering, nearby numbered continuity, or reliable TOC agreement
- retain sub-report content as chunkable regions while preventing reused local numbers such as `5.0 Safety Performance` from inheriting an unrelated main-report sibling such as `5 PIPO`
- preserve the enclosing equipment attribution for sub-report content when it is supported by a valid equipment header
- create an explicit local context for `N Attachments`, `N Appendix`, or `N Sub Reports` so local numbering is interpreted within that block
- use primary TOC evidence only as supporting validation; do not discard sub-report content solely because the primary TOC does not contain the local number

These are separate fixes because they have different failure modes and regression risks. The Generator expansion must retain the existing table/value and multiline-artifact protections.

For sub-reports, retaining the content and preventing incorrect hierarchy inheritance is preferred over dropping the content. If local ownership remains unclear after the context boundary, emit low-confidence or ambiguous metadata and allow the existing recursive fallback chunking to preserve searchability.

Long-label preservation is an optional, regression-gated improvement. First locate whether truncation happens in PDF extraction, preprocessor candidate capture, or downstream display/projection. Apply it only if the change is local and does not cause material regression across the representative document set.

The existing two-leader/page-number threshold for recognizing multi-page TOC continuation pages remains unchanged. A sparse final TOC page may be missed, but this is accepted as a low-impact edge case for the current repair cycle.

### 4. Treat the no-TOC UUID outliers as controlled exceptions for now

There is no need to design a second no-TOC parser immediately.

The current working assumption is:

- future FSRs will include a TOC
- `4` UUID documents are now tracked in the materially affected/manual-exception group
- those can be assigned or overwritten manually if needed, with the fallback reason recorded
- the latest addition is `92387bdc-55df-41ab-8db3-f7fec0b15fa5`

### 5. Reprocess only the affected docs after validation

If only `preprocessor_regions` and `section_path` change, the remediation scope should be:

1. rerun preprocessing for affected docs
2. rerun chunking for those docs
3. regenerate downstream artifacts that depend on chunk identity or content
4. rerun retrieval and data-quality checks

## What not to do

- Do not weaken global heading acceptance for every document family.
- Do not move the fix into recursive chunk splitting.
- Do not add a second UUID-specific parser or make raw exact title matching authoritative.
- Do not make incomplete TOCs authoritative.
- Do not require every document in the `50K+` population to use UUID-specific rules.
- Do not change the current Generator/Turbine boundary or span generation for this fix.
- Do not change the current ESN attribution logic for this fix.

## Expected outcome

This should produce one chunk unit per smallest intended section, preserve full section labels where available, and improve remaining root/subsection and sub-report metadata without changing current Generator/Turbine span or ESN behavior. The small residual set of four UUID documents can remain manual exceptions for now.

## Short-section and front-matter behavior

Short-section handling is not the cause of the missing `1.2` boundary. Region-first chunking does not merge adjacent preprocessor regions. It recursively splits within each region and filters outputs below `min_chunk_size`. In the reported case, `1.2 Gas Turbine Executive Summary` appeared inside text attributed to `1.1` because the preprocessor had not created a `1.2` region. Explicit Gas Turbine subsection recognition fixes that boundary directly; disabling recursive segment merging would not.

Front matter before the first valid equipment boundary remains a `shared` region by design. Once an explicit equipment header is reached, later section regions receive equipment attribution. This prevents cover and TOC content from being assigned to the first equipment merely because it appears nearby.

## Components impacted

- Preprocessing and section-label construction: this is still part of the change surface because full section labels must be preserved in the metadata that chunking receives.
- Metadata extraction flow: no major design change is expected here, but the affected documents must be reprocessed so the corrected section regions and section paths are stored in document metadata.
- Metadata enrichment: no primary fix is proposed here. This layer should continue to merge and persist the corrected preprocessing output. If a profile or version marker is introduced, it would flow through this layer as well.
- Chunking: this is part of the primary fix scope because section-to-chunk granularity must change so that each smallest section becomes its own chunking unit.
- Embeddings and index sync: no direct design change is expected, but any changed chunks will need refreshed embeddings and index synchronization for the affected documents.
- Retrieval and downstream validation: retrieval is not the root cause, but it is part of the acceptance check because corrected section boundaries may change what evidence is surfaced.
## Decision on exact matching

Exact matching remains appropriate for stable structural components such as section numbers. It is not sufficient as raw string equality for complete headings because PDF extraction can alter whitespace, line breaks, hyphenation, and punctuation. The recommended guardrail is normalized structural matching with a TOC-quality gate, not semantic search and not unrestricted literal matching.

This design scales across the full document population: reliable structure receives stronger validation, while uncertain extraction falls back conservatively instead of silently dropping valid sections or accepting page/table noise.

## Boundary of deterministic preprocessing and future LLM use

The preprocessor should not become an increasingly rigid collection of document-specific rules. That approach can improve a known sample while increasing regression risk across the broader `50K+` population.

The recommended boundary is:

- deterministic preprocessing owns text extraction, offsets, obvious heading patterns, section-number structure, equipment boundaries, ESN attribution, and rejection of clear table/page artifacts
- deterministic checks should emit confidence and reason codes when structure is incomplete or ambiguous
- an LLM may be evaluated later as a bounded ambiguity resolver, classifier, or QA signal for low-confidence cases
- an LLM should not silently rewrite authoritative spans, ESNs, or section paths in the primary ingestion path
- any LLM-assisted decision must be versioned, auditable, sampled for human review, and covered by document-level regression tests

Potential LLM use cases include deciding whether an ambiguous numbered line is a real heading, selecting between two plausible normalized titles, or classifying a known exception such as `OUTAGE DETAIL`. These should initially run offline or asynchronously and produce recommendations or review queues. They should not be introduced as part of this narrow fix until deterministic confidence signals and regression baselines are in place.

## Diagnostic metadata and schema impact

The first implementation adds `heading_confidence` and `heading_reason_codes` to the existing `preprocessor_regions` JSON metadata. The shared Spark JSON schema is updated so consumers can read these fields, but no new relational table column is added and no chunk filtering contract changes.

Initial reason codes are deliberately limited to signals already proven by the deterministic pipeline, such as `numbered_subsection`, `toc_seeded_heading`, `hierarchy_level_conflict`, and `untyped_heading_context`. We should measure their volume across a representative sample before introducing a dedicated diagnostics table or adding LLM review workflow fields.
