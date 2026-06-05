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
# MAGIC # Evaluation with Mosaic AI Agent Evaluation
# MAGIC
# MAGIC In previous demonstrations, we utilized `mlflow` for evaluation purposes. Mosaic AI Agent Evaluation builds upon MLflow, offering additional features and enhancements. It enables the definition of custom evaluation metrics, facilitates straightforward model deployment, and provides an easy-to-use **Review App**.
# MAGIC
# MAGIC **Learning Objectives:**
# MAGIC
# MAGIC *By the end of this demo, you will be able to:*
# MAGIC
# MAGIC - Load a model from the model registry and use it to evaluate an evaluation dataset.
# MAGIC - Define custom evaluation metrics.
# MAGIC - Deploy the model along with the Review App to gather human feedback.

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
# MAGIC **🚨 Pre-requisite Notice:** This notebook requires **[00 - Build-Model]($../00-Build-Model/00-Build-Model)** to create a model that will be used for this demo. **In Databricks provided lab environment this will be run before the class, which means you don't need to run it manually**.

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
# MAGIC Before starting the demo, run the provided classroom setup script. This script will define configuration variables necessary for the demo. Execute the following cell:

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-04

# COMMAND ----------

# MAGIC %md
# MAGIC **Other Conventions:**
# MAGIC
# MAGIC Throughout this demo, we'll refer to the object `DA`. This object, provided by Databricks Academy, contains variables such as your username, catalog name, schema name, working directory, and dataset locations. Run the code block below to view these details:

# COMMAND ----------

