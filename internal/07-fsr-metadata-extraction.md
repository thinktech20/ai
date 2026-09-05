# 07 — FSR Metadata Extraction Pipeline

Source: DS team POC (`reference/ds-team/ds-team-docs/FSR Scraping POC/`).

This pipeline extracts and enriches structured metadata from FSR PDFs.

Current POC output: `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref`

Intended production target: `vgpd.fsr_std_views.fsr_scraped_file_mapping_ref`, the third metadata view expected to be joined at query time by `query_fsr`.

---

## Overview

A 3-stage pipeline transforms raw FSR PDFs into an enriched structured table:

```
Stage 1 — PDF Text Extraction
  ↓  (raw JSON)
Stage 2 — LLM Normalization
  ↓  (normalized Excel/JSON)
Stage 3 — IBAT + Event Vision Enrichment
  ↓
fsr_scraped_file_mapping_ref (15 normalized fields per FSR)
```

Important: the current DS experimentation code writes this table to the POC location in `main.gp_services_sdg_poc.*` by default. A promotion or equivalent production write path to `vgpd.fsr_std_views.*` is not shown in the current repo.

---

## Stage 1 — PDF Text Extraction

**Tool:** Python + `pdfplumber`

**What it does:**
- Recursively walks the FSR PDF Volume folder
- Extracts text from **first page only** (where header metadata lives)
- Parses title (lines before first colon-separated field)
- Parses `key: value` pairs; handles multi-line values by concatenating continuation lines
- Duplicate keys → concatenated with ` | ` separator

**Input:** FSR PDFs in Databricks Volume
```
/Volumes/vgpd/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/
```

**Output JSON structure:**
```json
{
  "FSR_data": [
    {
      "PDF Name / path / identifier": "<full_path>",
      "Title": "<extracted title>",
      "<key1>": "<value1>",
      "<key2>": "<value2 | additional_value>"
    }
  ]
}
```

**Reference implementation:** `local_scraping_pipeline_json_title_2016.py`

---

## Stage 2 — LLM Normalization

**Tool:** Python + `litellm`; batch size 50 PDFs per LLM call

**What it does:**
- Takes the raw extracted JSON from Stage 1
- Sends batches of 50 records to an LLM with a detailed structured extraction prompt
- LLM enforces a strict 15-field schema with ID mapping rules and controlled vocabulary

**LLM Configuration:**
- API Base: `https://dev-gateway.apps.gevernova.net`
- Models available: `azure-gpt-4o`, `azure-gpt-5o`, `vertex-ai-gemini-2.5-flash`, `azure-gpt-4-1`, `gemini-3-flash`
- Model used in POC: `gemini-3-flash`

**Output Schema (15 normalized fields):**

| Field | Notes |
|---|---|
| `ESN` | Equipment Serial Number |
| `Equipment Sys ID` | Equipment system identifier |
| `Equipment Type` | From PDF or filled from IBAT |
| `Equipment Class / Code` | From PDF or filled from IBAT |
| `Event Type` | Controlled vocabulary (see below) |
| `EV Project ID` | EVP-prefixed |
| `EV Equipment Event ID` | EV-prefixed |
| `OFS Event ID` | Oracle Project ID (not EV/EVP-prefixed) |
| `FSP project ID` | FSP-prefixed |
| `xxx project id` | Other prefixes (A-, C-, etc.) |
| `PDF Name / path / identifier` | Source PDF path |
| `FSR Number (#)` | Often null in pre-2016 FSRs |
| `Report Issued Date` | Normalized date from PDF |
| `Outage Start Date` | From PDF (filled from Event Vision in Stage 3) |
| `Outage End Date` | From PDF (filled from Event Vision in Stage 3) |

**ID Prefix Mapping Rules:**
- Oracle Project IDs → `OFS Event ID` (excluding EV/EVP prefixes)
- `EV-` prefix → `EV Equipment Event ID`
- `EVP-` prefix → `EV Project ID`
- `FSP-` prefix → `FSP Project ID`
- `A-`, `C-`, etc. → `xxx project id`

