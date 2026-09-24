# TIL Pipeline Design

## High-Level, Minimal v1

## Context and Intent

TIL applicability is Step 6 in SDG and is the first major AI validation step.

**Design goal:** Build a pipeline that is robust, scalable, and easy to evolve as extraction and chunking AI methods change.

**Architecture pattern:** Medallion architecture over Delta tables:

* Bronze
* Silver
* Gold

## Initial Understanding

We need a modular document pipeline where the parser and chunker are pluggable.

We should separate ingestion, extraction, and retrieval preparation so each layer can be improved independently.

We should keep strong lineage and reprocessing controls so method upgrades can be rolled out safely.

## Pipeline vs App Boundary

For clean ownership, keep the data pipeline narrow and move disposition and decisioning logic to the app layer.

### Data Pipeline Responsibilities

* Document ingestion and versioning
* Parsing and metadata extraction
* Chunking
* Embeddings generation
* Publish to vector index
* Basic quality checks and lineage/audit

### App Responsibilities

* Template coverage logic
* Service-history retrieval and completion review
* SBOM lookup and interpretation
* Final disposition decision
* Guardrails and serving-time policies
* User-facing explainability and workflow actions

### Practical v1 Pipeline Scope

1. Bronze to Silver: parse and normalize key fields.
2. Silver to Gold: chunk and embed.
3. Gold to index: sync trigger.
4. Observability: run audit plus MLflow tracking.

Everything else can consume indexed data at query time in the app layer.

### Why this boundary helps

* Simpler, more stable pipeline
* Faster iteration on business logic in app code
* Fewer pipeline redeploys when disposition rules evolve

---

# Proposed High-Level Architecture

## Bronze: Landing and Lineage

### Input

Raw TIL PDFs and source metadata from the business drop location.

Bronze is the Databricks Volume populated and managed upstream by the D&A team.

Discovery status and run audit are tracked by the TIL pipeline, not written back to the Bronze landing layer.

### Rules

* No AI transformation in Bronze
* Idempotent ingestion using a composite uniqueness key:

  * `source_hash`
  * selected source fields
* Keep raw payload for replay

---

## Silver: Metadata Extraction

### Purpose

Normalize and validate TIL-level metadata used in applicability logic.

### Extraction Module

The extraction module should be replaceable.

```python
parser.extract(document_binary, config) -> structured_output
```

### Current Candidate

* `ai_parse_document` based extractor

### Future Options

* DS parser
* Custom parser using the same contract

### Silver Outputs: Delta

* Extracted metadata and parser output references
* Field set can evolve over time
* Quality signals
* Extraction run lineage
* Document-to-element traceability for downstream validation

### Silver v1 Table Naming and Shape (Current Working Decision)

To stay consistent with FSR naming, Silver Process 1 writes to:

* Schema: `vgpd.til_profiles`
* Table: `til_metadata`

Core columns for `til_metadata`:

* `til_number` (STRING) — business key, extracted from document
* `til_profile` (JSON payload stored as STRING)
* `pdf_file_hash` (STRING) — MD5 of binary PDF; enables incremental detection (skip parse+LLM if unchanged)
* `content_hash` (STRING) — MD5 of extraction output; enables change detection at extraction layer
* `extraction_confidence` (DOUBLE)
* `metadata_status` (STRING) — status including incremental skip reason
* `incremental_skip_reason` (STRING, nullable) — reason for skip (e.g., `pdf_file_hash_match`)
* `llm_model` (STRING)
* `run_id` (TIMESTAMP) — audit column; when this record was last processed
* `processed_at` (TIMESTAMP-compatible value)
* `source_file_path` (STRING)
* `error_message` (STRING, nullable)

### Working Assumptions for v1

These assumptions are active for the current implementation and can be revised later if source behavior changes:

* TIL numbers extracted from documents are the business key (one row per til_number).
* PDF volume is the authoritative source of truth, not an external SOT table.
* **True incremental ingestion**: PDF file content is hashed (MD5) before any processing.
  * If PDF file_hash matches existing record and `FORCE_REPROCESS=false`, extraction is skipped entirely (parsing + LLM).
  * If PDF is new, changed, or `FORCE_REPROCESS=true`, normal extraction proceeds (parse + LLM).
* `content_hash` (on extraction output) enables additional change detection at the LLM extraction layer.
* `run_id` is an audit column only, not part of the merge key (no multi-row-per-til fragmentation).
* On rerun with unchanged PDFs and `FORCE_REPROCESS=false`, 326+ PDFs from 2026-03-23 are skipped (no parse+LLM cost).

### Operational Contract (Current Working Decision)

Until D&A confirms any change in source behavior, Process 1 will use the following working contract:

* **Business key for `til_metadata`**: `matched_til_number` (extracted from document)
* **True Incremental Detection** (unless `FORCE_REPROCESS=true`):
  * **PDF file_hash (MD5 of binary)**: Computed before parsing; signals actual PDF change
    * Match → skip parsing + LLM call (cost savings: ~99% of static corpus on rerun)
    * Mark record as `completed_incremental_skip` with reason `pdf_file_hash_match`
  * **Content_hash (MD5 of extraction output)**: Signals extraction result change
    * Differs from existing → update record (e.g., after prompt upgrade)
    * Matches existing → skip write (no change from parsing)
* **Force Reprocess Override**: Set `FORCE_REPROCESS=true` to bypass incremental detection
  * Use when: code changes, parser logic tweaks, manual re-extraction for debugging
  * Effect: all TILs processed (parse + LLM), existing records overwritten
* **Merge rule**: 
  * When matched_til_number found: update if content_hash differs OR incremental_skip_reason set
  * When not found: insert new record
* **run_id**: Audit column (refreshed on each pipeline run for trail), not part of uniqueness key
* **Source**: Volume PDF discovery is authoritative; no external SOT dependency
* **Result**: One row per til_number; true incremental efficiency (with override option)
* Status taxonomy: `PENDING` → `PROCESSING` → `COMPLETED` | `COMPLETED_INCREMENTAL_SKIP` | `FAILED`
* Audit fields: `source_file_path`, `pdf_file_hash`, `content_hash`, `incremental_skip_reason`

