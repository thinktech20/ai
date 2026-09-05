# FSR v2 — Autonomous Operation Guide

**Read this first in any new chat session.** It is self-contained: role,
permissions, environment facts, the tooling, and the traps that have already cost
time. Everything here was verified by running it, not inferred from docs.

**Last verified:** 2026-09-02 against `dev-dbr-profile`.

---

## 1. Role

Operate as an **FSR v2 pipeline and Databricks RAG expert**:

- Know the P1 (metadata) → P2 (chunking) → P3 (VS index) flow and its state
  machine (`metadata_status`, `chunk_status`, claim/drain, idempotent MERGE).
- Know the retrieval path: chunk → embedding → Vector Search → ESN-filtered
  lookup, and its failure modes (dimension mismatch, endpoint name drift, stale
  index, orphan chunks, docs with no ESN).
- Diagnose from tables and run history. Do not ask for screenshots.
- Fix root causes in `pw_sdg_ai_ser_repo`, not symptoms.
- **Verify claims by running them.** Several confident-sounding hypotheses in this
  file turned out wrong when tested (see §8).

## 2. Authorization

**Authorized for everything except git check-ins.**

| Action | Allowed |
|---|---|
| Read/write workspace files, run commands, query tables | yes |
| Trigger / poll / cancel Databricks jobs | yes |
| Submit one-off serverless runs; sync to the sandbox | yes |
| Drop + recreate tables **that the calling user owns** | yes |
| **`git commit` / `git push` / any git write** | **ask first** |

`git status` / `diff` / `log` are fine. VS Code may still prompt for terminal
commands — that is an editor setting (`chat.tools.terminal.autoApprove`), not
something this file can grant.

---

## 3. Environment facts

**Compute is serverless. Serverless runs Python 3.10.12.**

| Thing | Value |
|---|---|
| Profile | `dev-dbr-profile` |
| Host | `gevernova-ai-dev-dbr.cloud.databricks.com` |
| SQL warehouse | `ai-pw-ser-ds-dev-sqlw` = `c383216f6af5c7c0` |
| CLI | `~/.vscode-server/extensions/databricks.databricks-2.15.0/bin/databricks` |
| LLM key | not in env — read from `databricks.yaml` (see §5) |

**Jobs (dev), all `CAN_MANAGE`:**

| Stage | Job | ID | Notebook (repo-relative) |
|---|---|---|---|
| DDL | `PW_SDG_FSR_V2_DDL` | 542681720135008 | `ddls/fsr_v2/nb_sdg_fsr_v2_ddl` |
| P1 | `PW_SDG_FSR_V2_Metadata` | 1003518188699476 | `silver/src/etl/nb_sdg_fsr_v2_metadata` |
| P2 | `PW_SDG_FSR_V2_Chunking` | 185943124898155 | `gold/src/etl/nb_sdg_fsr_v2_chunks` |
| P3 | `PW_SDG_FSR_V2_VS_Index` | 844746489495403 | `vs/src/etl/nb_sdg_fsr_v2_index` |

**CI/CD deploys only from the `dev` branch.** Check-ins to `fsr_v2` do **not**
deploy. To run unmerged branch code, use the sandbox (§6).

**Verified dev deploy blocker (2026-09-03):**

- `databricks bundle deploy -t dev --profile dev-dbr-profile` does not complete
  in this workspace because the caller lacks `Manage` permission on many existing
  Databricks jobs. The deployment fails with `403 PERMISSION_DENIED` when trying
  to update job permissions.
- A second deployment failure path is a missing cluster id on some jobs (400
  `INVALID_PARAMETER_VALUE: Cluster id cannot be empty`). This blocks bundle
  updates before code reaches the target dev tables or index.
- Until the bundle deploy succeeds, do not assume the dev tables/index are in a
  deployable state for a full reset/ingest cycle. This is a prerequisite blocker,
  not a data issue, and it should be treated as such for all future simple-task
  runs.

### Permissions — what actually blocks work

Table owners decide what you can drop. One-off runs execute as **the calling
user**, not `service.globalopsfsso`, so the deployed jobs can do things you cannot.

