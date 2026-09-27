# Post-Fix Verification Analysis

Updated: 2026-09-25  
Scope: Findings received after dev verification of the section-path and final-master-report changes

## Executive conclusion

The findings are not one defect and should not be addressed with one broad parser change.

There were five confirmed implementation gaps, all addressed in the current code change set:

1. P2 drops valid short region output below `FSR_MIN_CHUNK_SIZE` instead of retaining or merging it. This can remove body content across document families.
2. The final-master-report profile replaces the shared preprocessor regions without carrying `section_path`, so `section_1` through `section_5` are null by construction. P2 then performs region-first recursive chunking, not section-based chunking.
3. The final-master-report profile uses the first matching `N. COMPONENTS` and scans anchored equipment labels from that point. A Components occurrence and labels in the primary ToC can therefore become attribution boundaries before the body Components section.
4. Generator ESN fallback resolution runs only when an unlabeled page crosses the Generator fallback threshold. An explicit Generator Components label does not trigger the same train-scoped IBAT resolution when the document has no locally extracted Generator ESN.
5. In the shared hierarchy, a numbered level-0 equipment root can inherit an incompatible open unnumbered equipment header, producing paths such as `Generator -> 2 Turbine`.

The implementation now merges short fragments without silently dropping split tails, overlays shared section hierarchy onto final-master equipment regions, selects body Components outside structurally identified ToC pages, runs guarded Generator ESN resolution for explicit Generator labels, and detaches numbered equipment roots from incompatible unnumbered equipment parents. Code review also found and fixed two follow-up defects: repeated Components entries in multi-page ToCs and a stale `end_char` after duplicate-heading removal.

One observation still requires data/run reconciliation before a code change:

- chunks existing without a corresponding `metadata_v2` row is not possible through the current P2 claim path against the same table pair; it indicates mismatched catalog/schema/table, document-ID normalization, stale output, or an interrupted/manual workflow

The requested 1.5x recursive size and overlap change is reasonable as a targeted experiment, but not as an unqualified global default change. The shared P2 path processes all profiles, so a global increase would affect chunk size, retrieval precision, embedding cost, and table-boundary behavior for unrelated documents.

## Agreed priority map

This map follows the numbering in `Issues`.

### Final Master Reports

1. **P1:** missing body context/pages. Diagnose and fix first because missing text can also cause downstream section and equipment-tagging failures.
2. **P3:** null section fields. Fix if straightforward; fully recursive fallback is acceptable for this cycle.
3. **P2:** missing Generator ESN. Resolve only one active train-scoped candidate and exclude `SY` identifiers.
4. **P3/P2:** chunks without metadata remain a P3 investigation and do not block chunking/tagging validation; the isolated test-table run confirmed the final `4.14` section is persisted.
5. **P2:** incorrect Steam Turbine/shared assignment. Validate the failing Steam Turbine case separately because Generator and Gas Turbine examples succeed.
6. **P3:** add the five observed irregular Generator labels within the final-master profile.

### 36-Document Set

1. **P3:** remove only exact duplicated boundary headers; accept isolated vertical words such as `FROM` for now.
2. **After final-master and version-format work:** test larger chunk size and overlap with cross-format regression controls.
3. **P2 and highest priority in this set:** stop an end-of-ToC `Generator` heading from becoming the parent of Turbine body sections.

## Implementation status

| Item | Status | Validation |
|---|---|---|
| P1 retain short semantic content without losing split tails | Code complete; review follow-up fixed | Short fragments merge into neighboring chunks, sole nonsemantic noise remains filtered, and semantic standalone regions remain retained; affected-document dev reprocessing pending |
| P2 resolve Generator ESN from an explicit Generator label | Code complete; review follow-up fixed | Candidate and existing-metadata `SY` exclusion covered; dev reprocessing pending |
| P2 missing final section | Resolved in test-table output | Persisted chunk 17 begins with `## 4.14`, at page 659 and character offset 6181; the earlier absence was a verifier regex false negative |
| P2 Steam Turbine/shared attribution | Code complete; review follow-up fixed | Page-aware selection skips repeated Components entries across multi-page ToCs, accepts early body Components, and preserves the first section when no primary ToC exists; affected-document dev reprocessing pending |
| P2 end-of-ToC Generator parent leakage | Code complete; test-table verified | `796f...` proved the transition at offsets 7978/8233; focused P1/P2 rerun produced 160 chunks with zero `Generator -> 2 Turbine` paths and zero bad offsets |
| P3 null section fields | Code complete | Shared section hierarchy is overlaid without replacing equipment metadata; regression verifies contiguous full-document region coverage; dev reprocessing pending |
| P3 chunks without metadata | Not started | Operational investigation; does not block chunking/tagging validation |
| P3 irregular Generator labels | Code complete | Five approved labels and arbitrary-label rejection pass; dev reprocessing pending |
| P3 duplicate trailing header | Code complete; review follow-up fixed | Cleanup requires a section transition, updates `end_char`, preserves repeated same-section prose, and retains nonmatching vertical `FROM` text |
| Larger chunk size/overlap experiment | Deferred | Run after final-master and version-format fixes |