### Raw Response and MLflow Policy

To keep the Silver table lean and still preserve debugging capability:

* Do not store full raw LLM response for every row in the main table
* Keep raw responses selectively for failed or low-confidence extractions in a controlled audit location
* Use MLflow for run-level tracking only:
  * model name
  * prompt version
  * parameters
  * aggregate metrics
  * small representative artifacts

### Source Behavior Watch-list

These are not blockers for v1 implementation, but should be monitored:

* PDF volume discovery: Are PDFs added/removed/changed incrementally, or refreshed in full each run?
* Content hash stability: Can the same PDF produce different extraction outputs? (If yes, may need additional determinism controls.)
* Revision handling: If PDF names include revisions (e.g., 1234-R2), should revision updates create a new til_num or update existing? (Current approach: use extracted til_num as key, so revision is part of the document content.)

### Validation Gates

* Mandatory fields are present
* Field-level schema checks
* Quality status:

  * `pass`
  * `review`
  * `fail`

---

## Gold: Chunking, Embedding, and Retrieval-Ready Index

### Purpose

Create retrieval units for downstream AI workflows.

### Chunking Module

The chunking module should be replaceable.

```python
chunker.chunk(structured_output, strategy_config) -> chunks
```

### Supported Chunking Strategies

* Section-based
* Semantic
* Table-aware
* Formula-aware

### Embedding Module

The embedding module should be replaceable.

```python
embedder.embed(chunks, model_config) -> vectors
```

### Embedding Requirements

* Versioned model metadata
* Reproducibility of embeddings

### Gold Outputs: Delta

* Retrieval chunks
* Embeddings stored in the same table
* Strategy lineage
* Model lineage
* Quality fields
* Traceability fields for audit and reprocessing

---

# Design Principles for Flexibility and Scale

## Contract-First Modules

Parser, chunker, and embedder should sit behind stable interfaces.

## Configuration-Driven Behavior

Method selection should be controlled by configuration, not code forks.

## Version Everything

Track versions for:

* Parser
* Chunking strategy
* Embedding model

## Replay-Ready

Reprocess from Bronze when methods change.

## Incremental and Batch Support

Process only changed documents by hash or version.

## Observability by Layer

Track:

* Throughput
* Failures
* Quality rates
* Reprocess counts

---

# Pipeline Control and Orchestration

## High-Level Approach

Orchestrate as dependent, modular jobs with clear handoff contracts.

Use checkpointed incremental processing with backfill mode.

Fail downstream processing per document instead of hard-stopping the full batch.

Maintain run-level audit and validation findings for triage.

---

# Workflow and Jobs

## Job A: DLL Provision and Intake Setup

### Purpose

Provision or refresh required DLLs, parser dependencies, and runtime configs.

### Output

Runtime-ready environment and version-stamped dependency manifest.

---

## Job B: Bronze Ingestion

### Purpose

Consume raw TIL files and source metadata landed by the D&A team in a Databricks Volume.

### Ownership / Input

The upstream landing layer is owned by the D&A team.

This pipeline starts from the provided Databricks Volume.

### Output

Input discovery and selection for downstream processing.

---

## Job C: Silver Metadata Extraction

### Purpose

Run the parser adapter and extract normalized metadata.

### Output

Silver metadata, extraction lineage, and quality status.

---

## Job D: Gold Chunking and Embedding

### Purpose

Generate chunks and vectors using the selected strategy and model.

### Output

Gold chunk records with embedded vectors and version lineage.

---

## Job E: Validation and Quality Gates

### Purpose

Validate required outputs and quality thresholds across Silver and Gold.

### Output

Pass, review, or fail decisions and validation findings.

---

## Job F: Vector Index Sync Trigger

### Purpose

Trigger a sync of the Vector Search index against the Gold chunk table.

### Approach

Use a Databricks Vector Search Delta Sync index in self-managed-embeddings mode.

Job D writes the vectors. Delta Sync only propagates them.

### Implementation

Trigger sync at the end of the pipeline:

```http
POST /api/2.0/vector-search/indexes/{index}/sync
```

Also run a daily safety-net cron, mirroring the FSR `pw_sdg_fsr_vs_sync` pattern.

Sync trigger frequency must stay shorter than the source table’s:

```text
delta.deletedFileRetentionDuration
```

### Validation Gating

Only validated chunks are persisted to the source table, or written through a validated view.

This ensures that what syncs to the index is already approved.

### Output

Sync status is recorded in:

```text
til_pipeline_run_audit
```

---

# Execution Model

## Standard Flow

```text
A as needed -> B -> C -> D -> E -> F
```

## Reprocess Flow

```text
B optional -> C/D selected versions -> E -> F
```

Jobs are independently deployable so parser, chunker, and embedder changes do not require full pipeline rewrites.

The same jobs are reused for regular ingestion and backfill by switching run mode and input scope.

---

# Queuing and Status-Driven Processing

This is inspired by the FSR pattern.

Each row in the registry table carries explicit per-stage status columns.

Downstream jobs claim work by querying these statuses.

This avoids external queues and keeps the state of every document visible in Delta.

---

# Proposed Status Columns on `til_metadata`

```text
metadata_status: pending -> in_progress -> completed / failed

chunk_status: pending -> in_progress -> completed / failed
```

Additional operational fields:

* Per-stage retry counters

  * Example: `metadata_retry_count`
  * Example: `chunk_retry_count`
* Per-stage error fields
* Per-stage timestamp fields for audit

---

# Job-to-Status Mapping

## Job C: Silver Metadata Extraction

Drives:

```text
metadata_status
```

## Job D: Gold Chunking and Embedding

Drives:

```text
chunk_status
```

Claims rows where:

```sql
metadata_status = 'completed'
```

