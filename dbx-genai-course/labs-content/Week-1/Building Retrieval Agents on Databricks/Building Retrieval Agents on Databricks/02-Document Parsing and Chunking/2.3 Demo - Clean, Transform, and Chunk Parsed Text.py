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
# MAGIC # Demo - Clean, Transform, and Chunk Parsed Text
# MAGIC
# MAGIC ## Overview
# MAGIC In this demo, we’ll learn how to **clean** and **transform** parsed document text for effective use with language models, and then **chunk** the text for retrieval workflows. The parsed text is currently in JSON format, and we’ll demonstrate two methods to convert it into plain, clean text:
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC By the end of this demo, you will be able to:
# MAGIC 1. **Transform** parsed JSON text into clean, markdown-formatted or plain text suitable for LLMs.
# MAGIC 2. **Compare** two transformation methods: LLM-powered semantic cleaning and fast concatenation.
# MAGIC 3. **Chunk** the cleaned text by page, with overlap for context, using LangChain.
# MAGIC 4. **Store** the final chunked table for downstream embedding and vector search.
# MAGIC
# MAGIC ## Requirements
# MAGIC * **Parsed document table** in JSON format. This table is created in the previous demo. If you haven't done so yet, **you must complete this demo first (`2.2 Demo - Parse Documents to Structured Data`)**.
# MAGIC * **Serverless Compute (environment version 4)**. Follow the instructions [here](https://docs.databricks.com/aws/en/compute/serverless/dependencies#-select-an-environment-version) to select the appropriate environment version.
# MAGIC * Required libraries are added to **Dependencies** of Serverless compute configuration.

# COMMAND ----------

# MAGIC %pip install -qq langchain-text-splitters

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC Run the code below to configure the classroom environment. This step ensures all dependencies are available and your workspace is ready for the demo.

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-02

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Transform Parsed JSON to Clean Text
# MAGIC
# MAGIC In this section, we’ll convert the parsed JSON text into clean, plain text that’s ready for use with language models. We’ll demonstrate two methods:
# MAGIC
# MAGIC 1. **LLM-powered semantic cleaning** using `ai_query` to batch process and convert JSON to markdown text. This method preserves more document semantics but may be more expensive.
# MAGIC 2. **Fast concatenation** by joining all text elements into a single plain text string. This method is quick and cost-effective, but loses some semantic structure (e.g., page headers).
# MAGIC
# MAGIC *In both methods, we’ll use a `== page ==` token to separate pages for later chunking and retrieval workflows.*

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. Load Parsed Document
# MAGIC
# MAGIC Let’s begin by loading the parsed documents generated in the previous demo. This step ensures we have the structured data needed for cleaning and transformation.
# MAGIC
# MAGIC *Reminder: Make sure the parsed table exists and is up to date before proceeding.*

# COMMAND ----------

parsed_table = f"{catalog}.{schema}.docs_parsed"
chunked_table = f"{catalog}.{schema}.docs_chunked"

parsed_df = spark.read.table(parsed_table)

print(f"Loaded parsed documents from: {parsed_table}")
parsed_df.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. LLM-Powered Semantic Cleaning with ai_query
# MAGIC
# MAGIC In this method, we use the `ai_query` function to batch process the parsed JSON text and convert it into clean, markdown-formatted text. This approach leverages a large language model (LLM) to preserve document semantics, such as headers, tables, and structure, making the output more useful for downstream LLM tasks.
# MAGIC
# MAGIC - **Pros:** Retains more structure and meaning, produces high-quality markdown.
# MAGIC - **Cons:** May be more expensive due to LLM usage.
# MAGIC
# MAGIC **⚠️ Warning**: LLM-powered cleaning may incur higher costs for processing many documents. Use fast concatenation for quick, low-cost processing.
# MAGIC
# MAGIC **Note:** The `ai_query` function supports many foundation models, including those from OpenAI, Anthropic, and Databricks. In this demo, we will use OpenAI's GPT-5 Open Source model.
# MAGIC
# MAGIC We’ll instruct the LLM to parse the JSON and output clean markdown, using `== page ==` as a separator between pages.

# COMMAND ----------

# DBTITLE 1,Python: Batch process parsed text with ai_query
from pyspark.sql.functions import expr

# Choose a Databricks foundation model (or your own serving endpoint name)
ENDPOINT = "databricks-gpt-oss-20b"

# Example prompt for the LLM
prompt_prefix = '''
You are a helpful assistant. Given a JSON object representing a parsed document (with pages, elements, and metadata), convert the content into clean, readable markdown. Use "== page ==" to separate each page. Preserve important structure such as headers, tables, and captions. Do not include any JSON or code blocks in the output—just the clean markdown text.

JSON:

'''

# Apply ai_query to batch process the parsed JSON text
transformed_df = (
    parsed_df.withColumn(
        "clean_markdown_text",
        expr(f"""
          ai_query(
            '{ENDPOINT}',
            CONCAT('{prompt_prefix}', CAST(parsed_content AS STRING)),
            responseFormat => '{{"type":"text"}}'
          )
        """)
    )
)

