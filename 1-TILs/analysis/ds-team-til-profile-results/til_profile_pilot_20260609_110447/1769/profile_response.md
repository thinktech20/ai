# TIL Profile Review: 1769

| Field | Value |
| --- | --- |
| Requested TIL | 1769 |
| Matched TIL | TIL 1769 |
| Revision | Not provided |
| Title | F-CLASS AFT STATOR ROCKING INSPECTION |
| Publish Date | 2010-12-01 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | True |

## Purpose
This TIL outlines the inspection procedure to check for stator rocking on the aft stages (S14-S16) of the outlined F-class machines.

## Reason For Revision
Not provided

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: Not provided
- Coarse Outage Type: CI/HGPI/MI
- Maintenance Trigger Text: At First Opportunity (next shutdown) - Timing Code 2
- Completion Criteria: 100% TIL Completed as noted in TIL Compliance Record; all findings documented with pictures and submitted to GE Service Manager or Contract Performance Manager for disposition.

## Scope Of Work
- Borescope inspection of aft stages S14-S16 during CI, HGPI, or yearly monitoring when aft stators are NOT exposed (Procedure 1)
- Stator rocking check and visual inspection of stators and casing slots during HGPI or MI when CDC is removed and aft stators are exposed (Procedure 2)
- It should take one 12-hour shift to complete the aft stator rocking inspection

## Service Recommendation Line Items
- Inspect aft stator slots on all affected F-class units at the first available opportunity
- During planned CI and HGPI, perform thorough borescope inspection (BI) of aft stages S14-S16
- During major inspections or outages requiring CDC removal, perform stator rocking check and visual inspection of stators and casing slots
- During borescope inspection look for base protruding into airflow path, large circumferential gap at horizontal joint, protruding or missing shims, cracks and/or excessive wear (fretting) between square base platform and case
- When CDC is removed, measure opening circumferential drop at horizontal joint of stators in S14, S15, S16
- Check stator rocking by measuring radial drop (delta max) - push vanes in direction producing largest radial drop and record in stator rocking datasheet
- If rocking is excessive or wear found in lower half, remove stators and inspect bases for fretting, cracks and wear; inspect casing slot for wear into lower and upper rail
- If any significant component wear, stator rocking, or cracks are discovered, document with pictures and submit to GE Energy Services representative for engineering disposition

## Recommended Interval Or Trigger
- At first available opportunity (Timing Code 2 - next shutdown)
- During planned combustion inspections (CI) and hot gas path inspections (HGPI) - borescope inspection of S14-S16
- During major inspections or outages requiring CDC removal - stator rocking check and visual inspection
- Yearly monitoring borescope inspection if CDC is not removed

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: All 6FA+e, 7FA+, 7FA+e (flared and unflared), 7FB, 9FA+, 9FA+e (flared and unflared), and 9FB units
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Units that have not implemented a Package 4 or Package 5 enhanced compressor upgrade (which contains the enhanced aft stator modification)
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Units that have implemented a Package 4 or Package 5 enhanced compressor upgrade (which contains the enhanced aft stator modification) are excluded.
- Required Prior Modifications: None
- Prerequisite Outage or Inspection Context: Procedure 1 applies when CDC is not removed (CI, HGPI, yearly monitoring). Procedure 2 applies when CDC is removed during HGPI or Major Inspections and aft stators are exposed.

## SBOM Trigger Reason
Applicability depends on whether Package 4 or Package 5 enhanced compressor upgrade has been implemented, requiring installed-configuration verification.

## MLI Numbers
- None

## Parts Referenced
- None

## Reference Documents
- None

## Tables Found Summary
- {"table_label": "TIL Compliance Record - Installed Equipment", "table_description": "Compliance record form with fields for unit numbers, part description, part number, and MLI number (all blank/template)", "useful_for_downstream": false, "reason": "Template form with no populated data"}

## Source Snippets
- {"field": "purpose", "snippet": "This TIL outlines the inspection procedure to check for stator rocking on the aft stages (S14-S16) of the outlined F-class machines."}
- {"field": "failure_consequences", "snippet": "If the wear is significant enough it can lead to stator tip rubs, and may potentially lead to stator vane liberation."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "All 6FA+e, 7FA+, 7FA+e (flared and unflared), 7FB, 9FA+, 9FA+e (flared and unflared), and 9FB units that have not implemented a Package 4 or Package 5 enhanced compressor upgrade (which contains the enhanced aft stator modification)."}
- {"field": "service_recommendation_line_items", "snippet": "During planned combustion inspections (CI) and hot gas path inspections (HGPI), a thorough borescope inspection (BI) of the aft stages (S14-S16) area should be performed."}
- {"field": "scope_of_work", "snippet": "It should take one 12-hour shift to complete the aft stator rocking inspection."}
- {"field": "severity_signals", "snippet": "In most cases, the square base of the stator had worn to the point where the base was protruding into the airflow path"}

## PDF Context
- File Name: TIL 1769 - F-CLASS AFT STATOR ROCKING INSPECTION.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1769 - F-CLASS AFT STATOR ROCKING INSPECTION.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
