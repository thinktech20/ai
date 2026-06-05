# Databricks notebook source
# MAGIC %run ./Classroom-Setup-Common

# COMMAND ----------

# MAGIC %md
# MAGIC **Check for Serverless**

# COMMAND ----------

if not is_serverless_4():
    raise EnvironmentError("⛔️ ERROR: This notebook must be run on a Databricks Serverless 4 environment. Please switch your compute to Serverless 4 and retry.")
else:
    print("✅ Environment check passed: Serverless 4 detected.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Check If Vector Search Endpoint is Ready**

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

def check_vector_search_endpoint(endpoint_name: str):
    vsc = VectorSearchClient(disable_notice=True)
    try:
        endpoint = vsc.get_endpoint(endpoint_name)
    except Exception as e:
        raise RuntimeError(f"⛔️ ERROR: Vector search endpoint '{endpoint_name}' does not exist. Details: {e}")
    status = endpoint.get("endpoint_status", {}).get("state", "")
    if status != "ONLINE":
        raise RuntimeError(f"⛔️ ERROR: Vector search endpoint '{endpoint_name}' exists but is not ready.")
    print(f"✅ Vector search endpoint '{endpoint_name}' exists and is ready.")

vs_endpoint_name = "vs_endpoint_1"
check_vector_search_endpoint(vs_endpoint_name)

# COMMAND ----------

# MAGIC %md
# MAGIC
# MAGIC **Check If Vector Search Index Exists**

# COMMAND ----------

section = dbutils.widgets.get("section") or "lab"

if(section == "lab"):
    vs_index_name = f"{catalog}.{schema}.docs_chunked_lab_index"
else:
    vs_index_name = f"{catalog}.{schema}.docs_chunked_index"

vsc = VectorSearchClient(disable_notice=True)
try:
    vsc.get_index(vs_endpoint_name, vs_index_name)
    print(f"✅ Vector search index '{vs_index_name}' exists and is ready.")
except Exception as e:
    raise RuntimeError(f"⛔️ ERROR: Vector search index '{vs_index_name}' does not exist. You should have created this in the previous demo. Make sure you have run the previous demo. Details: {e}")