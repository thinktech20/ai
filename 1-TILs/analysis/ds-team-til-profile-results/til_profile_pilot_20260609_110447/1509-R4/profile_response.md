# TIL Profile Review: 1509-R4

| Field | Value |
| --- | --- |
| Requested TIL | 1509-R4 |
| Matched TIL | TIL 1509 |
| Revision | R4 |
| Title | F-CLASS FRONT END (R0, S0, AND R1) COMPRESSOR INSPECTIONS |
| Publish Date | 2020-09-23 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.93 |
| SBOM Dependency Flag | True |

## Purpose
To provide compressor front-end (R0, S0, R1) inspection recommendations to help improve unit availability and reliability.

## Reason For Revision
To update the criteria that warrants R1 blade tip non-destructive inspections, to recommend performing the described non-destructive inspections during major inspections, and to update TIL language for improved clarity.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Compliance Required - Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: Yes - annual recurring inspections and NDI at specified start intervals
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: Annual visual/borescope inspections; NDI triggered by actual fired starts milestones (50, 25, 100 starts), rub findings, corrosive environment, or major inspection exposure
- Completion Criteria: If R0 LE root cracks, R0/R1 tip indications, or S0 TE cracks exist and are confirmed by NDI, do not restart the unit. Contact GE Gas Power Services representative for evaluation.

## Scope Of Work
- Visual inspection of R0 LE root, R0 and R1 tip, and S0 TE
- Non-destructive inspection (NDI) of R0 LE root
- NDI of R0 and R1 tip
- NDI of S0 TE
- Two hours to complete visual inspection after unit shutdown and completion of all safety requirements
- One 12-hour shift to complete NDI of R0 roots after unit shutdown and completion of all safety requirements
- Three 12-hour shifts to complete NDI of R0 and R1 blade tips after unit shutdown and completion of all safety requirements
- Two 12-hour shifts to complete NDI of S0 TE after unit shutdown and completion of all safety requirements

## Service Recommendation Line Items
- Perform annual visual/borescope inspection of R0 LE root, R0 and R1 tips, and S0 TE for all compressor configurations
- For standard (non-enhanced) 7F/9F: Perform annual R0 root NDI, annual R0 tip NDI (if prior rubs), annual R1 tip NDI (if conditions met), annual S0 TE NDI (flared only)
- For enhanced compressor package 2 (7F/9F): R0 root and R0 tip NDI not required; annual R1 tip NDI and S0 TE NDI
- For enhanced compressor package 2+, 3, 4 (7F/9F): Only annual R1 tip NDI required
- For enhanced compressor package 5 (7F/9F): Only annual visual/borescope required
- For standard (non-enhanced) 6F: Perform R0 root NDI, R0 tip NDI, R1 tip NDI, and S0 TE NDI at major inspection (MI)
- Perform R0 LE root NDI after first 50 actual fired starts, repeat after additional 25 starts, then annual per table
- If no rub indications on R0/R1 tips after 100 starts, continue visual monitoring; if rubs identified, NDI at first discovery then at 25, 50, and 100 starts
- If rolled-over metal, burrs, cracks, or tip loss noted, perform NDI every 12 actual fired starts until repairs completed
- Following tip repair, repeat NDI at 25, 50, and 100 actual fired starts from time of repair
- In corrosive environment without NUVS S0 and S1 vanes, perform R0 and R1 tip NDI every 40 to 50 starts
- If R0 LE root cracks confirmed by NDI, do not restart the unit
- If R0 or R1 tip indications confirmed by NDI, do not restart the unit; perform borescope of entire compressor at first opportunity
- If S0 TE cracks confirmed by NDI, do not restart the unit
- If cracks observed on any S0 TE, recommend entire stage replacement
- During MI or other opportunity where 7F/9F compressor front-end is exposed, perform R0 root, R0 tip, S0 TE, and R1 tip NDI irrespective of previous findings
- If 6F compressor front-end is exposed prior to MI, perform R0 root, R0 tip, S0 TE, and R1 tip NDI
- NDI method: red dye penetrant inspection; FPI preferred when available
- Report any distress identified during visual or NDI to GE Gas Power Services representative for evaluation