### Code review outcome

The reviewed working-tree change set has no remaining code-review findings. Review found and corrected:

- body Components selection choosing the second match even when a multi-page ToC contained several repeated entries; selection now skips matches on pages with structural ToC signals
- duplicate-heading cleanup changing `chunk_text` without updating `end_char`; the retained source boundary is now reflected in the offset
- cleanup comparing arbitrary adjacent text; it now runs only across a section transition and matches the recognized next section heading

Validation: `93 passed, 5 subtests passed` in `tests/fsr_v2/test_preprocessor_v2.py`. The isolated 12-document run completed P1/P2 for all documents with 719 chunks, zero bad offsets, and zero orphan chunks. Changed-file diagnostics and `git diff --check` are clean.

### Remaining work

1. Commit, merge, and deploy the verified shared-hierarchy correction to dev.
2. Reprocess the 12-document corpus in dev and verify persisted source coverage, equipment/ESN attribution, section fields, and page mappings.
3. Reconcile any reported chunk rows without metadata using fully qualified tables, document IDs, run IDs, and pipeline versions; the isolated run found zero orphans.
4. Provision an isolated Vector Search index before applying P3 to test-table chunks, or defer P3 to the controlled dev run.
5. Run the larger chunk-size/overlap experiment only after the format-specific fixes are verified, with unrelated document-family controls.

## Evidence reviewed

- verification chat transcript in `Issues`
- screenshots `image.png` through `image (11).png`; numbering below follows the transcript's stated ordering
- prior section-path RCA and implementation plan
- prior final-master-report RCA and implementation plan
- pushed final-master fix at commit `e1c29ea` plus the current reviewed working-tree follow-ups
- final-master-report implementation commits `4eec9d5` and `bf28ec8`
- shared section-heading implementation commit `7721f72`

The 2026-09-25 verification used isolated `ms_test` metadata, chunk, scope,
rollback, run-log, DQ, and equipment-map tables. No regular dev target table or
Vector Search index was changed.

## Control path

The relevant processing path is:

1. P1 parses PDF pages and creates one `full_text` plus page offsets.
2. `metadata_processor.run()` selects either the shared preprocessor or the final-master-report profile.
3. P1 persists document metadata and `preprocessor_regions` in `fsr_metadata_v2`.
4. P2 claims only completed metadata rows, reloads parsed text, and calls `split_region_first_with_offsets()`.
5. Every region is recursively chunked with `FSR_CHUNK_SIZE=3800`, `FSR_CHUNK_OVERLAP=150`, and `FSR_MIN_CHUNK_SIZE=450` unless overridden at runtime.
6. P2 writes `fsr_chunks_v2` and deletes stale chunks for each successfully rewritten document.

This distinction matters: the current production P2 path is always `region_first:recursive`. It does not invoke the chunker's section strategy.

## Finding-by-finding analysis

### 1. Missing body context and pages

Examples: `00f23784-d121-4595-b61d-49d223253a05`, `153595df-646d-410b-8ee5-371fa057c1f4`; transcript images 0-3.

**Assessment: P1 and the highest overall priority. Not acceptable; confirmed systemic loss condition, exact document cause still requires tracing.**

The final-master profile calls `complete_region_coverage()`, and P2 also completes malformed region coverage. The profile is therefore not intentionally excluding uncovered pages.

Combining short sections with adjacent content inside the same region is expected recursive-chunking behavior. The defect is narrower: when a short section is emitted as its own semantic region, its only chunk can be discarded instead of being retained or combined with a neighboring chunk.

However, `split_with_offsets()` discards every chunk whose stripped text is shorter than `min_chunk_size`. In region-first mode, a valid short page or section can be the only output of its region. It is then removed without being merged into a neighbor. This is a confirmed content-loss condition and can affect all document profiles.

For each cited document, compare these stages before changing heading rules:

