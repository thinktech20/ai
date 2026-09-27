{
    -- Databricks notebook source
    -- MAGIC %python
    -- MAGIC dbutils.widgets.text("source_schema", "")
    -- MAGIC dbutils.widgets.text("target_schema", "")
    -- MAGIC source_schema=dbutils.widgets.get("source_schema")
    -- MAGIC target_schema=dbutils.widgets.get("target_schema")

    -- COMMAND ----------

    CREATE TABLE IF NOT EXISTS .sot_ehs.ehs_dept_ref 
    AS
    SELECT
    CAST(business_id AS DECIMAL(38,18)) AS business_id,
    CAST(business_name AS STRING) AS business_name ,
    CAST(org_name AS STRING) AS org_name ,
    CAST(location AS STRING) AS location ,
    CAST(coe AS STRING) AS coe ,
    CAST(dept_id AS DECIMAL(38,18)) AS dept_id ,
    CAST(dept_sub_site AS STRING) AS dept_sub_site ,
    CAST(dept_mgr_name AS STRING) AS dept_mgr_name ,
    CAST(dept_ops_mgr_name AS STRING) AS dept_ops_mgr_name ,
    CAST(dept_country_name AS STRING) AS dept_country_name ,
    CAST(dept_region_name AS STRING) AS dept_region_name ,
    CAST(dept_created_date AS DATE) AS dept_created_date ,
    CAST(dept_archive_ind AS DECIMAL(38,18)) AS dept_archive_ind ,
    CAST(src_last_updated_date AS DATE) AS src_last_updated_date ,
    CAST(src_system_name AS STRING) AS src_system_name ,
    CAST(dl_load_func_name AS STRING) AS dl_load_func_name ,
    CAST(dl_load_date AS DATE) AS dl_load_date ,
    CAST(dl_update_date AS DATE) AS dl_update_date ,
    CAST(dl_created_by AS STRING) AS dl_created_by ,
    CAST(dl_updated_by AS STRING) AS dl_updated_by
    FROM .sot_ehs.ehs_dept_ref 

    -- COMMAND ----------

    -- select 'GP Table' as table_name, count(*) as count from gpfp.sot_ehs.ehs_dept_ref 
    -- union all
    -- select 'DBR Table' as table_name, count(*) as count from vgpd.sot_ehs.ehs_dept_ref

    -- COMMAND ----------


}
