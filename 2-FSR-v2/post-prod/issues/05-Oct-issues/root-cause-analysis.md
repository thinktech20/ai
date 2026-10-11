# October Review RCA: Recurrence vs. Regression

## Dev repair execution (2026-10-06)

- Approved scope: all 12 previous candidates, including Rotor Out.
- Repair scope ID: `oct-fsr-75daefa-20261006`.
- Preparation job: `661313870227575`; dry-run execution `268071164082953` and manifest apply `14598897910055` succeeded.
- Read-only serverless preflight `518779092944469` confirmed exactly 12 approved candidates, 12 existing completed metadata/chunk rows, and zero active overlapping repair scopes.
- Deployed workspace code was checked for Generator Scope, page-separator mapping, plural Controls System, and duplicate ToC/body heading suppression. Job defaults are `5700`/`225`.
- Document-repair job: `58807500594750`; dry-run execution `64791126878626` and apply execution `846453865297727` succeeded with a 12-document cap and `5700`/`225` tuning.
- Read-only persisted verification: `381902884720981`, followed by enhanced exception verification `1040498653005111`. Evidence: [dev-repair-results-20261006.json](dev-repair-results-20261006.json).
- All 12 scope rows are resolved with P1/P2/P3 completed, no scope errors, and rollback snapshots available. Output is 558 chunks, with zero empty chunks and zero missing/wrong-sized embeddings (3072 dimensions). Profiles are nine final-master and three shared; Rotor Out routes to final-master and `017...` stays shared.
- Confirmed in persisted dev output: `d72...` has `gen_esn=337X662` and Generator-tagged Scope chunks with that ESN in `active_esns`; `93c...` Components chunk maps to page index 16 rather than 558; `796...` has no standalone `###` chunks and `4 Controls System -> 4.1 Control System` is Gas Turbine with ESN `297627`.
- Residual observations: a different `93c...` Generator alignment chunk (index 62, start offset 60307) has a null page with an explicit mapping-miss flag; `017...` chunk 26 at page index 149 still contains only `###`. These are not cleared by job success and require separate follow-up.
- Attribution review: the new `d72...` Generator span includes subsequent `4. PIPO` text. Generator ESN resolution is verified, but correctness of that span's downstream ownership is not established by this run.
- Traceability limitation: `deployed_code_commit` and `chunking_parameters` remain null on scope rows; deployment fixes were checked through workspace file exports, and tuning is recorded in job parameters. Retrieval quality is not yet tested.
- Run link: https://gevernova-ai-dev-dbr.cloud.databricks.com/?o=7474648066331722#job/58807500594750/run/846453865297727
- No SQL Statement API or SQL warehouse was used for this repair operation.

Updated: 2026-10-04  
Scope: Xujin's October review notes collected in [xujin-review-issue-list.md](xujin-review-issue-list.md), compared with the September issue/fix records.

## Executive conclusion

The available evidence does **not** establish that the October findings are regressions introduced by the September fixes. It shows a mixture of:

- findings Xujin subsequently marked fixed;
- behaviors already known to be unresolved or accepted limitations;
- residual defects addressed in later source commits but not yet verified by a documented post-fix dev run; and
- separate operational or format-specific questions that cannot be classified from screenshots alone.

The current FSR repository is clean at `66353a9` (`fsr_v2`, tracking `origin/fsr_v2`). The focused preprocessing suite passes: `101 passed, 5 subtests passed`. Read-only queries against the supplied dev tables on 2026-10-04 returned rows last written on 2026-09-29. They do not establish a post-`66353a9` deployment/reprocess. The latest documented repair run remains `postfix-dev-cce00fc-20260929`, which the prior RCA identifies as using a build preceding the latest residual-fix changes. We can describe the persisted September 29 behavior, but cannot call it a regression in later code.

Therefore, “still visible in dev” cannot by itself distinguish a regression from output produced by the earlier deployed build, an unreprocessed row, or a different table/run. A regression claim needs the deployed commit and a fresh persisted output for the same document.

