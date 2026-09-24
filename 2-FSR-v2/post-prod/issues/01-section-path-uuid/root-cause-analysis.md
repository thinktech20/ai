# Root Cause Analysis

Updated: 2026-09-15
Issue: Section path / UUID chunking

## Scope

This RCA is limited to the `36UUID` section-path issue tracked as priority bucket `1`.

## Executive finding

The issue should now be treated as a section-based chunking granularity and section-label completeness problem, not as a Generator/Turbine boundary-generation problem.

The latest clarification is that the current Generator and Turbine span generation, ESN attribution, and parent-inherit logic should remain unchanged. The intended fix is narrower:

- each smallest section should become its own section-to-chunk unit
- section metadata should preserve the full section label, not a shortened prefix form

## Control path

The relevant control path is:

1. `common/fsr_v2/preprocessor_v2.py`
2. heading candidate collection for `SECTION_HDR` and `SUBSEC`
3. hierarchical span construction
4. region emission into `preprocessor_regions`
5. chunk emission and section metadata propagation in the FSR v2 chunking path

The current pipeline still depends on precomputed section spans, but the latest direction is that the fix should not change the equipment boundary/span generation itself. The target is the way those spans are converted into chunk-sized units and how their labels are preserved in section metadata.

## What is actually failing

There are two coupled failure modes behind the UUID section-path issue.

### 1. Chunking is too coarse within the existing section structure

The current behavior groups too much content into one section-to-chunk unit, effectively carrying content forward until the next recognized keyword instead of creating one chunk unit per smallest intended section.

The requested change is to make each smallest section its own section-based chunking unit. That is a chunk granularity problem, not a request to redefine Gas Turbine versus Generator boundaries.

### 2. Some section labels are being preserved in shortened form instead of full heading form

The latest example shows a second issue in metadata shape: section metadata should preserve the full section label, such as `3.2.1 Generator Bearing Metal 2`, instead of shortening it to `3.2.1 Generator`.

This means the current path is preserving equipment typing correctly but not always preserving the full semantic heading text that users expect to see in `section_path` and in `section_1` through `section_5`.

This is consistent with the earlier preprocessor work recorded in the bug-preprocessor RCA plan: actual section candidates can be filtered out when TOC detection begins too late, and OCR/page-join artifacts such as `25.0\nGenerator flange above (mils)` can leak into the section tree if they are not rejected before the path is stored.

Grounding from current code and tests:

- current chunking metadata carries `section_path` into `section_1` through `section_5`
- some typed subsection patterns preserve equipment-type prefixes correctly but can store shortened heading labels such as `3.2.1 Generator` instead of the full heading line
- validation artifacts under `validate/section-issue/test` show the before-fix shape where section-based chunks are not isolated at the smallest intended section level

## Why this changes the earlier interpretation

The post-prod note says the issue is narrow inside the UUID family:

- about `18,340` UUID docs total
- `29` with bad or undetectable TOC format
- `4` now tracked as meaningful/manual exceptions after adding `92387bdc-55df-41ab-8db3-f7fec0b15fa5` on 2026-09-16

That scope still suggests the main UUID path is not broadly broken. The difference is that the requested fix is now narrower and more concrete:

So the root cause is not "UUID docs need a different global header rule" and not "Generator/Turbine spans are wrong." The narrower finding is:

- the current equipment boundary and ESN logic should remain intact
- the current section-based chunking output is too coarse
- some preserved section labels are too short for the intended metadata output

## Falsifiable local conclusion

If an affected document already has the right Generator/Turbine boundary and ESN attribution, but the produced chunks still span too broadly or carry shortened labels, then the defect is in chunk granularity and label preservation rather than equipment-span generation.

A cheap disconfirming check is to inspect one affected document and ask two questions separately:

- are the Generator/Turbine spans and ESN fields already correct?
- are the smallest section chunks and full section labels still missing?

Based on the latest clarification, the expected outcome is that equipment spans remain correct while chunk size and full-label preservation need adjustment.