| Object | Owner | Can I drop it? |
|---|---|---|
| `fsr_metadata_v2`, `fsr_chunks_v2`, `fsr_document_equipment_map_v2` | `service.globalopsfsso` | **no** |
| `ms_test_fsr_*`, `ms_sbx_*` | `madhurima.saxena` | yes |
| Schemas `ai_sot_…` / `ai_std_con_field_service_report` | `goutham.p` | n/a |
| Schema `ai_std_con_monitoring_diagnostics` | `msrinivasa.reddy` | **no `USE SCHEMA`** |

Consequences:

- Cannot reset the real dev tables from a sandbox run. Use `ms_test_*` (track 4).
- **`fsr_run_log_v2`/`fsr_data_quality_log_v2` now live in
  `ai_std_con_field_service_report`** (same schema as `fsr_chunks_v2`), not
  `ai_std_con_monitoring_diagnostics`. Fixed 2026-09-02 — `databricks.yaml` used
  to point `fsr_run_log_table_v2`/`fsr_dq_log_table_v2` at the diagnostics
  schema, which is inaccessible; repointed for dev/qa/stg/prod. The calling
  user can read/write/ALTER these tables directly now — no track-4 workaround
  needed for run-log/DQ-log access specifically (track 4 is still needed for
  metadata/chunks/equip-map, which remain `service.globalopsfsso`-owned).
- **Do not "fix" this by deleting the dev tables so they get recreated under your
  ownership.** The `Updater` group has `MODIFY` but not `MANAGE`, so
  `service.globalopsfsso` would then be unable to drop them and the deployed
  `RESET_FSR_V2=true` would break. If dev-table access is genuinely needed, ask
  for `MANAGE` on those three tables.

### Targeted 53-doc ingest run (required for quick reset/rebuild cycles)

For a clean dev ingest without touching the deployed dev tables, use the
combined Batch A + Batch B document list from
`pw_sdg_ai_ser_repo/validation/fsr_v2/ingest_data/nb_fsr_v2_dev_ingest.py`.
This is the full 53-doc cycle used by the validation workflow, and it must be
passed as one comma-separated `TARGET_PDF_NAMES` value with
`DROP_TABLES_AND_INDEX=true`.

Safe tables for this task:

- `vaid.ai_sot_field_service_report.ms_test_fsr_metadata_v2`
- `vaid.ai_std_con_field_service_report.ms_test_fsr_chunks_v2`
- `vaid.ai_sot_field_service_report.ms_test_fsr_document_equipment_map_v2`
- `vaid.ai_sot_field_service_report.ms_test_fsr_run_log_v2`
- `vaid.ai_sot_field_service_report.ms_test_fsr_data_quality_log_v2`
- `vaid.ai_std_con_field_service_report.ms_test_fsr_vs_index_v2`

Use the track-4 path unless the caller has `MANAGE` on the real dev objects.
The real dev table names remain the operational targets for smoke checks, but
resetting them is not safe for a normal user without the required ownership.

---

## 4. What works autonomously

**Query any dev table** — SQL Statement Execution API, seconds, no cluster.
Put the statement in a JSON file and use `--json @file` for anything with quotes;
inline shell quoting breaks constantly.

```bash
databricks api post /api/2.0/sql/statements --profile dev-dbr-profile --json @/tmp/q.json
```

**Trigger jobs** — `run-now` + poll `runs/get`. **Use `job_parameters`, not
`notebook_params`**; the legacy field is rejected outright, and undeclared names
are rejected too. `FSR_PDF_REF_VIEW` (P1) and `FSR_EMBEDDING_DIMENSION` (P2) are
*not* declared — they come from bundle variables.

**Run arbitrary code on serverless** — `workspace import` then
`POST /api/2.1/jobs/runs/submit` with only a `notebook_task`. Return results with
`dbutils.notebook.exit(json.dumps(...))` and read `notebook_output.result`.
Do **not** rely on stdout: serverless returns **no `logs`** field. `runs/get-output`
needs the **task** run_id, not the parent `job_run_id` (`run_output()` handles it).

---

## 5. The verification tooling

```
2-FSR-v2/automation/
  autonomous.md      this file
  dbx_client.py      stdlib REST client: sql, run_job, submit_notebook, wait_for_run
  checks.py          one function per assertion
  tracks.json        per-track tables, doc lists, job params (supports "_inherits")
  verify_fsr_v2.py   CLI: `check` (assert only) / `run` (execute + assert)
  sandbox_sync.sh    push the working branch to a personal workspace sandbox
```

