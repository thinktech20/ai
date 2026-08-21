# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_fsr_list_to_csv — convert FSR-list.xlsx → target_pdf_names.csv
#
# Run this once after updating FSR-list.xlsx.
# Produces target_pdf_names.csv (one PDF stem per line) in the same folder.
# The ingest notebook reads from the CSV — no openpyxl/xlrd dependency there.
#
# Input:  FSR-list.xlsx  (column: "Volume path" — one /Volumes/... path per row)
# Output: target_pdf_names.csv (one bare PDF stem per line, no header)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

import os
import pandas as pd

# Derive the folder this notebook lives in (always has /Workspace prefix on DBR)
_nb_path_raw = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()  # noqa: F821
_nb_path = _nb_path_raw if _nb_path_raw.startswith("/Workspace") else f"/Workspace{_nb_path_raw}"
_DATA_DIR = os.path.dirname(_nb_path)

EXCEL_PATH = os.path.join(_DATA_DIR, "FSR-list.xlsx")
CSV_PATH   = os.path.join(_DATA_DIR, "target_pdf_names.csv")

print(f"Reading : {EXCEL_PATH}")
print(f"Writing : {CSV_PATH}")

# COMMAND ----------

df = pd.read_excel(EXCEL_PATH)
vol_paths = df["Volume path"].dropna().astype(str).str.strip().tolist()

stems = []
for vp in vol_paths:
    fname = vp.rstrip("/").split("/")[-1]
    if fname.lower().endswith(".pdf"):
        fname = fname[:-4]
    if fname:
        stems.append(fname)

print(f"Found {len(stems)} PDF names:")
for s in stems:
    print(f"  {s}")

# COMMAND ----------

with open(CSV_PATH, "w") as f:
    f.write("\n".join(stems) + "\n")

print(f"\nWritten to {CSV_PATH}")
