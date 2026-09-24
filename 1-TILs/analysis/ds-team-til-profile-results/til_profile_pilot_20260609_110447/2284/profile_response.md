# TIL Profile Review: 2284

| Field | Value |
| --- | --- |
| Requested TIL | 2284 |
| Matched TIL | TIL 2284 |
| Revision | Not provided |
| Title | F-CLASS BALANCE WEIGHT GROOVE ENTRY SLOT RECOMMENDATIONS |
| Publish Date | 2021-05-05 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | False |

## Purpose
To advise users of the recommendation to inspect compressor aft shaft (CAS) and distance piece (DP) balance weight groove entry slots corner and perform blending operations.

## Reason For Revision
Not provided

## Compliance And Triggering Context
- Compliance Category Code: S
- Compliance Category Text: Safety - Failure to comply with this TIL could result in personal injury. Compliance is mandated within a specific operating time.
- Recurring Indicator: Not provided
- Coarse Outage Type: HGP or MI
- Maintenance Trigger Text: At first exposure of component (Timing Code 4); next planned HGP or MI outage at or before rotor reaches 378,000 equivalent cold rotor turning time hours.
- Completion Criteria: This TIL may be considered complete after completion of the FPI/MPI inspection and the CAS and DP geometry is modified.

## Scope Of Work
- FPI to inspect BWG entry slot pre-blending condition
- Set up BWG Entry Slot tool and perform blending operation
- FPI to inspect BWG entry slot post-blending condition
- Flapper peen the modified geometry post machining and post machining successful FPI

## Service Recommendation Line Items
- Perform fluorescent penetrant inspection (FPI) for all BWG entry slots on the CAS and DP during the next planned HGP or MI outage at or before the rotor reaches 378,000 equivalent cold rotor turning time (ECRT) hours
- For FPI clear cases - evaluate all balance entry slot corner conditions with replication process
- If any balance weight entry slot corner condition presents with a <0.060" fillet size - perform entry slot blending, FPI, and peening operations
- If any portion of a specific balance weight groove corner meets the <0.060" fillet criteria, perform modification machining on the entire BWG entry slot corner
- Fillet >0.060" and uniformly this size over full length of the BWG entry slot corner - leave in as-found condition
- For cases with observable FPI indication/indications - contact GE engineering through an ER case for technical disposition
- In service center, MPI inspection may be substituted for FPI inspection based on service center capability

## Recommended Interval Or Trigger
- At first exposure of component (Timing Code 4)
- Next planned HGP or MI outage at or before rotor reaches 378,000 equivalent cold rotor turning time (ECRT) hours

## Usage Counter Requirements
- Counters To Check or Consider: turning_gear_hours, fired_starts, forced_cool_downs, forced_cool_hours, cool_starts, offline_water_washes, equivalent_cold_rotor_turning_time
- Requirements Text: Equivalent Cold Rotor Turning Time (ECRT) must be calculated using turning gear hours, fired starts, forced cool downs, forced cool hours, cool starts (warm 2 and cold starts per GER-3620), and offline water washes. ECRT = TTG - ((SFS-SFC)*X) + TFC*0.25*(20% Full Speed / 6) + (Swc*Y) + (Sww*3*(20% Full Speed / 6)). Inspection required at or before 378,000 ECRT hours.

## Applicability And Exclusions
- Frame or Model Applicability: 6F, 7F, and 9F Heavy Duty Gas Turbines
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Compressor aft shaft (CAS) and distance piece (DP) balance weight groove entry slots. Applicable to components with BWG entry slots containing corner fillet size <0.060".
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Fillet >0.060" and uniformly this size over full length of the BWG entry slot corner - leave in as-found condition (no modification required).
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Requires rotor exposure during HGP or MI outage. Component must be accessible for FPI/MPI and potential machining operations.

## SBOM Trigger Reason
Not provided

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Compressor Aft Shaft (CAS) - balance weight groove entry slots requiring FPI inspection and potential blending (Recommendations section, page 3)
- [no explicit part number]: Distance Piece (DP) - balance weight groove entry slots requiring FPI inspection and potential blending (Recommendations section, page 3)
- [no explicit part number]: BWG Entry Slot Portable Machining Tool - special tooling required for blending operation (Planning Information - Special Tooling, page 5)
- [no explicit part number]: Flapper peening kit - required for peening modified geometry post machining (Planning Information - Special Tooling, page 5)

## Reference Documents
- GER-3620: Referenced for definition of warm 2 and cold starts (figure 22, latest revision) used in ECRT calculation

## Tables Found Summary
- {"table_label": "ECRT Calculation Parameters", "table_description": "Table on page 5 showing ECRT calculation variables (TTG, SFS, SFC, X, TFC, Swc, Y, Sww) with definitions and example values for a Combined Cycle 7FA.03", "useful_for_downstream": true, "reason": "Required for calculating equivalent cold rotor turning time to determine inspection timing threshold of 378,000 hours"}

## Source Snippets
- {"field": "purpose", "snippet": "To advise users of the recommendation to inspect compressor aft shaft (CAS) and distance piece (DP) balance weight groove entry slots corner and perform blending operations."}
- {"field": "failure_consequences", "snippet": "If not mitigated, the fracture propagation may lead the CAS and/or DP to separate into two separate pieces. Separation of either shaft into two pieces may create the possibility for components to exit the gas turbine leading to the possibility for INJURY TO PERSONNEL/INDIVIDUALS and substantial damage to adjacent equipment."}
- {"field": "recommended_interval_or_trigger", "snippet": "It is recommended to perform fluorescent penetrant inspection (FPI) for all BWG entry slots on the CAS and DP during the next planned outage for the unit Hot Gas Path (HGP) or Major Inspection (MI) at or before the rotor reaches a total of 378,000 equivalent cold rotor turning time."}
- {"field": "completion_criteria_text", "snippet": "This TIL may be considered complete after completion of the FPI/MPI inspection and the CAS and DP geometry is modified."}
- {"field": "service_recommendation_line_items", "snippet": "If any balance weight entry slot corner condition presents with a <0.060\" fillet size - perform entry slot blending, FPI, and peening operations to mitigate the risk of crack initiation and propagation."}
- {"field": "configuration_summary", "snippet": "Simple Cycle Unit (SC) Y = 72; Combined Cycle Unit (CC) Y = 86"}

## PDF Context
- File Name: TIL 2284 - F-CLASS BALANCE WEIGHT GROOVE ENTRY SLOT RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2284 - F-CLASS BALANCE WEIGHT GROOVE ENTRY SLOT RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
