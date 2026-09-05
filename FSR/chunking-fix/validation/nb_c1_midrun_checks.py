# Databricks notebook source
# MAGIC %md
# MAGIC # C1 Mid-Run Verification — `_chunk_test` tables
# MAGIC
# MAGIC Run any cell while P1 + P2 jobs are in flight. All queries are read-only and safe to repeat.
# MAGIC
# MAGIC Tables:
# MAGIC - `vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test`
# MAGIC - `vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test`
# MAGIC - `vaid.ai_sot_field_service_report.fsr_run_log_chunk_test`
# MAGIC - `vaid.ai_sot_field_service_report.fsr_data_quality_log_chunk_test`

# COMMAND ----------

# MAGIC %md
# MAGIC ## M1 — Live progress dashboard
# MAGIC Re-run every 2-3 min. Counts evolve: pending/pending → completed/pending → completed/in_progress → completed/completed.

# COMMAND ----------

m1 = spark.sql("""
SELECT 
  metadata_status, 
  chunk_status, 
  COUNT(*) AS n
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
GROUP BY metadata_status, chunk_status
ORDER BY n DESC
""")
display(m1)

# COMMAND ----------

# MAGIC %md
# MAGIC ## M2 — Chunk count growing
# MAGIC `total_chunks` and `docs_with_chunks` should monotonically increase.

# COMMAND ----------

m2 = spark.sql("""
SELECT 
  COUNT(*) AS total_chunks,
  COUNT(DISTINCT document_id) AS docs_with_chunks,
  MIN(created_at) AS first_chunk,
  MAX(created_at) AS latest_chunk
FROM vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test
WHERE created_at >= current_timestamp() - INTERVAL 2 HOURS
""")
display(m2)

# COMMAND ----------

# MAGIC %md
# MAGIC ## M3 — Section metadata + embedding dim spot-check (chunker fix proof)
# MAGIC Latest 20 chunks. Expect: non-null `section_1`, `start_page`, `end_page`; `dim=3072` on all.

# COMMAND ----------

m3 = spark.sql("""
SELECT 
  document_id,
  chunk_index,
  get_json_object(metadata, '$.section_1') AS section_1,
  get_json_object(metadata, '$.start_page') AS start_page,
  get_json_object(metadata, '$.end_page')   AS end_page,
  size(chunk_embedding) AS dim,
  created_at
FROM vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test
WHERE created_at >= current_timestamp() - INTERVAL 30 MINUTES
ORDER BY created_at DESC
LIMIT 20
""")
display(m3)

# COMMAND ----------

# MAGIC %md
# MAGIC ## M3b — Section coverage % (aggregated)
# MAGIC `with_section / total` should be ≥ 0.90.

# COMMAND ----------

m3b = spark.sql("""
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN get_json_object(metadata,'$.section_1') IS NOT NULL THEN 1 ELSE 0 END) AS with_section,
  SUM(CASE WHEN get_json_object(metadata,'$.start_page') IS NOT NULL THEN 1 ELSE 0 END) AS with_start_page,
  SUM(CASE WHEN get_json_object(metadata,'$.end_page')   IS NOT NULL THEN 1 ELSE 0 END) AS with_end_page,
  SUM(CASE WHEN size(chunk_embedding) = 3072 THEN 1 ELSE 0 END) AS dim_3072,
  SUM(CASE WHEN size(chunk_embedding) <> 3072 THEN 1 ELSE 0 END) AS dim_other
FROM vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test
""")
display(m3b)

# COMMAND ----------

# MAGIC %md
# MAGIC ## M4 — Partial-ingestion guard (integrity fix proof)
# MAGIC Every `failed` doc must have `chunks_in_table = 0`.

# COMMAND ----------

m4 = spark.sql("""
SELECT m.document_id, m.chunk_status, COUNT(c.chunk_id) AS chunks_in_table
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test m
LEFT JOIN vaid.ai_std_con_field_service_report.vec_field_service_report_chunk_test c
  ON m.document_id = c.document_id
WHERE m.chunk_status = 'failed'
GROUP BY m.document_id, m.chunk_status
ORDER BY chunks_in_table DESC
""")
display(m4)

# COMMAND ----------

# MAGIC %md
# MAGIC ## M5 — Run-log rows (P1 + P2)
# MAGIC P2 writes one row per iteration at the end of the iteration. P1 writes one at job end.

# COMMAND ----------

m5 = spark.sql("""
SELECT run_id, job_name, start_time, end_time,
       docs_claimed, docs_succeeded, docs_failed, chunks_written,
       duration_seconds, error_summary
FROM vaid.ai_sot_field_service_report.fsr_run_log_chunk_test
ORDER BY start_time DESC
LIMIT 10
""")
display(m5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## M6 — DQ log findings (last 2 hours)
# MAGIC No FAIL severities expected. WARNs are acceptable.

# COMMAND ----------

m6 = spark.sql("""
SELECT severity, check_name, COUNT(*) AS n
FROM vaid.ai_sot_field_service_report.fsr_data_quality_log_chunk_test
WHERE created_at >= current_timestamp() - INTERVAL 2 HOURS
GROUP BY severity, check_name
ORDER BY severity, n DESC
""")
display(m6)

# COMMAND ----------

# MAGIC %md
# MAGIC ## M7 — Random sample of completed metadata rows (cross-doc audit prep)
# MAGIC Pick 5–10 of these and eyeball page 1 of the source PDF to confirm no contamination.

# COMMAND ----------

m7 = spark.sql("""
SELECT document_id, pdf_name, esn, equipment_sys_id, fsr_number,
       outage_start_date, event_type, volume_path
FROM vaid.ai_sot_field_service_report.biz_metadata_field_service_report_chunk_test
WHERE metadata_status='completed'
ORDER BY rand()
LIMIT 10
""")
display(m7)