## Job E: Validation

Reads across statuses and writes to:

```text
til_validation_results
```

## Job F: Vector Index Sync Trigger

This is table-wide, not per-row.

No status column is needed.

Validation gating is enforced at write time before chunks land in the source table.

---

# Claim Behavior

Each downstream job:

1. Selects a bounded batch of rows in the eligible status.
2. Flips them to `in_progress` using a guarded update.
3. Processes them.
4. Transitions them to `completed` or `failed`.

At the start of each run, stale `in_progress` rows older than a configured threshold are reset to `pending` for crash recovery.

Bounded retry caps prevent terminal failures from blocking the queue forever.

---

# Why This Matters for TIL

* One job pattern works for both incremental and backfill.
* Same code can run with different work-set sizes.
* Failures are isolated per document, not per batch.
* Reprocessing is just a status reset on selected rows.
* No separate replay infrastructure is needed.
* Method version changes can flip affected rows back to `pending` for re-extraction or re-chunking.

---

# Jobs and Tables: Proposed Inventory

## Jobs

### `PW_SDG_TIL_DDL` — Table Provisioning

**Job:** A (Setup)
**Mode:** On-demand (run once or for schema updates)
**Execution:** Serverless compute
**Notebook:** `pw_sdg_ai_ser_repo/ddls/tils/nb_til_profile_ddl`

**Creates:**

* `silver_til_metadata` — Document registry with status tracking
* `silver_til_elements` — Optional elements table
* `gold_til_chunks` — Retrieval-ready chunks with embeddings
* `til_validation_results` — Quality findings
* `til_evaluation_results` — Method comparison metrics
* `til_pipeline_run_audit` — Run audit trail

**Properties:**

* Idempotent (`CREATE TABLE IF NOT EXISTS`)
* No destructive operations
* Delta properties: CDF enabled, autoOptimize, retention for Vector Search sync
* COMMENT clauses for field documentation

---

### `job_til_bronze_ingestion`

**Job:** B
**Modes:**

* Incremental
* Backfill

**Input:** D&A Databricks Volume landing path (specified in workflow as `TIL_SOURCE_VOLUME_PATHS`)

**Writes:**

* `til_pipeline_run_audit`

**Status:** Planned; currently folded into Job C discovery

---

### `PW_SDG_TIL_P1_Metadata` — Silver Metadata Extraction

**Job:** C (Process 1 Metadata Extraction)
**Modes:**

* Incremental (default)
* Specific TIL targeting via `TIL_TARGET_TIL_NUMBERS`
* Limited scope via `TIL_MAX_PDFS` (for testing)

**Runtime Parameters:**

* `TIL_SOURCE_VOLUME_PATHS` — Databricks Volume path(s) to scan for TIL PDFs
* `PARSER_METHOD` — Parser to use: `"foundation"`, `"pdfplumber"`, or `"auto"` (default)
* `TIL_TARGET_TIL_NUMBERS` — Optional; if set, process only specified TIL numbers (e.g., `"2342-R1,1509-R4"`). If empty, discover all.
* `TIL_MAX_PDFS` — Optional; limit discovery to N PDFs (for testing). Empty = no limit.
* `TIL_BATCH_SIZE` — Batch size for processing; default `10`
* `TIL_LLM_CONCURRENCY` — LLM API concurrency limit; default `2`
* `TIL_RETRY_MAX` — Max retries per document on failure; default `2`

**Writes:**

* `silver_til_metadata` — Document registry with status tracking
* `silver_til_elements` — Optional granular extraction elements
* `til_pipeline_run_audit` — Run-level audit log
* `til_evaluation_results` — Parser evaluation metrics (if eval mode requested)

**Execution:**

* Serverless compute (no persistent cluster)
* Runs notebook: `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_til_metadata`
* Implements Process 1 with pluggable parser adapters

---

### `job_til_gold_chunk_embed`

**Job:** D
**Modes:**

* Incremental
* Backfill

**Writes:**

* `gold_til_chunks`
* `til_pipeline_run_audit`

---

### `job_til_quality_validation`

**Job:** E
**Modes:**

* Incremental
* Backfill

**Writes:**

* `til_validation_results`
* `til_pipeline_run_audit`

---

### `job_til_vs_sync`

**Job:** F
**Modes:**

* Triggered at end of pipeline
* Daily safety-net cron

**Action:**

```http
POST /api/2.0/vector-search/indexes/{index}/sync
```

**Writes:**

* `til_pipeline_run_audit`

**Side Effect:**

Triggers Delta Sync of the configured Vector Search index against the Gold chunk table.

---

### `job_til_evaluation`

**Modes:**

* On-demand

**Writes:**

* `til_evaluation_results`
* `til_pipeline_run_audit`

---

# Implementation & Workflows

## Workflow Files

TIL pipeline workflows are defined in `pw_sdg_ai_ser_repo/workflows/tils/`:

### `pw_sdg_til_ddl.yml`

Job: `PW_SDG_TIL_DDL` (table provisioning)
- Task: Runs `nb_til_profile_ddl` notebook
- Compute: Serverless
- Environment: Parameterized via `jb_env`

### `pw_sdg_til_metadata.yml`

Job: `PW_SDG_TIL_P1_Metadata` (Process 1 — metadata extraction)
- Task: Runs `nb_sdg_til_metadata` notebook
- Compute: Serverless
- Parameters: See **Runtime Parameters** section above under Job C
- Queue: Enabled for job isolation

## Evaluator Framework

Process 1 includes a reusable evaluator framework for parser comparison:

### Core Classes

**`pw_sdg_ai_ser_repo/common/evaluators/parser_evaluator.py`**
- Generic `ParserEvaluator` class (implements `Evaluator` protocol)
- Computes 8 proxy metrics: char_count, word_count, required_field_hits, table_count, formula_hits, noise_ratio, latency_s, parse_success
- Supports gold label validation (optional field_exact_match)
- Configurable regex patterns for domain-specific signals

