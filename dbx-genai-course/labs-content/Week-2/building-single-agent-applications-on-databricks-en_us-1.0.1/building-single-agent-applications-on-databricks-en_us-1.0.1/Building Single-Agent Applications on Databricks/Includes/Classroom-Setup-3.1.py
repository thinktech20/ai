# Databricks notebook source
# MAGIC %pip install -U -qqqq backoff databricks-openai uv databricks-agents mlflow-skinny[databricks] databricks_langchain
# MAGIC %pip install -U databricks-langchain langchain-community langchain
# MAGIC %pip install unitycatalog-langchain[databricks]
# MAGIC %pip install unitycatalog-ai[databricks]
# MAGIC %pip install -U databricks-sdk
# MAGIC %pip install reportlab
# MAGIC %restart_python

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

config_name = "setup-common-with-tools.yaml"

# COMMAND ----------

import sys, os

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
includes_dir = "../Includes"
course_dir = os.path.dirname(includes_dir)
sys.path.insert(0, course_dir)


config_path = f"{includes_dir}/config/{config_name}"

# COMMAND ----------

from Includes import setup_demo_environment

env = setup_demo_environment(
    config_path=config_path,
)
catalog_name = env["catalog_name"]
schema_name = env["schema_name"]

# COMMAND ----------

import json

config = {
    "llm_endpoint": "databricks-gpt-oss-120b",
    "llm_temperature": 0.1,
    "system_prompt": "You are a helpful assistant. Make sure to use tools for additional functionality.",
    "tool_list": [
        f"{catalog_name}.{schema_name}.avg_neigh_price",
        f"{catalog_name}.{schema_name}.cnt_by_room_type",
    ],
}

with open("./demo_agent1_config.json", "w") as f:
    json.dump(config, f, indent=4)

print("Configuration file created: ./demo_agent1_config.json")