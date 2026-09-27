# TIL Profile Review: 1937-R2

| Field | Value |
| --- | --- |
| Requested TIL | 1937-R2 |
| Matched TIL | TIL 1937 |
| Revision | R2 |
| Title | F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS |
| Publish Date | 2024-04-10 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
Advise users to perform routine inspections at a maintenance interval based on installed configuration for select F-class gas turbine rotors operating in high ambient and specific environmental conditions.

## Reason For Revision
1) Added a new 3 Step-Age Heat Treatment category for Stage 1 & Stage 2 wheels. 2) Added a specific ECI inspection interval for Stage 1 enhanced wheels with 2 Step-Age heat treatment. 3) Added a specific ECI inspection interval for Stage 2 wheels post Rotor Life Extension.

## Compliance And Triggering Context
- Compliance Category Code: A
- Compliance Category Text: Alert - Failure to comply with the TIL could result in equipment damage or facility damage. Compliance is mandated within a specific operating time.
- Recurring Indicator: Yes - recurring inspections at defined intervals until turbine wheels reach end of life
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: Inspections triggered by operating hours, starts, outage type (HGPI/Major), bucket removal, CDC removal, and Rotor Life Extension milestones.
- Completion Criteria: This TIL is considered completed when the turbine wheels reach end of life and are removed from service.

## Scope Of Work
- Qualified vendor to perform CO₂ blast cleaning of turbine rotor
- GE Vernova qualified personnel to perform rotor inspections
- Back-cut stage 1 and stage 2 turbine blades
- Rotor inspection equipment and blend/peen kit are provided and applied by GE Vernova
- Turbine blades should be removed prior to beginning these inspections per hot gas path outage scope
- CO₂ blast cleaning of turbine rotor can be completed in one shift (12 hours), including a prior hand wiping to remove oil from the dovetail surfaces if necessary
- ECI of first and second stages can be completed in three shifts or all three stages in four shifts
- Total time between turbine blade removal and installation should be four shifts (two days)

## Service Recommendation Line Items
- Perform ECI, Visual, BI, FPI, and UT inspections every 24 khrs or 900 starts for wheels fired without shot peening (original cooling slot, original LWT)
- Perform ECI every 32 khrs or 1,200 starts for 2 Step Age wheels with original cooling slot (every 24 khrs or 900 starts if back cut buckets not installed)
- Perform ECI at 96 khrs or 3,600 starts for 2 Step Age wheels with contoured/enhanced cooling slot (every 48 khrs or 2,400 starts if back cut buckets not installed)
- Perform BI every HGPI when CDC is not removed
- Perform FPI on LWT every HGPI when buckets are removed; on BWG every Major and when CDC is removed during HGPI
- For Stage 2 wheels with 2 Step Age: perform ECI at first Major after TW2 Life Extension in addition to interval-based ECI
- For 3 Step Age wheels with enhanced cooling slot and stakeless/modified tab: FPI on LWT every Major
- TW3 balance weight grooves (if staked): FPI every Major Inspection and when Exhaust Frame is removed during HGPI; if stakeless: no inspections necessary
- TW3 lockwire tabs (if original): FPI every HGPI while buckets are removed; if modified: FPI every MI
- TAS balance weight grooves (if staked): FPI every MI and when Exhaust Frame is removed during HGPI; if stakeless: no inspections necessary
- Install back cut (dovetail modified) Stage 1 and 2 turbine blades at next scheduled maintenance (HGPI or MI)
- If cooling slot crack is detected during inspection, immediate wheel replacement is recommended
- Contact GE Vernova representative to determine peening condition for Peening Modification category wheels
- Prior to ECI, turbine rotor must be appropriately cleaned (preferred: CO₂ blasting; alternative: hand-cleaning 2-3 shifts)

