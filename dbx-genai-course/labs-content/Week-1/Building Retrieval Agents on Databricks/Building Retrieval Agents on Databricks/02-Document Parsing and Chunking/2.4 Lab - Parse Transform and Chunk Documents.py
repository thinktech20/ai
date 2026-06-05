# Databricks notebook source
# MAGIC %md
# MAGIC
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img
# MAGIC     src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png"
# MAGIC     alt="Databricks Learning"
# MAGIC   >
# MAGIC </div>
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC # Lab - Parse, Transform and Chunk Documents
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC In this lab, you will work with a set of documents stored in a specified volume. You will learn how to **parse**, **transform**, and **chunk** these documents using Python and Databricks tools. The final results will be saved to a Delta table for further analysis.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC By the end of this lab, you will be able to:
# MAGIC 1. **Parse** the documents using Python.
# MAGIC 2. **Flatten** the parsed documents from JSON format.
# MAGIC 3. **Use AI Query** to convert JSON to Markdown.
# MAGIC 4. **Chunk** the Markdown by a constant size.
# MAGIC 5. **Save** the results to a Delta table.
# MAGIC
# MAGIC ## Requirements
# MAGIC - A volume containing sample documents. This is created with setup code. This is done in the workspace config.
# MAGIC - **Serverless Compute (environment version 4)**.
# MAGIC - Required libraries are added to **Dependencies** of Serverless compute configuration.
# MAGIC
# MAGIC **📌 Your Task: In this lab, your task is to replace `<FILL_IN>` sections with appropriate code.**

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC Run the code below to install required libraries and configure your classroom environment.
# MAGIC
# MAGIC This step ensures all dependencies are available and your workspace is ready for the demo.

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-02

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 1: Parse Documents Using Python
# MAGIC
# MAGIC In this section, you will **load and parse** a set of documents from a specified volume. Use Python to read the files and parse their contents for further processing.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Use the provided variable for the volume path (e.g., `docs_path`).
# MAGIC 2. Parse each document using the AI document parsing function.
# MAGIC 3. Store the parsed results in a DataFrame named `df_raw`.
# MAGIC
# MAGIC Complete the code below to perform this task.

# COMMAND ----------

# Parse all documents in the specified volume using ai_parse_document
# Store the parsed results in a DataFrame named df_raw

from pyspark.sql.functions import expr

# Read all files from the documents volume as binary
files_df = spark.read.format("binaryFile").load(user_docs_path)

# Parse each document using ai_parse_document (version 2.0)
df_raw = files_df.withColumn(
   "parsed_content",
   expr(f"ai_parse_document(content, map('version', '2.0', 'imageOutputPath', '{user_docs_path}/parsed_images/'))")
)

# Drop the binary content column for easier display
result_df = df_raw.drop("content")
display(result_df)

# COMMAND ----------

# MAGIC %skip
# MAGIC # Parse all documents in the specified volume using ai_parse_document
# MAGIC # Store the parsed results in a DataFrame named df_raw
# MAGIC from pyspark.sql.functions import expr
# MAGIC
# MAGIC # Read all files from the documents volume as binary
# MAGIC files_df = spark.read.format("binaryFile").load(user_docs_path)
# MAGIC
# MAGIC # Parse each document using ai_parse_document (version 2.0)
# MAGIC df_raw = files_df.withColumn(
# MAGIC    "parsed_content",
# MAGIC    expr(f"ai_parse_document(content, map('version', '2.0', 'imageOutputPath', '{user_docs_path}/parsed_images/'))")
# MAGIC )
# MAGIC
# MAGIC # Drop the binary content column for easier display
# MAGIC result_df = df_raw.drop("content")
# MAGIC display(result_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 2: Flatten Parsed JSON Documents
# MAGIC
# MAGIC In this section, you will **transform the parsed JSON content** into a flat, tabular structure for easier analysis and downstream processing.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Extract relevant fields from the `parsed_content` column in `df_raw`.
# MAGIC 2. Create a new DataFrame named `df_flat`.
# MAGIC 3. Focus on extracting key metadata and page-level information.
# MAGIC
# MAGIC Complete the code below to perform this task.

