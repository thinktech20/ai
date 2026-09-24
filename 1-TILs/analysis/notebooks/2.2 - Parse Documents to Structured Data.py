# Databricks notebook source
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
# MAGIC - A TIL PDF in your Unity Catalog volume.
# MAGIC - **Serverless Compute (environment version 4)**. Follow the instructions [here](https://docs.databricks.com/aws/en/compute/serverless/dependencies#-select-an-environment-version) to select the appropriate environment version.
# MAGIC - Required libraries are added to **Dependencies** of Serverless compute configuration.
# MAGIC
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC Run the following cell to configure this copied notebook for one sample TIL PDF.

# COMMAND ----------

from pyspark.sql.functions import expr
import csv
import json
import os
import re
from pathlib import Path

PDF_PATH = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL 2284 - F-CLASS BALANCE WEIGHT GROOVE ENTRY SLOT RECOMMENDATIONS.pdf"
# PDF_PATH = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL 1603-R2 - R0 EROSION AND WATER INGESTION RECOMMENDATIONS.pdf"
# PDF_PATH = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL 1502-2R1 - 7F AND 9F AFT END COMPRESSOR RUBS.pdf"
# PDF_PATH = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL 2284 - F-CLASS BALANCE WEIGHT GROOVE ENTRY SLOT RECOMMENDATIONS.pdf"
# PDF_PATH = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL 1945-R2 - F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf"
PDF_PATH = "/Volumes/viud/ing_ud_fsr_manual/manual_field_service_report/TILS_new/TIL 1937-R2 - F-CLASS TURBINE WHEEL INSPECTION AND MAINTENANCE RECOMMENDATIONS.pdf"

PDF_DIR = os.path.dirname(PDF_PATH)
IMAGE_OUTPUT_PATH = "/Volumes/vaid/ai_std_con_field_service_report/test_tils/parsed_images/til_2284_dbr_dev"
# Default export root points to Workspace Files so each run writes to:
# /Users/madhurima.saxena@gevernova.com/TILs/ai_parse_extraction/<til_id>/
LOCAL_OUTPUT_ROOT = os.environ.get(
  "TIL_PARSE_OUTPUT_ROOT",
  "/Workspace/Users/madhurima.saxena@gevernova.com/TILs/ai_parse_extraction"
)

catalog = spark.sql("SELECT current_catalog()").first()[0]
schema = spark.sql("SELECT current_schema()").first()[0]
parsed_table = f"{catalog}.{schema}.til_2284_docs_parsed_demo"

print(f"Using PDF_PATH={PDF_PATH}")
print(f"Using IMAGE_OUTPUT_PATH={IMAGE_OUTPUT_PATH}")
print(f"Using LOCAL_OUTPUT_ROOT={LOCAL_OUTPUT_ROOT}")
print(f"Parsed table will be written to {parsed_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC Complete the following steps to view the sample TIL PDF stored in your volume.
# MAGIC
# MAGIC 1. In the workspace sidebar, click on *Catalog* to open the data explorer.
# MAGIC 1. Select the appropriate **catalog** for your environment.
# MAGIC 1. Expand the relevant schema that has access to the FSR volume.
# MAGIC 1. Locate and expand the **TILS_new** volume path.
# MAGIC 1. Download the configured TIL PDF if you want to inspect the source locally before parsing.
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
# Read one sample TIL PDF from the volume
docs_df = spark.read.format("binaryFile").load(PDF_PATH)

# Parse each document using ai_parse_document (use expr for SQL function)
parsed_df = docs_df.withColumn("parsed_content", 
                               expr(f"""ai_parse_document(content, map(
                                    "version", "2.0",
               "imageOutputPath", "{IMAGE_OUTPUT_PATH}"
                                   ))""")
                              )
# Drop binary content
parsed_df = parsed_df.drop("content")

# Display a sample of the parsed results using a display-safe JSON projection.
parsed_df_preview = parsed_df.select(
  "path",
  expr("to_json(parsed_content) as parsed_content_json")
)
display(parsed_df_preview)


def _extract_til_id(pdf_path: str) -> str:
  """Extract the numeric TIL ID from a source PDF path."""
  filename = os.path.basename(pdf_path)
  match = re.search(r"TIL\s*(\d+)", filename, flags=re.IGNORECASE)
  return match.group(1) if match else "unknown"


def export_parsed_outputs(
  parsed_preview_df,
  pdf_path: str,
  output_root: str,
) -> tuple[Path, Path] | None:
  """Write both parsed.json and <til_id>.csv for the first parsed row."""
  rows = parsed_preview_df.limit(1).collect()
  if not rows:
    print("No parsed rows found. Skipping local export.")
    return None

  row = rows[0]
  row_path = row["path"]
  parsed_json = row["parsed_content_json"]
  if not parsed_json:
    print("Empty parsed_content_json. Skipping local export.")
    return None

  til_id = _extract_til_id(pdf_path)
  out_dir = Path(output_root) / til_id
  out_dir.mkdir(parents=True, exist_ok=True)

  json_path = out_dir / "parsed.json"
  csv_path = out_dir / f"{til_id}.csv"

  parsed_obj = json.loads(parsed_json)
  json_path.write_text(json.dumps(parsed_obj, ensure_ascii=False, indent=2), encoding="utf-8")

  with csv_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["path", "parsed_content_json"])
    writer.writeheader()
    writer.writerow(
      {
        "path": row_path,
        "parsed_content_json": json.dumps(parsed_obj, ensure_ascii=False, separators=(",", ":")),
      }
    )

  return json_path, csv_path