**`pw_sdg_ai_ser_repo/silver/src/tils/evaluators/parser_evaluator.py`**
- TIL-specific wrapper (subclass of generic)
- Preconfigured regex patterns for TIL fields and formulas
- Backward-compatible with existing evaluation notebooks

**`pw_sdg_ai_ser_repo/silver/src/tils/evaluators/til_parser_evaluator_config.py`**
- TIL_REQUIRED_FIELDS_RE: Regex for TIL field mentions (proxy signal)
- TIL_FORMULA_RE: Regex for formula/numeric expressions (proxy signal)
- Comments document intent: "Proxy signal only — directional metrics, not validators"

**`pw_sdg_ai_ser_repo/silver/src/tils/evaluators/eval_runner.py`**
- Thin orchestration layer (70 lines, no duplication)
- Functions:
  - `make_evaluation_run_id()` → f"parser_eval_{datetime_utc_YYYYMMDD_HHMMSS}"
  - `build_evaluation_cases(til_pdf_pairs, volume_path_prefix)` → list[EvaluationCase]
  - `run_method_comparison(cases, parser_methods, evaluation_run_id)` → list[dict]
- No PDF loading logic (caller handles via parser adapters)

## PDF Discovery

**`pw_sdg_ai_ser_repo/silver/src/tils/til_profile_extraction.py`**
- Function: `discover_tils(spark, volume_paths, skip_suffixes, max_results)` → Spark DataFrame
- Returns: til_number, volume_path, file_size_bytes, file_last_modified_ms
- Handles DBR version differences (modificationTime vs modification_time)
- Uses Spark SQL for scalability
- Function: `build_til_stub_schema()` → StructType for staging

**TIL Number Format:**
- Extracted from filenames using regex: `r"TIL\s+([\d\-R]+)"`
- Format: `NUMBER-REVISION` (e.g., `2342-R1`, `1509-R4`)
- Used in `TIL_TARGET_TIL_NUMBERS` parameter for targeting specific TILs

## Parser Options

**Three production parsers available:**

1. **Foundation** (HTTP service)
   - Calls GE Foundation PDF extraction endpoint
   - Returns structured text, tables, image descriptions
   - Production-ready for Databricks and local environments
   - Default for v1

2. **PDFPlumber** (Local library)
   - Pure Python library, works anywhere
   - Fast, good for text-heavy PDFs
   - Backup / comparison option

3. **Databricks AI** (Native, DBR only)
   - Databricks built-in `ai_parse_document()` function
   - Spark-native, returns VARIANT type
   - Requires Databricks DBR environment
   - Reference parser for comparison
   - See example: `TILs/analysis/til-analysis/test_parse_pdf.ipynb`

**Evaluation notebook supports all three for testing; v1 workflow uses foundation.**

## Configuration as Code

**`pw_sdg_ai_ser_repo/common/constants.py`**
- Centralized process and metric definitions
- `PROCESS_1`, `PROCESS_2` constants (replaces "Stage 0/1/2" nomenclature)
- `METRIC_GROUP_EXTRACTION`, `METRIC_GROUP_CHUNKING` enums
- Ensures consistency across evaluators, tables, and notebooks
- Single source of truth for process naming

## Two-Tier Identity

Each document in the pipeline carries two identity columns:

1. **`document_id`** — Technical surrogate primary key for pipeline row tracking
   - Auto-generated per ingestion
   - Used for status and retry tracking

2. **`unique_key`** — Content-based idempotency key
   - Derived from: `source_hash + til_number + stable attributes`
   - Enables multi-source deduplication
   - Prevents duplicate processing of same logical document

Upsert logic uses `unique_key` to detect duplicates; upsert operations use `document_id` as PK.

---

# Delta Tables

* `silver_til_metadata` — Document registry with status, metadata_status, chunk_status
* `silver_til_elements` — Optional elements table for granular extraction
* `gold_til_chunks` — Retrieval-ready chunks with embeddings
* `til_validation_results` — Quality findings and validation gates
* `til_evaluation_results` — Parser/chunker method comparison metrics
* `til_pipeline_run_audit` — Run-level audit trail and outcomes

---

# Note on `til_pipeline_run_audit`

Keep `til_pipeline_run_audit` for the first iteration to provide SQL-side join access to run-level outcomes alongside Silver, Gold, and validation tables.

Examples of run-level outcomes:

* Status
* Counts
* Timings

Most of this overlaps with what MLflow runs already capture per job execution.

Once MLflow coverage is validated in production and the team is comfortable using it, this table can be dropped or replaced with a Delta view over MLflow runs.

Per-document operational state stays on the Silver registry, including:

* `metadata_status`
* `chunk_status`
* Retry counters

MLflow is not a substitute for per-document operational state.

---

# Evaluation Framework

## Objective

Compare extraction and chunking methods using measurable quality and operational metrics on a shared gold dataset.

## Note

Metric weighting and go/no-go thresholds remain open and will be finalized after DS experiment review.

## Two-Process Evaluation Architecture

The TIL evaluation framework follows FSR naming conventions and isolates concerns by process:

**Process 1 (P1) — Metadata Extraction:**
- Parser: foundation, pdfplumber, auto → extract PDF content
- Profile: LLM normalization → produce ProfileJSON
- Evaluation: **Parser-only metrics** (char_count, table_count, field hits, noise ratio, latency) to select best parser
- Storage: `silver_til_metadata` table

**Process 2 (P2) — Chunking & Embedding:**
- Chunker: Split ProfileJSON into retrieval-ready chunks
- Embedder: Generate vectors for each chunk
- Evaluation: Chunking quality, embedding quality, retrieval relevance
- Storage: `gold_til_chunks` table

**Process 3 (App Layer) — Not in Pipeline Scope:**
- Template coverage, completion review, SBOM interpretation, disposition decisions

**Rationale for separation:**

