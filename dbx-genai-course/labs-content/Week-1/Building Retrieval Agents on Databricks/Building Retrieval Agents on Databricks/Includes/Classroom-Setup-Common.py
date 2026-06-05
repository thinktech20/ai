# Databricks notebook source
# MAGIC %run ./_common

# COMMAND ----------

import os

# COMMAND ----------

def is_serverless_4():
    is_serverless = os.environ.get('IS_SERVERLESS', '')
    runtime_version = os.environ.get('DATABRICKS_RUNTIME_VERSION', '')
    return is_serverless == 'TRUE' and runtime_version.startswith('client.4.')

# COMMAND ----------

# Setup logging to lowest level. In dev, this can be changed
import warnings
import logging

# Hide warnings
warnings.filterwarnings("ignore")

# Limit other library logs
logging.getLogger().setLevel(logging.ERROR)

# Library-level logging setup
logging.getLogger("py4j").setLevel(logging.ERROR)

# COMMAND ----------

@DBAcademyHelper.add_method
def validate_table(self, name):
    if spark.catalog.tableExists(name):
        print(f'Validation of table {name} complete. No errors found.')
        return True
    else:
        raise AssertionError(f"The table {name} does not exist")

# COMMAND ----------

# MAGIC %md
# MAGIC **Set default catalog and schema:**

# COMMAND ----------

DA = DBAcademyHelper()
catalog = DA.catalog_name
schema = DA.schema_name

spark.sql(f"USE CATALOG {catalog}")
spark.sql(f"USE SCHEMA {schema}")

print("Default catalog and schema are set.")

# COMMAND ----------

# MAGIC %md
# MAGIC **Prepare Datasets:**

# COMMAND ----------

def create_and_copy_volume_if_missing(volume_name):
    shared_path = f"/Volumes/{catalog}/data/{volume_name}"
    user_path = f"/Volumes/{catalog}/{schema}/{volume_name}"

    if spark.sql(f"SHOW VOLUMES IN {catalog}.{schema} LIKE '{volume_name}'").collect():
        print(f"✅ Volume {volume_name} already exists. Skipping copy.")
    else:
        print(f"⏳ Creating volume {volume_name} ...")
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume_name}")
        print(f"⏳ Copying files from {shared_path} to {user_path} ...")
        try:
            os.makedirs(user_path, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create directory {user_path} with os.makedirs: {e}")
        # Copy files using Spark (serverless safe)
        files_df = spark.read.format("binaryFile").load(shared_path)
        for row in files_df.collect():
            file_name = os.path.basename(row.path)
            dest_path = os.path.join(user_path, file_name)
            with open(dest_path, "wb") as f:
                f.write(row.content)
        print(f"✅ Files copied to {user_path}.")

create_and_copy_volume_if_missing("orion_docs")

create_and_copy_volume_if_missing("orion_text")

# Define variables for the downstream notebooks
source_docs_path = f"/Volumes/{catalog}/datasets/orion_docs"
user_docs_path = f"/Volumes/{catalog}/{schema}/orion_docs"
user_docs_volume = f"{catalog}.{schema}.orion_docs"
user_text_path = f"/Volumes/{catalog}/{schema}/orion_text"
user_text_volume = f"{catalog}.{schema}.orion_text"