## Recommended Interval Or Trigger
- Annual visual/borescope inspection for all configurations
- R0 root NDI: after first 50 actual fired starts, then after additional 25 starts, then annual (7F/9F standard) or at MI (6F standard)
- R0 tip NDI: annual if prior rubs (7F/9F standard); at MI if prior rubs (6F standard)
- R1 tip NDI: annual if qualifying conditions met (7F/9F standard); at MI (6F standard)
- S0 TE NDI: annual for flared compressors (7F/9F standard); at MI for flared (6F standard)
- If rubs identified: NDI at discovery, then at 25, 50, 100 starts
- If damage noted pending repair: NDI every 12 actual fired starts
- Corrosive environment without NUVS: NDI every 40-50 starts
- During MI or front-end exposure: perform all NDI regardless of previous findings

## Usage Counter Requirements
- Counters To Check or Consider: starts
- Requirements Text: Inspections are triggered by actual fired starts: R0 root NDI after first 50 starts then 25 additional starts; R0/R1 tip NDI at 25, 50, 100 starts after rub discovery or repair; every 12 starts if damage pending repair; every 40-50 starts in corrosive environment without NUVS.

## Applicability And Exclusions
- Frame or Model Applicability: This TIL is applicable to all 6F, 7F, and 9F gas turbines with an 18-stage axial compressor.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Inspection requirements vary by compressor configuration: Standard (non-enhanced), Enhanced compressor package 1, 2, 2+, 3, 4, or 5. R0 tip NDI required only if blades have experienced previous rubs. R1 tip NDI required if prior tip rubs/cracks/loss, or rotor previously operated with UVS S0 and S1 (flared only), or rotor shipped prior to 2006 (flared only). S0 TE NDI required only for flared compressors.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Enhanced compressor package 2 or higher: R0 LE root NDI not required. Enhanced compressor package 2 or higher: R0 tip NDI not required. Enhanced compressor package 5: R1 tip NDI not required. Enhanced compressor package 2+ or higher: S0 TE NDI not required. S0 TE NDI not required for unflared compressors. 6F compressor is at lower risk for front end compressor distress per field data.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: For 7F and 9F, inspections can be performed in-situ through the inlet plenum without casing removal. For 6F, NDI cannot be performed on S0 TE or R1 tips through the inlet; recommended NDI frequency is at major inspection. R0 blend/repair for 7F/9F may be performed in situ. R1 repair for 7F/9F requires lifting upper-half compressor casing. 6F R0 and R1 repairs require lifting upper half mid compressor casing. S0 vane replacement requires lifting upper-half compressor casing.

## SBOM Trigger Reason
Inspection requirements depend on installed compressor configuration (enhanced package level 1-5 vs standard), flared vs unflared compressor type, presence of UVS vs NUVS S0/S1 vanes, and rotor ship date (prior to 2006), all requiring installed-configuration verification.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: R0 rotor stage-0 blades - subject of LE root NDI and tip NDI (Recommendations sections 1-3, Tables 1 and 2)
- [no explicit part number]: R1 rotor stage-1 blades - subject of tip NDI (Recommendations section 3, Tables 1 and 2)
- [no explicit part number]: S0 stator stage-0 vanes - subject of trailing edge NDI; if cracks found, entire stage replacement recommended (Recommendations section 4, Tables 1 and 2)
- [no explicit part number]: Non-uniform vane spacing (NUVS) S0 and S1 vanes - presence affects corrosive environment inspection interval (Page 7, corrosive environment recommendation)

