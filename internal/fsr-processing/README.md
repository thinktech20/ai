# FSR Processing — Runners, Workflows, and Design

This folder holds the active FSR processing implementation area:

- scraping runner assets
- workflow and Airflow YAMLs
- active FSR processing design docs

It currently wraps the existing DS-team FSR metadata extraction pipeline
(`ds-experimentation-code/fsr_scraping/run_scraping_pipeline.py`)
for safe **interactive testing** and eventual **Databricks job scheduling**.

---

## What the scraping pipeline does

A 3-stage pipeline that turns raw FSR PDFs into enriched structured metadata:

```
Stage 1 — PDF text extraction  (pdfplumber, first page only)
     ↓
Stage 2 — LLM normalization    (15-field schema, multi-ESN splitting)
     ↓
Stage 3 — IBAT + Event Vision enrichment  (left-joins)
     ↓
Output → Delta table (fsr_scraped_file_mapping_ref)
```

See [internal/07-fsr-metadata-extraction.md](../../internal/07-fsr-metadata-extraction.md)
for the full technical breakdown.

---

## Safety: Temporary outputs only

All runner configs write to **temporary / sandboxed** locations to avoid
touching existing experiment or production tables:

| What | Safe target |
|---|---|
| Output Delta table | `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref__dev_tmp` |
| Volume output (if any) | `/Volumes/vgpd/fsr_std_views/fsr_std_vol/data/_dev_tmp/` |

The `__dev_tmp` suffix makes it obvious these are throwaway.
Clean up after testing with `DROP TABLE IF EXISTS ...`.

---

## Quick start — Interactive notebook

1. Open `run_scraping_interactive.py` as a Databricks notebook
2. Attach to cluster `ai-pw-ser-ds-dev-apc` (or Serverless)
3. Run cells top-to-bottom
4. The notebook defaults to processing **10 PDFs only** (`MAX_PDFS=10`)
5. Outputs land in `main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref__dev_tmp`

To process more, change `MAX_PDFS` in cell 2, or set it to `None` for all.

---

## Quick start — Databricks Job

See `job_config.json` for a ready-to-use job definition.

Deploy via CLI:
```bash
databricks jobs create --json @job_config.json
```

Or create manually in the Databricks UI → Workflows → Create Job, using
the notebook path and parameters from the config.

---

## Safe workflow YAML test

For workflow-orchestration testing only, use the test YAMLs in `workflows/`:

| File | Purpose |
|---|---|
| `pw_sdg_fsr_ingestion_test.yml` | Safe Databricks multi-task job using the same print-only notebook for both tasks |
| `airflow_pw_sdg_fsr_ingestion_test.yml` | Safe Airflow DAG that triggers the Databricks test job via `run-now` |

These test files do **not** reference existing FSR tables, volumes, or production notebooks.
They mirror only the orchestration shape: `fsr_metadata_extraction -> fsr_chunk_ingestion`.

The Databricks bundle variable `workflow_test_notebook_path` defaults to:

```text
/Workspace/Users/madhurima.saxena@ge.com/workflow_test_fsr/test_workflow_fsr_pipeline
```

If needed at deploy time, override the run identity and notebook path explicitly:

```bash
databricks bundle deploy -t dev \
     --var jb_run_as=madhurima.saxena@ge.com \
     --var workflow_test_notebook_path=/Workspace/Users/madhurima.saxena@ge.com/workflow_test_fsr/test_workflow_fsr_pipeline
```

---

## VS Code / API note

If you want to create or trigger Databricks jobs from VS Code or a local
script, you can set the Databricks API endpoint and token explicitly.

```python
# Set the Databricks API endpoint and credentials
databricks_api_endpoint = "https://your-databricks-instance.com/api/2.0"
databricks_api_token = "your-databricks-api-token"
```

Use placeholders only in notes and examples. Store real tokens in environment
variables, secret managers, or local private config files rather than hardcoding
them in shared code.

---

## Vince's metadata materialization plan

The current scraping pipeline writes a **file-level metadata table**.
Vince's proposal extends this by **materializing selected metadata fields
directly into chunk rows** at ingestion time, reducing query-time joins.

See [design/03-vince-metadata-materialization-plan.md](design/03-vince-metadata-materialization-plan.md)
for the full plan (phases A–E, field precedence rules, migration strategy).

**Key takeaway**: the scraping pipeline itself doesn't change — it still
produces the canonical file-level metadata table. The *chunk ingestion
pipeline* (fsr_pipeline) is what would read from this table and copy
selected fields into chunk rows. That's a Phase C change, not a scraping
change.

---

## Docs to review

| Doc | What it covers |
|---|---|
| [internal/07-fsr-metadata-extraction.md](../../internal/07-fsr-metadata-extraction.md) | 3-stage pipeline technical spec, schemas, known gaps |
| [design/03-vince-metadata-materialization-plan.md](design/03-vince-metadata-materialization-plan.md) | Vince's full materialization proposal (phases, precedence, migration) |
| [design/README.md](design/README.md) | Index of active FSR processing design docs |
| [internal/04-data-catalog.md](../../internal/04-data-catalog.md) | All catalogs, tables, volumes, join keys |
| [internal/06-pipeline-code-analysis.md](../../internal/06-pipeline-code-analysis.md) | Chunk ingestion pipeline analysis |
| [poc/fsr-pipeline-dbr-candidate/docs/PIPELINE_TECHNICAL_GUIDE.md](../../poc/fsr-pipeline-dbr-candidate/docs/PIPELINE_TECHNICAL_GUIDE.md) | Chunk pipeline technical guide |

---

## Files in this directory

| File | Purpose |
|---|---|
| `run_scraping_interactive.py` | Databricks notebook for interactive testing (safe temp output) |
| `job_config.json` | Databricks job definition for scheduling as a workflow |
| `deploy_scraping.py` | Script to upload the scraping notebook to the workspace |
| `README.md` | This file |
