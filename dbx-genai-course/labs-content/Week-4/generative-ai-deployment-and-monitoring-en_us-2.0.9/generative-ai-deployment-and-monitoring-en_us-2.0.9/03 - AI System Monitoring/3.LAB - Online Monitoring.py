# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img
# MAGIC     src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png"
# MAGIC     alt="Databricks Learning"
# MAGIC   >
# MAGIC </div>
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC # LAB - Online Monitoring
# MAGIC
# MAGIC In this lab, you will create an online monitor for a sample inference table using Databricks Lakehouse Monitoring. A sample inference table, extracted from a deployed Model Serving Endpoint, has been imported for you to use for monitoring.
# MAGIC
# MAGIC **Lab Outline:**
# MAGIC
# MAGIC *In this lab, you will need to complete the following tasks:*
# MAGIC
# MAGIC * **Task 1:** Define Evaluation Metrics
# MAGIC * **Task 2:** Unpack the Request Payload
# MAGIC * **Task 3:** Compute Metrics
# MAGIC * **Task 4:** Save the Processed Inference Table
# MAGIC * **Task 5:** Create a Monitor on the Inference Table
# MAGIC * **Task 6:** Review the Monitor Details
# MAGIC * **Task 7:** View the Monitor Dashboard

# COMMAND ----------

# MAGIC %md
# MAGIC ## REQUIRED - SELECT CLASSIC COMPUTE
# MAGIC Before executing cells in this notebook, please select your classic compute cluster in the lab. Be aware that **Serverless** is enabled by default.
# MAGIC
# MAGIC Follow these steps to select the classic compute cluster:
# MAGIC 1. Navigate to the top-right of this notebook and click the drop-down menu to select your cluster. By default, the notebook will use **Serverless**.
# MAGIC
# MAGIC 2. If your cluster is available, select it and continue to the next cell. If the cluster is not shown:
# MAGIC
# MAGIC    - Click **More** in the drop-down.
# MAGIC
# MAGIC    - In the **Attach to an existing compute resource** window, use the first drop-down to select your unique cluster.
# MAGIC
# MAGIC **NOTE:** If your cluster has terminated, you might need to restart it in order to select it. To do this:
# MAGIC
# MAGIC 1. Right-click on **Compute** in the left navigation pane and select *Open in new tab*.
# MAGIC
# MAGIC 2. Find the triangle icon to the right of your compute cluster name and click it.
# MAGIC
# MAGIC 3. Wait a few minutes for the cluster to start.
# MAGIC
# MAGIC 4. Once the cluster is running, complete the steps above to select your cluster.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Requirements
# MAGIC
# MAGIC Please review the following requirements before starting the lesson:
# MAGIC
# MAGIC * To run this notebook, you need to use one of the following Databricks runtime(s): **17.3.x-cpu-ml-scala2.13**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Classroom Setup
# MAGIC
# MAGIC Install required libraries and load classroom configuration.

# COMMAND ----------

# MAGIC %pip install -U -qq databricks-sdk textstat tiktoken evaluate

# COMMAND ----------

# MAGIC %pip install mlflow>=3.0 databricks-feature-engineering --upgrade
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-03

# COMMAND ----------

# MAGIC %md
# MAGIC ## Inference Table
# MAGIC
# MAGIC You are going to use the same inference table that we used for the demo. The inference table is pre-loaded and ready to be used.

# COMMAND ----------

