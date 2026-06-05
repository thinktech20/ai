# Databricks notebook source
# MAGIC %pip install unitycatalog-ai[databricks]==0.3.2
# MAGIC %pip install reportlab
# MAGIC %restart_python

# COMMAND ----------

import sys, os

ctx = dbutils.notebook.entry_point.getDbutils().notebook().getContext()
includes_dir = "../Includes"
course_dir = os.path.dirname(includes_dir)
sys.path.insert(0, course_dir)


config_path = f"{includes_dir}/config/setup-common-with-py-tools-lab.yaml"

# COMMAND ----------

from Includes import setup_demo_environment

env = setup_demo_environment(
    config_path=config_path,
)
catalog_name = env["catalog_name"]
schema_name = env["schema_name"]