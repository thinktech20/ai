# Session State — SDG Use Case

> This is a historical operating log captured before the workspace was reorganized. Paths below have been updated where straightforward, but older narrative context is preserved.

> Read this first when resuming work. Update at end of every session.

---

## Update: 2026-04-24

### P1 Metadata Extraction — COMPLETE

- `process-1-metadata-extraction-backfill` workflow completed:
  - DDL: succeeded (40s)
  - metadata_extraction: succeeded (1h 43m)
  - validate: failed (expected during active backfill — see below)
- Final P1 numbers: **17,033 metadata completed**, 830 terminal failures (corrupt PDFs: `No /Root object!`)
- 0 pending — P1 is fully drained

### P2 Chunking/Embedding — Active

- `chunking_embedding_job` still running, draining the queue
- **10,492 / 17,863 fully completed (58.7%)**
- 591,215 chunks across 10,444 docs (avg 56.6/doc)
- 6,490 docs still awaiting P2 processing
- ETA: ~17 hours at current ~387 docs/hour

### Retry Cap Shipped (commit `5ff2665`)

- Problem: 5 doc IDs kept failing and cycling every batch (2 corrupt PDFs, 3 embedding coverage failures)
- Fix: added `chunk_retry_count` column + `P2_MAX_RETRIES=3` config
- Claim query now filters `COALESCE(chunk_retry_count, 0) < P2_MAX_RETRIES`
- On failure: increment count. On success: reset to 0.
- `ALTER TABLE` applied to live table. Code activates on next P2 job restart.
- DDL notebook handles schema evolution for new/existing tables (commit `f5740ab`)

### Validation Warnings Downgraded (commit `3fc636c`) #BACKFILL

- Checks 3.4 (stale pending chunks) and 5.2 (in_progress claims) downgraded from `check()` to `warn()` during backfill
- These are expected conditions when P2 lags behind P1
- Tagged `#BACKFILL` for easy revert post-backfill

### Validation Results (latest run)

- 32/39 passed, 7 failed, 2 warnings
- Remaining failures are pre-existing DQ issues:
  - 1.7: 30 missing titles
  - 1.8: bad date formats (2+4+9 docs)
  - 3.5: 74 missing pdf_name
- Next run should show green (3.4 + 5.2 now warnings)

### Earlier Today

- Fixed partial ingestion bug root cause (commit `a25912b`) — success/failure computed before row assembly
- Added per-document DQ logging to validation (commit `1e5601a`)
- Reorganized validation notebooks: pulse check vs data correctness, all cells use `display()` for downloadable CSV
- Backfill tracker + design doc updated

### Active Jobs

| Job | Role | Status |
|-----|------|--------|
| `process-1-metadata-extraction-backfill` | P1 metadata | **completed** |
| `chunking_embedding_job` | P2 chunk/embed | **active** — draining queue |

### Next Steps

- Monitor P2 until backfill completes (~17 hours remaining)
- After backfill: revert `#BACKFILL` code (search codebase), re-enable checks 3.4 + 5.2
- Investigate pre-existing DQ: 30 missing titles, 74 missing pdf_name, bad date formats
- Build lightweight test app for independent chunk/embed/VS validation
- Open PR for `feature/fsr-pipelines` → `main`

---

## Update: 2026-04-21

### Schema Update (Pranesh Confluence Spec)

- Applied Pranesh's schema changes across all 5 pipeline files per Confluence spec:
  - Metadata DDL: `equipment_code` → `equipment_class_code`, `project_id` → `xxx_project_id`, added `outage_type`, `technology_type`, `document_summary`, `chunked_at`; removed `metadata_retry_count`, `metadata_version`, `updated_at`
  - Chunk DDL: restructured to `chunk_id`, `pdf_name` (NOT NULL), `page_number`, `chunk_text`, `esn`, `report_date` (DATE), `chunk_embedding`, `metadata` (JSON blob), `created_at`
  - Reference tables now point to `vgpp` (production catalog), added `PSOT_TABLE` for outage/technology enrichment
  - P1 retry cap: pending query split into pending (all) + failed (LIMIT P1_MAX_RETRIES)
  - `document_summary = NULL` placeholder in success MERGE (blocked on Tao discussion re: large files)
