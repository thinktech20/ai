# TIL Profile Review: 1603-R2

| Field | Value |
| --- | --- |
| Requested TIL | 1603-R2 |
| Matched TIL | TIL 1603-R2 |
| Revision | R2 |
| Title | R0 EROSION AND WATER INGESTION RECOMMENDATIONS |
| Publish Date | 2019-02-12 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.78 |
| SBOM Dependency Flag | False |

## Purpose
To advise operators of the inspection and maintenance considerations necessary to mitigate R0 erosion effects, and to inform them of a new online water wash (OnWW) system that reduces the rate of erosion in the principal area of concern. Failure to properly monitor or repair R0 erosion could result in cracking of the R0 blades and risks of compressor damage.

## Reason For Revision
The reason for this revision is to improve the clarity of the recommendations regarding online water wash frequency and mold inspections for specific F-class compressor configurations.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Compliance Required
- Recurring Indicator: Not provided
- Coarse Outage Type: At Scheduled Component Part Repair or Replacement
- Maintenance Trigger Text: R0 erosion inspections should include both mold impressions and FPI and should be performed when cumulative wet inlet operation time reaches 100 hours as defined by the following formula: Combined Wet Time = 4*(OnWW hours[A]) + 1*(OnWW hours[B]) + (Fogger hours[C]) + 2*(SPRITS hours[D]) + (Evap hours[E]).
- Completion Criteria: Design analysis and field experience have defined this threshold at a measured erosion depth of .008 inches.

## Scope Of Work
- Perform R0 erosion quantification using mold impressions of the R0 leading-edge root location (recommended method for erosion quantification).
- Perform fluorescent penetrant inspection (FPI) following mold inspections to ensure against existing cracks.
- Monitor/inspect evaporative cooler systems for evidence of water carry-over (water stains, puddles, streaking, deposits, missing/damaged/misaligned filter or cycle deck material) and disposition/eliminate carry-over.
- Schedule and perform recurring R0 erosion inspections (molds + FPI) based on cumulative wet inlet operation time using the Combined Wet Time formula.
- If erosion approaches cracking-risk threshold, disposition may include reduced inspection interval, discontinuance of wet inlet operation, and/or leading edge blend repair by qualified GE Energy Services technicians; shot peening required post-blending.
- For units operating with original OnWW system, modify per TIL 1323 and inspect erosion at regular intervals of OnWW via molds at R0 leading-edge root location.
- Consider upgrade to the new/upgraded online water wash system (Gen-2) with relocated/redesigned spray nozzles; contact GE Power Services representative for upgrade information and quotation.

## Service Recommendation Line Items
- For current F-class units operating with the original OnWW system: modify the original online water wash system per TIL 1323, then inspect R0 erosion at regular intervals of OnWW by taking mold impressions of the R0 leading-edge root location; follow mold inspections with FPI.
- Perform OnWW per guidelines to balance erosion rates and output degradation: 5 minutes per 48 Fired Hours (standard R0s + Gen-1 WW); 15 minutes per 48 Fired Hours (standard R0s + Gen-2 WW); 15 minutes per 48 Fired Hours (enhanced R0s (ECP 2, 2+3, 4, 5) + Gen-1 or Gen-2 WW).
- For units utilizing fogging systems: inspect R0 blades with mold impressions and FPI at regular intervals of cumulative hours of fogger operation as defined in Combined Wet Inlet Operation.
- For evaporative cooler operation: monitor for proper operation and any evidence of water carry-over; disposition and eliminate any evidence of carry-over; perform R0 erosion molds and FPI between 100 and 300 hours of cumulative operation of the evap system; repeat at this interval if carry-over is identified or as determined based on mold impressions; if no significant erosion and continually verified no carry-over, no continual R0 mold inspection is necessary.
- For combined wet inlet operation: perform R0 erosion inspections (mold impressions + FPI) when cumulative wet inlet operation time reaches 100 hours per Combined Wet Time formula; following initial inspections, parameters C and D may be adjusted per GE disposition.
- If measured erosion depth approaches the cracking-risk threshold (.008 inches): disposition may include reduced interval for subsequent inspection and/or discontinuance of further wet inlet operation until R0s can be blend repaired by qualified GE Energy Services technicians; perform shot peening post-blending using a qualified vendor.
- Note configuration exclusions: interval recommendations do not apply to unit operation with p-cut R0 blades (erosion repairs can be performed at Major Inspection intervals or earlier as preferred); leading edge R0 inspections and molds highlighted in this TIL are no longer recommended if the unit has enhanced R0 blades.
- Consider upgrading to the new/upgraded online water wash system (Gen-2) which requires no maintenance for up to 1000 cumulative hours of washing and allows daily water washing (15 minutes per 48 fired hours) with no R0 erosion maintenance necessary until the scheduled Major Inspection interval; contact GE Power Services representative for upgrade.

## Recommended Interval Or Trigger
- Combined Wet Inlet Operation: perform R0 erosion inspections (FPI & molds) when cumulative wet inlet operation time reaches 100 hours per Combined Wet Time formula.
- Original OLWW (Gen-1) stand-alone mold inspection interval: 23-30 hrs OnWW or annually (usage guideline: 5 min / 48 FH).
- Upgraded OLWW (Gen-2) stand-alone mold inspection interval: 1000 hrs OnWW or MI's (usage guideline: 15 min / 48 FH).
- Non-GE Fogging stand-alone mold inspection interval: 100 hrs fogging (may be adjusted).
- GE Fogging / SPRITS stand-alone mold inspection interval: 500 hrs fogging (may be adjusted).
- Evaporative Cooling: initial commissioning inspection between 100 and 300 hrs evaps; repeat if carry-over is observed; not applicable once no carry-over verified.

