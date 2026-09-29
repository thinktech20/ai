# Dev Verification Follow-up Root Cause Analysis

Updated: 2026-09-28  
Scope: Xujin's dev verification comments after the September 25 postfix changes

## Executive conclusion

The September 25 fixes did resolve the originally demonstrated missing-text cases, metadata/chunk repair for item 4, irregular Generator labels, and the incompatible `Generator -> 2 Turbine` hierarchy case that was tested.

The remaining comments are a mix of four categories:

1. **Acceptance gap in the implemented chunking behavior:** overlap is applied only while recursively splitting one preprocessor region. It is not applied across section/region boundaries. Retaining short semantic regions prevents text loss but can create a header-only or very short chunk.
2. **Cases not covered by the original fix:** ToC headings being emitted as sections, false headings inside short tables, embedded sub-reports corrupting later hierarchy, duplicate hierarchy levels, and the separate `2.43` page mapping case were not fixed by the September 25 changes.
3. **Confirmed residual defects in the postfix dev output:** live queries show that all seven original documents completed P1, P2, and P3 in `postfix-dev-cce00fc-20260925`. The missing Generator ESN, Steam Turbine attribution, region ESN, page/section boundary, and hierarchy observations are present in that output.
4. **New issue, decision pending:** `Unit Serial #: 336X860` is not one of the deterministic ESN label patterns. Hold implementation until feedback is received.

The main reason tests passed while Xujin still sees problems is that the tests proved source retention, exact duplicate-boundary cleanup, and one specific incompatible-parent transition. They did not assert that paragraphs remain within valid section boundaries, reject table lines before they split a real section, reject all ToC false headings, restore hierarchy after an embedded sub-report, or validate the `2.43` page case.

## Verification status by comment

| Comment | Status | Root cause / next action |
|---|---|---|
| Missing body text | **Fixed and verified** | Xujin confirms the missing text is now present. |
| Paragraph split with no overlap | **Not fixed; acceptance gap** | Recursive overlap does not cross preprocessor region boundaries. |
| Very short table/header chunks | **Confirmed false-boundary defect** | Valid short sections may remain separate. The defect is a table line being misdetected as a new section and splitting the real section. |
| Section path polluted by `Generator Mechanical` | **Not covered** | A table/ToC line is being accepted as a heading and remains active as hierarchy context. |
| Header at end / `3.15 TURBINE BUCKET(S)` ToC chunk | **Not fixed by duplicate cleanup** | The cleanup only removes an exact next heading across a recognized section transition. This screenshot is a standalone ToC entry, not the exact duplicate case tested. |
| Generator ESN absent for `00f...` | **Confirmed residual defect** | The row exists and ran the postfix pipeline. Generator evidence is counted per page and peaks at 1, so the `>7` fallback never activates despite document-wide Generator evidence. |
| Item 4 metadata and missing `4.14` | **Fixed** | Xujin confirms this item. The focused test also retained `4.14`. |
| Steam Turbine body still `shared` in `429...` | **Confirmed residual defect** | ToC chunks are tagged Steam Turbine while the actual body `3.15` heading is `shared`; body Components selection fails on the real extracted layout. |
| `2.43` section mapped to page 558 | **Confirmed boundary defect; previously misclassified** | The chunk starts on page 558 before `## 2.43`, so page mapping follows the chunk start. The chunk retained stale `2.42` section metadata and crossed the `2.43` heading. |
| Gas Turbine `region_primary_esn` blank while type and `active_esns` are correct | **Confirmed enrichment defect** | `9ec...` has one active GT ESN, `298081`, but all 23 GT chunks have blank region ESN. Explicit GT/ST regions are not enriched like explicit Generator regions. |
| Short level-1/level-2 header chunks in `796...` | **Not fixed; acceptance gap** | Short semantic regions are deliberately retained to prevent source loss. Retrieval quality now requires a merge policy, not dropping them. |
| `Generator -> 2 Turbine` removed | **Fixed** | Xujin confirms Generator was removed from the Turbine section. |
| Summary section paths still affected by ToC | **Not covered** | The hierarchy fix only detached an incompatible unnumbered equipment parent from a numbered level-0 root. It did not suppress all ToC-seeded headings. |
| `Generator -> 3 Generator -> ...` | **Confirmed defect; decision resolved** | Keep numbered `3 Generator`; remove only the extra unnumbered parent leaked from the ToC or previous section. |
| Missing `3.4` after embedded sub-report | **New hierarchy defect** | Embedded report headings reset the stack; the outer report hierarchy is not restored when the embedded report ends. |
| `3.4.7 Generator Field` duplicated in section 1 and 2 | **New hierarchy defect** | Conflict/re-anchoring can produce a duplicate self-parent path; no regression test covers this state. |
| `Unit Serial #: 336X860` | **New ESN extraction issue** | Generic `Unit Serial` is not recognized by deterministic v2 patterns. |