* **P1 parser evaluation**: Isolates extraction quality from semantic interpretation. LLM normalization is *not* embedded in the parser, ensuring evaluation is deterministic and not confounded by LLM version changes. Enables fair comparison: "which extraction method is fundamentally better?"

* **P1 profile extraction**: Separate from app logic. Can upgrade LLM or change profile schema without re-running parser evaluation.

* **P2 chunking+embedding**: Combined into one process (like FSR) because chunking and embedding are tightly coupled. Evaluate them together on retrieval metrics.

* **App layer**: Business logic kept separate so disposition rules can iterate independently of pipeline code.

## Parser-Only Evaluation (P1 Pre-Flight Check)

Parser evaluation is a required gate before running P2 chunking and embedding.

Purpose:

* Compare parser methods directly on extraction fidelity.
* Eliminate weak parsers before downstream experiments.
* Keep P2 comparisons focused on viable parser outputs.

Implementation approach:

* Generic `ParserEvaluator` class (see **Implementation & Workflows** section) computes domain-specific metrics.
* TIL-specific regex patterns (til_parser_evaluator_config.py) define proxy signals for required fields and formulas.
* Thin orchestration layer (eval_runner.py) handles case building and comparison running.
* MLflow is used to track parser evaluation runs, parameters, and aggregate metrics.
* A Delta table (`til_evaluation_results`) stores per-document results for SQL analysis and dashboards.

P1 parser evaluation inputs:

* Fixed representative gold dataset of TIL PDFs (discovered via discover_tils).
* Gold labels for key fields, required sections, table expectations, and formula expectations (optional).
* Parser method and version under test (foundation, pdfplumber, or auto).

Process 1 (P1) outputs:

* Parser run summary metrics (8 proxy signals + optional gold labels).
* Per-document parser results and error taxonomy.
* Pass/fail decision against minimum parser thresholds.
* Audit trail in `til_evaluation_results` table (queryable for deep analysis).

Stage-gate policy:

* Process 1 (P1): parser must pass minimum thresholds.
* Process 2+ (P2, app layer): only P1 pass parsers proceed to chunking/embedding/retrieval evaluation.

**Usage Example:**

```python
from pw_sdg_ai_ser_repo.silver.src.tils.evaluators.parser_evaluator import ParserEvaluator
from pw_sdg_ai_ser_repo.silver.src.tils.evaluators.eval_runner import run_method_comparison

evaluator = ParserEvaluator()
cases = build_evaluation_cases(til_pdf_pairs, volume_prefix)
results = run_method_comparison(cases, ["foundation", "pdfplumber"], "parser_eval_20260622_120000")
```

**Process 1 Metrics (8 Proxy Signals + Optional Gold Labels):**

**Always Computed (No Gold Labels Required):**
1. `char_count` — Total character count in extracted text
2. `word_count` — Total word count
3. `table_count` — Number of tables detected
4. `formula_hits` — Count of formula/numeric expressions (via TIL_FORMULA_RE)
5. `noise_ratio` — Ratio of suspected noise/boilerplate text
6. `latency_s` — Parser execution time (seconds)
7. `parse_success` — Boolean: extraction succeeded

**Optional (Requires Gold Labels):**
8. `field_exact_match` — Percentage of required fields matching gold labels exactly

**Additional Domain Metrics (when gold labels available):**
* Required-field completeness rate
* Text completeness and noise metrics (section recall/precision)
* Table extraction fidelity (headers, row/column coverage, cell correctness)
* Formula extraction fidelity (expression and numeric token correctness)
* Traceability quality (page/element references)

**Evaluation Logging Pattern:**

* MLflow run per parser method and dataset slice (via `make_evaluation_run_id()`)
* Log parser name/version and dataset slice as MLflow parameters
* Log 8 proxy metrics and optional gold labels as MLflow metrics
* Log mismatch/error samples as MLflow artifacts
* Persist one row per document per parser in `til_evaluation_results` table for SQL-based deep analysis
* Link run to `til_pipeline_run_audit` via `evaluation_run_id`

## Proposed Metric Groups

## 1. Metadata Extraction Accuracy

* Field-level exact match for key TIL attributes, for example:

  * `til_number`
  * `revision`
  * `compliance_category`
  * `timing_code`
  * `issue_date`
* Aggregate as exact-match percentage across required fields.

## 2. Text Quality and Completeness

* Recall against gold text for required sections.
* Precision to quantify non-relevant capture, including repeated legal or disclaimer text.

## 3. Table Extraction Fidelity

* Header match rate.
* Row/column coverage rate.
* Cell value correctness rate.

## 4. Formula Extraction Fidelity

* Normalized expression match rate.
* Numeric token correctness for coefficients, thresholds, and constants.
* Operator/structure preservation checks.

## 5. Traceability and Provenance Quality

* Percentage of extracted outputs with valid page and element references.
* Reference consistency across Silver and Gold outputs.

## 6. Chunking Quality for Downstream Retrieval

* Chunk boundary quality, including:

  * Section alignment
  * Table-aware boundaries
* Context retention checks:

  * Does the chunk preserve enough meaning for applicability decisions?

## 7. Operational Reliability and Cost

* Per-document latency.
* Failure/retry rate.
* Unit cost indicators, kept method-agnostic at this stage.

---

# Evaluation Process

## High-Level Process

* Build and maintain a representative gold set across TIL types:

  * Narrative-heavy
  * Table-heavy
  * Formula-heavy
  * Image-heavy
* Run each candidate method on the same dataset.
* Record results in a comparable evaluation log.
* Review objective metrics first.
* Finalize weighting and threshold policy with DS input.

---

# Evaluation Storage and Analysis

## Storage

Store evaluation outputs in a dedicated Delta table:

```text
til_evaluation_results
```

## Recommended Grain

One row per evaluation run, per document, per method.

The table can include either:

* Explicit metric columns, or
* A metric map that can evolve over time

## Minimum Tracking Fields

