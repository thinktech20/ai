# October 6 Review: Issues to Confirm

Updated: 2026-10-06

Purpose: Confirm our understanding of the remaining findings before root-cause analysis or further fixes. Reported symptoms below are not conclusions about their causes. Earlier nested messages are context, not additional independent findings.

## Dev Update Confirmed

A fresh read-only serverless check at **2026-10-06 21:54 UTC** confirmed that all 12 repair documents, including Rotor Out, have metadata records and chunks in these tables:

- Metadata: `vaid.ai_std_con_field_service_report.fsr_metadata_v2`
- Chunks: `vaid.ai_std_con_field_service_report.fsr_chunks_v2`

For all 12 documents:

- Metadata `updated_at` and `chunked_at`: **2026-10-06 18:51:18.026625 UTC**.
- Chunk `created_at`: **2026-10-06 18:51:08.227097 UTC**.
- Repair scope P1/P2/P3 statuses: `completed`; metadata and chunk statuses: `completed`.
- Current chunk counts match the repair scope's recorded after-counts.

The repair ran under scope `oct-fsr-75daefa-20261006`, job execution `846453865297727`. Fresh verification execution: `128420883284159`. Evidence is in [dev-table-freshness-20261006.json](dev-table-freshness-20261006.json).

The metadata table `vaid.ai_sot_field_service_report.fsr_metadata_v2` is a different table, not the target above. It returned only two of the twelve scoped IDs in this check. Please use the fully qualified `ai_std_con_field_service_report` table for this review.

An unchanged chunk count does not mean a document was skipped: `00f...` has 36 chunks before and after, but the rows have the new write timestamps. Successful ingestion does not establish that every content issue was fixed.

## Persisted Symptom Verification

Read-only serverless verification execution `571538077779425` queried metadata and chunk rows at **2026-10-06 22:09 UTC**. Evidence is in [dev-issue-evidence-20261006.json](dev-issue-evidence-20261006.json). No source parsing, cause analysis, ingestion, or production-code changes were performed in this check.

| Item | Verified result in current dev rows |
|---|---|
| O6-01 | Confirmed: `00f...` chunk 8 contains the Hood Sprays descriptive body under `3. Components`; chunk 9 contains only `3.1 HOOD SPRAYS`. The body appears before its child heading, and the raw page parsing results already show this order. Remediation is postponed. |
| O6-02 | Confirmed: `00f...` chunks 2 and 3 split the Executive Summary at the reported phrase, with zero exact shared suffix/prefix characters. |
| O6-03 | Confirmed: `00f...` chunk 4 contains Work Scope with Gas/Steam Turbine, and chunk 5 contains Generator/Mechanical/Support Systems with `section_path = [Generator]`. The chunk 4 path also contains Executive Summary prose as its parent label. The table split and incorrect section metadata are both present. |
| O6-04 | Resolved as a lookup mismatch: all twelve metadata rows exist in `vaid.ai_std_con_field_service_report.fsr_metadata_v2`. The other `ai_sot_field_service_report` table does not contain the same document set. |
| O6-05 | Confirmed: `93c...` chunk 22, headed `2.3 FLOATING SEAL INSPECTION`, contains the oil-deflector body; chunk 23, headed `2.4 INSPECT OIL DEFLECTORS T1 AND T2`, contains the thrust-bearing body. `CBM: NA` appears after `Part Condition Description` in chunk 22, though it appears before it in the PDF. The raw page parsing results show the reported ordering/alignment issues before chunking. Remediation is postponed. |
| O6-06 | Confirmed in example document `796...`: examples include chunk 73 (`3.2 Stator Tests`), chunk 81 (`3.4 Generator Inspections & Clearances`), and chunk 120 (`4 Controls System`), each containing a heading and layout-label letters without descriptive body. These 36-UUID heading-only observations are postponed. Similar parsing-related issues may occur in other documents and chunk indexes; the examples are not exhaustive. |
| O6-07 | Confirmed in example document `796...`: chunk 74 ends with vertical `3.2.2 Armature Insulation Resistance with Polarization Index (PI) Test`, which begins chunk 75 normally; chunk 79 ends with vertical `3.3.1 Inspection Photos and Wedge Tightness Test Results`, which begins chunk 80 normally. This repeated-heading work is postponed with the other 36-UUID chunk observations. |
| O6-08 | Confirmed in example document `796...`: chunk 91 has `section_path = [Generator, 4.7 1A BFP]`, without the stated main-report ancestors. This subreport-path issue remains in scope. |

Reusable read-only validation notebook: `ai-arch/pw_sdg_ai_ser_repo/validation/fsr_v2/nb_fsr_v2_review_issue_evidence.py`. It captures chunk text, paths, indexes, timestamps, and the above examples. Header-only classification is an evidence filter, not a decision to merge or discard every matching chunk. `796...` is an example from the 36-UUID set; similar issues may affect other documents and chunk indexes.

## Reported Open Issues

