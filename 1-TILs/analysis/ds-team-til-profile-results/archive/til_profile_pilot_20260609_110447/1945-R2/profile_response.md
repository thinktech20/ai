# TIL Profile Review: 1945-R2

| Field | Value |
| --- | --- |
| Requested TIL | 1945-R2 |
| Matched TIL | TIL 1945 |
| Revision | R2 |
| Title | F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS |
| Publish Date | 2024-07-15 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
Advise users to perform routine inspections at a maintenance interval based on installed configuration. This TIL supersedes TILs 1280, 1327, 1434, 1539, 1540, and 1742.

## Reason For Revision
1) Added a new 3 Step-Age Heat Treatment category for Stage 1 & Stage 2 wheels applicable to 7F and 6F. 2) Added a specific ECI inspection interval for Stage 1 contoured and enhanced wheels with 2 Step-Age heat treatment. 3) Added a specific ECI inspection interval for Stage 2 wheels post Rotor Life Extension.

## Compliance And Triggering Context
- Compliance Category Code: A
- Compliance Category Text: Alert - Failure to comply with the TIL could result in equipment damage or facility damage. Compliance is mandated within a specific operating time.
- Recurring Indicator: Yes - TIL is considered complete when the turbine wheels reach end of life and are removed from service
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: Inspections at intervals based on installed configuration (operating hours, starts, or outage type). Timing Code 6 - Next Scheduled Outage.
- Completion Criteria: This TIL is considered complete when the turbine wheels reach end of life and are removed from service.

## Scope Of Work
- Remove turbine blades prior to beginning inspections per hot gas path outage scope
- CO2 blast cleaning of turbine rotor (one shift / 12 hours), including prior hand wiping to remove oil from dovetail surfaces if necessary
- ECI of first and second stages (three shifts), or all three stages in four shifts
- Total time between turbine blade removal and installation should be four shifts (two days) - estimates only
- Visual inspection of all exposed turbine rotor surfaces
- Borescope inspection of accessible rotor surfaces
- FPI of staked balance weight grooves and lock wire tab fillets
- UT of counterbore outside diameter ligaments on distance piece and turbine aft shaft

## Service Recommendation Line Items
- Perform ECI, Visual, BI, FPI, and UT every 24 khrs or 900 starts for wheels fired without shot peening (original cooling slot, original balance rail/LWT)
- Perform ECI every 48 khrs or 2,400 starts for 2 Step Age wheels with original cooling slot that were never fired without shot peening (every 24 khrs or 900 starts if back cut buckets not installed)
- Perform ECI at 96 khrs or 3,600 starts for 2 Step Age Stage 1 wheels with contoured or enhanced cooling slot (every 48 khrs or 2,400 starts if back cut buckets not installed for contoured)
- Perform ECI at 96 khrs or 3,600 starts for 2 Step Age Stage 1 enhanced wheels with stakeless & modified tab
- For Stage 2 wheels with 2 Step Age: ECI at 96 khrs or 3,750 starts if specific S2B P/N installed (inspection window 80-104 khrs), otherwise at first Major after TW2 Life Extension
- Perform BI every HGPI when CDC is not removed for applicable Stage 1 wheels
- Perform FPI on LWT every HGPI when buckets are removed; on BWG every Major and when CDC is removed during HGPI
- For stakeless & modified tab wheels: FPI LWT every Major only
- For 3 Step Age wheels: FPI LWT every Major only
- Install back cut (modified) turbine blades on all turbine rotors at next scheduled maintenance
- TW3 staked BWG: FPI every MI and when Exhaust Frame is removed during HGPI; stakeless: no inspections necessary
- TW3 original LWT: FPI every HGPI while buckets are removed; modified LWT: FPI every MI
- TAS staked BWG: FPI every MI and when Exhaust Frame is removed during HGPI; stakeless: no inspections necessary
- Contact GE Vernova representative for peening modification wheels to determine applicable peening condition based on turbine serial number
- If cooling slot crack is detected, immediate wheel replacement is recommended to avoid risk of wheel post liberation during operation
- If crack-like indications found on LWT or BWG, contact GE Vernova for disposition; in-situ repair procedure may be used

