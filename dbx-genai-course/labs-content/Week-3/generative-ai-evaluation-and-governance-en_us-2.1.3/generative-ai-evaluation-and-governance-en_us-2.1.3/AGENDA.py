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
# MAGIC ## Generative AI Evaluation and Governance
# MAGIC
# MAGIC This course introduces learners to evaluating and governing generative artificial intelligence (AI) systems. First, learners will explore the meaning behind and motivation of building evaluation and governance/security systems. Next, learners will be introduced to a variety of evaluation techniques for LLMs and their tasks. Next, the course will discuss how to govern and secure AI systems using Databricks. And finally, the course will conclude with an analysis of evaluating entire AI systems with respect to performance and cost.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Prerequisites
# MAGIC The content was developed for participants with these skills/knowledge/abilities:  
# MAGIC - Familiarity with natural language processing concepts
# MAGIC - Familiarity with prompt engineering/prompt engineering best practices 
# MAGIC - Familiarity with the Databricks Data Intelligence Platform
# MAGIC - Familiarity with RAG  (preparing data, building a RAG architecture, concepts like embedding, vectors, vector databases, etc.)
# MAGIC - Experience with building **`LLM`** applications using multi-stage reasoning **`LLM`** chains and agents
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Course Agenda  
# MAGIC The following modules are part of the **Generative AI Evaluation and Governance** course by **Databricks Academy**.
# MAGIC
# MAGIC | # | Module Name | Lesson Name |
# MAGIC |---|-------------|-------------|
# MAGIC | 1 | [Data Legality and Guardrails]($./01 - Data Legality and Guardrails) | • *Lecture:* Why Evaluating GenAI Applications <br> • [Demo: Explore Licensing of Datasets]($./01 - Data Legality and Guardrails/1.1 - Explore Licensing of Datasets) <br> • [Demo: Prompts and Guardrails Basics]($./01 - Data Legality and Guardrails/1.2 - Prompts and Guardrails Basics) <br> • [Lab: Implement and Test Guardrails for LLMs]($./01 - Data Legality and Guardrails/1.LAB - Implement and Test Guardrails for LLMs) |
# MAGIC | 2 | [Securing and Governing AI Systems]($./02 - Securing and Governing AI Systems) | • *Lecture:* AI System Security <br> • [Demo: Implementing AI Guardrails]($./02 - Securing and Governing AI Systems/2.1 - Implementing AI Guardrails) <br> • [Lab: Implementing AI Guardrails]($./02 - Securing and Governing AI Systems/2.LAB - Implementing AI Guardrails) |
# MAGIC | 3 | [Gen AI Evaluation Techniques]($./03 - Gen AI Evaluation Techniques) | • *Lecture:* Evaluation Techniques <br> • [Demo: Benchmark Evaluation]($./03 - Gen AI Evaluation Techniques/3.1 - Benchmark Evaluation) <br> • [Demo: LLM-as-a-Judge]($./03 - Gen AI Evaluation Techniques/3.2 - LLM-as-a-Judge) <br> • [Lab: Domain-Specific Evaluation]($./03 - Gen AI Evaluation Techniques/3.LAB - Domain-Specific Evaluation) |
# MAGIC | 4 | [End-to-end Application Evaluation]($./04 - End-to-end Application Evaluation) | • *Lecture:* End-to-end Application Evaluation <br> • [Demo: Evaluation with Mosaic AI Agent Evaluation]($./04 - End-to-end Application Evaluation/4.1 - Evaluation with Mosaic AI Agent Evaluation) <br> • [Lab: Evaluation with Mosaic AI Agent Evaluation]($./04 - End-to-end Application Evaluation/4.LAB - Evaluation with Mosaic AI Agent Evaluation) |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Requirements
# MAGIC
# MAGIC Please review the following requirements before starting the lesson:
# MAGIC
# MAGIC * Use Databricks Runtime version: **`15.4.x-cpu-ml-scala2.12`** for running all demo and lab notebooks.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>