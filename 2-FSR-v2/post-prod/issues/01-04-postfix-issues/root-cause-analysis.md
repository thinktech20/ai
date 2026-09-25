# Post-Fix Verification Analysis

Updated: 2026-09-25  
Scope: Findings received after dev verification of the section-path and final-master-report changes

## Executive conclusion

The findings are not one defect and should not be addressed with one broad parser change.

There are four confirmed implementation gaps:

1. P2 drops valid short region output below `FSR_MIN_CHUNK_SIZE` instead of retaining or merging it. This can remove body content across document families.
2. The final-master-report profile replaces the shared preprocessor regions without carrying `section_path`, so `section_1` through `section_5` are null by construction. P2 then performs region-first recursive chunking, not section-based chunking.
3. The final-master-report profile uses the first matching `N. COMPONENTS` and scans anchored equipment labels from that point. A Components occurrence and labels in the primary ToC can therefore become attribution boundaries before the body Components section.
4. Generator ESN fallback resolution runs only when an unlabeled page crosses the Generator fallback threshold. An explicit Generator Components label does not trigger the same train-scoped IBAT resolution when the document has no locally extracted Generator ESN.

Two observations require data/run reconciliation before a code change:

- chunks existing without a corresponding `metadata_v2` row is not possible through the current P2 claim path against the same table pair; it indicates mismatched catalog/schema/table, document-ID normalization, stale output, or an interrupted/manual workflow
- page and final-section mismatches must be traced through parsed text, P1 regions, and P2 offsets before assigning them to heading recognition

The requested 1.5x recursive size and overlap change is reasonable as a targeted experiment, but not as an unqualified global default change. The shared P2 path processes all profiles, so a global increase would affect chunk size, retrieval precision, embedding cost, and table-boundary behavior for unrelated documents.

## Evidence reviewed

- verification chat transcript in `Issues`
- screenshots `image.png` through `image (11).png`; numbering below follows the transcript's stated ordering
- prior section-path RCA and implementation plan
- prior final-master-report RCA and implementation plan
- current implementation at commit `371dfcd`
- final-master-report implementation commits `4eec9d5` and `bf28ec8`
- shared section-heading implementation commit `7721f72`

No production or dev table queries were run as part of this document. Findings that depend on persisted rows are therefore marked for verification rather than stated as confirmed parser causes.

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

**Assessment: not acceptable; confirmed systemic loss condition, exact document cause still requires tracing.**

The final-master profile calls `complete_region_coverage()`, and P2 also completes malformed region coverage. The profile is therefore not intentionally excluding uncovered pages.

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

**Assessment: not acceptable if section metadata is part of the final-master-report contract.**

The final-master profile first runs the shared preprocessor, but then constructs a new region list containing equipment/page-fallback metadata only. It does not overlay those labels onto the shared regions and does not copy `section_path` into the replacement regions. P2 reads section fields only from each region's `section_path`, so null `section_1` through `section_5` are expected from the current implementation.

The chunks may appear section-based because category markers or page boundaries happen to align with report sections. They are still recursively split inside equipment regions.

**Recommended correction:** intersect/overlay final-master equipment attribution with shared section spans rather than replacing them. Preserve the shared section hierarchy and add profile attribution metadata to the resulting intervals. This is safer than implementing a second section parser in the profile.

### 3. Section header appears at the end of the preceding chunk

Examples: final-master reports and 36-document output; transcript images 4, 9, and 10.

**Assessment: accept isolated OCR-oriented words such as `FROM`; do not accept a duplicated next-section header when it can be removed deterministically.**

The current P2 path preserves extracted text order. It has no orientation metadata and no trailing-heading cleanup. Removing text based only on vertical-looking line breaks would risk deleting real table columns and body content in other documents.

A safe correction is limited to an exact duplicated boundary case: remove a trailing normalized heading only when the same heading is the recognized start of the immediately following region/chunk. Without that agreement, retain the text. Coordinate- or orientation-based cleanup should wait until the parser supplies reliable layout metadata.

### 4. Generator ESN missing from `gen_esn` and `active_esns`

Examples: `00f23784-d121-4595-b61d-49d223253a05` and `d72f404c-7d35-49e9-a341-40266e687652`.

**Assessment: not acceptable when Generator ownership is structurally established and one train-scoped active Generator candidate exists.**

The train-scoped IBAT lookup added in `bf28ec8` is invoked only when page fallback sets `generator_fallback_detected`. Explicit `GENERATOR` category markers do not set that flag. Therefore, an explicitly labeled Generator section can still leave `gen_esn` empty when no Generator ESN is extracted locally.

`active_esns` is built from document and region ESNs, so the missing `gen_esn` naturally propagates there.

**Recommended correction:** trigger one shared document-level Generator ESN resolution whenever either explicit Components labels or qualified fallback evidence establishes Generator presence. Keep the existing safeguards: require a turbine anchor, accept exactly one active train-scoped candidate, and record zero or multiple candidates as unresolved. Do not retype unlabeled Generator-evidence pages as Generator; retaining `shared` for those pages is intentional.

### 5. Chunks exist but no `metadata_v2` row

Examples: `153595df-646d-410b-8ee5-371fa057c1f4` and `42944a96-6210-4f8a-ba54-fa1d5cd2a29b`; transcript image 5.

**Assessment: not a heading-parser defect; not acceptable operationally.**

Current P2 can claim a document only from the configured metadata table with `metadata_status='completed'`. A missing final section such as `4.14` cannot explain a missing document row. If chunks exist while metadata does not, the compared rows did not come through the current same-table execution path.

