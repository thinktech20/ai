%pip install openpyxl

import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, monotonically_increasing_id, trim, concat, lit, upper, regexp_replace
)
from pyspark.sql.types import StringType

import time

start_time = time.time()

# Initialize Spark
spark = SparkSession.builder.getOrCreate()

# Paths
fsr_xl_path = "/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/llm_filtered_title_2016_Vinayaka_230_17Mar.xlsx"
text_output_path = "/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/fsr_enriched_2016_Vinayaka_230_17Mar.txt"

# Step 1: Load Excel into pandas and normalize column names for internal processing
fsr_pd = pd.read_excel(fsr_xl_path)
fsr_pd = fsr_pd.rename(columns={
    "ESN": "esn",
    "Equipment Sys ID": "equipment_sys_id",
    "Equipment Type": "equipment_type",
    "Equipment Class / Code": "equipment_sub_class",
    "EV Project ID": "ev_project_id",
    "EV Equipment Event ID": "ev_equipment_event_id",
    "Event Type": "ev_event_type",
    "OFS Event ID": "ofs_event_id",
    "FSP project ID": "fsp_project_id",
    "Outage Start Date": "p6_outage_start_date",
    "Outage End Date": "p6_outage_end_date"
})

# Preserve original Excel column names for final export
original_excel_cols = list(pd.read_excel(fsr_xl_path).columns)

# Step 2: Convert to Spark DataFrame and add row index
fsr_df = spark.createDataFrame(fsr_pd)
fsr_df = fsr_df.select([col(c).cast(StringType()).alias(c) for c in fsr_df.columns])

# Trim blanks and normalize IDs
fsr_df = (
    fsr_df
    .withColumn("ev_project_id", trim(col("ev_project_id")))
    .withColumn("ev_equipment_event_id", trim(col("ev_equipment_event_id")))
    .withColumn("ofs_event_id", trim(col("ofs_event_id")))
    .withColumn("fsp_project_id", trim(col("fsp_project_id")))
    # strip FSP- prefix for join
    .withColumn("fsp_project_id_stripped", regexp_replace(col("fsp_project_id"), "FSP-", ""))
    # strip EV- / EVP- prefixes for join
    .withColumn("ev_project_id_stripped", regexp_replace(col("ev_project_id"), "EVP-", ""))
    .withColumn("ev_equipment_event_id_stripped", regexp_replace(col("ev_equipment_event_id"), "EV-", ""))
    .withColumn("row_index", monotonically_increasing_id())
)

# Step 3: Load IBAT Equipment Master and rename overlapping columns
ibat_equipment = spark.read.table("vgpd.prm_std_views.ibat_equipment_mst") \
    .withColumnRenamed("equipment_sys_id", "ibat_equipment_sys_id") \
    .withColumnRenamed("equipment_type", "ibat_equipment_type") \
    .withColumnRenamed("equipment_sub_class", "ibat_equipment_sub_class") \
    .withColumnRenamed("equip_serial_number", "ibat_equip_serial_number")

ibat_equipment = ibat_equipment.select([col(c).cast(StringType()).alias(c) for c in ibat_equipment.columns])
ibat_equipment = (
    ibat_equipment
    .withColumn("ibat_equipment_sys_id", upper(trim(col("ibat_equipment_sys_id"))))
    .withColumn("ibat_equip_serial_number", upper(trim(col("ibat_equip_serial_number"))))
)

# Step 4: Join with IBAT
enriched = (
    fsr_df.join(
        ibat_equipment,
        (fsr_df["equipment_sys_id"] == ibat_equipment["ibat_equipment_sys_id"]) |
        (fsr_df["esn"] == ibat_equipment["ibat_equip_serial_number"]),
        "left"
    )
)

# Step 5: Fill missing values from IBAT
enriched = (
    enriched
    .withColumn("esn",
        when((col("esn").isNull()) | (col("esn") == ""), col("ibat_equip_serial_number"))
        .otherwise(col("esn")))
    .withColumn("equipment_sys_id",
        when((col("equipment_sys_id").isNull()) | (col("equipment_sys_id") == ""), col("ibat_equipment_sys_id"))
        .otherwise(col("equipment_sys_id")))
    .withColumn("equipment_type",
        when((col("equipment_type").isNull()) | (col("equipment_type") == ""), col("ibat_equipment_type"))
        .otherwise(col("equipment_type")))
    .withColumn("equipment_sub_class",
        when((col("equipment_sub_class").isNull()) | (col("equipment_sub_class") == ""), col("ibat_equipment_sub_class"))
        .otherwise(col("equipment_sub_class")))
)

