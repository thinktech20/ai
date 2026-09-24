# TIL Profile Review: 1972-R2

| Field | Value |
| --- | --- |
| Requested TIL | 1972-R2 |
| Matched TIL | TIL 1972 |
| Revision | R2 |
| Title | F-CLASS CONICAL FLAT SLOT BOTTOM (FSB) COMPRESSOR WHEEL RECOMMENDATIONS |
| Publish Date | 2017-07-07 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
Provide users with inspection, repair, rebuild, and operational recommendations for compressor rotors with Flat Slot Bottom (FSB) dovetails in the Stage 12-17 compressor wheels. Failure to comply with this TIL could result in compressor damage and potential material liberation through the casing.

## Reason For Revision
Included inspection recommendations for units which have Fast Ramp product installed. Update TIL to include following information: 1) Updated operational impact recommendations 2) Incorporated load swing as factor in re-inspection interval analysis 3) Incorporated forced cool recommendation statement 4) Removed inspection of CW12 and CW13 forward during UT inspections to eliminate need to remove mid-compressor case (only require CDC removal to complete UT inspection).

## Compliance And Triggering Context
- Compliance Category Code: S
- Compliance Category Text: Safety - Failure to comply with this TIL could result in personal injury. Compliance is mandated within a specific operating time.
- Recurring Indicator: Yes - re-inspection intervals are assigned after initial inspection based on indication findings and load swing factoring
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: Affected rotors accumulating between 1,300 and 2,200 actual fired starts on one or more of the Stage 12-17 compressor wheels must be inspected. Re-inspection intervals are assigned after initial inspection based on findings and load swing factoring.
- Completion Criteria: GE will evaluate the results of each inspection and provide an operational recommendation and re-inspection interval. Inspections will be certified as complete and accurate by GE.

## Scope Of Work
- Inspect Stage 12-17 FSB compressor wheels for dovetail slot indications between 1,700-2,200 actual fired starts (without OpFlex Fast Ramp) or 1,300-1,800 actual fired starts (with OpFlex Fast Ramp)
- Borescope inspection (BI) of aft rim face of Stage 17 wheel if upper half CDC installed
- Digital microscope inspection of aft rim face of Stage 17 wheel with upper half CDC removed
- Fluorescent Penetrant Inspection (FPI) if digital microscope not possible
- Ultrasonic testing (UT) of forward rim face of Stage 17 wheel and both rim faces of Stage 13 aft-16 wheels when upper half CDC can be removed
- Thorough cleaning of aft rim face around dovetail slots and compressor wheel/shaft rims prior to inspection
- Identify and record dovetail slots in traceable manner for subsequent comparison
- When rotor is in GE service shop, inspect all Stage 12-17 wheels up close for dovetail indications
- Repairs to remove indications on Stage 12-17 FSB compressor wheels when feasible
- Rebuild option: Replace existing FSB wheels with RSB wheels (Stages 12-17) to permanently remove rotor from TIL applicability

## Service Recommendation Line Items
- Inspect affected rotors between 1,700-2,200 actual fired starts (without OpFlex Fast Ramp) or 1,300-1,800 actual fired starts (with OpFlex Fast Ramp)
- Inspections must be performed by GE Life Extension Services (LES) group for quantitative accuracy
- Do not repair Stage 17 shaft indications if borescope is the only monitoring option, to preserve correlation capability
- When CW13-CW17 FSB wheels are replaced, CW12 must be changed out concurrently
- Minimize start-up and shutdown cycles to the maximum extent possible
- Prioritize start-ups/shutdowns to units with lower start rotors for multi-unit sites
- Utilize turndown in lieu of shutting down; account for decreasing load swings using Table 1 factors once indications detected
- Minimize forced cool-downs; if required, shutdown normally and cool at turning gear speed for 8 hours before initiating forced cool
- Perform Full Speed No Load (FSNL) hold upon shutdown when feasible (at least 30 minutes, up to 60 minutes)
- Perform warm restarts (within 8-10 hours of shutdown) to the maximum extent possible
- Minimize Fast Starts as much as possible
- Do not use OpFlex Fast Start features (Fast Acceleration and Fast Load) on units with FSB Stage 12-17 compressor wheels
- Apply decreasing load swing factors to all dispositioned re-inspection intervals once indications/cracks have been observed
- Load swing factors apply only for decreasing load movements above 1 MW/min rate; movements at 1 MW/min or less have no factor
- Consider RSB wheel replacement for permanent resolution

