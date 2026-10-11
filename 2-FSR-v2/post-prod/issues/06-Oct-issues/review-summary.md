# FSR Review: Remaining Issues

Updated: 2026-10-06

All 12 documents were updated in dev on October 6. Checks of the updated metadata and chunks confirmed the remaining issues below.

## Verified Remaining Issues

**Document `00f23784-d121-4595-b61d-49d223253a05`**

- Hood Sprays body text appears under `3. Components` before the standalone `3.1 HOOD SPRAYS` heading (chunk indexes 8 and 9). The raw page parsing results show this ordering already, so the issue is present before chunking.
- The Executive Summary paragraph is split between chunks 2 and 3 without shared text at the reported boundary.
- The short Work Scope table is split between chunks 4 and 5 around Generator Mechanical. Incorrect section-path labels are also present.

**Document `93c2180b-f866-4521-b090-b88442c6dcf1`**

- Heading/body alignment remains incorrect: chunk 22 is headed `2.3 FLOATING SEAL INSPECTION` but contains the oil-deflector description; chunk 23 is headed `2.4 INSPECT OIL DEFLECTORS T1 AND T2` but contains the thrust-bearing description. `CBM: NA`, which appears in the PDF between `Part Condition: Good` and `Part Condition Description`, follows the description in chunk 22. The raw page parsing results show these ordering/alignment issues before chunking.

**Document `796f4d53-a8ad-42e1-af4d-53a8add2e1a4` (example from the 36-UUID set)**

- Heading-only chunks remain, including `3.2 Stator Tests`, `3.4 Generator Inspections & Clearances`, and `4 Controls System` (postponed).
- Chunks 74 and 79 end with vertical headings that repeat at the start of the following chunks (postponed).
- Subreport chunk 91 has path `Generator -> 4.7 1A BFP`, without the expected main-report sections 3, 3.4, and 3.4.1.

Other documents and chunk indexes may show the same 36-UUID parsing-related issues; these examples are not exhaustive.

## Metadata Lookup

All twelve metadata records exist in:

`vaid.ai_std_con_field_service_report.fsr_metadata_v2`

The updated chunks are in:

`vaid.ai_std_con_field_service_report.fsr_chunks_v2`

The metadata table in `ai_sot_field_service_report` is a different table and does not contain the same document set.

## Proposed Approaches

The following scope was confirmed on 2026-10-07. No fixes or reprocessing have been completed.

- **POSTPONED - Heading/body alignment (`00f...` and `93c...`):** The raw page parsing results contain the reported ordering/alignment issues. The proposed source-layout review and heading-to-body correction are postponed for now.
- **Executive Summary paragraph split (`00f...`):** Keep the paragraph within its actual section and remove any incorrect boundary inside it. If it still needs to split because of size, apply overlap within that section rather than mixing content across unrelated sections or equipment.
- **Work Scope table (`00f...`):** Keep the short table together and prevent table cells such as Generator Mechanical from becoming section headings or changing later section paths. Preserve the table content while correcting its boundary and metadata.
- **Heading-only chunks (final-master and 36-UUID):** Postponed for the 36-UUID examples. Final-master heading-only observations were attributed to parsing results and are not part of this current work. Retain genuine short sections with useful content; do not discard them solely because they are small.
- **Repeated vertical headings (36-UUID):** Postponed with the other 36-UUID parsing-related chunk observations.
- **Subreport paths (36-UUID):** Keep detected local subreport headings for chunking, but retain the enclosing main-report path in `section_1`-`section_5`. With a reliable primary ToC, `4.7 1A BFP` would not replace `3 -> 3.4 -> 3.4.1`; the main-report path would change when a matching main-report section such as `3.4.2` resumes. Treat an incomplete ToC cautiously rather than dropping valid content. If both local-heading detection and correct outer paths cannot be retained safely, prioritize the correct main-report path.
- **Metadata lookup:** All twelve metadata records exist in `vaid.ai_std_con_field_service_report.fsr_metadata_v2`. The earlier lookup used a different table, `ai_sot_field_service_report`; no metadata-row repair is needed.

After agreement, validate the affected PDFs and regression cases, then reprocess the approved dev scope and compare persisted output. Retrieval checks should also confirm that combining short headings with body content still allows each issue to be found separately.

## Confirmed Responses

1. The listed issues are accurate. The 36-UUID examples are from `796...`, but similar issues may affect other documents and chunk indexes.
2. All twelve metadata records are present in the fully qualified `vaid.ai_std_con_field_service_report.fsr_metadata_v2` table. The earlier lookup used the wrong table.
3. The 36-UUID heading-only/repeated-heading observations are postponed; their parsing output is acceptable for now.
4. For embedded subreports, retain local headings for chunking and the enclosing main-report path in section metadata. The main-report path takes priority if both cannot be retained safely.

## Scope Clarification

Complete section-field coverage for final-master reports remains deferred; null `section_1`-`section_5` values are acceptable for now. The earlier questions about why `3.15 TURBINE BUCKET(S)` populated `section_1` but `3.16` did not, and whether `3.16`/`3.17` stayed together because `3.17` was not detected, will be revisited later.

The heading/body-alignment remediation is postponed, though the findings remain documented. The Executive Summary split, Work Scope table/path issues, and 36-UUID subreport-path issue remain in scope. The 36-UUID heading-only and repeated-heading observations are postponed. These decisions are separate from optional final-master section-field coverage.

No new fixes have been made for this list.