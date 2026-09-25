# PROD Backfill — Monitoring Plan

> **Status: ✅ COMPLETED** (backfill cutover Apr 30 – May 3, 2026). Kept for reference. Active post-deployment work lives in [plan.md](plan.md).

> **Goal:** Take the FSR PROD pipeline from cold start to ~17,800 docs fully ingested + embedded + indexed in VS, with confidence in the data quality, in ~2–3 days. Lessons from the DEV backfill (Apr 22–26) and AF_TEST run (Apr 27–28) are baked in.

---

## 1. Operating model

- **US daytime (Madhurima + Tao):** active monitoring, knob tuning, restarts.
- **India morning hand-off:** Sonam / Vinayaka pick up if anything is stuck overnight US.
- **Cadence:** pulse check every **1–2 hours** during US day, every **3–4 hours** otherwise. Append every check to [backfill-pulse-log.md](backfill-pulse-log.md).
- **Comms:** Slack thread for live status. Major events (job stop/restart, parameter change, terminal failure cluster) get a short note in the thread + a tracker entry.

### Day-1 schedule (Apr 30, 2026 PST)

| Time (PST) | Action | What to look for |
|---|---|---|
| ~10:55 | P1 batch 1 commit (~500 docs) | ✅ done |
| ~11:25 | Pre-2PM readiness check | ✅ done — 500 pickable |
| ~11:45 | nb_02 metadata-check on batch 1 | ✅ done — clean (ESN redaction-leak flagged for follow-up) |
| ~13:01 | ESN flag follow-up + ecrt confirmation | ✅ done — ecrt queued OK |
| ~13:15 | nb_01 pulse | ✅ done — batch 2 landed (999 + 1 fail) |
| ~13:25 | First P1 failure characterized | ✅ done — logged as terminal |
| ~14:45 | Quick queue snapshot pre-P2 | ✅ done — 999 pickable, clean |
| ~14:55 | P1 batch 3 commit | ✅ done (Δ 99 min from batch 2) |
| ~15:00 | P2 (chunking) job kickoff | ✅ done — kicked off on time |
| ~15:13 | P2 iteration 1 in-flight log review | ✅ done — ~30/50 docs in 3 min, 0 failures |
| ~15:30 | nb_03 chunk-check on first 150 docs | ✅ done — 8,611 chunks, all integrity checks pass |
| ~16:30 | P1 batch 4 commit | ✅ done (Δ 101 min from batch 3) |
| ~16:50 | nb_01 pulse — P2 14 batches deep | ✅ done — 699 docs (3.9%), 399 docs/hr P2 |
| ~20:08 | End-of-day pulse + handoff note | ✅ done — 2,098/18,094 done (11.6%), both jobs healthy, P2 at 410 docs/hr |
| ~20:20 | nb_02 metadata-check (2,498 completed) | ✅ done — clean; no new failure pattern; date-format DQ ratio holding ~0.04% |
| ~20:30 | nb_03 chunk-check (2,148 docs / ~143k chunks) | ✅ done — all integrity checks pass; only 1 P2 error (known 74ed935e) |
| ~23:25 | Pre-sleep pulse (nb_01 + nb_02 + nb_03) | ✅ done — 18.5% complete (3,347/18,094); both jobs healthy; 74ed935e now terminal (retry-cap=3); +1 new P1 terminal (132a4598, same null-pdf pattern). No knob changes. |
| **overnight (India)** | **3–4h cadence pulse** | Sonam/Vinayaka. Watch for stale claims, gateway errors, queue stall. 74ed935e is now terminal — no action needed. |

### Day-2 schedule (May 1, 2026 PST)