1. raw parsed page text and page offsets
2. P1 `full_text` and `preprocessor_regions`
3. pre-filter recursive chunks
4. chunks remaining after the 450-character filter
5. persisted chunk character/page coverage

If the missing text is absent in stage 1, the cause is extraction. If present through stage 3 but absent after stage 4, the minimum-size filter is the cause. If present after stage 4 but absent in the table, the cause is persistence or run/table selection.

**Recommended correction:** replace drop-only minimum-size filtering with deterministic neighbor merging, or retain a short chunk when it is the sole output for a semantic region. Add a document-level coverage assertion so non-whitespace source text cannot disappear silently.

### 2. Null section fields and apparent section-based chunking

Example: `00f23784-d121-4595-b61d-49d223253a05`; transcript image 4.

**Assessment: P3. Fix if straightforward; fully recursive fallback is acceptable for this cycle.**

The final-master profile first runs the shared preprocessor, but then constructs a new region list containing equipment/page-fallback metadata only. It does not overlay those labels onto the shared regions and does not copy `section_path` into the replacement regions. P2 reads section fields only from each region's `section_path`, so null `section_1` through `section_5` are expected from the current implementation.

The chunks may appear section-based because category markers or page boundaries happen to align with report sections. They are still recursively split inside equipment regions.

**Recommended correction:** intersect/overlay final-master equipment attribution with shared section spans rather than replacing them. Preserve the shared section hierarchy and add profile attribution metadata to the resulting intervals. This is safer than implementing a second section parser in the profile. Defer this work if it materially complicates the P1/P2 fixes; recursive fallback is an acceptable temporary result.

### 3. Section header appears at the end of the preceding chunk

Examples: final-master reports and 36-document output; transcript images 4, 9, and 10.

**Assessment: P3. Accept isolated OCR-oriented words such as `FROM`; do not accept a duplicated next-section header when it can be removed deterministically.**

The current P2 path preserves extracted text order. It has no orientation metadata and no trailing-heading cleanup. Removing text based only on vertical-looking line breaks would risk deleting real table columns and body content in other documents.

A safe correction is limited to an exact duplicated boundary case: remove a trailing normalized heading only when the same heading is the recognized start of the immediately following region/chunk. Without that agreement, retain the text. Coordinate- or orientation-based cleanup should wait until the parser supplies reliable layout metadata.

### 4. Generator ESN missing from `gen_esn` and `active_esns`

Examples: `00f23784-d121-4595-b61d-49d223253a05` and `d72f404c-7d35-49e9-a341-40266e687652`.

**Assessment: P2. Not acceptable when Generator ownership is structurally established and one train-scoped active Generator candidate exists.**

The train-scoped IBAT lookup added in `bf28ec8` is invoked only when page fallback sets `generator_fallback_detected`. Explicit `GENERATOR` category markers do not set that flag. Therefore, an explicitly labeled Generator section can still leave `gen_esn` empty when no Generator ESN is extracted locally.

`active_esns` is built from document and region ESNs, so the missing `gen_esn` naturally propagates there.

**Recommended correction:** trigger one shared document-level Generator ESN resolution whenever either explicit Components labels or qualified fallback evidence establishes Generator presence. Keep the existing safeguards: require a turbine anchor, exclude `SY` identifiers, accept exactly one active train-scoped non-`SY` candidate, and record zero or multiple candidates as unresolved. Do not retype unlabeled Generator-evidence pages as Generator; retaining `shared` for those pages is intentional. The current IBAT resolver already excludes identifiers matching `SY` followed by seven digits; regression tests should preserve that rule.

### 5. Chunks exist but no `metadata_v2` row

Examples: `153595df-646d-410b-8ee5-371fa057c1f4` and `42944a96-6210-4f8a-ba54-fa1d5cd2a29b`; transcript image 5.

**Assessment: P3 investigation. Not a heading-parser defect and does not block chunking/tagging validation.**

Current P2 can claim a document only from the configured metadata table with `metadata_status='completed'`. A missing final section such as `4.14` cannot explain a missing document row. If chunks exist while metadata does not, the compared rows did not come through the current same-table execution path.

Check fully qualified table names, workspace/environment, normalized document IDs, `run_id`, pipeline version, and whether chunks are stale from an earlier/manual run. Also verify that a repair or cleanup did not remove metadata independently. Add a referential-integrity check from chunks to metadata to the release gate.

### 6. Last section/page mismatch, including `4.14` and page 658

Examples: `153595df-646d-410b-8ee5-371fa057c1f4` and `93c2180b-f866-4521-b090-b88442c6dcf1`; transcript images 5-7.