- Commits: `6bab254` (initial copy), `17cccf3` (schema update), `9064b81` (chunk_size fix), `58f9439` (pdf_name fix v1), `a71f712` (pdf_name fix v2 — keep_cols), `9215e62` (schema alignment checks)

### End-to-End Test Job

- Created Databricks job **"PW SDG FSR Ingestion -TEST"** with 4 tasks: `ddl → metadata_extraction → chunk_ingestion → validate`
- All tasks point to Databricks Repos (user folder), branch `feature/fsr-pipelines`
- Job base parameters isolate writes to test tables:
  - `FSR_METADATA_TABLE` = `main.gp_services_sdg_poc.fsr_metadata_registry_test`
  - `FSR_CHUNK_TABLE` = `main.gp_services_sdg_poc.fsr_chunks_test`
  - `FSR_VS_INDEX` = `main.gp_services_sdg_poc.vs_fsr_chunks_test`
  - `FORCE_RESET` = `true`
  - `FSR_TARGET_PDF_NAMES` = 7 UUIDs (one per ESN: 290T543, 290T762, 337X369, 337X709, 338X408, 338X425, 338X713)

### Test Run Results (Run 1)

- DDL: passed
- Metadata extraction: passed (7/7 completed)
- Chunk ingestion: failed — `KeyError: 'chunk_size'` in log line (schema update removed `chunk_size` from chunk dict)
  - Fixed: `c['chunk_size']` → `len(c['chunk_text'])` (commit `9064b81`)

### Test Run Results (Run 2)

- DDL: passed
- Metadata extraction: passed
- Chunk ingestion: passed (1125 chunks across 7 documents)
- Validation: 31/32 passed, 1 failed — `3.5 Completed docs have pdf_name derived` (7/7 null)
  - Root cause: `success_records` dict missing `volume_path`, causing derivation SQL to fail silently (caught by try/except), fallback also couldn't find `volume_path`
  - Fixed: added `volume_path` to success_records (commit `58f9439`)

### Test Run Results (Run 3)

- DDL: passed
- Metadata extraction: passed
- Chunk ingestion: passed
- Validation: 31/32 passed, 1 failed — same `3.5 pdf_name null`
  - Root cause: enrichment step rebuilds `success_records` from Spark DataFrame using `keep_cols` list, which didn't include `volume_path`. Previous fix only added it to the pre-enrichment dict.
  - Fixed: added `"volume_path"` to `keep_cols` (commit `a71f712`)

### Test Run Results (Run 4) — PASSED

- DDL: passed
- Metadata extraction: passed (7/7 completed)
- Chunk ingestion: passed (1125 chunks across 7 documents)
- Validation: **32/32 passed**
- All checks green — pipeline is end-to-end functional

### Test Run Results (Run 5) — validate only, schema alignment checks

- Added 3 new checks (4.1 enrichment score, 4.2 metadata JSON keys, 4.3 report_date) — commit `9215e62`
- Validation: **35/35 passed**
- Enrichment and Pranesh schema alignment confirmed

### Environment Safety Note

- There is not a clean DEV / QA / UAT separation in the current Databricks workspace setup.
- Be very cautious with any existing shared tables or Vector Search indexes because some are actively used for UAT.
- Do not use UAT-backed objects as throwaway test targets.
- For FSR validation work, do not touch:
  - `main.gp_services_sdg_poc.field_service_report_gt_litellm`
  - `main.gp_services_sdg_poc.vs_field_service_report_gt_litellm`
- Prefer isolated `*_test` objects for pipeline reruns, schema resets, and targeted PDF validation.

### Team Repo Integration