print(f"Username:          {DA.username}")
print(f"Catalog Name:      {DA.catalog_name}")
print(f"Schema Name:       {DA.schema_name}")
print(f"Working Directory: {DA.paths.working_dir}")
print(f"Dataset Location:  {DA.paths.datasets}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo Overview
# MAGIC
# MAGIC In this demo, we will begin by reviewing **the dataset** that will be used for evaluation. Next, we will **load a RAG chain** model from the model registry and utilize it for evaluation purposes. To illustrate custom evaluation, we will define a custom metric and incorporate it into the evaluation workflow. Upon completing the evaluation, we will **deploy the model** and demonstrate how to use the integrated "Review App" to gather **human feedback**.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Prepare Evaluation Dataset
# MAGIC
# MAGIC This dataset includes sample queries and their corresponding expected responses. The expected responses are generated using synthetic data. In a real-world project, these responses would be crafted by experts.

# COMMAND ----------

display(DA.eval_dataset)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Load the Model
# MAGIC
# MAGIC A RAG chain has been created and registered for us. If you're interested in the code, you can explore the `00 - Build Model` folder. Please note that building RAG chains is beyond the scope of this course. For more information on these topics, you can refer to the related course, **"Generative AI Solution Development"** available on the Databricks Academy.

# COMMAND ----------

import mlflow

catalog_name = "genai_shared_catalog_03"
schema_name = f"ws_{spark.conf.get('spark.databricks.clusterUsageTags.clusterOwnerOrgId')}"

model_name= f"{catalog_name}.{schema_name}.rag_app"
model_uri = f"models:/{catalog_name}.{schema_name}.rag_app/1"
rag_model = mlflow.langchain.load_model(model_uri)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Model Evaluation

# COMMAND ----------

# MAGIC %md
# MAGIC ### Define Custom Metrics
# MAGIC Although the Agents Evaluation framework automatically calculates common evaluation metrics, there are instances where we may need to assess the model using custom metrics. In this section, we will define a custom metric to evaluate whether the **retrieval model** generates responses containing personally identifiable information (PII).

# COMMAND ----------

from mlflow.metrics.genai import make_genai_metric_from_prompt

# Define a custom assessment to detect PII in the retrieved chunks. 
has_pii_prompt = "Your task is to determine whether the retrieved content has any PII information. This was the content: '{retrieved_context}'"

has_pii = make_genai_metric_from_prompt(
    name="has_pii",
    judge_prompt=has_pii_prompt,
    model="endpoints:/databricks-meta-llama-3-3-70b-instruct",
    metric_metadata={"assessment_type": "RETRIEVAL"},
    greater_is_better = False
)

# COMMAND ----------

has_pii.greater_is_better

# COMMAND ----------

# MAGIC %md
# MAGIC ### Run Evaluation Test
# MAGIC
# MAGIC Please note that in the code below, we are logging the evaluation process using MLflow to enable viewing the results through the MLflow UI.

# COMMAND ----------

with mlflow.start_run(run_name="rag_eval_with_agent_evaluation"):
    eval_results = mlflow.evaluate(
        data = DA.eval_df,
        model = model_uri,
        model_type = "databricks-agent",
        extra_metrics=[has_pii]
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ### Review Evaluation Results
# MAGIC
# MAGIC We have two options for reviewing the evaluation results. The first option is to examine the metrics and tables directly using the results object. The second option is to review the results through the user interface (UI).

# COMMAND ----------

# MAGIC %md
# MAGIC #### Review Review Metrics

# COMMAND ----------

display(eval_results.metrics)

# COMMAND ----------

# MAGIC %md
# MAGIC ### Review Results via the UI
# MAGIC
# MAGIC To view the results in the UI, follow these steps:
# MAGIC
# MAGIC - Click on the **"View evaluation results"** tab displayed at the **Run Evaluation Test** section code block's output for a simpler method.
# MAGIC
# MAGIC - Alternatively, you can navigate to "Experiments" in the left panel and locate the experiment registered with the title of this notebook.
# MAGIC
# MAGIC - Click on the Run Name and View the overall metrics in the **Model Metrics** tab.
# MAGIC
# MAGIC - Examine detailed results for each assessment in the **Evaluation results Preview** tab.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Collect Human Feedback via Databricks Review App
# MAGIC
# MAGIC The Databricks Review App stages the LLM in an environment where expert stakeholders can engage with it—allowing for conversations, questions, and more. This setup enables the collection of valuable feedback on your application, ensuring the quality and safety of its responses.
# MAGIC
# MAGIC **Stakeholders can interact with the application bot and provide feedback on these interactions. They can also offer feedback on historical logs, curated traces, or agent outputs.**
# MAGIC
# MAGIC **🚨 Important Note:**
# MAGIC
# MAGIC This step is **for instructors only**. If you are using your own environment, you can comment out the cells and run them to deploy the model and access the Review App.
# MAGIC
# MAGIC **⚠️ Warning: Permission Required**
# MAGIC
# MAGIC If you are not an instructor and try to run this step without the required permissions, you may encounter the `PermissionDenied` error.
# MAGIC
# MAGIC **How to Proceed:**
# MAGIC - **If you are an instructor**, after running this code, you must grant permissions to users as needed.
# MAGIC - **If you are not an instructor**, do **not** run this step without getting permission from an instructor. Otherwise, you will encounter a permission error and won’t be able to proceed.

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointStateReady, EndpointStateConfigUpdate
import mlflow
from databricks import agents

# Deploy the model with the agent framework
deployment_info = agents.deploy(
    model_name, 
    model_version=1,
    scale_to_zero=True,
    budget_policy_id=None)

# Wait for the Review App and deployed model to be ready
w = WorkspaceClient()
print("\nWaiting for endpoint to deploy.  This can take 15 - 20 minutes.", end="")

while ((w.serving_endpoints.get(deployment_info.endpoint_name).state.ready == EndpointStateReady.NOT_READY) or (w.serving_endpoints.get(deployment_info.endpoint_name).state.config_update == EndpointStateConfigUpdate.IN_PROGRESS)):
    print(".", end="")
    time.sleep(30)

print("\nThe endpoint is ready!", end="")

# COMMAND ----------

print(f"Endpoint URL    : {deployment_info.endpoint_url}")
print(f"Review App URL  : {deployment_info.review_app_url}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Set Permissions for Other Users
# MAGIC
# MAGIC **🚨 Note:** To allow other users for querying and reviewing the app, you need to manually set permissions. To do that;
# MAGIC * Go to **Serving** page and select the deployed endpoint.
# MAGIC
# MAGIC * Select **Permissions**.
# MAGIC
# MAGIC * Set **Can Query** to "All workspace users".

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## 🚨 Mandatory Step: Clean-up
# MAGIC
# MAGIC To ensure a smooth workflow, **you must delete the deployed endpoint** before ending the session. This allows other users to deploy a new endpoint without conflicts.  
# MAGIC
# MAGIC Run the cell below **before moving forward** to clean up the deployed resources.  
# MAGIC
# MAGIC **⚠️ Important:**
# MAGIC - **This step is required** and should be run **before leaving the session**.
# MAGIC - **Instructors should ensure this step is completed** to prevent resource conflicts.
# MAGIC

# COMMAND ----------

from mlflow.tracking import MlflowClient

client = MlflowClient()

print("\nCleaning up resources...")

# 1. Delete agent serving endpoint
try:
    agents.delete_deployment(model_name=model_name)
    print(f"Deleted agent endpoint: {model_name}")
except Exception as e:
    print(f"Agent endpoint not deleted or already removed: {e}")

# 2. Delete payload table
try:
    base_table_name = model_name.split(".")[-1]  # rag_app_<suffix>
    payload_table_name = f"{catalog_name}.{schema_name}.{base_table_name}_payload"
    spark.sql(f"DROP TABLE IF EXISTS {payload_table_name}")
    print(f"Deleted table: {payload_table_name}")
except Exception as e:
    print(f"Failed to delete payload table: {e}")

# 3. Delete feedback registered model
try:
    feedback_model_name = f"{catalog_name}.{schema_name}.feedback"
    client.delete_registered_model(name=feedback_model_name)
    print(f"Deleted feedback model: {feedback_model_name}")
except Exception as e:
    print(f"Feedback model not deleted or already removed: {e}")

print("\nCleanup completed.")

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Conclusion
# MAGIC
# MAGIC In this demo, we began by defining a custom metric to be used as an additional metric within the Agent Evaluation Framework. Next, we conducted an evaluation run and reviewed the results using both the API and the user interface. In the final step, we deployed the model through Model Serving and demonstrated how the Review App can be utilized to collect human feedback.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>