## Recommended Interval Or Trigger
- ECI every 24 khrs or 900 starts (fired without shot peening, original cooling slot)
- ECI every 48 khrs or 2,400 starts (2 Step Age, original cooling slot, never fired without shot peening; or every 24 khrs/900 starts if back cut buckets not installed)
- ECI at 96 khrs or 3,600 starts (2 Step Age, contoured or enhanced cooling slot; or every 48 khrs/2,400 starts if back cut buckets not installed for contoured Stage 1)
- ECI at 96 khrs or 3,750 starts for Stage 2 with specific S2B P/N installed (inspection window 80-104 khrs)
- ECI at first Major after TW2 Life Extension (Stage 2 enhanced/contoured wheels)
- BI every HGPI when CDC is not removed
- FPI LWT every HGPI when buckets are removed
- FPI BWG every Major and when CDC is removed during HGPI
- FPI LWT every Major (stakeless & modified tab or 3 Step Age wheels)
- FPI BWG every MI and when Exhaust Frame removed during HGPI (TW3 and TAS staked)

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours, starts
- Requirements Text: Inspection intervals are defined in operating hours (khrs) and starts. For example: every 24 khrs or 900 starts, every 48 khrs or 2,400 starts, at 96 khrs or 3,600 starts, at 96 khrs or 3,750 starts (inspection window 80-104 khrs). Whichever limit is reached first triggers the inspection.

## Applicability And Exclusions
- Frame or Model Applicability: Select F-class gas turbine rotors. Tables specify 7F, 9F, and 6F frames.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Applicability depends on: material heat treatment (2 Step Age vs 3 Step Age), peening condition (fired without shot peening, peening modification, never fired without shot peening), cooling slot geometry (original, contoured, enhanced), balance rail & lock wire tab configuration (original, stakeless & modified tab), and whether back cut buckets are installed. Specific Stage 2 Bucket (S2B) part numbers determine ECI interval for Stage 2 wheels.
- Serial or Unit Applicability: For peening modification wheels, contact GE Vernova representative with turbine rotor serial number to determine applicable peening condition.
- Exclusions or Non-Applicable Conditions: Stakeless BWG wheels require no BWG inspections. Rotors operating in high ambient and/or corrosive conditions are addressed separately in TIL 1937.
- Required Prior Modifications: Back cut (modified) turbine blades recommended for all turbine rotors. Dovetail back cut modifications performed as part of standard turbine blade repair/refurbishment process.
- Prerequisite Outage or Inspection Context: Turbine blades must be removed prior to beginning inspections per hot gas path outage scope. Prior to ECI, turbine rotor must be appropriately cleaned (CO2 blasting preferred). Surfaces must be free of oil beforehand.

## SBOM Trigger Reason
Inspection intervals and types are determined by specific installed turbine wheel part numbers, Stage 2 Bucket (S2B) part numbers, peening condition requiring serial number verification, cooling slot geometry, balance rail/LWT configuration, material heat treatment, and whether back cut buckets are installed. Configuration verification against installed hardware is required.

## MLI Numbers
- None

