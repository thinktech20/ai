# Databricks notebook source
# MAGIC %pip install -U \
# MAGIC   "langchain<0.4,>=0.3.27" \
# MAGIC   "langchain-core<0.4,>=0.3.79" \
# MAGIC   "langchain-community<0.4,>=0.2" \
# MAGIC   "langchain-text-splitters<1.0,>=0.3.9" \
# MAGIC   "langchain-openai<0.3,>=0.2.0" \
# MAGIC   "pydantic>=2.0.0,<3.0.0" \
# MAGIC   "databricks-sdk>=0.65.0" \
# MAGIC   "databricks-langchain==0.8.2" \
# MAGIC   "reportlab"
# MAGIC %restart_python

# COMMAND ----------

config_name = "setup-common-with-tools-lab.yaml"

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