## Recommended Interval Or Trigger
- Every 24 khrs or 900 starts (fired without shot peening, original cooling slot)
- Every 32 khrs or 1,200 starts (2 Step Age, original cooling slot, never fired without shot peening; reduces to 24 khrs/900 starts if back cut buckets not installed)
- At 96 khrs or 3,600 starts (2 Step Age, contoured/enhanced cooling slot; every 48 khrs/2,400 starts if back cut buckets not installed)
- Every HGPI when CDC is not removed (BI)
- Every HGPI when buckets are removed (FPI on LWT)
- Every Major and when CDC is removed during HGPI (FPI on BWG)
- Every Major (FPI on LWT for modified tab / 3 Step Age configurations)
- At first Major after TW2 Life Extension (ECI for Stage 2 wheels)

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours, starts
- Requirements Text: Inspection intervals are defined in thousands of operating hours (khrs) and number of starts. Specific thresholds vary by wheel configuration: 24 khrs/900 starts, 32 khrs/1,200 starts, 48 khrs/2,400 starts, or 96 khrs/3,600 starts depending on heat treatment, peening condition, cooling slot geometry, and whether back cut buckets are installed.

## Applicability And Exclusions
- Frame or Model Applicability: Select F-class gas turbine rotors: 6F, 7F, and 9F frames
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Applicability depends on material heat treatment (2 Step Age vs 3 Step Age), peening condition (fired without shot peening, peening modification, never fired without shot peening), cooling slot geometry (original, contoured, enhanced), and balance rail & lock wire tab configuration (original, stakeless & modified tab). Whether back cut buckets are installed affects ECI interval.
- Serial or Unit Applicability: Units operating in high ambient and humid or corrosive environmental conditions. For Peening Modification category wheels, contact GE Vernova representative with turbine rotor serial number to determine applicable peening condition.
- Exclusions or Non-Applicable Conditions: Stakeless balance weight grooves on TW3 and TAS require no BWG inspections. Modified lock wire tabs on TW3 only require FPI every MI rather than every HGPI.
- Required Prior Modifications: Back cut (dovetail modified) Stage 1 and 2 turbine blades recommended to be installed on all turbine rotors. Relief cut modifications incorporated into new production F-class turbine blades and performed as part of standard turbine blade repair/refurbishment.
- Prerequisite Outage or Inspection Context: Turbine blades must be removed prior to beginning inspections per hot gas path outage scope. Rotor must be cleaned (CO₂ blast preferred) prior to ECI. For Peening Modification wheels, until validated by GE Vernova representative, assume Fired without Shot Peening recommendations apply.

## SBOM Trigger Reason
Inspection intervals and required inspection types are determined by specific turbine wheel part numbers, which must be validated against installed configuration. Multiple part numbers per frame/stage with different heat treatment, peening, cooling slot, and LWT configurations drive different maintenance requirements.

## MLI Numbers
- None

## Parts Referenced
- 227C5762 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 1)
- 103E5795 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 1)
- 188D7369 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 1)
- 109E3085 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 1)
- 101E8627 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 1)
- 109E3896 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 1)
- 103E5773 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 1)
- 193D2053 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, peening modification, original cooling slot, original LWT - contact GE Vernova to determine peening condition (Table 1)
- 193D2063 [ECI, VT, BI, FPI, UT]: 7F Stage 1 wheel, peening modification, original cooling slot, original LWT - contact GE Vernova to determine peening condition (Table 1)
- 243C1494 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 109E5612 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 188D7996 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 114E1228 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 196D1915 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 116E2434 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 199D3931 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 117E5673 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 109E5303 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 119E2398 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 109E5589 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 119E2621 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 1)
- 116E3967 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 1)
- 119E3771 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 1)
- 119E4181 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 1)
- 323E2241 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original LWT (Table 1)
- 144E7560 [ECI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 1)
- 146E3626 [FPI]: 7F Stage 1 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 1)
- 227C5763 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original LWT (Table 2)
- 103E5796 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original LWT (Table 2)
- 101E8629 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original LWT (Table 2)
- 108E4197 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original LWT (Table 2)
- 103E5775 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original LWT (Table 2)
- 109E3897 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original LWT (Table 2)
- 193D2055 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, peening modification, original cooling slot, original LWT (Table 2)
- 193D2064 [ECI, VT, BI, FPI, UT]: 7F Stage 2 wheel, peening modification, original cooling slot, original LWT (Table 2)
- 193D2400 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 2)
- 199D3925 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 2)
- 109E5591 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 2)
- 109E5614 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 2)
- 114E1229 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 2)
- 116E2436 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 2)
- 116E3968 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 2)
- 119E6503 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 2)
- 323E2240 [ECI, BI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original LWT (Table 2)
- 144E7562 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 2)
- 146E3627 [FPI]: 7F Stage 2 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 2)
- 101E2274 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 3)
- 103E3969 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 3)
- 109E3982 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, fired without shot peening, original cooling slot, original LWT (Table 3)
- 227C5743 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 193D2050 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 188D7864 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 193D2422 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 193D2023 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 196D1632 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 193D2036 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 198D1211 [ECI, VT, BI, FPI, UT]: 9F Stage 1 wheel, peening modification, original cooling slot, original LWT (Table 3)
- 109E5254 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 3)
- 111E3299 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 3)
- 119E6594 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 3)
- 133E8667 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original LWT (Table 3)
- 146E2874 [ECI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 3)
- 131T7528 [FPI]: 9F Stage 1 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 3)
- 131T7534 [FPI]: 9F Stage 2 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 4)
- 109E9194 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original LWT (Table 5)
- 116E3992 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 5)
- 323E1860 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original LWT (Table 5)
- 137E1002 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original LWT (Table 5)
- 141E4569 [ECI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 5)
- 131T7543 [FPI]: 6F Stage 1 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 5)
- 131T7549 [FPI]: 6F Stage 2 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 6)