## Root cause statement

The root cause for the current UUID section-path issue is not that Generator/Turbine spans are wrong. The issue is that the section-based chunking output is too coarse and that some section labels are preserved only as shortened type prefixes instead of full section headings. The intended fix is therefore to tighten section-to-chunk granularity and preserve full section labels, while leaving the current equipment boundary, ESN attribution, and span-generation logic unchanged.

## What is not the root cause

- Not a request to change current Generator and Turbine span generation
- Not a request to change current ESN attribution logic such as `parent_inherit`
- Not evidence that the whole `36UUID` family needs a new default profile
- Not a reason to weaken global heading rules broadly

## Evidence references

- `post-prod/section-path-issue-discussion.md`
- `pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor_v2.py`
- `pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunk_splitter.py`
- `pw_sdg_ai_ser_repo/tests/fsr_v2/test_preprocessor_v2.py`
- `validate/section-issue/test/before-section-fix/*`
- `validate/section-issue/test/after-section-fix/*`

## Latest Review Findings (2026-09-17)

Xujin reviewed the updated output and identified four remaining behaviors. These are not all the same type of defect and should not be handled with one broader heading rule.

### 1. Section 6 Quality Checkpoint is not detected

**Assessment: fix required.**

The current root-level keyword rule recognizes only exact forms such as `PIPO`, `Control System`, and `QCP`. A heading such as `6 Quality Checkpoint (QCP)` has a valid section number and a known semantic keyword, but the parenthesized suffix prevents the current exact pattern from recognizing it as a root section.

This is a deterministic recognition gap. It should be fixed with a narrow normalized pattern for `Quality Checkpoint` and `QCP` variants, with the same front-matter, TOC, and artifact guardrails already used for other root headings. It should not require a general relaxation of heading acceptance.

### 2. Generic subsections under a Generator equipment header are incomplete

**Assessment: fix, but with guardrails.**

The current generic subsection path is intentionally more restrictive under Generator context. It permits generic titles mainly after known Generator-specific subsection signals or under an Electrical/Electrification root. This protects against promoting table text and unrelated numbered lines, but it also means a document such as `GENERATOR (337X164 | SY0072347)` may retain only keyword-shaped subsections while dropping valid general numbered sections.

The cited document `c9ed4e93-8408-4371-9f90-4e8641dd1ee6` is a useful regression case. The desired change is not to accept every numbered line under Generator. Instead, accept a generic Generator subsection when multiple structural signals agree, for example:

- it is a single-line valid section heading
- it is inside the Generator root span
- its number/title is supported by a reliable TOC or nearby numbered heading sequence
- it is not a table/value line, page artifact, or known equipment-prefix duplicate

This should be implemented as a confidence-gated Generator path and validated against both Generator and Gas Turbine documents. Otherwise, broadening the rule risks reintroducing the table contamination that the current guardrail was designed to prevent.

### 3. Sub-report content is detected but receives ambiguous parent context

**Assessment: keep the content, fix the hierarchy metadata.**

It is useful to retain detected sub-report sections for section-based chunking. Dropping them would lose searchable content. The problem is that independently numbered sub-report sections such as `5.0 Safety Performance` are currently attached to the nearest active main-report root, so they can appear under `5 PIPO` even though they belong to a sub-report or attachment block.

The screenshot confirms the ambiguity: the sub-report contains its own sequence such as `1.0` through `7.0`, but the current hierarchy interprets `5.0` as a continuation of the main report's `5 PIPO` branch. That is a metadata-quality problem, not a reason to discard the section.

Recommended behavior:

- retain the sub-report section as a chunk boundary
- create an explicit sub-report/attachment context boundary when `N Sub Reports` or `N Attachments` is detected
- prevent the sub-report's local numbering from being attached to the preceding main-report sibling solely because the numeric prefix is reused
- mark unresolved sub-report ownership as ambiguous or low-confidence rather than assigning a misleading main-report path
- keep equipment attribution when it is supported by the enclosing equipment header

