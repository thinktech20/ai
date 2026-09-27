# TIL Profile Review: 2212-R3

| Field | Value |
| --- | --- |
| Requested TIL | 2212-R3 |
| Matched TIL | TIL 2212-R3 |
| Revision | R3 |
| Title | 7F.05 COMPRESSOR T-FAIRING DISTRESS |
| Publish Date | 2022-08-03 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.91 |
| SBOM Dependency Flag | True |

## Purpose
Inform 7F.05 users with T-fairings of front end compressor inspections and recommendations to improve availability and reliability.

## Reason For Revision
Document release of the enhanced T-fairing with springs configuration for units with T-fairings installed on the GT compressor rotor. Update recommendations associated with risk understanding gained from fleet operational observations, low speed turning gear, and T-fairings with springs.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Compliance Required - Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: Yes - borescope inspections are recurring
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: Primary contribution to distress is related to time on turning gear, operational time at lower speeds during gas turbine start up and shut down activities, and/or speed up and speed down for purge related activities. ETG calculation determines inspection and replacement thresholds.
- Completion Criteria: TIL is considered completed, with no further actions required, once either modified original T-fairings with springs or enhanced T-fairings with springs have been installed in the rotor.

## Scope Of Work
- Increased T-Fairing inspections during borescope inspections.
- Enhanced T-fairing with spring replacement or Low Speed Turning Gear installation depending on specific situation.
- For units on the specific affected units list (AUL) for TIL-2167 (only specific 7FA.05 & 7F.04-200 units), ensure to perform VSV2 and 2-3 TF inspections recommended per TIL-2167 during the activities for this current TIL.

## Service Recommendation Line Items
- For units with original T-fairings (without springs) and without LSTG: If projected to reach first major inspection before 5,000 ETG hours, perform normal borescope inspections and install enhanced T-fairings with springs during first planned major inspection.
- For units with original T-fairings (without springs) and without LSTG: If projected to exceed 5,000 ETG prior to first planned major inspection, install Low Speed Turning Gear at first available opportunity.
- For units with original T-fairings (without springs) and without LSTG: During any planned borescope inspections after accumulating >5,000 ETG hours, perform detailed T-fairing inspection - inspect 100% of 1-2 and 2-3 T-Fairings for edge distress, circumferential gaps, misalignments, tilting, and rubs with borescope measurements.
- For units with original T-fairings (without springs) and without LSTG: Inspect 100% of VSV1s and VSV2s for evidence of tip rubs, tip indications, or tip loss.
- For units with original T-fairings (without springs) and without LSTG: If projected to exceed 10,000 ETG prior to first planned major inspection, order enhanced T-fairings with springs and have available at site.
- For units with original T-fairings (without springs) and LSTG installed: If projected to reach first major inspection before 5,000 ETG hours, perform normal borescope inspections and install enhanced T-fairings with springs during first planned major inspection.
- For units with original T-fairings (without springs) and LSTG installed: During any planned borescope inspections after accumulating >5,000 ETG hours, perform detailed T-fairing inspection with 100% inspection of 1-2 and 2-3 T-Fairings and VSV1s/VSV2s.
- For units with original T-fairings (without springs) and LSTG installed: If projected to exceed 10,000 ETG prior to first planned major inspection, order enhanced T-fairings with springs and have available at site.
- For units with replaced set of original T-fairings (without springs) and LSTG installed: Order enhanced T-fairings with springs and have available at site.
- For units with replaced set of original T-fairings (without springs) and LSTG installed: Once unit has accumulated >1,000 ETG hours since T-fairing replacement, perform detailed T-fairing inspection with 100% inspection of 1-2 and 2-3 T-Fairings and VSV1s/VSV2s.
- Document the condition of each T-Fairing so that rubs and measurements can be monitored over time.
- If T-Fairing edge distress is severe, replacement of the T-Fairings may be needed.
- Calculate and project ETG value for all planned hot gas path and/or major inspection outages to plan for Low Speed Turning Gear and/or Enhanced T-fairing with springs procurement.

## Recommended Interval Or Trigger
- 5,000 ETG hours - threshold for detailed T-fairing borescope inspections to begin
- 10,000 ETG hours - threshold where wear may require imminent T-fairing replacement
- 1,000 ETG hours since T-fairing replacement - threshold for detailed inspection on replaced original T-fairings without springs
- Recurring borescope inspections after applicable ETG threshold is exceeded
- Next scheduled outage (Timing Code 6)

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours, starts, turning_gear_hours, equivalent_turning_gear_hours
- Requirements Text: ETG = [TG6 * (TG6S/6)] + [TGLS * (1/60)] + [FS *4] + [PC*4]. Where ETG = Equivalent Turning Gear Hours, TG6 = TG time at normal TG speed (hours), TG6S = Normal Turning gear speed (rpm), TGLS = TG time at Low speed TG speed (hours), FS = Number of fired starts, PC = Number of purge cycles without completing a fired start. Units with >5,000 ETG hours have seen distress requiring inspection management; units with >10,000 ETG hours have observed wear reaching levels of risk that may require imminent T-fairing replacement.

