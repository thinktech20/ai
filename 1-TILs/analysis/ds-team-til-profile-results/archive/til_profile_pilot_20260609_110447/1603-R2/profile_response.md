# TIL Profile Review: 1603-R2

| Field | Value |
| --- | --- |
| Requested TIL | 1603-R2 |
| Matched TIL | TIL 1603 |
| Revision | R2 |
| Title | R0 Erosion and Water Ingestion Recommendations |
| Publish Date | 2019-02-12 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.92 |
| SBOM Dependency Flag | True |

## Purpose
To advise operators of the inspection and maintenance considerations necessary to mitigate R0 erosion effects, and to inform them of a new online water wash (OnWW) system that reduces the rate of erosion in the principal area of concern. Failure to properly monitor or repair R0 erosion could result in cracking of the R0 blades and risks of compressor damage.

## Reason For Revision
To improve the clarity of the recommendations regarding online water wash frequency and mold inspections for specific F-class compressor configurations.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Compliance Required - Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: Yes - recurring mold inspections at defined cumulative wet inlet operation intervals
- Coarse Outage Type: Major Inspection / Scheduled Component Part Repair or Replacement
- Maintenance Trigger Text: Cumulative wet inlet operation time reaching 100 hours per Combined Wet Time formula, or stand-alone system-specific intervals; erosion depth reaching 0.008 inches requires repair.
- Completion Criteria: Mold impressions evaluated and dispositioned by GE Engineering; FPI confirms no existing cracks; erosion depth maintained below 0.008 inches threshold.

## Scope Of Work
- R0 erosion molds and FPI can be performed concurrently with TIL 1509 inspections
- R0 erosion molds typically take at most ½ shift or 6 man-hours to complete
- FPI of R0s typically requires one 12-hour shift
- Leading edge blending for R0 erosion can be done at site or with blades sent to a GE Service Center; typical duration for blending in the unit is four days and requires inlet bellmouth be jacked approximately two feet
- Blending may be performed in a GE Service Center in as little as two days
- For OnWW upgrade to Gen-2, the CM&U process should be followed for quoting of labor and parts; on-site machining will be necessary

## Service Recommendation Line Items
- Perform mold impressions and FPI of R0 leading-edge root location at regular intervals based on Combined Wet Time formula reaching 100 hours
- For Original OnWW (Gen-1): inspect at 23-30 hrs OnWW or annually (stand-alone interval)
- For Upgraded OnWW (Gen-2): inspect at 1000 hrs OnWW or at Major Inspections (stand-alone interval)
- For Non-GE Fogging: inspect at 100 hrs fogging (may be adjusted based on initial inspections)
- For GE Fogging/SPRITS: inspect at 500 hrs fogging (may be adjusted based on initial inspections)
- For Evaporative Cooling: initial commissioning inspection at 100-300 hrs evaps; repeat if carry-over is observed
- OnWW duration guidelines: 5 min per 48 Fired Hours if standard R0s and Gen-1 WW system; 15 min per 48 Fired Hours if standard R0s and Gen-2 WW system; 15 min per 48 Fired Hours if enhanced R0s (ECP 2, 2+3, 4, 5) with either Gen-1 or Gen-2 WW
- Modify original OnWW system per TIL 1323 to reduce water impingement on R0 leading edge root
- Monitor evaporative coolers for proper operation and evidence of water carry-over; eliminate any carry-over
- If measured erosion depth reaches 0.008 inches, discontinue wet inlet operation until R0s can be blend repaired
- Shot peening is required post-blending by a qualified vendor
- Leading edge R0 inspections and molds are no longer recommended if the unit has enhanced R0 blades
- For units with p-cut R0 blades, erosion repairs can be performed at Major Inspection intervals or earlier as preferred

## Recommended Interval Or Trigger
- Combined Wet Time = 4*(OnWW hours[A]) + 1*(OnWW hours[B]) + (Fogger hours[C]) + 2*(SPRITS hours[D]) + (Evap hours[E]) reaching 100 hours
- Original OnWW (Gen-1) stand-alone: 23-30 hrs OnWW or annually
- Upgraded OnWW (Gen-2) stand-alone: 1000 hrs OnWW or at Major Inspections
- Non-GE Fogging stand-alone: 100 hrs fogging
- GE Fogging/SPRITS stand-alone: 500 hrs fogging
- Evaporative Cooling: initial 100-300 hrs; repeat if carry-over observed
- New Gen-2 OnWW system allows daily washing (15 min per 48 fired hours) with no R0 erosion maintenance until scheduled Major Inspection interval up to 1000 cumulative hours of washing

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours, cumulative_onww_hours, cumulative_fogger_hours, cumulative_sprits_hours, cumulative_evap_hours, fired_hours
- Requirements Text: Combined Wet Time formula must be tracked: 4*(OnWW hours Gen-1) + 1*(OnWW hours Gen-2) + (Fogger hours non-GE) + 2*(SPRITS hours GE) + (Evap hours if carry-over present). Inspection triggered when cumulative value reaches 100 hours. Stand-alone intervals also apply per system type. OnWW duration guidelines reference fired hours (per 48 FH).

