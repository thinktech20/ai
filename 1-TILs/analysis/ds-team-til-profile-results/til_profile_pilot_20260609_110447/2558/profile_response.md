# TIL Profile Review: 2558

| Field | Value |
| --- | --- |
| Requested TIL | 2558 |
| Matched TIL | TIL 2558 |
| Revision | Not provided |
| Title | 7F.05 & 7FA.04-200 Turbine Wheel Inspection and Maintenance Recommendations |
| Publish Date | 2025-04-29 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
To advise users to perform routine inspections at maintenance intervals for 7F.05 and 7FA.04-200 gas turbine rotors to mitigate crack propagation in turbine wheels.

## Reason For Revision
Not provided

## Compliance And Triggering Context
- Compliance Category Code: A
- Compliance Category Text: Alert - Failure to comply with the TIL could result in equipment damage or facility damage. Compliance is mandated within a specific operating time.
- Recurring Indicator: Recurring - TIL is considered completed when the turbine wheels reach end of life and are removed from service
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: ECI at 96k FFH or 3,600 FFS; FPI on lock wire tabs every Major at 64k FFH; Visual/BI when rotor is available
- Completion Criteria: This TIL is considered completed when the turbine wheels reach end of life and are removed from service.

## Scope Of Work
- Qualified vendor to perform CO₂ blast cleaning of turbine rotor
- GE Vernova qualified personnel to perform rotor inspections
- Rotor inspection equipment is provided and applied by GE Vernova
- Turbine blades should be removed prior to beginning these inspections per hot gas path outage scope
- CO₂ blast cleaning of turbine rotor can be completed in one shift (12 hours), including a prior hand wiping to remove oil from the dovetail surfaces if necessary
- ECI of first and second stages can be completed in three shifts or all three stages in four shifts
- Total time between turbine blade removal and installation should be four shifts (two days)

## Service Recommendation Line Items
- Perform ECI on Stage 1 wheel (PN 146E3626) at 96k FFH or 3,600 FFS
- Perform FPI on Stage 1 wheel (PN 146E3626) lock wire tabs every Major at 64k FFH
- Perform ECI on Stage 2 wheel (PN 146E3601) at 96k FFH or 3,600 FFS
- Perform FPI on Stage 2 wheel (PN 146E3601) lock wire tabs every Major at 64k FFH
- Perform visual (VT) and borescope (BI) inspection of all accessible rotor surfaces when available
- Examine broach slot fillets, slot bottoms, tangs, and cooling slots visually
- Examine turbine blade cooling slots in wheel broach slots via Visual/BI
- Inspect spacer rim seal tooth rubs/coating visually
- Inspect balance weights for looseness/migration, set screw staking quality, tight set screw via Visual/BI
- Inspect nut damage or surface indications in flanges and webs via BI
- Inspect counterbore outside diameter ligaments on distance piece via UT
- Perform FPI on lock wire tab fillets when turbine blades are removed during routine maintenance intervals
- Perform FPI on TAS and DP with staked balance weights
- Perform FPI on TW1 Forward Web
- Dovetail ECI should be performed until rotor retirement at the frequency defined in Table 1
- Prior to ECI, turbine rotor must be appropriately cleaned; preferred method is dry ice (CO₂) blasting
- Turbine blade installation and removal should always be performed by GE Vernova turbine blade technicians to ensure appropriate tools and techniques are utilized
- If crack-like indications are found, contact local GE Vernova service representative for disposition

## Recommended Interval Or Trigger
- ECI at 96,000 Factored Fired Hours (FFH) or 3,600 Factored Fired Starts (FFS)
- FPI on lock wire tabs every Major inspection at 64,000 FFH
- Visual and Borescope inspection when rotor is available

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours, starts
- Requirements Text: ECI interval is 96k Factored Fired Hours (FFH) or 3,600 Factored Fired Starts (FFS). FPI on lock wire tabs is recommended every Major at 64k FFH.

## Applicability And Exclusions
- Frame or Model Applicability: 7F.05 and 7FA.04-200 gas turbine rotors
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: All 7F.05 and 7FA.04-200 wheels are 3-step age heat treated (3SA). All utilize an enhanced cooling slot geometry, stakeless balance rail, and modified lock wire tab. The inspection interval recommended aligns with the interval established for the latest 2SA wheels on the 7FA.04 fleet.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: FPI is not recommended for the wheel posts, as cracks under the dovetail tangs are typically closed.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Turbine blades should be removed prior to beginning these inspections per hot gas path outage scope. Rotor surfaces must be free of oil before CO₂ blast cleaning.

## SBOM Trigger Reason
Specific part numbers (146E3626, 146E3601) are referenced for applicable turbine wheel configurations requiring configuration verification to confirm applicability.

## MLI Numbers
- None

## Parts Referenced
- 146E3626 [ECI, FPI]: Stage 1 turbine wheel for 7F.05 & 7FA.04-200 (Table 1, Page 4)
- 146E3601 [ECI, FPI]: Stage 2 turbine wheel for 7F.05 & 7FA.04-200 (Table 1, Page 4)

## Reference Documents
- None

## Tables Found Summary
- {"table_label": "Table 1", "table_description": "Applicable 7F.05 & 7FA.04-200 Stages 1 & 2 Turbine Wheel Configurations with inspection types (ECI, FPI), intervals (96k FFH or 3,600 FFS for ECI; every Major at 64k FFH for FPI LWT), and applicable part numbers (146E3626, 146E3601)", "useful_for_downstream": true, "reason": "Defines specific inspection types, intervals, and applicable part numbers for outage scoping and compliance tracking"}

## Source Snippets
- {"field": "failure_consequences", "snippet": "The crack propagates to a critical length, releasing a wheel section and/or adjacent turbine blades into the turbine hot gas path section, potentially resulting in significant damage."}
- {"field": "completion_criteria_text", "snippet": "This TIL is considered completed when the turbine wheels reach end of life and are removed from service."}
- {"field": "hardware_or_part_configuration_text", "snippet": "All 7F.05 and 7FA.04-200 wheels are 3-step age heat treated (3SA). The inspection interval recommended in this TIL aligns with the interval established for the latest 2SA wheels on the 7FA.04 fleet."}
- {"field": "scope_of_work", "snippet": "CO blast cleaning of turbine rotor can be completed in one shift (12 hours), including a prior hand wiping to remove oil from the dovetail surfaces if necessary. ECI of first and second stages can be completed in three shifts or all three stages in four shifts."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "Fluorescent penetrant inspection (FPI) is recommended to detect cracks on lock wire tabs. However, it is not recommended for the wheel posts, as cracks under the dovetail tangs are typically closed."}
- {"field": "recommended_interval_or_trigger", "snippet": "Dovetail ECI should be performed until rotor retirement at the frequency defined in Table 1"}

## PDF Context
- File Name: TIL 2558 - 7F.05 & 7FA.04-200 TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2558 - 7F.05 & 7FA.04-200 TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
