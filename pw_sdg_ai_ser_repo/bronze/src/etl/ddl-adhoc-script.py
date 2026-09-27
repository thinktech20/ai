# Databricks notebook source
dbutils.widgets.text("filename", " ", "Set the noteook path files (comma separated values) ")

# COMMAND ----------

# Get the list of notebooks to run from the widget
notebooks_to_run = dbutils.widgets.get("filename").split(',')

# print(type(notebooks_to_run))
# Function to run multiple notebooks
def run_notebooks(notebook_paths, timeout=600000):
    results = []
    for path in notebook_paths:
        result = dbutils.notebook.run(path, timeout)
        results.append(result)
    return results

# Execute the notebooks
execution_results = run_notebooks(notebooks_to_run)

# Display results
for i, result in enumerate(execution_results):
    print(f"{notebooks_to_run[i]} - is executed sucessfully;")
