# TIL Profile Review: 2045-R2

| Field | Value |
| --- | --- |
| Requested TIL | 2045-R2 |
| Matched TIL | TIL 2045-R2 |
| Revision | R2 |
| Title | 7F.04 S3B CREEP DISTRESS |
| Publish Date | 2024-02-28 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
Inform affected users of Stage 3 Bucket (S3B) and Stage 3 Shroud (S3S) modifications required for more reliable gas turbine operation. Failure to comply with these recommendations may result in a forced outage and/or increased part fallout during refurbishment.

## Reason For Revision
Add Tech Advanced Gas Path (AGP) configuration, clarify overall recommendations, and update the TIL Affected Units List.

## Compliance And Triggering Context
- Compliance Category Code: A
- Compliance Category Text: Alert - Failure to comply with the TIL could result in equipment damage or facility damage. Compliance is mandated within a specific operating time.
- Recurring Indicator: Yes - FPI every 4000 fired hours for previously refurbished S3Bs until removed from service
- Coarse Outage Type: At First Exposure of Component
- Maintenance Trigger Text: At First Exposure of Component (Timing Code 4). For previously refurbished S3Bs without new repair process: FPI every 4000 fired hours until removed from service.
- Completion Criteria: This TIL will be considered complete when all affected S3Bs and S3Ss have received their respective modifications or have been retired from service.

## Scope Of Work
- GE qualified NDT technician with tooling to perform FPI inspection
- 3 X 8 hour shift

## Service Recommendation Line Items
- All affected spare sets of S3Ss should be sent to a GE Vernova Service Center to receive the cooling air modification prior to installation and operation in a unit.
- All affected S3Ss currently operating in a unit should be sent to a GE Vernova Service Center to receive the cooling air modification after completion of current tour.
- After installation of modified S3Ss, resize ninth-stage extraction air orifice plate.
- After installation of modified S3Ss, perform unit control constant update.
- After installation of modified S3Ss, install updated inter-segment seals (laminate seals) on Stage 1 Shroud, Stage 2 Nozzle, Stage 2 Shroud, Stage 3 Nozzle, and Stage 3 Shroud.
- Affected S3Bs that have operated with uncooled S3Ss should be sent to a GE Vernova Service Center for evaluation and to receive the new repair process.
- 7F.04 Standard AGP parts repaired with the new process should only be operated with modified (cooled) S3Ss in their subsequent tour.
- For 7F.04 Tech parts, eligibility for subsequent tour operation will be assessed during the repair process; if eligible, they must be operated with the modified (cooled) S3S configuration.
- Parts tagged 129T6911P0001 through P048 and 129T6911P0101 through P0108 are limited to ONLY one tour after repair and must be scrapped after completion of that tour.
- S3Bs previously refurbished before the new repair process was implemented should be Fluorescent Penetrant inspected (FPI) every 4000 fired hours until removed from service, covering both pressure and suction sides of the tip shroud fillets.
- A CM&U process is mandatory to implement the S3S cooling modification and associated configuration changes.

## Recommended Interval Or Trigger
- At first exposure of component for S3S cooling modification and S3B repair
- FPI every 4000 fired hours for previously refurbished S3Bs until removed from service
- S3Ss currently operating should receive modification after completion of current tour
- Spare S3Ss should receive modification prior to installation and operation

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours
- Requirements Text: S3Bs that have operated for longer hours at higher temperatures and loads will tend to see more creep distress. FPI required every 4000 fired hours for previously refurbished S3Bs. Parts tagged 129T6911P0001-P048 and P0101-P0108 limited to one tour after repair.

## Applicability And Exclusions
- Frame or Model Applicability: 7F gas turbines with the Standard, Tech, or Tech-Lite Advanced Gas Path (AGP) configurations installed or in inventory.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Applies to S3Bs that have operated with affected (uncooled) S3Ss per Table 1. S3S cooling air modification changes part numbers from uncooled to cooled versions. After S3B repair, parts marked with machining part number 129T6911.
- Serial or Unit Applicability: Refer to TIL Affected Units List (updated in R2).
- Exclusions or Non-Applicable Conditions: Laminate seals are not required for Stage 1 Nozzles. S3S recommendations apply regardless of which AGP configuration is installed or the unit's hours/starts duty cycle.
- Required Prior Modifications: Partial completion of the TIL may result in unexpected unit performance or undesirable conditions. All configuration changes (orifice plate resizing, control constant update, laminate seal installation) must be completed together with S3S cooling modification.
- Prerequisite Outage or Inspection Context: S3S modification to be applied after completion of current tour for operating units. S3B repair requires evaluation at GE Vernova Service Center to determine creep accumulation and eligibility.

