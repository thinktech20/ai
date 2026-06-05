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
# MAGIC
# MAGIC # LAB- Evaluation with Mosaic AI Agent Evaluation
# MAGIC
# MAGIC In this lab, you will have the opportunity to evaluate a RAG chain model **using Mosaic AI Agent Evaluation Framework.**
# MAGIC
# MAGIC **Lab Outline:**
# MAGIC
# MAGIC *In this lab, you will complete the following tasks:*
# MAGIC
# MAGIC - **Task 1**: Define a custom Gen AI evaluation metric.
# MAGIC
# MAGIC - **Task 2**: Conduct an evaluation test using the Agent Evaluation Framework.
# MAGIC
# MAGIC - **Task 3**: Analyze the evaluation results through the user interface.

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
# MAGIC * To run this notebook, you need to use one of the following Databricks runtime(s): **15.4.x-cpu-ml-scala2.12**
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Classroom Setup
# MAGIC
# MAGIC Install required libraries.

# COMMAND ----------

# MAGIC %pip install -U -qq databricks-agents databricks-sdk databricks-vectorsearch langchain==0.3.7 databricks-langchain mlflow-skinny[databricks]==3.4.0
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC Before starting the lab, run the provided classroom setup script. This script will define configuration variables necessary for the lab. Execute the following cell:

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-04

# COMMAND ----------

# MAGIC %md
# MAGIC **Other Conventions:**
# MAGIC
# MAGIC Throughout this lab, we'll refer to the object `DA`. This object, provided by Databricks Academy, contains variables such as your username, catalog name, schema name, working directory, and dataset locations. Run the code block below to view these details:

# COMMAND ----------

print(f"Username:          {DA.username}")
print(f"Catalog Name:      {DA.catalog_name}")
print(f"Schema Name:       {DA.schema_name}")
print(f"Working Directory: {DA.paths.working_dir}")
print(f"Dataset Location:  {DA.paths.datasets}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Lab Overview
# MAGIC
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Evaluation Dataset
# MAGIC
# MAGIC In this lab, you will work with the same dataset utilized in the demos. This dataset contains sample queries along with their corresponding expected responses, which are generated using synthetic data.

# COMMAND ----------

display(DA.eval_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load the Model
# MAGIC
# MAGIC A RAG chain has been created and registered for use in this lab. The model details are provided below.
# MAGIC
# MAGIC **📌 Note:** If you are using your own workspace to run this lab, you must manually execute **`00 - Build Model / 00-Build Model`**.

# COMMAND ----------

import mlflow

catalog_name = "genai_shared_catalog_03"
schema_name = f"ws_{spark.conf.get('spark.databricks.clusterUsageTags.clusterOwnerOrgId')}"

mlflow.set_registry_uri("databricks-uc")

model_uri = f"models:/{catalog_name}.{schema_name}.rag_app/1"
model_name = f"{catalog_name}.{schema_name}.rag_app"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 1 - Define A Custom Metric
# MAGIC
# MAGIC For this task, define a custom metric to evaluate whether the generated **"ANSWER"** from the RAG chain is easily readable by a non-expert user.

# COMMAND ----------

from mlflow.metrics.genai import make_genai_metric_from_prompt

## Prompt for LLM as judge to determine if the generated response is easily readable by non-academic or expert readers
eval_prompt = "Your task is to determine whether the generated response easily readable by non-academic or expert readers. This was the content: '{retrieved_context}'"

## Use Llama-3 as LLM
llm="endpoints:/databricks-meta-llama-3-3-70b-instruct"

## Define the metric
is_readable = <FILL_IN>

# COMMAND ----------

# MAGIC %skip
# MAGIC from mlflow.metrics.genai import make_genai_metric_from_prompt
# MAGIC
# MAGIC ## Prompt for LLM as judge to determine if the generated response is easily readable by non-academic or expert readers
# MAGIC eval_prompt = "Your task is to determine whether the generated response easily readable by non-academic or expert readers. This was the content: '{retrieved_context}'"
# MAGIC
# MAGIC ## Use Llama-3 as LLM
# MAGIC llm="endpoints:/databricks-meta-llama-3-3-70b-instruct"
# MAGIC
# MAGIC ## Define the metric
# MAGIC is_readable = make_genai_metric_from_prompt(
# MAGIC     name="is_readable",
# MAGIC     judge_prompt=eval_prompt,
# MAGIC     model=llm,
# MAGIC     metric_metadata={"assessment_type": "ANSWER"},
# MAGIC )

# COMMAND ----------

# MAGIC %md
# MAGIC ##Task 2 - Run Evaluation Test
# MAGIC
# MAGIC Next, run an evaluation using the custom metric you defined. Ensure that you select **Mosaic AI Agent Evaluation** as the evaluation type.
# MAGIC

# COMMAND ----------

with <FILL_IN>(run_name="lab_04_agent_evaluation"):
    eval_results = <FILL_IN>

# COMMAND ----------

# MAGIC %skip
# MAGIC with mlflow.start_run(run_name="lab_04_agent_evaluation"):
# MAGIC     eval_results = mlflow.evaluate(
# MAGIC         data = DA.eval_df,
# MAGIC         model = model_uri,
# MAGIC         model_type = "databricks-agent",
# MAGIC         extra_metrics=[is_readable]
# MAGIC     )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 3 - Review Evaluation Results
# MAGIC
# MAGIC Review the evaluation results in the **Experiments** section. Examine the following information regarding this evaluation:
# MAGIC
# MAGIC - Token usage
# MAGIC
# MAGIC - Model metrics
# MAGIC
# MAGIC - Results of the custom metric defined earlier ("readability")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conclusion
# MAGIC
# MAGIC In this lab, you evaluated a RAG chain using the Mosaic AI Evaluation Framework library. You began by loading the dataset and RAG model. Then, you defined a custom metric and initiated the evaluation process. Finally, you reviewed the results through the user interface.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>