inference_table_name = f"{DA.catalog_name}.{DA.schema_name}.rag_app_realtime_payload"
display(spark.sql(f"SELECT * FROM {inference_table_name}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 1: Define Evaluation Metrics
# MAGIC In this task, you will define evaluation metrics such as toxicity, perplexity, and readability, which will be used to analyze the inference table data.
# MAGIC
# MAGIC -  Define the evaluation metrics functions using `pandas_udf`.

# COMMAND ----------

##

## Import necessary libraries
import tiktoken, textstat, evaluate
import pandas as pd
from pyspark.sql.functions import pandas_udf

## Define a pandas UDF to compute the number of tokens in the text
@pandas_udf("int")
def compute_num_tokens(texts: pd.Series) -> pd.Series:
  encoding = tiktoken.get_encoding("cl100k_base")
  return pd.Series(map(len, encoding.encode_batch(texts)))

## Define a pandas UDF to compute the toxicity of the text
@pandas_udf("double")
def compute_toxicity(texts: pd.Series) -> pd.Series:
  ## Omit entries with null input from evaluation
  toxicity = evaluate.load("toxicity", module_type="measurement", cache_dir="/tmp/hf_cache/")
  return pd.Series(toxicity.compute(predictions=texts.fillna(""))["toxicity"]).where(texts.notna(), None)

## Define a pandas UDF to compute the perplexity of the text
@pandas_udf("double")
def compute_perplexity(texts: pd.Series) -> pd.Series:
  ## Omit entries with null input from evaluation
  perplexity = evaluate.load("perplexity", module_type="measurement", cache_dir="/tmp/hf_cache/")
  return pd.Series(perplexity.compute(data=texts.fillna(""), model_id="gpt2")["perplexities"]).where(texts.notna(), None)

# COMMAND ----------

# MAGIC %skip
# MAGIC ##
# MAGIC
# MAGIC ## Import necessary libraries
# MAGIC import tiktoken, textstat, evaluate
# MAGIC import pandas as pd
# MAGIC from pyspark.sql.functions import pandas_udf
# MAGIC
# MAGIC ## Define a pandas UDF to compute the number of tokens in the text
# MAGIC @pandas_udf("int")
# MAGIC def compute_num_tokens(texts: pd.Series) -> pd.Series:
# MAGIC   encoding = tiktoken.get_encoding("cl100k_base")
# MAGIC   return pd.Series(map(len, encoding.encode_batch(texts)))
# MAGIC
# MAGIC ## Define a pandas UDF to compute the toxicity of the text
# MAGIC @pandas_udf("double")
# MAGIC def compute_toxicity(texts: pd.Series) -> pd.Series:
# MAGIC   ## Omit entries with null input from evaluation
# MAGIC   toxicity = evaluate.load("toxicity", module_type="measurement", cache_dir="/tmp/hf_cache/")
# MAGIC   return pd.Series(toxicity.compute(predictions=texts.fillna(""))["toxicity"]).where(texts.notna(), None)
# MAGIC
# MAGIC ## Define a pandas UDF to compute the perplexity of the text
# MAGIC @pandas_udf("double")
# MAGIC def compute_perplexity(texts: pd.Series) -> pd.Series:
# MAGIC   ## Omit entries with null input from evaluation
# MAGIC   perplexity = evaluate.load("perplexity", module_type="measurement", cache_dir="/tmp/hf_cache/")
# MAGIC   return pd.Series(perplexity.compute(data=texts.fillna(""), model_id="gpt2")["perplexities"]).where(texts.notna(), None)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 2: Unpack the Request Payload
# MAGIC In this task, you will unpack the request payload from the inference table and prepare it for processing.
# MAGIC
# MAGIC **Steps:**
# MAGIC
# MAGIC - Unpack the requests as a stream.
# MAGIC - Drop unnecessary columns for monitoring jobs.

# COMMAND ----------

##

import os

## Reset checkpoint [for demo purposes ONLY]
checkpoint_location = os.path.join(DA.paths.working_dir, "checkpoint")
dbutils.fs.rm(checkpoint_location, True)

## Define the JSON path and type for the input requests
INPUT_REQUEST_JSON_PATH = "inputs[*].query"
INPUT_JSON_PATH_TYPE = "array<string>"
KEEP_LAST_QUESTION_ONLY = False

## Define the JSON path and type for the output responses
OUTPUT_REQUEST_JSON_PATH = "predictions"
OUPUT_JSON_PATH_TYPE = "array<string>"

## Unpack the requests as a stream.
requests_raw_df = spark.readStream.table(inference_table_name)
requests_processed_df = unpack_requests(
    requests_raw_df,
    INPUT_REQUEST_JSON_PATH,
    INPUT_JSON_PATH_TYPE,
    OUTPUT_REQUEST_JSON_PATH,
    OUPUT_JSON_PATH_TYPE,
    KEEP_LAST_QUESTION_ONLY
)

## Drop un-necessary columns for monitoring jobs
requests_processed_df = requests_processed_df.drop("date", "status_code", "sampling_fraction", "client_request_id", "databricks_request_id")

# COMMAND ----------

# MAGIC %skip
# MAGIC ## 
# MAGIC import os
# MAGIC
# MAGIC ## Reset checkpoint [for demo purposes ONLY]
# MAGIC checkpoint_location = os.path.join(DA.paths.working_dir, "checkpoint")
# MAGIC dbutils.fs.rm(checkpoint_location, True)
# MAGIC
# MAGIC ## Define the JSON path and type for the input requests
# MAGIC INPUT_REQUEST_JSON_PATH = "inputs[*].query"
# MAGIC INPUT_JSON_PATH_TYPE = "array<string>"
# MAGIC KEEP_LAST_QUESTION_ONLY = False
# MAGIC
# MAGIC ## Define the JSON path and type for the output responses
# MAGIC OUTPUT_REQUEST_JSON_PATH = "predictions"
# MAGIC OUPUT_JSON_PATH_TYPE = "array<string>"
# MAGIC
# MAGIC ## Unpack the requests as a stream.
# MAGIC requests_raw_df = spark.readStream.table(inference_table_name)
# MAGIC requests_processed_df = unpack_requests(
# MAGIC     requests_raw_df,
# MAGIC     INPUT_REQUEST_JSON_PATH,
# MAGIC     INPUT_JSON_PATH_TYPE,
# MAGIC     OUTPUT_REQUEST_JSON_PATH,
# MAGIC     OUPUT_JSON_PATH_TYPE,
# MAGIC     KEEP_LAST_QUESTION_ONLY
# MAGIC )
# MAGIC
# MAGIC ## Drop un-necessary columns for monitoring jobs
# MAGIC requests_processed_df = requests_processed_df.drop("date", "status_code", "sampling_fraction", "client_request_id", "databricks_request_id")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 3: Compute Metrics
# MAGIC
# MAGIC In this task, you will compute the defined evaluation metrics for the unpacked request payloads.
# MAGIC
# MAGIC - Compute the toxicity, perplexity, and token count for the input and output columns.

# COMMAND ----------

##
## Define the columns to measure
column_to_measure = ["input", "output"]

## Iterate over each column to measure
for column_name in column_to_measure:
    ## Compute the metrics and add them as new columns to the DataFrame
    requests_df_with_metrics = (
      requests_processed_df
                 .withColumn(f"toxicity({column_name})", compute_toxicity(col(column_name))) 
                 .withColumn(f"perplexity({column_name})", compute_perplexity(col(column_name))) 
                 .withColumn(f"token_count({column_name})", compute_num_tokens(col(column_name))) 
    )

# COMMAND ----------

# MAGIC %skip
# MAGIC ## Define the columns to measure
# MAGIC column_to_measure = ["input", "output"]
# MAGIC
# MAGIC ## Iterate over each column to measure
# MAGIC for column_name in column_to_measure:
# MAGIC     ## Compute the metrics and add them as new columns to the DataFrame
# MAGIC     requests_df_with_metrics = (
# MAGIC       requests_processed_df
# MAGIC                  .withColumn(f"toxicity({column_name})", compute_toxicity(col(column_name))) 
# MAGIC                  .withColumn(f"perplexity({column_name})", compute_perplexity(col(column_name))) 
# MAGIC                  .withColumn(f"token_count({column_name})", compute_num_tokens(col(column_name))) 
# MAGIC     )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 4: Save the Processed Inference Table
# MAGIC
# MAGIC In this task, you will save the processed inference table with the computed metrics to a Delta table.
# MAGIC
# MAGIC **Steps:**
# MAGIC
# MAGIC - Create the processed inference table if it doesn't exist.
# MAGIC - Append the new unpacked payloads and metrics to the processed table.

# COMMAND ----------

##

from delta.tables import DeltaTable
## Define the name of the processed table
processed_table_name = f"{DA.catalog_name}.{DA.schema_name}.rag_app_processed_inferences_lab"

## Create the table if it does not exist
(DeltaTable.createOrReplace(spark)
        .tableName(processed_table_name)
        .addColumns(requests_df_with_metrics.schema)
        .property("delta.enableChangeDataFeed", "true")
        .property("delta.columnMapping.mode", "name")
        .execute())
## Write the requests_df_with_metrics DataFrame to the processed table as a stream
(requests_df_with_metrics.writeStream
                      .trigger(availableNow=True)
                      .format("delta")
                      .outputMode("append")
                      .option("checkpointLocation", checkpoint_location)
                      .toTable(processed_table_name).awaitTermination())

# COMMAND ----------

# MAGIC %skip
# MAGIC ##
# MAGIC
# MAGIC from delta.tables import DeltaTable
# MAGIC ## Define the name of the processed table
# MAGIC processed_table_name = f"{DA.catalog_name}.{DA.schema_name}.rag_app_processed_inferences_lab"
# MAGIC
# MAGIC ## Create the table if it does not exist
# MAGIC (DeltaTable.createOrReplace(spark)
# MAGIC         .tableName(processed_table_name)
# MAGIC         .addColumns(requests_df_with_metrics.schema)
# MAGIC         .property("delta.enableChangeDataFeed", "true")
# MAGIC         .property("delta.columnMapping.mode", "name")
# MAGIC         .execute())
# MAGIC ## Write the requests_df_with_metrics DataFrame to the processed table as a stream
# MAGIC (requests_df_with_metrics.writeStream
# MAGIC                       .trigger(availableNow=True)
# MAGIC                       .format("delta")
# MAGIC                       .outputMode("append")
# MAGIC                       .option("checkpointLocation", checkpoint_location)
# MAGIC                       .toTable(processed_table_name).awaitTermination())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 5: Create a Monitor on the Inference Table
# MAGIC
# MAGIC In this task, you will create a monitor on the processed inference table using Databricks Lakehouse Monitoring.
# MAGIC
# MAGIC - Create a monitor using the `databricks-sdk`.

# COMMAND ----------

##

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import MonitorTimeSeries
## Initialize the workspace client
w = WorkspaceClient()

try:
  ## Create a monitor using the workspace client's quality_monitors service
  lhm_monitor = w.quality_monitors.create(
    table_name=processed_table_name,
    time_series = MonitorTimeSeries(
      timestamp_col = "timestamp",
      granularities = ["5 minutes"],
    ),
    assets_dir = os.getcwd(),
    slicing_exprs = ["model_id"],
    output_schema_name=f"{DA.catalog_name}.{DA.schema_name}"
  )

## Handle any exceptions that occur during monitor creation
except Exception as lhm_exception:
  print(lhm_exception)

# COMMAND ----------

# MAGIC %skip
# MAGIC ##
# MAGIC
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC from databricks.sdk.service.catalog import MonitorTimeSeries
# MAGIC ## Initialize the workspace client
# MAGIC w = WorkspaceClient()
# MAGIC
# MAGIC try:
# MAGIC   ## Create a monitor using the workspace client's quality_monitors service
# MAGIC   lhm_monitor = w.quality_monitors.create(
# MAGIC     table_name=processed_table_name,
# MAGIC     time_series = MonitorTimeSeries(
# MAGIC       timestamp_col = "timestamp",
# MAGIC       granularities = ["5 minutes"],
# MAGIC     ),
# MAGIC     assets_dir = os.getcwd(),
# MAGIC     slicing_exprs = ["model_id"],
# MAGIC     output_schema_name=f"{DA.catalog_name}.{DA.schema_name}"
# MAGIC   )
# MAGIC
# MAGIC ## Handle any exceptions that occur during monitor creation
# MAGIC except Exception as lhm_exception:
# MAGIC   print(lhm_exception)

# COMMAND ----------

##

from databricks.sdk.service.catalog import MonitorInfoStatus

## Get the monitor information for the processed table
monitor_info = w.quality_monitors.get(processed_table_name)
print(monitor_info.status)

## Check if the monitor status is pending
if monitor_info.status == MonitorInfoStatus.MONITOR_STATUS_PENDING:
    print("Wait until monitor creation is completed...")

# COMMAND ----------

# MAGIC %skip
# MAGIC ##
# MAGIC
# MAGIC from databricks.sdk.service.catalog import MonitorInfoStatus
# MAGIC
# MAGIC ## Get the monitor information for the processed table
# MAGIC monitor_info = w.quality_monitors.get(processed_table_name)
# MAGIC print(monitor_info.status)
# MAGIC
# MAGIC ## Check if the monitor status is pending
# MAGIC if monitor_info.status == MonitorInfoStatus.MONITOR_STATUS_PENDING:
# MAGIC     print("Wait until monitor creation is completed...")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 6: Review the Monitor Details
# MAGIC
# MAGIC In this task, you will review the details of the monitor created in the previous step. This will involve checking the **Quality** tab for the monitor details and reviewing the metrics tables generated by the monitor.
# MAGIC
# MAGIC **Steps:**
# MAGIC
# MAGIC
# MAGIC Complete following steps:
# MAGIC
# MAGIC
# MAGIC 1. **Review Monitor Details in Quality Tab**
# MAGIC    - Go to the **[Catalog](explore/data)** and find the table you monitored.
# MAGIC    - Click on the **Quality** tab to view the monitor details.
# MAGIC
# MAGIC 2. **Review Metrics Tables**
# MAGIC    - Examine the metrics tables (`*_processed_profile_metrics` and `*_processed_drift_metrics`).
# MAGIC
# MAGIC
# MAGIC **🚨Note:** Ensure that the refresh process is completed and the metrics tables are ready before reviewing the details.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 7: View the Monitor Dashboard
# MAGIC
# MAGIC In this task, you will view the Databricks SQL dashboard generated by Lakehouse Monitoring to review the data and metrics of your monitoring solution.
# MAGIC
# MAGIC **Steps:**
# MAGIC
# MAGIC Complete following steps:
# MAGIC
# MAGIC 1. **View the SQL Dashboard**
# MAGIC    - Click on **View Dashboard** to open the SQL dashboard from the **Quality** tab.
# MAGIC
# MAGIC 2. **Inspect Overall Summary Statistics**
# MAGIC    - Examine the overall summary statistics presented in the dashboard.
# MAGIC
# MAGIC 3. **Review the Created Metrics**
# MAGIC    - Review the metrics that were created in the first step of this lab to understand the data quality and model performance over time.
# MAGIC
# MAGIC
# MAGIC **🚨Note:** Make sure there is an accessible DBSQL cluster up and running to ensure dashboard creation.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC In this lab, you created an online monitor using Databricks Lakehouse Monitoring. First, you defined evaluation metrics and computed these metrics for the inference table. Then, you created a monitor on the inference table. Lastly, you reviewed the monitor details and the auto-created Databricks SQL dashboard. After successfully completing this lab, you should be able to create online monitoring for an inference table that captures the inference requests of deployed AI models.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>