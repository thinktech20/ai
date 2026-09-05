# FSR v2 — Backfill + Incremental Ingestion Validation Plan (DEV first)

> **Status: draft, not yet run.** Modeled on the FSR v1 plan
> ([`../../fsr-prod-ops/backfill-monitoring-plan.md`](../../fsr-prod-ops/backfill-monitoring-plan.md)),
> adapted to FSR v2's schema, jobs, and tooling. **Scope: dev only.** Once this
> is validated in dev and the branch is promoted (`fsr_v2` → `dev` → prod
> deploy), repeat the same two tracks against prod tables and use
> [`../prod-hardening/backfill-runbook`](../prod-hardening/backfill-runbook) for
> the full-scale, year-cohort prod backfill. Do not reuse this file's "stop
> early" posture in prod — prod runs to completion.

**Read [`autonomous.md`](autonomous.md) first** for environment facts, job
IDs, permissions, and the verification tooling (`dbx_client.py`, `checks.py`,
`verify_fsr_v2.py`, `tracks.json`).

---

## 1. What's actually being tested

FSR v2 has **no separate backfill code path**. Per
[`prod-hardening-items`](../prod-hardening/prod-hardening-items) §6, one job
graph (`PW_SDG_FSR_V2_Ingestion`, or the 3 independent jobs
`PW_SDG_FSR_V2_Metadata` / `_Chunking` / `_VS_Index`) serves both:

- **Backfill** — first pass over the ~22,000+ eligible docs (`outage/report
  date >= FSR_V2_MIN_DOC_YEAR`, default 2016) in the dev source volumes.
- **Incremental ingestion** — the *same* job, re-triggered, with
  `FSR_TARGET_PDF_NAMES` empty. Idempotency (unchanged doc → reuse, not
  reprocess) is what makes a rerun "incremental" instead of a full redo.

So there are really **two things to prove**, not two code paths:

1. **Backfill mechanics work at scale** — concurrency, throughput, logging
   (run log + DQ log), failure handling — over a long-running claim/drain
   loop against the full 2016+ corpus. We do **not** need it to finish in dev;
   ~22K docs is hours, and dev has no consumer waiting on the data.
2. **Incremental behavior is correct** — a rerun (or a run that discovers new
   docs) only touches new/changed documents, does not reprocess or duplicate
   completed ones, and the completed set stays stable.

---

## 2. Track A — Backfill sample validation (bounded, dev)

**Goal:** run the full 2016+ dev corpus through P1 → P2 → P3 long enough to
observe healthy behavior at scale, then **stop deliberately** — no need to
reach 22K completions in dev.

### 2.1 Pre-flight

- [ ] Confirm dev tables are in a known state (either freshly reset via DDL
      with `RESET_FSR_V2=true`, or continuing from an existing track —
      decide and note which, since Track B needs a stable "already completed"
      baseline to diff against).
- [ ] Confirm no other track/job is writing to the same dev tables
      concurrently (see `autonomous.md` §3 ownership table — you cannot drop
      the real `fsr_metadata_v2`/`fsr_chunks_v2`/`fsr_document_equipment_map_v2`,
      only `service.globalopsfsso` can).
- [ ] `FSR_TARGET_PDF_NAMES` empty, `FSR_SOURCE_VOLUME_PATHS` set to all dev
      volumes (see `tracks.json` track 1/2 `p1` params for the current list).