## Applicability And Exclusions
- Frame or Model Applicability: All F-class gas turbines excluding 6F.01, 7F.04-200 and 7F.05.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Applicability depends on R0 blade type (standard R0, enhanced R0 ECP 2/2+3/4/5, p-cut R0) and OnWW system configuration (Gen-1 original, Gen-2 upgraded). Leading edge R0 inspections and molds are no longer recommended if the unit has enhanced R0 blades. For p-cut R0 blades, erosion repairs can be performed at Major Inspection intervals.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Excludes 6F.01, 7F.04-200 and 7F.05. Interval recommendations do not apply to units with p-cut R0 blades. Leading edge R0 inspections and molds no longer recommended if unit has enhanced R0 blades.
- Required Prior Modifications: Original OnWW system should be modified per TIL 1323 to reduce volume of water impinging on R0 leading edge root location.
- Prerequisite Outage or Inspection Context: R0 erosion molds and FPI can be performed concurrently with TIL 1509 inspections. Leading edge blending requires inlet bellmouth be jacked approximately two feet if performed outside of an MI; a spare set of R0s may be preferred.

## SBOM Trigger Reason
Inspection intervals and recommendations depend on installed R0 blade configuration (standard, enhanced ECP 2/2+3/4/5, p-cut) and OnWW system version (Gen-1 vs Gen-2), requiring installed-configuration verification.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: R0 (Rotor stage 0) compressor blades - standard, enhanced (ECP 2, 2+3, 4, 5), or p-cut variants (Recommendations section, pages 3-5)
- [no explicit part number]: Molding kit for R0 erosion replications - contact GE Services representative to procure (Parts section, page 6)
- [no explicit part number]: Gen-2 upgraded OnWW system (relocated and redesigned spray nozzles) - available through CM&U process (On-line Water Wash section, pages 3-4; Parts section, page 6)
- [no explicit part number]: Seed set of R0 blades for swap during repair to minimize outage delays (Page 5, recommendations)

## Reference Documents
- TIL 1285: Evaporative cooler maintenance and annual commissioning
- TIL 1303: Superseded by TIL 1603 - prior R0 erosion guidance
- TIL 1323: Modification to original online water wash system to reduce water impingement on R0 leading edge root
- TIL 1389: Superseded by TIL 1603 - prior R0 erosion guidance; also referenced for evaporative cooler maintenance
- TIL 1399: Evaporative cooler maintenance and annual commissioning
- TIL 1400: Superseded by TIL 1603 - prior R0 erosion guidance
- TIL 1401: Superseded by TIL 1603 - prior R0 erosion guidance
- TIL 1509: R0 erosion molds and FPI can be performed concurrently with TIL 1509 inspections

## Tables Found Summary
- {"table_label": "Standard R0 Inspection Guidelines for Wet Inlet Conditioning (Figure 5)", "table_description": "Table showing systems (Original OLWW Gen-1, Upgraded OLWW Gen-2, Non-GE Fogging, GE Fogging/SPRITS, Evaporative Cooling), their usage guidelines, stand-alone mold inspection intervals, and combined operational mold inspection interval formula", "useful_for_downstream": true, "reason": "Defines specific inspection intervals per system configuration and the Combined Wet Time formula components needed for outage planning and compliance tracking"}

## Source Snippets
- {"field": "failure_consequences", "snippet": "Failure to properly monitor or repair R0 erosion could result in cracking of the R0 blades and risks of compressor damage."}
- {"field": "failure_consequences", "snippet": "Failure to follow these recommendations could result in excessive erosion, which, in turn, could lead to subsequent cracking and possible liberation of R0 blades with potential downstream damage to the gas turbine."}
- {"field": "maintenance_trigger_text", "snippet": "Design analysis and field experience have defined this threshold at a measured erosion depth of .008 inches."}
- {"field": "recommended_interval_or_trigger", "snippet": "Combined Wet Time = 4*(OnWW hours[A]) + 1*(OnWW hours[B]) + (Fogger hours[C]) + 2*(SPRITS hours[D]) + (Evap hours[E])"}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "The leading edge R0 inspections and molds highlighted in this TIL are no longer recommended if the unit has enhanced R0 blades."}
- {"field": "exclusions_or_non_applicable_conditions_text", "snippet": "These interval recommendations do not apply to unit operation with p-cut R0 blades."}
- {"field": "recommended_interval_or_trigger", "snippet": "GE has now engineered and validated a new online water wash system that imparts significantly reduced erosion at the R0 root and requires no maintenance for up to 1000 cumulative hours of washing."}
- {"field": "reason_for_revision", "snippet": "The reason for this revision is to improve the clarity of the recommendations regarding online water wash frequency and mold inspections for specific F-class compressor configurations."}

## PDF Context
- File Name: TIL 1603-R2 - R0 EROSION AND WATER INGESTION RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1603-R2 - R0 EROSION AND WATER INGESTION RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
