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
    
    print("✅ Vector Search endpoint is ready. ")
    print(f"\n✍️ Vector Search endpoint to use: {endpoint_name}")

vector_search_endpoint = "vs_endpoint_1"
check_vector_search_endpoint(vector_search_endpoint)

# COMMAND ----------

docs_table = f"{catalog}.{schema}.docs_chunked"