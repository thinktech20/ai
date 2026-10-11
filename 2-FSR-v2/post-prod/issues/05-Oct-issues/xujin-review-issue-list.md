# Xujin Review Issue List

Purpose: Capture the issues Xujin reports after the dev ingestion for review. This is an intake list only; do not analyze or propose fixes until all issues have been recorded.

## Issues

_Add each issue in the order provided. Record the reported behavior and any document IDs, pages, or other evidence as stated._

### 1. Chunking and section-boundary behavior

- In document `00f23784-d121-4595-b61d-49d223253a05`, a paragraph is split across two chunks without overlap.
- Short tables are split across two chunks, reportedly because a section header is detected incorrectly. Following chunks then receive `section_1 = generator`, apparently based on “Generator Mechanical” in the table.
- Chunks can contain only a section header. In the example, `3. Components`, `3.1 HOOD SPRAYS`, and the section 3.1 body text should be together in a chunk. The reported misplaced `3.1 HOOD SPRAYS` header follows `3. Components` in the output.
- In document `42944a96-6210-4f8a-ba54-fa1d5cd2a29b`, section `3.4` is in a separate chunk and its header appears at the end of a chunk. The report says it should be with the preceding chunk and, in the PDF, appears before “Part Condition: Good,” not after the paragraph.
- Status as reported: the missing-text issue from the earlier message seems fixed; the chunking issues above are still present.
- Evidence: screenshots attached with this report, including nested earlier messages.
- Attachment check: screenshots provided. No missing attachment identified from the supplied set.

#### Follow-up: section fields in `42944a96-6210-4f8a-ba54-fa1d5cd2a29b`

- Reported behavior: after the `## 3.15 TURBINE BUCKET(S)` chunk, subsequent chunks had `section_1 = 3.15 TURBINE BUCKET(S)`. The message also reported a paragraph split across two chunks without overlap.
- Follow-up status: reported fixed. The user is fine with `section_1` through `section_5` being null for final-master reports; no section-field fix is requested now.
- Two clarification questions remain for later: in chunk 74, `3.16` and `3.17` appear together, but the report questions whether `3.17` was detected as a new section; and it asks why `3.15` was detected in `section_1` but `3.16` was not, including whether “Turbine” in `3.15` matters.
- Xujin confirmed no section-path fixes are needed for this round. Later, validate retrieval quality if short sections discussing different issues are combined: query for each issue separately and check whether the relevant content is retrieved easily. She expects current hybrid search to work.
- Keep the two section-detection questions deferred; no fixes requested now. Revisit after the other fixes, with rollback if regression is large.
- Evidence: screenshots attached with the nested messages.

### 2. Generator ESN not added

- In document `00f23784-d121-4595-b61d-49d223253a05`, only one Turbine ESN is present. The report says there are no labels in the Components section, so page fallback should apply; the text contains “generator” 12 times, but no Generator ESN was added to `gen_esn` or `active_esns`. The report also says the metadata table identifies the primary equipment type as Generator.
- In document `d72f404c-7d35-49e9-a341-40266e687652`, a Generator header is present in the Components section, but no Generator ESN was added.
- Status as reported: the issue is still present.
- Attachment check: no separate attachment included with this message. Let me know if there is a screenshot or other evidence to attach.

### 3. Missing records in `fsr_metadata_v2`

- The report says records are still missing from `fsr_metadata_v2`; cited example: `153595df-646d-410b-8ee5-371fa057c1f4`.
- Attachment check: no separate attachment included with this message. Let me know if there is a screenshot or query output to attach.

### 4. Steam Turbine section attribution

- In document `42944a96-6210-4f8a-ba54-fa1d5cd2a29b`, the report was that Steam Turbine body sections were assigned to Shared, while part of the table of contents was assigned to Steam Turbine.
- Status as reported: fixed.
- Attachment check: no additional screenshots are available for this issue.

### 5. Page and section handling in `93c2180b-f866-4521-b090-b88442c6dcf1`

- Resolved: the `2.43` Generator chunk previously assigned to page 558. The follow-up says sections are chunked correctly, `section_1` metadata is correct, and primary ESN and equipment type are correct.
- Remaining report: `2. Components` is in a separate chunk with an incorrect page number.
- Sections under `1. Summary` are not recognized as sections and use recursive fallback. The report says this is acceptable if they cannot be detected easily; shared equipment-type tagging is correct.
- Evidence: screenshots attached with the nested messages.
- Attachment check: screenshots provided. No missing attachment identified from the supplied set.

