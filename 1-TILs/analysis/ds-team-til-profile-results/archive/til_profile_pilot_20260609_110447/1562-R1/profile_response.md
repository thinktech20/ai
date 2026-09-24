# TIL Profile Review: 1562-R1

| Field | Value |
| --- | --- |
| Requested TIL | 1562-R1 |
| Matched TIL | TIL 1562-R1 |
| Revision | R1 |
| Title | HEAVY-DUTY GAS TURBINE SHIM MIGRATION AND LOSS |
| Publish Date | 2009-08-20 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | True |

## Purpose
To inform users of the need to monitor the condition of compressor shims and corrective actions necessary to mitigate the risks of migrating shims.

## Reason For Revision
Revised to add additional gas turbine classes and to update recommendations.

## Compliance And Triggering Context
- Compliance Category Code: M
- Compliance Category Text: Maintenance - Identifies maintenance guidelines or best practices for reliable equipment operation.
- Recurring Indicator: Yes - annual borescope inspections and at regular maintenance outages (CI & HGPI)
- Coarse Outage Type: MI
- Maintenance Trigger Text: Annual borescope inspections, regular maintenance outages (CI & HGPI), and additional monitoring inspections based on findings. Front-end shims >50% protrusion require disposition prior to restart. Continued front-end shim movement requires corrective action as soon as possible.
- Completion Criteria: Shim pinning modification implemented on all compressor stages at next MI or compressor maintenance outage with rotor exposed; ongoing borescope monitoring per GER 3620 with corrective action applied for any migrating shims.

## Scope Of Work
- Borescope inspections requiring approximately 8-12 hours to complete, completed annually and at regular maintenance outages (CI & HGPI) as outlined in GER3620
- Additional monitoring inspections may be required based on findings
- Implementation of shim pinning modification during scheduled outages in which the compressor casing has been removed
- Removal of stators varies greatly; worst-case requires destructive removal from casing
- Once stators removed, modification may occupy two blade technicians for four shifts to complete

## Service Recommendation Line Items
- Continue normal borescope and visual inspections per GER 3620, noting the condition of all shims
- Inspect first four stages of B-class/E-class machines (first eight stages for 9E) and first five stages of F-class machines for shims located between stator segments, 60 degrees above and below left and right horizontal joints
- Report any shim anomalies to local GE Service Manager or Contract Performance Manager for documentation and recommendations
- For front-end segmented-stator shims with LESS than 50% height protruding: monitor movement based on historical knowledge of the shim (low-to-moderate risk)
- For front-end shims with GREATER than 50% height protrusion: require disposition prior to restart of the unit
- For continued movement of front-end shims: corrective action should take place as soon as possible to avoid liberation
- Aft stage shim migration is considered low-risk and can typically be addressed at the scheduled major inspection interval
- Remove protruding shim if it can be done without risk of damaging neighboring blades/vanes; operating with shim removed is acceptable until next planned casing removal outage
- If removal proves difficult, grind shim flush with flow path without risk of damaging neighboring blades/vanes; then inspect for further movement after 25 starts
- Implement shim pinning modification at next major inspection (MI) interval or next compressor maintenance outage in which the rotor is exposed
- Replacement shims should be of no less than 80 mils thickness for robust retention
- Order shim pinning modification kit through local GE Service Manager or Contract Performance Manager; allow 10 weeks for parts delivery
- Do not use alternative concepts not approved by GE such as capturing shims between adjoined stators, as this may subject vane base to excessive forces beyond design intent

## Recommended Interval Or Trigger
- Annual borescope inspection
- At regular maintenance outages (CI & HGPI) per GER 3620
- After grinding: inspect for further movement after 25 starts
- Shim modification at next MI interval or next compressor maintenance outage with rotor exposed
- Front-end shims >50% protrusion: prior to restart
- Aft stage shim migration: at scheduled major inspection interval

## Usage Counter Requirements
- Counters To Check or Consider: starts
- Requirements Text: After grinding a shim flush, inspect for further movement after 25 starts.