**Assessment: resolved in persisted test-table output.**

The reported format places the page number before the section title. A focused normalized-text regression using `658` followed by `4.14 Final Inspection` successfully produces the heading candidate, so that ordering alone is not the root cause. P2 assigns a chunk's page from its starting character, so overlap or a heading at a page boundary can produce a surprising displayed page. A short final section can additionally be removed by the minimum-size filter.

The parsed artifact contains `## 4.14 1DPS2018071_Screen dump Shut down .pdf`, and the persisted result contains it in chunk 17 at page 659 and character offset 6181. The earlier aggregate check used an incompatible Spark SQL regex and was a verifier false negative, not missing output. No additional heading-order rule is required.

### 7. Steam Turbine body content is `shared`, while ToC content is Steam Turbine

Example: `42944a96-6210-4f8a-ba54-fa1d5cd2a29b`; transcript finding 5.

**Assessment: P2. Not acceptable; confirmed profile-boundary weakness.**

The profile selects the first anchored `N. COMPONENTS` occurrence. In these reports that occurrence may be in the primary ToC. It then recognizes equipment marker lines from that point, so ToC category labels can become real attribution boundaries. The implementation does not distinguish a ToC Components occurrence from the body Components section.

The anchored Steam Turbine marker regex itself supports `STEAM TURBINE` and `STEAM TURBINE - ...`. Generator and Gas Turbine examples are being detected successfully while the cited Steam Turbine case fails. The incorrect result is therefore more likely a Steam-specific extracted-line shape or Components/body anchoring problem than a generally missing equipment-label rule.

**Recommended correction:** identify all Components candidates, exclude the primary ToC span from body attribution, and select/validate the body Components occurrence using page position and the next real top-level boundary. Keep marker recognition anchored and restricted to the selected Components body span.

### 8. Region equipment type works but region ESNs are missing

Example: `93c2180b-f866-4521-b090-b88442c6dcf1`.

**Assessment: partially expected, but incomplete for explicit equipment labels.**

Equipment type and ESN are separate facts. `shared` regions should not receive a guessed ESN. Explicit Gas/Steam/Generator regions should receive a region ESN only when a unique local, inherited, document-level, or train-scoped candidate is available. The final-master profile currently creates equipment regions after the shared ESN resolution and does not enrich those new regions with resolved per-type ESNs.

Overlaying profile labels onto the shared section regions should be followed by deterministic per-type ESN enrichment. Ambiguous or absent candidates must remain empty with a reason code.

### 9. Irregular Generator Components labels

Example: `9ecb1354-1f3a-4634-8a74-12943aff45a9`; transcript image 8.

Observed exact labels:

- `GENERATOR ASSEMBLED`
- `GENERATOR EXCITATION`
- `GENERATOR ALIGNMENT`
- `GENERATOR COOLERS`
- `GENERATOR VISUAL`

**Assessment: P3. Acceptable to fix with a closed, profile-scoped allowlist.**

The current marker pattern accepts bare `GENERATOR` or a suffix introduced by `-` or `:`. It does not accept these five space-separated labels. The supplied occurrence counts justify support, especially `GENERATOR ASSEMBLED`.

Add exact, anchored, all-caps alternatives only inside the validated final-master Components body span. Do not change the shared preprocessor's generic Generator detection and do not allow arbitrary `GENERATOR <words>`, because that would promote prose and other formats.

When one of these labels establishes Generator presence, run the same unique train-scoped ESN resolution described in finding 4. Attribution of the category span should follow the explicit-label contract; unlabeled fallback spans can remain `shared`.

### 10. Recursive chunk size and overlap for the 36-document set

Example: DC leakage test split across two chunks; transcript image 11.

**Assessment: accept as a controlled experiment, not as a global default decision.**

The effective defaults are 3800 characters and 150 characters of overlap. A literal 1.5x experiment is therefore 5700 and 225, not 6000 and 300. The latter values are 1.58x and 2x respectively.

Run both the baseline and proposed values on the affected set plus representative final-master, normal UUID, table-heavy, and short-section controls. Compare:

- source-text coverage
- chunks per document and size distribution
- table row continuity
- retrieval quality for known questions
- embedding volume/cost
- equipment and section boundary crossings

Prefer profile/cohort-specific runtime configuration if the larger size benefits the 36-document format but degrades other formats. Fix short-region dropping independently; increasing chunk size does not solve that defect.

### 11. Section 1 is `Generator` for the 36-document report

**Assessment: P2 and the highest-priority issue in the 36-document set. Do not solve it in a system prompt.**