### 6. Missing Gas Turbine primary ESN

- In document `9ecb1354-1f3a-4634-8a74-12943aff45a9`, the screenshot shows `region_primary_esn` missing for Gas Turbine rows. The accompanying note says retrieval or data readiness should be okay because equipment tagging and active ESNs are correct.
- Status as reported: fixed.
- Evidence: screenshot attached.
- Attachment check: screenshot provided.

### 7. 36-UUID chunk boundaries and chunk size

- Most vertical-word issues are reported fixed; isolated `FROM` text is acceptable. Remaining observation: a chunk can end with a vertical section header even though the same header appears normally at the beginning of the next chunk. Removing the trailing duplicate is preferred, but acceptable if not feasible.
- In document `796f4d53-a8ad-42e1-af4d-53a8add2e1a4`, short level-Q / level-2 section headers appear in separate chunks; the follow-up says this issue is still present.
- A DC leakage test report is split into two chunks. The report requests trying 1.5 times the recursive chunk-size threshold and 1.5 times the overlap, to reduce paragraph splits and the chance of splitting a data table.
- Evidence: screenshots attached with the nested messages.
- Attachment check: screenshots provided. No missing attachment identified from the supplied set.

### 8. Section paths and Control System attribution in `796f4d53-a8ad-42e1-af4d-53a8add2e1a4`

- Reported corrected: after a subreport, the section path returns to section 3, then 3.4, then 3.4.7.
- `section_1 = Generator` from the table of contents under `1 Summary` and `3 Generator` is acceptable to the reporter.
- Remaining report: a `###` chunk before `3.4.8` appears to cause an incorrect path for `3.4.8` and for section 4. Section 4 is shown under `3.4.8 Generator Alignment`, with section fields `4.1 Control System` and `4.1.1 Controls Final Report`; section 4 is also assigned to Generator.
- Clarification question: if `4 Controls System` is detected, should it be assigned to Turbine equipment type?
- A `4 Control System` section appears at the end of the preceding `3.4.8 Generator Alignment` section. The report says this may affect detection and Turbine tagging; other section headers appear correctly placed. The cited examples are on pages 351 and 348. The reporter thinks fixing the `###` chunk may address this and plans to check other documents to see whether it is limited to Control System or Generator Alignment.
- Evidence: screenshots attached with the nested messages.
- Attachment check: screenshots provided. No missing attachment identified from the supplied set.

### 9. Legacy-format detection and processing notes

- Suggested legacy-format signal: under `TABLE OF CONTENT`, entries matching `TEXT [single space] NUMBER [single space] TEXT [single space] NUMBER`. The report says this pattern does not occur in other document formats.
- Document ID characteristics may also help distinguish legacy from version-format documents. Volume path may be another signal; legacy documents are mostly in the `ecrt` folder.
- For the 18K+ legacy reports, `Equipment Serial #` is on the first page, except these listed IDs, which have `Generator Serial #`:
	- `090dbba18010f009`
	- `090dbba18010f5fb`
	- `090dbba18010f11e`
	- `090dbba18010f845`
	- `090dbba18010f896`
	- `090dbba18010f908`
	- `090dbba180110051`
	- `090dbba180110082`
	- `090dbba1801101a4`
- Suggested ESN handling: scan for the first detected `Equipment Serial #` or `Generator Serial #`. The report says each legacy-format document contains at most one train ESN, so body text and sections do not need to be scanned for additional ESNs. `Equipment Serial #` may identify either a Generator or a Turbine serial.
- Of roughly 18K reports, around 1K have the title `GAS TURBINE INSPECTION REPORTS` but `GENERATOR` or `EXCITATION` in the primary ToC. The report says to retain ToC-based assignment; the ToC can be detected using the legacy-format signal above.
- Attachment check: confirmed, no attachment for this item.

## Attachment check

For each issue, record whether an attachment was included or whether one is needed. Ask about missing or unclear attachments before moving on to the next issue.

## Completion

Issue intake completed on 2026-10-04. Root-cause analysis is in [root-cause-analysis.md](root-cause-analysis.md). Post-fix recurrence remains unverified pending a dev run ID and deployed-code revision for the reviewed ingestion.
