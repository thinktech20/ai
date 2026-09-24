# Root Cause Analysis

Updated: 2026-09-22
Issue: Final master report format

## Status

RCA not fully completed yet.

## Current understanding

- `final_master_report` appears to be a distinct document family.
- Current notes suggest it shares a common structure large enough to justify its own preprocessing profile.

## Working root cause

The likely issue is format mismatch: the current default processing path was optimized for a different family and is not the best fit for `final_master_report` structure.

## Latest input (2026-09-18/21)

See `review-9-21` for the raw note and screenshot reference (`master-reports-issue.png`).

- The `final_master_report` TOC carries category labels inside `COMPONENTS` (e.g. `UNCATEGORIZED`, `GAS TURBINE - BEARINGS`, `GAS TURBINE - CLEARANCES`, `GAS TURBINE - COMBUSTION SECTION`), shown as unnumbered lines above numbered subsections. `COMPONENTS` may be section 2 or section 3, so the profile must detect the title rather than hard-code a section number.
- Equipment-leading labels map to the equipment (`GAS TURBINE - BEARINGS` -> `Gas Turbine`). Other unrecognized or unlabeled content remains `shared`; nested labels such as `JOURNAL BEARING` and `THRUST BEARING` do not independently change attribution.
- The latest format review distinguishes the exact family signals from generic
	words: observed Components headings use fully capitalized `2. COMPONENTS` or
	`3. COMPONENTS`; `GENERATOR -` is a stronger discriminator than plain
	`GENERATOR`, which can occur in other formats. The dotted Contents pattern
	should be checked in the primary ToC window, not anywhere in the document.
- Root cause read-through: the current logic has no rule that treats these unnumbered all-caps lines inside Components as label-flip markers, so equipment attribution inside Components is not reliably tied to these existing category headers.
- Outside Components, there is no equivalent reliable per-equipment signal in this family, so defaulting those sections to `shared` avoids guessing.
- Short reports without Components, and reports where Components cannot be detected, fall back entirely to `shared`. Some unlabeled Components content may be a scanned or text sub-report; `ambiguous` plus page fallback is deferred pending more examples.
- Confirmed heading order for this family: content number comes before the content title (`2.1 Dallas Shop QC Report`, not the reverse). This should be assumed when building/validating the heading regex for this profile.

## Open questions

- Which heading and TOC signals are consistently available in this family?
- Can one profile handle this family cleanly without affecting other families?
- Which additional text-based sub-reports, if any, justify an `ambiguous` label and page fallback?