# TIL Profile Review: 2322-R2

| Field | Value |
| --- | --- |
| Requested TIL | 2322-R2 |
| Matched TIL | TIL 2322 |
| Revision | R2 |
| Title | HA AND .05 COMPRESSOR STATOR VANE RING DISTRESS |
| Publish Date | 2024-12-26 |
| Method Used | foundation |
| PDF Source | workspace_sample_pdf |
| PDF Match Type | exact_til_number |
| Model | Not provided |
| Extraction Confidence | 0.91 |
| SBOM Dependency Flag | True |

## Purpose
The purpose of this TIL is to inform affected users about the potential for Vane Ring distress and the inspections needed to monitor the said distress at the next scheduled outages. Failure to comply with this requirement may result in domestic object damage to compressor airfoils.

## Reason For Revision
Fleet findings showed wear mainly on unloaded segments. This TIL revision is issued to inform the users of the updated fleet findings and of the availability of a new vane kit that contains fully coated vane and ring unloaded segments.

## Compliance And Triggering Context
- Compliance Category Code: C
- Compliance Category Text: Compliance Required - Identifies the need for action to correct a condition that, if left uncorrected, may result in reduced equipment reliability or efficiency. Compliance may be required within a specific operating time.
- Recurring Indicator: Yes
- Coarse Outage Type: Next Scheduled Outage
- Maintenance Trigger Text: Next Scheduled Outage (Timing Code 6). Annual borescope inspections, Major Inspections, and any planned/unplanned outages when compressor stages under CDC are exposed.
- Completion Criteria: With the replacement of new vane kit of unloaded segments for S11 to S13, this TIL can be considered compliant, however affected users should continue inspecting the remaining affected segments as per Table 1 during planned annual BI and other planned or unplanned outages when CDC is exposed.

## Scope Of Work
- Borescope inspection: Qualified and competent LES borescope technician. Inspect 100% of Vane and Ring platforms and first two segments from upper half right side and lower half left side horizontal joint segments Vane tips.
- Major inspection and other planned/unplanned outage: Two blade millwrights. Inspect Vane and Ring platform, Vane tips, Ring tabs and Casing slots. Replace unloaded segments of S11 to S13 during Major Inspection.
- New replacement part for other stages in CDC (outside S11 to S13) may be needed if significant distress is noted.
- The inspection during planned exposure may take one additional shift. Replacement of parts may take minimum of three additional shifts for all affected stage replacement.
- Order Stator keys as uninstalling stator segments may require key replacement.

## Service Recommendation Line Items
- During planned annual borescope inspections: Inspect 100% of affected stage Vane and ring platforms, focusing on ring forward side interface with casing for signs of material cracking and chipping.
- During planned annual borescope inspections: Inspect Vane tips on the first two segments from upper half right horizontal joint and first two segments from lower half left horizontal joint (forward looking aft), focusing on pressure side trailing edge squealer tip region for signs of rubs; if rub is noted, continue inspecting adjacent segments.
- During planned major inspections: Replace unloaded segments of S11 to S13. Lead time for these parts is generally high (in some cases longer than 1 year), therefore plan ordering replacement part well in advance of planned MI.
- During planned major inspections: In addition to unloaded segments replacement, inspect segments that are not being replaced per item 3.
- During any planned/unplanned outages when compressor stages under CDC are exposed: Inspect 100% of affected stage vane and ring platforms for signs of material cracking and chipping. All cracked/chipped vane and ring segments shall be pulled out from casing and inspected.
- During any planned/unplanned outages when CDC is exposed: Inspect 100% of affected stage vane tips for signs of rubs, focusing on pressure side trailing edge squealer tip region. All worn TE tips segments shall be pulled out from casing and inspected.
- During any planned/unplanned outages when CDC is exposed: Inspect stator ring tabs for signs of wear, start with unloaded segments; if wear is observed, continue inspection on adjacent ring segments until there are no findings.
- For segments with tab thickness loss >40% and/or Airfoil TE tip wear or notch: Measure ring tab thickness for adjacent segments and report all tab thickness measurements and pictures to GE Vernova Engineering for disposition.
- Measure ring tab thickness along three circumferential locations (either ends and in the middle on forward and aft side of segments).
- Inspect casing slot for any distress and document the condition of the distress.
- Limit blending of any casing wear only to remove high metal that protrudes above the original casing slot, ensuring that the overall casing slot width is not increased.
- All removed parts, if acceptable to be reused, shall be installed back in the same position from which they were removed.
- Segment removal can be done with the rotor installed. Care should be taken during S14 removal or installation to avoid damages to brush seal.
- Order stator keys in advance because uninstalling stator segments may require key replacement.