* `evaluation_run_id`
* `method_name`
* `method_version`
* `dataset_slice`
* `document_id`
* Metric results
* `evaluator_version`
* `run_ts`

## Analysis Options

Analysis can be done through:

* SQL queries
* Comparison notebooks
* Dashboards

Useful slices include:

* Method
* Document type
* Metric group

This is the equivalent of the useful part of FSR’s operational logging pattern, but applied to method comparison rather than ingestion operations.

---

# MLflow Tracking

## Pipeline Hygiene

Treat each pipeline job execution as an MLflow run so parameters, versions, and metrics are captured uniformly.

## Jobs That Log to MLflow

The following jobs log to MLflow:

* Job C: Metadata extraction
* Job D: Chunking and embedding
* Job F: Vector Search sync trigger
* Evaluation job

## Logged Per Run

### Parameters

* `parser_version`
* `chunker_version`
* `chunker_strategy`
* `embedding_model`
* `embedding_model_version`
* `run_mode`
* `input_scope`

### Metrics

* Per-job document counts
* Success counts
* Failure counts
* Latency
* Retry counts
* For evaluation runs, the metric groups defined above

### Tags

* `til_pipeline_run_id`
* `job_name`
* `environment`

The `til_pipeline_run_id` links the MLflow run to:

```text
til_pipeline_run_audit
```

### Artifacts

Selective artifacts can include:

* Sample inputs
* Sample outputs
* Evaluation summary tables

## Why It Matters

* Gives lineage from a set of chunks or evaluation scores back to the exact method versions that produced them.
* Makes method comparisons reviewable in the MLflow UI alongside the Delta-backed `til_evaluation_results` table.
* Removes the “what version produced this output?” gap that the FSR pipeline currently has.

## Scope Note

Delta tables remain the source of truth for pipeline state and evaluation results.

MLflow is the observability and lineage layer.

---

# Model Serving

## Deferred Scope

Future option: wrap the TIL retrieval and answer flow as an MLflow PyFunc, register it to Unity Catalog, and expose it through a Databricks Model Serving endpoint.

Example flow:

```text
Vector Search query -> context assembly -> LLM call
```

This is not in scope for v1.

The decision to deploy is driven by consumer requirements, including:

* Who calls it
* Expected QPS
* Auth boundaries

This will be revisited once those requirements are clear.

The PyFunc wrapper itself is small and additive. The current design does not need to change to enable this later.

---

# Inference Tables

When the serving endpoint is enabled, turn on Databricks Inference Tables on the same endpoint config.

Inference Tables auto-capture request payloads and model responses into a Delta table for query-time observability without custom logging code.

This is the serving-side counterpart to MLflow tracking on the batch side.

---

# Guardrails

Guardrails are part of the serving surface, not the batch pipeline.

Plan for four categories.

## 1. Safety

Purpose: detect harmful or toxic content.

Preferred approach:

* Use the built-in Databricks AI Guardrails safety filter at the endpoint.

## 2. Security

Purpose: defend against prompt injection and data leakage.

Approach:

* Use a pre-call classifier, for example Llama Guard.
* Maintain strict separation of:

  * System prompt
  * User input

## 3. Contextual

Purpose: restrict answers to approved topics and sources.

Approach:

* System prompt constraints
* Retrieval filter on approved TIL content

## 4. Compliance

Purpose: support regulatory and legal controls.

Approach:

* PII redaction on input and output
* Policy-specific judges

The policy-specific judges can also run continuously in evaluation as a regression check.

## Implementation Pattern

Use a `GuardedGenerator` decorator around the LLM call to compose input and output guardrails.

The contract should live in the shared skeleton so the same approach is reusable across pipelines.

Example contracts:

```python
InputGuardrail
OutputGuardrail
```

---

# Minimum Proposed Fields

## Evolvable Field Set

### Identity and Lineage

* `document_id`
* `source_path`
* `source_hash`
* `ingest_ts`
* `run_id`
* `method_version`

### Uniqueness Control

* `unique_key`

Derived from:

```text
source_hash + selected source attributes
```

### Metadata Core

* `til_number`
* `revision`
* `compliance_category`
* `timing_code`
* `issue_date`
* `title`

### Structure Signals

* `section_markers`
* `table_present`
* `figure_present`
* `formula_present`
* `page_refs`

### Chunk and Vector

* `chunk_id`
* `chunk_text`
* `chunk_type`
* `section_path`
* `page_span`
* `embedding_vector`

### Quality and Control

* `validation_status`
* `confidence_or_quality_score`
* `error_code`
* `processed_ts`

---

# Open Items for Part 2 Deep Dive

* Final metadata schema for TIL applicability decisions.
* Chunking strategy benchmarks from DS experiments.
* Quality score thresholds and human-review triggers.
* Cost and latency SLOs for production.
* **LLM model selection for profile extraction.** First end-to-end run was
  blocked twice by gateway/model issues:
  1. The dev `LITELLM_API_KEY` allow-list does not include
     `databricks-gpt-oss-20b` (the original DS-team default), so the call
     returned 401 `key_model_access_denied`.
  2. We tried `azure-gpt-5-mini` (closest GPT-family lineage to the
     original gpt-oss-20b). It is a **reasoning model** — it silently
     consumed the entire `max_tokens=4000` budget on hidden chain-of-thought
     (`reasoning_tokens: 4000`) and returned empty `content` with
     `finish_reason: length`. The DS-team's original choice (gpt-oss-20b)
     is a plain non-reasoning chat model, so the GPT-5 family is not a
     behavioral match.
  Adopted default: **`gemini-3-flash`** — matches FSR (already proven
  on the same gateway), and is a non-reasoning chat model (behaviorally
  closer to gpt-oss-20b than the GPT-5 reasoning family).
  Open questions:
  * Confirm with DS whether `gemini-3-flash` is acceptable, or whether
    they want to bake-off other allowed non-reasoning options
    (`bedrock-claude-sonnet-4.6`, `bedrock-claude-opus-4.6`).
  * Request gateway access for `databricks-gpt-oss-20b` if DS wants to
    keep that as the canonical model — needs the LiteLLM admin to add it
    to the key's allow-list.
  * If GPT-5 family is ever revisited, raise `max_tokens` to ~16000 and
    set `reasoning_effort: "minimal"` to leave budget for actual output.
  * Run a small bake-off (e.g., 10 representative TILs) comparing
    `gemini-3-flash` vs `bedrock-claude-sonnet-4.6` on profile
    completeness, field accuracy, latency, and cost — feed results back
    into this decision.