## Detailed analysis

### Live dev run evidence

Read-only queries were run against:

- `vaid.ai_std_con_field_service_report.fsr_metadata_v2`
- `vaid.ai_std_con_field_service_report.fsr_chunks_v2`
- `vaid.ai_sot_field_service_report.fsr_v2_repair_scope`

All seven original documents have metadata rows and completed P1, P2, and P3 in repair run `postfix-dev-cce00fc-20260925`, completed on 2026-09-26. The new `895613a2-8568-4d17-bd45-b53c935645e9` PDF is the only queried document without a dev metadata/chunk row.

The repair scope records profile `v2` and the expected final-master/shared strategies, but `deployed_code_commit` and `chunking_parameters` are null. That is a traceability gap, not evidence that the run used old rows. The metadata and chunks were rewritten together on September 26 and the resulting counts match the repair scope.

### 1. No overlap across section boundaries

P2 calls `split_region_first_with_offsets()`. It first treats preprocessor regions as authoritative semantic boundaries, then invokes recursive splitting independently inside each region with the configured overlap.

This means overlap exists only when one region is larger than the chunk size and is recursively split into multiple chunks. Two adjacent section regions never overlap, even if a paragraph was incorrectly divided between them.

The September 25 no-drop fix addressed a different problem: a short region could disappear because it was below `FSR_MIN_CHUNK_SIZE`. It retained that region, but did not change boundary semantics. Xujin's observation is therefore valid and consistent with the implementation.

**Root cause:** section detection can place a region boundary inside a paragraph, and the region-first chunker forbids cross-region overlap.

**Decision:** no overlap is required between valid sections. Fix the false section boundary that divides a paragraph; do not add cross-section overlap or blur equipment attribution.

### 2. Short header-only chunks and table splits

The tests assert that a short section such as `1.3 Work Scope` must be retained. That behavior is acceptable for a genuine section. The missing protection is a test proving that table content cannot create a false region boundary.

The screenshot showing isolated `2 Turbine SECTION`, `2.2 Inlet Section CATEGORY`, and similar rows is the direct tradeoff of the retention rule. If a table row such as `Generator Mechanical` is falsely detected as a section header, the same behavior creates a short chunk and makes that false heading the parent of later chunks.

**Root cause:** the no-drop solution correctly retains valid short semantic regions, but heading detection lacks sufficient table/ToC rejection. A table line can be promoted to a section heading, split the real section, and create a misleading short chunk.

**Decision:** keep the current behavior for genuine short sections. Do not add a general rule that merges all short or heading-only chunks forward.

**Recommended correction:**

- require stronger evidence for headings inside table-like text
- reject table-derived false headings before regions are built
- keep the content within the actual parent section when a false candidate is rejected
- add retrieval checks ensuring header-only chunks do not consume top-k results

### 3. ToC entries and trailing headings

The duplicate-heading cleanup is intentionally narrow. It runs only when adjacent chunks have different recognized section metadata and the final line of the prior chunk exactly matches the next section's heading, including the supported vertical-text form.

The `3.15 TURBINE BUCKET(S) ... 67 ... 71` screenshot is a ToC entry emitted as its own chunk. It is followed by other ToC entries, not by the corresponding body section. Therefore, it does not satisfy the cleanup contract and remains.

After this false `3.15` section becomes active, later chunks can inherit `section_1 = 3.15 TURBINE BUCKET(S)`.

**Root cause:** ToC classification failed before chunk cleanup. The cleanup was never intended to remove arbitrary ToC chunks.

**Recommended correction:** fix ToC span identification and suppress ToC-derived section candidates from persisted body hierarchy. Keep exact duplicate cleanup as a separate final guardrail.

### 4. Generator ESN for `00f...`

