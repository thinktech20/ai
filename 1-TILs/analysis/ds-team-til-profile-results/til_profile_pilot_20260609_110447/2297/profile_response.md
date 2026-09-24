# TIL Profile Review: 2297

| Field | Value |
| --- | --- |
| Requested TIL | 2297 |
| Matched TIL | TIL 2297 |
| Revision | Not provided |
| Title | FLARED 7F & 9F PRE-ENHANCED COMPRESSOR R1 BLADE RECOMMENDATIONS |
| Publish Date | 2021-08-02 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | True |

## Purpose
To inform affected users of the risk of R1 tip cracks, or tip corner liberations and to provide recommendations to help improve unit availability and reliability.

## Reason For Revision
Not provided

## Compliance And Triggering Context
- Compliance Category Code: M
- Compliance Category Text: Maintenance - Identifies maintenance guidelines or best practices for reliable equipment operation.
- Recurring Indicator: Recurring until full set of R1 blades are replaced
- Coarse Outage Type: At Scheduled Component Part Repair or Replacement
- Maintenance Trigger Text: At Scheduled Component Part Repair or Replacement (Timing Code 5). Also triggered by identification of R1 tip rubs, tip indications, tip corner loss, tip repairs, or operation with uniform spaced S0 and S1 vanes.
- Completion Criteria: This TIL can be considered complete when the above recommendations are incorporated into the site's maintenance planning practices, or when the full set of R1 blades are replaced. Until the full set of R1 blades are replaced, it is recommended to continue with the operation, maintenance, and inspection guidelines per this TIL and TIL 1509.

## Scope Of Work
- Inspection and maintenance scope per the listed reference documents (TIL 1509, TIL 1638) in the field.
- Compressor rotor unstack and R1 blade replacement at repair shop.
- During planned or annual borescope inspections, monitor the R1 blade tips for indications of rubs and evidence of corrosion pitting.
- If R1 tip rubs are identified, or if R1 tips had previously rubbed or repaired, or if the rotor has previously operated with or currently operating with uniform spaced S0 and S1 vanes, perform a non-destructive inspection (NDI) of all R1 blades as described in TIL 1509.
- If new R1 tip rubs or indications are identified, or if R1 tip indications are repaired, perform repeat R1 tip NDI per the schedule described in TIL 1509.

## Service Recommendation Line Items
- Follow the operational and maintenance best practices to avoid or limit the likelihood of heavy tip rubs as described in TIL 1509.
- During planned or annual borescope inspections, monitor the R1 blade tips for indications of rubs and evidence of corrosion pitting.
- If R1 tip rubs are identified, or if R1 tips had previously rubbed or repaired, or if the rotor has previously operated with or currently operating with uniform spaced S0 and S1 vanes, perform NDI of all R1 blades as described in TIL 1509.
- If new R1 tip rubs or indications are identified, or if R1 tip indications are repaired, perform repeat R1 tip NDI per the schedule described in TIL 1509.
- Consider installing a full set of enhanced R1 blades whenever the unit rotor is sent to a GE repair shop and scope requires unstacking the compressor rotor.
- Optionally, consider unstacking the compressor rotor to replace the R1 blades at the next opportunity the unit rotor is sent to a GE repair shop.

## Recommended Interval Or Trigger
- Annual borescope inspection to monitor R1 blade tips
- NDI of all R1 blades per TIL 1509 schedule if rubs, indications, or uniform spaced S0/S1 vane operation identified
- Repeat R1 tip NDI per TIL 1509 schedule if new indications found or tips repaired
- R1 blade replacement at next compressor rotor unstack at GE repair shop

## Usage Counter Requirements
- Counters To Check or Consider: starts
- Requirements Text: A light or moderate R1 tip rub may not manifest into an indication in the short term and it could take several start-stop cycles following the rub event before an indication is identified.

## Applicability And Exclusions
- Frame or Model Applicability: Flared 7F and 9F gas turbines
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Units operating with pre-enhanced (standard) rotor stage-1 (R1) blades. Enhanced R1 blades are full airfoil shot-peened and have higher damage tolerance compared to pre-enhanced R1 blades.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Not applicable to units already operating with enhanced R1 blades. Installing enhanced R1 blades eliminates TIL 1509 inspection scope beyond annual BI and eliminates TIL 1638 R1 dovetail ultrasonic testing scope.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: R1 blade replacement requires compressor rotor unstack at GE repair shop. R1 blend repair requires lifting the upper-half compressor casing.

## SBOM Trigger Reason
TIL requires identification of whether pre-enhanced (standard) or enhanced R1 blades are installed, and whether uniform spaced S0 and S1 vanes are or were previously installed. Configuration verification of installed blade type is necessary to determine applicability.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Pre-enhanced (standard) rotor stage-1 (R1) compressor blades - the affected component (Application section and Recommendations section)
- [no explicit part number]: Enhanced R1 blades (full airfoil shot-peened) - recommended replacement parts for improved damage tolerance (Page 4 - Recommendations and Planning Information)
- [no explicit part number]: Uniform spaced S0 and S1 vanes - configuration contributing to higher risk of R1 tip cracks (Application section and Background Discussion)

## Reference Documents
- TIL 1509: F-class Front End (R0, S0, and R1) Compressor Inspections - provides NDI schedule and operational/maintenance best practices for R1 tip rubs
- TIL 1638: F-class R0 and R1 Platform Ultrasonic Testing - scope eliminated when enhanced R1 blades are installed

## Tables Found Summary
- {"table_label": "Compliance Category Legend", "table_description": "Defines compliance categories M, C, A, S with descriptions", "useful_for_downstream": false, "reason": "Standard legend table, not operationally specific to this TIL"}
- {"table_label": "Timing Code Legend", "table_description": "Defines timing codes 1-6 with descriptions", "useful_for_downstream": false, "reason": "Standard legend table, not operationally specific to this TIL"}

## Source Snippets
- {"field": "purpose", "snippet": "To purpose of this TIL is to inform affected users of the risk of R1 tip cracks, or tip corner liberations and to provide recommendations to help improve unit availability and reliability."}
- {"field": "failure_consequences", "snippet": "The liberated R1 tip corners resulted in considerable distress to the downstream compressor section. Owing to the extent of distress, the compressor rotor required replacement."}
- {"field": "completion_criteria_text", "snippet": "This TIL can be considered complete when the above recommendations are incorporated into the site's maintenance planning practices, or when the full set of R1 blades are replaced."}
- {"field": "hardware_or_part_configuration_text", "snippet": "Enhanced R1 blades are full airfoil shot-peened and have a higher damage tolerance when compared to the pre-enhanced R1 blades."}
- {"field": "usage_counter_requirements_text", "snippet": "A light or moderate R1 tip rub may not manifest into an indication in the short term and it could take several start-stop cycles following the rub event before an indication is identified."}
- {"field": "risk_summary", "snippet": "Field data suggests that flared 7F and 9F units with pre-enhanced R1 blades with prior tip rubs, and current or previous operation with uniform spaced S0 and S1 vanes are at higher risk of experiencing R1 tip cracks."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "installing enhanced R1 blades would improve unit availability as TIL 1509 inspection scope is limited to an annual BI, and TIL 1638 inspection scope to perform R1 dovetail ultrasonic testing is eliminated."}

## PDF Context
- File Name: TIL 2297 - FLARED 7F & 9F PRE-ENHANCED COMPRESSOR R1 BLADE RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2297 - FLARED 7F & 9F PRE-ENHANCED COMPRESSOR R1 BLADE RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