```bash
cd 2-FSR-v2/automation
export LITELLM_API_KEY=$(grep -oP '(?<=litellm_api_key: ")sk-[^"]+' \
  ../../pw_sdg_ai_ser_repo/databricks.yaml | head -1)

python3 verify_fsr_v2.py check --track 4              # read-only, safe anytime
./sandbox_sync.sh                                     # push branch code
python3 verify_fsr_v2.py run --track 4 --sandbox --stages ddl,p1,p2 --no-rerun
```

Long runs: launch with `setsid nohup … > /tmp/run.log 2>&1 &` and poll the log.
53 docs ≈ 15 min for P1, ≈ 10 min for P2.

| Track | Tables | Docs | Use |
|---|---|---|---|
| 1 | real dev `fsr_*_v2` | 8 | smoke, needs deployed code |
| 2 | real dev | 27 (Batch A) | — |
| 3 | real dev | 53 (A+B) | after a `dev` deploy |
| 4 | `ms_test_*` (owned) | 53 | **the one that runs today** |

Track 4 inherits track 3 via `"_inherits": "3"` and overrides only the tables.

`--snapshot capture` refuses to overwrite an existing baseline. That guard exists
because capturing *after* a rerun and then comparing compares a state to itself
and always passes — an easy way to fake an idempotency result.

### Preprocessor-only autonomous checking

For an isolated preprocessor check, use
`pw_sdg_ai_ser_repo/validation/fsr_v2/preprocessor/run-preprocessor-standalone.ipynb`.
This path uses the P1 parser (`parse_pymupdf`, `pymupdf_v1.0`) and calls
`common/fsr_v2/preprocessor_v2.py` directly. It does not run LLM enrichment,
chunking, embeddings, or table writes.

Required check sequence:

1. Confirm the target PDF or parsed artifact is available. Do not infer a result
  for a missing PDF from another document's output.
2. Run only the requested document IDs and save one JSON artifact per ID.
3. Record parser name/version, page count, character count, metadata, region
  count, and the relevant `section_path` / equipment metadata.
4. For section-boundary bugs, inspect both the extracted heading text and the
  candidate collector output. A TOC heading is not proof that the body heading
  was detected.
5. Treat a missing candidate boundary as a preprocessor detection issue; do not
  describe it as an ESN-resolution issue until a span exists.
6. Report missing source files explicitly and request the PDF or parsed text when
  document-level verification cannot be completed.

For the Sep 3 electrical checks, the minimum assertions are:

- `5.1 DC Leakage` or the exact extracted equivalent is tagged `Generator`.
- The first subsequent root/subsection boundary after Electrical is tagged
  `Gas Turbine` when the governing equipment header is Gas Turbine.
- The output includes the exact extracted heading spelling, since `5.1 DC Leakage`
  in a TOC may differ from the body heading or may be absent from the body.

---

## 6. Sandbox workflow (run an unmerged branch, no deploy)

Notebook path resolution is fully **cwd-relative**
(`os.getcwd()/../../../silver/src/etl`), so the repo runs from any workspace
folder. `sandbox_sync.sh` wipes and re-syncs to
`/Users/madhurima.saxena@gevernova.com/fsr_v2_sandbox`; `--sandbox` makes the
driver submit one-off runs against those paths.

Non-obvious constraints:

- **Do not strip `# Databricks notebook source` from `common/fsr_v2/config.py`.**
  All four pipeline notebooks pull it in with `%run`, which requires a NOTEBOOK
  object. Everything genuinely *imported* from `common/` (`chunker`, `enums`,
  `mlflow_logger`, `preprocessor_v2`, `prompts/*`) is already marker-free and
  syncs as a FILE. An earlier "fix" that stripped markers broke `%run`.
- `silver/src/etl/fsr_v2` and `gold/src/etl/fsr_v2` are **both** packages named
  `fsr_v2`. Never put both on `sys.path` in one session.
- The sandbox isolates **code**, not **data** — runs still write to real tables.
  Point them at `ms_test_*`.
- Delete-then-sync is needed when an object of the wrong type sits at a path,
  otherwise sync fails with "file already exists".

---

## 7. FSR v2 schema gotchas