# Step 6: Load Event Vision SOT table and rename overlapping columns
event_sot = spark.read.table("vgpd.fsr_std_views.eventmgmt_event_vision_sot") \
    .withColumnRenamed("ev_project_id", "sot_ev_project_id") \
    .withColumnRenamed("ev_equipment_event_id", "sot_ev_equipment_event_id") \
    .withColumnRenamed("ev_gtm_id", "sot_ev_gtm_id") \
    .withColumnRenamed("fsp_project_id", "sot_fsp_project_id") \
    .withColumnRenamed("ev_event_type", "sot_ev_event_type") \
    .withColumnRenamed("p6_outage_start_date", "sot_outage_start_date") \
    .withColumnRenamed("p6_outage_end_date", "sot_outage_end_date")

event_sot = event_sot.select([col(c).cast(StringType()).alias(c) for c in event_sot.columns])

# Step 7: Join with Event Vision SOT using EV, EVP, OFS, and FSP keys
enriched = (
    enriched.join(
        event_sot,
        (enriched["ev_project_id_stripped"] == event_sot["sot_ev_project_id"]) |   # EVP match
        (enriched["ev_equipment_event_id_stripped"] == event_sot["sot_ev_equipment_event_id"]) | # EV match
        (enriched["ofs_event_id"] == event_sot["sot_ev_gtm_id"]) |
        (enriched["fsp_project_id_stripped"] == event_sot["sot_fsp_project_id"]),
        "left"
    )
)

# Step 8: Fill missing values from Event Vision SOT
enriched = (
    enriched
    .withColumn("ev_project_id",
        when((col("ev_project_id").isNull()) | (col("ev_project_id") == ""),
             concat(lit("EVP-"), col("sot_ev_project_id")))
        .otherwise(col("ev_project_id")))
    .withColumn("ev_equipment_event_id",
        when((col("ev_equipment_event_id").isNull()) | (col("ev_equipment_event_id") == ""),
             concat(lit("EV-"), col("sot_ev_equipment_event_id")))
        .otherwise(col("ev_equipment_event_id")))
    .withColumn("ofs_event_id",
        when((col("ofs_event_id").isNull()) | (col("ofs_event_id") == ""), col("sot_ev_gtm_id"))
        .otherwise(col("ofs_event_id")))
    .withColumn("fsp_project_id",
        when((col("fsp_project_id").isNull()) | (col("fsp_project_id") == ""),
             concat(lit("FSP-"), col("sot_fsp_project_id")))
        .otherwise(col("fsp_project_id")))
    .withColumn("ev_event_type",
        when((col("ev_event_type").isNull()) | (col("ev_event_type") == ""), col("sot_ev_event_type"))
        .otherwise(col("ev_event_type")))
    .withColumn("p6_outage_start_date",
        when((col("p6_outage_start_date").isNull()) | (col("p6_outage_start_date") == ""), col("sot_outage_start_date"))
        .otherwise(col("p6_outage_start_date")))
    .withColumn("p6_outage_end_date",
        when((col("p6_outage_end_date").isNull()) | (col("p6_outage_end_date") == ""), col("sot_outage_end_date"))
        .otherwise(col("p6_outage_end_date")))
)

# Step 9: Select only original Excel columns + row_index
enriched = enriched.select([col(c) for c in fsr_pd.columns] + [col("row_index")])

# Step 10: Restore row order and drop row_index
enriched = enriched.orderBy("row_index").drop("row_index")

# Step 11: Convert to Pandas and save as plain text (CSV-style) with original Excel headers
enriched_pd = enriched.toPandas()

with open(text_output_path, "w", encoding="utf-8") as f:
    f.write(",".join(original_excel_cols) + "\n")
    for row in enriched_pd.itertuples(index=False):
        f.write(",".join([str(x) if x is not None else "" for x in row]) + "\n")

print(f"✅ Enrichment complete. Final text file saved to {text_output_path}")

end_time = time.time()
execution_time = end_time - start_time
print(f"Execution time: {execution_time} seconds")