## Finding-by-finding assessment

| October finding | Assessment | Evidence and interpretation |
|---|---|---|
| Missing body context in `00f...` | Reported fixed; no recurrence established | Xujin says the missing-text issue seems fixed. The remaining screenshots concern chunk boundaries, not proof that source text is absent. |
| Paragraph split without overlap; short/header-only chunks | Known behavior/acceptance gap, not a new regression | P2 recursively chunks each preprocessor region independently. Overlap applies within a region, not across region boundaries. The earlier RCA already identified this. False headings can create short regions; latest source adds table/ToC guards and limited heading-only merging, but synthetic tests do not establish the behavior on these PDFs. |
| Generator ESN missing in `00f...` / `d72...` | Earlier defect; current recurrence unverified | The 2026-09-29 repair output records `gen_esn=316X825` for `00f...`. Current source adds document-level Generator evidence and resolution for explicit Generator labels. A blank value in a fresh post-fix run would be a regression candidate; no such run evidence is provided. |
| Missing `fsr_metadata_v2` row for `153...` | Operational inconsistency; not established as a code regression | The prior 12-document repair reported all documents completed P1/P2/P3, and the earlier RCA found that P2 claims from the configured metadata table. The supplied dev target is `vaid.ai_std_con_field_service_report.fsr_metadata_v2`; however, the bundle default points to `vaid.ai_sot_field_service_report.fsr_metadata_v2`. Confirm which target the reviewed job actually used, plus normalized ID and run ID, before concluding the row is absent from the run's table. |
| Steam Turbine body attribution to Shared | Reported fixed; not confirmed to have reappeared | The September 29 pre-residual-fix output did contain this defect. Later source changes address body Components selection; Xujin subsequently says it is fixed. A post-fix dev reprocess is still needed to verify persisted output. |
| `93c...` `2.43` page/section mapping | Reported fixed; no recurrence established | The earlier bad output placed `2.43` in a chunk with stale `2.42` metadata. Current source recognizes inline Markdown headings such as `... ## 2.43 ...`, with a regression test, and Xujin says the issue is fixed. The separate `2. Components` chunk with a wrong page is not the same finding and remains unclassified. |
| Missing Gas Turbine `region_primary_esn` in `9ec...` | Earlier enrichment gap; reported fixed | The earlier RCA found explicit Gas Turbine regions were not enriched like Generator regions. Current source enriches explicit GT/ST regions from a unique document metadata ESN. Xujin says the screenshot concern is fixed; no fresh output is available to independently verify it. |
| 36-UUID vertical headings and chunk-size request | Known edge case; global 1.5x tuning requested across formats | Exact duplicated next-heading cleanup is tested; unmatched vertical text such as `FROM` is intentionally retained. Xujin confirms that chunk size and overlap should be increased to 1.5x across document formats because reports such as DC leakage tests share table-heavy content. This is an agreed direction to validate with cross-format regression controls, not yet a verified fix. |
| Section path after subreport / `3.4.8` / Control System | Final-master section paths deferred; Control System equipment rule clarified | Xujin is fine with null `section_1`-`section_5` for final-master reports and requests no section-path fixes this round. Keep the `3.16`/`3.17` detection and `3.15` versus `3.16` metadata questions for later. For other formats, numbered `N Control System` headings should map to Turbine; the screenshot shows `4 Control System` at the end of the preceding chunk, separate from `4.1`, so verify boundary placement and attribution on reprocessed output. |
| `93c...` `2. Components` wrong page | Separate unresolved symptom | This is distinct from the fixed `2.43` case. The current evidence does not include extracted page offsets, region boundaries, or the persisted run metadata needed to identify whether the wrong page originates in extraction, offset mapping, or stale chunk output. Do not treat the `2.43` fix as resolving it. |
| Legacy-format detection and serial rules | New format-specific design scope, not a regression | The prior fixes cover final-master reports and 36-UUID/version-format section handling. The `ecrt`/legacy signals, first-page serial labels, and one-train-ESN assumption were not validated by those fixes. The proposed ToC signature and listed `Generator Serial #` exceptions need representative legacy fixtures before implementation. |