exported_paths = export_parsed_outputs(parsed_df_preview, PDF_PATH, LOCAL_OUTPUT_ROOT)
if exported_paths:
  json_path, csv_path = exported_paths
  print(f"Saved parsed JSON to: {json_path}")
  print(f"Saved parsed CSV to: {csv_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC List the files in the TIL source directory.
# MAGIC
# MAGIC Notice it contains the original TIL PDF files. The parser writes extracted images to the configured `IMAGE_OUTPUT_PATH`.

# COMMAND ----------

spark.sql(f"LIST '{PDF_DIR}'").display()

# COMMAND ----------

# MAGIC %md
# MAGIC Run the cell below and observe that the configured parsed image directory now contains a series of output images.

# COMMAND ----------

spark.sql(f"LIST '{IMAGE_OUTPUT_PATH}'").display()

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
docs_df.createOrReplaceTempView("til_docs_binary")

parsed_df_sql = spark.sql(f"""
SELECT
  path,
  ai_parse_document(
    content,
    map(
      'version', '2.0'
    )
  ) as parsed_doc
FROM til_docs_binary""")

display(parsed_df_sql.selectExpr("path", "to_json(parsed_doc) as parsed_doc_json"))

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

# Select key metadata fields as display-safe strings.
meta_df = parsed_df.select(
    "path",
    expr("CAST(to_json(parsed_content:document:pages) AS STRING) as pages_json"),
    expr("CAST(to_json(parsed_content:document:elements) AS STRING) as elements_json"),
    expr("CAST(parsed_content:error_status AS STRING) as error_status"),
    expr("CAST(parsed_content:corrupted_data AS STRING) as corrupted_data"),
    expr("CAST(to_json(parsed_content:metadata) AS STRING) as metadata_json")
)

display(meta_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## B. View and Debug Parsed Document Content
# MAGIC
# MAGIC After parsing, it’s important to inspect and debug the structured output to ensure quality and completeness. In this copied TIL version, we inspect the parsed JSON structure directly so the notebook stays self-contained in DBR dev.

# COMMAND ----------

# MAGIC %md
# MAGIC ### B1. Import DocumentRenderer Helper Class
# MAGIC
# MAGIC This copied notebook stays self-contained, so instead of importing the classroom `DocumentRenderer` helper, we will inspect the parsed structure directly from the DataFrame.

# COMMAND ----------

# DBTITLE 1,Preview parsed document structure
structure_df = parsed_df.select(
  "path",
  expr("CAST(to_json(parsed_content:metadata) AS STRING) as metadata_json"),
  expr("CAST(to_json(parsed_content:document:pages) AS STRING) as pages_json"),
  expr("CAST(to_json(parsed_content:document:elements) AS STRING) as elements_json"),
  expr("json_array_length(CAST(to_json(parsed_content:document:pages) AS STRING)) as page_count"),
  expr("json_array_length(CAST(to_json(parsed_content:document:elements) AS STRING)) as element_count")
)

display(structure_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ### B2. Display Parsed Results
# MAGIC
# MAGIC The code below selects the parsed TIL document and shows a compact preview of page count, element count, and the first few parsed elements. This is usually enough to validate that parsing worked in DBR dev before moving into downstream cleaning or chunking.

# COMMAND ----------

# DBTITLE 1,Display parsed result for one TIL document
sample = structure_df.limit(1).collect()

if sample:
    row = sample[0]
    print(f"Path: {row['path']}")
    print(f"Page count: {row['page_count'] or 0}")
    print(f"Element count: {row['element_count'] or 0}")
    display(
    structure_df.select(
            "path",
      expr("substring(elements_json, 1, 4000) as elements_json_preview")
        )
    )
else:
    print("No parsed documents found. Please check the configured PDF path and parsing step.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## C. Save Parsed Results to Delta Table
# MAGIC
# MAGIC Now that we’ve parsed and explored our documents, let’s save the results for further processing. The parsed content is currently in JSON format, so **we’ll need to clean and transform it** before it can be effectively used for retrieval tasks.

# COMMAND ----------

# DBTITLE 1,Save parsed_df to Delta table
# Save the parsed results as a Delta table for easy querying and sharing
output_table = parsed_table

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