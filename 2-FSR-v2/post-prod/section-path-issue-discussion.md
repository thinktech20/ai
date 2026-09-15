# FSR v2 Section Path Issue Discussion

## Purpose

Prepare for the next discussion about section-based chunking, section path accuracy, and whether different document formats need different preprocessing logic.

## Current understanding

Current FSR v2 chunking depends on the preprocessor output indirectly:

1. The preprocessor identifies section/header candidates and creates regions with character offsets and metadata.
2. The regions are persisted with the document metadata, including `section_path` and equipment/ESN context.
3. The chunking step processes those regions first and recursively splits them by size when needed.
4. The resulting chunks inherit the region metadata.

Therefore, if the preprocessor creates an overly broad region or assigns the wrong section path, recursive chunking will not correct the semantic boundary. It will only split the broad region according to the recursive fallback rules.

If the preprocessor regions or section paths are corrected, the affected documents need to be rechunked so the corrected boundaries and metadata are propagated to the chunk records. Re-parsing should not be necessary unless the extracted text or character offsets change.

## Latest input

The latest update is consistent with the current diagnosis and adds more concrete scope:

- the current preprocessor parsing and section-header detection logic is causing bad section-based chunking in QA
- the issue does not appear to directly reduce metadata tagging accuracy
- the likely downstream impact is on risk or retrieval performance because multiple sections with the same ESN and equipment type are being merged into one broad section
- the team expects a fix this week, followed by reprocessing in QA or Prod depending on the rollout path
- even before the fix, the expected QA symptom is that users may see missing documents surfacing and no Turbine evidence cited

This reinforces that the current defect is primarily a section-boundary and section-path problem in preprocessing, not a generic metadata-tagging failure.

Latest clarification (2026-09-14):

- Among the 36UUID-format documents (about 18,340 total), only 29 have a bad ToC format (no ToC or the preprocessor cannot detect it).
- Of those 29, only 3 have meaningful context; the other 26 are short documents or just cover-page variants.
- The three with meaningful context are rare edge cases and can be handled manually or ignored without materially affecting overall corpus quality.
- Operationally, this suggests the section-path issue is narrow and concentrated, rather than a broad failure mode across the entire FSR corpus.

## Format inventory

The latest discussion also shared a rough inventory of the FSR corpus, which is useful for deciding whether to extend one global rule or route documents through multiple preprocessing profiles:

- `36UUID` format: about 18,340 FSRs. All appear to use the regular TOC format that the current preprocessor can support except 29 documents, and only 3 of those 29 appear to have actual content. Current plan: ignore those outliers or attach tags manually.
- `final_master_report` format: about 4,923 FSRs. These appear to contain at most one Generator and one Turbine evidence item and share the same TOC format. Current direction: design preprocessor 2 for this family.
- legacy format such as `090dbba` or `09001389`: about 18,422 FSRs. These also appear to contain at most one Generator and one Turbine evidence item and share the same TOC format. About 102 have ESN and associated ESN typos on the cover page, all before 2017.
- versioned format such as `num_v...`: about 9,064 FSRs. These also appear to contain at most one Generator and one Turbine evidence item and share the same TOC format. About 76 have ESN and associated ESN typos on the cover page, all before 2017. Current direction: design preprocessor 3 for the legacy and versioned families.
- remaining formats: about 310 FSRs. Current plan: ignore them or fall back to preprocessor 1.

This breakdown supports a profile-based design more strongly than a single global section-header rule.

## Observed issue

In the document reviewed yesterday, Section 2 was not placed into its own section-based chunk. The output treated content spanning approximately Sections 1.1 through 3.1 as one broad section/region, with recursive fallback chunking applied inside it.

The expected behavior is for meaningful sections such as Section 2 to have their own region and section path, subject to the document's actual structure and the desired chunking rules.

The table of contents example also shows why this is not simply a generic numbered-heading problem. It contains entries such as:

- `1 Summary`
- `1.1 Generator Executive Summary`
- `2 Technical`
- `2.1 Recommendations`
- `3 Generator`
- `3.1 Generator Mechanical`
- `3.1.1 Oil Ingress Investigation`

Another document format has a table of contents with unnumbered entries such as:

- `JOB SUMMARY`
- `INSPECTION SUMMARY`
- `RECOMMENDATIONS`
- `PARTS USED & RECOMMENDED`
- `GENERATOR STATOR`
- `GENERATOR FIELD`
- `ALIGNMENT & CLEARANCES OVERVIEW`

These formats may require different header detection signals and hierarchy rules. The format inventory suggests that there are at least a few large document families that may justify separate preprocessing profiles rather than one shared detection rule.

## Main concern

Changing the general section-header detection logic could improve this document but introduce regressions in other document types. In particular, we previously saw table content being incorrectly classified as section headers when numbering checks were ignored or relaxed too broadly.

Numbering alone is not sufficient evidence for a section header. A robust decision may need to combine several signals, such as:

- heading text and numbering pattern
- font, size, weight, or other layout information when available
- location in the document body versus a table of contents or table
- TOC alignment and expected page number
- surrounding text and hierarchy consistency
- repeated patterns across pages
- whether the candidate creates a plausible section span
- document-specific formatting characteristics

## Possible design

A document-specific preprocessing strategy may be safer than changing one global rule for every document.

Possible routing model:

1. Identify the document format or preprocessing profile using `document_id` or another stable document attribute.
2. Apply the existing logic for documents that already work well, such as the majority of the `36UUID` family.
3. Apply a specialized section-header strategy for the affected format families, likely as explicit profile versions such as preprocessor 1, 2, and 3.
4. Persist the selected preprocessing profile/version with the preprocessing output for traceability.
5. Compare section regions, section paths, and chunk counts against the current output.
6. Rechunk only the affected documents after the new regions are validated.

This should be treated as a versioned/configured preprocessing path rather than a temporary production workaround. The routing key and fallback behavior need to be explicit so a document is not silently processed with the wrong strategy.

The inventory also suggests a practical prioritization:

- keep the current profile for the large `36UUID` population that already works well
- add a separate profile for `final_master_report`
- add a separate profile for the legacy and versioned families
- decide explicitly whether the remaining long-tail formats should be ignored, manually tagged, or processed with a known fallback profile

## Regression and validation plan

Before changing production output, validate the candidate logic against representative documents from at least these groups:

- the document where Section 2 is currently missed
- documents using numbered hierarchical headings
- documents using unnumbered all-caps headings
- documents with embedded tables and table-like rows
- documents with a table of contents
- documents with missing, incomplete, or inconsistent TOCs
- documents with equipment-specific section structures

Compare the current and candidate outputs for:

- detected section/header candidates
- region start and end offsets
- section hierarchy and `section_path`
- false-positive headers from table rows or body text
- missing section boundaries
- equipment and ESN attribution
- number of regions and chunks
- chunk size distribution
- downstream retrieval or data-correctness impact

A useful acceptance check is that the candidate logic creates the expected Section 2 boundary without increasing false section detection in the existing regression set.

## Rechunking impact

If only preprocessor regions or section paths change:

- rerun preprocessing for the affected documents
- persist the new region metadata
- rerun chunking for those documents
- regenerate embeddings or other downstream artifacts if they are tied to chunk identity/content
- rerun data-correctness and retrieval checks

If the extracted text or character offsets change, the parsed artifact and all offset-dependent preprocessing/chunking outputs must be regenerated together.

The safest operational approach is to keep the current output available for comparison until the candidate output passes validation.

The latest discussion referred to this operationally as a likely re-ingestion in QA or Prod. More precisely, the required scope depends on what changes:

- if only section boundaries, section paths, or preprocessing region metadata change, reprocessing and rechunking the affected documents should be sufficient
- if extracted text, offsets, or parsed artifacts change, the broader ingestion chain must be rerun for those documents

## Questions for discussion

1. Should the target behavior be one chunking region per semantic section, or should some sections remain grouped when they are small or closely related?
2. Is the desired boundary based on headings found in the document body, the TOC, or both?
3. How should an unnumbered heading format be recognized without treating table rows as headers?
4. Can `document_id` reliably identify a stable document format, or do we need a document-family/profile field?
5. Should preprocessing profiles be selected by document family, template, source system, or an explicit configuration table?
6. Do we want a global detection improvement first, or a document-specific strategy for the known format families identified in the inventory?
7. What level of regression testing is required before enabling a new profile?
8. Should old chunks be replaced in place, or should the new preprocessing/chunking output have a new version for comparison and rollback?
9. Which downstream artifacts must be regenerated after rechunking, especially embeddings and retrieval indexes?
10. What is the acceptable behavior when no reliable section headers are found: one shared document region, smaller generic chunks, or an explicit ambiguous classification?

## Proposed discussion position

The immediate issue appears to be a preprocessor region-boundary problem, not a recursive chunk-size problem. We should avoid weakening global header rules based only on numbering because that can turn table content into false section headers.

A practical path is to first reproduce the section candidates and region boundaries for the affected document, then test a narrowly scoped preprocessing profile against a representative regression set. If the format is genuinely different, route it through a document-specific profile and rechunk only the affected documents after validation.

Based on the latest inventory, the likely next design discussion is no longer just whether one document is misdetected. It is whether the corpus should be split into a small number of explicit preprocessing families with clear routing, validation, and downstream reprocessing rules.

## Decision to capture

- Target section-boundary behavior
- Signals required to accept a section header
- Scope of any new preprocessing profile
- Mapping from known document families to preprocessing profiles
- Routing key and fallback profile
- Regression dataset and acceptance criteria
- Reprocessing and rechunking procedure
- Versioning, rollback, and downstream regeneration requirements