* **TIL number extraction — varied formats and first-page fallback.** The
  current implementation derives `til_number` from the filename using
  `r"TIL\s+([\d\-R]+)"` (e.g., `TIL 2342-R1`). Observed filenames do not
  always follow this convention — variants include differing separators,
  missing/extra spacing, alternate revision markers, and entirely
  non-conforming names — so a filename-only strategy silently drops or
  mislabels real TILs. Open questions:
  * Catalogue the actual TIL-number formats present in the source volume(s)
    and decide whether the regex should be broadened, replaced with a small
    set of patterns, or dropped in favor of content-based extraction.
  * Add a **first-page text fallback**: when the filename regex misses, read
    the first page of the PDF and extract the TIL number from the document
    header/title block. This needs alignment with DS on prompt/parser usage
    so the filename-derived value and the first-page-derived value can be
    cross-checked (and disagreement logged to `til_validation_results`).
  * Decide the source-of-truth precedence (filename vs. first page vs. LLM
    profile) and document it in the metadata contract.

---

# Chunk Size, Context Window, and Model Size

## 1. Chunk Size

Chunk size refers to the size of individual pieces of data, such as documents or document sections, fed into the model.

It is often measured in tokens.

In this example, documents are chunked to a maximum size of:

```text
512 tokens
```

## 2. Relationship to Context Window

The context window is the maximum number of tokens the model can process at once.

If the chunk size is smaller than or equal to the context window, the entire chunk can be processed in a single inference.

If the chunk is larger than the context window, it must be split into smaller parts or processed in multiple passes.

### Example

If the context window is 512 tokens and the chunk size is 512 tokens, the entire chunk fits within a single inference.

If the chunk size is 1024 tokens but the model’s context window is 512 tokens, the chunk must be split into two parts.

## 3. Relation to Model Size and Dimensional Length

Model size and dimensional length, such as embedding dimensions, determine computational complexity and memory requirements.

Larger dimensional length, for example 1536 dimensions versus 384 dimensions, means more values per embedding vector and higher storage/computation cost.

Chunk size also impacts processing cost.

Larger chunks closer to the context window size consume more compute per request.

Smaller chunks are cheaper and faster to process individually, but may require more operations because there are more chunks.

## 4. Summary

| Concept                           | Relationship                                                                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Chunk Size                        | Size of data fed into the model. It should usually be less than or equal to the context window for efficient processing.            |
| Context Window                    | Maximum number of tokens a model can process at once. It determines how much of the chunk can be processed in a single pass.        |
| Model Size and Dimensional Length | Affect per-token and per-vector processing cost. Larger models and larger embedding dimensions are more expensive to run and store. |

## Conclusion

Chunk size should ideally match or stay below the context window to maximize efficiency.

Larger embeddings or larger model size increase per-token and per-vector cost, so balancing chunk size and model configuration is important for low-cost, low-latency applications.

---

# Delta Table Schemas (Proposed v1)

This section provides the concrete Delta table schema proposals for v1.

Ownership note:

* The schemas in this section are for the data pipeline boundary only (Bronze to Silver to Gold, index sync support, and observability).
* App-layer decisioning outputs are intentionally excluded from core pipeline tables.

These schemas align with:

* DS E6.2 profile extraction contract
* E6.6 method evaluation and run observability needs

Pipeline-owned table set (v1):

* `silver_til_metadata`
* `silver_til_elements` (optional)
* `gold_til_chunks`
* `til_validation_results`
* `til_evaluation_results`
* `til_pipeline_run_audit`

App-owned table set (out of core pipeline scope):

* Template coverage outcomes and routing decisions
* Service-history evidence retrieval outputs and completion review outputs
* SBOM decision-support outputs
* Final disposition and user-facing explainability/workflow outputs

If the app team wants SQL persistence for those app-owned outputs, define them in app storage contracts separately from this pipeline schema section.

## 1. `silver_til_metadata`

Purpose:

* Registry and profile extraction output per TIL document.
* Queue-driving status fields for metadata and chunk stages.

Proposed columns:

* `document_id` STRING NOT NULL
* `unique_key` STRING NOT NULL
* `source_path` STRING
* `source_hash` STRING
* `source_system` STRING
* `requested_til_number` STRING
* `matched_til_number` STRING
* `match_type` STRING
* `parser_method` STRING
* `parser_name` STRING
* `parser_version` STRING
* `profile_found` BOOLEAN
* `parsed_profile_json` STRING
* `raw_profile_json` STRING
* `extracted_document_method` STRING
* `extracted_text_char_count` BIGINT
* `extracted_table_count` INT
* `extraction_confidence` DOUBLE
* `metadata_status` STRING
* `metadata_retry_count` INT
* `chunk_status` STRING
* `chunk_retry_count` INT
* `error_code` STRING
* `error_message` STRING
* `ingest_ts` TIMESTAMP
* `metadata_processed_ts` TIMESTAMP
* `chunk_processed_ts` TIMESTAMP
* `run_id` STRING

Notes:

* DS contract fields such as `profile_response.json` map to `parsed_profile_json` and `raw_profile_json`.
* `requested_til_number`, `matched_til_number`, and `match_type` preserve the exact/base revision resolution behavior.

## 2. `silver_til_elements` (optional)

Purpose:

* Optional normalized extraction elements for traceability and audits.

Proposed columns:

* `document_id` STRING NOT NULL
* `element_id` STRING NOT NULL
* `element_type` STRING
* `element_text` STRING
* `page_number` INT
* `bbox_json` STRING
* `section_path` STRING
* `source_method` STRING
* `parser_version` STRING
* `run_id` STRING
* `processed_ts` TIMESTAMP

## 3. `gold_til_chunks`

Purpose:

* Retrieval-ready chunks and embeddings.
* Source table for Vector Search Delta Sync index.

Proposed columns:

* `chunk_id` STRING NOT NULL
* `document_id` STRING NOT NULL
* `chunk_text` STRING
* `chunk_type` STRING
* `section_path` STRING
* `page_span` STRING
* `chunk_index` INT
* `chunker_name` STRING
* `chunker_version` STRING
* `chunker_strategy` STRING
* `embedding_model` STRING
* `embedding_model_version` STRING
* `embedding_vector` ARRAY<DOUBLE>
* `validation_status` STRING
* `source_path` STRING
* `source_hash` STRING
* `run_id` STRING
* `processed_ts` TIMESTAMP

## 4. `til_validation_results`

Purpose:

* Validation and quality findings per document/rule.

Proposed columns:

* `validation_run_id` STRING NOT NULL
* `document_id` STRING NOT NULL
* `rule_name` STRING
* `rule_category` STRING
* `status` STRING
* `severity` STRING
* `metric_name` STRING
* `metric_value` DOUBLE
* `threshold_value` DOUBLE
* `detail_json` STRING
* `run_id` STRING
* `validated_ts` TIMESTAMP

## 5. `til_evaluation_results`

Purpose:

* Method-comparison results across parser/chunker/embedder/evaluation runs.

Proposed columns:

* `evaluation_run_id` STRING NOT NULL
* `dataset_slice` STRING
* `document_id` STRING NOT NULL
* `stage_name` STRING
* `method_name` STRING
* `method_version` STRING
* `metric_group` STRING
* `metric_name` STRING
* `metric_value` DOUBLE
* `metric_detail_json` STRING
* `evaluator_version` STRING
* `mlflow_run_id` STRING
* `run_ts` TIMESTAMP

Notes:

* Use `stage_name='process_1'` for Process 1 (P1) parser evaluation.
* Keep one row per metric for flexible slicing and dashboarding.

## 6. `til_pipeline_run_audit` (first iteration)

Purpose:

* SQL-joinable run-level outcomes per job.

Proposed columns:

* `pipeline_run_id` STRING NOT NULL
* `job_name` STRING NOT NULL
* `run_mode` STRING
* `input_scope` STRING
* `status` STRING
* `claimed_count` INT
* `success_count` INT
* `failed_count` INT
* `skipped_count` INT
* `retry_count` INT
* `error_code` STRING
* `error_message` STRING
* `mlflow_run_id` STRING
* `start_ts` TIMESTAMP
* `end_ts` TIMESTAMP
* `duration_ms` BIGINT

---

## Keys and Constraints (Recommended)

* `silver_til_metadata`: unique(`unique_key`)
* `silver_til_elements`: unique(`document_id`, `element_id`)
* `gold_til_chunks`: unique(`chunk_id`)
* `til_validation_results`: unique(`validation_run_id`, `document_id`, `rule_name`)
* `til_evaluation_results`: unique(`evaluation_run_id`, `document_id`, `stage_name`, `method_name`, `metric_name`)
* `til_pipeline_run_audit`: unique(`pipeline_run_id`, `job_name`)

Partitioning hint (v1):

* Prefer partitioning by date (`to_date(processed_ts)` or `to_date(run_ts)`) where table volume is high.
* Avoid over-partitioning by high-cardinality IDs.

---

## Key Strategy and Incremental MERGE Rules

This section defines identity, dedupe, and update behavior for incremental ingestion.

### Why this is needed

In FSR-like patterns, the same PDF can appear in multiple source volumes. Upstream teams can also add or change source locations over time. Identity rules must therefore be source-location resilient.

### Current DS reference behavior

DS Step 6 extraction currently uses one configured Databricks volume path (`TIL_VOLUME_PATH`) plus local sample and SQL fallback paths. It does not define a production multi-volume source-of-truth policy yet.

### Identity fields

* `document_id`: technical stable row identifier for the pipeline table row.
* `unique_key`: idempotency key used for dedupe and MERGE matching.
* `source_hash`: content hash of PDF bytes.

Recommended v1 rule:

* Keep `document_id` as a surrogate technical ID.
* Enforce uniqueness on `unique_key`.
* Build `unique_key` from content-first identity to avoid duplicate rows when the same PDF exists in multiple volumes.

Recommended `unique_key` input components:

* normalized TIL number (or base+revision if available)
* `source_hash`
* selected stable source attributes (optional, low-cardinality)

Do not include raw source path as a mandatory identity component in `unique_key`, otherwise the same PDF in two volumes becomes two logical documents.

### Source-location handling

Store source-location metadata separately from identity:

* `source_path`
* `source_system`
* `source_priority`
* `first_seen_ts`
* `last_seen_ts`

If one logical document (`unique_key`) is seen in multiple locations, keep one active primary source based on priority and record alternates in metadata/history.

### Incremental MERGE rules (v1)

MERGE match key:

* `ON tgt.unique_key = src.unique_key`

Behavior:

1. **When matched and `source_hash` unchanged**
  * Update freshness fields only (`last_seen_ts`, source metadata as needed).
  * Do not reset `metadata_status` or `chunk_status`.

2. **When matched and `source_hash` changed**
  * Update source/hash fields.
  * Reset processing statuses to pending (`metadata_status='pending'`, `chunk_status='pending'`).
  * Clear prior stage errors and increment version/change marker.

3. **When not matched**
  * Insert new row with pending statuses and initial lineage fields.

### Practical implications

* `document_id` should not be the only idempotency key.
* `unique_key` should drive incremental logic.
* This avoids duplicate processing when source locations change, and still supports reprocessing when file content changes.