- `chunk_status` lives on **`fsr_metadata_v2`**, not `fsr_chunks_v2`.
- **`metadata_status` has a fourth, terminal value: `date_filtered`** (added
  2026-09-03) for docs outside `FSR_V2_MIN/MAX_DOC_YEAR`. It is not an error.
  P2 ignores it (P2 claims `completed` only), the retry query never re-claims
  it, and discovery skips it. A drained queue therefore looks like
  `completed + date_filtered + failed`, with **zero `pending`** — do not read a
  large `date_filtered` count as a problem. `doc_year` / `doc_date_source` on
  the same row record why it was filtered.
- All date columns are **`STRING`** — use regex, not date functions.
- Empty values are written as **`''`, not NULL**. Test `IS NULL OR trim(col)=''`.
- **`pdf_name` is not the source filename.** P1 derives it from ESN + date
  (`Generator_337X581_2020-12-12`). Correlate to source PDFs with **`document_id`**
  (the UUID); target names may carry a suffix, so match on prefix.
- Chunk embedding column is `chunk_embedding`; dimension is `embedding_dimension`.
- The DDL uses `CREATE TABLE IF NOT EXISTS` and **no ALTER by design** — the
  DDL notebook itself won't add new columns to an existing table, only
  `RESET_FSR_V2=true` (drop/recreate) does that through the notebook. But a
  manual, non-destructive `ALTER TABLE ... ADD COLUMNS` works fine and is the
  right fix for schema drift on a table you don't want to wipe — used this
  2026-09-02 to fix `fsr_run_log_v2` missing `p1_workers`/`llm_batch_count`/
  `docs_date_filtered` without losing existing rows.
- `enrichment.run` executes on the **main thread**, sequentially — the
  `ThreadPoolExecutor(P1_WORKERS)` only ever runs stage 2/3. **Never move it into
  the pool** — it uses a fixed temp view name `_fsr_v2_enriched` that concurrent
  threads would clobber (silent corruption). This still holds after the
  2026-09-02 interleaving fix (see §8) — Stage 4 fires more often now, but still
  only from the main thread, never from inside the pool.
- **`FSR_V2_P1_WORKERS` does not control overall P1 throughput at the levels
  tested (4/8/16 all measured ~295-302 docs/hr on equal-size doc chunks).** It
  only threads Stage 2-3 (parse+preprocess); Stage 4 (LLM batch call +
  per-doc enrichment/MERGE) is sequential regardless of worker count and is
  the actual bottleneck. Don't raise it expecting a speedup without also
  addressing Stage 4.
- Stage 1 discovery / target-lookup (`silver/src/etl/fsr_v2/input.py`) raises
  `ValueError: Ambiguous PDF matches for ...` when a target document ID matches
  two files in a volume (e.g. an original + a `_1`-suffixed duplicate in a
  manual-upload volume) instead of handling it gracefully. Hit this picking a
  random doc sample from `ecrt_reports`/manual volumes — filter samples to
  well-formed UUID document IDs to avoid it, or expect it as a real crash risk
  on an untargeted discovery run against those volumes.

---

## 8. Traps that have already burned time

- **Serverless is Python 3.10; this machine is 3.13.** PEP 701 nested-quote
  f-strings (`f"'{x.replace("'", "''")}'"`) compile locally and fail on Databricks.
  Five occurrences shipped on `fsr_v2` and would have broken P1 and P2 on deploy.
  Grep for that pattern before shipping.
- **Serverless returns no driver logs.** Any check that greps stdout reports
  "not found" on healthy runs. Emit structured rows instead — the run log now has
  `p1_workers`, `llm_batch_count`, `docs_date_filtered` for exactly this.
- **Positional `INSERT INTO … VALUES`** silently corrupts when a column is added.
  Always name columns.
- **Small smoke sets hide real bugs.** 8 docs passed clean; 53 docs surfaced a
  Delta write conflict and a date-format gap.
- **Check your own test before trusting a green result** (the snapshot self-compare
  above; also a MERGE column count "mismatch" that was really a regex tripping on
  `current_timestamp()`).
- **A full-corpus P1 run with no `FSR_TARGET_PDF_NAMES` can show zero progress
  for hours and still be healthy, not stalled.** Before the 2026-09-02 fix,
  Stage 4 (LLM+write) didn't start until Stage 2-3 finished for *every*
  discovered doc — at 50K+ docs / 4 workers that's a multi-hour barrier with
  nothing landing in the table. Fixed by interleaving Stage 4 into the Stage
  2-3 `as_completed()` loop so it fires per `LLM_BATCH_SIZE`-doc buffer
  instead of after the whole set drains. If testing an unpatched checkout,
  always scope with `FSR_TARGET_PDF_NAMES` to a few hundred docs.
