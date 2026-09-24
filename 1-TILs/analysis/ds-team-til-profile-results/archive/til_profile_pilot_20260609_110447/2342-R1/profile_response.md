# TIL Profile Review: 2342-R1

| Field | Value |
| --- | --- |
| Requested TIL | 2342-R1 |
| Matched TIL | TIL 2342 |
| Revision | R1 |
| Title | EXHAUST FRAME FLEX SEALS |
| Publish Date | 2022-09-01 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
To inform users of inspection recommendations for the flex seals installed

## Reason For Revision
Add 9F units to the AUL

## Compliance And Triggering Context
- Compliance Category Code: M
- Compliance Category Text: Identifies maintenance guidelines or best practices for reliable equipment operation.
- Recurring Indicator: Yes - applicable as long as GEN0, GEN1, or GEN2 flex seal configuration is installed; yearly planned borescope inspections
- Coarse Outage Type: Borescope Inspection
- Maintenance Trigger Text: At First Exposure of Component (Timing Code 4); yearly planned borescope inspections
- Completion Criteria: Inspection of flex seals completed during yearly planned borescope inspection with findings reported to engineering if indications observed

## Scope Of Work
- Inspect the flex seals during yearly planned borescope inspections

## Service Recommendation Line Items
- Inspect units with GEN0, GEN1, or GEN2 flex seal configuration during yearly planned borescope inspections
- If inspecting through the hot gas path section, note that limited areas of the lower section can be captured
- Report signs of wear at the exhaust frame pipe/ring or flange side to engineering for disposition
- Report cracks, misalignment, bending, disengagement, and/or liberation to engineering for disposition
- Monitor the unit for 3AO elevated wheel space temperatures and exhaust frame blower alarms; report any unusual observations to engineering for disposition

## Recommended Interval Or Trigger
- Yearly planned borescope inspections
- At First Exposure of Component (Timing Code 4)

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: 7F and 9F units with GEN0, GEN1, or GEN2 flex seal configuration installed
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: GEN0: SS410 Flex seal; GEN1: SS347 Flex seal; GEN2: SS410 coated Flex seal
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: This TIL is applicable as long as GEN0, GEN1, or GEN2 flex seal configuration is installed
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Yearly planned borescope inspection; if inspecting through the hot gas path section, limited areas of the lower section can be captured

## SBOM Trigger Reason
TIL applicability depends on which flex seal configuration (GEN0, GEN1, or GEN2) is installed, requiring installed-configuration verification

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: GEN0 - SS410 Flex seal (Page 3, Figure 2 caption)
- [no explicit part number]: GEN1 - SS347 Flex seal (Page 3, Figure 2 caption)
- [no explicit part number]: GEN2 - SS410 coated Flex seal (Page 3, Figure 2 caption)

## Reference Documents
- None

## Tables Found Summary
- {"table_label": "Compliance Category Legend", "table_description": "Defines compliance categories M, C, A, S with descriptions", "useful_for_downstream": false, "reason": "Standard legend table, not specific to this TIL's engineering content"}
- {"table_label": "Timing Code Legend", "table_description": "Defines timing codes 1-6 with descriptions", "useful_for_downstream": false, "reason": "Standard legend table, not specific to this TIL's engineering content"}

## Source Snippets
- {"field": "purpose", "snippet": "To inform users of inspection recommendations for the flex seals installed"}
- {"field": "scope_of_work", "snippet": "Inspect the flex seals during yearly planned borescope inspections"}
- {"field": "service_recommendation_line_items", "snippet": "GE recommends inspecting the units in operation that have installed the GEN0, GEN1, or GEN2 flex seal configuration during yearly planned borescope inspections."}
- {"field": "severity_signals", "snippet": "Historically, flex seals have in some cases experienced wear, cracking, misalignment, bending, disengagement, and/or liberation."}
- {"field": "recurring_indicator_if_found", "snippet": "This TIL is applicable as long as GEN0, GEN1, or GEN2 flex seal configuration is installed."}
- {"field": "service_recommendation_line_items", "snippet": "It is also recommended to monitor the unit for 3AO elevated wheel space temperatures and exhaust frame blower alarms; report any unusual observations to engineering for disposition."}

## PDF Context
- File Name: TIL 2342-R1 - EXHAUST FRAME FLEX SEALS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2342-R1 - EXHAUST FRAME FLEX SEALS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