## Recommended Interval Or Trigger
- Units without OpFlex Fast Ramp: Inspect between 1,700 and 2,200 actual fired starts
- Units with OpFlex Fast Ramp: Inspect between 1,300 and 1,800 actual fired starts
- Re-inspection interval determined by GE after initial inspection based on indication findings and load swing factoring

## Usage Counter Requirements
- Counters To Check or Consider: starts, operating_hours
- Requirements Text: Actual fired starts on Stage 12-17 compressor wheels are the primary trigger (may differ from unit fired starts). Load swings in decreasing direction must be factored into actual fired starts count using Table 1 factors once indications are detected. GE can assist with determining actual fired starts of Stage 13-17 compressor rotor wheels if this figure differs from unit fired starts.

## Applicability And Exclusions
- Frame or Model Applicability: Units with 7FA.02, 7FA.03, 7FA.04, 9FA.02, 9FA.03, and 9FA.04 compressor configurations
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Units in which one or more of the Stage 12-17 compressor rotor wheels have the Flat Slot Bottom (FSB) configuration. Does not apply to units with Round Slot Bottom (RSB) wheels/shafts. Beginning in 2001, GE began introducing RSB compressor wheels into new F-class compressor rotors.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: This notification does not apply to units with Round Slot Bottom (RSB) wheels/shafts. To permanently remove a rotor from applicability of this TIL, replacement of existing FSB wheels with RSB wheels is necessary.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Inspection requires at minimum upper half CDC removal for UT and digital microscope inspections. Borescope inspection possible with CDC installed. CW12 and CW13 forward no longer required to be inspected in field inspection (only CDC removal needed for UT). When rotor is in GE service shop, all Stage 12-17 wheels inspected.

## SBOM Trigger Reason
TIL applicability depends on whether installed compressor wheels are FSB or RSB configuration, which requires installed-configuration verification. Rotor drawing number and serial number needed for further recommendations. Stage 12-17 wheel configuration (FSB vs RSB) and manufacturing date (post-2001 RSB introduction) are critical configuration variables.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Stage 12-17 Flat Slot Bottom (FSB) compressor rotor wheels - applicable components requiring inspection (Recommendations - Inspections section, pages 3-4)
- [no explicit part number]: Round Slot Bottom (RSB) replacement compressor wheels for Stages 12-17 - rebuild option to permanently remove rotor from TIL applicability (Rebuild section, page 4)
- [no explicit part number]: CW12 compressor wheel - must be changed out concurrently when CW13-CW17 FSB wheels are replaced (Inspections section, page 3)

## Reference Documents
- None

## Tables Found Summary
- {"table_label": "Table 1", "table_description": "Decreasing Load Swing Factors - maps decreasing load swing percentage ranges to equivalent actual fired start factors", "useful_for_downstream": true, "reason": "Required for calculating adjusted actual fired starts when load swings occur after indications are detected, directly affects re-inspection interval calculations"}

## Source Snippets
- {"field": "purpose", "snippet": "Failure to comply with this TIL could result in compressor damage and potential material liberation through the casing."}
- {"field": "recommended_interval_or_trigger", "snippet": "Units without OpFlex Fast Ramp installed - Inspect between 1,700 and 2,200 actual fired starts"}
- {"field": "recommended_interval_or_trigger", "snippet": "Units with OpFlex Fast Ramp installed - Inspect between 1,300 and 1,800 actual fired starts"}
- {"field": "failure_consequences", "snippet": "the structural integrity of the wheel could be affected and potentially lead to a wheel burst that may not be contained by the casing"}
- {"field": "service_recommendation_line_items", "snippet": "certain features of OpFlex Fast Start - specifically, Fast Acceleration and Fast Load - are not recommended on units with FSB Stage 12-17 compressor wheels"}
- {"field": "service_recommendation_line_items", "snippet": "If a forced cool down is required it is strongly recommended to shutdown the unit following a normal shutdown sequence and cool down at turning gear speed for 8 hours"}
- {"field": "hardware_or_part_configuration_text", "snippet": "when the CW13 thru CW17 flat slot bottom wheels are replaced, the CW12 must be changed out concurrently"}
- {"field": "usage_counter_requirements_text", "snippet": "load swings in a decreasing direction do induce tensile stresses on the flat slot bottom dovetail indications and therefore need to be accounted for once indications have been detected on a rotor to properly perform re-inspection intervals"}

## PDF Context
- File Name: TIL 1972-R2 - F-CLASS CONICAL FLAT SLOT BOTTOM (FSB) COMPRESSOR WHEEL RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1972-R2 - F-CLASS CONICAL FLAT SLOT BOTTOM (FSB) COMPRESSOR WHEEL RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