## Applicability And Exclusions
- Frame or Model Applicability: All B, C, E, F, and H-Class gas turbines
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Stages 0-4 on 7H machine, 1-4 on 9H machine, and 1-2 on 6C machine do not have shims (these stages contain Variable Guide Vanes and do not use shims). First four stages of B-class/E-class (first eight stages for 9E), first five stages of F-class may have shims between stator segments 60 degrees above and below left and right horizontal joints.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Stages 0-4 on 7H machine, 1-4 on 9H machine, and 1-2 on 6C machine do not have shims (VGV stages).
- Required Prior Modifications: None
- Prerequisite Outage or Inspection Context: Shim modification requires scheduled outage with compressor casing removed and rotor exposed.

## SBOM Trigger Reason
Shim pinning modification kit containing shims and pins must be ordered specific to unit configuration; replacement shim thickness requirement (no less than 80 mils); configuration-dependent shim locations vary by frame class and stage.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Shim pinning modification kit containing necessary shims and pins to complete the job; must be ordered through local GE Service Manager or Contract Performance Manager; allow 10 weeks for parts delivery (Page 4, Parts section)
- [no explicit part number]: Replacement shims of no less than 80 mils thickness for robust retention (Page 3, Modification section)
- [no explicit part number]: Drive pins used to align and mechanically attach each shim to an adjacent stator base/segment (Page 3, Modification section)

## Reference Documents
- GER 3620: Referenced for normal borescope and visual inspection guidelines and maintenance outage schedule (CI & HGPI)

## Tables Found Summary
- {"table_label": "TIL Compliance Record - Installed Equipment", "table_description": "Compliance record table with fields for Unit Numbers, Part Description, Part Number, and MLI Number (all blank/template)", "useful_for_downstream": false, "reason": "Template form with no populated data"}

## Source Snippets
- {"field": "purpose", "snippet": "To inform users of the need to monitor the condition of compressor shims and corrective actions necessary to mitigate the risks of migrating shims."}
- {"field": "severity_signals", "snippet": "Shim migration poses a risk of shim liberation, which could lead to compressor damage. These risks are greatest for front stages due to shim size and the number of stages that could be impacted by a liberated shim."}
- {"field": "recommended_interval_or_trigger", "snippet": "Borescope inspections, requiring approximately 8-12 hours to complete, should be completed annually and at regular maintenance outages (CI & HGPI) as outlined in GER3620."}
- {"field": "service_recommendation_line_items", "snippet": "Front-end shims with GREATER than 50% height protrusion pose a greater risk for liberation, regardless of their history, and require disposition prior to restart of the unit."}
- {"field": "service_recommendation_line_items", "snippet": "If the shim is accessible for grinding, it is recommended to do so and then inspect for further movement after 25 starts."}
- {"field": "configuration_dependent", "snippet": "Note that stages 0-4 on the 7H machine, 1-4 on the 9H machine, and 1-2 on the 6C machine do not have shims. These stages contain Variable Guide Vanes (VGV) and do not use shims."}
- {"field": "parts_referenced", "snippet": "A kit containing the necessary shims and pins to complete the job must be ordered for the modification. Contact your local GE Service Manager or Contract Performance Manager for assistance. Allow 10 weeks for parts delivery."}
- {"field": "service_recommendation_line_items", "snippet": "Replacement shims should be of no less than 80 mils thickness for robust retention."}
- {"field": "failure_consequences", "snippet": "Alternative concepts not approved by GE, such as capturing shims between adjoined stators, may subject the base of the vane to excessive forces beyond design intent and add new risks, potentially resulting in component failure."}
- {"field": "coarse_outage_type", "snippet": "GE recommends the shim modification be implemented at the next major inspection (MI) interval or the next compressor maintenance outage in which the rotor is exposed."}

## PDF Context
- File Name: TIL 1562-R1 - HEAVY DUTY GAS TURBINE SHIM MIGRATION AND LOSS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1562-R1 - HEAVY DUTY GAS TURBINE SHIM MIGRATION AND LOSS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
