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
# MAGIC
# MAGIC # Serving Models with Provisioned Throughput
# MAGIC
# MAGIC **In this demo, we will focus on deploying GenAI applications using provisioned throughput.**
# MAGIC
# MAGIC Deployment is a key part of operationalizing our LLM-based applications. We will explore deployment options within Databricks and demonstrate how to achieve production-ready model serving.
# MAGIC
# MAGIC ## Why Provisioned Throughput?
# MAGIC
# MAGIC Provisioned throughput deployments are essential for production environments because they provide:
# MAGIC
# MAGIC * **Throughput Guarantees:** Ensure consistent, predictable performance with dedicated compute resources that meet your application's SLA requirements.
# MAGIC * **Compliance Requirements:** Maintain data isolation and security controls required for regulated industries and enterprise governance policies.
# MAGIC * **Production Reliability:** Eliminate cold starts and resource contention, delivering stable response times even under variable load conditions.
# MAGIC * **Cost Predictability:** Fixed capacity pricing enables accurate budget forecasting for production workloads.
# MAGIC
# MAGIC **Learning Objectives:**
# MAGIC
# MAGIC *By the end of this demo, you will be able to:*
# MAGIC
# MAGIC * Understand when to use provisioned throughput for model deployments.
# MAGIC * Deploy an external model from the `system.ai` catalog to a Databricks Model Serving endpoint with provisioned throughput.
# MAGIC * Query and validate deployed models in production.
# MAGIC
# MAGIC **🚨 Important: Deploying models with provisioned throughput involves substantial compute resources. As such, this demonstration is designed to be instructor-led, and the model WILL NOT be deployed in the training workspace.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Requirements
# MAGIC
# MAGIC Please review the following requirements before starting the lesson:
# MAGIC
# MAGIC * To run this notebook, you need to use one of the following Databricks runtime(s): **17.3.x-cpu-ml-scala2.13**
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Demo Overview
# MAGIC
# MAGIC In this demo, we will walk through deploying models with provisioned throughput in Databricks. We'll discuss this in the following steps:
# MAGIC
# MAGIC 1. Access models in the **`system.ai` catalog**.
# MAGIC
# MAGIC 1. **Deploy the `gpt-oss-20b` model** to a Databricks Model Serving endpoint with provisioned throughput.
# MAGIC
# MAGIC 1. Query and validate the deployed model.

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ## Deploy a Model with Provisioned Throughput
# MAGIC
# MAGIC While we have described and used tools like the AI Playground and Foundation Model APIs for querying common LLMs, production applications often require dedicated compute resources with guaranteed throughput and performance SLAs.
# MAGIC
# MAGIC To achieve this, we use **Databricks Model Serving with Provisioned Throughput**. This deployment option provides dedicated infrastructure that ensures consistent performance, meets compliance requirements, and delivers predictable costs for production workloads.
# MAGIC
# MAGIC Next, we will demonstrate how to deploy a model from the `system.ai` catalog with provisioned throughput.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Getting a Model from `system.ai` Catalog
# MAGIC
# MAGIC The Databricks **`system.ai` catalog** is part of the Databricks GenAI and Unity Catalog offerings. It is a curated list of state-of-the-art open source models managed in Unity Catalog. These models can be easily deployed using Model Serving with provisioned throughput or fine-tuned with Model Training.
# MAGIC
# MAGIC For this demo, we will show how to deploy the **`gpt-oss-20b`** model, a powerful open-source language model suitable for production use cases.
# MAGIC
# MAGIC To view and access the model:
# MAGIC
# MAGIC 1. From the left panel select **Catalog**.
# MAGIC 1. Select **system** catalog.
# MAGIC 1. Select **ai** schema. This will show a list of available models that you can serve.
# MAGIC 1. Locate the **`gpt-oss-20b`** model in the list.
# MAGIC
# MAGIC <!--  -->
# MAGIC
# MAGIC ![genai-as-04-system-ai-catalog](../Includes/images/genai-as-04-system-ai-catalog-v2.png)
# MAGIC
# MAGIC **Note:** Models in the `system.ai` catalog are governed by Unity Catalog, ensuring secure access control and compliance with your organization's data governance policies.

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Deploying a Model with Provisioned Throughput
# MAGIC
# MAGIC Once we've located the `gpt-oss-20b` model in the `system.ai` catalog, we can deploy it to Databricks Model Serving with provisioned throughput by following these steps:
# MAGIC
# MAGIC 1. Navigate to the **`system.ai.gpt_oss_20b`** model page in the Catalog.
# MAGIC
# MAGIC 1. Click the **Serve this Model** button.
# MAGIC
# MAGIC 1. Configure the served entity:
# MAGIC     * Name: `gpt_oss_20b_endpoint`.
# MAGIC     * For served entities, select the `gpt-oss-20b` model.
# MAGIC
# MAGIC 1. Click the **Confirm** button.
# MAGIC
# MAGIC 1. Configure the Model Serving endpoint with **Provisioned Throughput**:
# MAGIC     * Select **Provisioned Throughput** as the compute type.
# MAGIC     * Choose the appropriate workload size based on your throughput requirements (e.g., Small, Medium, Large).
# MAGIC     * Configure scaling parameters to meet your SLA requirements.
# MAGIC     * Review security and access control settings.
# MAGIC
# MAGIC 1. **🚨 Notice: We won't deploy the model due to associated cost. In real use cases, we would click the Create button to provision the endpoint.**
# MAGIC
# MAGIC **Note:** Provisioned throughput deployments typically take 10-15 minutes to initialize as dedicated compute resources are allocated for your endpoint.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query the Deployed Model
# MAGIC
# MAGIC More realistically, we can query the deployed model directly from our serving applications.

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Option 1 - Query via the UI
# MAGIC
# MAGIC We can query the model directly in Databricks to confirm everything is working using the **Query endpoint** capability.
# MAGIC
# MAGIC Sample query:
# MAGIC `{"messages": [{"role": "user", "content": "What are the key benefits of using Databricks for data engineering?"}]}`

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Option 2 - Query the Deployed Model in AI Playground
# MAGIC
# MAGIC To test the model with AI Playground, select the deployed `gpt_oss_20b_endpoint` model and use the chatbox to send queries.

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC ### Option 3 - Query the Deployed Model with the SDK
# MAGIC
# MAGIC
# MAGIC ```
# MAGIC from databricks.sdk import WorkspaceClient
# MAGIC
# MAGIC w = WorkspaceClient()
# MAGIC
# MAGIC # Sample messages to send to the model
# MAGIC messages = [
# MAGIC     {"role": "system", "content": "You are a helpful assistant."},
# MAGIC     {"role": "user", "content": "Explain the benefits of using provisioned throughput for production ML deployments."}
# MAGIC ]
# MAGIC
# MAGIC response = w.serving_endpoints.query(
# MAGIC     name="gpt_oss_20b_endpoint",  # name of the model serving endpoint
# MAGIC     messages=messages,
# MAGIC     max_tokens=200,
# MAGIC     temperature=0.7
# MAGIC )
# MAGIC
# MAGIC print(response.choices[0].message.content)
# MAGIC ```
# MAGIC
# MAGIC **💡 Tip:** Adjust `max_tokens` and `temperature` parameters to control response length and creativity. With provisioned throughput, you'll experience consistent response times regardless of concurrent request volume.

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC
# MAGIC ## Conclusion
# MAGIC
# MAGIC At this point, you should be able to:
# MAGIC
# MAGIC * Understand when to use provisioned throughput for model deployments.
# MAGIC * Deploy an external model from the `system.ai` catalog to a Databricks Model Serving endpoint with provisioned throughput.
# MAGIC * Query and validate deployed models in production.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>