display(transformed_df.select("path", "clean_markdown_text"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Fast Plain Text Conversion
# MAGIC
# MAGIC In this method, we rapidly concatenate all text elements from the parsed JSON into a single plain text string. This approach is fast and cost-effective, but it sacrifices document structure—such as headers, tables, and captions.
# MAGIC
# MAGIC - **Pros:** Fast, inexpensive, and simple to implement.
# MAGIC - **Cons:** Loses important structure and semantics.
# MAGIC
# MAGIC **NOTE:** We use Spark to extract and join text from each page, inserting a `== page ==` token between pages for later chunking.
# MAGIC
# MAGIC The content extraction logic is provided in the `Includes/content_extractor` file.

# COMMAND ----------

from pyspark.sql import functions as F

# Convert VARIANT/struct/map to a JSON string first (avoids VariantVal issues)
safe_json_col = F.coalesce(
    F.to_json(F.col("parsed_content")),
    F.col("parsed_content").cast("string")
)

# Apply the UDF
plain_text_df = parsed_df.withColumn(
    "plain_text",
    extract_contents_udf()(safe_json_col)
)

display(plain_text_df.select("path", "plain_text"))


# COMMAND ----------

# MAGIC %md
# MAGIC ## B. Chunk Cleaned Text for Retrieval
# MAGIC
# MAGIC Now that we have clean, page-separated text, we’ll chunk it for retrieval workflows. Chunking helps language models and vector search systems efficiently process and retrieve relevant information.
# MAGIC
# MAGIC We’ll use LangChain’s `RecursiveCharacterTextSplitter` to split the text by the `== page ==` token. This utility automatically handles chunking and overlap, making it easy to prepare text for embedding and search.
# MAGIC
# MAGIC **Note:** Overlap is only introduced when a single input is split into multiple chunks. In this example, each page typically forms one chunk with `chunk_size=2000`, so some rows may not show any overlap. To observe overlapping chunks more clearly, try reducing the chunk size.

# COMMAND ----------

# DBTITLE 1,Python: Chunk plain text by page with overlap using LangChain
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pyspark.sql.types import StructType, StructField, StringType
import pandas as pd

# Set chunking parameters: chunk_size controls the max length of each chunk, and chunk_overlap allows for overlapping text between chunks to improve retrieval quality.
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

# Build the text splitter with preferred separators.
# This splitter will break the text at page markers or other natural boundaries, preserving document structure where possible.
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n== page ==\n", "== page ==", "\n\n", "\n", " ", ""]
)

# Define the output schema for the chunked DataFrame.
# Each row will contain the document path and a single text chunk.
schema = StructType([
    StructField("path", StringType(), True),
    StructField("chunk", StringType(), True),
])

def split_rows(iterator):
    """
    mapInPandas function: input pdfs with columns [path, plain_text],
    output rows [path, chunk].
    This function splits each document's text into chunks and yields them for DataFrame construction.
    """
    for pdf in iterator:
        out = []
        for _, row in pdf.iterrows():
            path = row["path"]
            text = row["plain_text"]
            if isinstance(text, str) and text.strip():
                for c in splitter.split_text(text):
                    if c and c.strip():
                        out.append((path, c))
        yield pd.DataFrame(out, columns=["path", "chunk"])

# Apply the splitter to the plain text DataFrame.
# This step transforms each document into multiple chunked rows for efficient downstream retrieval and embedding.
df_chunks = (
    plain_text_df
    .select("path", "plain_text")
    .mapInPandas(split_rows, schema=schema)
)

# Display the resulting chunked DataFrame for inspection.
display(df_chunks)

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Save Chunked Data to Delta Table
# MAGIC
# MAGIC Let’s save our chunked text data to a Delta table for downstream embedding and retrieval workflows.
# MAGIC
# MAGIC **Task:** Write the chunked DataFrame to the table defined as **`chunked_table`** in the setup section.

# COMMAND ----------

# DBTITLE 1,Python: Save chunked DataFrame to Delta table
from pyspark.sql import functions as F

# Add a unique, incremental id column before saving
df_chunks = df_chunks.withColumn("id", F.monotonically_increasing_id())

# Save the chunked data with id to the Delta table for retrieval and embedding
df_chunks.write.format("delta").mode("overwrite").option("mergeSchema", "true").saveAsTable(chunked_table)

display(spark.read.table(chunked_table))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary and Next Steps
# MAGIC
# MAGIC In this demo, we loaded parsed documents, applied both **LLM-powered semantic cleaning** and **fast plain text extraction**, and **chunked** the results for retrieval workflows. We then saved the chunked data to a Delta table, preparing it for embedding and integration with vector search and LLM-powered applications.
# MAGIC
# MAGIC **Key Takeaways:**
# MAGIC - Use LLM-powered semantic cleaning or fast concatenation to prepare text for chunking.
# MAGIC - Chunk text by page.
# MAGIC - Store chunked data in a Delta table for easy integration with vector search and embedding pipelines.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>