## Parts Referenced
- 227C5762 [ECI, Visual, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 103E5795 [ECI, Visual, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 188D7369 [ECI, Visual, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 109E3085 [ECI, Visual, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 101E8627 [ECI, Visual, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 109E3896 [ECI, Visual, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 103E5773 [ECI, Visual, BI, FPI, UT]: 7F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 193D2053: 7F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT - contact GE to determine peening condition (Table 1)
- 193D2063: 7F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT - contact GE to determine peening condition (Table 1)
- 243C1494 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 109E5612 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 188D7996 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 114E1228 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 196D1915 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 116E2434 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 199D3931 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 117E5673 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 109E5303 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 119E2398 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 109E5589 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 119E2621 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 1)
- 116E3967 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 1)
- 119E3771 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 1)
- 119E4181 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 1)
- 323E2241 [ECI, BI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original balance rail & LWT (Table 1)
- 144E7560 [ECI, FPI]: 7F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 1)
- 146E3626 [FPI]: 7F Stage 1 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 1)
- 227C5763 [ECI, Visual, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 103E5796 [ECI, Visual, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 101E8629 [ECI, Visual, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 108E4197 [ECI, Visual, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 103E5775 [ECI, Visual, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 109E3897 [ECI, Visual, BI, FPI, UT]: 7F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 193D2055: 7F Stage 2 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 2)
- 193D2064: 7F Stage 2 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 2)
- 193D2400 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 199D3925 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 109E5591 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 109E5614 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 114E1229 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 116E2436 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 2)
- 116E3968 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 2)
- 119E6503 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 2)
- 323E2240 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original balance rail & LWT (Table 2)
- 144E7562 [ECI, FPI]: 7F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 2)
- 146E3601 [FPI]: 7F Stage 2 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 2)
- 118T8421: 7F Stage 2 Bucket P/N - if installed, ECI at 96 khrs or 3,750 starts for applicable Stage 2 wheels (Table 2)
- 122T9656: 7F Stage 2 Bucket P/N - if installed, ECI at 96 khrs or 3,750 starts for applicable Stage 2 wheels (Table 2)
- 101E2274 [ECI, Visual, BI, FPI, UT]: 9F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 3)
- 103E3969 [ECI, Visual, BI, FPI, UT]: 9F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 3)
- 109E3982 [ECI, Visual, BI, FPI, UT]: 9F Stage 1 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 3)
- 227C5743: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 193D2050: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 188D7864: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 193D2422: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 193D2023: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 196D1632: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 193D2036: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 198D1211: 9F Stage 1 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 3)
- 109E5254 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 3)
- 111E3299 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 3)
- 119E6594 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 3)
- 133E8667 [ECI, BI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original balance rail & LWT (Table 3)
- 146E2874 [ECI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 3)
- 113T0325 [ECI, FPI]: 9F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 3)
- 101E2276 [ECI, Visual, BI, FPI, UT]: 9F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 4)
- 103E3971 [ECI, Visual, BI, FPI, UT]: 9F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 4)
- 109E3893 [ECI, Visual, BI, FPI, UT]: 9F Stage 2 wheel, fired without shot peening, original cooling slot, original balance rail & LWT (Table 4)
- 188D7848: 9F Stage 2 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 4)
- 193D2106: 9F Stage 2 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 4)
- 188D7895: 9F Stage 2 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 4)
- 193D2025: 9F Stage 2 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 4)
- 193D2037: 9F Stage 2 wheel, peening modification, original cooling slot, original balance rail & LWT (Table 4)
- 109E5256 [ECI, FPI]: 9F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 4)
- 111E3298 [ECI, FPI]: 9F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 4)
- 119E6597 [ECI, FPI]: 9F Stage 2 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 4)
- 133E8776 [ECI, FPI]: 9F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original balance rail & LWT (Table 4)
- 146E1078 [ECI, FPI]: 9F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 4)
- 146E2875 [ECI, FPI]: 9F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 4)
- 113T0328 [ECI, FPI]: 9F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 4)
- 119T9404: 9F Stage 2 Bucket P/N - if installed, ECI at 96 khrs or 3,750 starts for applicable Stage 2 wheels (Table 4)
- 122T0124: 9F Stage 2 Bucket P/N - if installed, ECI at 96 khrs or 3,750 starts for applicable Stage 2 wheels (Table 4)
- 109E9194 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 5)
- 116E3992 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 5)
- 323E1860 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 5)
- 137E1002 [ECI, BI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original balance rail & LWT (Table 5)
- 141E4569 [ECI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 5)
- 121T7210 [ECI, FPI]: 6F Stage 1 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 5)
- 131T7543 [FPI]: 6F Stage 1 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 5)
- 109E9196 [ECI, FPI]: 6F Stage 2 wheel, 2 Step Age, never fired without shot peening, original cooling slot, original balance rail & LWT (Table 6)
- 116E3994 [ECI, FPI]: 6F Stage 2 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 6)
- 323E1916 [ECI, FPI]: 6F Stage 2 wheel, 2 Step Age, never fired without shot peening, contoured cooling slot, original balance rail & LWT (Table 6)
- 137E1062 [ECI, FPI]: 6F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, original balance rail & LWT (Table 6)
- 141E4586 [ECI, FPI]: 6F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 6)
- 126T7211 [ECI, FPI]: 6F Stage 2 wheel, 2 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 6)
- 131T7549 [FPI]: 6F Stage 2 wheel, 3 Step Age, never fired without shot peening, enhanced cooling slot, stakeless & modified tab (Table 6)
- 120T1387: 6F Stage 2 Bucket P/N - if installed, ECI at 96 khrs or 3,750 starts for applicable Stage 2 wheels (Table 6)
- 123T0809: 6F Stage 2 Bucket P/N - if installed, ECI at 96 khrs or 3,750 starts for applicable Stage 2 wheels (Table 6)