# COMMAND ----------

# Flatten the parsed_content column from df_raw
# Extract only the 'elements' field into df_flat

from pyspark.sql.functions import expr

df_flat = df_raw.select(
   "path",
   expr("parsed_content:document:elements").alias("elements")
)
display(df_flat)

# COMMAND ----------

# MAGIC %skip
# MAGIC # Flatten the parsed_content column from df_raw
# MAGIC # Extract only the 'elements' field into df_flat
# MAGIC from pyspark.sql.functions import expr
# MAGIC
# MAGIC df_flat = df_raw.select(
# MAGIC    "path",
# MAGIC    expr("parsed_content:document:elements").alias("elements")
# MAGIC )
# MAGIC display(df_flat)

# COMMAND ----------

# DBTITLE 1,Task 2: Flatten the Parsed Document # TODO
# MAGIC %md
# MAGIC ## Task 3: Convert JSON to Markdown Using AI Query
# MAGIC
# MAGIC In this section, you will use the **ai_query** function to convert the JSON elements into clean, readable Markdown format. This approach leverages a large language model to preserve document semantics, such as headers, tables, and structure, making the output more useful for downstream LLM tasks.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Use a prompt to instruct the LLM to convert JSON to Markdown.
# MAGIC 2. Store the Markdown results in a new column named `markdown` in the DataFrame `df_markdown`.
# MAGIC
# MAGIC Complete the code below to perform this task.

# COMMAND ----------

# Convert the JSON 'elements' to Markdown using AI Query

from pyspark.sql.functions import expr, concat, lit, col

# Choose a Databricks foundation model endpoint
ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"

# Prompt for the LLM
prompt_prefix = '''
You are a helpful assistant. Given a JSON object representing document elements, convert the content into clean, readable markdown. Preserve important structure such as headers, tables, and captions. Do not include any JSON or code blocks in the output—just the clean markdown text.

JSON:
'''

# Apply ai_query to convert elements to Markdown
# Concatenate the prompt and elements as string
# Specify responseFormat for text output
df_markdown = df_flat.withColumn(
    "markdown",
    expr(f"ai_query('{ENDPOINT}', CONCAT('{prompt_prefix}', CAST(elements AS STRING)), responseFormat => '{{\"type\":\"text\"}}')")
)
display(df_markdown)

# COMMAND ----------

# MAGIC %skip
# MAGIC # Convert the JSON 'elements' to Markdown using AI Query
# MAGIC from pyspark.sql.functions import expr, concat, lit, col
# MAGIC
# MAGIC # Choose a Databricks foundation model endpoint
# MAGIC ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
# MAGIC
# MAGIC # Prompt for the LLM
# MAGIC prompt_prefix = '''
# MAGIC You are a helpful assistant. Given a JSON object representing document elements, convert the content into clean, readable markdown. Preserve important structure such as headers, tables, and captions. Do not include any JSON or code blocks in the output—just the clean markdown text.
# MAGIC
# MAGIC JSON:
# MAGIC '''
# MAGIC
# MAGIC # Apply ai_query to convert elements to Markdown
# MAGIC # Concatenate the prompt and elements as string
# MAGIC # Specify responseFormat for text output
# MAGIC df_markdown = df_flat.withColumn(
# MAGIC     "markdown",
# MAGIC     expr(f"ai_query('{ENDPOINT}', CONCAT('{prompt_prefix}', CAST(elements AS STRING)), responseFormat => '{{\"type\":\"text\"}}')")
# MAGIC )
# MAGIC display(df_markdown)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 4: Chunk Markdown by Constant Size
# MAGIC
# MAGIC In this section, you will **split the Markdown text into chunks** of a fixed size for efficient retrieval and downstream processing. You will use the langchain-text-splitters library to perform the chunking.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Set a constant chunk size (e.g., 1000 characters) and overlap (e.g., 200 characters).
# MAGIC 2. Store the chunked results in a new DataFrame named `df_chunks`.
# MAGIC
# MAGIC Complete the code below to perform this task.

# COMMAND ----------