- Team shared `pw_sdg_ai_ser_repo` (GEV-SoX-DataBricks org on GitHub Enterprise).
- Created branch `feature/fsr-pipelines` from `main`.
- Copied all 5 FSR pipeline notebooks into the team repo structure:
  - `Common/fsr_config.py` — shared config, secrets, table names, chunking params
  - `silver/src/ddl/nb_sdg_fsr_ddl.py` — CREATE TABLE for metadata + chunk tables
  - `silver/src/etl/nb_sdg_fsr_metadata.py` — Process 1: metadata extraction
  - `gold/src/etl/nb_sdg_fsr_chunks.py` — Process 2: chunking + embedding + VS sync
  - `silver/src/validation/nb_sdg_fsr_validate.py` — post-run validation checks
- Updated all `%run` paths to `../../../Common/fsr_config` to match team folder structure.
- Pushed branch to remote successfully.
- Workflow YAMLs NOT copied — Databricks team likely manages those in a separate repo (confirmed by EHS team pattern in existing `silver/src/workflows/` YAML).

### Databricks Repos Setup

- Existing repo `ai_pw_fsr_dbr` in `Repos > Power` was on branch `bigswingAI_19FEB2026/chaithra`, owned by Shivam Sharma.
- That repo required Git credentials (PAT) — Databricks Repos does not support SSH auth.
- Could not add `pw_sdg_ai_ser_repo` under `Repos > Power` — missing `Manage` permissions on that folder.
- Created the repo under own user Repos folder instead — works fine.
- PAT generation needed from `https://github.apps.gevernova.net/settings/tokens` (token with `repo` scope).

### Next Steps

- Open PR for `feature/fsr-pipelines` → `main` on `pw_sdg_ai_ser_repo`
- Confirm with Databricks team which repo holds workflow YAMLs for job definitions
- Resolve `document_summary` placeholder (blocked on Tao — large file handling)
- Move Repos from user folder to `Repos > Power` once Manage permissions are granted
- Scale test: run on larger document set (50+) to stress-test LLM batching / VS sync

---

## Update: 2026-04-17

### Databricks Workflow Progress

- Created and ran a safe Databricks workflow test in the AI Dev workspace using a print-only notebook under the user's workspace folder.
- Verified both a single-task job and a two-task dependency flow in the Databricks UI.
- Created test-only Databricks workflow YAML at `implementation/fsr-processing/workflows/pw_sdg_fsr_ingestion_test.yml`.
- Created matching Airflow trigger YAML at `implementation/fsr-processing/workflows/airflow_pw_sdg_fsr_ingestion_test.yml`.
- Kept the test setup isolated from existing FSR tables, volumes, and production notebooks.

### Local Deployment Attempt

- Installed Databricks CLI locally into `$HOME/bin` after the standard installer failed on permissions and corporate TLS.
- PAT-based CLI profile setup succeeded only with `skip_verify = true`.
- Local CLI access is still blocked by workspace/network policy with:
  `Unauthorized network access to workspace: 7474648066331722`

### Current Practical Status

- UI workflow validation is done.
- Databricks workflow YAML and Airflow YAML are ready.
- Local bundle deployment from VS Code is not unblocked yet.
- Next external input needed: AWS account / MWAA environment, Airflow repo/path, and Databricks Airflow trigger connection details.

---

## Last Active: 2026-04-10

---

### Where We Are Right Now

**Tao call is TODAY (2026-04-10)** — summary docs were originally created and prepped for the meeting.

**What was done this session:**
1. Created the summary doc set now located in `internal/summaries/` for Tao review
2. Docs are neutral tone — no person names, placeholders where decisions needed
3. User confirmed: **Track B (query service) is already implemented** — only minor modifications needed based on gap decisions

**Summary folder structure:**
```
internal/summaries/
  README.md                   ← index
  01-poc-assessment.md        ← current state + our understanding of the POC
  02-gaps-and-risks.md        ← 9 gaps (5 from Apr-7 discussion, 4 from DS pipeline review)
  03-proposed-architecture.md ← two-track design; Track B marked as existing, Track A TBD
  04-open-questions.md        ← 10 open questions with decision owners (by role, not name)
  05-roadmap.md               ← 4 phases; Phase 3 = query service updates only, not a build
```

---

### Next Actions (in priority order)

