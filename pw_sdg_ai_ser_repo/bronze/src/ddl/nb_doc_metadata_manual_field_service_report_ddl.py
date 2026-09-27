# Databricks notebook source
# MAGIC %md
# MAGIC Import Libraries 

# COMMAND ----------

import sys
 
try:
    # First attempt to import from the common path
    from common.common_utils import *
except ImportError:
    try:
        # If the first import fails, append the first alternative path and try again
        sys.path.append("/Workspace/Users/d44c1af5-e99e-4010-8302-464e74d13ba1/.bundle/FSR/files")
        from common.common_utils import *
    except ImportError:
        # If the second import fails, append the second alternative path and try again
        sys.path.append("/Workspace/Users/d44c1af5-e99e-4010-8302-464e74d13ba1/.bundle/FSR/files")
        from common.common_utils import *

# COMMAND ----------

dropQuery= f"""DROP TABLE IF EXISTS {viu_catalog}.{ing_ud_fsr_manual}.doc_metadata_manual_field_service_report"""

spark.sql(dropQuery)

# COMMAND ----------

# MAGIC %md
# MAGIC DDL QUERY

# COMMAND ----------

createQuery=f"""CREATE TABLE {viu_catalog}.{ing_ud_fsr_manual}.doc_metadata_manual_field_service_report
(
    file_id STRING,
    file_name STRING,
    file_extension STRING,
    file_size STRING,
    file_creation_time TIMESTAMP,
     file_modification_time TIMESTAMP,
    s3_file_path STRING,
    extracted_object_name STRING,
    volume_location STRING
) USING delta
TBLPROPERTIES
(  
    'delta.autoOptimize.optimizeWrite' = 'true',  
    'delta.enableChangeDataFeed' = 'true',  
    'delta.feature.allowColumnDefaults' = 'supported',  
    'delta.feature.changeDataFeed' = 'supported',  
    'delta.feature.timestampNtz' = 'supported',  
    'delta.minReaderVersion' = '3',  
    'delta.minWriterVersion' = '7',
    'delta.columnMapping.mode' = 'name'
)"""
#executing the Create query
query_create=spark.sql(createQuery)

# COMMAND ----------

# MAGIC %md
# MAGIC Alter Query

# COMMAND ----------

alterQuery = f"""ALTER table  {viu_catalog}.{ing_ud_fsr_manual}.doc_metadata_manual_field_service_report SET TAGS ('domain' = 'Operations and SWE', 'sub_domain_code' = 'FSR', 'sot_flag' = 'sot_fsr', 'table_type' = 'CSOT');"""

#Executing the Alter query
spark.sql(alterQuery)