Check fully qualified table names, workspace/environment, normalized document IDs, `run_id`, pipeline version, and whether chunks are stale from an earlier/manual run. Also verify that a repair or cleanup did not remove metadata independently. Add a referential-integrity check from chunks to metadata to the release gate.

### 6. Last section/page mismatch, including `4.14` and page 658

Examples: `153595df-646d-410b-8ee5-371fa057c1f4` and `93c2180b-f866-4521-b090-b88442c6dcf1`; transcript images 5-7.

**Assessment: not acceptable, but root cause is not yet proven.**

Page number preceding section title is not by itself enough to identify the cause. P2 assigns a chunk's page from its starting character, so overlap or a heading at a page boundary can produce a surprising displayed page. A short final section can also be removed by the minimum-size filter.

Trace the raw page offsets, heading candidate offset, region start/end, pre-filter chunk, and persisted `chunk_start_char`. Do not broaden the heading regex until this trace shows that the title was never recognized.

### 7. Steam Turbine body content is `shared`, while ToC content is Steam Turbine

Example: `42944a96-6210-4f8a-ba54-fa1d5cd2a29b`; transcript finding 5.

**Assessment: not acceptable; confirmed profile-boundary weakness.**

The profile selects the first anchored `N. COMPONENTS` occurrence. In these reports that occurrence may be in the primary ToC. It then recognizes equipment marker lines from that point, so ToC category labels can become real attribution boundaries. The implementation does not distinguish a ToC Components occurrence from the body Components section.

The anchored Steam Turbine marker regex itself supports `STEAM TURBINE` and `STEAM TURBINE - ...`. The incorrect result is therefore more likely a Components/body anchoring or extracted-line-shape problem than a missing Steam Turbine keyword.

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

**Assessment: acceptable to fix with a closed, profile-scoped allowlist.**

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

**Assessment: improve deterministically if a reliable larger parent exists; do not solve in a system prompt.**

The persisted section path is created before any retrieval prompt, so prompt guidance cannot correct stored hierarchy or filtering fields. If the document has a recognized larger report/root section, preserve it above the Generator equipment heading. If no reliable parent exists, `Generator` is preferable to inventing one.

Validate the change against Gas Turbine and mixed-equipment documents. Do not globally force a larger heading to win when hierarchy signals conflict, because attachments and embedded sub-reports legitimately restart numbering.

## Acceptance decisions

| Finding | Decision | Rationale |
|---|---|---|
| Missing body pages/context | Fix before rollout | Silent source-text loss is not acceptable |
| Null section metadata in final-master reports | Fix | Current profile discards shared section paths |
| Isolated vertical `FROM` text | Accept for now | No reliable orientation signal; broad cleanup risks data loss |
| Exact duplicated next header at prior chunk end | Fix when deterministic | Safe only when matched to the next recognized boundary |
| Missing unique train-scoped Generator ESN | Fix | Resolution exists but is not triggered by explicit labels |
| Chunks without metadata row | Investigate and add integrity gate | Cannot arise from current same-table P2 path |
| Missing final section/page mismatch | Investigate, then fix measured stage | Cause is not yet isolated |
| ToC attributed as equipment/body left shared | Fix | First Components occurrence is not a safe body boundary |
| Missing region ESN with no unique candidate | Accept with reason code | Guessing would be worse than empty attribution |
| Five irregular Generator labels | Fix in final-master profile only | Closed observed set limits cross-document impact |
| 1.5x chunk settings | Experiment only | Shared global change has retrieval and cost impact |
| Section 1 equals Generator | Conditional deterministic fix | Preserve a proven parent; do not invent or prompt over it |

## Recommended implementation order

1. Add stage-level coverage diagnostics and reproduce the missing-text documents.
2. Stop dropping sole/valid short-region chunks; add coverage regression tests.
3. Reconcile the chunk-only documents against fully qualified tables, runs, and IDs; add an orphan-chunk release check.
4. Change final-master processing from region replacement to section-region overlay.
5. Select the body Components span and exclude primary-ToC markers from attribution.
6. Add the five exact Generator labels inside that profile scope.
7. Resolve and propagate a unique Generator ESN for explicit and fallback Generator presence.
8. Run the 36-document chunk-size experiment with control documents before changing runtime configuration.
9. Add only deterministic duplicated-boundary cleanup; defer general vertical-text removal.

## Regression gates

Do not promote the changes unless all of the following hold:

- every non-whitespace source interval is represented in a chunk or has an explicit exclusion reason
- short valid sections are retained or merged, never silently dropped
- final-master `section_path` survives equipment attribution
- primary-ToC markers do not assign body equipment regions
- body `GAS TURBINE`, `STEAM TURBINE`, `GENERATOR`, and `UNCATEGORIZED` transitions are correct
- the five approved Generator variants match only inside the final-master Components body span
- a Generator ESN is populated only for one active train-scoped candidate
- ambiguous Generator candidates remain unresolved and observable
- no chunk row is orphaned from the configured metadata table
- section/page offsets are monotonic and map to the expected source pages
- chunk-setting experiments include unrelated document-family controls
- shared preprocessor and final-master profile tests both pass

## Image-reference note

The transcript's image numbering is internally consistent with the files present in the folder. Because the chat client repeatedly returned an upstream 404 while resolving image attachments, this analysis does not depend on re-downloading or embedding those files. The transcript, previously opened workspace copies, and current code are the evidence sources used here.