- [ ] `FSR_V2_MIN_DOC_YEAR=2016`, `FSR_V2_MAX_DOC_YEAR` unset (full range —
      do not partition by year cohort in dev; that's a prod-scale concern).
- [ ] Note current `FSR_V2_P1_WORKERS` / `FSR_P2_BATCH_SIZE` / P2 concurrency
      knobs — see §5.

### 2.2 Kick off

Trigger P1 (`PW_SDG_FSR_V2_Metadata`, job `1003518188699476`) against the full
volume list, no target filter. Once P1 has committed at least one batch, kick
off P2 (`PW_SDG_FSR_V2_Chunking`, job `185943124898155`) in drain mode
(`FSR_P2_MAX_ITERATIONS=0`), then P3 (`PW_SDG_FSR_V2_VS_Index`, job
`844746489495403`, `INDEX_MODE=sync`).

```bash
cd 2-FSR-v2/automation
databricks jobs run-now 1003518188699476 --profile dev-dbr-profile \
  --json '{"job_parameters": {}}'    # empty target names + full volume list already in the job's saved params — confirm in UI first
```

> Prefer triggering from the Databricks UI for this one — a long-running,
> full-corpus run is exactly the kind of "hard to reverse, runs for hours"
> action that's worth a manual look at the job's saved parameters before
> pressing go, even though CLI trigger is otherwise fine.

### 2.3 Pulse checks — every 30–60 min during the observation window

Reuse the query shapes from
[`../../fsr-prod-ops/backfill-monitoring-plan.md`](../../fsr-prod-ops/backfill-monitoring-plan.md)
§3, adapted to the v2 schema (both statuses live on **`fsr_metadata_v2`**,
not split across tables — see `autonomous.md` §7):

```sql
-- 1. Queue state
-- metadata_status: pending | completed | failed | date_filtered
-- 'date_filtered' is terminal and expected (doc outside FSR_V2_MIN/MAX_DOC_YEAR);
-- a drained queue has zero 'pending', not zero 'date_filtered'.
SELECT metadata_status, chunk_status, count(*)
FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
GROUP BY 1, 2 ORDER BY 1, 2;

-- 2. Throughput last 60 min (P1 uses scraped_at, not a claimed_at column)
SELECT count(*) FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE scraped_at > current_timestamp() - INTERVAL 60 MINUTES;

-- 3. Chunk table volume
SELECT count(*) AS total_chunks, count(DISTINCT document_id) AS docs,
       count(*) / count(DISTINCT document_id) AS avg_per_doc
FROM vaid.ai_std_con_field_service_report.fsr_chunks_v2;

-- 4. Run log — concurrency + batching evidence (the thing serverless stdout can't show you)
SELECT job_name, start_time, p1_workers, llm_batch_count, docs_date_filtered,
       docs_claimed, docs_succeeded, docs_failed, error_summary
FROM vaid.ai_std_con_field_service_report.fsr_run_log_v2
ORDER BY start_time DESC LIMIT 10;

-- 5. DQ log — are failures being logged, not just swallowed?
SELECT failure_category, count(*) AS n
FROM vaid.ai_std_con_field_service_report.fsr_data_quality_log_v2
GROUP BY 1 ORDER BY n DESC;

-- 6. Stale claims
SELECT document_id, chunked_at FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE chunk_status = 'in_progress' AND chunked_at < current_timestamp() - INTERVAL 60 MINUTES;

-- 7. Recent failures (sample)
SELECT document_id, substr(metadata_error, 1, 150) FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE metadata_status = 'failed' ORDER BY scraped_at DESC LIMIT 10;
SELECT document_id, substr(chunk_error, 1, 150) FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE chunk_status = 'failed' ORDER BY chunked_at DESC LIMIT 10;
```

Append each check to [`backfill-pulse-log.md`](backfill-pulse-log.md) (same
template as v1 — see §7 below).

**What "healthy" looks like, specifically for what we're validating here:**

| Signal | Evidence it's working |
|---|---|
| **Concurrency** | `fsr_run_log_v2.p1_workers` matches the configured `FSR_V2_P1_WORKERS`; `llm_batch_count > 0` and growing; P2 batches complete in minutes, not one-doc-at-a-time serial pace |
| **Logs are written** | Run log gets a new row per P1/P2 batch; timestamps advance; no long gap with docs moving but no run log row |
| **DQ problems are logged** | `fsr_data_quality_log_v2` has rows when `metadata_status='failed'` or `chunk_status='failed'` exist — not just a silent status flip with no reason captured |
| **No silent stalls** | Queue counts move between two consecutive pulses; stale-claim query returns 0 |
| **Failure rate sane** | Failed docs are a small fraction (corrupt PDFs, LLM 5xxs) — compare against the ~830/18K (4.6%) v1 baseline as a rough sanity bound, not a hard gate |

### 2.4 Stop criteria (dev — deliberately incomplete)

Stop the run once **all** of these hold, regardless of how much of the 22K
corpus is done:

- [ ] At least 3–4 P1 commit batches observed, with the run log confirming
      the configured worker count and LLM batching on each.
- [ ] At least a few dozen P2 batches drained cleanly (batch success, chunk
      counts landing, embedding dimension correct).
- [ ] At least one real failure has been seen end-to-end (a corrupt PDF or an
      LLM error) and confirmed it lands in `metadata_status='failed'` /
      `chunk_status='failed'` **with** a DQ log row and a run-log error
      summary — not silently dropped. If none occurs naturally within the
      window, don't force one in dev; note it as unverified and rely on the
      unit/integration tests in `prod-hardening/test-plan` (LLM failure
      recovery scenario) instead.
- [ ] No stale claims and no unexplained stall observed across 2+ consecutive
      pulses.
- [ ] VS index (P3) has synced at least once and row count tracks the chunk
      table (allow lag — see v1 playbook, VS sync only fires when the P2
      drain loop exits an iteration, `FSR_P2_MAX_ITERATIONS=0` means it may
      lag until a natural exit point).

Then: **cancel the P1 and P2 job runs** (Databricks UI or
`databricks jobs cancel-run <run_id>`). Do not let them drain the full corpus
in dev. Record final doc counts, elapsed time, and throughput in the pulse
log's closing entry.

---

## 3. Track B — Incremental ingestion validation

**Precondition:** Track A has left a **partially-completed** corpus in dev —
some docs `completed`/`completed`, a large remainder still `pending`. This is
exactly the substrate needed: incremental ingestion must be indistinguishable
from "rerun the same job on a partially-done queue."

### 3.1 What "incremental" means here — two behaviors to prove separately

1. **Already-completed docs are not reprocessed.** Rerunning P1/P2 with the
   same empty `FSR_TARGET_PDF_NAMES` must not re-call the LLM or re-chunk docs
   already at `metadata_status='completed'` / `chunk_status='completed'`
   unless their source changed (see `prod-hardening-items` §2, "P1
   reprocessing contract").
2. **New/still-pending docs get picked up on the next trigger**, without
   manual intervention, and only those — the completed set stays byte-for-byte
   stable (parsed path, chunk count).

### 3.2 Test steps

**Step 1 — idempotency snapshot before the incremental run.**
Use the existing tool rather than hand-rolling this:

```bash
cd 2-FSR-v2/automation
python3 verify_fsr_v2.py check --track <track-used-in-A> --snapshot capture
```

This records `(document_id, parsed_volume_path, chunk_count)` for every
currently-completed doc (`take_snapshot()` in `verify_fsr_v2.py`).

**Step 2 — trigger the same job again** (empty `FSR_TARGET_PDF_NAMES`, same
source volume paths). This is the "incremental ingestion" trigger — in prod
this would be the daily schedule; in dev it's a manual re-run.

**Step 3 — while it runs, confirm only the pending remainder is being
claimed**, not the already-completed set:

```sql
-- docs_claimed in the new run-log rows should equal the pending count from
-- before the trigger, not the full corpus size
SELECT start_time, docs_claimed, docs_succeeded, docs_failed
FROM vaid.ai_std_con_field_service_report.fsr_run_log_v2
WHERE start_time > '<trigger_timestamp>'
ORDER BY start_time;
```

**Step 4 — after the run (or after another bounded observation window),
compare against the snapshot:**

```bash
python3 verify_fsr_v2.py check --track <track-used-in-A> --snapshot compare
```

`snapshot_compare()` fails if any previously-completed doc's
`parsed_volume_path` or chunk count changed, disappeared, or if row identity
drifted — i.e., it directly asserts "the completed set was left alone."

**Step 5 — confirm the new docs actually landed:**

```sql
SELECT count(*) FROM vaid.ai_sot_field_service_report.fsr_metadata_v2
WHERE metadata_status = 'completed' AND scraped_at > '<trigger_timestamp>';
```

Should be > 0 and roughly match `docs_succeeded` from the run log for that
window.

### 3.3 Stronger signal: simulate a genuinely new document

The above proves "rerun only touches the backlog," which is necessarily true
for any correct incremental behavior, but doesn't prove a doc that becomes
newly available *after* a run started gets picked up on the *next* run. To
test that directly:

1. Pick one doc ID not yet processed (`metadata_status` is `MISSING` for it —
   check it isn't already in `fsr_metadata_v2`).
2. Confirm it is present in one of the configured `FSR_SOURCE_VOLUME_PATHS`
   (it already is, if using the real dev volumes — nothing to upload).
3. Run P1 with **only that ID** via `FSR_TARGET_PDF_NAMES` (this both proves
   targeted-mode still works and gives a clean single-doc "arrival" signal
   without depending on discovery order across ~22K docs).
4. Assert: that doc reaches `completed`, no other doc's row changed (snapshot
   compare again), and P2/P3 pick it up on their next trigger the same way
   they would any other pending doc — no special-casing needed.

### 3.4 Pass/fail

| Check | Pass condition |
|---|---|
| Snapshot compare (Step 4) | Zero diffs — completed set unchanged |
| New docs claimed (Step 3/5) | `docs_claimed` ≈ pending backlog size, not full corpus; new completions > 0 |
| Targeted single-doc arrival (§3.3) | Doc completes; snapshot compare still clean |
| No duplicate chunk rows | `check_orphan_chunks` / a `count(*) vs count(DISTINCT chunk_id)` check on `fsr_chunks_v2` for the affected docs |

---

## 4. Topology (dev)

Reuse `autonomous.md` §3 and `tracks.json` verbatim — do not duplicate table
names here beyond what's needed for the queries above. Key ones:

| Table | Full name |
|---|---|
| Metadata (both statuses live here) | `vaid.ai_sot_field_service_report.fsr_metadata_v2` |
| Chunks | `vaid.ai_std_con_field_service_report.fsr_chunks_v2` |
| Equipment map | `vaid.ai_sot_field_service_report.fsr_document_equipment_map_v2` |
| Run log | `vaid.ai_std_con_field_service_report.fsr_run_log_v2` |
| DQ log | `vaid.ai_std_con_field_service_report.fsr_data_quality_log_v2` |
| VS index | `vaid.ai_std_con_field_service_report.fsr_vs_index_v2` |
| VS endpoint | `pw-ser-sdg-vector-search` |

Jobs: see `autonomous.md` §3 table (DDL/P1/P2/P3 job IDs). If triggering via
the chained `PW_SDG_FSR_V2_Ingestion` workflow instead of the 3 independent
jobs, look up its job ID in the Databricks UI before scripting against it —
it isn't in the automation tooling's `JOBS` dict yet.

---

## 5. Knobs

| Param | Dev default | Note |
|---|---|---|
| `FSR_V2_P1_WORKERS` | 4 | conservative; raise to 8 only if no LLM 429/5xx over a sustained window |
| `FSR_V2_P1_LLM_BATCH_SIZE` | 5–10 | tracks.json uses 5 (track 1) / 10 (track 2+); higher = fewer LLM calls, larger blast radius per batch failure |
| `FSR_V2_MIN_DOC_YEAR` | 2016 | do not change for this test |
| `FSR_V2_MAX_DOC_YEAR` | unset | leave unset in dev — year-cohort partitioning is a prod-scale concern (see backfill-runbook) |
| `FSR_P2_BATCH_SIZE` | 20 | |
| `FSR_P2_MAX_RETRIES` | 3 | |
| `FSR_P2_MAX_ITERATIONS` | 0 (drain) | don't change — governs when VS sync fires, see v1 playbook §"VS index sync investigation" |
| `FSR_TARGET_PDF_NAMES` | empty for Track A/B.2; single ID for Track B.3 | |
| `RESET_FSR_V2` | false | **never true mid-track** — wipes progress; only at the start of a fresh track |

---

## 6. Failure playbook

Reuse the v1 playbook categories (`../../fsr-prod-ops/backfill-monitoring-plan.md`
§6) — LLM gateway bursts, corrupt PDFs, embedding failures, stale claims,
silent zero-progress — they apply unchanged. The one v2-specific addition:

**P1 batch-level LLM failure blast radius.** Per `prod-hardening-items` §2,
LLM batching means one bad response in a `FSR_V2_P1_LLM_BATCH_SIZE`-doc batch
marks *all* docs in that batch as failed (missing rows within a batch are
caught individually, but a batch-level exception is not). If failures cluster
in same-sized groups matching the batch size, that's this — not N independent
corrupt PDFs. Check `fsr_run_log_v2.llm_batch_count` vs failure count to
confirm the pattern before treating it as a data-quality signal.

---

## 7. Pulse log

Append entries to [`backfill-pulse-log.md`](backfill-pulse-log.md) using the
same template as v1 (queue state, throughput, run log summary, notable
failures, action taken, next check). Keep Track A and Track B entries
clearly labeled since they interleave in time.

---

## 8. After dev validation — promotion to prod

**Status: both tracks completed 2026-09-02.** Results, bugs found/fixed, and
the worker-count sweep are in the closing summary at the bottom of
[`backfill-pulse-log.md`](backfill-pulse-log.md). Read that before starting
the prod run — do not repeat the same discovery work.

### Settings to carry into prod

| Param | Recommendation | Basis |
|---|---|---|
| `FSR_V2_P1_WORKERS` | **4** (default) | Swept 4/8/16 on equal-size doc chunks — throughput was flat (~299/302/295 docs/hr). Stage 4 (LLM + enrichment) is serial regardless of worker count, so it isn't the bottleneck lever. Don't pay for concurrency that doesn't help. |
| `FSR_V2_P1_LLM_BATCH_SIZE` | 10 (default) | Untested higher — larger batches cut LLM round-trips but widen blast radius (one bad response fails the whole batch). |
| `FSR_V2_P1_LLM_DELAY_S` | 1 to start | Re-verify against the **prod** LLM gateway specifically — only tested against dev's gateway, which may have different rate limits. |
| `FSR_V2_MIN_DOC_YEAR` / `MAX_DOC_YEAR` | year-cohort partitioning per backfill-runbook | **More important now** — dev discovered 50,177 eligible docs, not ~22K. If prod's corpus is similarly larger than assumed, passes may need to be smaller/more numerous than originally planned. |
| `RESET_FSR_V2` | **false**, always | Never true against real prod data. |
| `FSR_P2_BATCH_SIZE` / `FSR_P2_EMBED_CONCURRENCY` | defaults (20 / 4) | **Not load-tested this session** — only P1 was swept at scale. Run an equivalent bounded P2 sweep before trusting these for prod. |

**Throughput math:** ~300 docs/hr for P1 alone means a 22K–50K-doc corpus is
roughly **3–7 days of P1 wall clock**. Confirm this is acceptable before
committing to the run; the only way to meaningfully speed it up is
parallelizing Stage 4 (LLM + enrichment), which was not attempted this
session (see `prod-hardening-items` §2 for the tracked item).

### Steps

1. Record final dev doc counts, throughput (docs/hr for P1 and P2), and the
   observed failure rate in the pulse log's closing entry. **Done** — see
   closing summary in `backfill-pulse-log.md`.
2. Merge/deploy the validated branch to `dev` (CI/CD only deploys from
   `dev` — see `autonomous.md` §3) so the prod bundle picks it up. **Code fix
   for the Stage 2–3/4 barrier is committed to `fsr_v2` but confirm it has
   actually merged to `dev` and deployed before relying on it in prod.**
3. Before the prod run: check `vaip.ai_std_con_field_service_report.fsr_run_log_v2`
   for the same schema drift found in dev (missing `p1_workers`/
   `llm_batch_count`/`docs_date_filtered` columns) — `ALTER TABLE ADD COLUMNS`
   if so, same as the dev fix.
4. Switch to [`../prod-hardening/backfill-runbook`](../prod-hardening/backfill-runbook)
   for the actual prod backfill — full corpus, year-cohort partitioning
   (2016–18, 2019–20, 2021–22, 2023–present), daily incremental job paused
   for the duration, and run-to-completion (no early stop).
5. Re-validate incremental ingestion in prod the same way as Track B here,
   once the prod backfill has landed a partial corpus — confirm the daily
   incremental job only claims new/changed docs against real prod data.
6. Known open item from dev testing: Stage 1 discovery (`input.py`) raises on
   ambiguous filename matches (an original + a `_1`-suffixed duplicate in a
   manual-upload volume). If prod's `ecrt_reports`/manual volumes have similar
   duplicates, a full untargeted discovery run could hit the same crash —
   worth a fix or at least a known-affected-doc list before running untargeted
   in prod.
