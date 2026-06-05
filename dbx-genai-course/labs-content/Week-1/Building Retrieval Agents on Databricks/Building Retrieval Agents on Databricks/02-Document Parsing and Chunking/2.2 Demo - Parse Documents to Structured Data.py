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
# MAGIC # Demo - Parse Documents to Structured Data
# MAGIC
# MAGIC ## Overview
# MAGIC
# MAGIC In this demo, we’ll explore how to parse unstructured documents into structured data using Databricks’ **AI-powered document parsing** capabilities. This process enables you to extract tables, images, and text from files stored in a volume, making it easier to analyze, search, and build downstream workflows.
# MAGIC
# MAGIC In most real-world retrieval agent use cases, you’ll encounter documents that need to be parsed to create a structured knowledge base. This knowledge base can then be used to provide additional context to language models.
# MAGIC
# MAGIC ## Learning Objectives
# MAGIC By the end of this demo, you will be able to:
# MAGIC - **Parse** multi-format documents (PDF, DOCX) using the `ai_parse_document()` function in both SQL and Python.
# MAGIC - **Inspect** and understand the parsed output schema.
# MAGIC - **Identify** and interpret key metadata fields in the parsed output.
# MAGIC - **Visualize** and debug parsed document content.
# MAGIC
# MAGIC ## Requirements:
# MAGIC - A volume containing sample documents. **This is created with setup code for you.**
# MAGIC - **Serverless Compute (environment version 4)**. Follow the instructions [here](https://docs.databricks.com/aws/en/compute/serverless/dependencies#-select-an-environment-version) to select the appropriate environment version.
# MAGIC - Required libraries are added to **Dependencies** of Serverless compute configuration.
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC Run the following cells to configure the classroom environment. Volume name that contains sample documents and will be used in this demo printed below.

# COMMAND ----------

# MAGIC %run ../Includes/Classroom-Setup-02

# COMMAND ----------

# MAGIC %md
# MAGIC Complete the following steps to view one of the PDF files stored in your volume. Follow these instructions using the volume name printed above.
# MAGIC
# MAGIC 1. In the workspace sidebar, click on *Catalog* to open the data explorer.
# MAGIC 1. Select the appropriate **catalog** for your environment.
# MAGIC 1. Expand the relevant **schema (`datasets`)** within the catalog.
# MAGIC 1. Locate and expand the **orion-docs** volume.
# MAGIC 1. Download the **01_Orion_A1_Product_Overview.pdf** file to your local machine.
# MAGIC 1. Open the file and review its contents to understand the document before parsing.
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## A. Parsing Documents with AI
# MAGIC
# MAGIC In this section, we’ll learn how to use the `ai_parse_document` function to extract structured data from unstructured documents. This function leverages Databricks Mosaic AI to automatically identify and extract text, tables, and images from files such as PDFs and images. We’ll demonstrate both SQL and Python approaches, and explain the key metadata fields produced by the parser. This capability is valuable for automating document processing and enabling advanced analytics.
# MAGIC
# MAGIC **🚨 Note:** You must use **Version 2** of `ai_parse_document` to get the parsed format covered in this demo.

# COMMAND ----------

# MAGIC %md
# MAGIC ### A1. Parsing Documents with Python
# MAGIC
# MAGIC **Python** is ideal for flexible, interactive workflows and integration with machine learning or custom logic. Here, we use the Spark DataFrame API and the `expr` function to call `ai_parse_document` on each file. This lets you inspect results, apply further transformations, or build ML pipelines.
# MAGIC
# MAGIC After running the code, review the DataFrame output to see how each document is parsed. If your volume is empty, check your path and permissions.
# MAGIC
# MAGIC The `ai_parse_document` function accepts options such as:
# MAGIC - **`version`**: The parser version to use (e.g., `'2.0'`).
# MAGIC - **`imageOutputPath`**: Where to store extracted images.
# MAGIC - **`descriptionElementTypes`**: Which elements to extract (e.g., `*`, `table`, `image`, `text`).
# MAGIC
# MAGIC
# MAGIC **Note:** We are dropping the binary content field as `display` function doesn't show the result. Binary field is too long to display.

# COMMAND ----------

# DBTITLE 1,ai_parse_document Python example (code)
from pyspark.sql.functions import expr

# Read all files from the documents volume
docs_df = spark.read.format("binaryFile").load(user_docs_path)

# Parse each document using ai_parse_document (use expr for SQL function)
parsed_df = docs_df.withColumn("parsed_content", 
                               expr(f"""ai_parse_document(content, map(
                                    "version", "2.0",
                                    "imageOutputPath", "{user_docs_path}/parsed_images/"
                                   ))""")
                              )
# Drop binary content
parsed_df = parsed_df.drop("content")

# Display a sample of the parsed results
display(parsed_df)

# COMMAND ----------

# MAGIC %md
# MAGIC List the files in your volumes path. 
# MAGIC
# MAGIC   Notice it contains both the original PDF files used for the demonstration and the new `/parsed_images/` directory, which holds all of the output images generated during parsing.

# COMMAND ----------

spark.sql(f"LIST '{user_docs_path}'").display()

# COMMAND ----------

# MAGIC %md
# MAGIC Run the cell below and observe that the `/parsed_images/` directory in your volume now contains a series of output images.

# COMMAND ----------

spark.sql(f"LIST '{user_docs_path}/parsed_images'").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ### A2. Parsing with SQL
# MAGIC
# MAGIC **SQL** is great for batch processing and easy integration with Lakehouse tables. The example below parses all documents in the specified volume and returns a structured result.
# MAGIC
# MAGIC This approach is ideal for scheduled jobs or when you want to persist results in a table.
# MAGIC
# MAGIC **Note:** If the image output path is not defined, the images extracted during the previous parsing are also parsed. 

