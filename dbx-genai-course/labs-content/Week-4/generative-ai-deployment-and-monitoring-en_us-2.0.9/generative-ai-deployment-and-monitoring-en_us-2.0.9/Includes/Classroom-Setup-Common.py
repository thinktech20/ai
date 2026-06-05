# Databricks notebook source
# code common to all notebooks belongs in this notebook. Please do not modify **_common**, as it may be dynamically manipulated
# and any changes you make to it may be lost at deploy time.

# COMMAND ----------

# MAGIC %run ./_common

# COMMAND ----------

@DBAcademyHelper.add_method
def validate_table(self, name):
    if spark.catalog.tableExists(name):
        print(f'Validation of table {name} complete. No errors found.')
        return True
    else:
        raise AssertionError(f"The table {name} does not exist")

# COMMAND ----------

print("\nThe examples and models presented in this course are intended solely for demonstration and educational purposes.\n Please note that the models and prompt examples may sometimes contain offensive, inaccurate, biased, or harmful content.")