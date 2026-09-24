# TIL Profile Review: 1615-R1

| Field | Value |
| --- | --- |
| Requested TIL | 1615-R1 |
| Matched TIL | TIL 1615-R1 |
| Revision | R1 |
| Title | RO COMPRESSOR BLADE AXIAL RETENTION (STAKING) ALTERNATIVES |
| Publish Date | 2016-05-17 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | False |

## Purpose
To inform operators of the limitations of traditional means of axial retention (peening/staking) for compressor stage 0 rotor blades (ROs) resulting from successive R0 change-outs, and to notify users of a recommended wheel modification to apply when the traditional means of retention is no longer available. This alternative method uses replacement inserts as a staking medium that has no limitation on the number of times it can be replaced.

## Reason For Revision
To update the 7F and 9F casing lifting and removal requirements.

## Compliance And Triggering Context
- Compliance Category Code: M
- Compliance Category Text: Maintenance - Identifies maintenance guidelines or best practices for reliable equipment operation.
- Recurring Indicator: Not provided
- Coarse Outage Type: At Scheduled Component Part Repair or Replacement
- Maintenance Trigger Text: Third or greater replacement of the R0 blades, when traditional staking locations on the Forward Stub Shaft are exhausted.
- Completion Criteria: This TIL is considered complete when the biscuit modification has been installed.

## Scope Of Work
- For 6F units: Removal of the UH inlet bellmouth is required
- For 7F and 9F units: The UH of the inlet bellmouth must be jacked ~18" off the horizontal joint or may be removed
- Machining of FSS R0 dovetail slots (1x to 32x depending on scope) for the staking inserts
- R0 removal/installation and staking performed by blade technicians from a GE Service Center
- Estimated duration is 3-4 shifts
- Two milling technicians from GE certified repair shop per shift
- One NDT technician needed per shift
- One Field Engineer and scaffolding crew (three craft laborers) needed
- Turning gear/rotating fixture operator (dedicated person) needed

## Service Recommendation Line Items
- Apply replacement staking insert modification to any operator planning to change R0 blades for the third or greater time, if the modification has not previously been applied
- Modification should be performed in conjunction with the planned R0 change-out, or at a suitable maintenance opportunity preceding this
- Depending on scope and unit conditions, all blades in the stage may need to be removed for tooling access
- Do not use pressure face staking marks or blade platform flow path surface staking as alternative staking locations - these are no longer recommended
- Contact GE Services representative to initiate the CM&U process for R0 wheel modification

## Recommended Interval Or Trigger
- At Scheduled Component Part Repair or Replacement (Timing Code 5)
- Third or greater R0 blade replacement

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: All commissioned F-class gas turbines (6F, 7F, 9F)
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Compressor stage 0 rotor blades (R0), Forward Stub Shaft (FSS), R0 dovetail slots, replaceable staking inserts
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Modification is usually needed on the third or greater replacement of the R0 blades; units that have not yet exhausted traditional staking locations may not require this modification.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Modification should be performed in conjunction with the planned R0 change-out, or at a suitable maintenance opportunity preceding this. For 7F and 9F units, inlet bellmouth must be jacked ~18" or removed. For 6F units, inlet bellmouth must be removed.

## SBOM Trigger Reason
Not provided

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: Replaceable staking inserts installed in wheel slots for R0 axial retention - contact local GE Service Representative for parts (Page 4, Parts section)
- [no explicit part number]: Controlled milling machinery and special milling fixtures required for accurate drilling of pockets; dual-staking tool for proper staking geometry and placement - provided by GE Service Center technicians (Page 4, Special Tooling section)

## Reference Documents
- None

## Tables Found Summary
- {"table_label": "Compliance Category Legend", "table_description": "Defines M, C, A, S compliance categories", "useful_for_downstream": false, "reason": "Standard legend table, does not contain unit-specific operational data"}
- {"table_label": "Timing Code Legend", "table_description": "Defines timing codes 1-6 for TIL compliance", "useful_for_downstream": false, "reason": "Standard legend table"}

## Source Snippets
- {"field": "purpose", "snippet": "To inform operators of the limitations of traditional means of axial retention (peening/staking) for compressor stage 0 rotor blades (ROs) resulting from successive R0 change-outs"}
- {"field": "completion_criteria_text", "snippet": "This TIL is considered complete when the biscuit modification has been installed."}
- {"field": "service_recommendation_line_items", "snippet": "GE recommends this modification to any operator planning to change RO blades for the third or greater time, if the modification has not previously been applied."}
- {"field": "scope_of_work", "snippet": "For 7F and 9F units: The UH of the inlet bellmouth must be jacked ~ 18\" off the horizontal joint or may be removed."}
- {"field": "configuration_summary", "snippet": "if staking locations are exhausted from all 32 R0 blades, the need to replace a single R0 blade may warrant removal of all 32 such that the modification can be conducted on the entire wheel."}
- {"field": "reason_for_revision", "snippet": "To update the 7F and 9F casing lifting and removal requirements."}

## PDF Context
- File Name: TIL 1615-R1 - R0 COMPRESSOR BLADE AXIAL RETENTION (STAKING) ALTERNATIVES.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1615-R1 - R0 COMPRESSOR BLADE AXIAL RETENTION (STAKING) ALTERNATIVES.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