## Root-cause synthesis

### Chunk boundaries and short regions

The region-first chunker treats preprocessor region boundaries as authoritative. Recursive overlap is generated only inside each region, so a paragraph divided by a false section boundary can appear in adjacent chunks without overlap. This is consistent with the existing implementation and was already called out in the September RCA; it is not evidence that overlap regressed. The root defect, where confirmed, is a false or misplaced heading boundary. Xujin expects the requested 1.5x recursive chunk-size and overlap tuning to apply across document formats; implement it as a cross-format parameter change only with regression checks for representative formats, section boundaries, and table-heavy reports. It does not replace fixing false or misplaced boundaries.

The short-chunk retention change prevents valid short semantic regions from being silently dropped. Its tradeoff is that a valid short heading/section can remain small; a false table heading can also split content and create a misleading path. Current code has table/ToC rejection and limited merging, but the tests do not cover the exact `Generator Mechanical` table or all cited extracted layouts. This is a coverage gap until the PDFs are rerun against the current build.

### ESN and equipment attribution

Two distinct prior defects are covered in current source: Generator resolution can use document-level evidence or an explicit Generator label, and explicit Gas/Steam Turbine regions can inherit a unique corresponding document ESN. The September 29 persisted run already showed the `00f...` Generator ESN, while it predates the final residual patch for other behaviors. Thus an old screenshot showing a blank field is not sufficient to show reappearance. Confirm against fresh `metadata_v2` and chunk JSON from the same post-fix run.

### Section hierarchy

The September fixes had narrow contracts: detach incompatible equipment parents, restore an exact numbered parent after hierarchy disruption, and remove adjacent duplicate labels. The October `3.4.7` correction is consistent with the later parent-recovery change. Xujin accepts null section fields for final-master reports and requests no section-path fix this round. The `3.16`/`3.17` heading-detection and `3.15` versus `3.16` section-field questions are deferred. Separately, the numbered Control System heading's Turbine attribution is confirmed; the `4 Control System` chunk-boundary placement remains to validate. The test suite passing proves synthetic cases, not document-level output.

### Deferred retrieval check for short sections

After the higher-priority fixes, assess whether combining short sections that discuss different issues harms retrieval. Use each issue separately as a query and verify that hybrid search still retrieves the relevant content. Xujin expects current hybrid search to work. This is a later validation, not a request to change section paths or merge behavior now.

### Metadata row discrepancy

A chunk row and missing metadata row can coexist if the rows come from different tables, runs, normalized document identifiers, or an earlier/manual write. The documented repair run reports completed metadata and chunks for its scoped documents. The supplied `dev` target table names are:

- Metadata: `vaid.ai_std_con_field_service_report.fsr_metadata_v2`
- Chunks: `vaid.ai_std_con_field_service_report.fsr_chunks_v2`
- Document equipment map: `vaid.ai_std_con_field_service_report.fsr_document_equipment_map_v2`
- Run log: `vaid.ai_sot_field_service_report.fsr_run_log_v2`
- DQ log: `vaid.ai_sot_field_service_report.fsr_data_quality_log_v2`

These match the `dev` overrides in [databricks.yaml](../../../../../pw_sdg_ai_ser_repo/databricks.yaml), but several bundle defaults differ: metadata and equipment map default to `ai_sot_field_service_report`, while run log and DQ log default to `ai_std_con_field_service_report`. This is a concrete way a query using defaults rather than the deployed `dev` target could inspect a different table. It is a plausible explanation, not proof that the October query used the wrong schema. Confirm the effective target and run ID for the reviewed job, then compare the document ID in the named metadata and chunk tables.

