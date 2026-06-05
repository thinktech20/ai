# Databricks notebook source
# MAGIC %run ./Classroom-Setup-Common

# COMMAND ----------

DA = DBAcademyHelper()
DA.init()

# COMMAND ----------

from databricks.sdk import WorkspaceClient


DA.scope_name = f"genai_training_{DA.unique_name('_')}"

w = WorkspaceClient()
try:
    w.secrets.delete_scope(DA.scope_name)
except:
    pass

try:
    w.secrets.create_scope(DA.scope_name)
    w.secrets.put_secret(DA.scope_name, key="depl_demo_host", string_value='https://' + dbutils.notebook.entry_point.getDbutils().notebook().getContext().tags().get('browserHostName').getOrElse(None))
    w.secrets.put_secret(DA.scope_name, key="depl_demo_token", string_value=dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None))
except Exception as e:
    print(f'unable to create secret scope {DA.scope_name}, error: {e}')