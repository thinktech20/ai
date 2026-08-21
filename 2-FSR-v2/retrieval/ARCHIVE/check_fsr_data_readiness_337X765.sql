-- Check why FSRs are included/excluded for ESN 337X765 in Data Readiness
WITH fsr_check AS (
  SELECT
    d.document_id,
    d.esn,
    d.equip_type,
    d.is_primary_esn,
    d.is_active,
    m.pdf_name,
    m.report_issued_date,
    m.outage_start_date,
    m.outage_end_date,
    m.event_type,
    m.outage_type,
    m.metadata_status,
    m.chunk_status,
    CASE
      WHEN d.is_active = true
       AND m.metadata_status = 'completed'
       AND m.chunk_status = 'completed'
       AND to_date(m.outage_start_date) >= add_months(current_date(), -120)
      THEN 'INCLUDED_IN_DATA_READINESS'
      ELSE concat_ws(
        '; ',
        CASE WHEN d.is_active <> true THEN 'inactive mapping' END,
        CASE WHEN m.metadata_status <> 'completed' THEN concat('metadata_status=', coalesce(m.metadata_status, 'NULL')) END,
        CASE WHEN m.chunk_status <> 'completed' THEN concat('chunk_status=', coalesce(m.chunk_status, 'NULL')) END,
        CASE WHEN to_date(m.outage_start_date) < add_months(current_date(), -120)
               OR m.outage_start_date IS NULL THEN concat('outage_start_date_out_of_window=', coalesce(cast(m.outage_start_date as string), 'NULL')) END
      )
    END AS inclusion_result
  FROM vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2 d
  INNER JOIN vaid.ai_sot_field_service_report.fsr_metadata_v2 m
    ON d.document_id = m.document_id
  WHERE upper(d.esn) = upper('337X765')
)
SELECT *
FROM fsr_check
ORDER BY try_cast(report_issued_date as date) DESC, document_id;