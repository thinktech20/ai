# TIL Profile Review: 2511

| Field | Value |
| --- | --- |
| Requested TIL | 2511 |
| Matched TIL | TIL 2511 |
| Revision | Not provided |
| Title | F.05 & HA COMPRESSOR-SECTION RETENTION-KEY IMPROVEMENTS |
| Publish Date | 2024-06-06 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
To inform affected users about: 1. The potential for keys retaining sub-assemblies such as stator vane segments, inducer, high pressure packing seal, aft-inducer seal, and/or casing treatment ring to overcome staked retention, which can result in object drops during casing lifts. 2. The availability of an improved key retention method, and the recommendation to install the improved key retention modification during a planned major inspection.

## Reason For Revision
Not provided

## Compliance And Triggering Context
- Compliance Category Code: S
- Compliance Category Text: Safety - Failure to comply with this TIL could result in personal injury. Compliance is mandated within a specific operating time.
- Recurring Indicator: Not provided
- Coarse Outage Type: Major Inspection
- Maintenance Trigger Text: Next scheduled major inspection when all compressor section upper-half casings will be removed.
- Completion Criteria: The TIL is considered as complete once the newly configured key retention modification is installed.

## Scope Of Work
- Machine threaded holes and counterbores on the UH compressor-section casings at the HJ to accept retention screws.
- Install new keys to retain stator-vanes, HPPS, AIS, inducer, and CT ring; torque retention screws to specification.
- Stake around the keys at 4x places to serve as secondary retention.

## Service Recommendation Line Items
- Apply the newly configured retention key modification at the next major inspection (MI) when all compressor section upper-half casings will be removed.
- The modification may optionally be applied at an earlier opportunity if all affected compressor section UH casings are removed prior to an MI.
- Prior to lifting any UH casing, take additional precautions and, if possible, inspect the retention keys for any potential abnormalities such as a displaced key using telescoping mirrors once the UH casing is separated.
- Contact regional GE Vernova representative to determine the specific components recommended to be modified on your gas turbine model.

## Recommended Interval Or Trigger
- Next Scheduled Outage (Timing Code 6)
- Next major inspection (MI) when all compressor section UH casings are removed
- Optionally at an earlier opportunity if all affected compressor section UH casings are removed prior to an MI

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: All 7F.04-200, 7F.05, 7HA.01, 7HA.02, 7HA.03, 9F.05-18, 9HA.01, and 9HA.02 gas turbines.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: AIS is installed only on HA.0x units. Inducer is installed only on HA.0x units with a double-wall compressor discharge casing. CT ring is installed only on 7HA.03 units.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: AIS, inducer, and CT ring are installed only on specific gas turbine models; contact GE Vernova representative to determine specific components recommended for modification on your model.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Requires removal of all compressor section upper-half casings; typically performed during a major inspection.

## SBOM Trigger Reason
Modification requires configuration-specific determination of which components (AIS, inducer, CT ring) are installed based on gas turbine model and casing configuration (e.g., double-wall compressor discharge casing on HA.0x units).

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Upgraded retention keys with flanged screws (new keys to retain stator-vanes, HPPS, AIS, inducer, and CT ring) (Scope of Work and Recommendations sections)
- [no explicit part number]: Retention screws (flanged screws) to be torqued to specification for improved key retention (Scope of Work item 2 and Recommendations section)

## Reference Documents
- PSSB 20210505A: Describes two reported incidents where stator vane retention keys fell out during UH casing lifts

## Tables Found Summary
- {"table_label": "Compliance Category Legend", "table_description": "Defines compliance categories M, C, A, and S with descriptions of required actions and consequences", "useful_for_downstream": false, "reason": "Standard legend table; compliance category S already captured in structured fields"}
- {"table_label": "Timing Code Legend", "table_description": "Defines timing codes 1-6 for TIL compliance timing", "useful_for_downstream": false, "reason": "Standard legend table; Timing Code 6 (Next Scheduled Outage) already captured"}

## Source Snippets
- {"field": "failure_consequences", "snippet": "If the retention stakes are not adequately applied, there is potential for keys and the sub-assemblies, such as stator vane segments, inducer, and seals to drop during UH casing lifts, which can lead to personnel injury."}
- {"field": "scope_of_work", "snippet": "Machine threaded holes and counterbores on the UH compressor-section casings at the HJ to accept retention screws."}
- {"field": "completion_criteria_text", "snippet": "The TIL is considered as complete once the newly configured key retention modification is installed."}
- {"field": "recommended_interval_or_trigger", "snippet": "It is recommended that the newly configured retention key modification be applied to the unit at the next major inspection (MI) when all the compressor section upper-half (UH) casings will be removed."}
- {"field": "hardware_or_part_configuration_text", "snippet": "AIS is installed only on HA.0x units. Inducer is installed only on HA.Ox units with a double-wall compressor discharge casing. CT ring is installed only on 7HA.03 units."}
- {"field": "service_recommendation_line_items", "snippet": "Prior to lifting any UH casing, GE Vernova recommends the site personnel to take additional precautions and, if possible, to inspect the retention keys for any potential abnormalities such as a displaced key."}

## PDF Context
- File Name: TIL 2511 - F.05 & HA COMPRESSOR-SECTION RETENTION-KEY IMPROVEMENTS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2511 - F.05 & HA COMPRESSOR-SECTION RETENTION-KEY IMPROVEMENTS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
