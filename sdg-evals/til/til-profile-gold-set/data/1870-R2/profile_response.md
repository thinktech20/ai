# TIL Profile Review: 1870-R2

| Field | Value |
| --- | --- |
| Requested TIL | 1870-R2 |
| Matched TIL | TIL 1870 |
| Revision | R2 |
| Title | FIRST ROW COMPRESSOR BLADE STAKING INSPECTIONS |
| Publish Date | 2015-02-10 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | True |

## Purpose
To inform sites that there is a potential for first row blade migration caused by insufficient interference between the stake marks and the blade. During annual borescope inspections, it is recommended to confirm ROs have not migrated forward. The staking quality can be verified during a major inspection or when the bellmouth is scheduled to be removed.

## Reason For Revision
Expanded affected unit list and updated recommendations to reflect the more robust field installation procedural changes.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Compliance Required - Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: Not provided
- Coarse Outage Type: Major Inspection / Bellmouth Removal
- Maintenance Trigger Text: F-class units that received an R0 re-installation from January 2008 to November 2014
- Completion Criteria: This TIL is considered complete once recommendations outlined in step 3 (verify staking measurements and radial gaps during planned bellmouth removal) have been executed. Units that have not installed ROs since 2008 may mark this TIL as complete without performing the recommended inspections.

## Scope Of Work
- Visually inspect R0s for axial migration during annual borescope inspection
- Inspect for staking insert (biscuit) rotation during annual borescope, if applicable
- Verify staking measurements and radial gaps during planned bellmouth removal (major inspection)
- Re-stake any blades that have migrated or are at risk of migrating
- Blade inspection can be completed in one-half shift; re-staking requires four 12-hour shifts

## Service Recommendation Line Items
- During annual borescope inspection, confirm no R0 blades have migrated forward
- During annual borescope, confirm staking inserts (if applicable) have not significantly rotated; use mirror if necessary
- If mild rotation is observed and stake marks cannot be confirmed as forward of the blade, contact GE representative
- During major inspection or bellmouth removal, ensure both stake marks on R0 biscuits are forward of or in contact with blade dovetail
- Measure each R0 blade stake mark geometry and radial gap: stake height h must be greater than 0.030in [0.762mm], radial gap r should be less than 0.005in [0.127mm]
- Any stake marks not meeting minimum height should be re-staked
- Exception: if R0 blade is exactly flush against face of forward stub shaft with biscuits in place, stake height slightly less than 0.030in may be acceptable due to geometrical considerations - contact GE representative
- If radial gap is above limits, contact GE representative for final engineering disposition
- Any blades that move axially forward will need to be re-staked to ensure the staking ligament is actively engaged with the blade
- Replacement staking inserts should be available on sites with existing insert modifications
- Spare R0s should be available if R0 rub damage has occurred
- Staking equipment or biscuit modification installation equipment should be available to complete any necessary re-staking

## Recommended Interval Or Trigger
- Annual borescope inspection for visual migration check and insert rotation check
- Major inspection or scheduled bellmouth removal for staking measurement verification (Timing Code 5 - At Scheduled Component Part Repair or Replacement)

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: F-class units that received an R0 re-installation from January 2008 to November 2014
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: R0 migration has occurred in units with and without enhanced blades, and with and without a staking insert modification. Units with staking insert (biscuit) modification require additional insert rotation inspection.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Units that have not installed ROs since 2008 may mark this TIL as complete without performing the recommended inspections.
- Required Prior Modifications: NA
- Prerequisite Outage or Inspection Context: Steps 1 and 2 can be performed during annual borescope inspection. Step 3 requires bellmouth removal (major inspection or scheduled bellmouth removal).

## SBOM Trigger Reason
TIL applicability depends on whether R0 blades were re-installed between January 2008 and November 2014, and whether staking insert (biscuit) modification is present - requires installed-configuration verification.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: R0 staking replaceable insert (biscuit) - inserted into slot bottom to perform staking function when original slot bottom edge no longer has room for staking (Page 2 Background Discussion and Page 3-4 Recommendations)
- [no explicit part number]: First row compressor blades (R0 blades) - subject of migration inspection (Page 1 Application, Page 3 Recommendations)
- [no explicit part number]: Replacement staking inserts should be available on sites with existing insert modifications in case any stake marks do not meet inspection requirements (Page 5 Parts section)
- [no explicit part number]: Spare R0s should be available if R0 rub damage has occurred (Page 5 Parts section)

## Reference Documents
- TIL 1796: Provides recommendations for the specific team population of R0 re-installations in North America with migration events
- GE Operation and Maintenance Manual: Customers should refer to for any additional recommendations or safety warnings specific to this equipment

## Tables Found Summary
- {"table_label": "TIL Compliance Record - Installed Equipment", "table_description": "Table on page 6 with columns for Unit Numbers, Part Description, Part Number, and MLI Number - blank form for compliance recording", "useful_for_downstream": false, "reason": "Blank compliance form template with no pre-populated data"}

## Source Snippets
- {"field": "frame_or_model_applicability_text", "snippet": "The recommended inspection should be completed on F-class units that received an RO re-installation from January 2008 to November 2014."}
- {"field": "completion_criteria_text", "snippet": "This TIL is considered complete once recommendations outlined in step 3 have been executed."}
- {"field": "failure_consequences", "snippet": "The axial movement could eventually lead to compressor blades rubbing against the casing bellmouth, causing damage to the blade and rub ring."}
- {"field": "service_recommendation_line_items", "snippet": "The stake height, h, must be greater than 0.030in [0.762mm], and the radial gap between dovetail bottom and slot bottom/top of biscuit, r, should be less than 0.005in [0.127mm]"}
- {"field": "scope_of_work", "snippet": "The blade inspection be completed in one-half shift. Any potential re-staking for blades that have migrated or at risk of migrating will require four 12-hour shifts."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "Units that have not installed ROs since 2008 may mark this TIL as complete without performing the recommended inspections."}
- {"field": "hardware_or_part_configuration_text", "snippet": "RO migration has occurred in units with and without enhanced blades, and with and without a staking insert modification."}

## PDF Context
- File Name: TIL 1870-R2 - FIRST ROW COMPRESSOR BLADE STAKING INSPECTIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1870-R2 - FIRST ROW COMPRESSOR BLADE STAKING INSPECTIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