# COMMAND ----------

# DBTITLE 1,ai_parse_document SQL example (code)
parsed_df_sql = spark.sql(f"""
SELECT
  path,
  ai_parse_document(
    content,
    map(
      'version', '2.0'
    )
  ) as parsed_doc
FROM read_files('{user_docs_path}', format => 'binaryFile')""")

display(parsed_df_sql)

# COMMAND ----------

# MAGIC %md
# MAGIC ### A3. Understanding Parsed Document Metadata
# MAGIC
# MAGIC The output of `ai_parse_document` includes a rich metadata structure in the `parsed_content` field. **Key fields include:**
# MAGIC
# MAGIC - **`parsed:document:pages`**: A list of page objects, each with:
# MAGIC   - **`page_number`**: The page’s index in the document.
# MAGIC   - **`text`**: Extracted text content.
# MAGIC   - **`tables`**: Structured table data, if detected.
# MAGIC   - **`images`**: Extracted images, often as base64 or file references.
# MAGIC - **`parsed:document:metadata`**: General document info (file name, size, format).
# MAGIC
# MAGIC *You can use these fields to build search indexes, automate reporting, or feed downstream ML models. For large documents, consider paginating or filtering results. If some fields are missing, check the document type and parser options.*

# COMMAND ----------

# DBTITLE 1,Python: Display parsed document metadata
# Display document path and key metadata fields
from pyspark.sql.functions import expr

# Select key metadata fields using expr for nested fields
meta_df = parsed_df.select(
    "path",
    expr("parsed_content:document:pages"),
    expr("parsed_content:document:elements"),
    expr("parsed_content:error_status"),
    expr("parsed_content:corrupted_data"),
    expr("parsed_content:metadata")
)

display(meta_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. View and Debug Parsed Document Content
# MAGIC
# MAGIC After parsing, it’s important to inspect and debug the structured output to ensure quality and completeness. **Visualization** helps you validate extraction accuracy and understand how the parser handles mixed content. We’ll use a helper class to render the parsed results, making it easier to review text, tables, and images from each page.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Import DocumentRenderer Helper Class
# MAGIC
# MAGIC The `DocumentRenderer` class is a utility for visualizing parsed document content in Databricks notebooks. It supports rendering text, tables, and images from each page, which is critical for document QA and workflow validation.
# MAGIC
# MAGIC You can find the helper class in the **Includes** folder or as provided by your instructor. We won’t cover its implementation here—just use it to streamline your workflow and focus on interpreting results.

# COMMAND ----------

# DBTITLE 1,Import DocumentRenderer helper class
# Import the DocumentRenderer helper class
import sys, os
sys.path.append(os.path.abspath('..'))
from Includes.document_renderer import render_ai_parse_output, render_ai_parse_output_interactive

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. Display Parsed Results
# MAGIC
# MAGIC The code below selects a document with both images and tables (if available) and uses the `DocumentRenderer` helper class to visualize its parsed content. You should see a visual representation of the document’s pages, including extracted text, tables, and images. This makes it much easier to debug and understand how the AI parser has structured the content for downstream analysis.
# MAGIC
# MAGIC *If no suitable document is found, check your volume for files with mixed content or adjust the filter logic.*

# COMMAND ----------

# DBTITLE 1,Display parsed result for one document
# Select a sample document and render its parsed content using render_ai_parse_output
sample = parsed_df.select("parsed_content").limit(1).collect()

if sample:
    doc = sample[0]["parsed_content"]
    render_ai_parse_output(doc)
else:
    print("No parsed documents found. Please check your input volume and parsing step.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Save Parsed Results to Delta Table
# MAGIC
# MAGIC Now that we’ve parsed and explored our documents, let’s save the results for further processing. The parsed content is currently in JSON format, so **we’ll need to clean and transform it** before it can be effectively used for retrieval tasks.

# COMMAND ----------

# DBTITLE 1,Save parsed_df to Delta table
# Save the parsed results as a Delta table for easy querying and sharing
output_table = f"{catalog}.{schema}.docs_parsed"

# Overwrite the table if it already exists
parsed_df.write.format("delta").mode("overwrite").saveAsTable(output_table)

print(f"✅ Parsed results saved to Delta table: {output_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary and Next Steps
# MAGIC
# MAGIC You’ve learned how to parse unstructured documents using Databricks’ AI-powered `ai_parse_document` function in both Python and SQL. We demonstrated how to batch process files, extract structured content and metadata, and visualize results for quality assurance. By integrating these techniques, you can automate document extraction workflows and prepare data for downstream analytics or machine learning tasks.
# MAGIC
# MAGIC **Key Takeaways:**
# MAGIC - **Automate** document parsing with the `ai_parse_document` function in both Python and SQL.
# MAGIC - **Inspect** and understand the parsed output schema, including key metadata fields like `pages`, `elements`, and `metadata`.
# MAGIC - **Visualize** and debug parsed results using the DocumentRenderer helper class for quality assurance and workflow validation.
# MAGIC
# MAGIC For more information about the `ai_parse_document`, check the [official Databricks documentation](https://docs.databricks.com/sql/language-manual/functions/ai_parse_document.html).

# COMMAND ----------

# MAGIC %md
# MAGIC &copy; 2026 Databricks, Inc. All rights reserved. Apache, Apache Spark, Spark, the Spark Logo, Apache Iceberg, Iceberg, and the Apache Iceberg logo are trademarks of the <a href="https://www.apache.org/" target="_blank">Apache Software Foundation</a>.<br/><br/><a href="https://databricks.com/privacy-policy" target="_blank">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use" target="_blank">Terms of Use</a> | <a href="https://help.databricks.com/" target="_blank">Support</a>