The preferred implementation is to introduce an explicit local context boundary when a main section such as `6 Attachments`, `6 Appendix`, or `N Sub Reports` is detected. Numbered headings inside that block should be interpreted as local sub-report numbering rather than attached to the preceding main-report sibling. For example, the desired shape is conceptually:

```text
[6 Attachments, 5.0 Safety Performance]
```

The section should remain available for chunking and search. If the local hierarchy cannot be resolved confidently, mark it low-confidence or ambiguous rather than discarding it. A primary TOC check may support the decision, but should not hard-discard content by default because incomplete TOCs could remove valid sections.

This is a good candidate for the future low-confidence/LLM review path, but the deterministic fix should first prevent the clearly misleading `5.0 -> 5 PIPO` attachment.

### 4. Long section labels are truncated

**Assessment: fix if the truncation occurs before metadata persistence; otherwise treat as an extraction limitation.**

The preprocessor candidate code captures the full single-line match and does not contain an intentional 60-character heading limit. Therefore, a label such as `3.1.3 packaged electrical / electronic control compartment (PEECC)` being shortened to `...control com` likely comes from one of these upstream or downstream points:

- PDF text extraction or parser-specific line truncation
- a validation/display query truncating the field for presentation
- a different preprocessing version or output artifact
- a chunk metadata projection that shortens the section label

The correct first check is to compare the raw parsed page text, the `HeadingCandidate.heading_text`, the emitted `section_path`, and the final `section_1` through `section_5` values for `27fa1fe0-369e-456f-b795-d9a9fc9cd52d`. If the candidate is already truncated, the parser/extraction path needs attention. If the candidate is complete but the persisted value is truncated, the downstream projection is responsible.

This should be fixed because full labels are part of the issue contract, but it is lower priority than missing section boundaries and incorrect sub-report ownership. It should not be fixed by blindly increasing a string limit until the truncation point is measured.

Xujin's prioritization is to try this improvement if the cause is easy to isolate, but defer it if the change creates substantial regression risk. This makes long-label preservation a separately validated enhancement, not a blocker for the higher-value boundary and hierarchy fixes.

## Recommended priority

1. Add `Quality Checkpoint (QCP)` root recognition and regression coverage.
2. Add confidence-gated generic subsection support under Generator roots using `c9ed4e93-8408-4371-9f90-4e8641dd1ee6` as a regression case.
3. Preserve sub-report content while introducing an explicit sub-report/attachment context so reused numbers do not inherit the wrong main-report sibling; use ambiguity metadata when the local hierarchy remains unclear.
4. Optionally trace and fix the long-label truncation for `27fa1fe0-369e-456f-b795-d9a9fc9cd52d`; retain the change only if regression impact is low.

These changes should be implemented as separate, testable slices. They should not be combined into a global relaxation of numbered heading detection.

## 2026-09-21 implementation update

The remaining preprocessor fixes reported to Xujin were implemented in the shared path:

- narrow generic-root recognition now covers `OUTAGE DETAILS`, numbered `Summary`, and numbered `Technical` headings
- heading labels are normalized before section spans and persisted `section_path` metadata are emitted, removing leading Markdown markers
- explicit Turbine subsection titles are protected from inheriting a preceding Generator sibling's equipment type
- numeric and table-like heading guardrails remain active for measurement rows such as `14.00 Mils`, `10.83 Mils`, and `33.3 rps` 
- attachment and sub-report content remains retained under the existing local context handling

The FSR v2 test suite passes with `75` tests passing and no failures. This establishes local regression coverage for the fixes, but does not replace end-to-end verification on the three affected PDFs. The remaining end-to-end checks are the exact sub-report path shape and the point at which any long-label truncation occurs.

## Dev Track-4 Validation RCA (2026-09-17)

The sandbox regression run completed both pipeline stages successfully:

- P1 run: `342386524884095`
- P2 run: `605378533699252`
- 53 documents processed
- no stuck claims, orphan chunks, empty chunks, or embedding-dimension failures

