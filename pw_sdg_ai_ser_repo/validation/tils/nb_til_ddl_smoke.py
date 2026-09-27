# Databricks notebook source
# nb_til_ddl_smoke — quick post-DDL validation for TIL tables

# COMMAND ----------

from pyspark.sql import Row

from common.tils.til_config import TIL_CATALOG, TIL_SCHEMA
from contracts.table_specs.tils import (
    TIL_CHUNKS_TABLE,
    TIL_ELEMENTS_TABLE,
    TIL_EVALUATION_RESULTS_TABLE,
    TIL_METADATA_TABLE,
    TIL_PIPELINE_RUN_AUDIT_TABLE,
    TIL_VALIDATION_RESULTS_TABLE,
)

# COMMAND ----------

EXPECTED_TABLES = [
    TIL_METADATA_TABLE,
    TIL_ELEMENTS_TABLE,
    TIL_CHUNKS_TABLE,
    TIL_VALIDATION_RESULTS_TABLE,
    TIL_EVALUATION_RESULTS_TABLE,
    TIL_PIPELINE_RUN_AUDIT_TABLE,
]


# COMMAND ----------

def table_exists(table_name: str) -> bool:
    try:
        return bool(spark.catalog.tableExists(table_name))
    except Exception:
        return False


rows = []
for table_name in EXPECTED_TABLES:
    exists = table_exists(table_name)
    row_count = None
    if exists:
        row_count = spark.sql(f"SELECT COUNT(*) AS n FROM {table_name}").first().n
    rows.append(Row(table_name=table_name, exists=exists, row_count=row_count))

result_df = spark.createDataFrame(rows)
display(result_df)

# COMMAND ----------

display(result_df.orderBy("table_name"))


# COMMAND ----------

missing = [r.table_name for r in rows if not r.exists]
if missing:
    raise ValueError(
        "TIL DDL smoke check failed; missing tables: " + ", ".join(missing)
    )

print(f"TIL DDL smoke check passed in {TIL_CATALOG}.{TIL_SCHEMA}")