## Applicability And Exclusions
- Frame or Model Applicability: Specific gas turbines with 7F.05 compressors (same compressor as the 7F.04-200) with T-fairings installed.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Applicable to units with T-fairings installed on the GT compressor rotor. Recommendations differ based on: (1) original T-fairings without springs and without Low Speed Turning Gear, (2) original T-fairings without springs with Low Speed Turning Gear installed, (3) replaced set of original T-fairings without springs with Low Speed Turning Gear installed. Enhanced T-fairing with springs configuration is the corrective solution.
- Serial or Unit Applicability: Specific gas turbines with 7F.05 compressors with T-fairings installed. For TIL-2167 related VSV2 and 2-3 TF inspections, only specific 7FA.05 & 7F.04-200 units on the affected units list (AUL) for TIL-2167.
- Exclusions or Non-Applicable Conditions: TIL is considered completed once modified original T-fairings with springs or enhanced T-fairings with springs have been installed in the rotor.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Borescope inspections require borescope camera with 3D phase measurement capability. T-fairing replacement requires compressor case removal (major inspection). Low Speed Turning Gear installation requires millwright and controls engineering.

## SBOM Trigger Reason
TIL requires verification of installed T-fairing configuration (original without springs vs. modified original with springs vs. enhanced with springs) and presence/absence of Low Speed Turning Gear to determine applicable recommendations.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Enhanced T-Fairings with springs - replacement hardware for 1-2 and 2-3 T-Fairing positions (Page 7 - Parts section and Recommendations)
- [no explicit part number]: T-Fairing lockers - required for T-fairing replacement instances (Page 7 - Parts section)
- [no explicit part number]: Low Speed Turning Gear - solution to reduce ETG accumulation (Page 5 - Recommendations)
- [no explicit part number]: 1-2 T-Fairings - removable hardware forming rotor flow path between stage 1 and stage 2 compressor blades (Page 2 - Background Discussion)
- [no explicit part number]: 2-3 T-Fairings - removable hardware forming rotor flow path between stage 2 and stage 3 compressor blades (Page 2 - Background Discussion)
- [no explicit part number]: VSV1 - Variable Stator Vane Stage 1, subject to tip loss from T-fairing rubs (Page 2 - Background Discussion)
- [no explicit part number]: VSV2 - Variable Stator Vane Stage 2, subject to tip rubs/loss inspection (Page 5 - Recommendations)
- [no explicit part number]: Special tooling to install enhanced T-Fairings with springs (GE tooling center order/rental) (Page 7 - Special Tooling)

## Reference Documents
- TIL-2167: For units on the specific affected units list (AUL) for TIL-2167 (only specific 7FA.05 & 7F.04-200 units), ensure to perform VSV2 and 2-3 TF inspections recommended per TIL-2167. Corrective actions in TIL-2167 are independent of this TIL.

## Tables Found Summary
- {"table_label": "ETG Equation Variables", "table_description": "Defines variables for Equivalent Turning Gear hours calculation: ETG, TG6, TG6S, TGLS", "useful_for_downstream": true, "reason": "Required for calculating ETG hours to determine inspection and replacement thresholds"}
- {"table_label": "Compliance Category Legend", "table_description": "Defines M, C, A, S compliance categories", "useful_for_downstream": false, "reason": "Standard legend table"}
- {"table_label": "Timing Code Legend", "table_description": "Defines timing codes 1-6", "useful_for_downstream": false, "reason": "Standard legend table"}

## Source Snippets
- {"field": "completion_criteria_text", "snippet": "This TIL is considered completed, with no further actions required, once either modified original T-fairings with springs or enhanced T-fairings with springs have been installed in the rotor."}
- {"field": "failure_consequences", "snippet": "if the T-fairing gaps and overall wear increase are too large, it is possible that the T-fairings may shingle (condition where neighboring T-fairings overlap each other), which has at certain instances lead to seismic vibrations levels that cause the unit to be unable to startup due to vibrations reaching runback/trip levels."}
- {"field": "usage_counter_requirements_text", "snippet": "ETG = [TG6 * (TG6S/6)] + [TGLS * (1/60)] + [FS *4] + [PC*4]"}
- {"field": "recommended_interval_or_trigger", "snippet": "GE has observed that units with greater than 5,000 ETG hours have seen distress requiring inspection management to occur and units with greater than 10,000 ETG hours have observed wear reaching levels of risk that may require imminent T-fairing replacement to occur."}
- {"field": "recurring_indicator_if_found", "snippet": "The above borescope inspections are recurring."}
- {"field": "reason_for_revision", "snippet": "Document release of the enhanced T-fairing with springs configuration for units with T-fairings installed on the GT compressor rotor. Update recommendations associated with risk understanding gained from fleet operational observations, low speed turning gear, and T-fairings with springs."}
- {"field": "scope_of_work", "snippet": "For only units on the specific affected units list (AUL) for TIL-2167 (only specific 7FA.05 & 7F.04-200 units), ensure to perform VSV2 and 2-3 TF inspections recommended per TIL-2167 during the activities for this current TIL."}

## PDF Context
- File Name: TIL 2212-R3 - 7F.05 COMPRESSOR T-FAIRING DISTRESS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2212-R3 - 7F.05 COMPRESSOR T-FAIRING DISTRESS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
