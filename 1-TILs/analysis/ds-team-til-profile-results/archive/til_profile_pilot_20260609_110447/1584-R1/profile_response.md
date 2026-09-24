# TIL Profile Review: 1584-R1

| Field | Value |
| --- | --- |
| Requested TIL | 1584-R1 |
| Matched TIL | TIL 1584-R1 |
| Revision | R1 |
| Title | 7FA TURBINE SHELL INLET BLEED HEAT (IBH) EXTRACTION PIPE WELD CRACKING |
| Publish Date | 2011-03-08 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
To recommend inspection of 7FA turbine shell IBH extraction port cover flange pipes for potential weld cracking, and to specify corrective action if required.

## Reason For Revision
The purpose of revision is to provide recommended inspection intervals and update the affected unit list and application to include 7F, 7FA and 7FA+.

## Compliance And Triggering Context
- Compliance Category Code: S
- Compliance Category Text: Safety - Failure to comply with this TIL could result in personal injury. Compliance is mandated within a specific operating time.
- Recurring Indicator: Yes - Re-inspection at every HGPI/Major inspection, or at a convenient planned outage
- Coarse Outage Type: HGPI
- Maintenance Trigger Text: First inspection at first HGPI or next planned shutdown if beyond first HGPI. Re-inspection at every HGPI/Major inspection or convenient planned outage.
- Completion Criteria: Dye penetrant inspection completed by certified NDT level II inspector per SNT-TC-1A with no indications, or corrective action (repair or replacement) completed and re-inspected.

## Scope Of Work
- Dye penetrant inspection of the IBH extraction port cover flange pipe weld joint by a certified level II NDT inspector
- If cracks found: Option 1 - Grind off cracked section and perform repair welding per GE weld specification P8A-AG3 or equivalent
- If cracks found: Option 2 - Replace the flange with a new part and new flange gasket, install per MLI-0705 assembly drawing
- Re-inspect repaired, replaced, and original IBH weld joints per recommended schedule

## Service Recommendation Line Items
- Perform dye penetrant inspection of IBH extraction port cover flange pipe weld joint at first HGPI; if beyond first HGPI, then at next planned shutdown opportunity
- Re-inspect at every HGPI/Major inspection, or at a convenient planned outage
- If cracks found, perform repair by grinding off cracked section and weld repair per P8A-AG3 or equivalent, OR replace flange with new part per MLI-0705
- A new flange gasket is required if replacement option is chosen
- Re-inspect repaired, replaced, and original IBH weld joints per the same schedule
- All personnel must remain outside the gas turbine compartment while the gas turbine is fired and running, unless absolutely necessary

## Recommended Interval Or Trigger
- First inspection at first Hot Gas Path Inspection (HGPI); if beyond first HGPI, then at next planned shutdown opportunity
- Re-inspection at every HGPI/Major inspection, or at a convenient planned outage

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: All 7F, 7FA, 7FA+ and 7FA+e Gas Turbines.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Turbine shell IBH extraction port cover flange pipes - Part affected: 213C1469G001
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Not provided
- Required Prior Modifications: TIL 1584
- Prerequisite Outage or Inspection Context: Unit must be shut down and all safety requirements implemented prior to inspection. Estimated 2 hours for NDT inspection after shutdown. 1 shift to remove flanges and repair weld.

## SBOM Trigger Reason
Specific part number 213C1469G001 referenced as affected part; MLI-0705 assembly drawing referenced for replacement installation requiring configuration verification.

## MLI Numbers
- MLI-0705: Assembly drawing for installation of replacement flange (Option 2 corrective action)

## Parts Referenced
- 213C1469G001 [FPI]: Part affected - IBH extraction port cover flange pipe on turbine shell (Page 3 - Planning Information / Parts section)
- [no explicit part number]: New flange gasket required if replacement option is chosen (Page 3 - Recommendations Option 2)

## Reference Documents
- TIL 1584: Previous modification / original revision of this TIL
- P8A-AG3: GE weld specification for repair welding of cracked section
- SNT-TC-1A: Certification standard for NDT level II inspectors performing dye penetrant inspection

## Tables Found Summary
- {"table_label": "Compliance Category Table", "table_description": "Defines compliance categories (O, M, C, A, S) and timing codes (1-7)", "useful_for_downstream": false, "reason": "Standard legend table present in all TILs; does not contain unit-specific operational data"}
- {"table_label": "Installed Equipment Table", "table_description": "Blank compliance record table with columns for Unit Numbers, Part Description, Part Number, MLI Number", "useful_for_downstream": false, "reason": "Template table with no pre-filled data; intended for customer completion"}

## Source Snippets
- {"field": "purpose", "snippet": "To recommend inspection of 7FA turbine shell IBH extraction port cover flange pipes for potential weld cracking, and to specify corrective action if required."}
- {"field": "failure_consequences", "snippet": "The crack initiated at the pipe to cover flange weld as shown in Figure 2, and resulted in substantial hot air leakage."}
- {"field": "safety_or_damage_language_found", "snippet": "This type of leakage can cause elevated turbine compartment temperatures that could lead to a forced outage condition, and are also a safety concern."}
- {"field": "service_recommendation_line_items", "snippet": "GE recommends dye penetrant inspection of the weld joint by a certified level II NDT inspector"}
- {"field": "recommended_interval_or_trigger", "snippet": "First inspection at the first Hot Gas Path inspection (HGPI). If beyond first HGPI, then at the next planned shutdown opportunity."}
- {"field": "scope_of_work", "snippet": "Estimated time to complete: 2 hours for NDT inspection, after unit is shut down and all safety requirements are implemented. 1 Shift to remove the flanges and repair the weld."}
- {"field": "mli_numbers", "snippet": "Replace the flange with a new part. A new flange gasket will also be required. Install per the MLI-0705 assembly drawing."}

## PDF Context
- File Name: TIL 1584-R1 - 7FA TURBINE SHELL INLET BLEED HEAT (IBH) EXTRACTION PIPE WELD CRACKING.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1584-R1 - 7FA TURBINE SHELL INLET BLEED HEAT (IBH) EXTRACTION PIPE WELD CRACKING.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
