# Databricks notebook source
# MAGIC %run ./_common

# COMMAND ----------

DA = DBAcademyHelper()

# COMMAND ----------

import os

catalog =  DA.catalog_name

def copy_files_to_volume(source_path, volume_name, catalog, schema):
    
    shared_volume_path = f"/Volumes/{catalog}/{schema}/{volume_name}"
    full_volume_name = f"{catalog}.{schema}.{volume_name}"
    
    try:
        # Check if volume exists
        if spark.sql(f"SHOW VOLUMES IN {catalog}.{schema} LIKE '{volume_name}'").collect():
            print(f"✅ Volume {volume_name} already exists. Skipping copy.")
            print(f"\n\n ✍️ Volume path: {full_volume_name}")
            return True

        # Create volume since it does not exist
        spark.sql(f"CREATE VOLUME {full_volume_name}")
        print(f"✅ Volume '{full_volume_name}' created in schema '{schema}'.")

        # Grant read permissions on the volume to all account users
        spark.sql(f"GRANT READ VOLUME ON VOLUME {full_volume_name} TO `account users`")
        print(f"✅ Granted READ VOLUME permission on '{full_volume_name}' to all account users.")

        # Copy files from source to volume
        for name in os.listdir(source_path):
            local_path = os.path.join(source_path, name)
            if os.path.isfile(local_path):
                src_file = f"file:{local_path}"
                dst_file = f"{shared_volume_path}/{name}"
                try:
                    dbutils.fs.cp(src_file, dst_file)
                    print(f"✅ Copied '{name}' to volume '{full_volume_name}'.")
                except Exception as file_exc:
                    print(f"⚠️ Could not copy '{name}': {file_exc}")

        print(f"\n\n ✍️ Volume path: {full_volume_name}")
        return True
    except Exception as e:
        print(f"⛔️ ERROR: {e}")
        return False


def setup_orion_docs_volume(catalog, schema):
    """
    Set up the orion_docs volume with sample documents.
    """
    source_docs_path = os.path.join(os.getcwd(), "data/orion-docs/")
    return copy_files_to_volume(source_docs_path, "orion_docs", catalog, schema)


def setup_orion_text_volume(catalog, schema):
    """
    Set up the orion_text volume with sample text documents.
    """
    source_text_path = os.path.join(os.getcwd(), "data/orion-text/")
    return copy_files_to_volume(source_text_path, "orion_text", catalog, schema)


# Main execution logic
shared_schema = "data"

# Create the schema 'data' in the 'catalog' if it does not exist
try:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{shared_schema}")
    print(f"✅ Schema '{catalog}.{shared_schema}' created or already exists.")
    
    # Grant USAGE permission on catalog and schema to all account users
    spark.sql(f"GRANT USAGE ON SCHEMA {catalog}.{shared_schema} TO `account users`")
    
    schema_creation_success = True
except Exception as e:
    print(f"⛔️ ERROR creating dataset schema '{catalog}.{shared_schema}': {e}")
    schema_creation_success = False

# Only run the following setup if schema creation was successful
if schema_creation_success:
    setup_orion_docs_volume(catalog, shared_schema)
    setup_orion_text_volume(catalog, shared_schema)