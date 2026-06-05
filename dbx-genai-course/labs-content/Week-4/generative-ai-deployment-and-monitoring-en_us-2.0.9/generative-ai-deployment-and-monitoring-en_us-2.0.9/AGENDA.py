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
# MAGIC
# MAGIC ## Generative AI Deployment and Monitoring
# MAGIC
# MAGIC This course introduces learners to operationalizing, deploying, and monitoring generative artificial intelligence (AI) applications.. First, learners will develop knowledge and skills in the deployment of generative AI applications using tools like Model Serving. Next, the course will discuss operationalizing generative AI applications following modern LLMOps best practices and recommended architectures. And finally, learners will be introduced to the idea of monitoring generative AI applications and their components using Lakehouse Monitoring.
# MAGIC
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC The content was developed for participants with these skills/knowledge/abilities: 
# MAGIC - Familiarity with natural language processing concepts
# MAGIC - Familiarity with prompt engineering/prompt engineering best practices 
# MAGIC - Familiarity with the Databricks Data Intelligence Platform
# MAGIC - Familiarity with RAG  (preparing data, building a RAG architecture, concepts like embedding, vectors, vector databases, etc.)
# MAGIC - Experience with building LLM applications using multi-stage reasoning LLM chains and agents
# MAGIC - Familiarity with Databricks Data Intelligence Platform tools for evaluation and governance.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Course Agenda  
# MAGIC The following modules are part of the **Generative AI Deployment and Monitoring** course by **Databricks Academy**.
# MAGIC
# MAGIC | # | Module Name | Lesson Name |
# MAGIC |---|-------------|-------------|
# MAGIC | 1 | **Model Deployment Fundamentals** | • *Lecture:* Model Management <br> • *Lecture:* Deployment Methods |
# MAGIC | 2 | [Batch Deployment]($./01 - Batch Deployment) | • *Lecture:* Introduction to Batch Deployment <br> • [**Demo:** Batch Inference using SLM]($./01 - Batch Deployment/1.0 - Batch Inference using SLM) <br> • [**Lab:** Batch Inference using SLM]($./01 - Batch Deployment/1.LAB - Batch Inference using SLM) |
# MAGIC | 3 | [Real-time Deployment]($./02 - Real-time Deployment) | • *Lecture:* Introduction to Real-time Deployment <br> • *Lecture:* Databricks Model Serving <br> • [**Demo:** Deploying an LLM Chain to Databricks Model Serving]($./02 - Real-time Deployment/2.1 - Deploying an LLM Chain to Databricks Model Serving) <br> • [**Demo:** Serving Models with Provisioned Throughput]($./02 - Real-time Deployment/2.2 - Serving Models with PT) <br> • [**Lab:** Custom Model Deployment and A/B Testing]($./02 - Real-time Deployment/2.LAB - Custom Model Deployment and A-B Testing) |
# MAGIC | 4 | [AI System Monitoring]($./03 - AI System Monitoring) | • *Lecture:* AI Application Monitoring <br> • [**Demo:** Online Monitoring an LLM RAG Chain]($./03 - AI System Monitoring/3.1 - Online Monitoring an LLM RAG Chain) <br> • [**Lab:** Online Monitoring]($./03 - AI System Monitoring/3.LAB - Online Monitoring) |
# MAGIC | 5 | **LLMOps concepts** | • *Lecture:* MLOps primer <br> • *Lecture:* Deployment Methods |
# MAGIC
# MAGIC
# MAGIC ---
# MAGIC ## Requirements
# MAGIC
# MAGIC Please review the following requirements before starting the lesson:
# MAGIC
# MAGIC * Use Databricks Runtime version: **`17.3.x-cpu-ml-scala2.13`** for running all demo and lab notebooks.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>