**Event Type Controlled Vocabulary (40+ values):**
Major Inspection (MI), Major Inspection (Field Rewind), Major Inspection (Rotor Out), Major Inspection (Stator Rewind), Major Inspection (Robotic), Hot Gas Path Inspection (HGPI), Combustion Inspection (CI), Borescope Inspection (BI), C Inspection, B Inspection, A Inspection, Minor Inspection, Performance Testing, Call-Out, Large Call-Out, On Site Services, Onsite Services SP, Stand Alone Small Upgrade, Stand Alone Large Upgrade, Upgrade - PMO Billing only, TX Parts, TX Repairs, OP Spares, Initial Spares, Remote Diagnostics, Digital, Non CSA-MMP Billing, Services Warranty, Post COD New Unit Warranty, Unusual, Tooling(GE), Training Cost Accumulation, Training On Site Training, Training Open Enrollment - Costs, Training Open Enrollment - Billing, Training Simulation, null

**Record Splitting Logic (multi-ESN):**
When a record contains multiple distinct ESN / Equipment Sys ID values:
- Split into one row per ESN (positional pairing: 1st ESN with 1st Equipment Sys ID, etc.)
- All other fields duplicated unchanged
- `Equipment Type` and `Equipment Class/Code` set to empty strings in split rows
- Does NOT split other multi-value fields (project IDs, etc.)

**Reference implementation:** `normalize_json_llm_comb.py`

---

## Stage 3 — IBAT + Event Vision Enrichment

**Tool:** Python + PySpark

**What it does:**
- Enriches the FSR-derived metadata rows from Stages 1 and 2 using external source-of-truth systems; it is still FSR enrichment, just not from the PDF alone.
- Loads Stage 2 output (normalized Excel) to Spark DataFrame
- Left-joins with IBAT Equipment Master to fill missing equipment attributes
- Left-joins with Event Vision SOT to fill missing project IDs, event types, and outage dates
- Restores ID prefixes stripped for joins
- Exports as CSV-style text (preserving original column headers)

**IBAT Join (`vgpd.prm_std_views.ibat_equipment_mst`):**
```
fsr.equipment_sys_id == ibat.ibat_equipment_sys_id
OR
fsr.esn == ibat.ibat_equip_serial_number
```
Fields filled from IBAT if blank: `esn`, `equipment_type`, `equipment_sub_class`

**Event Vision SOT Join (`vgpd.fsr_std_views.eventmgmt_event_vision_sot`):**

Multi-key strategy (any key match wins):

| FSR field | SOT field |
|---|---|
| `ev_project_id` (stripped of EVP-) | `sot_ev_project_id` |
| `ev_equipment_event_id` (stripped of EV-) | `sot_ev_equipment_event_id` |
| `ofs_event_id` | `sot_ev_gtm_id` |
| `fsp_project_id` (stripped of FSP-) | `sot_fsp_project_id` |

Fields filled from SOT if blank: `ev_project_id`, `ev_equipment_event_id`, `fsp_project_id`, `ev_event_type`, `outage_start_date`, `outage_end_date`

> Prefixes are **restored** after filling: EVP-, EV-, FSP- prepended to filled values.

**Reference implementation:** `IBAT_EV_Mapping_2016_Vinayaka.py`

---

## Known Gaps

- **FSR # field**: Largely unpopulated in 2016-era FSRs — not present in source PDFs; no alternate source identified yet. Expected to be present in newer FSR population.
- **ESN nulls**: Pre-2016 FSRs often lack ESN on the first page; IBAT enrichment partially recovers these via `equipment_sys_id` join.

---

## File Output Sequence

| Stage | File | Format |
|---|---|---|
| 1 | `n_pdfs_extracted_title_2016_Vinayaka.json` | Raw extracted JSON |
| 2 | `llm_filtered_title_2016_Vinayaka.json` | LLM-normalized JSON |
| 2 | `llm_filtered_title_2016_Vinayaka.xlsx` | Same, as Excel |
| 3 | `fsr_enriched_2016_Vinayaka_combined.csv` | Final enriched dataset |

All files written to: `/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/`