| Time (PST) | Action | What to look for |
|---|---|---|
| ~05:30 | Morning pulse (nb_01 + nb_02 + nb_03) + VS index check | ✅ done — 19.3% complete (3,496/18,094). **🚨 P2 stopped overnight** (last run 06:44 UTC, clean shutdown — likely iteration cap or timeout). 1,995 docs waiting. **🚨 New P1 pattern:** 4 docs failed with bare `'content'` error in same 08:29 UTC batch (likely one bad LLM response). VS index 231,048 rows = chunk table ✅. Reached out to support to restart P2. |
| ~07:30 | Post-restart confirmation + nb_04 VS index check | ✅ done — P2 restarted. nb_04 endpoint+index checks all green; row-drift initially blocked by REST API limitation. |
| ~07:45 | nb_04 re-run with SDK fallback for row count | ✅ done — SDK fallback works; drift now reportable. |
| ~12:00 | Mid-day pulse (nb_01 + nb_02 + nb_03) + scheduler removal | ✅ done — 30.7% complete (5,546/18,094). Both jobs healthy. P2 throughput 407 docs/hr (steady). Vinayaka removed daily schedule from `PW_SDG_FSR_Chunking_Backfill` (UI-only, no PR needed) to prevent overlapping runs. ETA ~30.9h → late May 2 / early May 3 PST. |
| ~14:00 | VS index sync investigation | ✅ done — root cause: chunking notebook's `sync_vector_search()` only fires after iteration loop exits (`FSR_P2_MAX_ITERATIONS=0` = drain mode never exits). Last actual sync was Apr 30 11:43 PM. CDF confirmed enabled; pipeline running. UI "Sync now" appears to no-op. Raised with support; no data risk while no one is querying. End-of-backfill checklist updated. |
| TBD | End-of-day pulse + India handoff | |

**P1 throughput (observed):** ~99–112 min/batch (avg ~104 min) × ~31 remaining batches ≈ **~54h P1 wall clock** total.
**P2 throughput (observed):** **~410 docs/hr** cumulative over 5h (above dev range midpoint). At current pace, P2 ETA **~39h** on remaining 15,996 docs.
**Expected full-backfill ETA:** ~2–2.5 days end-to-end (P2 will lag P1 by a few hours, but both finish in similar window).

### Day-3 schedule (May 2, 2026 PDT)

| Time (PDT) | Action | What to look for |
|---|---|---|
| ~06:00 | Morning pulse (nb_01) post-overnight India window | ✅ done — 65.2% complete (11,792/18,094). Both jobs healthy, no overnight stalls. P1 500/hr, 0 failures last 60m. P2 372 docs/hr cumulative; 2 single-doc PDF parse errors across last 20 runs (batch continued). +8 P1 terminal failures (all null-pdf "no matching row" pattern, ~1 every 3–4h). 6,302 docs remaining → ETA ~16.9h. |
| TBD | Mid-day pulse (nb_01 + nb_02 + nb_03) | Confirm P2 cadence holds; check if any of 3 retry-pending P2 docs (5eb78b05, 6a2840b8, 31b9a2df) settle one way or the other. |
| TBD | End-of-day pulse / completion check | If queue fully drained, run completion checklist (Section 7); else note state for India handoff. |

**Updated ETA (May 2 morning):** P1 producing ~500/hr > P2 consuming ~372/hr → P2 is the bottleneck. ~17h of P2 wall clock remaining → completion **late May 2 / early May 3 PDT**.

---

## 1a. Day-2/3 cadence (Fri May 1 onward)

- US day: pulse every **1–2h** during active window.
- India morning: pulse on handoff + every **3–4h**.
- **Major checkpoints:**
  - When P1 fully completes (all 17,800 in `metadata_status` terminal state) → run nb_02 against full corpus, cross-check ESN/date misses against dev baselines.
  - When P2 catches up to P1 → run nb_03 against full corpus, then nb_04 (VS index check) and nb_05 (full data correctness).
  - When queue is fully drained (zero claimable) → declare "done", run completion checklist (Section 7), notify Slack.

---

## 2. PROD topology + table references

### Catalogs

| Layer | Catalog |
|---|---|
| Application/processed | `vaip` |
| Source volumes | `viup` |

### Tables

| Table | Full name |
|---|---|
| Metadata registry | `vaip.ai_sot_field_service_report.biz_metadata_field_service_report` |
| Chunks (vector source) | `vaip.ai_std_con_field_service_report.vec_field_service_report` |
| VS index | `vaip.ai_std_con_field_service_report.vs_vec_field_service_report` |
| VS endpoint | `pw-ser-sdg-vector-search-prod` |
| Run log (P2) | `vaip.ai_sot_field_service_report.fsr_run_log` |
| DQ log | `vaip.ai_sot_field_service_report.fsr_data_quality_log` |

### Source volumes (driven by `FSR_SOURCE_VOLUME_PATHS` job param)