| ID | Document | Our understanding of the reported issue | Expected behavior | Evidence |
|---|---|---|---|---|
| O6-01 | `00f23784-d121-4595-b61d-49d223253a05` | `3.1 HOOD SPRAYS` appears after its descriptive body text and can occupy a standalone chunk. `3. Components` currently carries that body text without the correct child heading before it; the raw page parsing results already show this ordering. **Remediation postponed.** | `3.1 HOOD SPRAYS` should precede its own Part Condition Description. The parent heading, child heading, and short body should remain together as appropriate, rather than the child heading appearing after its body. | Image 1; Image 4 is the earlier message1 example. |
| O6-02 | `00f23784-d121-4595-b61d-49d223253a05` | The Executive Summary paragraph is still divided between adjacent chunks without overlap: one ends with "provided a new" and the next begins "alignment criteria for the unit". | Preserve the paragraph together where feasible, or provide the expected overlap when a split is necessary. | Image 2; Image 5 repeats the earlier message2 example. |
| O6-03 | `00f23784-d121-4595-b61d-49d223253a05` | The short `1.3 Work Scope` table is split around "Generator Mechanical"; incorrect section-path labels are also present. | Keep the short Work Scope table together. Do not treat a table cell as a new section heading or allow it to change subsequent section metadata. | Image 6; earlier message2. |
| O6-04 | Twelve-document repair scope | All twelve metadata records exist in `vaid.ai_std_con_field_service_report.fsr_metadata_v2`; a different table was queried previously. | No metadata-row repair is needed for these records. | Read-only serverless verification above. |
| O6-05 | `93c2180b-f866-4521-b090-b88442c6dcf1` | Section headings and body content are shifted: the `2.4` body appears in the chunk headed `2.3 FLOATING SEAL INSPECTION`, and the `2.5` body appears under `2.4 INSPECT OIL DEFLECTORS T1 AND T2`. `CBM: NA` is also after `Part Condition Description` in the chunk but before it in the PDF. The raw page parsing results show these ordering/alignment issues before chunking. **Remediation postponed.** | Each heading should precede and remain associated with its own body content. | Image 3 and raw page parsing results. |
| O6-06 | Example document `796f4d53-a8ad-42e1-af4d-53a8add2e1a4` from the 36-UUID set | Section headings remain as standalone chunks. Similar parsing-related issues may occur in other documents and chunk indexes; these examples are not exhaustive. **Postponed.** | Avoid isolated heading-only chunks where the heading can remain with the relevant body content without mixing unrelated ownership. | Current 36-UUID text comment; no new screenshot specifically identified for this item. |
| O6-07 | Example document `796f4d53-a8ad-42e1-af4d-53a8add2e1a4` from the 36-UUID set | A few chunks end with a repeated section heading in vertical form. **Postponed.** | Remove a duplicated trailing vertical header only when it represents the next section heading already retained elsewhere. | Current 36-UUID text comment; no screenshot specifically identified for these indexes. |
| O6-08 | Example document `796f4d53-a8ad-42e1-af4d-53a8add2e1a4` from the 36-UUID set | A subreport section under `3.4.1` is detected, with correct ESN/equipment type, but the path becomes Generator -> `4.7 1A BFP`, losing main-report section 3, 3.4, and 3.4.1. **Remains in scope.** | Preserve the main-report section path while retaining subreport headings/content. Use the primary ToC to decide when the main-report path changes, resuming at `3 -> 3.4 -> 3.4.2`; if both cannot be preserved, prioritize correct main-report paths. | Current text comment; no screenshot of the `4.7 1A BFP` path was supplied. |

## Confirmed Responses (2026-10-07)

1. The findings are accurate. The 36-UUID observations use `796...` as an example; similar issues may affect other documents and chunk indexes.
2. All twelve metadata records exist in the fully qualified target table above. The earlier lookup used the wrong table.
3. The 36-UUID heading-only and repeated-heading observations are postponed; the parsing output is acceptable for now.
4. The heading/body remediation described in the first proposed approach is postponed. The Executive Summary split and Work Scope table/path correction remain in scope.
5. For embedded subreports, retain detected local headings for chunking and the enclosing main-report path in section metadata. If both cannot be retained safely, prioritize the main-report path.

## Attachment Status

Six screenshots were supplied in chat and mapped here as Images 1-6 in attachment order. Images 4-6 repeat earlier examples; Images 1-3 show the reported current comparisons. The folder currently contains the message transcript but no image files, so these labels refer to the supplied chat attachments, not saved local image paths.

Screenshots for O6-06 through O6-08 are not present in the supplied set. The confirmed text examples are recorded above; additional screenshots were not needed to confirm the scope decisions.

No production-code changes or reprocessing have been made for this issue list. Heading/body-alignment remediation and 36-UUID heading-only/repeated-heading work are postponed. The Executive Summary split, Work Scope table/path correction, and explicit 36-UUID subreport-path issue remain in scope. Final-master section-field enhancements previously deferred remain deferred. The condensed sharing version is [review-summary.md](review-summary.md), without image labels or attachment-status notes.