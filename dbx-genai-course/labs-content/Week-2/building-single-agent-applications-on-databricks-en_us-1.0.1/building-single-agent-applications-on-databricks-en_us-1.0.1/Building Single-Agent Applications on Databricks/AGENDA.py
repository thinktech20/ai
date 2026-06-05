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
# MAGIC ## Building Single-Agent Applications on Databricks
# MAGIC
# MAGIC This course provides hands-on training for building  single-agent applications on the Databricks Data Intelligence Platform. Students will learn to create AI agents that leverage Unity Catalog functions as tools, implement comprehensive tracing and monitoring with MLflow, and deploy agents using both traditional frameworks like LangChain and modern solutions like Agent Bricks. The course covers the complete agent lifecycle from initial tool creation and testing in AI Playground through production deployment with governance, evaluation, and continuous improvement capabilities.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC - Intermediate Python programming experience, including familiarity with decorators, object-oriented programming, and package management
# MAGIC - Basic SQL knowledge for querying databases and creating user-defined functions
# MAGIC - Experience with Jupyter-style notebooks or similar interactive development environments
# MAGIC - Familiarity with Databricks workspace navigation and basic compute configuration
# MAGIC - Understanding of Unity Catalog concepts including catalogs, schemas, and basic governance principles
# MAGIC - Experience with Delta Lake tables and basic data querying in Databricks
# MAGIC - Basic understanding of large language models (LLMs) and their capabilities
# MAGIC - Familiarity with prompt engineering concepts and natural language processing
# MAGIC - Basic knowledge of MLflow for experiment tracking and model management
# MAGIC
# MAGIC ---
# MAGIC ## Course Agenda
# MAGIC The following modules are part of the **Building Single-Agent Applications on Databricks** course by **Databricks Academy**. 
# MAGIC
# MAGIC | # | Module Name                               |
# MAGIC | - | ----------------------------------------- |
# MAGIC | 1 | [Foundations of Agents]($./M01 - Foundations of Agents)                     |
# MAGIC | 2 | [Building Single Agents]($./M02 - Building Single Agents)                    |
# MAGIC | 3 | [Reproducible Agents]($./M03 - Reproducible Agents)                       |
# MAGIC | 4 | [Production Ready Agents with Agent Bricks]($./M04 - Production-Ready Agents with Agent Bricks) |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### Requirements
# MAGIC
# MAGIC Please review the following requirements before starting the lesson:
# MAGIC
# MAGIC - Use Databricks Runtime version: **`Serverless`** for running all demo and lab notebooks.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>