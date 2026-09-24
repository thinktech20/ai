# Implementation Plan

Updated: 2026-09-22
Issue: Final master report format

## Planned steps

1. Assemble representative sample documents and extract their parsed text,
    page offsets, heading candidates, and current preprocessor regions.
2. Implement behavioral family detection.
   - Treat the dotted Contents pattern (`. . . . . .`) as a strong signal
      observed in final-master-report documents. Do not assume it occurs in
      36UUID or versioned/legacy reports until representative parsed samples
      confirm that.
    - Detect the observed fully capitalized numbered Components heading:
       `2. COMPONENTS` or `3. COMPONENTS`, meaning number, dot, space, then
       `COMPONENTS`. Do not treat a generic `COMPONENTS` occurrence as enough.
    - Detect fully capitalized category markers inside Components using the
       same rule for `GAS TURBINE`, `STEAM TURBINE`, `GENERATOR`, and
       `UNCATEGORIZED`; Generator is not a special case.
    - Give `GENERATOR -` an additional discriminator weight because plain
       `GENERATOR` can occur in versioned or other document formats. Treat
       `GAS TURBINE -` as optional evidence because final master reports may
       omit that exact form.
    - Treat number-before-title headings and a valid next top-level boundary as
       supporting signals.
   - Give the dotted Contents pattern routing weight 2. Detect it only in the
       primary ToC window: the first 10% of parsed pages, including at least the
       first page. Ignore dotted patterns that appear only in later embedded or
       sub-report ToCs.
    - Use family-specific signals and a confidence threshold for routing. For
       current in-volume documents, `final_master_report` /
       `Final_Master_Report` in the filename and the known document-ID
       inventory are reliable routing signals. Use parsed structure to validate
       that routing and to support future documents with missing or inconsistent
       names.
    - Route low-confidence documents through the existing default profile.
3. Implement the family-specific attribution strategy within the existing
    preprocessing framework.
    - Reuse shared offset, region construction, full-coverage, metadata, and
       hints helpers; do not copy the default preprocessor.
    - Assign `shared` outside Components and Appendix. PDF reference entries
       such as `4.1 VIBRATION REPORT.PDF` are expected within those sections,
       so they do not require a separate outside-section rule.
    - Send an entirely unlabeled Components section and Appendix content to
       page fallback; do not send explicitly labeled Components content.
    - Flip the active label only on an anchored category line beginning with a
       supported equipment phrase.
    - Allow a suffix after any leading category label, such as
       `GAS TURBINE - ...` or `GENERATOR - ...`, and map it using the same
       category-marker rule. Map `UNCATEGORIZED` to `shared`.
    - Do not allow generic parent inheritance or incidental body-text mentions
       to override the explicit Components label state.
    - Preserve the observed family constraint of at most one turbine and one
       generator evidence item in final master reports; do not apply this
       assumption to 36UUID documents.
4. Implement page fallback in the same profile, as a separately configured
   decision within the implementation.
    - Use the supplied reference preprocessor only for page offsets, keyword
       signatures, and adjacent-page merging.
    - Do not copy its current behavior, which assigns pages to Generator or
       Gas Turbine based on the winning signal and document primary type.
    - Count Generator evidence only within eligible unlabeled Components or
       Appendix spans. One Generator occurrence in the ToC or repeated anchored
       Generator body evidence maps that fallback span to `shared`.
    - For a shared fallback span with Generator evidence, use the resolved
       Gas/Steam Turbine ESN as a train anchor for the existing IBAT Generator
       lookup. Persist `gen_esn` only when one active candidate is returned;
       record zero or multiple candidates as unresolved rather than guessing.
    - When Generator evidence does not qualify, map the fallback span to the
       resolved Gas Turbine or Steam Turbine; use `shared` if turbine type is
       unresolved.
    - Configure the initial experiment with a threshold of `>7` qualifying
       Generator evidence items. Keep it external to the parsing logic so it
       can be changed without a code rewrite.
    - Treat `>7` as a validation starting point, not a permanent production
       threshold. Test ordinary prose and mixed scanned/text pages, record the
       triggering evidence, and recalibrate before broad rollout.
    - Keep the fallback setting, tests, metrics, and acceptance checks separate
       from the core Components label rule so the behaviors can be compared or
       rolled back independently.
5. Preserve and record the existing output contract.
    - Return the same `metadata`, `hints`, and `regions` structure used by the
       current metadata processor.
    - Record the selected profile, detection method, confidence, and detection
       signals for review and troubleshooting.
    - Persist the actual per-document profile, profile version, strategy name,
       routing score/signals, and page-fallback reason in `preprocessor_regions`;
       add document-level profile columns for SQL reporting. Do not rely only on
       the run-level expected profile because one run may contain UUID and final
       master-report documents using different strategies.
6. Add focused unit and regression tests before rollout.
7. Compare candidate output with current output, then roll out only after
    targeted regression checks pass.

## Validation corpus

Use the following representative documents from the latest review. The
first three are the initial candidates; the remaining documents cover Steam
Turbine, sub-report, section-3 Components, and short-report cases:

1. `06d30404-cff8-4f87-abf5-379c7036a1a6_212533956-38805-SY0021643-Final_Master_Report.pdf`
2. `01c6f1c0-d293-4ff8-b169-38d36794b206_212494221-183897-SY0093781-Final_Master_Report.pdf`
3. `036fcec6-49ce-4553-9ca9-0ae10e42084b_605032377-192511-SY0016365-Final_Master_Report.pdf`

4. `93c2180b-f866-4521-b090-b88442c6dcf1_204006084-2510-297422-Final_Master_Report.pdf`
5. `a9d4cff6-3586-4d8c-a26b-09754468d833_605013480-50051-298340-Final_Master_Report.pdf`
6. `9ecb1354-1f3a-4634-8a74-12943aff45a9_605003354-23849-298081-Final_Master_Report.pdf` (Components is section 3)
7. `8ff5a231-c213-4441-b4ed-e39ed1988c8d_605030072-50465-298364-Final_Master_Report.pdf` (short report without Components)
8. `42944a96-6210-4f8a-ba54-fa1d5cd2a29b_605015096-47162-152296-final_master_report.pdf` (Steam Turbine)
9. `768c7c3f-b8f2-4603-8f4a-f5c5a4e0976f_605001793-17435-297129-Final_Master_Report.pdf` (sub-report in Components)
10. `00f23784-d121-4595-b61d-49d223253a05_605011513-188120-198090-Final_Master_Report.pdf`
11. `153595df-646d-410b-8ee5-371fa057c1f4_212369717-36105-SY0048243-Final_Master_Report.pdf`
12. `d72f404c-7d35-49e9-a341-40266e687652_605010863-54129-875064-Final_Master_Report.pdf`

### Latest recommended validation set

Use these eight documents as the current focused validation set before broader
processing. They cover the Steam Turbine case, Components sub-report case,
section-3 Components, short reports, and additional representative reports:

1. `42944a96-6210-4f8a-ba54-fa1d5cd2a29b_605015096-47162-152296-Final_Master_Report.pdf`
2. `768c7c3f-b8f2-4603-8f4a-f5c5a4e0976f_605001793-17435-297129-Final_Master_Report.pdf`
3. `00f23784-d121-4595-b61d-49d223253a05_605011513-188120-198090-Final_Master_Report.pdf`
4. `153595df-646d-410b-8ee5-371fa057c1f4_212369717-36105-SY0048243-Final_Master_Report.pdf`
5. `d72f404c-7d35-49e9-a341-40266e687652_605010863-54129-875064-Final_Master_Report.pdf`
6. `93c2180b-f866-4521-b090-b88442c6dcf1_204006084-2510-297422-Final_Master_Report.pdf`
7. `9ecb1354-1f3a-4634-8a74-12943aff45a9_605003354-23849-298081-Final_Master_Report.pdf`
8. `8ff5a231-c213-4441-b4ed-e39ed1988c8d_605030072-50465-298364-Final_Master_Report.pdf`

For each document, compare the parsed Components marker sequence with the
expected transitions, confirm that content outside Components and Appendix
remains `shared`, and compare the expected page-fallback outcome for unlabeled
Components and Appendix spans.

For the first operational validation round, use the FSR manual and FV field
service report volumes. Exclude the eSearch/ECRT volume because it contains a
separate Word-derived format outside the current final-master-report/36UUID
scope. Include manually uploaded documents as a small detector test set, but
do not broaden production scope until their document-ID resolution is
confirmed.

Also verify:

- behavior-based routing is correct when filenames are missing or misleading;
- the dotted Contents pattern is not incorrectly treated as unique to this
   family;
- known final-master-report filenames/document IDs route correctly and are
   structurally validated;
- `2. COMPONENTS` and `3. COMPONENTS` are both detected;
- generic or non-capitalized `COMPONENTS` text does not create the strong
   Components signal;
- suffixes such as `GAS TURBINE - BEARINGS` map to Gas Turbine;
- `GENERATOR -` is treated as a stronger discriminator than plain `GENERATOR`;
- versioned/legacy documents with plain `GENERATOR` but no final-master signals
   remain on their own profile;
- nested labels and incidental body-text mentions do not cause flips;
- the dotted Contents signal contributes weight 2 without alone selecting this
   profile;
- primary-ToC dotted Contents is detected within the first 10% page window;
- late embedded/sub-report dotted Contents does not trigger profile routing;
- page fallback handles only unlabeled Components and Appendix content;
- Generator once in ToC or repeated Generator body evidence maps the eligible
   fallback span to `shared`;
- fallback with no qualifying Generator evidence selects Gas Turbine or Steam
   Turbine only when that turbine type is resolved, otherwise `shared`;
- profile/version, routing signals, score, and fallback reason are persisted;
- actual profile and strategy are recorded per document, including mixed
   strategies within one `run_id`;
- region offsets remain contiguous and non-overlapping; and
- the existing default-profile regression suite remains unchanged.

## Status

Implementation not started. The Components profile contract, routing approach,
and same-profile page-fallback design are defined. Page fallback still requires
focused threshold calibration and acceptance checks before it is enabled.