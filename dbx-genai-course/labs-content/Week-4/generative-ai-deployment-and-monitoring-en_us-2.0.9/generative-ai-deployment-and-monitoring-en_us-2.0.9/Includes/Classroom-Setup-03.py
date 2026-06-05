# Databricks notebook source
# MAGIC %run ./Classroom-Setup-Common

# COMMAND ----------

DA = DBAcademyHelper()
DA.init()

# COMMAND ----------

import time
import re
import io
from pyspark.sql import DataFrame, functions as F
from pyspark.sql.functions import col, pandas_udf, transform, size, element_at


def unpack_requests(requests_raw: DataFrame, 
                    input_request_json_path: str, 
                    input_json_path_type: str, 
                    output_request_json_path: str, 
                    output_json_path_type: str,
                    keep_last_question_only: False) -> DataFrame:
    # Rename the date column and convert the timestamp milliseconds to TimestampType for downstream processing.
    requests_timestamped = (requests_raw
        .withColumn("timestamp", (col("timestamp_ms") / 1000))
        .drop("timestamp_ms"))

    # Convert the model name and version columns into a model identifier column.
    requests_identified = requests_timestamped.withColumn(
        "model_id",
        F.concat(
            col("request_metadata").getItem("model_name"),
            F.lit("_"),
            col("request_metadata").getItem("model_version")
        )
    )

    # Filter out the non-successful requests.
    requests_success = requests_identified.filter(col("status_code") == "200")

    # Unpack JSON.
    requests_unpacked = (requests_success
        .withColumn("request", F.from_json(F.expr(f"request:{input_request_json_path}"), input_json_path_type))
        .withColumn("response", F.from_json(F.expr(f"response:{output_request_json_path}"), output_json_path_type)))
    
    if keep_last_question_only:
        requests_unpacked = requests_unpacked.withColumn("request", F.array(F.element_at(F.col("request"), -1)))

    # Explode batched requests into individual rows.
    requests_exploded = (requests_unpacked
        .withColumn("__db_request_response", F.explode(F.arrays_zip(col("request").alias("input"), col("response").alias("output"))))
        .selectExpr("* except(__db_request_response, request, response, request_metadata)", "__db_request_response.*")
        )

    return requests_exploded

# COMMAND ----------

# Manual re-creation of inference table as delta table with correct schema (when read from .csv source)
import pandas as pd
from datetime import datetime, timedelta, UTC
from pyspark.sql.functions import col, from_json, to_date, current_date, expr
from pyspark.sql.types import IntegerType, MapType, LongType, StringType

inferences_df = spark.read.load(f'{DA.paths.datasets.arxiv}/inference-sample')

yesterday = datetime.now(UTC) + timedelta(days=-11)
yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
millis_yesterday_start = int(yesterday_start .timestamp() * 1000)

# inferences_processed_df = inferences_df.withColumn("client_request_id", col("client_request_id").cast(StringType())) \
#                                        .withColumn("date", to_date(expr("date_sub(current_date(), 10)"))) \
#                                        .withColumn("timestamp_ms", (col("timestamp_ms") % 86400000) + millis_yesterday_start ) \
#                                        .withColumn("status_code", col("status_code").cast(IntegerType())) \
#                                        .withColumn("execution_time_ms", col("execution_time_ms").cast(LongType())) \
#                                        .withColumn("request_metadata", from_json("request_metadata", MapType(StringType(), StringType())))

inferences_processed_df = inferences_df.withColumn("date", to_date(expr("date_sub(current_date(), 10)"))) \
                                       .withColumn("timestamp_ms", (col("timestamp_ms") % 86400000) + millis_yesterday_start )

inferences_processed_df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{DA.catalog_name}.{DA.schema_name}.rag_app_realtime_payload")