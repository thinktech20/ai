## ibat_equipment_mst

- Think of this as the equipment master table.
- It is used for direct ESN lookup, for example: ESN -> equipment_sys_id, equipment_type, equipment_sub_class.
- Best for row-level enrichment when you already know one ESN.
- In the codebase, this is the default IBAT source in fsr_config.py (line 132).

```sql
SELECT equipment_sys_id, equipment_sub_class AS equipment_class_code
FROM {IBAT_EQUIPMENT_TABLE}
WHERE UPPER(TRIM(equip_serial_number)) = UPPER(TRIM({_sql_str(esn)}))
LIMIT 1
```

## eu_ibat

- Think of this as the equipment-to-train relationship view.
- It includes train linkage (train_sys_id_fk) and sibling equipment on the same train.
- Best for train expansion logic: seed ESN -> train -> all sibling ESNs (GT/Gen/ST, etc.).
- This is the table used in the train investigation notes at "Box\FSR_v2\analysis\FSR_IBAT_Investigation_2026-05-26.md" (line 121).

```sql
-- input: :seed_esn
WITH seed_train AS (
  SELECT train_sys_id_fk
  FROM vgpp.fdc_std_views.eu_ibat
  WHERE UPPER(TRIM(esn)) = UPPER(TRIM(:seed_esn))
    AND COALESCE(record_status, '')    NOT ILIKE '%cancel%'
    AND COALESCE(equipment_status, '') NOT ILIKE '%cancel%'
    AND train_sys_id_fk IS NOT NULL
  LIMIT 1
)
SELECT DISTINCT
  UPPER(TRIM(e.esn)) AS esn,
  e.equipment_type,
  e.equipment_code,
  e.equipment_sub_class AS equipment_class_code,
  e.equipment_sys_id,
  e.train_sys_id_fk
FROM vgpp.fdc_std_views.eu_ibat e
JOIN seed_train t
  ON e.train_sys_id_fk = t.train_sys_id_fk
WHERE e.esn IS NOT NULL
  AND TRIM(e.esn) <> ''
  AND COALESCE(e.record_status, '')    NOT ILIKE '%cancel%'
  AND COALESCE(e.equipment_status, '') NOT ILIKE '%cancel%'
ORDER BY e.equipment_type, esn;
```

## Quick rule

- Use ibat_equipment_mst for single-ESN metadata fill.
- Use eu_ibat when recall depends on cross-equipment train expansion.
