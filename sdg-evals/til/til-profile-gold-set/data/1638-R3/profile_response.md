# TIL Profile Review: 1638-R3

| Field | Value |
| --- | --- |
| Requested TIL | 1638-R3 |
| Matched TIL | TIL 1638 |
| Revision | R3 |
| Title | F-CLASS R0 AND R1 PLATFORM ULTRASONIC TESTING |
| Publish Date | 2021-01-19 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
To inform affected users about the recommendation to perform in-situ ultrasonic inspection of the R0 and R1 blade platforms for evidence of dovetail distress.

## Reason For Revision
To communicate about updated recommendations specific to 7F and 9F R1 platform ultrasonic inspection interval and to update TIL language for clarity.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Compliance Required - Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: Recurrent basis
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: Recurrent in-situ DT-UT at specified intervals until blades with platform undercut feature are installed.
- Completion Criteria: This TIL can be considered complete when the R0 and R1 blades are replaced with blades with platform undercut feature.

## Scope Of Work
- Perform in-situ dovetail ultrasonic testing (DT-UT) of R0 blades on suction side and pressure side
- Perform in-situ dovetail ultrasonic testing (DT-UT) of R1 blades on suction side
- DT-UT may be performed concurrently with TIL 1509 and TIL 1603 inspections
- Inspections typically require one to two 12-hour shifts
- Ultrasonic testing requires rotor rotation
- R0 DT-UT can typically be carried out in 12 to 16 hours following applicable cool down and inlet entry requirements
- R1 DT-UT can typically be carried out within 12 hours following applicable cool down and inlet entry requirements

## Service Recommendation Line Items
- 7F and 9F: Perform R0 and R1 DT-UT the sooner of 8,000 actual fired hours (FH) or 150 actual fired starts (FS) on a recurrent basis
- 7F and 9F peaking units performing more than 150 actual fired starts in a year: Conduct DT-UT just before and after the peak season
- 6F: Perform R0 and R1 DT-UT during the Major Inspection (MI), or at any opportunity when the upper-half compressor casing is removed
- Units with ECP 2, 2+, 3 or 4 installed: Only R1 DT-UT is necessary since enhanced R0 blades have platform undercut feature
- Units with ECP 5 installed: TIL is not applicable since both enhanced R0 and R1 blades have platform undercut feature
- If positive indication during DT-UT, contact GE Gas Power Services representative to evaluate results
- If R0 dovetail cracks confirmed, replace entire set of R0 blades even if indications limited to fewer blades
- If R1 indications confirmed, rotor requires sending to GE Service Center to replace full set of R1 blades
- May incorporate DT-UT during annual borescope inspection or forward compressor inspections per TIL 1509 and TIL 1603

## Recommended Interval Or Trigger
- 7F and 9F: Sooner of 8,000 actual fired hours or 150 actual fired starts (recurrent)
- 7F and 9F peaking units (>150 starts/year): Just before and after peak season
- 6F: During Major Inspection (MI) or any opportunity when upper-half compressor casing is removed

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours, starts
- Requirements Text: For 7F and 9F units, DT-UT to be performed the sooner of 8,000 actual fired hours (FH) or 150 actual fired starts (FS). For peaking units performing more than 150 actual fired starts in a year, conduct DT-UT just before and after the peak season.

## Applicability And Exclusions
- Frame or Model Applicability: Applicable to select 6F, 7F, and 9F gas turbines with an 18-stage compressor.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Applicable to units operating with rotor Stage 0 (R0) and Stage 1 (R1) blades that do not have the platform undercut feature. Includes standard or non-enhanced R0 (including the P-cut R0) and R1 blades without the platform undercut feature.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Not applicable to units with ECP 5 installed since both enhanced R0 and R1 blades have platform undercut feature. For units with ECP 2, 2+, 3 or 4, only R1 DT-UT is necessary since enhanced R0 blades have platform undercut feature.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: GE has the capability to perform the R0 and R1 DT-UT without casing removal for 7F and 9F. For 6F, upper-half compressor casing removal is required. Requires rotor rotation, applicable cool down and inlet entry requirements, and qualified confined space entry personnel.

## SBOM Trigger Reason
TIL applicability depends on whether installed R0 and R1 blades have the platform undercut feature, and whether Enhanced Compressor Packages (ECP 2, 2+, 3, 4, or 5) are installed, requiring installed-configuration verification.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: R0 compressor rotor blades (standard or non-enhanced, including P-cut R0) without platform undercut feature (Recommendations section, page 3)
- [no explicit part number]: R1 compressor rotor blades without platform undercut feature (Recommendations section, page 3)
- [no explicit part number]: Enhanced Compressor Package (ECP) 2, 2+, 3, 4, or 5 - enhanced R0 and/or R1 blades with platform undercut feature (Recommendations section, page 3)

## Reference Documents
- TIL 1509: Forward compressor inspections; DT-UT may be performed concurrently with TIL 1509
- TIL 1603: Forward compressor inspections; DT-UT may be performed concurrently with TIL 1603

## Tables Found Summary
- {"table_label": "Compliance Category Table", "table_description": "Defines compliance categories C, A, and S with descriptions of required actions and consequences", "useful_for_downstream": false, "reason": "Standard GE TIL legend table, not specific to this TIL's technical content"}
- {"table_label": "Timing Code Table", "table_description": "Defines timing codes 1-6 with descriptions of when compliance is required", "useful_for_downstream": false, "reason": "Standard GE TIL legend table, not specific to this TIL's technical content"}

## Source Snippets
- {"field": "recommended_interval_or_trigger", "snippet": "For 7F and 9F units, it is recommended that the R0 and R1 DT-UT be performed the sooner of 8,000 actual fired hours (FH) or 150 actual fired starts (FS)."}
- {"field": "failure_consequences", "snippet": "Failure to comply with these recommendations may result in blade liberation and potentially result in downstream compressor distress."}
- {"field": "completion_criteria_text", "snippet": "This TIL can be considered complete when the R0 and R1 blades are replaced with blades with platform undercut feature."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "For units that have installed ECP 5, this TIL is not applicable since both the enhanced R0 and R1 blades included in ECP 5 have the platform undercut feature."}
- {"field": "hardware_or_part_configuration_text", "snippet": "This recommendation only applies to the standard or non-enhanced R0 (including the P-cut R0) and R1 blades without the platform undercut feature."}
- {"field": "risk_summary", "snippet": "In 2005, a 9F unit experienced a compressor event due to R0 distress originating from the suction side of the dovetail."}
- {"field": "scope_of_work", "snippet": "GE has the capability to perform the R0 and R1 DT-UT without casing removal."}
- {"field": "recommended_interval_or_trigger", "snippet": "For peaking units performing more than 150 actual fired starts in a year, it is recommended to conduct the DT-UT just before and after the peak season."}

## PDF Context
- File Name: TIL 1638-R3 - F-CLASS R0 AND R1 PLATFORM ULTRASONIC TESTING.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1638-R3 - F-CLASS R0 AND R1 PLATFORM ULTRASONIC TESTING.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
