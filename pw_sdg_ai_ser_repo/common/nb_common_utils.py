# Databricks notebook source
# MAGIC %run /Workspace/Users/d44c1af5-e99e-4010-8302-464e74d13ba1/.bundle/FSR/files/env/dev/config.py

# COMMAND ----------

import sys
import json
from pyspark.sql import SparkSession
#spark = SparkSession.builder.appName('abc').getOrCreate()

cluster_tags = spark.conf.get("spark.databricks.clusterUsageTags.clusterAllTags") 
df = spark.createDataFrame(json.loads(cluster_tags))
envparam = df.filter(df.key == "env").select('value').collect()[0][0]
print(envparam)

if envparam == 'dev':
    try:
        # Try to execute this block for the dev environment
        sys.path.append(f"/Workspace/Repos/FSR/gp_fsr_repo/env/{envparam}/")
        from config import *
    except Exception as e:
        # If the above fails, fallback to this block
        sys.path.append(f"/Workspace/Users/d44c1af5-e99e-4010-8302-464e74d13ba1/.bundle/FSR/files/env/{envparam}/")
        from config import *
        print(f"Failed to use Repos path. Fallback to default dev path. Error: {e}")
else:
    # For 'prod' or any other environments
    sys.path.append(f"/Workspace/Users/d44c1af5-e99e-4010-8302-464e74d13ba1/.bundle/FSR/files/env/prod/")
    from config import *
	