The verification wrapper reported three failed quality checks. These are not evidence that the section-path changes caused new runtime or chunking failures.

### 1. Ambiguous source file

One document failed before preprocessing because the configured source volume contains two files with the same normalized document stem and different suffixes:

```text
0298436 - 32B0341 - CecilHPooleJr - 10262009.pdf
0298436 - 32B0341 - CecilHPooleJr - 10262009_1.pdf
```

This is a source-discovery ambiguity. It occurs before the preprocessor and is unrelated to section detection, chunking, or the recent heading changes. The correct remedy is to remove/rename the duplicate or apply an explicit source-selection policy.

### 2. Eleven completed documents have no primary ESN

The affected rows completed P1 and P2 successfully but have an empty `primary_esn`. They include small accessory/disposition documents and Generator/Gas Turbine documents whose extracted or known identifiers do not resolve to a primary ESN.

This matches existing known ESN cases documented in the preprocessor RCA work, including SY-only identifiers and documents where the body does not contain an assignable ESN. The recent changes modify heading recognition, TOC handling, and local hierarchy; they do not modify ESN inventory discovery or the deterministic ESN resolution order.

The result is therefore a pre-existing data-quality limitation, not a demonstrated regression from the section-path changes. It should be tracked separately from section-boundary validation.

### 3. Eleven documents have no equipment-map row

This is a downstream consequence of the same empty-ESN condition. The equipment-map builder has no ESN key to persist, so it emits no map row. The chunks still exist and are not orphaned.

The verification assertion is useful for documents expected to have an ESN, but it is too broad as a universal pass/fail criterion for report-level, accessory, SY-only, or otherwise unresolved-ESN documents. The check should distinguish:

- documents expected to have a resolvable primary ESN
- documents completed without an assignable ESN, which should produce an explicit DQ warning rather than be treated as a section-path regression

### Validation conclusion

The dev run confirms pipeline execution and chunk integrity. The three failed checks are source-resolution and ESN/data-quality issues. No new failure in section boundaries, TOC handling, chunk creation, stale-chunk cleanup, or embeddings was observed from this change set.

## Xujin 2026-09-18 Verification Addendum

The current local code was compared with Xujin's standalone findings. The available 575-page document was rerun locally with the current PyMuPDF/preprocessor path. The cited documents `c9ed4e93-8408-4371-9f90-4e8641dd1ee6`, `27fa1fe0-369e-456f-b795-d9a9fc9cd52d`, and `3d156a24-2bb9-4ccd-a81e-c122c39aa3ac` are not present in the workspace, so those cases cannot yet be confirmed locally.

### Confirmed or likely real gaps

1. `OUTAGE DETAILS`, `1 Summary`, and generic root sections such as `2 Technical` are present in extracted body text but have no candidate pattern in the current preprocessor. `1.2 Executive Summary` is detected because dotted subsection patterns already cover it. This is a real heading-recognition gap, not evidence of short-section merging.
2. The long-label case cannot be confirmed without `27fa1fe0-369e-456f-b795-d9a9fc9cd52d`. The current candidate code has no intentional 60-character truncation, so the source PDF is required to locate the truncation stage.

### Not reproduced in the available 90d document

1. `6.1 Attachments` and `8.1 Attachments` are detected locally and appear in section paths under `6 Quality Checkpoint (QCP)` and `8 Appendix`.
2. The local run produces no `Generator flange` candidates or paths and no numeric noise candidates matching the reported `14.00 Mils`/`10.83 Mils` examples.
3. The local candidate collection has no retained Markdown markers on section headings, while Xujin's output shows values such as `## 5 PIPO`. This may be a difference in her extraction/heading-normalization path rather than the current checked-in preprocessor. The current hierarchy level for `7 PIPO` is `0`; the visible `##` should not by itself be interpreted as a hierarchy level unless it is present in the actual candidate text.

### Required source files for full confirmation

Please attach these PDFs or parsed JSONs if available:

- `c9ed4e93-8408-4371-9f90-4e8641dd1ee6`
- `27fa1fe0-369e-456f-b795-d9a9fc9cd52d`
- `3d156a24-2bb9-4ccd-a81e-c122c39aa3ac`

Once available, compare raw parsed text, candidate headings, emitted paths, and chunk metadata before deciding whether the remaining issues are parser defects or differences in standalone extraction setup.

### Local verification of the three uploaded PDFs (2026-09-18)

The three PDFs were processed locally with PyMuPDF and the current checked-in preprocessor.

#### `c9ed4e93-8408-4371-9f90-4e8641dd1ee6`

- `5 PIPO` is emitted as a level-0 `SECTION_HDR`; no Markdown marker is present in the candidate text.
- `4 Quality Checkpoint (QCP)` and `4.1 Attachments` are detected.
- `6 Appendix`, `6.1 Attachments`, and the local sub-report headings including `5.0 Safety Performance` are detected.
- `5.0 Safety Performance` is currently scoped under `6 Appendix`, which matches the intended local-context direction.
- No newline-bearing candidates were observed.

This document does not reproduce the reported wrong PIPO hierarchy in the current local run. The `##` shown in Xujin's output may come from a different extraction/marker-injection path, not the candidate text produced by this checked-in code.

#### `27fa1fe0-369e-456f-b795-d9a9fc9cd52d`

- `3.1 Attachments` is present in the primary TOC on page 10 and in the body.
- The current TOC extractor does not include that final TOC continuation page because it stops when a continuation page has fewer than two leader/page-number lines. The resulting TOC list misses the valid `3.1 Attachments` entry, and the candidate collector then rejects the body occurrence through the TOC guard.
- This is understood as a TOC continuation behavior, not evidence that the primary TOC lacks the entry. Based on Xujin's review, the two-leader threshold is intentionally retained for now. The missed final TOC section is accepted as a low-impact edge case and will not be changed in this fix cycle.
- The long heading `3.1.3 packaged electrical / electronic control compartment` is captured completely by the candidate and section path locally. The reported truncation is therefore likely in Xujin's display/projection path or a different parser output, not the current candidate collector.

The missing `3.1 Attachments` is a confirmed parser-policy gap and should be handled by the attachment-context rule rather than by dropping all non-TOC content.

#### `3d156a24-2bb9-4ccd-a81e-c122c39aa3ac`

- The numeric-noise reports are reproduced in the current local run:
	- `33.3 rps).`
	- `14.00 Mils`
	- `10.83 Mils`
- These are emitted as generic `SUBSEC` candidates and enter section paths, confirming a real false-positive heading problem.
- The document also contains repeated standalone `Steam Turbine` and `Generator` lines that are emitted as unnumbered equipment candidates; these need separate table/body-context guardrails.
- PyMuPDF emits `unknown cid font type` warnings while parsing this PDF, but still returns a usable text stream. The numeric candidates are present in that extracted text, so the issue is reproducible despite the font warnings.

### Updated priority from the verified PDFs

1. Reject numeric/table-like generic subsection candidates such as `14.00 Mils`, `10.83 Mils`, and `33.3 rps).` without dropping valid numbered headings.
2. Add context-sensitive filtering for standalone `Generator`/`Steam Turbine` lines rather than treating every standalone occurrence as an equipment boundary.
3. Preserve Appendix/sub-report content under the nearest reliable Appendix/Attachment context, using primary-TOC filtering only for low-confidence candidates if noise remains.
4. Keep the long-label issue optional until the candidate-vs-display truncation difference is resolved.

### Trade-off decision from Xujin's latest feedback

The priority is to eliminate numeric/table noise and standalone equipment-word false positives. For sub-report or appendix content, the preferred fallback is to retain the content under the nearest reliable parent or an explicit attachment/appendix context, rather than hard-discarding it solely because TOC coverage is incomplete. If noise remains after the deterministic filters, a stricter primary-TOC guard can be applied to low-confidence candidates while preserving valid high-confidence body sections. The current two-leader continuation threshold remains unchanged by decision.