```
/Volumes/viup/ing_ud_fieldvision/fv_field_service_report,
/Volumes/viup/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports
```

### Jobs (assumed mirror of DEV split)

| Job | Role | Workflow file |
|---|---|---|
| **P1 — Metadata Backfill** | Discovers + LLM-normalizes metadata | `silver/src/workflows/fsr/pw_sdg_fsr_metadata.yml` |
| **P2 — Chunking + Embedding** | Claims `metadata_status=completed` rows, chunks, embeds | from `pw_sdg_fsr_ingestion.yml` (chunk task) |
| **Validate** | Data correctness checks (post-run) | `pw_sdg_fsr_validate.yml` |

> **Disable steady-state ingestion trigger** until backfill is done — don't let the scheduled job race the backfill on the same tables.

---

## 3. Pulse check — what to capture every check

Run [validation/nb_01_pulse_check.ipynb](validation/nb_01_pulse_check.ipynb) against PROD tables and capture in [backfill-pulse-log.md](backfill-pulse-log.md):

1. **Queue state** — counts grouped by `(metadata_status, chunk_status)`
2. **Throughput last 60 min** — `completed`, `failed` for both P1 and P2
3. **Chunk table** — total rows, unique docs, avg chunks/doc
4. **P2 run log (last 10)** — `docs_succeeded / docs_claimed`, duration, error_summary
5. **Recent failures** — sample 5–10 most recent `metadata_status=failed` and P2 failures with error reason
6. **Stale claims** — any `chunk_status=in_progress` claimed > 1 hour ago
7. **Job state** — both P1 and P2 jobs `active / stalled / stopped / completed`

---

## 4. Pre-flight checklist (before leaving the first batch unattended)

- [ ] **Trigger disabled** on the steady-state ingestion job
- [ ] **First P1 commit batch landed** — at least one MERGE wrote rows to metadata table
- [ ] **First P2 batch landed** — `fsr_run_log` shows ≥1 successful run with `docs_succeeded > 0`
- [ ] **VS endpoint reachable** — `pw-ser-sdg-vector-search-prod` ONLINE; index status not error
- [ ] **No silent zero-progress** — last 60 min has both `completed > 0` for P1 and at least 1 P2 batch
- [ ] **Failure rate sane** — P1 failures < 5% of completed in the first batch (corrupt PDFs are fine; LLM/network errors at scale are not)
- [ ] **Cluster health** — no driver OOM warnings; pool has capacity
- [ ] **Pulse log updated** — first pulse entry in [backfill-pulse-log.md](backfill-pulse-log.md)

---

## 5. Knobs (parameters you can tweak at runtime)

> All passed as Databricks job parameters. Don't change in code mid-run; change on the job and re-trigger.

| Param | Default | Backfill recommendation | When to change |
|---|---|---|---|
| `FSR_P1_COMMIT_BATCH` | 500 | **200–500** | Lower (200) for safer commits + faster recovery on failure; higher (500) for less MERGE overhead once stable |
| `FSR_P1_LLM_DELAY` | 0 | **1** initially, drop to **0** if gateway stable | Raise to 2–3 if seeing 502/503 storms; drop to 0 if no gateway issues for 2 hours |
| `FSR_BATCH_SIZE` | 4 | **4** | Raise to 8 only if LLM gateway is rock-solid and we want to push throughput |
| `FSR_P1_MAX_RETRIES` | 3 | **3** | Don't change |
| `FSR_MAX_PDFS` | *(unset = unlimited)* | **unset** for full backfill | Set to a small number (e.g. 50) only for a smoke test; **must be empty for full backfill** |
| `FSR_P2_BATCH_SIZE` | 50 | **50** | Don't change unless P2 idles too long between batches |
| `FSR_P2_MAX_RETRIES` | 3 | **3** | Don't change |
| `FSR_P2_MAX_ITERATIONS` | 0 (drain) | **0** | Don't change |
| `FORCE_RESET` | false | **false** | **NEVER true on prod** — it would wipe progress |
| `FSR_SOURCE_VOLUME_PATHS` | *(set per env in `databricks.yaml`)* | leave as-is | Only change if the source volume scope changes |

### Knob-change protocol

