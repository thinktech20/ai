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

Grounding from current code and tests:

- current chunking metadata carries `section_path` into `section_1` through `section_5`
- some typed subsection patterns preserve equipment-type prefixes correctly but can store shortened heading labels such as `3.2.1 Generator` instead of the full heading line
- validation artifacts under `validate/section-issue/test` show the before-fix shape where section-based chunks are not isolated at the smallest intended section level

## Why this changes the earlier interpretation

The post-prod note says the issue is narrow inside the UUID family:

- about `18,340` UUID docs total
- `29` with bad or undetectable TOC format
- only `3` with meaningful context

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
