# TIL Profile Review: 1907-R1

| Field | Value |
| --- | --- |
| Requested TIL | 1907-R1 |
| Matched TIL | TIL 1907-R1 |
| Revision | R1 |
| Title | ROTOR FORWARD SHAFT DOVETAIL CRACK |
| Publish Date | 2014-02-25 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
To inform users of the risk of cracking in the forward shaft dovetail region and to define inspection scope and intervals for specific unflared and flared configurations.

## Reason For Revision
Minor updates to clarify root cause statement, clarify flared and unflared part applicability for AUL, and remove 7FB from application statement.

## Compliance And Triggering Context
- Compliance Category Code: A
- Compliance Category Text: Alert - Failure to comply with the TIL could result in equipment damage or facility damage. Compliance is mandated within a specific operating time.
- Recurring Indicator: Yes - reinspections recommended at inspection interval until rotor maintenance interval is reached per GER 3620, unless upgraded to non-uniform S0/S1 vanes or enhanced compressor package
- Coarse Outage Type: At First Exposure of Component (Timing Code 4)
- Maintenance Trigger Text: At first exposure of component (Timing Code 4). For units already past interval, inspect at next interval per operating profile.
- Completion Criteria: Submit inspection results and the forward shaft serial number to GE Service Representative for review and additional recommendations. Complete TIL Compliance Record.

## Scope Of Work
- Perform dovetail ultrasonic (UT) inspection on all 32 wheel dovetail slots on both the pressure and suction side of the forward shaft dovetail
- UT inspector can complete all work within 1 shift; time to perform actual inspection is 2-3 hours with the rotor and IGV locked and tagged out
- Submit inspection results and the forward shaft serial number (located on the forward flange outside diameter of the shaft) to GE Service Representative for review and additional recommendations

## Service Recommendation Line Items
- Perform dovetail UT inspection on any 7FA unit that has operated for any length of time with all of the specified hardware configurations (uncambered IGV, standard R0 snowflake or p-cut R0, and uniform S0/S1 vane spacing for flared; uncambered IGV and standard R0 or p-cut R0 for unflared)
- Inspect all 32 wheel dovetail slots on both pressure and suction side of the dovetail
- For hours-based units: inspect at 48,000 factored fired hours
- For starts-based units: inspect at 900 factored fired starts
- For units that have already exceeded inspection interval: inspect at the next interval according to operating profile
- If compressor remains in unenhanced configuration or with uniform S0/S1 vane spacing, reinspect at the specified interval until rotor maintenance interval per GER 3620
- If unit is upgraded to non-uniform S0/S1 vanes or enhanced compressor package (package 2-5 for flared, package 3-5 for unflared), only one reinspection is necessary at time of upgrade
- If upgrade occurred prior to release of this TIL, only one inspection is necessary at the first interval outlined
- No inspections recommended for any 7FA shipped new with non-uniform S0/S1 vane spacing (flared) or enhanced compressor package 5

## Recommended Interval Or Trigger
- 48,000 factored fired hours for hours-based units
- 900 factored fired starts for starts-based units
- Reinspection at same interval until rotor maintenance interval per GER 3620, unless upgraded

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours, starts
- Requirements Text: Hours-based units: 48,000 factored fired hours. Starts-based units: 900 factored fired starts. Units that have already exceeded their inspection interval should inspect at the next interval according to operating profile.

## Applicability And Exclusions
- Frame or Model Applicability: Select unflared 7FA units and all flared 7FA units originally shipped with uniform S0/S1 vanes and non-enhanced forward compressor hardware. 7FB units are not affected by this TIL.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Flared configuration: Uncambered IGV, Standard R0 (snowflake) or p-cut R0, Uniform S0/S1 vane spacing. Unflared configuration: Uncambered IGV, Standard R0 or p-cut R0.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: No inspections recommended for any 7FA shipped new with non-uniform S0/S1 vane spacing (flared) or an enhanced compressor package 5. 7FB units are not affected by this TIL.
- Required Prior Modifications: N/A per document
- Prerequisite Outage or Inspection Context: Inspection requires rotor and IGV locked and tagged out. Timing Code 4 - At First Exposure of Component.

## SBOM Trigger Reason
Applicability depends on installed hardware configuration (IGV type, R0 blade type, S0/S1 vane spacing configuration, and compressor enhancement package level) which requires installed-configuration verification.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Rotor forward shaft - component subject to dovetail UT inspection; serial number located on forward flange outside diameter (Page 2-3, Recommendations section)
- [no explicit part number]: R0 blade - Standard R0 (snowflake) or p-cut R0 configuration relevant to applicability (Page 2, hardware configuration table)
- [no explicit part number]: Uncambered IGV - hardware configuration relevant to applicability (Page 2, hardware configuration table)
- [no explicit part number]: Uniform S0/S1 vane spacing - hardware configuration relevant to applicability for flared units (Page 2, hardware configuration table)
- [no explicit part number]: Standard R0 inspection kit - includes ultrasonic tooling for dovetail inspection (Page 4, Special Tooling section)

## Reference Documents
- GER 3620: Defines rotor maintenance interval; reinspections continue until this interval is reached

## Tables Found Summary
- {"table_label": "Table 1: Inspection Intervals", "table_description": "Defines UT inspection intervals by operating profile: 48,000 factored fired hours for hours-based units, 900 factored fired starts for starts-based units", "useful_for_downstream": true, "reason": "Directly defines inspection scheduling thresholds needed for outage planning"}
- {"table_label": "Hardware Configuration Table (unlabeled, page 2)", "table_description": "Lists hardware configurations that trigger applicability: Flared (uncambered IGV, standard R0/p-cut R0, uniform S0/S1 vane spacing) and Unflared (uncambered IGV, standard R0/p-cut R0)", "useful_for_downstream": true, "reason": "Defines which hardware configurations require inspection - critical for unit applicability determination"}

## Source Snippets
- {"field": "failure_consequences", "snippet": "Operation with a crack increases the risk of R0 migration, R0 and IGV clashing, or blade and wheel post liberation that could cause secondary damage to the gas turbine compressor."}
- {"field": "scope_of_work", "snippet": "The ultrasonic inspection should be performed on all 32 wheel dovetail slots on both the pressure and suction side of the dovetail."}
- {"field": "recommended_interval_or_trigger", "snippet": "If the compressor remains in the unenhanced configuration or with uniform S0/S1 vane spacing, reinspections are recommended at the inspection interval specified above, until the rotor maintenance interval is reached per GER 3620."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "No inspections are recommended for any 7FA shipped new with non-uniform S0/S1 vane spacing (flared) or an enhanced compressor package 5. 7FB units are not affected by this TIL."}
- {"field": "purpose", "snippet": "To inform users of the risk of cracking in the forward shaft dovetail region and to define inspection scope and intervals for specific unflared and flared configurations."}
- {"field": "risk_summary", "snippet": "One of the primary drivers is the RO response at full speed for the 1st Axial (1A) and 2nd Flex (2F) modes. This modal response drives a wheel vibratory response at full speed. A second driver for flared units is extended operation at turndown."}

## PDF Context
- File Name: TIL 1907-R1 - ROTOR FORWARD SHAFT DOVETAIL CRACK.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1907-R1 - ROTOR FORWARD SHAFT DOVETAIL CRACK.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