## Recommended Interval Or Trigger
- Annual borescope inspection for vane and ring platform and vane tip monitoring
- Major Inspection for replacement of unloaded segments S11 to S13
- Any planned/unplanned outage when compressor stages under CDC are exposed for full inspection of vane/ring platform, vane tips, ring tabs, and casing slots

## Usage Counter Requirements
- Counters To Check or Consider: Not provided
- Requirements Text: Not provided

## Applicability And Exclusions
- Frame or Model Applicability: Applicable to all 7F.04-200, 7F.05, 9F.05-18, 7HA.01, 7HA.02, 7HA.03, 9HA.01, and 9HA.02 units.
- Combustion or Fuel Configuration: Not provided
- Hardware or Part Configuration: Affected vane ring stages are those that interface with the Compressor Discharge Case (CDC). Variable vanes and forward vane ring stages that interface with the Mid Compressor Casing are not affected. New vane kit consists of four 'unloaded segments' (first two segments each on upper half right horizontal joint and lower half left horizontal joint) that are 'fully coated' with coating on stator ring and vane dovetail forward and aft faces and stator ring forward and aft tabs.
- Serial or Unit Applicability: Not provided
- Exclusions or Non-Applicable Conditions: Variable vanes and forward vane ring stages that interface with the Mid Compressor Casing are not affected.
- Required Prior Modifications: Not provided
- Prerequisite Outage or Inspection Context: Inspection requires CDC stages to be exposed. Segment removal can be done with rotor installed. Care should be taken during S14 removal or installation to avoid damages to brush seal.

## SBOM Trigger Reason
TIL references a new fully coated vane kit for unloaded segments requiring installed-configuration verification to determine whether units already have the fully coated parts installed, which changes the inspection process per the Ring Tab Inspection Process Map.

## MLI Numbers
- None

## Parts Referenced
- [no explicit part number]: New vane kit consisting of four 'unloaded segments' (fully coated part with coating on stator ring and vane dovetail forward and aft faces and stator ring forward and aft tabs) available for each stage in the CDC (Page 6 - Background Discussion / Recommendations)
- [no explicit part number]: Stator keys - order in advance because uninstalling stator segments may require key replacement (Page 7 and Page 11 - Recommendations / Scope of Work)
- [no explicit part number]: Replacement unloaded segments for S11 to S13 - lead time generally high (in some cases longer than 1 year) (Page 6 - Recommendations item 2)

## Reference Documents
- None

## Tables Found Summary
- {"table_label": "Table 1", "table_description": "Affected Vane Ring Stages by engine type showing number of affected stages and stage range", "useful_for_downstream": true, "reason": "Defines which stages require inspection per engine frame, critical for scoping outage work"}

## Source Snippets
- {"field": "purpose", "snippet": "The purpose of this TIL is to inform affected users about the potential for Vane Ring distress and the inspections needed to monitor the said distress at the next scheduled outages. Failure to comply with this requirement may result in domestic object damage to compressor airfoils."}
- {"field": "completion_criteria_text", "snippet": "With the replacement of new vane kit of unloaded segments for S11 to S13, this TIL can be considered compliant, however affected users should continue inspecting the remaining affected segments as per Table 1 during planned annual BI and other planned or unplanned outages when CDC is exposed."}
- {"field": "reason_for_revision", "snippet": "Fleet findings showed wear mainly on unloaded segments. This TIL revision is issued to inform the users of the updated fleet findings and of the availability of a new vane kit that contains fully coated vane and ring unloaded segments."}
- {"field": "configuration_summary", "snippet": "Updated fleet finding showed wear mainly on the S11 to S13 unloaded segment, while a few units had wear on the other stages of CDC unloaded segments."}
- {"field": "service_recommendation_line_items", "snippet": "It is recommended to replace unloaded segments of S11 to S13 during a Major Inspection. Lead time for these parts is generally high (in some cases longer than 1 year), therefore plan ordering replacement part well in advance of your planned MI."}
- {"field": "parts_referenced", "snippet": "GE Vernova has developed a new vane kit, consisting of four \"unloaded segments\" (first two segments each on upper half right horizontal joint and lower half left horizontal joint). This vane kit is available for each stage in the CDC. All the segments in these kits are \"fully coated\" part"}
- {"field": "severity_signals", "snippet": "Wear on the forward face of stator vane ring segment can progress to the ring and vane platform causing cracking and/or chipping."}

## PDF Context
- File Name: TIL 2322-R2 - HA AND .05 COMPRESSOR STATOR VANE RING DISTRESS.pdf
- PDF Path: C:\Users\560068861\Code\alexis_scoping\context\data\workspace_notes\samples\TILs\databricks_top25\TIL 2322-R2 - HA AND .05 COMPRESSOR STATOR VANE RING DISTRESS.pdf
- Source: workspace_sample_pdf
- Match Type: exact_til_number
