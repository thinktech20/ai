# FSR Pipeline — Technical Design

> **Date:** 2026-04-22  
> **Status:** Active — backfill scaling in progress  
> **Branch:** `feature/fsr-pipelines`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Key Insights / Aha Moments](#1a-key-insights--aha-moments)
3. [Workflow Structure](#2-workflow-structure)
   - [2.1 Job Topology](#21-job-topology)
   - [2.2 Job Parameter Matrix](#22-job-parameter-matrix)
3. [Data Model](#3-data-model)
   - [3.1 Metadata Registry (Silver)](#31-metadata-registry-silver)
   - [3.2 Chunk Table (Gold)](#32-chunk-table-gold)
   - [3.3 Operational Tables](#33-operational-tables)
4. [Process 1 — Metadata Extraction](#4-process-1--metadata-extraction)
   - [Flow](#flow)
   - [Batch model](#batch-model)
   - [Concurrency](#concurrency)
   - [Failure handling](#failure-handling)
   - [Resiliency](#resiliency)
5. [Process 2 — Chunking, Embedding & VS Sync](#5-process-2--chunking-embedding--vs-sync)
   - [Batch model](#batch-model-1)
   - [Batch Loop Architecture](#batch-loop-architecture)
   - [Per-batch flow (process_one_batch)](#per-batch-flow-process_one_batch)
   - [Drain loop behavior](#drain-loop-behavior)
   - [Claim-based locking](#claim-based-locking)
   - [Concurrency](#concurrency-1)
   - [Failure handling](#failure-handling-1)
   - [Resiliency](#resiliency-1)
   - [Vector Search Index Sync](#vector-search-index-sync)
6. [Embedding Configuration](#6-embedding-configuration)
7. [Validation](#7-validation)
8. [FORCE_RESET Behavior](#8-force_reset-behavior)
9. [Configuration Reference](#9-configuration-reference)
10. [Backfill Strategy](#10-backfill-strategy)
11. [Pipeline Improvements (Incremental + Backfill)](#11-pipeline-improvements-incremental--backfill)
    - [11.1 P1 — wire up real concurrency](#111-p1--wire-up-real-concurrency)
    - [11.2 P1 — tiered LLM error handling (transient retry + per-doc fallback)](#112-p1--tiered-llm-error-handling-transient-retry--per-doc-fallback)
    - [11.3 P1 — null-pdf-name failure cluster](#113-p1--null-pdf-name-failure-cluster)
    - [11.4 P2 — claim atomicity](#114-p2--claim-atomicity)
    - [11.5 Separate VS sync job](#115-separate-vs-sync-job)
    - [11.6 Operational — backfill kickoff hygiene](#116-operational--backfill-kickoff-hygiene)
    - [11.7 P1 — eliminate "completed but no metadata" via better discovery dedup](#117-p1--eliminate-completed-but-no-metadata-via-better-discovery-dedup)
    - [11.8 FORCE_RESET — separate out the destructive path](#118-force_reset--separate-out-the-destructive-path)
    - [11.9 P1 — BACKLOG trigger should exclude retry-exhausted rows](#119-p1--backlog-trigger-should-exclude-retry-exhausted-rows)
    - [11.10 P1 — re-upload detection via `file_last_modified`](#1110-p1--re-upload-detection-via-file_last_modified)
    - [11.11 Move Tier-2 LLM ESN detection from P2 into P1](#1111-move-tier-2-llm-esn-detection-from-p2-into-p1)
12. [Document Summary](#12-document-summary)

---

## 1. Overview

The FSR (Field Service Report) pipeline ingests ~17.8K PDF documents from Unity Catalog Volumes, extracts metadata and full text, generates vector embeddings, and syncs to a Vector Search index for RAG-based retrieval.

The pipeline runs on Databricks serverless compute as a multi-task workflow.

---

## 1A. Key Insights / Aha Moments

> Curated list of non-obvious lessons surfaced during design, dev backfill (Apr 22–26), and PROD backfill (Apr 30 – May 2). Each item is intentionally short — deck-extractable. Detailed mechanics live in their home sections; links provided.

- **Incremental and backfill share the same code path.** There is no separate "incremental" notebook. P1's DISCOVERY mode lists the volume via Spark SQL `LIST`, `left_anti`-joins against existing `document_id`s, and only new docs flow through. For an 8–10 docs/day steady-state cadence, the daily run is essentially a no-op against the existing 17.8K-doc corpus. Backfill design improvements (Spark SQL `LIST`, stub-row durability, drain-loop P2) all carry over for free. See [§4 Flow](#flow).
- **Re-running backfill jobs is naturally idempotent.** "Backfill" and "incremental" aren't different code paths — they're the same job with different work-set sizes. P1 dedups via `left_anti` on `document_id`; P2 dedups via `chunk_status` filter and `MERGE` on `chunk_id`. Re-triggering touches only pending/failed rows and brand-new files. The risks are operational (concurrent jobs racing, `FORCE_RESET` accidents — see next bullet), not correctness.
- **`FORCE_RESET` is a brittle flag for a destructive operation.** A single mis-checked job parameter truncates the metadata table and wipes ~30+ hours of backfill work. Today it's mitigated only by runbook discipline ("NEVER true on prod"). Should be redesigned as a separate notebook/job, ideally with a soft-reset variant that flips rows to `pending` instead of dropping them. See [§11.8](#118-force_reset--separate-out-the-destructive-path).
- **P1 discovery is mode-exclusive, not additive.** TARGET / BACKLOG / DISCOVERY / FORCE_RESET are an `if/elif` chain — exactly one runs per job execution. If any `pending`/`failed` rows exist, BACKLOG wins and the volume scan is **skipped entirely** that run. New PDFs landing in the volume are not picked up until the backlog drains. Intentional (drain failures before scanning), but operationally surprising. See [§4 Flow](#flow).
- **Latent bug: terminal failures can permanently block incremental ingestion.** BACKLOG mode triggers on any `metadata_status IN ('pending', 'failed')` row — without filtering by retry count. Retry-exhausted docs (`metadata_retry_count >= P1_MAX_RETRIES`) sit in `failed` forever, keep BACKLOG mode active forever, and DISCOVERY never runs again → new files never get picked up. PROD already has ~16 docs heading toward this state. See [§11.9](#119-p1--backlog-trigger-should-exclude-retry-exhausted-rows). _Update 2026-05-06 (UI-18):_ the underlying lifetime retry cap for P1 now exists — `metadata_retry_count` is incremented on every P1 failure MERGE and the failed-rows SELECT gates on `COALESCE(metadata_retry_count, 0) < P1_MAX_RETRIES`. Mirror of P2's existing `chunk_retry_count` behavior. The BACKLOG-trigger gap in §11.9 still stands as a follow-up; this just makes the retry-exhausted state actually reachable.
- **P1 had no run-log entries until UI-18.** P2 has always written one row per `process_one_batch` to `fsr_run_log`; P1 wrote nothing. So SRE telemetry ("how long did the metadata run take, how many docs succeeded/failed in this batch") only existed for P2. As of UI-18, P1 also writes one row per commit batch with `job_name='PW_SDG_FSR_Metadata'`, mirroring P2's pattern. See [§4 Resiliency](#resiliency).
- **Re-upload detection gap.** The original Confluence design called for tracking `file_last_modified` on each row and resetting `metadata_status='pending'` when a PDF is replaced in-volume. Current implementation does not store `file_last_modified` (or `file_size_bytes`), and DISCOVERY's `left_anti` skips any doc whose `document_id` already exists — regardless of content change. If a PDF is overwritten with corrected content under the same UUID filename, the pipeline silently keeps the old metadata and chunks forever. No error, no DQ flag, just stale data in the index. See [§11.10](#1110-p1--re-upload-detection-via-file_last_modified).

_Promote one bullet at a time as we re-read the doc._

---

## 2. Workflow Structure

```
DDL (separate infra job) + P1 (Metadata) → P2 (Chunks + Embedding) → Validate
```

| Task | Notebook | Layer | Purpose |
|------|----------|-------|---------|
| DDL | `silver/src/ddl/nb_sdg_fsr_ddl` | infra | Create/ensure all Delta tables exist |
| P1 — Metadata | `silver/src/etl/nb_sdg_fsr_metadata` | silver | Extract metadata from PDFs, normalize via LLM, enrich via IBAT/EV |
| P2 — Chunks | `gold/src/etl/nb_sdg_fsr_chunks` | gold | Chunk text, generate embeddings, MERGE to Delta, sync VS index |
| Validate | `silver/src/validation/nb_sdg_fsr_validate` | silver | 41+ automated checks on data quality and pipeline correctness |

Tasks run sequentially: each depends on the previous. All share configuration via `%run common/fsr_config`.

### 2.1 Job Topology

Five Databricks jobs cover all operational modes:

| Job | Tasks | Schedule | Purpose |
|-----|-------|----------|---------|
| **`FSR_DDL_Provision`** | `ddl` | Manual | Infra provisioning — run for first-time setup, schema changes, or controlled reset |
| **`PW_SDG_FSR_Ingestion`** | `P1 → P2` | Scheduled (daily 06:00 ET) | Incremental — processes new PDFs as they land in the volume. Validation no longer inline (UI-16). |
| **`PW_SDG_FSR_DQ_Validation`** | `validate` | Scheduled (daily 09:00 ET, paused) | Stand-alone DQ validation, offset 3h after ingestion. Paused until SRE/monitoring ownership lands (UI-16). |
| **`FSR_Metadata_Backfill`** | `P1` | Manual | Bulk metadata extraction for large initial loads |
| **`FSR_Chunking_Backfill`** | `P2` | Manual | Bulk chunking/embedding — run in parallel with metadata backfill |
| **`FSR_Validation`** | `validate` | Manual | Ad-hoc health checks — run after backfill batches, fixes, or on demand |

**Why DQ validation was split out (UI-16):** keeping `validate` as the third task on `PW_SDG_FSR_Ingestion` meant any DQ failure (including the standing 72 terminal-failure docs that check 5.7 surfaces every run) would turn the ingestion job red and confuse on-call about whether ingestion itself broke. Splitting them lets ingestion stay green when the data has known-bad inputs, and lets the DQ job carry its own SLO + ownership. The standalone job runs on its own schedule with its own alerting policy.

**DDL mode** (`FSR_DDL_Provision`): Run before first pipeline use in a new environment, before schema changes, or when doing controlled resets.

**Incremental mode** (`FSR_Ingestion`): Sequential is fine — typically a handful of new PDFs, takes minutes. Single job handles operational processing.

**Backfill mode** (`FSR_Metadata_Backfill` + `FSR_Chunking_Backfill`): Run in parallel. P1 writes rows with `metadata_status=completed, chunk_status=pending`. P2 claims rows as they appear. No conflict — P1 MERGEs metadata columns, P2 UPDATEs chunk columns. This is how the current 17.8K backfill operates.

```
Infra bootstrap:      DDL                           (Job 1, manual / as needed)

Incremental:          P1 → P2 → Validate            (single job, sequential)

Backfill (parallel):  P1 (hours)                    (Job 2)
                      P2 ────────────── (repeat)    (Job 3, runs alongside)
                      Validate                      (Job 4, ad-hoc)
```

### 2.2 Job Parameter Matrix

All parameters are defined in the workflow YAML (`pw_sdg_fsr_workflows.yml`) and resolved via `databricks.yaml` bundle variables for env-specific values (`-t dev` vs `-t prod`).

| Parameter | Default | DDL Provision | Ingestion | Metadata Backfill | Chunking Backfill | Validation |
|-----------|---------|:-------------:|:---------:|:-----------------:|:-----------------:|:----------:|
| **Tables / Infrastructure** | | | | | |
| `FORCE_RESET` | `false` | ✅ | ✅ | ✅ | — | — |
| `FSR_METADATA_TABLE` | `${var.fsr_metadata_table}` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `FSR_CHUNK_TABLE` | `${var.fsr_chunk_table}` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `FSR_RUN_LOG_TABLE` | `${var.fsr_run_log_table}` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `FSR_DQ_LOG_TABLE` | `${var.fsr_dq_log_table}` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `FSR_VS_ENDPOINT` | `${var.fsr_vs_endpoint}` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `FSR_VS_INDEX` | `${var.fsr_vs_index}` | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Run control** | | | | | |
| `FSR_MAX_PDFS` | _(empty)_ | — | ✅ | ✅ | ✅ | — |
| `FSR_TARGET_PDF_NAMES` | _(empty)_ | — | ✅ | ✅ | — | — |
| `LITELLM_API_KEY` | _(empty)_ | — | ✅ | ✅ | ✅ | — |
| **P1 tuning** | | | | | |
| `FSR_BATCH_SIZE` | `4` | — | ✅ | ✅ | — | — |
| `FSR_PDF_EXTRACT_WORKERS` | `16` | — | ✅ | ✅ | — | — |
| `FSR_LLM_CONCURRENCY` | `3` | — | ✅ | ✅ | — | — |
| `FSR_LLM_CONCURRENCY_MAX` | `6` | — | ✅ | ✅ | — | — |
| `FSR_BATCH_THREADS` | `4` | — | ✅ | ✅ | — | — |
| `FSR_BATCH_THREADS_START` | `2` | — | ✅ | ✅ | — | — |
| `FSR_BATCH_THREAD_RAMP_SECONDS` | `10` | — | ✅ | ✅ | — | — |
| `FSR_MAX_RETRIES` | `3` | — | ✅ | ✅ | — | — |
| `FSR_P1_COMMIT_BATCH` | `500` | — | ✅ | ✅ | — | — |
| **P2 tuning** | | | | | |
| `FSR_P2_BATCH_SIZE` | `50` | — | ✅ | — | ✅ | — |
| `FSR_P2_MAX_ITERATIONS` | `0` | — | ✅ | — | ✅ | — |
| `FSR_P2_PDF_WORKERS` | `4` | — | ✅ | — | ✅ | — |
| `FSR_P2_MAX_RETRIES` | `3` | — | ✅ | — | ✅ | — |

---

## 3. Data Model

### 3.1 Metadata Registry (Silver)

Table: `fsr_metadata_registry` (parameterized via `FSR_METADATA_TABLE`)

| Column | Type | Role |
|--------|------|------|
| `document_id` | STRING NOT NULL | PK — UUID stem from PDF filename |
| `pdf_name` | STRING | Human-readable name derived from `fsr_pdf_ref.PDF_name` |
| `volume_path` | STRING | Source path in Unity Catalog Volume |
| `metadata_status` | STRING | `pending` → `completed` / `failed` |
| `chunk_status` | STRING | `pending` → `in_progress` → `completed` / `failed` |
| `page_count` | INT | Total pages in PDF |
| _+ 20 metadata fields_ | | title, customer, esn, equipment details, dates, etc. |

> **Note on `prepared_by` / `approved_by`:** declared in the registry DDL and materialised into chunk metadata JSON, but **not populated** by P1 today (no LLM extraction or MERGE assignment). They render as `null` in chunks. Future LLM extraction work can fill these.

### 3.2 Chunk Table (Gold)

Table: `fsr_chunks` (parameterized via `FSR_CHUNK_TABLE`)

| Column | Type | Role |
|--------|------|------|
| `chunk_id` | STRING NOT NULL | PK — `md5(document_id + "_" + chunk_index)` |
| `document_id` | STRING NOT NULL | FK to metadata registry |
| `pdf_name` | STRING | Human-readable (nullable) |
| `page_number` | INT | Start page of chunk |
| `chunk_text` | STRING | Chunk content |
| `esn` | STRING | Denormalized for filtering |
| `report_date` | DATE | Denormalized for filtering |
| `chunk_embedding` | ARRAY\<DOUBLE\> | 3072-dim embedding vector |
| `metadata` | STRING | JSON blob with all materialized metadata |
| `created_at` | TIMESTAMP | Write time |

### 3.3 Operational Tables

| Table | Purpose |
|-------|---------|
| `fsr_run_log` | One row per P2 batch iteration **and** (UI-18) one row per P1 commit batch — `job_name`, `run_id`, timing, doc/chunk counts, error summary. Same schema; `job_name` distinguishes `PW_SDG_FSR_Metadata` from `PW_SDG_FSR_Chunks`. |
| `fsr_data_quality_log` | Per-doc DQ findings from validation — severity, check name, details, and (UI-17) a `failure_category` enum populated on terminal-failure rows. Append-only; never deleted. |

---

## 4. Process 1 — Metadata Extraction
### Key Field Extraction Logic
### Logic for Key Metadata Fields

**pdf_name**
- Try to resolve a human-readable name by joining the document's `document_id` with the `fsr_pdf_ref` table (matching on S3 filename, minus the .pdf extension).
- If a match is found, use the name from `fsr_pdf_ref`.
- If not, fall back to extracting the filename from the `volume_path` (using the stem of the file path).
- If still unavailable, use the confirmed fallback format from Slack: `title + '_' + customer + '_' + equipment_type + '_' + esn + '_' + outage_start_date`.

**ESN**
- Extracted from the document using LLM normalization of the first page’s fields.
- If the LLM does not provide an ESN, enrich by joining with the IBAT reference table, using either the equipment system ID or ESN.
- The `esn_source` field is set to "llm" if the LLM provided the ESN, or "ibat" if it was filled in from the IBAT table.
- Latest validation update: files sampled for missing metadata ESN still contain ESN on page 1, so near-term focus is extraction/parsing quality (not source document absence).

**document summary**
- Attempt to enrich the document with a summary from the PSOT table (`psot_executive_summary`).
- If the PSOT summary is not available, set `document_summary` to null.

**Notebook:** `nb_sdg_fsr_metadata`

### Flow

#### Step 1 — Discovery

The notebook picks one of four discovery modes (mutually exclusive — exactly one runs per execution):

- **TARGET mode** — `FSR_TARGET_PDF_NAMES` is set: stat each named file directly via `dbutils.fs.ls` (single-file lookup, instant), no volume scan.
- **BACKLOG mode** — any rows exist with `metadata_status IN ('pending', 'failed')`: skip the volume scan entirely and process the existing queue first.
- **DISCOVERY mode** — no targets, no backlog: scan volumes via **Spark SQL `LIST`** (parallelized; handles 17K+ files in seconds) and `left_anti` join on `document_id` to exclude already-known docs.
- **FORCE_RESET mode** — `FORCE_RESET=true`: truncate the table and full rescan via Spark SQL `LIST`.

For newly discovered files, insert stub rows with `metadata_status='pending'`, `chunk_status='pending'`, capturing `volume_path`, `file_size_bytes`, `file_last_modified`, and `ingested_at`. Stubs are written via `MERGE INTO` keyed on `document_id`.

> **Note:** `dbutils.fs.ls()` is NOT used for volume listing — it's FUSE-based and hangs on 17K+ files (see BUG-007). Spark SQL `LIST` is used instead. `dbutils.fs.ls` is only used in TARGET mode for single-file stat.

#### Step 2 — PDF Extraction

- Query the metadata table: `WHERE metadata_status IN ('pending', 'failed') AND COALESCE(metadata_retry_count, 0) < FSR_P1_MAX_RETRIES` (retry-cap-aware).
- Process docs in **commit batches** of `FSR_P1_COMMIT_BATCH` (default 500) — each batch is fully processed and MERGEd before the next slice begins.
- Extract page-1 text and key-value fields via `pdfplumber`.
- Capture `page_count` from the PDF.

#### Step 3 — LLM Normalisation

- Send extracted page-1 fields to LLM (`gemini-3-flash` by default) for normalisation.
- LLM calls are **batched** — `FSR_BATCH_SIZE` docs (default 4) packed into a single request.
- Produces: `title`, `customer`, `esn`, `equipment_sys_id`, `event_type`, `ev_project_id`, `ev_equipment_event_id`, `ofs_event_id`, `fsp_project_id`, `xxx_project_id`, `fsr_number`, `report_issued_date`, `outage_start_date`, `outage_end_date`. (Schema also declares `prepared_by` and `approved_by` but they are not populated today — see [§3.1](#31-metadata-registry-silver) note.)
- Date columns are normalised to `YYYY-MM-DD` (ISO 8601) regardless of source format.

#### Step 4 — Enrichment

- **IBAT (`ibat_equipment_mst`):** match on `equipment_sys_id` or `esn` → fill `equipment_type`, `equipment_class_code`; backfill `esn` / `equipment_sys_id` if blank; set `esn_source = 'ibat'` if ESN was resolved here. Otherwise `esn_source = 'llm'`.
- **Event Vision SOT (`eventmgmt_event_vision_sot`):** match on `ev_project_id` / `ev_equipment_event_id` / `ofs_event_id` / `fsp_project_id` → backfill any blank event/project ID fields and `event_type`.
- **PSOT (`fsr_field_vision_field_services_report_psot`):** match on `ev_equipment_event_id` → resolve `outage_type`, `technology_type`, and `document_summary` (sourced from PSOT `executive_summary`).
- **`fsr_pdf_ref`:** match `document_id` → `s3_filename` → resolve human-readable `pdf_name`. Falls back to volume-path stem if no match.

#### Step 5 — Write

Update the row via `MERGE INTO` on `document_id` with all extracted and enriched fields:

- **On success:** `metadata_status = 'completed'`, `scraped_at = current_timestamp()`, `metadata_retry_count` reset.
- **On failure:** `metadata_status = 'failed'`, `metadata_error = <truncated message>`, `scraped_at = current_timestamp()`, `metadata_retry_count` incremented. Re-attempted on next run if still under `FSR_P1_MAX_RETRIES` (default 3).

`FORCE_RESET` override: setting `FORCE_RESET = true` truncates the metadata table and re-scans all files from scratch. **Use with extreme caution on production** — wipes all progress (see [§11.8](#118-force_reset--separate-out-the-destructive-path)).

### Batch model

P1 has **two distinct "batch" notions** — they're not the same thing:

| Level | Knob | Default | What it controls |
|---|---|---|---|
| **Run-level work set** | _(none — driven by mode)_ | n/a | Which docs this run will process. Built once at start: TARGET → only the listed PDFs; BACKLOG → existing `pending`/`failed` rows; DISCOVERY → Spark SQL `LIST` minus already-known IDs. No upper cap by default — could be all 17.8K. |
| **Commit batch** | `FSR_P1_COMMIT_BATCH` | 500 | The work set is sliced into chunks of this size. Each slice is fully extracted + LLM-normalized + enriched, then MERGEd to Delta as one transaction. Keeps the transaction size bounded and gives a recovery checkpoint every 500 docs. |
| **LLM batch** | `FSR_BATCH_SIZE` (a.k.a. `P1_BATCH_SIZE`) | 4 | Inside a commit batch, the page-1 `llm_fields` dicts are sliced and **N docs are packed into a single LLM request**. The "4" is docs per request, not text slices per doc. |

Code references: commit slicing at [`nb_sdg_fsr_metadata.py#L555-L557`](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L555); LLM batch loop at [`#L625-L628`](../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L625).

### Concurrency

**P1 today is single-threaded.** `nb_sdg_fsr_metadata` does not import `concurrent.futures` and does not use any thread pool:

- **PDF extraction** — sequential `for row in batch_rows: with pdfplumber.open(...)`. One PDF at a time.
- **LLM normalization** — sequential `for i in range(0, len(all_llm_fields), P1_BATCH_SIZE)`. One LLM request at a time, optionally `time.sleep(P1_LLM_DELAY)` between calls. The only "parallelism" is that the LLM processes 4 docs server-side per request — there is zero client-side concurrency.
- **Vestigial knobs** — `P1_EXTRACT_WORKERS` (16), `P1_LLM_CONCURRENCY` (3), `P1_LLM_CONCURRENCY_MAX` (6), `P1_BATCH_THREADS` (4), `P1_BATCH_THREADS_START` (2) are defined in [`common/fsr_config.py`](../../pw_sdg_ai_ser_repo/common/fsr_config.py) but **not referenced** by the metadata notebook. They were intended for a thread-pool implementation that never landed. Changing them today has no effect.

Observed PROD throughput: ~500 docs / ~85–90 min commit batch (~5–6 docs/min), bounded by serial LLM round-trips. See [Section 11.1](#111-p1--wire-up-real-concurrency) for the planned parallelization.

### Failure handling

P1 distinguishes three failure surfaces with different blast radii:

| Failure surface | Blast radius | Outcome | Retry path |
|---|---|---|---|
| **PDF extraction error** (e.g., corrupt PDF, pdfplumber exception) | Single doc | Doc dropped from this run's `extractions` map; recorded in `failures` dict with truncated error | Re-attempted on next run via BACKLOG mode (up to `P1_MAX_RETRIES`) |
| **LLM call exception** (network, gateway 5xx, parse error) | **Whole LLM batch** (default 4 docs) | All docs in that batch tagged with the same error string and added to `llm_failures` | Re-attempted on next run via BACKLOG mode. No in-loop per-doc fallback today — see [Section 11.2](#112-p1--tiered-llm-error-handling-transient-retry--per-doc-fallback) for proposed tiered handler. |
| **LLM response missing a row** for a particular doc's `volume_path` | Single doc | That doc gets `"LLM returned no matching row for this document"`; sibling docs in the batch may succeed | Re-attempted on next run via BACKLOG mode |

All three roll up into the same write path: the doc is MERGEd with `metadata_status=failed`, `metadata_error=<reason>`, `metadata_retry_count` incremented. When `metadata_retry_count >= P1_MAX_RETRIES` the doc is no longer claimed.

**Observed in PROD (May 1–2, 2026):**
- ~16 docs hit the "no matching row" path — all with `pdf_name=null`/`page_count=null`, almost certainly image-only or corrupt PDFs that yielded empty page-1 text.
- 4 docs in one 08:29 UTC batch failed with bare error `'content'` — a single bad LLM response (`KeyError: 'content'`) tainted all 4 docs in that micro-batch. See [Section 11.2](#112-p1--defensive-llm-response-parsing) for the proposed defensive-parsing fix.

### Resiliency

- **Stub-row durability** — every discovered doc gets a row written to the metadata registry with `metadata_status=pending` before any extraction work. If the cluster crashes mid-run, the next run picks up exactly where it left off via BACKLOG mode. No re-discovery needed.
- **Idempotent MERGE** — successful + failed records are written via `MERGE INTO` keyed on `document_id`. Re-running on the same docs updates rather than duplicates.
- **Commit-batch checkpointing** — Delta MERGE happens every 500 docs, not at end-of-run. A driver crash at doc 17,500 of 17,800 loses at most the in-flight 500-doc batch.
- **Bounded retry** — `P1_MAX_RETRIES=3` ensures terminally-bad docs (corrupt PDFs, persistently malformed LLM responses) eventually stop being retried and don't block the queue.
- **Mode-driven discovery skip** — BACKLOG mode bypasses the volume scan entirely if any pending/failed rows exist, so restart cost is dominated by useful work, not file-listing.
- **No in-flight global state** — the `extractions`/`failures`/`llm_failures` dicts are scoped per commit batch. Crashes between commit batches lose nothing; crashes within a batch lose only that batch's progress.
- **Per-commit-batch audit row (UI-18)** — after each commit batch, P1 INSERTs one row into `fsr_run_log` with `job_name='PW_SDG_FSR_Metadata'`, the per-run `P1_RUN_ID`, batch start/end timestamps, wall-clock duration, attempted / succeeded / failed counts, and a truncated error summary of the first ~10 failures. Mirrors what P2 has always done from `process_one_batch`. The INSERT is wrapped in try/except so an audit-write failure does not break the batch — SRE telemetry is best-effort, not on the success path.

---

## 5. Process 2 — Chunking, Embedding & VS Sync

**Notebook:** `nb_sdg_fsr_chunks`

### Batch model

P2 has **three nested batch notions**:

| Level | Knob | Default | What it controls |
|---|---|---|---|
| **Run-level work set** | `FSR_P2_MAX_ITERATIONS` | 0 = drain | How many claim-iterations one job run performs. 0 means "keep claiming until the queue is empty." |
| **Claim batch** | `FSR_P2_BATCH_SIZE` | 50 | Docs claimed atomically per iteration via `SELECT ... LIMIT N` then guarded UPDATE. The whole iteration (extract → chunk → embed → MERGE → status) operates on these N docs. |
| **Embedding sub-batch** | `EMBED_BATCH_SIZE` | 32 | All chunks across all 50 claimed docs are flattened, then sliced into 32-chunk sub-requests for the embeddings API. |

So one P2 iteration = one claim batch (50 docs) → typically ~3,000–4,000 chunks → ~100–125 embedding sub-batch requests, run concurrently. With the default drain-loop, a 17.8K-doc backfill is ~356 iterations.

### Batch Loop Architecture

P2 runs a **drain loop** that keeps claiming and processing batches until the queue is empty or `P2_MAX_ITERATIONS` is reached.

```
┌─────────────────────────────────────────────────┐
│  Stale claim recovery (>30 min in_progress → pending)  │
└─────────────────────┬───────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │  process_one_batch()  │◄──── loop until queue empty
          │                       │      or P2_MAX_ITERATIONS hit
          │  1. Claim batch       │
          │  2. Extract text      │
          │  3. Chunk             │
          │  4. Embed (concurrent)│
          │  5. MERGE to Delta    │
          │  6. Update status     │
          │  7. Write audit log   │
          └───────────┬───────────┘
                      │ (no more pending docs)
          ┌───────────▼───────────┐
          │  VS sync (once)       │
          │  Final verify + log   │
          └───────────────────────┘
```

### Per-batch flow (process_one_batch)

#### Step 0 — Stale claim recovery (run-level, once)

At the start of each run (before the first iteration), reset any rows stuck in `chunk_status='in_progress'` for more than 30 minutes back to `'pending'`. Recovers from prior crashed runs / cluster auto-shutdown without manual intervention.

#### Step 1 — Claim

Select up to `FSR_P2_BATCH_SIZE` (default 50) rows where `metadata_status='completed'` AND `chunk_status IN ('pending', 'failed')` AND `COALESCE(chunk_retry_count, 0) < FSR_P2_MAX_RETRIES`. Capture the `document_id` list, then UPDATE those rows to `chunk_status='in_progress'`. The WHERE-guard on the UPDATE ensures a doc can't be double-claimed even if two jobs SELECT the same IDs (see [Claim-based locking](#claim-based-locking)).

#### Step 2 — PDF text extraction

For each claimed doc, load the PDF from `volume_path` and open via PyMuPDF (`fitz`); extract text from every page. Track page boundaries for chunk-to-page mapping.

#### Step 3 — Hierarchical semantic chunking

Split the document via `hierarchical_semantic_chunking_from_snapshot` (DS V3 chunker) using `CHUNKING_CONFIG.chunk_size` and `CHUNKING_CONFIG.chunk_overlap`. Each chunk is mapped to its start page using character offset tracking against the page boundary spans. *(Note: `RecursiveCharacterTextSplitter` is imported in the notebook but no longer used as the splitter — it's a leftover from the pre-V3 chunker.)*

#### Step 4 — Denormalise metadata

For each chunk, copy all enrichment fields from the source registry row (esn, equipment_type, event_type, dates, document_summary, etc.) into the chunk's `metadata` JSON blob. No additional table lookups — Process 1 already enriched everything.

#### Step 5 — Embedding

All chunks across all docs in the batch are flattened and sent to LiteLLM (`azure-text-embedding-3-large-1`, 3072 dims) in sub-batches of `EMBED_BATCH_SIZE` (default 32). Up to `P2_EMBED_CONCURRENCY` (default 8) sub-batches run concurrently via `ThreadPoolExecutor`.

- Per-sub-batch fault tolerance: `safe_embed_batch` catches failures and returns None for that batch's refs.
- Per-doc coverage check: if more than 10% of a doc's chunks fail to embed, the whole doc is marked failed (avoids partial / low-quality vector representations).

#### Step 6 — MERGE chunk rows to Delta

Chunk rows are assembled with the materialised metadata JSON blob and `MERGE INTO` the chunk table on `chunk_id` (= `md5(document_id + "_" + chunk_index)`). Idempotent — re-running on the same docs updates existing rows; no duplicates.

#### Step 7 — Status update

- **On success:** `chunk_status='completed'`, `chunk_error=NULL`, `chunked_at=current_timestamp()`, `chunk_retry_count` reset.
- **On failure:** `chunk_status='failed'`, `chunk_error=<truncated message>`, `chunked_at=current_timestamp()`, `chunk_retry_count` incremented. Re-claimed on next iteration if still under retry cap; quarantined permanently once `chunk_retry_count >= FSR_P2_MAX_RETRIES`.

#### Step 8 — Audit log

One row per batch iteration written to `fsr_run_log` with run_id, timing, doc/chunk counts, and error summary.

#### Step 9 — VS index sync (run-level, once after drain loop)

After the drain loop exits (queue empty or `P2_MAX_ITERATIONS` reached), call `sync_vector_search()` once to trigger the Delta Sync (Triggered) index. The index does not auto-sync on source-table changes — it must be triggered explicitly. *Operational caveat: in long backfills the loop may run for many hours without exiting, leaving the index drifted behind the chunk table — see [§5 Vector Search Index Sync](#vector-search-index-sync) and [§11.5](#115-p2--periodic-vs-sync-during-drain-mode--should-have).*

### Drain loop behavior

| Parameter | Default | Effect |
|-----------|---------|--------|
| `FSR_P2_BATCH_SIZE` | 50 | Docs claimed per iteration |
| `FSR_P2_MAX_ITERATIONS` | 0 (unlimited) | Max iterations before stopping. 0 = drain until queue empty |
| `FSR_P2_MAX_RETRIES` | 3 | Max times a doc can fail before it stops being re-claimed |
| `FSR_MAX_PDFS` | _(none)_ | When set, overrides batch size (for testing) |

**Single-job backfill:** Set `P2_MAX_ITERATIONS=0` (default). One job run processes all pending docs in batches of 50. For 17.8K docs → ~356 iterations in a single job.

**Parallel backfill:** Launch N concurrent job runs. Each claims its own batch per iteration — claim locking prevents overlap. All N jobs drain the queue in parallel.

**Testing:** Set `FSR_MAX_PDFS=10` and `FSR_P2_MAX_ITERATIONS=1` for a single batch of 10 docs.

### Claim-based locking

```
chunk_status state machine:
  pending ──► in_progress ──► completed
     ▲            │
     │            ▼
     └───── failed ◄────────── (retry up to P2_MAX_RETRIES times)
                │
                ▼ (retry count >= P2_MAX_RETRIES)
          permanently failed (stays failed, no longer claimed)
```

- Claims use `SELECT ... LIMIT N` then `UPDATE ... WHERE document_id IN (...) AND chunk_status IN (pending, failed)` — the WHERE guard ensures a doc can't be double-claimed even if two jobs SELECT the same IDs.
- Claim query also filters `COALESCE(chunk_retry_count, 0) < P2_MAX_RETRIES` so docs that have exhausted retries are skipped.
- On failure: `chunk_retry_count` is incremented. On success: reset to 0.
- Stale claims (>30 min in `in_progress`) are recovered to `pending` at the start of each run.
- Not fully atomic (SELECT+UPDATE are separate statements), but Delta ACID + the WHERE guard make the worst case "one job claims fewer docs than expected" — no data corruption.
- Permanently failed docs remain queryable: `WHERE chunk_status = 'failed' AND chunk_retry_count >= 3`.

### Concurrency

Unlike P1, **P2 is genuinely parallel** at the embedding stage:

- **Within an iteration** — embedding sub-batches run on a `ThreadPoolExecutor(max_workers=P2_EMBED_CONCURRENCY)` (default 8). All 32-chunk sub-batches for the 50-doc claim run concurrently up to that pool size. See [`nb_sdg_fsr_chunks.py#L351`](../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py#L351).
- **PDF extraction + chunking** — sequential per doc within an iteration (no thread pool there today). The cost is dominated by embedding, so this hasn't been a hot path.
- **Across iterations** — strictly sequential within a single job. The drain loop waits for `process_one_batch()` to return before claiming the next 50.
- **Across jobs (parallel backfill)** — claim-based locking lets you launch N concurrent P2 job runs. Each job claims its own 50 docs per iteration (modulo the SELECT+UPDATE non-atomicity caveat — see [Claim-based locking](#claim-based-locking) above and [Section 11.4](#114-p2--claim-atomicity)).

### Failure handling

P2 has four distinct failure surfaces, each with bounded blast radius:

| Failure surface | Blast radius | Outcome | Retry path |
|---|---|---|---|
| **PDF extraction error** (PyMuPDF parse failure, e.g., `code=5: too many nested graphics states`, `code=7: object is not a stream`) | Single doc | Doc marked `chunk_status=failed`, `chunk_retry_count++`, error captured. Other 49 docs in the batch continue normally. | Re-claimed on next iteration if `chunk_retry_count < P2_MAX_RETRIES` |
| **Embedding sub-batch failure** (LiteLLM 4xx/5xx, network) | Up to 32 chunks | `safe_embed_batch` catches and returns None for those refs. The chunks are dropped, not propagated. | Triggers per-doc coverage check (next row) |
| **Per-doc embedding coverage** (more than 10% of a doc's chunks failed embedding) | Single doc | Doc marked `chunk_status=failed` with `Embedding coverage too low: X/Y chunks (Z% missing, threshold=0%)` | Re-claimed up to retry cap |
| **Iteration-level exception** (claim query fails, MERGE fails, etc.) | Whole iteration (50 docs) | Iteration aborts. In-progress claims released by the next run's stale-claim recovery (>30 min) | Stale recovery flips them back to `pending`; next iteration re-claims |

`P2_MAX_RETRIES=3`. After 3 failed attempts a doc is excluded from claim queries and stays `failed` permanently — quarantined, not deleted.

**Observed in PROD (May 1–2, 2026, ~12K docs processed):**
- 1 terminal failure: `74ed935e` — `code=5: too many nested graphics states` (complex graphics PDF, hit retry cap=3).
- 3 in-flight failures still under retry cap: `5eb78b05` (`code=7: object is not a stream`), `6a2840b8` (`Embedding coverage too low: 86/95 chunks`), `31b9a2df` (`code=5`).

### Resiliency

- **Claim-based locking** — no doc is processed twice concurrently. SELECT+UPDATE pattern with WHERE guard tolerates SELECT races; worst case is "one job claims fewer docs than expected" (no corruption). See [Section 11.4](#114-p2--claim-atomicity) for proposed atomic-claim improvement.
- **Stale-claim recovery** — at the start of each run, any doc stuck in `in_progress` for >30 min is reset to `pending`. Recovers from driver crashes, cluster auto-shutdown, or killed jobs without manual intervention.
- **Idempotent MERGE** — chunk rows are MERGEd on `chunk_id` (= `md5(document_id + "_" + chunk_index)`). Re-running the same batch overwrites identical rows — no duplicates, no orphans.
- **Bounded retry** — `P2_MAX_RETRIES=3` quarantines terminally-bad docs so they don't block the queue indefinitely.
- **Per-iteration audit** — every iteration writes a row to `fsr_run_log` (run_id, timing, doc/chunk counts, error_summary). A killed run still leaves a trail for the in-flight batch via the next run's recovery + this log.
- **Failure isolation at doc and sub-batch level** — one corrupt PDF or one embedding 5xx does not poison the whole 50-doc iteration. The notebook walks the failure tree and lets unaffected docs commit.
- **Drain-loop bounded restart cost** — restarting P2 mid-backfill costs at most one in-flight 50-doc iteration (released via stale recovery). All previously-completed docs stay completed.
- **Known caveat** — in long drain runs, `sync_vector_search()` only fires after the loop exits, so the VS index can drift far behind the chunk table during the backfill itself. See [Vector Search Index Sync](#vector-search-index-sync) and [Section 11.5](#115-p2--periodic-vs-sync-during-drain-mode).

### Vector Search Index Sync

The VS index is created as **`DELTA_SYNC`** with **`pipeline_type: TRIGGERED`**. This means the index does not auto-sync when the source table changes — it only syncs when explicitly triggered via the API.

**How sync works:**
- `sync_vector_search()` runs once at the end of P2, after the drain loop finishes
- It calls `POST /api/2.0/vector-search/indexes/{index}/sync` to trigger a sync
- If the endpoint isn't ONLINE or the index doesn't exist, it creates the index first
- Retries up to 3 times with 20s waits if the endpoint is warming

**Operational implication:**
- In **incremental mode** (scheduled job): sync fires automatically at the end of each job run — no manual intervention needed
- In **backfill mode**: if the job is stopped/restarted or spinning on terminal failures with no new data written, the last successful sync may be stale. Manually trigger a sync from the Databricks UI or API after stopping the job.
- **Why TRIGGERED over CONTINUOUS:** TRIGGERED is cheaper — no always-on sync pipeline. For this workload (batch ingestion, not real-time), a sync at the end of each job run is sufficient.

> **Open follow-up (May 2, 2026 — observed in PROD backfill):** In drain mode (`FSR_P2_MAX_ITERATIONS=0`), the iteration loop only exits when the claimable queue is empty, so `sync_vector_search()` doesn't fire for the entire duration of a long backfill. Observed gap: chunk table 831k rows vs VS index 231k rows (~600k drift) ~36h into the PROD run with last sync ~36h prior. Acceptable while no one queries the index, but we should design a smarter mid-run sync trigger for future long-running backfills. See [Section 11.5](#115-p2--periodic-vs-sync-during-drain-mode) for proposed options.

---

## 6. Embedding Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FSR_EMBEDDING_MODEL` | `azure-text-embedding-3-large-1` | Model via LiteLLM gateway |
| `FSR_EMBEDDING_DIMENSION` | 3072 | Expected vector dimension |
| `FSR_EMBED_BATCH_SIZE` | 32 | Texts per API call |
| `FSR_P2_EMBED_CONCURRENCY` | 8 | Parallel API calls via ThreadPoolExecutor |
| `FSR_EMBED_MAX_RETRIES` | 3 | Retries per API call (exponential backoff) |
| `FSR_EMBED_FAIL_THRESHOLD` | 0.10 | Max % of chunks that can fail embedding before doc is marked failed |

LiteLLM gateway URL: `dev-gateway.apps.gevernova.net`

---

## 7. Validation

**Notebook:** `nb_sdg_fsr_validate`

41+ automated checks organized in 5 categories:

| Category | Checks | Examples |
|----------|:------:|---------|
| 1. Table existence | 4 | All 4 tables exist and are queryable |
| 2. Metadata quality | ~10 | document_id NOT NULL, metadata_status distribution, page_count > 0, pdf_name derivation rate |
| 3. Chunk quality | ~10 | chunk_id uniqueness, chunk_text NOT NULL, embedding dimension = 3072, chunk_embedding NOT NULL |
| 4. Cross-table joins | ~8 | Every chunk has a metadata parent, every completed metadata doc has chunks, materialized field coverage |
| 5. Backfill safety | ~7 | No in_progress stuck, failure rate < threshold, chunk/page ratio sanity |

Findings are logged to `fsr_data_quality_log` per-doc. Some checks are hard fails (raise exception), others are warnings (logged but don't block).

### 7.1 SRE handoff — terminal failures, DQ log shape, and the operational query

This section consolidates the resiliency / SRE design behind the DQ log so the monitoring team has one place to read instead of chasing it through Slack threads. Companion to the standalone `PW_SDG_FSR_DQ_Validation` job introduced in UI-16.

#### Definitions — what counts as a "terminal failure"

A "terminal failure" is a doc that has been sitting in `metadata_status='failed'` (or `chunk_status='failed'`) across multiple ingestion runs and nobody has fixed the root cause (corrupt source PDF, image-only PDF, malformed structure, etc.). Two retry surfaces exist:

- **Per-call (in-run) retry** — the LLM and embedding clients each have their own retry loops (`FSR_MAX_RETRIES=3`, exponential backoff; embed has 3 retries plus a bisect fallback that re-tries the failed sub-batch one chunk at a time so good chunks still land). After both exhaust within a run, the doc is MERGEd as `failed`.
- **Per-doc lifetime retry** — `metadata_retry_count` (UI-18) and `chunk_retry_count` (pre-existing) are incremented on every failure MERGE and reset on success MERGE. The claim queries gate on `COALESCE(<counter>, 0) < {P1_MAX_RETRIES | P2_MAX_RETRIES}` (default 3 each), so a doc that fails 3 lifetime attempts stays in `failed` forever, consumes zero compute on subsequent runs, and is what we call "terminal".

*Operator note:* re-ingesting a terminal failure (after fixing the source PDF or patching code) requires resetting both the status **and** the counter, e.g. `UPDATE <metadata_table> SET metadata_status='pending', metadata_retry_count=0 WHERE document_id IN (...)`. Same pattern for the chunk side.

#### Stale-claim recovery (separate from retry)

P2 also has a separate safety net: any doc stuck in `chunk_status='in_progress'` for more than `FSR_STALE_CLAIM_MINUTES` (default 30) is reset to `pending` at the start of every run. So a crashed worker doesn't permanently park a doc — it goes back into the queue automatically. P1 does not need this because it doesn't have an `in_progress` state.

#### How the DQ job surfaces terminal failures

Check 5.7 (`Log all failed docs to DQ table for visibility`) scans the metadata + chunk tables and writes one `FAIL`-severity row per failed doc per run into `fsr_data_quality_log`. Three UI-17 fixes shaped how this row looks today:

1. **De-dup across runs** — 5.7 pre-loads `(document_id, check_name)` pairs already logged in the last `DQ_FAIL_DEDUP_DAYS=2` days and skips them. Without this the same standing terminal-failure population was being re-logged every run (~70 rows/day for the 72 prod terminals). SRE now sees a doc once when it first lands in the failed state, not every day forever.
2. **`failure_category` column** — added to the DQ log table (additive `ALTER TABLE ... ADD COLUMNS`). Populated at write time via `_classify_failure()` mapping the error string to one of: `corrupt_source`, `image_only_or_no_text`, `pdf_parse_error`, `partial_embed`, `gateway_error`, `unknown`. The set is open and expected to grow as ops categorizes new patterns. Routing hint only — the actual `metadata_error` / `chunk_error` columns on the source tables remain the source of truth.
3. **`pdf_name` backfill** — metadata-failure rows used to land with `pdf_name=NULL` because the `fsr_pdf_ref` lookup happens after metadata succeeds. 5.7 now pre-loads a `s3_filename → PDF_name` lookup from `FSR_PDF_REF_VIEW` and falls back to the `volume_path` basename if the ref view doesn't have it. SRE no longer has to JOIN back to the metadata table to get the filename.

#### How the DQ job itself behaves on failure

The notebook ends with `if failed > 0: raise AssertionError(...)`. Any failed check (including 5.7 firing because there are terminal-failure docs in the table) makes the workflow task FAIL. The yml has no `max_retries` on the task, so the failure is final for that run — ingestion is unaffected because the two jobs are now decoupled (UI-16). The DQ table write is wrapped in try/except, so even if the table write itself errors, the job still surfaces the assertion failure.

*Caveat:* check 5.7 will fire as long as any `failed` doc exists. With the de-dup window of 2 days, the daily fire rate drops to "only when a new terminal lands", but the assertion still trips. Two ways to handle this once monitoring is in place: (a) drain the standing terminal bucket per the terminal-failures plan, (b) tweak 5.7 to compare against an `accepted_terminals` baseline list and only fail on **new** terminals. Worth raising once an owner is assigned.

#### Suggested operational query for monitoring

For "what's actually new and actionable since yesterday":

```sql
SELECT document_id, pdf_name, check_name, failure_category, detail, created_at
FROM <fsr_dq_log_table>
WHERE created_at >= current_date() - INTERVAL 1 DAY
  AND severity = 'FAIL'
  AND failure_category != 'gateway_error'   -- self-clearing transient
ORDER BY failure_category, created_at DESC;
```

Route by `failure_category`:
- `corrupt_source` / `image_only_or_no_text` / `pdf_parse_error` → data team for source replacement
- `partial_embed` / `gateway_error` → should self-clear; only escalate if persistent
- `unknown` → the only category that should page on-call (means we have a pattern we haven't categorized yet — patch `_classify_failure()` once we know the shape)

#### Snapshot — prod DQ log on 2026-05-06 (pre-UI-17)

For calibration when the team starts watching this. Pulled from the May 5 validation run (last run before UI-17 lands):

| Category | Count | Owner |
|---|---|---|
| `corrupt_source` (No /Root, Unexpected EOF) | 52 | data team — source replacement |
| `image_only_or_no_text` (LLM returned no matching row) | 11 | us — likely image-only / no anchor text |
| `gateway_error` (KeyError 'content') | 3 | self-clearing post UI-11 patch |
| `pdf_parse_error` (PyMuPDF code=5/7) | 2 | malformed PDFs |
| `partial_embed` (embedding coverage too low) | 3 | partial-embed failure |
| WARN volume (enrichment, chunk/page ratio) | ~670 | non-blocking; filter by `severity='FAIL'` |

Net ~72 distinct terminal-failure docs in PROD; matches the bucket tracked in [terminal-failures-plan](../../fsr-prod-ops/comms/2026-05-06/terminal-failures-plan.md). After UI-17 lands, the de-dup means subsequent runs only log deltas off this baseline.

---

## 8. FORCE_RESET Behavior

When `FORCE_RESET=true`:

| Task | Action |
|------|--------|
| DDL | **Drops all 4 tables**, then recreates with latest schema. **Deletes VS index** so P2 recreates it fresh |
| P1 | Truncates metadata table, rescans all files (ignores watermark) |
| P2 | No special behavior (claims from metadata as normal). Auto-creates VS index if missing |

Use for: schema migrations on test/backfill tables, clean-slate reruns.

---

## 9. Configuration Reference

All parameters are set via Databricks job `base_parameters` (passed as widgets on serverless). Fall back to environment variables.

### Required — must set per job (no defaults, fail-fast)

| Parameter | Example (`_af_test`) | Example (`_backfill`) | Description |
|-----------|-------------------|----------------------|-------------|
| `FSR_METADATA_TABLE` | `vaid...biz_metadata_field_service_report_af_test` | `...biz_metadata_field_service_report` | Metadata registry table |
| `FSR_CHUNK_TABLE` | `vaid...vec_field_service_report_af_test` | `...vec_field_service_report` | Chunk table |
| `FSR_RUN_LOG_TABLE` | `vaid...fsr_run_log_af_test` | `...fsr_run_log` | P2 batch audit log |
| `FSR_DQ_LOG_TABLE` | `vaid...fsr_data_quality_log_af_test` | `...fsr_data_quality_log` | Validation DQ findings |
| `FSR_VS_ENDPOINT` | `pw-ser-sdg-vector-search_af_test` | `pw-ser-sdg-vector-search` | Vector Search endpoint |
| `FSR_VS_INDEX` | `vaid...vs_vec_field_service_report_chunks_af_test` | `...vs_vec_field_service_report` | Vector Search index |
| `LITELLM_API_KEY` | `sk-...` | `sk-...` | LiteLLM gateway API key |

### Run control

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FORCE_RESET` | `false` | DDL drops+recreates all tables; P1 truncates+rescans all files |
| `FSR_MAX_PDFS` | _(none)_ | Cap total docs per run. Overrides `P2_BATCH_SIZE` for P2. For testing only |
| `FSR_TARGET_PDF_NAMES` | _(none)_ | Comma-separated document_ids — only these are processed (debug) |

### Operator quick modes (copy/paste)

Use these when you need to tell an operator exactly what to set.

#### A) Ingest specific PDFs (TARGET mode)

Run P1 first, then P2 with the same target list.

**Job:** `PW_SDG_FSR_Metadata_Backfill`  
Set:
- `jb_env=prod`
- `FORCE_RESET=false`
- `FSR_TARGET_PDF_NAMES=<comma-separated document_id list>`
- `FSR_MAX_PDFS=` _(blank, or set to target-count as a hard cap)_

Keep defaults for `FSR_SOURCE_VOLUME_PATHS` and other tuning knobs unless you are load-testing.

**Job:** `PW_SDG_FSR_Chunking_Backfill`  
Set:
- `jb_env=prod`
- `FSR_TARGET_PDF_NAMES=<same comma-separated document_id list>`
- `FSR_P2_MAX_ITERATIONS=0` _(drain queue for those targets)_

Notes:
- `FSR_TARGET_PDF_NAMES` expects **document_id**, not full filename.
- For manual reports, `document_id` is lowercase filename stem with one trailing `.pdf` removed.

#### B) Backfill mode (DISCOVERY)

Use this for normal bulk discovery and processing.

**Job:** `PW_SDG_FSR_Metadata_Backfill`  
Set:
- `jb_env=prod`
- `FORCE_RESET=false`
- `FSR_TARGET_PDF_NAMES=` _(empty)_
- `FSR_MAX_PDFS=` _(empty for full run, or set a cap for staged backfill)_

Then run:

**Job:** `PW_SDG_FSR_Chunking_Backfill`  
Set:
- `jb_env=prod`
- `FSR_TARGET_PDF_NAMES=` _(empty)_
- `FSR_P2_MAX_ITERATIONS=0`

Safety:
- Never use `FORCE_RESET=true` on prod.

### P1 tuning (metadata extraction)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FSR_BATCH_SIZE` | `4` | Docs per LLM normalization batch |
| `FSR_PDF_EXTRACT_WORKERS` | `16` | Concurrent PDF extraction threads |
| `FSR_LLM_CONCURRENCY` | `3` | Starting LLM call concurrency |
| `FSR_LLM_CONCURRENCY_MAX` | `6` | Max LLM call concurrency |
| `FSR_BATCH_THREADS` | `4` | Batch processing threads |
| `FSR_BATCH_THREADS_START` | `2` | Starting batch threads (ramps up) |
| `FSR_BATCH_THREAD_RAMP_SECONDS` | `10` | Seconds between thread ramp-ups |
| `FSR_MAX_RETRIES` | `3` | Max retries for failed docs per run |

### P2 tuning (chunking + embedding)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FSR_P2_BATCH_SIZE` | `50` | Docs claimed per loop iteration |
| `FSR_P2_MAX_ITERATIONS` | `0` | Max batch iterations. **0 = drain queue** (process all pending). Set `1` for single-batch test |
| `FSR_P2_PDF_WORKERS` | `4` | PDF extraction concurrency |
| `FSR_P2_EMBED_CONCURRENCY` | `8` | Concurrent embedding API calls |
| `FSR_EMBED_BATCH_SIZE` | `32` | Texts per embedding API call |
| `FSR_EMBED_MAX_RETRIES` | `3` | Retries per embedding call |
| `FSR_EMBED_FAIL_THRESHOLD` | `0.10` | Doc-level embedding failure threshold (fraction) |
| `FSR_STALE_CLAIM_MINUTES` | `30` | Timeout for stale in_progress claims |

### Model / gateway

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FSR_LLM_MODEL` | `gemini-3-flash` | LLM for metadata normalization |
| `FSR_EMBEDDING_MODEL` | `azure-text-embedding-3-large-1` | Embedding model |
| `FSR_EMBEDDING_DIMENSION` | `3072` | Expected vector dimension |
| `FSR_LLM_VERIFY_SSL` | `false` | SSL verification for LLM calls |
| `FSR_VS_ENDPOINT` | _(required)_ | Vector Search endpoint name |

### Catalog / schema (rarely need to override)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `FSR_CATALOG_VIUD` | `viud` | Source volume catalog |
| `FSR_CATALOG_VGPP` | `vgpp` | Reference-table catalog. For the current FSR deployment plan, this stays `vgpp` in DEV as well as PROD. |
| `FSR_POC_CATALOG` | `main` | POC catalog |
| `FSR_POC_SCHEMA` | `gp_services_sdg_poc` | POC schema |

### Example: complete test job parameters

```
FORCE_RESET              = true
FSR_METADATA_TABLE       = main.gp_services_sdg_poc.fsr_metadata_registry_test
FSR_CHUNK_TABLE          = main.gp_services_sdg_poc.fsr_chunks_test
FSR_VS_INDEX             = main.gp_services_sdg_poc.vs_fsr_chunks_test
FSR_RUN_LOG_TABLE        = main.gp_services_sdg_poc.fsr_run_log_test
FSR_DQ_LOG_TABLE         = main.gp_services_sdg_poc.fsr_data_quality_log_test
FSR_MAX_PDFS             = 10
FSR_P2_MAX_ITERATIONS    = 1
FSR_TARGET_PDF_NAMES     = (optional — comma-separated UUIDs)
LITELLM_API_KEY          = sk-...
```

### Example: backfill job parameters

```
FORCE_RESET              = true   (first run only, then false)
FSR_METADATA_TABLE       = main.gp_services_sdg_poc.fsr_metadata_registry_backfill
FSR_CHUNK_TABLE          = main.gp_services_sdg_poc.fsr_chunks_backfill
FSR_VS_INDEX             = main.gp_services_sdg_poc.vs_fsr_chunks_backfill
FSR_RUN_LOG_TABLE        = main.gp_services_sdg_poc.fsr_run_log_backfill
FSR_DQ_LOG_TABLE         = main.gp_services_sdg_poc.fsr_data_quality_log_backfill
FSR_P2_BATCH_SIZE        = 50     (or 200/500 after scaling tests)
FSR_P2_MAX_ITERATIONS    = 0      (drain the queue)
LITELLM_API_KEY          = sk-...
```

For the current canonical DEV backfill, the live job parameters are:

```
FORCE_RESET              = false
FSR_METADATA_TABLE       = vaid.ai_sot_field_service_report.biz_metadata_field_service_report
FSR_CHUNK_TABLE          = vaid.ai_std_con_field_service_report.vec_field_service_report
FSR_VS_INDEX             = vaid.ai_std_con_field_service_report.vs_vec_field_service_report
FSR_RUN_LOG_TABLE        = vaid.ai_sot_field_service_report.fsr_run_log
FSR_DQ_LOG_TABLE         = vaid.ai_sot_field_service_report.fsr_data_quality_log
FSR_BATCH_SIZE           = 8
FSR_P2_BATCH_SIZE        = 50
FSR_P2_MAX_ITERATIONS    = 0
```

---

## 10. Backfill Strategy

For the full 17.8K document corpus:

### Single-job approach

One workflow run with `P2_MAX_ITERATIONS=0` (default). P1 processes all PDFs, P2 drains the queue in batches of `P2_BATCH_SIZE`.

Estimated time depends on embedding throughput. With `EMBED_BATCH_SIZE=32`, `P2_EMBED_CONCURRENCY=8`, and ~33 chunks/doc average:

```
17,800 docs × 33 chunks = 587,400 chunks
587,400 / 32 = 18,356 embedding API calls
18,356 / 8 threads = 2,295 serial rounds
At ~0.5s/call → ~19 min of pure embedding time
+ PDF extraction + chunking + MERGE overhead
```

### Parallel-job approach

Launch N concurrent workflow runs (skip DDL + P1 after the first). Current P2 code uses `SELECT` then `UPDATE`, so concurrent runs can still race before rows flip to `in_progress`; scale N cautiously and treat MERGE idempotency as the main duplicate guard until claim logic is made atomic.

### Monitoring

- `fsr_run_log`: track per-batch timing, success/failure rates
- `fsr_data_quality_log`: track per-doc DQ issues
- Databricks job run page: wall-clock time per task
- SQL queries on metadata table: `SELECT chunk_status, COUNT(*) GROUP BY chunk_status`

---

## 11. Pipeline Improvements (Incremental + Backfill)

Observations from the Apr 30 – May 2, 2026 PROD backfill (~18.1K docs). Incremental and backfill share the same code path, so most items apply to both — the **Mode** column flags where each one bites. Items here are **proposals to evaluate after backfill completes** — do not implement mid-run.

### Priority legend

| Label | Meaning |
|---|---|
| 🔴 **Critical** | Latent bug or risk that will cause user-visible breakage soon. Fix before it bites. |
| 🟠 **Should have** | Real correctness/efficiency issue or operational footgun. Fix in the next code window. |
| 🟡 **Good to have** | Hygiene, scalability headroom, or process polish. No urgency. |

### Summary

| # | Item | Description | Mode | Priority |
|---|---|---|---|---|
| 11.1 | P1 wire up real concurrency | Make P1 actually parallel — today PDF reads + LLM calls run one at a time even though config knobs suggest threading. | Both (helps backfill more) | 🟡 Good to have |
| 11.2 | P1 tiered LLM error handling (transient retry + per-doc fallback) | Stop one bad LLM response from killing all 4 docs in the batch; retry transient errors in-loop, isolate parse errors per doc. | Both | 🟠 Should have |
| 11.3 | P1 null-pdf-name short-circuit | Detect empty page-1 text and fail fast instead of wasting an LLM call on image-only / corrupt PDFs. | Both | 🟡 Good to have |
| 11.4 | P2 atomic claim | Replace SELECT-then-UPDATE with a single MERGE so two parallel P2 jobs can't race on the same docs. | Both (matters more in parallel backfill) | 🟠 Should have |
| 11.5 | Separate VS sync job | Pull `sync_vector_search()` out of P2 into its own scheduled job so the index stays current independent of chunking iteration speed (fixes ~600K-row drift seen in PROD backfill). | Both | 🟠 Should have |
| 11.6 | Operational — backfill kickoff hygiene | Pre-flight checklist item: make sure no schedule is attached to backfill jobs (avoids overlapping runs). | Backfill-only | 🟡 Good to have |
| 11.7 | P1 discovery dedup re-validation | Re-check the `left_anti` discovery path with full backfill telemetry to make sure no "completed-but-no-metadata" rows slip through. | Both | 🟡 Good to have |
| 11.8 | FORCE_RESET — separate out the destructive path | Move the truncate-and-rescan flag out of the everyday job into a separate notebook/job; add a soft-reset variant for the common "re-extract" case. | Both (riskier in PROD incremental) | 🟠 Should have |
| 11.9 | P1 BACKLOG trigger should exclude retry-exhausted rows | Filter terminal failures out of the BACKLOG count — otherwise stuck failures keep BACKLOG mode on forever and DISCOVERY never runs again. | Incremental-only | 🔴 **Critical** |
| 11.10 | P1 re-upload detection via `file_last_modified` | Track file mtime so a PDF replaced in-volume gets re-extracted instead of silently keeping stale metadata + chunks. | Incremental-only | 🟡 Good to have (pending team confirmation) |

### 11.1 P1 — wire up real concurrency — 🟡 Good to have

**Problem:** P1 is sequential despite the config knobs (`P1_EXTRACT_WORKERS`, `P1_LLM_CONCURRENCY`, `P1_BATCH_THREADS`) suggesting otherwise. Throughput is ~500 docs every ~85–90 min, gated by serial LLM round-trips. P1 currently produces faster than P2 consumes, so this isn't the wall-clock bottleneck today — but P2 will eventually parallelize further and P1 will become the limit.

**Proposal:**
- PDF extraction: wrap the `for row in batch_rows` loop in `ThreadPoolExecutor(max_workers=P1_EXTRACT_WORKERS)` — pdfplumber is I/O-bound on volume reads, easy win.
- LLM normalization: run the per-batch LLM calls under `ThreadPoolExecutor(max_workers=P1_LLM_CONCURRENCY)` with the existing ramp logic.
- If we don't intend to use them, **delete the unused knobs** from `common/fsr_config.py` so the config surface matches reality.

### 11.2 P1 — tiered LLM error handling (transient retry + per-doc fallback) — 🟠 Should have

**Problem:** The current `try/except Exception` around the LLM call has two efficiency problems and conflates fundamentally different error classes:

1. **Blast radius too big.** A single transient gateway 5xx fails all 4 docs in the LLM batch and burns 1 of 3 retry budget for each — even though nothing is wrong with the docs. Three unlucky transient errors → 4 perfectly-valid docs go terminal.
2. **No in-loop retry on transient errors.** Network blips, 502/503, and 429 rate limits are exactly the failures that succeed on a quick retry. Today they fall all the way out to "next run via BACKLOG mode" — minutes-to-hours of latency for what should be a 1–2 second retry.
3. **Parse errors conflated with network errors.** A `KeyError: 'content'` (May 1 incident — 4 sibling docs failed in the 08:29 UTC batch) is **deterministic** — retrying it does nothing, but it's caught by the same broad handler and burns 3 retries × 4 docs = 12 wasted LLM calls before going terminal.

**Proposal — tiered handler:**

| Error class | Action | Blast radius |
|---|---|---|
| Network / 5xx / timeout | Retry the **same** call in-loop with exponential backoff (3 attempts, 1s/2s/4s). Then fail the batch. | 0 docs (typical case) |
| Rate limit (429) | Sleep `Retry-After` (or default backoff) then retry. | 0 docs |
| Parse error (response shape wrong, missing keys, JSON decode) | Fall back to **per-doc LLM calls** for just that batch — isolates the one bad response from the 3 good ones. | 1 doc (typical case) |
| Per-doc downstream errors (e.g., `LLM returned no matching row`) | Mark only the affected doc failed (already current behavior). | 1 doc |

**Net effect:** transient errors stop consuming retry budget; parse-error blast radius shrinks from 4 → typically 0–1 docs.

### 11.3 P1 — null-pdf-name failure cluster — 🟡 Good to have

**Problem:** ~16 P1 terminal failures over ~36h, all with `pdf_name=null`, `page_count=null`, error `"LLM returned no matching row for this document"`. Likely image-only or corrupt PDFs where pdfplumber's page-1 text extraction returns empty, leaving the LLM nothing to anchor on.

**Proposal:** Detect empty page-1 text **before** sending to LLM and short-circuit with a clearer terminal status (e.g., `metadata_error="empty_page1_text"`). Avoids burning an LLM call and gives the data team a cleaner signal.

### 11.4 P2 — claim atomicity — 🟠 Should have

**Problem:** Current P2 claim is `SELECT` then `UPDATE`. Two concurrent P2 jobs can read the same `pending` rows before either flips them to `in_progress`. MERGE on chunk write is the only real duplicate guard. Cautioned in [Section 10](#10-backfill-strategy) but not fixed.

**Proposal:** Use a single `MERGE INTO ... WHEN MATCHED AND chunk_status='pending' THEN UPDATE SET chunk_status='in_progress', claimed_by=:run_id` to atomically claim. Enables safe N-way parallel P2 jobs without race risk.

### 11.5 Separate VS sync job — 🟠 Should have

**Problem:** In drain mode (`P2_MAX_ITERATIONS=0`), `sync_vector_search()` only fires after the iteration loop exits. During PROD backfill the loop didn't exit for ~36h → chunk table grew to 831K rows while VS index stayed at 231K (~600K drift). Acceptable while no one queries the index; not acceptable for any future backfill where the index is live.

**Proposal — separate sync-only job, decoupled from chunking:**

Pull the `sync_vector_search()` call out of the P2 notebook entirely and put it in its own small notebook + Databricks job (`PW_SDG_FSR_VS_Sync`) that runs on a fixed cadence (e.g., every 30 min, or hourly). The chunking job stops carrying the sync responsibility; it just writes Delta rows and exits its iteration. The sync job triggers `POST /sync` against the VS index and logs the result.

**Why this over the "sync every N iterations" or "sync when delta > threshold" alternatives:**

| Aspect | Inline (every N iters / delta) | Separate sync job |
|---|---|---|
| Coupling | Sync latency tied to chunking iteration speed — slow iters = stale index | Cadence is independent of chunking throughput |
| Failure isolation | A sync API failure in the middle of a 36h drain can crash or stall the chunking loop | Sync failures don't touch chunking; rerun the sync job |
| Parallel chunking jobs | Each chunking job calls sync independently → duplicate / racing sync calls | Exactly one sync caller regardless of how many chunking jobs run |
| Incremental mode | Still fine — sync job runs on its cadence, picks up the small delta | Same — no special-case code path for incremental vs backfill |
| Operability | Sync behavior buried inside chunking notebook | Standalone job: clear last-run time, clear failure surface, easy to pause |

**Implementation sketch:**
- New notebook `silver/src/etl/nb_sdg_fsr_vs_sync` — reads `FSR_VS_ENDPOINT` / `FSR_VS_INDEX`, calls the existing `sync_vector_search()` helper, writes a row to `fsr_run_log` with the sync outcome.
- New job `PW_SDG_FSR_VS_Sync` with a cron trigger (start at every 30 min during backfill; relax to hourly or per-incremental-run cadence afterwards).
- Remove the end-of-drain `sync_vector_search()` call from `nb_sdg_fsr_chunks` (or guard it behind a `FSR_P2_TRIGGER_VS_SYNC` flag, default off, so the old behavior is still available for ad-hoc one-shot runs).
- Sync is idempotent — a no-op call when there's nothing new is cheap, so over-scheduling is safe.

### 11.6 Operational — backfill kickoff hygiene — 🟡 Good to have

**Problem:** During PROD kickoff, `PW_SDG_FSR_Chunking_Backfill` was given a daily UI-level schedule that would have caused overlapping P2 runs (doubled cost + LLM gateway pressure). Caught and removed mid-run.

**Proposal:** Add a pre-flight check item: "No schedule attached to backfill jobs (UI or YAML)." Already in [fsr-prod-ops/backfill-monitoring-plan.md](../../fsr-prod-ops/backfill-monitoring-plan.md) as a one-off; promote to a standing checklist item in the runbook.

### 11.7 P1 — eliminate "completed but no metadata" via better discovery dedup — 🟡 Good to have

*Open for discussion.* Discovery mode joins `left_anti` on `document_id` to skip already-known docs. If a row is in `failed` state, it's still re-claimed on next run via BACKLOG mode (correct). No known bug here, but worth re-validating the dedup paths once we have full backfill telemetry.

### 11.8 FORCE_RESET — separate out the destructive path — 🟠 Should have

**Problem:** `FORCE_RESET=true` is a job parameter that truncates the metadata registry before discovery. Today it sits side-by-side with routine knobs in the Databricks Jobs UI. A single accidental check (or a copy-paste from a test job config) wipes the entire backfill — ~30+ hours of work. The only protection is the runbook line "NEVER true on prod" and the YAML default of `false`.

This is a high-blast-radius, low-frequency operation glued onto a high-frequency, low-blast-radius UI. The design surface is wrong.

**Proposal — three options, in increasing order of effort:**

| Option | Description | Effort | Safety gain |
|---|---|---|---|
| (a) Two-key confirmation | Require `FORCE_RESET=true` **and** `FORCE_RESET_CONFIRM_TABLE=<exact metadata table name>`. Notebook fails fast if both aren't present and matching. | Tiny — small notebook tweak. | Removes accidental single-click damage. Doesn't help if both params are copied together. |
| (b) Separate notebook + job | Move the truncate path out of `nb_sdg_fsr_metadata` entirely into `nb_sdg_fsr_force_reset` with its own job (`PW_SDG_FSR_ForceReset`). Ingestion notebook stops carrying destructive code. | Small refactor — extract the truncate block, new YAML. | Clean separation of concerns. Job nobody runs by accident. Pairs well with (a). |
| (c) Soft-reset variant | Add a "soft reset" mode that flips all rows to `metadata_status='pending'` instead of dropping them. Most callers of `FORCE_RESET` actually want "re-extract metadata after a logic change" — they don't need a truncate. Hard reset becomes the rare admin-only path. | Slightly more — new code path, new param. | Eliminates the most common reason anyone reaches for `FORCE_RESET` in the first place. |

**Recommendation:** (b) + (c). Put the destructive path in its own job; offer a soft-reset for the everyday "re-extract" case so the destructive job rarely needs to run at all. Aligns with the broader principle that **destructive operations should require deliberate ceremony, not a checkbox**.

### 11.9 P1 — BACKLOG trigger should exclude retry-exhausted rows — 🔴 **Critical**

**Problem (latent bug, will surface within days):** P1's BACKLOG-mode trigger is:

```python
SELECT COUNT(*) FROM {METADATA_TABLE}
WHERE metadata_status IN ('pending', 'failed')
```

This counts **all** failed rows — including those that have already exhausted `P1_MAX_RETRIES=3` and are excluded from claim queries. Once a doc goes terminal:

- It stays in `failed` state permanently (by design — quarantine, not deletion).
- It keeps BACKLOG mode triggered on every subsequent run (`COUNT(*) > 0`).
- BACKLOG mode skips the volume scan entirely.
- DISCOVERY mode therefore never runs again.
- **New PDFs landing in the volume never get ingested.**

PROD already has ~16 P1 terminal failures heading toward retry-cap exhaustion (the null-pdf "no matching row" cluster + the `'content'` cluster from May 1). Once they hit the cap, incremental ingestion silently stops working — no error, no alert, just nothing happens.

**Proposal:**

Change the trigger query to exclude retry-exhausted rows:

```python
SELECT COUNT(*) FROM {METADATA_TABLE}
WHERE metadata_status = 'pending'
   OR (metadata_status = 'failed'
       AND COALESCE(metadata_retry_count, 0) < {P1_MAX_RETRIES})
```

This matches what the claim query already filters on, so BACKLOG mode count == claim-eligible count. When the only remaining failures are terminal, count drops to zero and DISCOVERY runs normally on the next execution.

**Bonus consideration:** Even with the fix, terminal-failed rows accumulate forever in the metadata table. Consider a `terminated` status (or a `metadata_status='quarantined'` value) as a third terminal state — clearer signal to operators and downstream consumers that the doc is parked, not actively-failing.

### 11.10 P1 — re-upload detection via `file_last_modified` — 🟡 Good to have (pending team confirmation)

**Problem (design gap, not a confirmed bug today):** The original Confluence design specified Step 1 as: *"Insert stub rows for new files with `metadata_status = 'pending'`; reset `metadata_status = 'pending'` for re-uploaded files (changed `file_last_modified`)."* Current implementation drops the second half:

- The registry does **not** store `file_last_modified` or `file_size_bytes`.
- DISCOVERY's `left_anti` join keys on `document_id` only — any doc already in the table is skipped regardless of whether its content has changed in the volume.
- If a PDF is overwritten in-volume with the same UUID filename but different content (corrected version, re-scan, re-export from upstream), the pipeline silently keeps the old metadata + chunks. The vector index serves stale results indefinitely.
- No error path triggers. Metadata table looks healthy (`completed`/`completed`). Only way to detect today: byte-compare every PDF in the volume against… nothing, because no fingerprint is stored.

**Pre-condition before implementing:** confirm with the upstream owners (FieldVision team, ecrt_reports manual uploaders) whether re-uploads under the same filename actually happen. If they don't, this stays as a documented gap with no code change. If they do — even occasionally — fix becomes worthwhile.

**Proposal — staged:**

| Stage | Description | Effort | Risk |
|---|---|---|---|
| **1. Capture** | Add `file_size_bytes` and `file_last_modified` columns to the registry. Populate from the volume listing during discovery. No behavior change beyond writing two more columns. | Tiny — schema add + 2 lines in discovery. | Zero. |
| **2. Detect** | Add a DQ / pulse query: `WHERE registry.file_last_modified < volume.mod_time` to surface stale rows. Visibility only, no auto-action. | Small — one validation check. | Zero. |
| **3. Auto-reprocess** | Modify DISCOVERY's `left_anti` to dedup on `(document_id, file_last_modified)` instead of just `document_id`. Modified files reset to `metadata_status='pending'`, retry counters cleared. Behind a feature flag until drift volume is understood. | Medium — touches discovery logic and stub-row reset semantics. | Low if flagged; could surprise operators if it silently re-runs many docs. |
| **4. Content hash (optional)** | If mtime proves unreliable (e.g., `cp` without `-p` resets it), store an MD5/SHA on first ingest and compare on rediscover. | Larger — hash compute on every PDF. | Probably overkill; defer until Stage 3 telemetry shows mtime is insufficient. |

**Recommendation:** Stage 1 + 2 first (cheap, zero behavior change, gives evidence). Stage 3 only after team confirms re-uploads happen and we've seen drift volume. Stage 4 only if Stage 3 isn't enough.

---

### 11.11 Move Tier-2 LLM ESN detection from P2 into P1 — 🟠 Should have (before enabling the feature)

**Problem (separation-of-concerns gap, not a runtime bug):** Tier-2 LLM ESN detection currently lives inside P2 (`nb_sdg_fsr_chunks.py`, the `if FSR_ESN_DETECT_ENABLED and doc_full_text:` block). P2's responsibility is chunk → embed → index. Metadata extraction is P1's job. The current placement was an optimization shortcut to reuse the already-loaded PDF snapshot, but it creates a few problems once the flag is turned on:

- **Re-pays the LLM bill on every re-chunk.** Re-chunking for a new chunk size, embedder swap, or a chunk-table rebuild re-calls the LLM for ESN detection that hasn't changed.
- **Mixed concerns.** Anyone reading P2 has to understand metadata-extraction logic that doesn't belong there. Same for anyone debugging metadata gaps in P1.
- **No persistence on the metadata side.** The result lives only in an in-memory dict (`doc_llm_esns`) and gets materialised straight into `chunk_rows.metadata` JSON. If P2 fails after Tier-2 ran, the work is lost. The metadata table is not the source of truth for "what ESNs does this doc have."
- **Two sources of truth for ESN.** Every other metadata field is in the metadata table; ESN (when Tier-2 fires) is split across `metadata.esn` (Tier-1) + chunk-row JSON (Tier-2).

**Why this is currently dormant:** `FSR_ESN_DETECT_ENABLED=false` in production. The feature is built but not active, so no live impact today. This open item is "fix before turning the feature on", not "fix now."

**Proposal:**

| Stage | Description | Effort | Risk |
|---|---|---|---|
| **1. Move the LLM call into P1** | Run `analyze_document_text_for_esn_counts()` in P1 when Tier-1 returns null/low-confidence. Persist the qualified ESNs into a metadata-table column (e.g. `esn_set` array, or a parallel `metadata_esn_tier2` column with a confidence/source tag). | Medium — PDF text already loaded in P1 for first-page extraction; reuse the same snapshot. | Low. |
| **2. P2 reads only from metadata** | Replace the in-P2 ESN block with a read of `metadata.esn_set`. P2 has no LLM calls; the multi-ESN fan-out logic stays unchanged but sources its ESNs from a single column. | Small — delete the Tier-2 block, swap one input. | Low. |
| **3. Backfill story** | When Tier-2 is first turned on, an offline P1 re-run over completed docs (mode TBD — a new TARGET-style mode or one-shot script) populates `esn_set`. P2 then re-runs (already idempotent via `chunk_status`/MERGE) and writes the multi-ESN chunk rows. | Medium — needs a clean re-run mode without forcing a full reprocess. | Medium — must avoid corrupting good metadata; gate on a flag. |

**Result after fix:**
- P1 owns all metadata extraction (Tier-1 regex + Tier-2 LLM, both feeding the metadata table).
- P2 has zero LLM calls — only the embedding model. Re-chunking is free.
- Metadata table is the single source of truth for ESN; chunk rows just denormalise from it.
- When `FSR_ESN_DETECT_ENABLED` flips to `true`, only P1 cost goes up; P2 stays cheap.

**Recommendation:** schedule alongside any work that turns Tier-2 on. Doing both in the same change keeps the cost of the move small (we'd be touching this code anyway) and avoids carrying a known design debt into production behavior.

---

## 12. Document Summary

> **Status (May 12):** Decision updated after alignment call.  
> **Selected path:** Use Pranesh TOC-based summary extraction flow for both backfill and incremental.  
> **Not selected:** PSOT `executive_summary` path is not part of the target implementation for document summary.  
> **Priority:** Execute backfill first, then incremental P1 update.

### Implementation split (required)

Document summary rollout is intentionally two-part:

1. **One-time backfill for existing corpus**
   - Run ad-hoc backfill to populate `document_summary` for already-ingested docs.
   - This is an operator/data-fix path and can be rerun safely for null/failed rows.

2. **Incremental path for new docs**
   - Keep `document_summary` population in P1 metadata extraction for newly discovered documents.
   - New docs should not rely on ad-hoc backfill once incremental is live.

This split avoids reprocessing the full corpus through normal ingestion while ensuring all future docs get summary by default.

### What it is

A short summary of each FSR document, stored once per document in the metadata registry and materialized into every chunk row's metadata JSON. Gives the RAG retrieval layer document-level context alongside chunk-level text.

Example: _"FSR report on ESN 338X424 covering a 12-month combustion inspection — findings include bearing replacement, blade tip oxidation, and transition piece cracking. Report issued 2024-03-15 by J. Smith."_

### Source: TOC-based extraction (selected)

The agreed behavior is:

- Use TOC/summary-section extraction from PDF (`pdfplumber`-based Pranesh flow).
- Use the same extraction logic for both backfill and incremental to keep outputs consistent.
- Do not depend on PSOT `executive_summary` for summary population in this rollout.

### Current state in code

The plumbing already exists:

| Layer | What's there | What's missing |
|-------|-------------|----------------|
| **Schema** | `document_summary STRING` column in metadata DDL (nullable) | Nothing — column exists |
| **P1** | MERGE writes `document_summary` | Replace current PSOT summary block with TOC extraction call |
| **P2** | Reads `document_summary` from metadata, includes in chunk metadata JSON blob | Nothing — already materializes it |
| **Chunk table** | `metadata` JSON column carries `document_summary` field | Just gets NULL today |

### Phase 1 — TOC extraction (production)

Populate `document_summary` using TOC extraction during backfill and during P1 for new docs.

**Change in P1:**
1. Remove PSOT `executive_summary` summary assignment block.
2. Call TOC extraction helper on `volume_path`.
3. Write extracted text to `document_summary`; on extraction failure, keep null and record status/error.

**Impact:**
- P2 already materializes `document_summary` into chunk metadata JSON — no changes needed.
- One consistent logic path across old and new docs.

**Code effort:** Moderate — replace PSOT summary block with TOC extraction call + error handling.

**Multi-ESN consideration:** 
Since PSOT lookup is a simple table JOIN, there is no inefficiency: all rows for a document (primary + secondary ESNs) share the same `volume_path` and simply join to the same PSOT row. ✅

However, if Phase 2 or backfill uses **Pranesh's TOC extraction** (PDF parsing), this becomes critical: documents with multiple ESNs (e.g., `document_id = uuid_ESN1`, `uuid_ESN2`, `uuid_ESN3`) all point to the same PDF. **Current implementations will extract the same PDF 3 times** (once per `document_id`).

**Mitigation before backfill/Phase 2:**
- Deduplicate by `volume_path` before extraction
- Extract once per PDF
- Broadcast result to all `document_id` rows pointing to that path
- Reduces wall-clock time from ~70 hours to ~24 hours for 17K+ corpus

### Phase 2 — Summary enhancement (future)

For docs where SOT `executive_summary` is null/empty, add a separate enhancement pipeline after production stabilization.

**Approach:**
1. Query metadata registry for docs where `document_summary IS NULL`
2. Detect TOC/summary section from early pages
3. Extract summary section text directly when available
4. Use LLM fallback only when deterministic extraction is not possible
5. UPDATE `document_summary` in metadata registry and re-materialize chunk metadata if needed

**Why separate:**
- Avoids heavy whole-document LLM calls in the production critical path
- Keeps backfill focused on required metadata/chunking outcomes
- Summary generation remains independent and can be improved iteratively

**Design decisions for Phase 2:**

| Question | Decision |
|----------|----------|
| **Which pages?** | TOC/early pages first; extract target summary section when present |
| **Which LLM?** | Optional fallback only, not first-line strategy |
| **Store where?** | `document_summary` in metadata, materialized to all chunks via metadata JSON |
| **Cost?** | Lower than full-document summarization due to deterministic extraction first |

### Summary of approach

```
Production now:       PSOT/SOT executive_summary when present; otherwise null (acceptable)
Priority now:         ESN extraction quality + pdf_name fallback format
Future enhancement:   TOC/summary-section extraction, with optional LLM fallback
```

**Open items:**
- Confirm exact TOC parsing rules for summary section extraction
- Decide threshold for acceptable summary coverage before additional enhancement work
- Confirm whether any downstream consumer requires non-null summary for all docs

No schema changes needed. No P2 changes needed. Existing chunk data is unaffected — Phase 2 just triggers a re-materialization for updated docs.
