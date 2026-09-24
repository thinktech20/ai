# TIL Profile Review: 2167-R1

| Field | Value |
| --- | --- |
| Requested TIL | 2167-R1 |
| Matched TIL | TIL 2167-R1 |
| Revision | R1 |
| Title | 7F.05 VSV2 COMPRESSOR INSPECTIONS |
| Publish Date | 2020-06-04 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | False |

## Purpose
To inform 7F.05 users of front end compressor inspections to improve unit availability and reliability.

## Reason For Revision
To improve TIL language and clarity.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: The above borescope inspections are recurring until the below actions are completed.
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: During planned borescope inspections (recurring) and during planned major inspections or planned outages when the compressor is exposed.
- Completion Criteria: This TIL can be deemed complete if the vanes are tipped to increase the clearance or replaced with the VSV2s that have an increased tip clearance.

## Scope Of Work
- During planned BIs: Inspect 100% of the VSV2s for signs of tip loss or tip indications
- During planned BIs: Inspect 100% of the 2-3 T-Fairings for signs of severe rubs. Document the conditions of each T-Fairing so that rubs can be monitored over time.
- During planned major inspections or planned outages when the compressor is exposed: Inspect the condition of VSV2 tips and document any rubs or tip curl with photographs. Following this, it is recommended to tip the VSV2s to increase the radial clearance.
- During planned major inspections or planned outages when the compressor is exposed: Inspect the 2-3 T-Fairing flow path surface and edges for signs of high metal, burrs, or rubs. If high metal, burrs, or rubs are noted, document the condition of the T-Fairing's with pictures.

## Service Recommendation Line Items
- During planned borescope inspections, inspect 100% of VSV2s for evidence of tip loss or tip indications.
- During planned borescope inspections, inspect 100% of the 2-3 T-Fairings for rubs and document conditions so rubs can be monitored over time.
- Contact GE representative with inspection results for evaluation and disposition by GE engineering.
- During planned major inspections or outages when compressor is exposed, inspect VSV2 tips and document rubs or tip curl with photographs.
- Tip the VSV2s to increase radial clearance during major inspections (contact GE representative for guidance on tipping).
- During major inspections, inspect 2-3 T-Fairing flow path surface and edges for high metal, burrs, or rubs; document with pictures if found.
- Post-tipping NDT required: FPI recommended; red dye penetrant acceptable if FPI not available.

## Recommended Interval Or Trigger
- Borescope inspections: recurring at each planned BI until corrective action is completed
- Major inspections or planned outages when compressor is exposed: tip VSV2s or replace with increased tip clearance VSV2s
- Annual inspections of VSV2 and 2-3 TF can be performed during the recommended inspection in TIL 2212

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: Gas turbines with 7F.05 compressors.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: 7F.05 compressor with 14 stage compressor, IGVs, three stages of variable stator vanes (VSVs), and two stages of T-Fairings (1-2 T-Fairing and 2-3 T-Fairing).
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Not provided
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: The corrective actions (tipping or replacing the VSV2s) in this TIL are independent of the corrective actions recommended in TIL 2212.

## SBOM Trigger Reason
Not provided

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: VSV2 (Stage 2 Variable Stator Vane) - subject of inspection for tip loss and tipping to increase radial clearance (Recommendations and Scope of Work sections)
- [no explicit part number]: 2-3 T-Fairing - removable hardware forming rotor flowpath between stage 2 and stage 3 compressor blades, inspected for rubs, high metal, and burrs (Recommendations and Scope of Work sections)

## Reference Documents
- TIL 2212: Annual inspections of VSV2 and 2-3 TF can be performed during the recommended inspection in TIL 2212. Corrective actions in TIL 2167 are independent of TIL 2212.

## Tables Found Summary
- {"table_label": "Compliance Category Definitions", "table_description": "Defines compliance categories C, A, and S with their associated risk descriptions.", "useful_for_downstream": false, "reason": "Standard legend table, does not contain unit-specific operational data."}
- {"table_label": "Timing Code Definitions", "table_description": "Defines timing codes 1 through 6 with their associated action timing.", "useful_for_downstream": false, "reason": "Standard legend table; Timing Code 6 = Next Scheduled Outage is the only relevant item and is captured elsewhere."}

## Source Snippets
- {"field": "recurring_indicator_if_found", "snippet": "The above borescope inspections are recurring until the below actions are completed."}
- {"field": "completion_criteria_text", "snippet": "This TIL can be deemed complete if the vanes are tipped to increase the clearance or replaced with the VSV2s that have an increased tip clearance."}
- {"field": "purpose", "snippet": "To inform 7F.05 users of front end compressor inspections to improve unit availability and reliability."}
- {"field": "service_recommendation_line_items", "snippet": "it is recommended to tip the VSV2s to increase the radial clearance. Please contact your GE representative for further guidance on this tipping."}
- {"field": "risk_summary", "snippet": "This clearance increase is expected to have a negligible impact on compressor flow, efficiency, and stall margin."}
- {"field": "reference_documents", "snippet": "The annual inspections of VSV2 and 2-3 TF can be performed during the recommended inspection in TIL 2212."}
- {"field": "parts_referenced", "snippet": "A competent and qualified non-destructive testing NDT) inspector for post tipping NDT. For this work, NDT is considered a penetrant inspection. Flourescent penetrant inspection (FPI) is recommended."}

## PDF Context
- File Name: TIL 2167-R1 - 7F.05 VSV2 COMPRESSOR INSPECTIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2167-R1 - 7F.05 VSV2 COMPRESSOR INSPECTIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