The dev row exists and completed the postfix repair run. It has `primary_esn=198090`, `primary_equip_type=Generator`, `gt_esn=198090`, empty `gen_esn`, and 28 chunks. All 28 chunks are `shared` with blank region ESNs.

Persisted regions show only `unresolved_turbine` and `outside_components_appendix`; no region records `generator_toc`, `generator_evidence_threshold`, or `generator_esn_resolution`. The highest persisted `generator_evidence_count` is 1.

The profile applies the threshold separately to each page. Xujin's document-wide count of 12 Generator mentions therefore does not trigger a threshold of `>7`. Although the shared hierarchy recognizes a `Generator` section path, the final-master profile does not use an overlaid section path to establish `generator_presence_detected`. IBAT resolution is never called.

**Confirmed root cause:** the fallback's evidence scope is page-level while the expected behavior is document/Components-level, and shared Generator hierarchy evidence is ignored by the Generator-presence gate.

**Recommended correction:** aggregate qualified evidence across the selected Components span, or treat a high-confidence shared Generator section as presence evidence. Keep page-level attribution separate so document-wide evidence does not incorrectly retype every page as Generator.

### 5. Steam Turbine still assigned to `shared`

Live rows confirm the exact failure. In `429...`:

- chunk 4, page 2 is the dotted `3.15 TURBINE BUCKET(S)` ToC entry and is `shared`
- chunks 5-6, pages 2-3 are ToC text incorrectly tagged `Steam Turbine`
- chunk 67, page 70 is the actual `## 3.15 TURBINE BUCKET(S)` body heading and is `shared`
- only 2 of 111 chunks are tagged Steam Turbine; all 111 have blank region ESNs
- persisted regions contain 104 `shared/unresolved_turbine` spans but only one explicit Steam Turbine region

**Confirmed root cause:** the real ToC layout is not rejected by `_body_section_match()`. The profile starts marker attribution in the ToC and later applies unresolved page fallback to the body. The synthetic ToC tests do not represent this extracted layout.

**Recommended correction:** add this document's parsed page shape as a fixture, improve ToC-page detection, and validate the selected body Components offset before accepting equipment markers.

### 6. Section hierarchy findings in `796...`

The September 25 hierarchy fix had one narrow contract: when a numbered level-0 equipment root such as `2 Turbine` has an open unnumbered parent with a different equipment type such as `Generator`, detach it. Xujin confirms that correction worked.

The remaining observations are different:

- `3 Generator` is the valid numbered parent for content under section 3. Remove only an extra unnumbered `Generator` parent leaked from the ToC or a previous section.
- ToC headings in the summary remain because the fix did not remove ToC candidates generally.
- after an embedded sub-report, the outer `3.4` hierarchy is not restored before `3.4.2 Hydrogen Coolers`
- `3.4.7 Generator Field` appears as both section 1 and section 2, indicating a duplicate/self-parent hierarchy path

The expected path is `3 Generator -> 3.4 Generator Inspections & Clearances -> 3.4.2 Hydrogen Coolers`, not `Generator -> 3 Generator -> 3.4.2 Hydrogen Coolers`. The hierarchy fix must distinguish the valid numbered root from leaked unnumbered context. The remaining defects require an embedded-report boundary model or a stack snapshot/restore rule, plus a path invariant that the same normalized heading cannot occur twice consecutively.

The dev table quantifies the impact for `796...`: 44 of 160 chunks are below 450 characters, 18 are 50 characters or shorter, 53 retain the unnumbered `Generator` root, 22 have duplicate adjacent section levels, and 9 have a `3.4.x` child directly under `3 Generator` with the `3.4` parent missing.

### 7. `2.43` on page 558

The previous RCA incorrectly marked a combined “last section/page mismatch” finding resolved based on `153...` retaining `4.14` at page 659. Xujin's `2.43` observation concerns `93c...` and was not exercised by that test.

P2 assigns `page_number` from the chunk start offset. A wrong result can come from:

- the heading text physically occurring in an embedded ToC/sub-report on page 558
- an incorrect page-offset map
- a chunk starting on page 558 while later content is the part being inspected
- a false heading candidate copied from another report segment

Live data shows chunk 23 starts on page 558 with Generator alignment prose and later contains `## 2.43 CLOSING DIMENSIONS ON INSTALLED H2 SEALS`. Its persisted section metadata is still `2.42 TURBINE COMPARTMENT AND BELLMOUTH INSPECTION`.

