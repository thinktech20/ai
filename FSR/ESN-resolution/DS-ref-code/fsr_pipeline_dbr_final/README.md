# FSR Pipeline v6

This folder contains the smallest set of files needed to deploy and run the FSR Databricks pipeline and its evaluation notebook.

It also includes a small docs folder with reference material that is not required to run the pipeline.

This cleaned package is experimental validation code. It is not the production `query_fsr` REST service described in `docs/Query FSR Tool Spec.md`.

If you are new to this codebase, the two files that matter most are:

- run_pipeline.py: chunks PDFs, writes Delta rows, enriches ESNs, and triggers a Vector Search sync.
- run_evaluation.py: evaluates retrieval quality across ANN and HYBRID search, with reranking on and off, against the heat map and the processed citations workbook.

Everything else in this folder exists to support those two notebooks.

## What this project does

The pipeline reads Field Service Report PDFs from configured Databricks volumes, splits them into chunks, enriches those chunks with generator serial metadata, writes the rows to a Delta table, and syncs a Databricks Vector Search index.

The evaluation notebook then runs a fixed set of issue prompts against that index and measures whether the right chunks are retrieved for known ground-truth citations.

The docs folder captures the target production tool contract and the retrieval metrics that informed it, but the runtime code in this package is still the experiment used to assess validity.

## What is in this folder

- run_pipeline.py: main Databricks notebook entrypoint.
- run_evaluation.py: Databricks notebook for retrieval evaluation.
- src: Python modules imported by the notebooks.
- deploy.py: uploads the notebooks, source files, cert, and evaluation workbooks into a Databricks workspace.
- docs: reference documentation that is not part of the runtime path.
- .env.example: local template for deployment-time environment variables.
- requirements.txt: local Python packages needed for deployment and code editing.
- GE_Enterprise_Root_CA_2_1.crt: GE certificate used when internal HTTPS endpoints need the corporate CA.
- Heat Map - Unified Structure v0.1.xlsx: source of evaluation queries.
- FSR_citations_processed_20260305_135321.xlsx: source of evaluation ground truth.

## Reference docs

- docs/Query FSR Tool Spec.md: target production REST-tool specification, plus a gap list showing what the current notebook experiment does not implement yet.
- docs/fsr_retrieval_metrics_final.csv: retrieval comparison results used to judge which retrieval strategy is most promising for production.

## Before you start

You need access to the target Databricks workspace and permission to run notebooks there.

The notebooks also assume the following Databricks objects already exist, unless you intentionally override them in environment variables:

- the Delta table named by EMBEDDINGS_TABLE
- the Vector Search index named by VS_INDEX_NAME
- the Vector Search endpoint named by VS_ENDPOINT_NAME
- the Databricks secret scope named by DBR_SECRET_SCOPE

Those defaults are defined in src/config.py.

## First-time local setup

Open a PowerShell terminal in this folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Then edit .env.

At minimum, set:

- DATABRICKS_HOST
- DATABRICKS_TOKEN

You only need to set LITELLM_BASE_URL and LITELLM_API_KEY in .env if you plan to run code outside Databricks. In Databricks, src/config.py will try the configured secret scope first.

## Deploying to Databricks

From this folder, run:

```powershell
python deploy.py
```

If you do not want the PAT in .env, you can instead provide a token file:

```powershell
python deploy.py --token-file dbr_token.txt
```

Deploy uploads:

- run_pipeline as a Databricks notebook
- run_evaluation as a Databricks notebook
- every runtime module in src
- the GE certificate file
- both Excel workbooks used by evaluation

## Running the pipeline

After deployment:

1. Open the deployed run_pipeline notebook in Databricks.
2. Attach it to the intended compute.
3. Review the top configuration cell only if you need overrides such as FORCE_RESET or a different secret scope.
4. Run all cells.

What it does:

1. Finds the configured PDF volume.
2. Chunks PDFs with the recursive chunker.
3. Enriches chunks with ESN metadata.
4. Appends rows to the configured Delta table.
5. Loads the written rows back for inspection.
6. Triggers a Vector Search sync.
7. Optionally runs retrieval evaluation at the end.

## Running evaluation by itself

Open the deployed run_evaluation notebook and run all cells.

On the first run, the evaluation code creates results/citations_parsed.csv automatically from FSR_citations_processed_20260305_135321.xlsx. You do not need to pre-generate that CSV anymore.

Evaluation uses:

- the heat map workbook for issue prompts
- the citations workbook for ground truth
- the configured Delta table and Vector Search index for retrieval

## Files in src

Each remaining module in src is on the live path for the two notebooks:

- config.py: environment detection, secrets, table names, index names, and chunking settings.
- pipeline.py: orchestration for the main pipeline notebook.
- pdf_processor.py: single-PDF chunking flow.
- recursive_chunking_v3.py: the chunking implementation used by pdf_processor.py.
- delta_store.py: Delta reads/writes and ref-view enrichment helpers. Databricks Vector Search creates embeddings during sync.
- esn_identifier.py: ESN extraction and labeling.
- document_loader.py: reloads chunk rows from Delta for inspection during pipeline runs.
- evaluate_retrieval.py: ground-truth loading, Vector Search queries, and metric calculation.
- utils.py: shared logging and helper utilities.

Stale runtime modules were removed during cleanup.

## Common configuration points

Most people only need these values from src/config.py:

- DBR_SECRET_SCOPE
- EMBEDDINGS_TABLE
- VS_ENDPOINT_NAME
- VS_INDEX_NAME
- FSR_REF_VIEW

Only change them if you are deliberately targeting a different environment.

## Troubleshooting

If deploy.py cannot authenticate:

- verify DATABRICKS_TOKEN or the token file
- verify DATABRICKS_HOST points at the correct workspace

If the notebooks fail to find PDFs:

- check the PDF volume paths in src/config.py
- confirm the attached compute has permission to read those volumes

If evaluation returns poor or zero recall:

- confirm the Delta table actually contains rows
- confirm generator_serial is populated in those rows
- confirm the Vector Search index has been synced after the latest pipeline run

If HTTPS calls fail with certificate errors:

- keep GE_Enterprise_Root_CA_2_1.crt beside the notebooks and src directory
- confirm the deployed workspace copy includes that file

## Expected outputs

This cleaned package does not ship with logs or results.

When you run evaluation, it creates a results directory and writes output files there, including raw per-query results and summary CSVs.