- **DDL reset wipes `fsr_run_log_v2`/`fsr_data_quality_log_v2` too, not just
  the metadata/chunks/equip-map tables.** Running `RESET_FSR_V2=true` between
  sweep iterations (e.g. comparing worker counts) silently discards the
  previous iteration's run-log row before you can read it. Capture
  `duration_seconds` etc. immediately after each run, or don't reset between
  comparison runs at all — use disjoint target-doc chunks against the same
  tables instead.

---

## 9. Current state (2026-09-02)

**Dev backfill + incremental validation (§ new `backfill-monitoring-plan.md` /
`backfill-pulse-log.md` in this folder): both tracks passed.** Full summary,
bugs found/fixed, and the `FSR_V2_P1_WORKERS` sweep (4 vs 8 vs 16 — flat
throughput, no need to raise it) are in `backfill-pulse-log.md`'s closing
session summary. Headline fixes this session:

- Stage 2-3/Stage 4 barrier in P1 (see §8) — fixed, verified continuous
  progress on sandbox test, committed to `fsr_v2` ("concurrency discovery
  fix"). **Confirm merged to `dev` + deployed before relying on it in prod.**
- `fsr_run_log_v2`/`fsr_data_quality_log_v2` relocated in `databricks.yaml`
  from the inaccessible `ai_std_con_monitoring_diagnostics` to
  `ai_std_con_field_service_report` for all four envs. Merged to `dev`.
- `fsr_run_log_v2` schema drift (missing columns, INSERT silently failing)
  fixed non-destructively via `ALTER TABLE ADD COLUMNS` in dev. **Check
  qa/stg/prod for the same drift before trusting their run logs.**
- `RESET_FSR_V2` was `"true"` for both dev and qa — fixed to `"false"` for
  dev; qa deliberately kept `"true"` (explicit decision, still needs
  validation-mode resets).
- Discovered the dev corpus is **50,177 eligible docs (2016+), not ~22,000**
  as previously assumed — factor this into prod backfill sizing/partitioning.

Track 4, 53 docs, branch code via sandbox (2026-09-01 snapshot, superseded by
the above): **14 checks, 2 failed**.
53 docs / 7036 chunks / 88 map rows / 44 with `primary_esn` / 5 with `st_esn`.
Both remaining failures are OPEN-4 below — correct behaviour, not defects.

Fixed and verified on real data: doc-level ESN fallback (`gt → gen → st`),
equipment-map seeding from doc-level ESNs, `st_esn` persisted end-to-end,
PEP 701 syntax, Delta MERGE retry, hyphenated date formats, run-log columns.

Open items — details in
`2-FSR-v2/bug-preprocessor/new-preprocessor-issues/rca-plan.md`:

- **OPEN-1** equipment-prefixed subsections do not flip back to parent root.
  Red since `771ffca`. Preprocessor change — do not touch without asking.
- **OPEN-2** two stale unit tests (`ibat_resolver` mock signature; a TOC-gate
  assumption). Test-only.
- **OPEN-4** 9 of 53 docs print a **sys_id (`SY…`) where the ESN belongs**.
  Not an OCR problem — all have text. IBAT resolves some (`SY0048845 → V02450`).
  These are non-GE serial formats (`V02450`, `SLF3319`). 17% of the corpus is
  unreachable by ESN-filtered retrieval. Fix lands in the preprocessor.
- **New (2026-09-02):** Stage 1 discovery (`input.py`) raises on ambiguous
  filename matches (original + `_1`-suffixed duplicate) in manual-upload
  volumes instead of handling gracefully. Not yet fixed.

Not yet verified: P3/VS retrieval against the real index; P2 at the same scale
the P1 worker sweep covered (only P1 was load-tested this session).

---

## 10. How to give me a task

State the outcome, not the steps.

- "Verify track 4" → I sync, run, and report the PASS/FAIL table.
- "Why are N docs missing X?" → I query tables + parsed JSONs and come back with
  a cause and evidence.
- "Fix Y" → I diagnose, change the repo, run it in the sandbox, verify, then
  **ask before committing**.
