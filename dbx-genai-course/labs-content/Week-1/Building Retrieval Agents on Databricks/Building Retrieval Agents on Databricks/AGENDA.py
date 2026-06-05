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
# MAGIC ## Building Retrieval Agents on Databricks
# MAGIC
# MAGIC This course provides hands-on training for building retrieval agents on the Databricks Data Intelligence Platform. Participants will learn to parse unstructured documents into structured data, transform and chunk content for retrieval workflows, build vector search solutions for document retrieval, and develop production-ready agents using MLflow and Agent Bricks. The course covers the complete agent lifecycle from document processing through embedding generation, vector indexing, and agent deployment with governance capabilities.
# MAGIC  
# MAGIC ---
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC - Intermediate Python programming experience
# MAGIC - Basic SQL knowledge for querying and creating functions
# MAGIC - Familiarity with Databricks Data Intelligence Platform
# MAGIC - Understanding of Unity Catalog concepts including catalogs and schemas
# MAGIC - Basic understanding of large language models (LLMs) and prompt engineering
# MAGIC - Basic knowledge of MLflow for experiment tracking
# MAGIC
# MAGIC ---
# MAGIC ## Course Agenda
# MAGIC The following modules are part of the **Building Retrieval Agents on Databricks** course by **Databricks Academy**. 
# MAGIC
# MAGIC | # | Module Name | Lessons |
# MAGIC | - | ----------- | ------- |
# MAGIC | 1 | [Foundations of Retrieval Agents]($./01-Foundations of Retrieval Agents) | [1.1 Lecture - Beyond Prompts – Retrieval Agents and Context Engineering]($./01-Foundations of Retrieval Agents/1.1 Lecture - Beyond Prompts – Retrieval Agents and Context Engineering) |
# MAGIC | 2 | [Document Parsing and Chunking]($./02-Document Parsing and Chunking) | [2.1 Lecture - Document Parsing and Chunking]($./02-Document Parsing and Chunking/2.1 Lecture - Document Parsing and Chunking) |
# MAGIC | | | [2.2 Demo - Parse Documents to Structured Data]($./02-Document Parsing and Chunking/2.2 Demo - Parse Documents to Structured Data) |
# MAGIC | | | [2.3 Demo - Clean, Transform, and Chunk Parsed Text]($./02-Document Parsing and Chunking/2.3 Demo - Clean, Transform, and Chunk Parsed Text) |
# MAGIC | | | [2.4 Lab - Parse Transform and Chunk Documents]($./02-Document Parsing and Chunking/2.4 Lab - Parse Transform and Chunk Documents) |
# MAGIC | 3 | [Vector Search for Retrieval]($./03-Vector Search for Retrieval) | [3.1 Lecture - Embeddings and Vector Search]($./03-Vector Search for Retrieval/3.1 Lecture - Embeddings and Vector Search) |
# MAGIC | | | [3.2 Demo - Building Vector Search for Retrieval]($./03-Vector Search for Retrieval/3.2 Demo - Building Vector Search for Retrieval) |
# MAGIC | | | [3.3 Lab - Building Vector Search for Retrieval]($./03-Vector Search for Retrieval/3.3 Lab - Building Vector Search for Retrieval) |
# MAGIC | 4 | [Building and Logging Retrieval Agents]($./04-Building and Logging Retrieval Agents) | [4.1 Lecture - MLflow and Agent Development]($./04-Building and Logging Retrieval Agents/4.1 Lecture - MLflow and Agent Development) |
# MAGIC | | | [4.2 Demo - Building and Logging a Retrieval Agent]($./04-Building and Logging Retrieval Agents/4.2 Demo - Building and Logging a Retrieval Agent) |
# MAGIC | | | [4.3 Lab - Building and Registering Retrieval Agent]($./04-Building and Logging Retrieval Agents/4.3 Lab - Building and Registering Retrieval Agent) |
# MAGIC | 5 | [Agent Bricks]($./05-Agent Bricks) | [5.1 Lecture - Knowledge Assistant with Agent Bricks]($./05-Agent Bricks/5.1 Lecture - Knowledge Assistant with Agent Bricks) |
# MAGIC | | | [5.2 Demo - Building KA Agent with Agent Bricks]($./05-Agent Bricks/5.2 Demo - Building KA Agent with Agent Bricks) |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Technical Requirements
# MAGIC
# MAGIC Please review the following requirements before starting the lesson:
# MAGIC
# MAGIC - Use **Serverless Compute (environment version 4)** for running all demo and lab notebooks
# MAGIC - Access to **`ai_parse_document()`** function (Beta feature)
# MAGIC - Access to **Mosaic AI Agent Bricks** (Beta feature)
# MAGIC - A pre-created **Vector Search endpoint**
# MAGIC - Access to **Foundation Model APIs** for embedding generation
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>