1. Note the symptom in [backfill-pulse-log.md](backfill-pulse-log.md).
2. Stop the affected job.
3. Edit the job parameter in Databricks UI.
4. Re-trigger — note the new param value in [backfill-pulse-log.md](backfill-pulse-log.md).
5. Verify the next pulse shows the expected change.

---

## 6. Failure playbook

### A. P1 LLM failure burst (502/503 from gateway)

- **Symptom:** Spike in `metadata_status=failed` rows; recent error sample shows `502 Bad Gateway` / `503 Service Temporarily Unavailable`.
- **Action:** If the burst is short (< 10 min), let the next P1 retry pass pick them up. If sustained, raise `FSR_P1_LLM_DELAY` to 2–3 and restart P1.
- **Reference:** Dev backfill saw 2 such windows. Both self-recovered after ~10 min.

### B. P1 stuck on corrupt PDFs

- **Symptom:** Recent failure sample dominated by `No /Root object! Is this really a PDF?` or `too many nested graphics states`.
- **Action:** No action — these are terminal source-data issues. They settle into `metadata_status=failed` with `metadata_retry_count >= 3` and stop being retried. Note count in tracker.
- **Expected:** ~830 such failures based on dev (same source volume).

### C. P2 stuck on embedding 400s

- **Symptom:** Same docs appearing repeatedly in P2 failures; coverage threshold (10%) blocks ingestion; `chunk_retry_count` climbing.
- **Action:** Let the retry cap (`P2_MAX_RETRIES=3`) terminate them. They'll stop being claimed after 3 attempts.
- **Expected:** Handful of docs (4–10 based on dev). Note in tracker; investigate post-backfill.

### D. P2 idling (queue not draining)

- **Symptom:** P1 has `metadata_status=completed` rows pending P2, but P2 isn't claiming.
- **Diagnostic:** Run P2 claim-diagnostic cell in pulse notebook. Check for stale claims (`chunk_status=in_progress` > 1 hour old).
- **Action:** If stale claims exist, manually flip them to `pending` so they can be re-claimed. If P2 job is stopped, restart it.

### E. P1 job dies / cluster crash

- **Symptom:** P1 job state = `failed` / `terminated`; no recent throughput.
- **Action:** Check Databricks job run logs for OOM or driver crash. Restart the job; it will resume from `metadata_status=pending` rows. Stub rows already written are durable.

### F. Silent zero-progress (both jobs running, no rows moving)

- **Symptom:** No change in `fully_completed` count between two consecutive pulse checks.
- **Diagnostic:** Check (1) cluster busy state, (2) P2 run log timestamps, (3) any locked tables.
- **Action:** Capture state in tracker, escalate to Sonam/Vinayaka if it persists > 30 min during US day.

### G. FORCE_RESET accidentally triggered

- **Symptom:** Metadata table count drops to near zero.
- **Action:** **STOP the job immediately.** Do not restart. Escalate. Restoration via Delta time-travel may be possible — confirm with Databricks team.

---

## 7. Completion criteria

Backfill is "done" when:

1. **Queue is fully resolved:** every doc is either `(completed, completed)` or `(failed, *)` (terminal P1 fail) or `(completed, failed)` with `chunk_retry_count >= 3` (terminal P2 fail).
2. **No active claims:** zero `chunk_status=in_progress`.
3. **P2 job exits cleanly:** last run shows `docs_claimed=0` (queue drained).
4. **Validation passes:** [validation/nb_05_data_correctness_full.ipynb](validation/nb_05_data_correctness_full.ipynb) against PROD tables — all integrity + embedding + VS-alignment checks pass. Pre-existing DQ checks (missing titles, etc.) may fail; that's expected.
5. **Counts reconcile:** chunk table doc count ≈ `metadata_status=completed AND chunk_status=completed` count.
6. **VS index ONLINE** with row count ≈ chunk table row count (allow lag).

When all 6 hold, append a final entry to [backfill-pulse-log.md](backfill-pulse-log.md), re-enable the steady-state ingestion trigger, and revoke the elevated access (per Slack agreement).

---

## 8. Post-backfill

- Re-enable scheduled ingestion job trigger.
- Ask for elevated access to be revoked.
- Record terminal failure list (corrupt PDFs, embedding-400 docs) for the FSR data team.
- Hand off VS index to consumers.
- Capture any new lessons in [`../bug-log.md`](../bug-log.md) and the dev backfill tracker for posterity.