## Reference Documents
- TIL 1323: LE erosion from water ingestion inspection/maintenance recommendations
- TIL 1399: LE erosion from water ingestion inspection/maintenance recommendations
- TIL 1603: LE erosion from water ingestion inspection/maintenance recommendations
- TIL 1518: Maintenance and Inspection Requirements for Gas Turbine Air Filter Compartments
- TIL 1345: Overspeed trip test procedures to prevent casing distortion
- TIL 1348: Start-up procedures for select 7F units to prevent inadequate blade clearances
- TIL 1579: Routine maintenance of piping and tubing within turbine enclosure to prevent fluid spills on casings
- TIL 1622: Water Removal Systems for Corrosion Reduction
- GEK 111330: Operations and Maintenance for Inlet Filter Compartment
- GEK 116269: Gas Turbine Inlet Air Specification
- GEK 111331: Operation and Maintenance Recommendations for Air Evaporative Coolers
- GEK 111332: Operations and Maintenance Recommendations for Gas Turbine Inlet Duct and Plenum

## Tables Found Summary
- {"table_label": "Table 1", "table_description": "Recommended inspections and schedule for 7F and 9F by compressor configuration (standard through enhanced package 5), showing Visual/Borescope, R0 Root NDI, R0 Tip NDI, R1 Tip NDI, and S0 TE NDI frequencies", "useful_for_downstream": true, "reason": "Defines exact inspection requirements by compressor configuration for 7F/9F units - critical for outage scoping"}
- {"table_label": "Table 2", "table_description": "Recommended inspections and schedule for 6F by compressor configuration (standard through enhanced package 5), showing Visual/Borescope, R0 Root NDI, R0 Tip NDI, R1 Tip NDI, and S0 TE NDI frequencies (MI-based)", "useful_for_downstream": true, "reason": "Defines exact inspection requirements by compressor configuration for 6F units - critical for outage scoping"}

## Source Snippets
- {"field": "compliance_category_code", "snippet": "Compliance Category - c"}
- {"field": "failure_consequences", "snippet": "Once a crack has initiated, it propagates during the start and stop cycles of normal operation. Subsequently, the crack can propagate at full speed operation due to high cycle fatigue and potentially lead to blade liberation. The liberation of an R0 blade from the root region can cause collateral damage to the gas turbine."}
- {"field": "service_recommendation_line_items", "snippet": "If R0 LE root cracks exist and are confirmed by NDI, do not restart the unit."}
- {"field": "usage_counter_requirements_text", "snippet": "Perform a visual inspection and NDI of the R0 LE roots after the first 50 actual fired starts on the R0 blades. Repeat the R0 LE root NDI after an additional 25 actual fired starts from the first inspection."}
- {"field": "configuration_dependent", "snippet": "R1 tip NDI is required per the above schedule if ANY of the below conditions are met: - R1 blades have had prior tip rubs, tip cracks, or tip loss (flared or unflared compressor). - Rotor has previously operated with uniform vane spacing (UVS) S0 and S1 (flared compressor only). - Rotor was shipped prior to 2006 (flared compressor only)."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "If the unit has received enhanced compressor package 2, or higher, then R0 LE root NDI is not required."}
- {"field": "prerequisite_outage_or_inspection_context_text", "snippet": "For the 7F and 9F, the above inspections can be performed in-situ through the inlet plenum without casing removal. For the 6F, an NDI cannot be performed on the S0 TE, or R1 tips through the inlet."}
- {"field": "service_recommendation_line_items", "snippet": "If the unit is suspected to be in a corrosive environment and the unit is not equipped with non-uniform vane spacing (NUVS) S0 and S1 vanes, it is recommended to perform an NDI on the R0 and R1 blade tips every 40 to 50 starts."}

## PDF Context
- File Name: TIL 1509-R4 - F-CLASS FRONT END (R0, S0, AND R1) COMPRESSOR INSPECTIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1509-R4 - F-CLASS FRONT END (R0, S0, AND R1) COMPRESSOR INSPECTIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