## Reference Documents
- TIL 1280: Superseded by TIL 1937-R2
- TIL 1327: Superseded by TIL 1937-R2
- TIL 1434: Superseded by TIL 1937-R2
- TIL 1539: Superseded by TIL 1937-R2
- TIL 1540: Superseded by TIL 1937-R2
- TIL 1742: Superseded by TIL 1937-R2

## Tables Found Summary
- {"table_label": "Table 1", "table_description": "Applicable 7F Stage 1 Turbine Wheel Configurations - maps heat treatment, peening condition, cooling slot geometry, and LWT configuration to required inspections, intervals, and applicable part numbers", "useful_for_downstream": true, "reason": "Defines inspection types and intervals by part number for 7F Stage 1 wheels; critical for outage scoping and SBOM validation"}
- {"table_label": "Table 2", "table_description": "Applicable 7F Stage 2 Turbine Wheel Configurations - same structure as Table 1 for Stage 2", "useful_for_downstream": true, "reason": "Defines inspection types and intervals by part number for 7F Stage 2 wheels including TW2 Life Extension ECI requirement"}
- {"table_label": "Table 3", "table_description": "Applicable 9F Stage 1 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines inspection types and intervals by part number for 9F Stage 1 wheels"}
- {"table_label": "Table 4", "table_description": "Applicable 9F Stage 2 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines inspection types and intervals by part number for 9F Stage 2 wheels including TW2 Life Extension ECI requirement"}
- {"table_label": "Table 5", "table_description": "Applicable 6F Stage 1 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines inspection types and intervals by part number for 6F Stage 1 wheels"}
- {"table_label": "Table 6", "table_description": "Applicable 6F Stage 2 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines inspection types and intervals by part number for 6F Stage 2 wheels including TW2 Life Extension ECI requirement"}

## Source Snippets
- {"field": "purpose", "snippet": "Advise users to perform routine inspections at a maintenance interval based on installed configuration."}
- {"field": "failure_consequences", "snippet": "the crack propagates to a critical length, releasing a wheel section and/or adjacent turbine blades into the turbine hot gas path section potentially resulting in significant damage"}
- {"field": "completion_criteria_text", "snippet": "This TIL is considered completed when the turbine wheels reach end of life and are removed from service."}
- {"field": "scope_of_work", "snippet": "Qualified vendor to perform CO\u2082 blast cleaning of turbine rotor. GE Vernova qualified personnel to perform rotor inspections. Back-cut stage 1 and stage 2 turbine blades."}
- {"field": "risk_summary", "snippet": "Rotors operating in high ambient and humid or corrosive conditions have an increased risk of crack initiation and propagation."}
- {"field": "service_recommendation_line_items", "snippet": "If a cooling slot crack is detected during the inspection, immediate wheel replacement will be recommended to help avoid the risk of wheel post liberation during operation."}
- {"field": "hardware_or_part_configuration_text", "snippet": "Some rotors may have a combination of enhanced, contoured, and/or original configuration wheels, depending on rotor repair history. All wheels should follow their applicable inspection recommendations."}
- {"field": "prerequisite_outage_or_inspection_context_text", "snippet": "Until validated by your GE Vernova representative, assume Fired without Shot Peening recommendations apply."}

## PDF Context
- File Name: TIL 1937-R2 - F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1937-R2 - F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
