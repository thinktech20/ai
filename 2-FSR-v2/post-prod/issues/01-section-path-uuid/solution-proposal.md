# Solution Proposal

Updated: 2026-09-15
Issue: Section path / UUID chunking

## Proposed direction

Fix the section-based chunking behavior first and do not add a separate `36UUID` no-TOC fallback at this time.

## Why this is the right scope

The current evidence and latest direction do not support a separate no-TOC fallback for the UUID family right now.

The working facts are:

- the UUID family is large, about `18,340` docs
- only `29` are currently called out as bad-TOC or undetectable-TOC cases
- only `3` of those appear materially important

That means the safest solution is:

- fix the main section-based chunking behavior first
- keep the standard UUID path for documents with TOC
- handle the three meaningful no-TOC UUID outliers manually if needed
- preserve the current Generator/Turbine span and ESN logic while making chunking finer-grained

## Proposed fix shape

### 1. Keep current TOC-assisted UUID behavior as the default path

For normal UUID docs with a parseable TOC, keep the existing profile behavior. It already gives the right guardrails against TOC contamination, OCR artifacts, and false section headers from table-like content.

### 2. Fix section-based chunking in the main path

The working priority is to correct how real section boundaries are emitted for the standard path, so sections like `2 Technical` become their own semantic regions when the document structure supports it.

Recommended implementation assumptions for this proposal:

- treat the smallest intended section as the deepest heading level that has its own body content
- keep small sections as standalone section-to-chunk units rather than merging them with sibling sections
- preserve the full section heading text in normalized form, without markdown markers or OCR formatting noise
- keep the same full normalized label in both `section_path` and `section_1` through `section_5`
- apply the same corrected full labels to persisted preprocessing region metadata so downstream stages stay aligned

The fix should:

- make each smallest intended section its own section-to-chunk unit
- preserve full section labels in `section_path` and `section_1` through `section_5`
- keep current Generator/Turbine boundary generation unchanged
- keep current ESN logic unchanged
- preserve the current protections against TOC contamination, OCR artifacts, and table-like false positives
- avoid broad behavioral changes outside chunk granularity and label preservation

### 3. Treat the no-TOC UUID outliers as manual exceptions for now

Based on the latest direction, there is no need to design a separate no-TOC UUID fallback immediately.

The current working assumption is:

- future FSRs will include a TOC
- only `3` UUID documents still look materially affected in the no-TOC group
- those can be assigned or overwritten manually if needed

### 4. Reprocess only the affected docs after validation

If only `preprocessor_regions` and `section_path` change, the remediation scope should be:

1. rerun preprocessing for affected docs
2. rerun chunking for those docs
3. regenerate downstream artifacts that depend on chunk identity or content
4. rerun retrieval and data-quality checks

## What not to do

- Do not weaken global heading acceptance for every document family.
- Do not move the fix into recursive chunk splitting.
- Do not add a separate UUID no-TOC fallback path unless the main section-based fix proves insufficient.
- Do not treat all UUID docs as needing a second profile by default.
- Do not change the current Generator/Turbine boundary or span generation for this fix.
- Do not change the current ESN attribution logic for this fix.

## Expected outcome

This should produce one chunk unit per smallest intended section and preserve full section labels in metadata, while keeping the current Generator/Turbine span and ESN behavior intact. The small residual no-TOC UUID set can remain a manual exception for now.

## Questions for confirmation

Only two points need confirmation before implementation:

1. Should `smallest section` be interpreted as the deepest heading level that has its own body text?
2. If a section is very short, should it still remain a standalone chunk unit rather than being merged with a neighboring section?

## Components impacted

- Preprocessing and section-label construction: this is still part of the change surface because full section labels must be preserved in the metadata that chunking receives.
- Metadata extraction flow: no major design change is expected here, but the affected documents must be reprocessed so the corrected section regions and section paths are stored in document metadata.
- Metadata enrichment: no primary fix is proposed here. This layer should continue to merge and persist the corrected preprocessing output. If a profile or version marker is introduced, it would flow through this layer as well.
- Chunking: this is part of the primary fix scope because section-to-chunk granularity must change so that each smallest section becomes its own chunking unit.
- Embeddings and index sync: no direct design change is expected, but any changed chunks will need refreshed embeddings and index synchronization for the affected documents.
- Retrieval and downstream validation: retrieval is not the root cause, but it is part of the acceptance check because corrected section boundaries may change what evidence is surfaced.