1. ⭐ **Tao call today** — walk through the overview folder; get feedback on structure + content
   - Key asks: Q1 (hosting), Q2 (embedding model), Q3 (reranking), Q4 (doc type classification), Q5 (ingestion ownership)
   - After call: update docs with decisions, close ADRs where possible

2. **Post to Confluence** — `internal/summaries/02-gaps-and-risks.md` is the right doc to post; pending go-ahead from today's call

3. **Connect with Databricks architect team** — need intro; bring gaps + open questions as agenda

4. **Build working notebook** — end-to-end `query_fsr` pipeline against `main.gp_services_sdg_poc`; start from `query_fsr_with_metadata.py`; still pending

---

### Key Decisions Still Open

| Q | Decision | Why it matters |
|---|---|---|
| Q1 | How is `query_fsr` currently hosted? | Understand deployment before modifying |
| Q2 | Embedding model for production? | GTE vs LiteLLM — must match ingest + query |
| Q3 | Reranking mandatory or configurable? | Eval shows it hurts R@1 by 30% |
| Q4 | Document type classification approach? | #1 quality gap — TILs/manuals mixed with FSRs |
| Q5 | Who owns ingestion pipeline in production? | Team dependency for Track A build |
| Q6 | Production Unity Catalog structure? | Schema must be locked before `vaid.*` tables created |
| Q7 | Write access + LiteLLM gateway key? | Needed to run pipeline end-to-end |

---

### Confirmed Facts

- **Track B (query service)**: Already implemented — only modifications needed based on gap decisions
- **Production tables** (`vaid.*`): Do NOT exist yet — all work against `main.gp_services_sdg_poc`
- **`field_service_report`** = full corpus; **`field_service_report_gt_litellm`** = 30-ESN experiment only
- **Embedding mismatch in full-corpus POC**: `fsr_pipeline` uses GTE (768-dim) at ingest, LiteLLM (3072-dim) at query — incompatible; `fsr_pipeline_gt_direct` is consistent and the reliable eval baseline
- **Reranking**: hurts R@1 (0.432 → 0.303); neutral at R@5 — spec mandates it unconditionally, conflicts with eval data
- **`fsr_scraped_file_mapping_ref`**: exists in `main.gp_services_sdg_poc` but NOT connected to any retrieval code
- **ESN identification**: 4-layer (regex → filename → LLM → SOT ref view); SOT ref takes priority
- **Join key**: `field_service_report.pdf_name` = `fsr_pdf_ref.s3_filename` (bare GUID)
- **UAT**: RE/OE flow UAT ongoing now → MVP2 planning starts after → architect channel heats up then

---

### People (internal reference — not in overview)

| Person | Role | What to ask |
|---|---|---|
| Tao | Tech lead | Q2, Q3, Q4, Q5 |
| Aaron | Databricks architect | Q1, Q6, Q7 |
| Shivam | Databricks team | Q1, Q7 (LiteLLM key) |
| Alex | DS (pipeline author) | Q8 (which pipeline variant), Q9 (scraping table readiness) |

---

### Key File Locations

| What | Where |
|---|---|
| **Deliverables (for sharing)** | `internal/summaries/` |
| Internal detailed docs | `internal/` |
| DS pipeline review (Apr-9) | `internal/reviews/09-Apr-alex-fsr-pipeline-review.md` |
| Reference query impl | `reference/examples/databricks_pipeline_sample/query_fsr_with_metadata.py` |
| Tao call transcript (Apr-7) | `internal/notes/source-materials/tao-apr-7-transcript.md` |
| ADRs | `internal/adr/` |
| Query results (Databricks) | `reference/examples/databricks_pipeline_sample/query_results/` |

---

### Resume Instructions

When coming back to this project:
1. Read this file
2. Check if Tao call happened — if yes, ask what decisions were made and update `internal/summaries/04-open-questions.md` + ADRs
3. If Tao call not yet done — summary folder is ready, walk through 5 docs, key asks are Q1–Q5
4. Next build task: working notebook from `query_fsr_with_metadata.py` against `main.gp_services_sdg_poc`