# Chunk the Markdown text by a constant size using langchain-text-splitters
from pyspark.sql.functions import udf, col, explode
from pyspark.sql.types import ArrayType, StringType
from langchain_text_splitters import RecursiveCharacterTextSplitter

# parameters
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)

@udf(ArrayType(StringType()))
def split_md(s: str):
    if not s or not s.strip():
        return []
    return [c for c in splitter.split_text(s) if c and c.strip()]

# Explode the split markdown into chunks
df_chunks = df_markdown.select("path", explode(split_md("markdown")).alias("chunk"))

display(df_chunks)

# COMMAND ----------

# MAGIC %skip
# MAGIC # Chunk the Markdown text by a constant size using langchain-text-splitters
# MAGIC from pyspark.sql.functions import udf, col, explode
# MAGIC from pyspark.sql.types import ArrayType, StringType
# MAGIC from langchain_text_splitters import RecursiveCharacterTextSplitter
# MAGIC
# MAGIC
# MAGIC # parameters
# MAGIC CHUNK_SIZE = 1000
# MAGIC CHUNK_OVERLAP = 200
# MAGIC
# MAGIC
# MAGIC splitter = RecursiveCharacterTextSplitter(
# MAGIC     chunk_size=CHUNK_SIZE,
# MAGIC     chunk_overlap=CHUNK_OVERLAP
# MAGIC )
# MAGIC
# MAGIC
# MAGIC @udf(ArrayType(StringType()))
# MAGIC def split_md(s: str):
# MAGIC     if not s or not s.strip():
# MAGIC         return []
# MAGIC     return [c for c in splitter.split_text(s) if c and c.strip()]
# MAGIC
# MAGIC
# MAGIC df_chunks = df_markdown.select("path", explode(split_md("markdown")).alias("chunk"))
# MAGIC display(df_chunks)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Task 5: Save Results to Delta Table
# MAGIC
# MAGIC In this section, you will **save the chunked Markdown results** to a Delta table for downstream analysis and retrieval workflows.
# MAGIC
# MAGIC **Steps:**
# MAGIC 1. Use the provided catalog and schema variables to define the output table name.
# MAGIC 2. Write the DataFrame `df_chunks` to the Delta table using overwrite mode.
# MAGIC
# MAGIC Complete the code below to perform this task.

# COMMAND ----------

# Save the chunked results to a Delta table for downstream analysis

# Define the output table name using catalog and schema variables
output_table = f"{catalog}.{schema}.lab_chunked_docs"

# Write the DataFrame to the Delta table
# Overwrite the table if it already exists
df_chunks.write.format("delta").mode("overwrite").saveAsTable(output_table)

print(f"✅ Chunked results saved to Delta table: {output_table}")

# COMMAND ----------

# MAGIC %skip
# MAGIC # Save the chunked results to a Delta table for downstream analysis
# MAGIC # Define the output table name using catalog and schema variables
# MAGIC output_table = f"{catalog}.{schema}.lab_chunked_docs"
# MAGIC
# MAGIC # Write the DataFrame to the Delta table
# MAGIC # Overwrite the table if it already exists
# MAGIC df_chunks.write.format("delta").mode("overwrite").saveAsTable(output_table)
# MAGIC
# MAGIC print(f"✅ Chunked results saved to Delta table: {output_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary and Next Steps
# MAGIC
# MAGIC You have completed the lab to parse, transform, and chunk documents using Python and Databricks tools. You learned how to:
# MAGIC
# MAGIC * **Parse** documents from a volume and extract structured content.
# MAGIC * **Flatten** parsed JSON to select relevant elements.
# MAGIC * **Use AI Query** to convert JSON elements to Markdown.
# MAGIC * **Chunk** Markdown text by a constant size for efficient retrieval.
# MAGIC * **Save** the final results to a Delta table for downstream analysis.
# MAGIC
# MAGIC **Next Steps (Optional):**
# MAGIC * Explore how to embed and search chunked data using vector search or LLM-powered retrieval.
# MAGIC * Experiment with different chunk sizes and prompts to optimize your workflow.
# MAGIC * Review the Delta table and validate the results for your use case.

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>