## Usage Counter Requirements
- Counters To Check or Consider: operating_hours
- Requirements Text: Intervals are based on cumulative hours of wet inlet operation (OnWW hours, Fogger hours, SPRITS hours, Evap hours) and a calculated Combined Wet Time trigger at 100 hours: Combined Wet Time = 4*(OnWW hours[A]) + 1*(OnWW hours[B]) + (Fogger hours[C]) + 2*(SPRITS hours[D]) + (Evap hours[E]). OnWW frequency guidance is expressed per 48 Fired Hours.

## SBOM Trigger Reason
Not provided

## Parts Referenced
- None

## Reference Documents
- {"document_number": "TIL 1303", "document_type": "TIL", "context": "Superseded by this TIL."}
- {"document_number": "TIL 1389", "document_type": "TIL", "context": "Superseded by this TIL; also referenced in evaporative cooling table usage guidelines (\"TIL1285, TIL1389\")."}
- {"document_number": "TIL 1400", "document_type": "TIL", "context": "Superseded by this TIL."}
- {"document_number": "TIL 1401", "document_type": "TIL", "context": "Superseded by this TIL."}
- {"document_number": "TIL 1323", "document_type": "TIL", "context": "Advises modification to the original online water wash system; referenced for original OnWW system modification and in Reference Documents list."}
- {"document_number": "TIL 1285", "document_type": "TIL", "context": "Referenced for evaporative cooler maintenance and annual commissioning; included in Reference Documents list."}
- {"document_number": "TIL 1399", "document_type": "TIL", "context": "Referenced for evaporative cooler maintenance and annual commissioning; included in Reference Documents list."}
- {"document_number": "TIL 1509", "document_type": "TIL", "context": "R0 erosion molds and FPI can be performed concurrently with TIL 1509 inspections."}

## Tables Found Summary
- {"table_label": "Page 1 Table 1", "table_description": "Compliance category definitions (M, C, A, S).", "useful_for_downstream": true, "reason": "Clarifies meaning of compliance category code shown on the TIL (\"Compliance Category - c\")."}
- {"table_label": "Page 1 Table 2", "table_description": "Timing code definitions (1-6), including Timing Code 5 = \"At Scheduled Component Part Repair or Replacement.\"", "useful_for_downstream": true, "reason": "Maps the TIL's Timing Code 5 to an outage/planning trigger."}
- {"table_label": "Page 5 Table 1 (Standard R0 Inspection Guidelines for Wet Inlet Conditioning)", "table_description": "System-specific usage guidelines and stand-alone mold inspection intervals for Original OLWW (Gen-1), Upgraded OLWW (Gen-2), Non-GE Fogging, GE Fogging/SPRITS, and Evaporative Cooling; includes notes about adjustability and carry-over verification.", "useful_for_downstream": true, "reason": "Provides the actionable inspection intervals and conditions needed to schedule molds/FPI based on wet inlet system usage."}

## Source Snippets
- {"field": "til_number", "snippet": "TIL 1603-R2"}
- {"field": "publish_date", "snippet": "12 FEBRUARY 2019"}
- {"field": "compliance_category_code", "snippet": "Compliance Category - c"}
- {"field": "coarse_outage_type", "snippet": "Timing Code - 5"}
- {"field": "purpose", "snippet": "Failure to properly monitor or repair R0 erosion could result in cracking of the R0 blades and risks of compressor damage."}
- {"field": "reason_for_revision", "snippet": "The reason for this revision is to improve the clarity of the recommendations regarding online water wash frequency and mold inspections for specific F-class compressor configurations."}
- {"field": "maintenance_trigger_text", "snippet": "R0 erosion inspections should include both mold impressions and FPI and should be performed when cumulative wet inlet operation time reaches 100 hours as defined by the following formula:\nCombined Wet Time = 4*(OnWW hours[A]) + 1*(OnWW hours[B]) + (Fogger hours[C]) + 2*(SPRITS hours[D]) +\n(Evap hours[E])"}
- {"field": "completion_criteria_text", "snippet": "Design analysis and field experience have defined this threshold at a measured erosion depth of .008 inches."}
- {"field": "recommended_interval_or_trigger", "snippet": "General guidelines for OnWW duration and frequency are as follows:\n5 minutes per 48 Fired Hours, if standard R0's and the Gen-1 WW system are in place\n15 minutes per 48 Fired Hours, if standard R0's and the Gen-2 WW system are in place (available through\nCM&U)\n15 minutes per 48 Fired Hours, if enhanced R0s (ECP 2, 2+3, 4, 5) are installed with either the Gen-1 WW\nor the Gen-2 WW system"}
- {"field": "configuration_dependent", "snippet": "These interval recommendations do not apply to unit operation with p-cut R0 blades."}
- {"field": "configuration_dependent", "snippet": "The leading edge R0 inspections and molds highlighted in this TIL are no longer recommended if the unit\nhas enhanced R0 blades."}

## PDF Context
- File Name: TIL 1603-R2 - R0 EROSION AND WATER INGESTION RECOMMENDATIONS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 1603-R2 - R0 EROSION AND WATER INGESTION RECOMMENDATIONS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