The reported path `Generator -> 2 Turbine -> 2.1 Auxiliaries` indicates that `Generator` likely leaked from the end of the ToC and was then retained as the parent for body sections. The persisted section path is created before any retrieval prompt, so prompt guidance cannot correct stored hierarchy or filtering fields.

The parsed artifact showed an unnumbered `Generator` region ending at offset 8233, where numbered root `2 Turbine` began. The hierarchy builder retained the incompatible Generator parent. The implemented rule detaches a numbered level-0 candidate only when its open unnumbered parent has a different equipment type. It preserves valid same-equipment nesting such as `Generator -> 3 Generator`.

The focused regression passes, as does the full preprocessor suite. The isolated P1/P2 rerun for `796f...` produced `2 Turbine -> 2.1 Auxiliaries`, 160 chunks, zero bad offsets, and zero `Generator -> 2 Turbine` paths.

## Acceptance decisions

| Finding | Decision | Rationale |
|---|---|---|
| Missing body pages/context | P1 fix before rollout | Silent source-text loss can also cause downstream tagging failures |
| Null section metadata in final-master reports | P3 / defer if complex | Recursive fallback is acceptable for this cycle |
| Isolated vertical `FROM` text | Accept for now | No reliable orientation signal; broad cleanup risks data loss |
| Exact duplicated next header at prior chunk end | P3 fix when deterministic | Safe only when matched to the next recognized boundary |
| Missing unique train-scoped Generator ESN | P2 fix | Resolve one active non-`SY` train candidate |
| Chunks without metadata row | P3 investigation | Does not block chunking/tagging validation |
| Missing final section/page mismatch | Resolved in isolated output | Chunk 17 retains `4.14` at page 659 and offset 6181 |
| ToC attributed as equipment/body left shared | P2 fix | First Components occurrence is not a safe body boundary; verify Steam-specific case |
| Missing region ESN with no unique candidate | Accept with reason code | Guessing would be worse than empty attribution |
| Five irregular Generator labels | P3 fix in final-master profile only | Closed observed set limits cross-document impact |
| 1.5x chunk settings | Experiment only | Shared global change has retrieval and cost impact |
| Section 1 equals Generator | P2 fix | Prevent end-of-ToC Generator state from leaking into body hierarchy |

## Implementation order used

1. P1: add stage-level coverage diagnostics, reproduce the missing-text documents, and stop dropping sole/valid short-region chunks.
2. P2: resolve and propagate one active non-`SY` Generator ESN for explicit and fallback Generator presence.
3. P2: trace the affected parsed artifact and persisted offsets for the reported missing final section.
4. P2: select the body Components span, exclude primary-ToC markers, and verify the Steam Turbine case separately from successful Generator/Gas Turbine controls.
5. P2: prevent an incompatible unnumbered equipment state from becoming the parent of a numbered equipment root.
6. P3: reconcile chunk-only documents against fully qualified tables, runs, and IDs; add an orphan-chunk integrity check.
7. P3: preserve final-master section paths through a section-region overlay if this remains straightforward; otherwise retain recursive fallback for this cycle.
8. P3: add the five exact Generator labels inside the final-master profile.
9. After final-master and version-format fixes: run the 36-document chunk-size experiment with control documents.
10. P3: add only deterministic duplicated-boundary cleanup; defer general vertical-text removal.

## Regression gates

Do not promote the changes unless all of the following hold:

- every non-whitespace source interval is represented in a chunk or has an explicit exclusion reason
- short valid sections are retained or merged, never silently dropped
- final-master `section_path` survives equipment attribution
- primary-ToC markers do not assign body equipment regions
- body `GAS TURBINE`, `STEAM TURBINE`, `GENERATOR`, and `UNCATEGORIZED` transitions are correct
- the five approved Generator variants match only inside the final-master Components body span
- a Generator ESN is populated only for one active train-scoped non-`SY` candidate
- `SY` identifiers are never selected as Generator ESNs by IBAT fallback
- ambiguous Generator candidates remain unresolved and observable
- no chunk row is orphaned from the configured metadata table
- section/page offsets are monotonic and map to the expected source pages
- chunk-setting experiments include unrelated document-family controls
- shared preprocessor and final-master profile tests both pass

## Image-reference note

The transcript's image numbering is internally consistent with the files present in the folder. Because the chat client repeatedly returned an upstream 404 while resolving image attachments, this analysis does not depend on re-downloading or embedding those files. The transcript, previously opened workspace copies, and current code are the evidence sources used here.