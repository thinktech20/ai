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

# MAGIC %md
# MAGIC #Meta data insert scripts 

# COMMAND ----------

from pyspark.sql import Row
from pyspark.sql import functions as F

VOLUME_PATH = f"/Volumes/{viu_catalog}/{ing_ud_spec}/spec_boroscope_insp_field_service_report"
TARGET_TABLE = f"{viu_catalog}.{ing_ud_spec}.doc_metadata_spec_boroscope_insp_field_service_report"

S3_BASE_PATH = f"s3://{viu_bucket}/{ing_ud_spec}/spec_boroscope_insp_field_service_report"
S3_BASE_PATH = S3_BASE_PATH.rstrip("/") + "/"

def list_files_recursive(path: str):
    files = []
    stack = [path.rstrip("/") + "/"]
    while stack:
        p = stack.pop()
        for x in dbutils.fs.ls(p):
            if x.isDir():
                stack.append(x.path)
            else:
                files.append(x)
    return files

items = list_files_recursive(VOLUME_PATH)

rows = []
for x in items:
    rows.append(Row(
        vol_path=x.path,
        file_name=x.name,
        length_bytes=int(x.size) if x.size is not None else None
    ))

df = spark.createDataFrame(rows)

meta_df = (
    df
    .withColumn("file_name", F.col("file_name"))
    .withColumn("file_extension", F.lit(".pdf"))
    .withColumn("file_id", F.regexp_replace(F.col("file_name"), r"\.[^.]+$", ""))
    .withColumn(
        "file_size",
        F.concat(F.round(F.col("length_bytes") / (1024 * 1024), 2).cast("string"), F.lit(" MB"))
    )
    .withColumn("file_creation_time", F.current_timestamp())
    .withColumn("file_modification_time", F.lit(None).cast("timestamp"))
    .withColumn("s3_file_path", F.lit(S3_BASE_PATH))
    .withColumn("extracted_object_name", F.col("file_name"))
    .withColumn("volume_location", F.lit(VOLUME_PATH.rstrip("/") + "/"))
    .select(
        "file_id", "file_name", "file_extension", "file_size",
        "file_creation_time", "file_modification_time",
        "s3_file_path", "extracted_object_name", "volume_location"
    )
)

existing_df = (
    spark.table(TARGET_TABLE)
    .select(F.lower(F.trim(F.col("extracted_object_name"))).alias("existing_file_name"))
    .distinct()
)

missing_meta_df = (
    meta_df.alias("m")
    .join(
        existing_df.alias("e"),
        F.lower(F.trim(F.col("m.extracted_object_name"))) == F.col("e.existing_file_name"),
        "left_anti"
    )
)

print("Total files from volume:", meta_df.count())
print("Already existing in target table:", existing_df.count())
print("Missing files to load:", missing_meta_df.count())

missing_meta_df.write.mode("append").saveAsTable(TARGET_TABLE)
print("Loaded only missing files into:", TARGET_TABLE)