## Reference Documents
- TIL 1280: Superseded by TIL 1945-R2
- TIL 1327: Superseded by TIL 1945-R2
- TIL 1434: Superseded by TIL 1945-R2
- TIL 1539: Superseded by TIL 1945-R2
- TIL 1540: Superseded by TIL 1945-R2
- TIL 1742: Superseded by TIL 1945-R2
- TIL 1937: Addresses rotors operating in high ambient and/or corrosive conditions with increased risk of crack initiation and propagation

## Tables Found Summary
- {"table_label": "Table 1", "table_description": "Applicable 7F Stage 1 Turbine Wheel Configurations - maps part numbers to inspection types and intervals based on heat treatment, peening, cooling slot, and balance rail/LWT configuration", "useful_for_downstream": true, "reason": "Defines specific inspection requirements (ECI, BI, FPI, UT, Visual) and intervals for each 7F Stage 1 wheel part number"}
- {"table_label": "Table 2", "table_description": "Applicable 7F Stage 2 Turbine Wheel Configurations - maps part numbers to inspection types and intervals including S2B-dependent ECI triggers", "useful_for_downstream": true, "reason": "Defines specific inspection requirements and intervals for each 7F Stage 2 wheel part number, including conditional ECI based on installed S2B P/N"}
- {"table_label": "Table 3", "table_description": "Applicable 9F Stage 1 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines specific inspection requirements and intervals for each 9F Stage 1 wheel part number"}
- {"table_label": "Table 4", "table_description": "Applicable 9F Stage 2 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines specific inspection requirements and intervals for each 9F Stage 2 wheel part number, including conditional ECI based on installed S2B P/N"}
- {"table_label": "Table 5", "table_description": "Applicable 6F Stage 1 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines specific inspection requirements and intervals for each 6F Stage 1 wheel part number"}
- {"table_label": "Table 6", "table_description": "Applicable 6F Stage 2 Turbine Wheel Configurations", "useful_for_downstream": true, "reason": "Defines specific inspection requirements and intervals for each 6F Stage 2 wheel part number, including conditional ECI based on installed S2B P/N"}

## Source Snippets
- {"field": "purpose", "snippet": "Advise users to perform routine inspections at a maintenance interval based on installed configuration. This TIL supersedes TILs 1280, 1327, 1434, 1539, 1540, and 1742."}
- {"field": "failure_consequences", "snippet": "the crack propagates to a critical length, releasing a wheel section and/or adjacent turbine blades into the turbine hot gas path section potentially resulting in significant damage"}
- {"field": "failure_consequences", "snippet": "Cracks in the forward wheel web, if left unaddressed, could result in a partial wheel material liberation, particularly when located on the stage 1 wheel."}
- {"field": "completion_criteria_text", "snippet": "This TIL is considered complete when the turbine wheels reach end of life and are removed from service."}
- {"field": "scope_of_work", "snippet": "CO2 blast cleaning of turbine rotor can be completed in one shift (12 hours), including a prior hand wiping to remove oil from the dovetail surfaces if necessary. ECI of first and second stages can be completed in three shifts, or all three stages in four shifts."}
- {"field": "service_recommendation_line_items", "snippet": "If a cooling slot crack is detected during the inspection, immediate wheel replacement will be recommended to avoid the risk of wheel post liberation during operation."}
- {"field": "service_recommendation_line_items", "snippet": "it is recommended that back cut turbine blades always be installed on all turbine rotors"}
- {"field": "risk_summary", "snippet": "Rotors operating in high ambient and humid or corrosive conditions have an increased risk of crack initiation and propagation."}
- {"field": "hardware_or_part_configuration_text", "snippet": "After 1996, all F-class turbine wheels shipped with full peening coverage; these wheels were never fired without shot peening."}
- {"field": "configuration_summary", "snippet": "Some rotors may have a combination of enhanced, contoured, and/or original configuration wheels, depending on rotor repair history. All wheels should follow their applicable inspection recommendations."}

## PDF Context
- File Name: TIL 1945-R2 - F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1945-R2 - F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
