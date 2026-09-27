# TIL Profile Review: 1850-R3

| Field | Value |
| --- | --- |
| Requested TIL | 1850-R3 |
| Matched TIL | TIL 1850-R3 |
| Revision | R3 |
| Title | F-CLASS COMPRESSOR MECHANICALLY-ATTACHED SHROUD S17 INSPECTION |
| Publish Date | 2024-01-17 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.91 |
| SBOM Dependency Flag | True |

## Purpose
This TIL advises operators to monitor the mechanically-attached shroud compressor S17 configurations and provides recommendations for mitigating any observed distress.

## Reason For Revision
This revision is intended to communicate the availability of new configuration Gen-V S17 assembly and availability to modify earlier mechanically-attached shroud S17 generations to Gen-V S17 in GE designated service shop.

## Compliance And Triggering Context
- Compliance Category Code: M
- Compliance Category Text: Maintenance - Identifies maintenance guidelines or best practices for reliable equipment operation.
- Recurring Indicator: Yes - annual borescope and inspection at each exposure until Gen-V installed across entire stage
- Coarse Outage Type: MI
- Maintenance Trigger Text: At First Exposure of Component (Timing Code 4)
- Completion Criteria: This TIL can be marked completed when the latest Gen-V S17 configuration has been installed across the entire stage.

## Scope Of Work
- Standard manpower for borescope inspection
- Manpower if replacement of S17 segment is required (these support personnel will already be onsite during MI): Two GE field technicians, One GE Field TA

## Service Recommendation Line Items
- Perform annual borescope inspection per GER 3620; inspect 100% of shrouded S17 for signs of distress when S17s are NOT exposed (Inspection Procedure 1)
- Perform borescope inspection during scheduled CI or HGPI when CDC is not removed
- During MI or HGPI with CDC removed (Inspection Procedure 2): visually inspect for bushing wear, tenon damage, shroud hole ovalization, and wear between vane tips and shroud
- S17s in the lower half should be either removed or inspected by borescope during MI
- If significant distress, cracks, detached bushings, or ovalized shroud hole are found, document with pictures and submit to GE Services representative for engineering disposition
- If wear or damage is observed, order and install the latest Gen-V S17 configuration as a set for durability improvement
- It is acceptable to replace only the damaged segment of S17 with the latest S17 segment (Gen-V configuration)
- GE offers refurbishment services to modify earlier mechanically-attached shroud S17 configurations to the latest Gen-V configuration based on approved repair instruction

## Recommended Interval Or Trigger
- Annual borescope inspection per GER 3620
- Borescope inspection during scheduled CI or HGPI when CDC is not removed
- Visual inspection during MI or HGPI when CDC is removed (S17s exposed)
- At first exposure of component (Timing Code 4)

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: All 7F.03, 7F.04, 7FB, and 9F.05 (9FB) units with mechanically-attached shroud S17 segments.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Applicable to Gen-IV and earlier mechanically-attached shroud S17 configurations including: welded bolt configuration (introduced 2004), staked bolt configuration (introduced 2008), staked bolt with changed bushing material Gen-IV (introduced 2016). Gen-V S17 assembly (2023) with self-mated cobalt-chromium based alloy bushing and shroud is the replacement configuration.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Units already equipped with Gen-V S17 configuration across the entire stage are considered complete.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Inspection Procedure 1 applies when S17s are NOT exposed (borescope). Inspection Procedure 2 applies during MI or HGPI when CDC is removed and S17s are exposed.

## SBOM Trigger Reason
TIL requires identification of installed S17 configuration generation (welded bolt 2004, staked bolt 2008, Gen-IV 2016, or Gen-V 2023) to determine applicability and completion status. Configuration-dependent hardware verification is required.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Gen-V S17 assembly - latest configuration with both bushing and shroud made of the same cobalt-chromium based alloy, available to order as replacement (Recommendations section, page 5-6)
- [no explicit part number]: S17 mechanically-attached shroud segment - bolt, bushing, washer, tenon, shroud components (Background Discussion, page 2)
- [no explicit part number]: Counterbore plugs referenced in TILs 1315-2R1 and 1478-2 for inner barrel counterbore cavity (Background Discussion, page 2)

## Reference Documents
- TIL 1315-2R1: Recommends installing counterbore plugs and modifying control system to reduce aft end distress
- TIL 1478-2: Recommends installing counterbore plugs and modifying control system to reduce aft end distress
- GER 3620: Annual borescope inspection recommended per GER 3620

## Tables Found Summary
- {"table_label": "Compliance Category Legend", "table_description": "Defines M, C, A, S compliance categories and their implications", "useful_for_downstream": false, "reason": "Standard legend table, not operationally specific to this TIL"}
- {"table_label": "Timing Code Legend", "table_description": "Defines timing codes 1-6 for TIL compliance timing", "useful_for_downstream": true, "reason": "Confirms Timing Code 4 = At First Exposure of Component"}

## Source Snippets
- {"field": "completion_criteria_text", "snippet": "This TIL can be marked completed when the latest Gen-V S17 configuration has been installed across the entire stage."}
- {"field": "failure_consequences", "snippet": "Excessive wear between the vane and bushing may cause S17 tip to detach from the shroud, and the S17 will act as a cantilever, increasing the stress on the vane. Over time, this condition poses a risk, possibly resulting in secondary damages to the adjacent airfoils and possible migration forward into the R17 wheel."}
- {"field": "service_recommendation_line_items", "snippet": "If wear or damage is observed during the inspection above, it is recommended to order and install the latest Gen-V S17 configuration as a set for durability improvement."}
- {"field": "hardware_or_part_configuration_text", "snippet": "In 2023, a new configuration Gen-V S17 assembly with both bushing and shroud made of the same cobalt-chromium based alloy has been developed and is now available to order."}
- {"field": "reason_for_revision", "snippet": "This revision is intended to communicate the availability of new configuration Gen-V S17 assembly and availability to modify earlier mechanically-attached shroud S17 generations to Gen-V S17 in GE designated service shop."}
- {"field": "scope_of_work", "snippet": "Standard manpower for borescope inspection. Manpower if replacement of S17 segment is required (these support personnel will already be onsite during MI): Two GE field technicians, One GE Field TA"}

## PDF Context
- File Name: TIL 1850-R3 - F-CLASS COMPRESSOR MECHNICALLY-ATTACHED SHROUD S17 INSPECTION.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1850-R3 - F-CLASS COMPRESSOR MECHNICALLY-ATTACHED SHROUD S17 INSPECTION.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
