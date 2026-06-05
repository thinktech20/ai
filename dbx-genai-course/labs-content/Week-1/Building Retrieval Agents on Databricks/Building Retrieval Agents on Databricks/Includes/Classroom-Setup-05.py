# Databricks notebook source
# MAGIC %run ./Classroom-Setup-Common

# COMMAND ----------

# MAGIC %md
# MAGIC **Document Volume to Use:**

# COMMAND ----------

user_docs_volume = f"{catalog}.{schema}.orion_docs"

print(f"✍️ Sample documents volume: {user_docs_volume}")