### Legacy format

The legacy proposal describes a separate family and a different metadata contract: detect the characteristic ToC shape, extract the first equipment/generator serial label on page one, and keep ToC-based equipment assignment even when report titles disagree. These are new requirements, not regressions from the final-master/36-UUID changes. Xujin confirmed that representative samples exist and are being collected/uploaded; keep implementation pending those samples. The “at most one train ESN” assumption should remain scoped to legacy documents unless validated against them.

## Evidence reviewed

- [September 28 review and RCA](../01-04-date-09-28-issues/root-cause-analysis.md), including its September 29 repair-run status and residual-fix list.
- [September 25 postfix RCA](../01-04-postfix-issues/root-cause-analysis.md).
- [36-UUID section-path RCA](../01-section-path-uuid/root-cause-analysis.md) and implementation plan.
- [Final-master-report RCA](../04-final-master-report-format/root-cause-analysis.md) and implementation plan.
- October issue intake in [xujin-review-issue-list.md](xujin-review-issue-list.md).
- Current `pw_sdg_ai_ser_repo` branch and history: clean `fsr_v2` checkout at `66353a9`; changes include `66d7bd0` and `66353a9`.
- Supplied dev table mappings and the corresponding `dev` overrides in `databricks.yaml`; bundle defaults differ for metadata, equipment-map, run-log, and DQ tables.
- Focused test: `PYTHONPATH=pw_sdg_ai_ser_repo pytest pw_sdg_ai_ser_repo/tests/fsr_v2/test_preprocessor_v2.py -q` -> `101 passed, 5 subtests passed`.

## Dev table verification (2026-10-04)

Read-only SQL Statement API queries used `dev-dbr-profile` and the user-supplied table targets. All seven metadata rows queried (`00f...`, `153...`, `429...`, `796...`, `93c...`, `9ec...`, `d72...`) are `completed` for metadata and chunking, with `updated_at=2026-09-29 23:28:19Z`. This is persisted September 29 output, not evidence of an October reprocess on the current deployed code.

| Document / check | Result in dev tables |
|---|---|
| `153595df-646d-410b-8ee5-371fa057c1f4` metadata | Present and completed in `vaid.ai_std_con_field_service_report.fsr_metadata_v2`; absent from the bundle-default `vaid.ai_sot_field_service_report.fsr_metadata_v2`. This confirms a wrong-schema query can explain the reported missing row. |
| `00f23784-d121-4595-b61d-49d223253a05` Generator ESN | `gen_esn=316X825`; all 36 chunks are `shared`, with no blank ESN among Generator-tagged chunks. |
| `d72f404c-7d35-49e9-a341-40266e687652` Generator ESN | `gen_esn` blank; primary/GT ESN is `875064`, primary equipment type blank, and no equipment-map row. The `## 3.4 GENERATOR SCOPE` chunk is `shared`; persisted regions use `unresolved_turbine` / `outside_components_appendix`. |
| `42944a96-6210-4f8a-ba54-fa1d5cd2a29b` Steam Turbine | 16 of 29 chunks are tagged Steam Turbine and 13 Shared. The body `3.15 TURBINE BUCKET(S)` chunk at page 70 is tagged Steam Turbine; its ToC occurrence at page 2 is Shared. |
| `93c2180b-f866-4521-b090-b88442c6dcf1` page mapping | ToC `2.43` appears at page 5 and body `2.43` is at page 444 with matching section metadata. A separate chunk containing only `## 2. Components` is assigned page 558; this remains an observed page-mapping defect. |
| `9ecb1354-1f3a-4634-8a74-12943aff45a9` region ESNs | 23 Gas Turbine chunks have nonblank region ESNs; one Generator chunk is present. |
| `796f4d53-a8ad-42e1-af4d-53a8add2e1a4` section path | Page 351 has a `###` chunk with path `Generator -> 3 Generator -> 3.4 -> 3.4.8`; the following body chunk drops the first two ancestors. `4.1 Control System` is tagged Generator. |

