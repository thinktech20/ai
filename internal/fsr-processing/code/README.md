# FSR Processing — Production Code

Production notebooks for the metadata-first FSR ingestion pipeline.

## Layout

| File | Workflow Task | Purpose |
|---|---|---|
| `fsr_config.py` | (shared) | Runtime parameters, table names, volume paths, secrets |
| `fsr_metadata_extraction.py` | `fsr_metadata_extraction` | Process 1 — PDF discovery, LLM normalization, IBAT/EV enrichment, Silver metadata table |
| `fsr_chunk_ingestion.py` | `fsr_chunk_ingestion` | Process 2 — Read pending docs from Silver, chunk, materialize metadata, embed, write Gold Delta |

## How It Runs

The Databricks workflow `pw_sdg_fsr_ingestion` (defined in `../workflows/pw_sdg_fsr_ingestion.yml`) runs these as sequential tasks:

1. **Task 1**: `fsr_metadata_extraction` — discovers new PDFs, extracts metadata, writes to Silver registry with `chunk_status = pending`
2. **Task 2**: `fsr_chunk_ingestion` — reads pending rows from Silver, chunks PDFs, materializes metadata onto chunk rows, writes to Gold Delta, updates `chunk_status`

Airflow triggers the workflow via `run-now` (see `../workflows/airflow_pw_sdg_fsr_ingestion.yml`).

## Design Reference

- Diagram: `../design/metadata-first-end-to-end-flow.drawio`
- Meeting notes: `../../../internal/comms/monday-arch-review-apr-21/monday-meeting-notes.md`

## Dev vs Prod

All table names, catalogs, and schemas are parameterized via job `base_parameters` (see workflow YAML) and `fsr_config.py` defaults.
- **Dev**: `main.gp_services_sdg_poc.*` (current POC schema)
- **Prod**: `vaid.ai_sot_field_service_report.*` / `vaid.ai_std_con_field_service_report.*` (TBD — pending naming convention confirmation)
