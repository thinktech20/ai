# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# FSR Scraping Pipeline — Step-by-Step Test Notebook
#
# Safe interactive testing — NO writes to existing tables or volumes.
# Output: main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref__dev_tmp
#
# Cluster: ai_dev_dbr  (DEV workspace)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# ── Cell 1: Install dependencies ─────────────────────────────────────────────
# MAGIC %pip install --quiet pdfplumber

# COMMAND ----------

# ── Cell 2: Restart Python ───────────────────────────────────────────────────
dbutils.library.restartPython()

# COMMAND ----------

# ── Cell 3: Read a single PDF (read-only test) ──────────────────────────────
import pdfplumber

test_pdf = "/Volumes/viud/ing_ud_fieldvision/fv_field_service_report/000496d8-fefa-4b6c-a654-791e328a4ddb"

with pdfplumber.open(test_pdf) as pdf:
    first_page = pdf.pages[0]
    text = first_page.extract_text()
    print(f"Pages in PDF: {len(pdf.pages)}")
    print(f"First page text length: {len(text) if text else 0}")
    print("---")
    print(text[:2000] if text else "[no text extracted]")

# COMMAND ----------

# ── Cell 4: Stage 1 — Extract fields from first page ────────────────────────
import json

def extract_fields_from_pdf(pdf_path: str) -> dict:
    """Stage 1: Extract key:value fields and title from the first page."""
    fields = {"PDF Name / path / identifier": pdf_path}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            if not text:
                return fields
            lines = text.splitlines()
            current_key = None
            title_lines = []
            for line in lines:
                if ":" in line:
                    break
                title_lines.append(line.strip())
            if title_lines:
                fields["Title"] = " ".join(title_lines)
            for line in lines:
                if ":" in line:
                    parts = line.split(":", 1)
                    key = parts[0].strip()
                    value = parts[1].strip()
                    current_key = key
                    if key in fields:
                        fields[key] = f"{fields[key]} | {value}"
                    else:
                        fields[key] = value
                else:
                    if current_key:
                        fields[current_key] += " " + line.strip()
    except Exception as e:
        print(f"  [WARN] Error extracting {pdf_path}: {e}")
    return fields

result = extract_fields_from_pdf(test_pdf)
print(json.dumps(result, indent=2))

# COMMAND ----------

# ── Cell 5: Stage 2 — LLM normalization (single record) ─────────────────────
# BLOCKED: needs working LLM gateway URL.
#
# Two issues to resolve:
#   1. Secret scope access: ask Pranesh to run:
#        databricks secrets put-acl fsr-pipeline madhurima.saxena@ge.com READ
#   2. Gateway returning 502 on dev-gateway.apps.gevernova.net
#      → check confluence for correct URL or alternative gateway
#
# Once resolved, uncomment and run:

import requests

# Option A: from secret scope (once access is granted)
# LITELLM_API_KEY = dbutils.secrets.get(scope="fsr-pipeline", key="LITELLM_API_KEY")
# LITELLM_BASE_URL = dbutils.secrets.get(scope="fsr-pipeline", key="LITELLM_BASE_URL")

# Option B: direct (for testing only)
# LITELLM_API_KEY = "YOUR_KEY"
# LITELLM_BASE_URL = "https://CORRECT_GATEWAY_URL"

SYSTEM_PROMPT = (
    "You are an expert in structuring technical data. "
    "Your task is to process the provided input json and output a structured/normalized "
    "JSON format according to user instructions. Focus on clarity, completeness, and "
    "following the JSON schema provided. Do not include any internal reasoning or system "
    "details in the output."
)