## SBOM Trigger Reason
Multiple specific part numbers for affected and modified S3S and S3B components requiring installed-configuration verification to determine if uncooled S3Ss are present and whether S3Bs have operated with them.

## MLI Numbers
- None

## Parts Referenced
- 146E1320: Affected (Uncooled) S3S Part Number (Table 1, Page 2)
- 125T7989: Modified (Cooled) S3S Part Number replacing 146E1320 (Table 1, Page 2)
- 115T4111: Affected (Uncooled) S3S Part Number (Table 1, Page 2)
- 125T6855: Modified (Cooled) S3S Part Number replacing 115T4111 (Table 1, Page 2)
- 100T8378 [FPI]: Affected S3B Kit part number for 7F.04 Standard AGP (Table 2, Page 3)
- 115T2726 [FPI]: Affected S3B Kit part number for 7F.04 Tech (Table 2, Page 3)
- 133E8966 [FPI]: Affected S3B Machining part number for 7F.04 Standard AGP (Table 2, Page 3)
- 144E7889 [FPI]: Affected S3B Machining part number for 7F.04 Standard AGP (Table 2, Page 3)
- 123T2854 [FPI]: Affected S3B Machining part number for 7F.04 Standard AGP (Table 2, Page 3)
- 124T3686 [FPI]: Affected S3B Machining part number for 7F.04 Standard AGP (Table 2, Page 3)
- 115T2721 [FPI]: Affected S3B Machining part number for 7F.04 Tech (Table 2, Page 3)
- 123T2881 [FPI]: Affected S3B Machining part number for 7F.04 Tech (Table 2, Page 3)
- 129T6911 [FPI]: Machining part number marked on S3Bs after receiving new repair process. Sub-numbers P0001-P048 and P0101-P0108 limited to one tour after repair then must be scrapped. (Page 3, Stage 3 Bucket Recommendations)
- [no explicit part number]: Ninth-stage extraction air orifice plate - requires resizing after S3S cooling modification installation (Page 2, configuration changes)
- [no explicit part number]: Updated inter-segment seals (laminate seals) for Stage 1 Shroud, Stage 2 Nozzle, Stage 2 Shroud, Stage 3 Nozzle, Stage 3 Shroud (Page 2, configuration changes)

## Reference Documents
- None

## Tables Found Summary
- {"table_label": "Table 1", "table_description": "Summary of Affected (Uncooled) and Modified (Cooled) S3S Part Numbers showing the mapping from original to modified part numbers", "useful_for_downstream": true, "reason": "Required to identify which S3S parts need the cooling air modification and to verify installed configuration"}
- {"table_label": "Table 2", "table_description": "Summary of Affected S3B Part Numbers by AGP configuration (Standard and Tech), showing Kit and Machining part numbers", "useful_for_downstream": true, "reason": "Required to identify which S3B parts are affected and need evaluation/repair at GE Vernova Service Center"}

## Source Snippets
- {"field": "purpose", "snippet": "Failure to comply with these recommendations may result in a forced outage and/or increased part fallout during refurbishment."}
- {"field": "failure_consequences", "snippet": "The internal creep voids that were observed may propagate to the surface and initiate cracks that could eventually lead to tip shroud liberation."}
- {"field": "recommended_interval_or_trigger", "snippet": "these S3Bs should be Fluorescent Penetrant inspected (FPI) every 4000 fired hours until removed from service"}
- {"field": "completion_criteria_text", "snippet": "This TIL will be considered complete when all affected S3Bs and S3Ss have received their respective modifications or have been retired from service."}
- {"field": "service_recommendation_line_items", "snippet": "Parts tagged with the following part numbers will be limited to ONLY one tour after repair: 129T6911P0001 through P048, 129T6911P0101 through P0108"}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "The above recommendations apply regardless of which AGP configuration (e.g., Standard, Tech, Tech-Lite, etc.) is installed in a unit or that unit's hours/starts duty cycle."}
- {"field": "required_prior_modifications_text", "snippet": "Partial completion of the TIL may result in unexpected unit performance or undesirable conditions. A CM&U process is mandatory to implement these changes."}

## PDF Context
- File Name: TIL 2045-R2 - 7F.04 S3B CREEP DISTRESS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2045-R2 - 7F.04 S3B CREEP DISTRESS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