The displayed page is therefore consistent with the chunk's start; this is not primarily a page-offset defect. The defect is that the region/chunk crosses a real `2.43` heading without creating a new section boundary, so both section metadata and retrieval context are wrong.

**Recommended correction:** add the exact extracted heading transition as a regression fixture and determine why `2.43` was not emitted as a heading candidate or region boundary.

### 8. Blank Gas Turbine `region_primary_esn`

`active_esns` is document-level inventory. `region_primary_esn` is assigned only when the region resolver has a unique local, parent, single-type, or IBAT-train candidate. Correct equipment type plus blank region ESN is therefore possible by design.

Live data removes the ambiguity for `9ec...`: `active_esns` is `["298081", "337X543"]`, metadata has `gt_esn=298081`, and all 23 Gas Turbine chunks have blank `region_primary_esn`. The one Generator chunk correctly receives `337X543` through `ibat_train`.

**Confirmed root cause:** final-master post-processing enriches explicit Generator regions with the resolved Generator ESN, but has no equivalent deterministic enrichment for explicit Gas Turbine or Steam Turbine regions.

**Recommended correction:** enrich explicit GT/ST regions from a unique document-level ESN of the same type, with the same ambiguity safeguards used by shared region resolution.

## New issue: `Unit Serial #: 336X860`

The attached appendix cover page visibly contains:

- `Generator Borescope Inspection Report`
- `Unit Serial #: 336X860`

Current deterministic v2 patterns support labels such as `Generator Serial`, `Equipment Serial`, and `ESN`. They do not support generic `Unit Serial`. The broad token collector can add an alphanumeric ESN only after at least three occurrences, so a single cover-page occurrence is not sufficient. The LLM ESN path may detect it in some versions/runs, which explains the remembered inconsistent behavior, but it is not a deterministic guarantee.

**Classification:** new issue, not a failure of the September 25 postfix changes.

**Decision pending:** hold this change until feedback is received. A possible correction is an anchored `Unit Serial` pattern only when Generator ownership is established by the same page or local report context, but it should not be implemented yet.

Acceptance tests if this change is approved:

1. Generator report title plus `Unit Serial #: 336X860` yields Generator ESN `336X860`.
2. The same label in a non-Generator appendix remains untyped unless another equipment signal exists.
3. An embedded Generator sub-report adds the ESN without replacing the main document's primary ESN.
4. The ESN is available to Generator regions within that embedded report, not unrelated outer-report regions.

## Why the existing tests passed

The focused suite proved these exact contracts:

- short semantic regions are not silently dropped
- split tails retain source coverage
- an exact duplicated next heading can be removed
- nonmatching vertical text is retained
- final-master section metadata is overlaid
- structurally obvious ToC Components pages are skipped
- one unique train-scoped Generator ESN is resolved
- an incompatible `Generator -> 2 Turbine` parent is detached

It did not prove:

- overlap across region boundaries
- merge behavior for heading-only regions
- all real-world ToC and table layouts are rejected as headings
- same-equipment redundant roots are removed
- hierarchy is restored after an embedded sub-report
- section paths cannot contain duplicate normalized headings
- the `2.43` page mapping is correct
- `Unit Serial` is an ESN label

## Recommended next steps

1. Require `deployed_code_commit` and `chunking_parameters` in repair-scope records; both are null in the verified postfix run.
2. Add diagnostics for each persisted chunk: region boundaries, heading source/confidence/reason codes, ToC classification, and profile version.
3. Preserve genuine short sections, but prevent table lines from creating false section boundaries and separate chunks.
4. Do not add overlap across valid section boundaries; fix false boundaries that split paragraphs.
5. Add real extracted fixtures for `429...`, `796...`, `93c...`, and the new `895...` PDF cases.
6. Treat embedded sub-report hierarchy restoration as a new issue; hold `Unit Serial` extraction pending feedback.

## Evidence reviewed

- original issues and September 25 RCA
- Xujin's September 28 message
- attached screenshots for `3.15`, blank region ESN, short section chunks, and `336X860`
- current `fsr_v2` branch at commit `cce00fc`
- final-master profile, shared hierarchy builder, region-first chunker, ESN patterns, and focused tests
- September 25 isolated-run verification scripts
- read-only live dev queries against metadata, chunks, and repair-scope tables on 2026-09-28

No additional image downloads were used after the VS Code/Copilot temporary image URLs returned upstream 404 errors.