NORMALIZATION_PROMPT = """Your task is to process JSON input and output a normalized JSON format
with the following fields only:

ESN, Equipment Sys ID, Equipment Type, Equipment Class / Code, Event Type,
EV Project ID, EV Equipment Event ID, OFS Event ID, FSP project ID, xxx project id,
PDF Name / path / identifier, FSR Number (#), Report Issued Date, Outage Start Date, Outage End Date.

If the PDF field contains an Oracle Project Id, map it to OFS Event ID only. But do not include field values that start with "EV" and "EVP" under OFS Event ID.
Map the PDF field containing "EV-" to EV Equipment Event ID only.
Map the PDF field containing "EVP-" to EV Project ID only.
Map the PDF field containing "SY" to Equipment Sys ID only.
If the PDF field contains a Field Service Project Id or "FSP-", map it to FSP project ID only.
If the PDF field contains a project id that starts with other prefixes (A-, C-, etc.), map it to xxx project id only.
If no relevant information is found, output it as an empty string.
Do not include any reasoning or commentary, only valid JSON output.
"""

# prompt = f"Here is a JSON list of PDF fields:\n{json.dumps([result], indent=2)}\n\n{NORMALIZATION_PROMPT}"
# base = LITELLM_BASE_URL.rstrip("/")
# resp = requests.post(
#     f"{base}/v1/chat/completions",
#     headers={"Authorization": f"Bearer {LITELLM_API_KEY}", "Content-Type": "application/json"},
#     json={
#         "model": "gemini-3-flash",
#         "messages": [
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user", "content": prompt},
#         ],
#     },
#     timeout=120,
#     verify=False,
# )
# print(f"HTTP {resp.status_code}")
# llm_output = resp.json()["choices"][0]["message"]["content"]
# print(llm_output)

print("⚠️  Stage 2 blocked — resolve LLM gateway URL first (see comments above)")

# COMMAND ----------

# ── Cell 6: Stage 3 — IBAT + Event Vision enrichment (read-only joins) ──────
# Depends on Stage 2 output. Sketch below for when Stage 2 works.
#
# from pyspark.sql import SparkSession
# from pyspark.sql.functions import col, when, trim, concat, lit, upper, regexp_replace
# from pyspark.sql.types import StringType
# import pandas as pd
#
# spark = SparkSession.builder.getOrCreate()
#
# # Load lookup tables (read-only)
# ibat = spark.read.table("vgpd.prm_std_views.ibat_equipment_mst").select(
#     upper(trim(col("equipment_sys_id"))).cast(StringType()).alias("ibat_equipment_sys_id"),
#     upper(trim(col("equip_serial_number"))).cast(StringType()).alias("ibat_equip_serial_number"),
#     col("equipment_type").cast(StringType()).alias("ibat_equipment_type"),
#     col("equipment_sub_class").cast(StringType()).alias("ibat_equipment_code"),
# )
#
# ev_sot = spark.read.table("vgpd.fsr_std_views.eventmgmt_event_vision_sot").select(
#     col("ev_project_id").cast(StringType()).alias("sot_ev_project_id"),
#     col("ev_equipment_event_id").cast(StringType()).alias("sot_ev_equipment_event_id"),
#     col("ev_gtm_id").cast(StringType()).alias("sot_ev_gtm_id"),
#     col("fsp_project_id").cast(StringType()).alias("sot_fsp_project_id"),
#     col("ev_event_type").cast(StringType()).alias("sot_event_type"),
#     col("p6_outage_start_date").cast(StringType()).alias("sot_outage_start_date"),
#     col("p6_outage_end_date").cast(StringType()).alias("sot_outage_end_date"),
# )
#
# print(f"IBAT rows: {ibat.count()}")
# print(f"EV SOT rows: {ev_sot.count()}")

print("⚠️  Stage 3 depends on Stage 2 output — skipping for now")

# COMMAND ----------

# ── Cell 7: Write to temp table (only after all stages work) ────────────────
# DEV_OUTPUT_TABLE = "main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref__dev_tmp"
#
# enriched_df.write.mode("overwrite").saveAsTable(DEV_OUTPUT_TABLE)
# display(spark.read.table(DEV_OUTPUT_TABLE).limit(20))

print("⚠️  Write step — only run after Stages 1-3 produce output")

# COMMAND ----------

# ── Cell 8: Cleanup (uncomment when done testing) ───────────────────────────
# spark.sql("DROP TABLE IF EXISTS main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref__dev_tmp")
# print("Temp table dropped")

print("⚠️  Cleanup — uncomment when done")