The P2 run log includes `b48180ac5aca4155a7ebb22b60bc9e7e` at 2026-09-29 23:27Z (12 claimed, 12 succeeded, 657 chunks). Chunk rows carry multiple `run_id` values from Sep 25, 26, and 29. This field is not a reliable last-write marker: P2's matched-row `MERGE` refreshes `created_at` but does not update `run_id`. Metadata `run_id` is null for these documents. The repair-scope table was not queried, so per-document correlation to `b481...` is not established.

The configured SQL Statement API automatically resumed `ai-pw-ser-ds-dev-sqlw`, which had been stopped before querying. No explicit start command was issued. Additional read-only statements were submitted to complete the requested verification after the auto-resume was detected. A stop request was denied by Databricks permissions; the warehouse reported `auto_stop_mins=10` and was still `RUNNING` at the last check on 2026-10-04. The user confirmed it was stopped on 2026-10-05.

## Checks needed to conclusively classify recurrence

1. Read the repair-scope row for `postfix-dev-cce00fc-20260929` to correlate documents with P1/P2/P3 statuses and fingerprints.
2. Confirm the deployed dev commit and profile version; the checked-out `66353a9` source does not prove that dev runs it.
3. For `d72...`, the `93c...` page-558 chunk, and the `796...` path, compare source parsed text, offsets, heading candidates, regions, and persisted chunks, then reprocess only after confirming the deployed build. Preserve current output as the before baseline.
4. Call an issue a regression only if a post-fix deployed run reproduces it. Otherwise classify it as older persisted output, an existing gap, or a new requirement.

## Implementation update (2026-10-05)

The following changes are implemented and validated locally against the three uploaded PDFs with the same `parse_pymupdf` parser and preprocessing/chunking functions used by the pipeline:

- Final-master marker detection now accepts a numbered `GENERATOR SCOPE` label. On `d72...`, the `3.4 GENERATOR SCOPE` span is explicitly tagged Generator and reaches the existing Generator ESN resolver. The local check used a stub IBAT resolver, so it verifies the invocation/region path, not the live resolved ESN.
- Page mapping now assigns the newline separator before a nonempty page to that following page. On `93c...`, the standalone `2. Components` chunk maps to source page index 16 rather than falling back to the last page (558). The `2.43` body chunk remains at page index 444 with its matching section metadata.
- A ToC page-hint candidate is suppressed when an identical normalized heading is already recognized on the same body line. On `796...`, this removes the four-character standalone `###` regions at `3.4.7` and `3.4.8` while preserving their headings and body content in the section chunks.
- The shared root-heading rule accepts both `N Control System` and `N Controls System`. For this PDF, `4 Controls System` is assigned Gas Turbine from the unambiguous document inventory, and `4.1 Control System` is nested under it.
- P2 chunk size/overlap are now `5700`/`225` in bundle defaults and standard/adhoc fallbacks; the minimum size remains `450`. With region-first recursive chunking, the three PDFs produced `14 -> 10`, `98 -> 90`, and `157 -> 135` chunks respectively when compared at old versus new settings. Retained short semantic-region counts did not change in this sample set. This parameter increase does not create overlap across valid preprocessor region boundaries; false boundaries still need to be corrected at heading detection.

Validation: `116 passed, 5 subtests passed` in `tests/fsr_v2`; modified Python modules compile; changed-file diagnostics and `git diff --check` are clean. `databricks bundle validate -t dev --profile dev-dbr-profile` succeeds with one warning about permissions on the existing bundle workspace folder. The missing `fsr_v2_min_doc_year` and `fsr_v2_max_doc_year` bundle variables are now defined with the metadata notebook's defaults. No Databricks job was run and no dev tables were changed. Deployment and targeted dev reprocessing are still required to verify persisted results.
