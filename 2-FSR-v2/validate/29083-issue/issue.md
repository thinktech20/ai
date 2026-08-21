# FSR Validation Notes: `270T483`

The report appears to be filed under and repeatedly labeled with ESN `270T483`, which is associated with a Generator. However, the content of the report references unit `290T483`, which is a Steam Turbine. This discrepancy suggests that the report may have been misfiled or mislabeled, as the equipment type and serial number do not match the actual unit being inspected.

## Document

```text
/Volumes/viud/ing_ud_fieldvision/fv_field_service_report/35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270T483-Final_Master_Report.pdf
```
Attached here - 2-FSR-v2\validate\29083-issue\35803273-2440-4d36-87fe-e45f7f0e5467_605011422-40815-270T483-Final_Master_Report.pdf
## FSR Metadata V2

Source table:

```sql
vaid.ai_sot_field_service_report.fsr_metadata_v2
```

| Field | Value |
|---|---|
| `esn` | `270T483` |
| `equip_type` | `Generator` |
| `is_primary_esn` | `true` |
| `is_active` | `true` |
| `source_region_count` | `7` |
| `document_summary` | `null` |

## Mapping Table

| Field | Value |
|---|---|
| `esn` | `270T483` |
| `is_primary_esn` | `true` |
| `is_active` | `true` |
| `equip_type` | `Generator` |

## Document Review

### First Page

```text
Equipment Serial #: 270T483
```

### Other Pages

The footer on the remaining pages contains:

```text
MAJOR - 270T483
```

### Page 3: Executive Summary

> **1.2 Executive Summary**
>
> This report documents the generator field in MAGIC Jr inspection (Miniature Air Gap Inspection) performed on unit 290T483 at Dynegy Corp. Moss Landing Power Plant located in Moss Landing, CA from March 01 to Apr 29, 2018. The intent was to provide a condition assessment of generator stator and field with minimal generator disassemble.
>
> GE Power Service provided the following services: Generator Specialist for Technical Direction and LES Technician operating the MAGIC equipment. Atlantic Plant and Maintenance (APM) supplied manpower during the disassemble, inspection, and reassemble of the unit. The scope of work was executed on one 10-hour shift per day and seven days per week.

## PDF Reference Table

Query:

```sql
SELECT *
FROM vgpd.fsr_std_views.fsr_pdf_ref
WHERE esn IN ('290T483', '270T483');
```

Observed result:

| Field | Value |
|---|---|
| `esn` | `270T83` |
| `ev_equipment_type` | `Steam Turbine` |

> **Note:** The returned ESN is recorded in the notes as `270T83`, which may be a transcription error or a source-data issue because the query used `270T483`.

## IBAT Equipment Master

Query:

```sql
SELECT
    equipment_sys_id,
    equip_serial_number,
    driven_equipment,
    equipment_type
FROM vgpd.prm_std_views.IBAT_EQUIPMENT_MST
WHERE equip_serial_number IN ('290T483', '270T483');
```

Results:

| `equipment_sys_id` | `equip_serial_number` | `driven_equipment` | `equipment_type` |
|---|---|---|---|
| `SY0073324` | `270T483` | `Generator` | `Steam Turbine` |
| `SY0072571` | `290T483` | `Steam turbine` | `Generator` |



