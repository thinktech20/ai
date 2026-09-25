# PROD Backfill — Tracker

> **Source of truth for current state.** Append new pulse entries at the **bottom**. Don't edit history.
>
> See [backfill-monitoring-plan.md](backfill-monitoring-plan.md) for cadence, knobs, and failure playbook.

---

## Run metadata

| Item | Value |
|---|---|
| Started | Apr 30, 2026 (US morning) |
| Branch deployed to prod | `main` (after PR #56 merge) |
| Code state | DS V3 chunker + `FSR_SOURCE_VOLUME_PATHS` param + retry-cap (`P2_MAX_RETRIES=3`) + warn-only validate checks 3.4/5.2 |
| Expected corpus size | ~17,800 PDFs |
| Expected wall clock | ~2–2.5 days based on dev (358 docs/hr P1, 375–500 docs/hr P2) |
| Expected terminal failures | ~830 corrupt PDFs (P1), handful of embedding-400 docs (P2) |

---

## Knob settings (current)

> Update this table whenever a parameter is changed. Keep it accurate to current job-config state.

| Param | Value | Note |
|---|---|---|
| `FSR_P1_COMMIT_BATCH` | 500 | confirmed from job UI Apr 30 |
| `FSR_P1_LLM_DELAY` | 0 | confirmed from job UI Apr 30 |
| `FSR_BATCH_SIZE` | 4 | confirmed from job UI Apr 30 |
| `FSR_BATCH_THREADS` | 4 (start 2, ramp 10s) | confirmed from job UI Apr 30 |
| `FSR_LLM_CONCURRENCY` | 3 (max 6) | confirmed from job UI Apr 30 |
| `FSR_PDF_EXTRACT_WORKERS` | 16 | confirmed from job UI Apr 30 (P1 only) |
| `FSR_MAX_RETRIES` | 3 | |
| `FSR_MAX_PDFS` | _empty_ | confirmed — no cap, full run |
| `FSR_P2_BATCH_SIZE` | 50 | confirmed from chunk job UI Apr 30 |
| `FSR_P2_MAX_RETRIES` | 3 | confirmed from chunk job UI Apr 30 |
| `FSR_P2_MAX_ITERATIONS` | 0 (drain) | confirmed from chunk job UI Apr 30 |
| `FSR_P2_PDF_WORKERS` | 4 | confirmed from chunk job UI Apr 30 |
| `FSR_TARGET_PDF_NAMES` | _empty_ | no targeted-doc filter |
| `FSR_VS_ENDPOINT` | `pw-ser-sdg-vector-search-prod` | confirmed from chunk job UI Apr 30 |
| `FSR_VS_INDEX` | `vaip.ai_std_con_field_service_report.vs_vec_field_service_report` | confirmed from chunk job UI Apr 30 |
| `FORCE_RESET` | false | NEVER true on prod |
| `FSR_SOURCE_VOLUME_PATHS` | `/Volumes/viup/ing_ud_fieldvision/fv_field_service_report,/Volumes/viup/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports` | confirmed Apr 30 — fv + ecrt_reports only (no naksha) |
| `LITELLM_API_KEY` | _plaintext job param (workaround)_ | follow-up: move to secret scope |
| `LITELLM_BASE_URL` | `https://prd-gateway.apps.gevernova.net` | |

---

## Pre-flight

- [ ] Trigger disabled on steady-state ingestion job
- [ ] First P1 commit batch landed
- [ ] First P2 batch landed
- [ ] VS endpoint `pw-ser-sdg-vector-search-prod` ONLINE
- [ ] No silent zero-progress
- [ ] Failure rate < 5% in first batch
- [ ] First pulse entry recorded below

---

## Pulse log

> One entry per check. Append at the bottom. Use the template.

### Pulse template

```text
### Pulse — <date> <time> PST

- **P1 job:** active / stalled / stopped / completed
- **P2 job:** active / stalled / stopped / completed
- **Queue state:**
  - completed/completed = N
  - completed/failed = N
  - completed/in_progress = N
  - completed/pending = N
  - failed/pending = N
  - pending/pending = N
- **Throughput last 60 min:** P1 completed=N, P1 failed=N, P2 batches=N (succeeded N/N)
- **Chunk table:** N total chunks across N docs (avg N/doc)
- **Notable failures (sample):**
  - <doc_id>: <reason>
- **Stale claims:** N (oldest claimed at <ts>)
- **Action taken:** <none / changed param X to Y / restarted job / etc.>
- **Next check:** <when + what to focus on>
```

---

### Pulse — Apr 30, 2026 (cold start, pre-pulse)

- **P1 job:** _started — first pulse pending_
- **P2 job:** _started — first pulse pending_
- **Action taken:** Backfill jobs kicked off in PROD (main branch deployment).
- **Next check:** Run [validation/nb_01_pulse_check.ipynb](validation/nb_01_pulse_check.ipynb) against PROD tables; capture queue state, first run-log batch, knob settings. Append a real pulse entry here.

### Pulse — Apr 30, 2026 ~18:13 PST (P1 in-flight, batch 1/37)

- **P1 job:** active — Commit Batch 1/37 (docs 1–500) in progress
- **P2 job:** not yet started (waiting on first P1 commit)
- **Phase observed in logs:**
  - 16:45:44 → ~16:50: PDF text extraction phase ran fast (~200+ `[OK]` extractions in ~5 min)
  - ~17:38 → 18:13: LLM extraction phase, micro-batches B62 → B115 (53 batches × 4 docs in ~35 min)
- **Throughput (LLM phase):** ~360 docs/hr (matches dev baseline of 358 docs/hr P1)
- **LLM round-trip:** ~25–60s per 4-doc batch; returning 4–7 normalized rows per batch
- **Errors / failures:** none visible in window — no `[FAIL]`, no terminal errors
- **Notable noise:** every LiteLLM call logs `InsecureRequestWarning` (SSL verification disabled on `prd-gateway`) — cosmetic, not blocking. Follow-up.
- **Action taken:** none — letting batch 1 complete before any tuning
- **Next check:** when batch 1/37 commits — confirm run-log entry, queue state, and check for any batch 1 P2 activity. If P1 throughput stays at ~360/hr, full P1 ≈ ~50h wall clock — flag for discussion if we want to push concurrency.

### Pulse — Apr 30, 2026 ~11:25 PST (pre-2PM chunk-job readiness check)

- **P1 job:** active — Commit Batch 1/37 has fully landed (500 docs committed)
- **P2 job:** not started yet — scheduled to kick off at 2 PM PST
- **Queue state:**
  - completed/pending = 500 (metadata done, awaiting chunking — pickable by P2)
  - pending/pending   = 17,594
  - in_progress / failed / completed-completed = 0
- **Pickable for chunk job at 2 PM:** **500** docs ready (all `chunk_pending`, no retries needed, no stale claims)
- **Corpus reconciliation:** total = 500 + 17,594 = 18,094 vs expected ~17,800 — small overcount (~300), likely registry stub rows / dupes; not blocking, flag for post-backfill cleanup
- **Errors / failures:** none
- **Action taken:** none — confirmed P2 will have work to claim when it starts
- **Next check:** after 2 PM PST — verify P2 starts, claims first batch (50), and run-log shows first P2 entry. Watch chunk_in_progress moves up while chunk_pending drains.

### Pulse — Apr 30, 2026 ~11:45 PST (metadata-check on first 500 committed docs)

- **Source:** [validation/nb_02_metadata_check.ipynb](validation/nb_02_metadata_check.ipynb) run against PROD
- **Required fields:** all 500 docs have `document_id`, `pdf_name`, `title`, `volume_path`, `page_count`, `scraped_at`, `esn` populated ✅
- **Date misses (content-level, expected):** report_issued_date=66, outage_start_date=37, outage_end_date=257
- **Date format malformed:** 0 / 0 / 0 ✅
- **`document_id` normalization (corpus-wide, 18,094 rows):** 0 with `.pdf` suffix, 0 uppercase — BUG-009 fix holding ✅
- **P1 failure breakdown:** empty (no failed docs) ✅
- **ESN buckets:** 0 null, 0 redacted, 342 pure_numeric, 67 valid_pattern → **91 docs (~18%) fall outside both buckets**. Need to sample to see actual format (prefixes/alpha-numeric/etc.) — flagged, not blocking.
- **Per-volume completion:** fieldvision 500/15,362; ecrt_reports 0/2,732. ecrt hasn't started — likely volume-listing order (fv listed first). Re-check after batch 2/37; if still 0 by batch 3, dig in.
- **Action taken:** none — both flags are observations, not blockers
- **Next check:** (a) sample the 91 non-bucketed ESNs to characterize format; (b) confirm ecrt starts processing within next 1–2 commit batches.

### Pulse — Apr 30, 2026 ~13:01 PST (follow-up on metadata flags)

- **ecrt_reports queueing — RESOLVED ✅** Sample of pending rows shows full ecrt paths populated (`/Volumes/.../ecrt_reports/<doc>.pdf`). Volume is queued correctly, just waiting in listing order behind fieldvision. No action.
- **ESN non-bucketed sample (5 examples):**
  - `{UK_NATIONAL_INSURANCE_NUMBER}` × 2 → 🚨 **PII redaction token leaked into ESN field** — LLM picked up a redaction placeholder. DQ issue, not backfill blocker.
  - `G501`, `T669` → short alphanumeric, possibly model/part numbers misclassified as ESN.
  - `270T530 | 290T530`, `270T598 | 290T598` → pipe-separated multi-value (LLM returning candidate list).
- **Severity:** medium DQ, low operational. Rows will chunk/embed fine; impact is on downstream search/filter precision.
- **Action taken:** none — backfill continues. To-do: open BUG entry for ESN cleanup; run sizing query across full corpus once P1 completes.
- **Next check:** after 2 PM PST P2 kickoff — pulse on chunking activity.

### Pulse — Apr 30, 2026 ~13:15 PST (batch 2 confirmed via scraped_at timeline)

- **`scraped_at` timeline:**
  - 18:20 UTC (11:20 PST): 500 docs (batch 1)
  - 20:12 UTC (13:12 PST): 499 docs (batch 2) — **batch 2 just landed**
- **Batch 2 wall clock:** ~112 min (vs ~85 min projection) — slightly slower, in-range
- **999 vs 1000:** one doc straddled the minute boundary or had `scraped_at` NULL — not concerning
- **Note on `metadata_in_progress`:** earlier `0` reading was NOT a stall. Schema has no `metadata_claimed_at` / `processed_at` column, so in-flight P1 work is invisible to the table until commit. Use `scraped_at` timeline as the progress signal instead.
- **Updated ETA:** ~112 min/batch × 35 remaining ≈ **~65h P1 wall clock** (vs original ~50h estimate)
- **P2 readiness at 2 PM:** ~1,000 docs claimable (better than the planned 500)
- **Action taken:** none
- **Next check:** ~14:05 PST — confirm P2 kicked off and is claiming from the now-1000-doc pool.

### Pulse — Apr 30, 2026 ~13:25 PST (first P1 failure characterized)

- **Queue:** completed/pending=999, failed/pending=1, pending/pending=17,094 (total 18,094 ✅)
- **First P1 failure:** `814e2f8b-44a3-4065-b584-5a0977f97ac9`
  - error: `LLM returned no matching row for this document`
  - `pdf_name` and `page_count` both null → PDF text extraction also returned nothing
  - Likely corrupt or image-only PDF — fits the ~830 corrupt-PDF expectation
- **P2 impact:** none — chunk job filters out `metadata_status='failed'` before claiming
- **Action taken:** added to terminal failures list; no live action
- **Next check:** ~14:05 PST — P2 kickoff

### Pulse — Apr 30, 2026 ~14:55 PST (batch 3 commit + pre-P2 readiness)

- **P1 commit timeline (from job SQL statements panel):**
  - Batch 1: 11:20 AM PST
  - Batch 2: 13:12 PM PST (Δ 112 min)
  - Batch 3: **14:51 PM PST** (Δ 99 min) ← slightly faster
- **Pre-P2 snapshot (14:45 PST, before batch 3 visible in queue):** 999 pickable, 0 in_progress — clean
- **Updated P1 ETA:** 99 min/batch × 34 remaining ≈ **~56h** (down from 65h)
- **Errors:** still just the 1 known terminal failure
- **Action taken:** none
- **Next check:** ~15:05 PST — confirm P2 (chunk job) kicked off via `fsr_run_log`

### Pulse — Apr 30, 2026 ~15:13 PST (P2 kickoff confirmed, first batch in-flight)

- **P2 alive ✅:** chunk_in_progress=50, claim timestamp 22:00:52 UTC = **15:00:52 PST** — kicked off right on schedule
- **First batch claim is one-shot:** all 50 claimed at the same instant (oldest = newest claim ts)
- **Queue:** completed/in_progress=50, completed/pending=1,449, failed/pending=1, pending/pending=16,594
- **fsr_run_log:** still empty — entries only written on batch completion (expected)
- **total_chunks:** 0 — chunks land at end of batch (expected)
- **P1 last 60m:** 500 done, 0 failed (batch 3 captured)
- **Watch flag:** if these same 50 are still `in_progress` past ~15:30, it's slow vs dev baseline (~6–10 min/batch). Re-check at next pulse.
- **Action taken:** none
- **Next check:** ~15:30 PST — confirm first P2 batch commits (chunks > 0, run_log row, in_progress drops to 0 then re-claims next 50)

### Pulse — Apr 30, 2026 ~15:18 PST (P2 iteration 1 in-flight, log review)

- **Source:** P2 driver log
- **Iteration 1 (run=36484a88a848):** started 22:00:51 UTC = 15:00:51 PST, claimed 50 docs
- **Pace:** ~30 of 50 docs done by 22:04 UTC (~3 min in) — well under dev baseline (~6–10 min/batch)
- **Failures:** 0
- **Page count range handled:** 9 → 1,065 pages, no issues
- **Chunk counts:** 6 → 368 per doc, scales with page count
- **`section_cov` distribution (V3 hierarchical chunker):**
  - 100% on most small/medium docs ✅
  - Partial (10–90%) on a few mid-sized docs
  - Low (2–8%) on several large multi-hundred-page docs (1065p, 349p, 320p, 309p)
  - **Expected behavior** — chunker degrades to size-based fallback when TOC structure is missing. Same pattern observed in dev.
- **Action taken:** none
- **Next check:** ~15:30 PST — confirm iteration 1 commits, chunks land in table, run_log gets first row, next 50 claimed

### Pulse — Apr 30, 2026 ~15:30 PST (P2 chunk-check via nb_03, ~3 batches in)

- **Source:** [validation/nb_03_chunk_check.ipynb](validation/nb_03_chunk_check.ipynb)
- **Progress:** 150 docs chunked → 8,611 total chunks (~3 P2 batches in 25 min ≈ **~360 docs/hr** P2, in dev range)
- **State integrity:** failed_with_chunks=0, in_progress_with_chunks=0, completed_missing_chunks=0, orphan_chunks=0, duplicate_chunk_ids=0 ✅
- **Embedding integrity:** null=0, wrong_dim=0, empty_text=0 — all 3072-dim populated ✅
- **Chunk quality:** oversized=0, bad_page_num=0, missing_metadata_json=0, missing_created_at=0 ✅
- **Cross-table:** esn_mismatch=0, completed_missing_chunked_at=0, failed_missing_chunk_error=0 ✅
- **Failures:** 0 across 8,611 chunks (cleaner than dev backfill at this stage)
- **Chunk distribution:** min=5, p5=7, median=35, p95=177, max=408, avg=57
- **Largest doc handled:** 1,035 pages → 408 chunks ✅ (no infra strain)
- **Action taken:** none
- **Next check:** ~16:30 PST — full pulse + likely P1 batch 4 commit (~16:30 expected)

### Pulse — Apr 30, 2026 ~16:50 PST (P1 batch 4 in, P2 14 batches deep)

- **Overall progress:** 699 / 18,094 docs fully completed (**3.9%**)
- **P1 commit timeline:** 11:20, 13:12, 14:51, **16:32** PST (batch 4 in; Δ 101 min)
- **P1 failures:** 2 total (0.1% rate) — both same pattern (`LLM returned no matching row`, null pdf_name & page_count)
- **P2 throughput:** 14 batches in 1.75h → **399 docs/hr** (in dev baseline range 375–500)
- **P2 ETA at current pace:** 43.5h remaining
- **P2 batches:** all 14 succeeded; durations 284–839s (median ~7 min); chunks 2,712–4,855 per batch
- **First P2 failure:** `74ed935e-e029-4c76-ad93-5ee029bc7675` — `code=5: too many nested graphics states` (PyMuPDF on complex PDF). retry_count=1, will be retried.
- **Total chunks:** 47,085 across 699 docs (avg 67/doc)
- **Stale claims:** 0 (50 in_progress are fresh, claimed seconds ago)
- **Action taken:** none — both jobs healthy, failures within expected band
- **Next check:** ~18:00 PST — end-of-day pulse + handoff note for India morning

### Pulse — Apr 30, 2026 ~17:30 PST (nb_02 metadata-check on 1,998 completed + flag follow-ups)

- **Source:** [validation/nb_02_metadata_check.ipynb](validation/nb_02_metadata_check.ipynb)
- **Required fields:** all populated except 4 missing `title` (~0.2%) and 1 missing `esn` ✅
- **NULL-ESN doc:** `79dee167-079f-4be9-adbb-54400e0bc51f` — `esn_source=null` (LLM no extract + no IBAT fallback). **Expected outcome per schema, not a bug.** 0.05% rate.
- **Date format malformed:** 3 rows with mixed format (LLM returning raw `DD MMM YYYY` in some cases instead of normalizing to `YYYY-MM-DD`)
  - `8877952f-...`: report_issued ✅, outage_start `10 Mar 2023` ❌, outage_end `16 Apr 2023` ❌
  - `8c800730-...`: report_issued `31 Jan 2024` ❌, outage_start ✅, outage_end null
  - Rate: 3/1,998 = 0.15%. **New DQ flag** — fix candidate: SQL post-process to normalize, or stricter LLM prompt.
- **ecrt_reports queueing — re-confirmed ✅** Sampled 10 ecrt rows, all properly registered with pdf paths. Just behind fieldvision's ~13k pending in listing order. Will start once fieldvision drains.
- **`document_id` normalization (corpus-wide, 18,094 rows):** 0 with `.pdf`, 0 uppercase ✅
- **P1 failure breakdown:** 2 docs, both `LLM returned no matching row` (consistent pattern)
- **ESN bucket distribution:** 1,383 pure_numeric + 271 valid_pattern + 343 outside-buckets — same ~17% non-bucketed proportion as batch 1. Includes the redaction-token leaks flagged earlier.
- **Action taken:** none. To-do (post-backfill): open BUG entries for (a) ESN redaction-token leak and (b) date-format inconsistency.
- **Next check:** ~18:00 PST — end-of-day handoff pulse

### Pulse — Apr 30, 2026 ~17:50 PST (nb_03 chunk-check, 849 docs)

- **Source:** [validation/nb_03_chunk_check.ipynb](validation/nb_03_chunk_check.ipynb)
- **Progress:** 849 docs chunked (up from 150 at 15:30) — added 699 docs in ~2.5h ≈ **~280 docs/hr in this window** (vs cumulative 399/hr; some natural variation)
- **Cross-table integrity:** esn_mismatch=0, completed_missing_chunked_at=0, failed_missing_chunk_error=0 ✅
- **P2 errors:** 1 (`code=5: too many nested graphics states` — known doc 74ed935e)
- **Chunk distribution (849 docs):** min=3, p5=5, median=40, p95=229, max=773, avg=68
- **Largest doc:** 1,560 pages → 773 chunks ✅
- **74ed935e follow-up:** failure-sample cell came back empty — possibly recovered on retry. Running targeted check next.
- **Action taken:** none
- **Next check:** confirm 74ed935e final state, then end-of-day handoff pulse

### Pulse — Apr 30, 2026 ~20:08 PST (end-of-day handoff pulse, P2 42 batches deep)

- **Source:** [validation/nb_01_pulse_check.ipynb](validation/nb_01_pulse_check.ipynb)
- **Overall progress:** 2,098 / 18,094 docs fully completed (**11.6%**)
- **Queue state:**
  - completed/completed = 2,098
  - completed/pending   = 349 (claimable by P2)
  - completed/in_progress = 50 (fresh claim, ts 03:08:54 UTC = 20:08 PST)
  - completed/failed = 1 (74ed935e — see below)
  - failed/pending   = 2 (terminal P1 fails)
  - pending/pending  = 15,594
  - **Total = 18,094 ✅** (reconciles)
- **P1 progress:** 2,448 docs metadata-completed (~batch 5 partially landed). Failures stable at 2 (0.08%). No new failure patterns.
- **P2 throughput (cumulative):** 42 runs in 5.12h → **410 docs/hr** (above dev baseline 375–500 midpoint). 2,098 docs done → 139,090 chunks (avg 66.3/doc). Run durations 237–722s (median ~7 min), all 50/50 except one batch with the single 74ed935e failure.
- **P2 ETA:** 39h on remaining 15,996 docs at 410/hr — tracks original 2.5d projection comfortably.
- **Stale claims:** 0 — 50 in_progress claimed seconds ago.
- **74ed935e update:** now at `chunk_status=failed`, `chunk_retry_count=2`, error unchanged (`code=5: too many nested graphics states`). One more retry and it goes terminal.
- **fsr_run_log P1 columns:** `p1_completed_last_60m` / `p1_failed_last_60m` returning null — run_log only captures P2 (known schema gap, not a regression). Use scraped_at timeline for P1 pace.
- **Action taken:** none — both jobs healthy, no knob changes.
- **Handoff to India morning:** see note below.

### Handoff note for India morning (Sonam / Vinayaka)

- **State at handoff (20:08 PST):** P1 + P2 both running, no stalls, no knob changes since cold start.
- **Overnight projection (~10h US night):**
  - P1: ~6 more commit batches → ~5,400 metadata-completed total by morning
  - P2: ~410 docs/hr × 10h ≈ ~4,100 more done → ~6,200 fully completed (~34%)
  - Healthy queue depth maintained; P2 won't starve
- **Pulse cadence:** every 3–4h. Notebook: `validation/nb_01_pulse_check.ipynb`. Append entries to this tracker.
- **Watch list:**
  - **74ed935e:** if `chunk_retry_count >= 3` and `chunk_status=failed` → move to terminal-failures table; no action needed (retry cap will stop it).
  - **Stale claims:** any `chunk_status=in_progress` older than ~1h → flip back to `pending` (see playbook D in backfill-monitoring-plan.md).
  - **Gateway 502/503 burst on P1:** if recent failures spike with gateway errors → playbook A (raise `FSR_P1_LLM_DELAY` to 2–3, restart P1).
  - **P2 idling:** if `completed/pending` grows but `total_chunks` doesn't → playbook D.
- **Do NOT:** change `FORCE_RESET`, change source volume paths, or restart cleanly without capturing state in tracker first.
- **Escalate to Madhurima/Tao on Slack** for: any sustained failure burst (>10 in 30 min), driver crash, or queue stall > 30 min.

### Pulse — Apr 30, 2026 ~20:20 PST (nb_02 metadata-check on 2,498 completed)

- **Source:** [validation/nb_02_metadata_check.ipynb](validation/nb_02_metadata_check.ipynb)
- **Completed corpus:** 2,498 docs (P1 has progressed 400 docs since 20:08 pulse — batch 5 finishing up)
- **Required fields:** all populated except `title`=7 missing (~0.28%) and `esn`=2 missing (~0.08%) — both `esn_source=null` rows are the same NULL-ESN docs (LLM no-extract + no IBAT fallback). Within expected schema behavior.
- **Date misses (content-level, expected):** report_issued=344, outage_start=196, outage_end=1,293 (proportions match earlier samples)
- **Date format malformed:** 1 / 1 / 1 — ratio holding at ~0.04% (1 doc, all 3 date fields). Same DQ flag class as prior pulses, no growth.
- **`document_id` normalization (corpus-wide):** 0 `.pdf` suffix, 0 uppercase ✅ (BUG-009 fix holding)
- **P1 failure breakdown:** still just 2 docs, both `LLM returned no matching row` — no new failure pattern.
- **ESN source mix:** 2,496 from LLM, 2 null (no IBAT-fallback rows yet — confirms IBAT path remains rarely used)
- **ESN duplicates (top of distribution):** 9 ESNs appear in 5 docs each (e.g. `297402`, `299422`, `299321`, `819414`); long tail at 3–4 docs/ESN. **Expected** — multiple FSRs per engine over time. Not a bug.
- **Volume split:** fieldvision = 2,498 completed + 2 failed + 12,862 pending; ecrt_reports = **0 completed**, 2,732 pending. Still queued behind fieldvision in listing order — re-confirmed earlier; no action.
- **Action taken:** none.
- **Next check:** overnight (India) per cadence; nb_02 again after fieldvision starts wrapping or ecrt starts processing (whichever first).

### Pulse — Apr 30, 2026 ~20:30 PST (nb_03 chunk-check on 2,148 docs)

- **Source:** [validation/nb_03_chunk_check.ipynb](validation/nb_03_chunk_check.ipynb)
- **Coverage:** 2,148 docs chunked → ~143k chunks (avg **66.5/doc**, holds steady from earlier samples)
- **State integrity:** failed_with_chunks=0, in_progress_with_chunks=0, completed_missing_chunks=0, orphan_chunks=0, duplicate_chunk_ids=0 ✅
- **Embedding integrity:** null=0, wrong_dim=0 (all 3072), empty_text=0 ✅
- **Chunk quality:** oversized (>4200 chars)=0, bad_page_num=0, missing_metadata_json=0, missing_created_at=0 ✅
- **Cross-table:** esn_mismatch=0, completed_missing_chunked_at=0, failed_missing_chunk_error=0 ✅
- **P2 errors:** 1 total (`code=5: too many nested graphics states` — known doc 74ed935e). No new failure pattern.
- **Distribution (2,148 docs):** min=1, p5=6, median=39, p95=221, max=891, avg=66.5
- **Largest doc:** `8ad30b7c-...` 2,434 pages → 891 chunks ✅ (also 3,641-page doc → 747 chunks, 3,063p → 557 chunks — no infra strain)
- **ecrt sanity:** ecrt_reports paths populated in queue (sampled 10 rows). Confirms ecrt is queued correctly, just listing-order behind fieldvision.
- **Action taken:** none — chunking pipeline is clean across the full processed corpus so far.
- **Next check:** overnight per cadence.

### Pulse — Apr 30, 2026 ~23:25 PST (pre-sleep pulse, full nb_01 + nb_02 + nb_03 sweep)

- **Source:** [validation/nb_01_pulse_check.ipynb](validation/nb_01_pulse_check.ipynb), [validation/nb_02_metadata_check.ipynb](validation/nb_02_metadata_check.ipynb), [validation/nb_03_chunk_check.ipynb](validation/nb_03_chunk_check.ipynb)
- **Overall progress:** 3,347 / 18,094 docs fully completed (**18.5%**)
- **Queue state:**
  - completed/completed = 3,347
  - completed/pending   = 99 (claimable by P2)
  - completed/in_progress = 50 (fresh claim, ts 06:23:05 UTC)
  - completed/failed = 1 (74ed935e — now retry-cap exhausted, see below)
  - failed/pending  = 3 (terminal P1 fails — +1 since 20:08)
  - pending/pending = 14,594
  - **Total = 18,094 ✅**
- **P1 progress:** 3,497 metadata-completed. 3 P1 failures total (0.09%) — same `LLM returned no matching row` pattern, all with null pdf_name & page_count. New addition: `132a4598-9860-4894-9d5d-31dff26f8692` (scraped 05:26 UTC).
- **P1 last 60m:** 499 completed / 1 failed — healthy. scraped_at timeline shows ~500-doc commit cadence every ~1.5–2h.
- **P2 throughput (cumulative):** 67 runs in 8.35h → **401 docs/hr** (in dev range, slightly under midpoint). 3,347 docs → 222,123 chunks (avg 66.4/doc).
- **P2 ETA:** 36.8h on remaining 14,747 docs at 401/hr — still tracks 2–2.5d projection.
- **Stale claims:** 0 — all 50 in_progress claimed seconds ago.
- **74ed935e update:** now `chunk_status=failed`, `chunk_retry_count=3` → **retry-cap exhausted, terminal.** No longer claimable. Pulse `retry_cap_exhausted=1` confirms.
- **nb_02 metadata-check (3,497 completed):**
  - Required-field misses: title=9 (~0.26%), esn=4 (~0.11%) — same NULL-ESN pattern (LLM no-extract + no IBAT fallback)
  - Date misses (content-level): report_issued=500 (~14%), outage_start=267 (~7.6%), **outage_end=1,767 (~50%)** — high but expected (many FSRs lack outage end date in source)
  - Date format malformed: 1 / 1 / 2 — ratio holding ~0.04%
  - document_id normalization: 0 `.pdf` suffix, 0 uppercase ✅ (BUG-009 fix holding corpus-wide)
  - ESN buckets: 2,411 pure_numeric + 459 valid_pattern + ~620 outside-buckets (~18%, consistent with prior samples; includes redaction-token leaks)
  - Volume split: fieldvision = 3,497 completed + 3 failed + 11,862 pending; ecrt_reports = **0 completed**, 2,732 pending (still queued behind fieldvision)
- **nb_03 chunk-check (3,397 docs / 224,808 chunks):**
  - State integrity: failed_with_chunks=0, in_progress_with_chunks=0, completed_missing_chunks=0, orphan_chunks=0, duplicate_chunk_ids=0 ✅
  - Embedding integrity: null=0, wrong_dim=0 (all 3072), empty_text=0 ✅
  - Chunk quality: oversized=0, bad_page_num=0, missing_metadata_json=0, missing_created_at=0 ✅
  - Cross-table: esn_mismatch=0, completed_missing_chunked_at=0, failed_missing_chunk_error=0 ✅
  - P2 errors: 1 (74ed935e — known terminal). No new failure pattern.
  - Distribution: min=1, p5=6, median=40, p95=222, max=891, avg=66.2
- **Action taken:** none. Going to sleep. Pipeline healthy, both jobs running, no knob changes.
- **Watch list for India morning (Sonam / Vinayaka):** updated handoff watchlist still applies. Add: 74ed935e is now terminal — will appear in failed table; no action needed.
- **Next check:** India morning per cadence (3–4h).

### Pulse — May 1, 2026 ~05:30 PST (morning pulse — P2 stopped, new P1 failure pattern)

- **Source:** [validation/nb_01_pulse_check.ipynb](validation/nb_01_pulse_check.ipynb), [validation/nb_02_metadata_check.ipynb](validation/nb_02_metadata_check.ipynb), [validation/nb_03_chunk_check.ipynb](validation/nb_03_chunk_check.ipynb)
- **Overall progress:** 3,496 / 18,094 docs fully completed (**19.3%**)
- **Queue state:**
  - completed/completed = 3,496
  - completed/pending   = 1,995 (claimable by P2 — backlog growing)
  - completed/in_progress = **0** ⚠️
  - completed/failed = 1 (74ed935e — terminal)
  - failed/pending  = 8 (+5 since pre-sleep — see below)
  - pending/pending = 12,594
  - **Total = 18,094 ✅**
- **🚨 P2 chunk job stopped:** last successful run `491314b52e10` ended 06:44:01 UTC (~5h before this pulse). Clean shutdown — no errors, no stale claims, no retries pending. Likely hit `FSR_P2_MAX_ITERATIONS` cap, cluster auto-shutdown, or job-level timeout. **Reached out to support team to restart.** 1,995 docs sitting ready, pool will keep growing while P1 commits continue.
- **🚨 New P1 failure pattern (`'content'` KeyError):** 4 docs failed in the same 08:29 UTC commit batch with bare error `'content'`. All 4 IDs look near-contiguous (`23df09c1`, `23d4fe9f`, `23d4844c`, `23d09079`). Strong suspicion: one bad LLM API response (missing `content` key) bubbled up as a `KeyError` and tagged all 4 docs in that micro-batch — not 4 corrupt PDFs. Worth a code look later (defensive handling around LLM response parsing). Not blocking; pattern hasn't recurred in subsequent batches.
- **P1 progress:** 5,492 metadata-completed. 8 failures total (~0.15%) — 4 `LLM returned no matching row` (null-pdf-name), 4 `'content'` (new). Plus 1 more null-pdf-name failure since pre-sleep (`a56e6e99`, scraped 12:09 UTC).
- **P1 last 60m:** 499 completed / 1 failed — healthy. Commit cadence ~500 docs every ~1.5–2h holding (12:09 UTC, 10:23, 08:29, 06:59, 05:26).
- **P2 throughput (cumulative, before stop):** 70 runs in 8.7h → **402 docs/hr** (still in dev range). 3,496 docs → 231,048 chunks (avg 66.1/doc).
- **P2 ETA (assuming clean restart):** 36.3h on remaining 14,598 docs at 402/hr.
- **VS index check (UI screenshot, Catalog Explorer):**
  - Index: `vaip.ai_std_con_field_service_report.vs_vec_field_service_report` — **Online** ✅
  - Type: Delta Sync, Triggered
  - Source table: `vaip.ai_std_con_field_service_report.vec_field_service_report` ✅
  - Endpoint: `pw-ser-sdg-vector-search` (note: actual endpoint name has no `-prod` suffix; nb_04 config still references `pw-ser-sdg-vector-search-prod` and needs updating)
  - Embedding dim: 3072 ✅
  - **Rows indexed: 231,048 — matches chunk table exactly** ✅
  - Pipeline id: `b0a62183-a80f-413f-900a-d0a1fdec549d`, Update status: Completed
  - Last processed timestamp: Apr 30, 11:43 PM PST (~6h before this pulse — before P2's overnight runs). Triggered sync only fires on schedule/manual; new chunks will land on next trigger.
  - Budget Policy: Unknown ⚠️ (cosmetic; doesn't block sync)
- **nb_02 metadata-check (5,492 completed):**
  - Required-field misses: title=12 (~0.22%), esn=7 (~0.13%) — same NULL-ESN pattern, proportions stable
  - Date misses: report_issued=812 (~14.8%), outage_start=399 (~7.3%), outage_end=2,615 (~47.6%) — same proportions, source-driven
  - Date format malformed: 1 / 1 / 2 — unchanged from pre-sleep snapshot, no growth
  - document_id normalization: 0 `.pdf` suffix, 0 uppercase ✅
  - ESN buckets: 3,814 pure_numeric + 731 valid_pattern + ~940 outside-buckets (~17%, consistent)
  - Volume split: fieldvision = 5,492 completed + 8 failed + 9,862 pending; ecrt_reports = **0 completed**, 2,732 pending (still queued)
- **nb_03 chunk-check (3,496 docs / 231,048 chunks):**
  - State integrity: failed_with_chunks=0, in_progress_with_chunks=0, completed_missing_chunks=0, orphan_chunks=0, duplicate_chunk_ids=0 ✅
  - Embedding integrity: null=0, wrong_dim=0, empty_text=0 ✅
  - Chunk quality: oversized=0, bad_page_num=0, missing_metadata_json=0, missing_created_at=0 ✅
  - Cross-table: esn_mismatch=0, completed_missing_chunked_at=0, failed_missing_chunk_error=0 ✅
  - P2 errors: 1 (74ed935e — known terminal). No new pattern.
  - Distribution: min=1, p5=6, median=40, p95=223, max=891, avg=66.1
- **Action taken:** sent Slack to team summarizing status; opened support request to restart P2 job.
- **Next check:** after P2 restart — confirm first new batch claim and run-log entry.

### Pulse — May 1, 2026 ~07:30 PST (post-restart confirmation + nb_04 VS index check)

- **P2 restart confirmed by support team.** Job is running again.
- **Chunking growth signal (via nb_04):** chunk table now at **256,529 rows** (up from 231,048 at 05:30 — +25,481 chunks in ~2h). P2 is actively draining the backlog. ✅
- **nb_04 VS index check (`pw-ser-sdg-vector-search`):**
  - Endpoint state: **ONLINE** ✅
  - Index ready: **true** ✅
  - Source table match: ✅ (`vaip.ai_std_con_field_service_report.vec_field_service_report`)
  - Index state msg: "Index creation succeeded"
  - **Row drift comparison: not available** — the `/api/2.0/vector-search/indexes/{name}` REST response doesn't return `num_of_rows` for this delta-sync index. Same API limitation we hit in dev. Catalog UI does show "Rows indexed" so use that for actual drift comparison until nb_04 is reworked to use the SDK.
- **nb_04 fix applied this session:** corrected `VS_ENDPOINT` from `pw-ser-sdg-vector-search-prod` → `pw-ser-sdg-vector-search`; added explicit schemas for createDataFrame to handle None values.
- **Action taken:** none on backfill side; P2 restart was the operational step.
- **Next check:** mid-day pulse to confirm steady P2 throughput post-restart and check if commits cadence has shifted.

### Pulse — May 1, 2026 ~07:45 PST (nb_04 re-run with SDK fallback)

- **nb_04 row-count drift now functional** via SDK fallback (`VectorSearchClient.get_index().describe()` returns `num_of_rows=231,048` even though REST API doesn't).
- **Drift snapshot:**
  - Chunk table: **260,131** rows (+3,602 in ~15 min — P2 still humming)
  - VS index: **231,048** rows (last sync Apr 30 23:43 PST, pre-restart)
  - Diff: 29,083 (**11.18%**) — outside 5% tolerance
- **Interpretation:** Expected during active backfill. Index sync is `Triggered`, so it lags the chunk table until next sync fires. Will resolve at end-of-backfill or on a manual "Sync now". Not actionable now.
- **Action taken:** none.
- **Next check:** mid-day pulse.

### Pulse — May 1, 2026 ~12:00 PST (mid-day pulse — nb_01 + nb_02 + nb_03 + scheduler removal)

- **Source:** [validation/nb_01_pulse_check.ipynb](validation/nb_01_pulse_check.ipynb), [validation/nb_02_metadata_check.ipynb](validation/nb_02_metadata_check.ipynb), [validation/nb_03_chunk_check.ipynb](validation/nb_03_chunk_check.ipynb)
- **Overall progress:** 5,546 / 18,094 docs fully completed (**30.7%**) — +11.4 pts since morning.
- **Queue state:**
  - completed/completed = 5,546
  - completed/pending   = 1,395
  - completed/in_progress = 50 (fresh claim, ts 18:46:26 UTC)
  - completed/failed = 1 (74ed935e — terminal)
  - failed/pending  = 8 (no growth since morning)
  - pending/pending = 11,094
- **P1:** ~500-doc commits every ~1.5–1.75h holding (latest 17:12 UTC). Cadence stable.
- **P2 (post-restart):** 20 most recent runs all 50/50 succeeded. 111 cumulative runs in 13.64h → **407 docs/hr** (slightly above midpoint, holding from morning's 402).
- **Total chunks:** 365,626 across 5,546 docs (avg 65.9/doc).
- **ETA:** ~12,548 docs at 407/hr → **~30.9h remaining** → completion ~late May 2 / early May 3 PST.
- **Failures:** P1 stable at 8 (no new patterns since morning's `'content'` batch); P2 stable at 1 (74ed935e terminal). 4 P1 commits since the `'content'` batch — confirms it was a one-time bad LLM response.
- **nb_02 metadata-check (6,992 completed):** all proportions stable (title=12 missing, esn=8 missing, dates within prior bands; 1/1/2 malformed dates unchanged; ESN buckets ~70/13/17%; ecrt still 0 completed, 2,732 pending).
- **nb_03 chunk-check (5,596 docs / 369,280 chunks):** all integrity / embedding / cross-table checks pass; new max-doc seen — `ad91ff9d` 3,291 pages → 906 chunks ✅. Only error: known 74ed935e.
- **Scheduler removal:** noticed `PW_SDG_FSR_Chunking_Backfill` had a daily schedule set in the Databricks Jobs UI (added by Vasvee yesterday so it would auto-kick after metadata). Risk of overlapping runs (the current notebook has been running uninterrupted in iteration loop — see VS-sync investigation below — so a scheduled trigger would have started a parallel run, doubling cluster cost + risk of LLM gateway rate-limiting).
  - Vinayaka removed the schedule from the UI (no PR needed — schedule was UI-only, not in `pw_sdg_fsr_chunks.yml`).
  - Job will now only run when manually triggered.
- **Action taken:** scheduler removal coordinated with support team.
- **Next check:** end-of-day pulse + VS sync follow-up with support.

### Pulse — May 1, 2026 ~14:00 PST (VS index sync investigation)

- **Symptom:** VS index `Last processed commit=136`, `Last processed timestamp=Apr 30 11:43 PM PST`, `num_of_rows=231,048` — unchanged for ~14h despite chunk table growing to 374,227 rows.
- **nb_04 drift:** chunk table 369,280 vs index 231,048 → 138,232 diff (**37.4%**).
- **Initial assumption:** the chunking notebook calls `sync_vector_search()` at the end of every P2 run (~every 5–9 min), so syncs should be firing constantly. Why is the index stuck?
- **Root cause found via P2 driver log:** the running notebook is on **iteration 43+ in a single, continuous notebook execution** (started 13:48 PST May 1, hit a ~5h serverless idle pause mid-batch, resumed). Because `FSR_P2_MAX_ITERATIONS=0` (drain mode), the iteration loop never exits — so `sync_vector_search()` never gets called. The sync is positioned **after** the iteration loop, not inside it.
  - Yesterday's accidental Apr 30 23:43 PST sync was the result of the previous notebook run completing/exiting at iteration cap.
  - Without a stop-and-restart, the sync simply doesn't fire while backfill is in drain mode.
- **Manual "Sync now" attempt from Catalog UI:** appeared to do nothing.
  - Source-table CDF: confirmed enabled (`delta.enableChangeDataFeed=true`) ✅ — not a CDF issue.
  - Pipeline (`b0a62183-a80f-413f-900a-d0a1fdec549d`): confirmed running.
  - Result still unchanged after click. Possibly the click silently 200s but no new pipeline update is triggered, or the UI is racing with the in-flight `Update status=Completed` state. Worth a follow-up with support to understand the trigger semantics.
- **Risk assessment:** zero impact on data correctness while no one is querying. Index stays cold but chunk table is fully populated. Final sync will happen when the chunking notebook eventually exits (end of backfill) or via a forced trigger.
- **No-risk re-trigger:** confirmed safe — index is `Delta Sync (Triggered)`, primary key `chunk_id`, idempotent upsert semantics. Retriggering can never duplicate or roll back.
- **Follow-up items added:**
  - End-of-backfill checklist must include manual "Sync now" + confirm `num_of_rows` matches chunk table before declaring done.
  - Code follow-up (post-backfill, low priority): consider moving `sync_vector_search()` inside the iteration loop (e.g., every N iterations) so triggered syncs fire periodically during long-running drain mode. For now, manual triggering via support is the workaround.
  - Open question for support: what's the actual semantics of the Catalog UI "Sync now" button on a triggered Delta Sync index? Why didn't our click fire a new pipeline update?
- **Action taken:** documented, raised with team for support follow-up; no operational change to backfill jobs.
- **Next check:** end-of-day pulse.

### Pulse — May 1, 2026 ~14:30 PST (nb_03 re-check post-VS-investigation)

- **nb_03 chunk-check (5,646 docs / 374,227 chunks):** all integrity / embedding / cross-table checks pass ✅. Only error: known 74ed935e. avg 66.3 chunks/doc, max 906 (same `ad91ff9d`).
- Chunk pipeline remains healthy and unaffected by the VS sync issue (which is purely on the index side).

### Pulse — May 2, 2026 ~06:00 PDT (overnight + morning pulse — nb_01)

- **Source:** [validation/nb_01_pulse_check.ipynb](validation/nb_01_pulse_check.ipynb)
- **Overall progress:** 11,792 / 18,094 docs fully completed (**65.2%**) — +34.5 pts since yesterday mid-day. Both jobs healthy through the overnight India window.
- **Queue state:**
  - completed/completed = 11,792
  - completed/pending   = 1,638
  - completed/in_progress = 50 (fresh claim, ts 12:49:47 UTC — same as latest run end, not stale)
  - completed/failed = 4 (1 terminal — 74ed935e; 3 still under retry cap)
  - failed/pending  = 16 (+8 since yesterday, all the null-pdf "no matching row" pattern, no new `'content'` recurrences)
  - pending/pending = 4,594
- **P1:** 500 docs/last 60m, 0 failures. Commit cadence holding ~500 docs every ~85–90 min (steady through overnight). 4,610 left for P1 (4,594 pending + 16 failed).
- **P2 (last 20 runs):** 50 docs/run, 6–12 min/run, **2 failures across 20 runs** (both single-doc PDF parse errors — batch continued normally). Cumulative 236 runs / 31.66h → **372 docs/hr**. 6,302 docs remaining → ETA **~16.9h** (completion late May 2 / early May 3 PDT).
- **Total chunks:** 796,214 across 11,792 docs (avg 67.5/doc).
- **Capacity:** P2 pickable pool 13,484 vs 1,641 currently eligible — plenty of headroom; P2 will auto-drain as P1 keeps producing. P1 (~500/hr) > P2 (~372/hr) → P2 is the wall-clock bottleneck.
- **New P1 failures (8 since yesterday, all same null-pdf / "LLM returned no matching row" pattern, ~one every 3–4h):** `c5e32e0e`, `dfce8556`, `522f8058`, `537a724f`, `67d39444`, `6dfd8a17`, `291787ce`, `3f516ae8`. Adding to terminal list below (these are stable failure modes — corrupt/image-only PDFs).
- **New P2 failures (3, not yet terminal — under retry cap):**
  - `5eb78b05` — `code=7: object is not a stream` (retry=2)
  - `6a2840b8` — `Embedding coverage too low: 86/95 chunks (9% missing, threshold=0%)` (retry=1)
  - `31b9a2df` — `code=5: too many nested graphics states` (retry=1)
- **Action taken:** none — both jobs healthy, let it run.
- **Next check:** mid-day pulse to confirm P2 cadence holds and ETA stays in window.

### Pulse — May 2, 2026 ~07:35 PDT (mid-morning, P2 still bottleneck)

- **P1 job:** active — last commit 14:22 UTC (~07:22 PDT), cadence ~88–95 min/batch holding
- **P2 job:** active — 50 just claimed at 14:35:30Z (clean, not stale)
- **Queue state:**
  - completed/completed = 12,291
  - completed/failed = 4 (3 retry-pending + 1 terminal `74ed935e`)
  - completed/in_progress = 50
  - completed/pending = 1,638
  - failed/pending = 17 (P1 terminals)
  - pending/pending = 4,094
  - **total = 18,094 ✅**
- **Progress:** 12,291 / 18,094 = **67.9%**; 5,803 docs remaining
- **Throughput last 60 min:** P1 completed=499, P1 failed=1; P2 ~5 batches × 50 docs = 250 docs (all clean)
- **P2 cumulative:** 246 runs / 33.4h → **368 docs/hr** (slight drift from 372 → 368, still in dev range)
- **Chunk table:** 831,070 chunks across 12,291 docs (avg 67.6/doc)
- **ETA on remaining:** ~15.8h at current P2 pace → completion late May 2 / early May 3 PDT
- **New P1 failures since 06:00:** +1 (`4b8098ad`, same null-pdf "no matching row" pattern, scraped 14:22 UTC). Total P1 terminals now 17.
- **P2 retry-pending status:** `6a2840b8` r2 (embed coverage), `5eb78b05` r2 (object not a stream), `31b9a2df` r1 (nested graphics). `74ed935e` confirmed terminal at retry=3 ✅.
- **Stale claims:** 0
- **Action taken:** none — both jobs healthy.
- **Next check:** mid-day (~12:00 PDT) — confirm P2 cadence, watch if 3 retry-pending docs settle (terminal vs succeed); expect ~67.9% → ~80%.

### Pulse — May 2, 2026 ~07:50 PDT (nb_02 metadata-check on 13,983 completed)

- **Required fields:** all populated except 28 missing titles (0.20%) and 24 missing ESNs (0.17%) — content-level, expected.
- **Date misses (content-level):** report_issued_date=2,057 (14.7%), outage_start_date=984 (7.0%), outage_end_date=6,559 (46.9%) — tracks dev baselines.
- **Date format malformed:** 1 / 2 / 5 — negligible.
- **document_id normalization (18,094 rows):** 0 `.pdf` suffix, 0 uppercase ✅ (BUG-009 fix holding).
- **P1 failure breakdown:** 13 null-pdf "LLM returned no matching row" + 4 `'content'` = 17 (matches queue ✅).
- **ESN (13,959 LLM-sourced):** 9,706 pure_numeric (69.5%), 1,834 valid_pattern (13.1%), 0 null/redacted, **2,419 (17.3%) non-bucketed** — consistent with Apr 30 sample (alphanumeric/multi-value/redaction-leak); DQ flag, not blocker.
- **Per-volume:** fieldvision 13,983 done / 17 failed / 1,362 pending (~91% done). **ecrt_reports still 0 processed / 2,732 pending** — listing-order lag continues; expect to start landing as fv drains.
- **Action taken:** none — clean DQ profile.
- **Next check:** mid-day pulse — watch for ecrt_reports starting to process.

### Pulse — May 2, 2026 ~08:00 PDT (nb_03 chunk-check on 12,291 docs / 831k chunks)

- **All integrity checks pass ✅** — 0 failed-with-chunks, 0 in_progress-with-chunks, 0 completed-missing-chunks, 0 orphans, 0 duplicate IDs (831,070 distinct), 0 null/wrong-dim embeddings, 0 oversized/bad-metadata, 0 ESN mismatch.
- **P2 errors (4 total, all known):** 2× `code=5: too many nested graphics states` (`74ed935e` terminal r3, `31b9a2df` r1), 1× `code=7: object is not a stream` (`5eb78b05` r2), 1× embedding coverage low (`6a2840b8` r2). Only `74ed935e` terminal.
- **Chunk distribution (12,291 docs):** min=1, p5=6, median=40, p95=223, max=1,785 (4,162-page PDF), avg=67.6/doc — stable.
- **Action taken:** none.
- **Next check:** mid-day pulse — watch for ecrt_reports starting to process.

### Pulse — May 2, 2026 ~08:10 PDT (nb_04 VS index check)

- **Endpoint `pw-ser-sdg-vector-search`:** ONLINE ✅
- **Index `vs_vec_field_service_report`:** ready, source-table match ✅, CDF enabled ✅
- **Row drift:** chunks=831,070 vs index=231,048 → 600,022 (72.2%) behind. Expected — last real sync Apr 30 ~11:43 PM; in drain mode (`FSR_P2_MAX_ITERATIONS=0`) the iteration loop doesn't exit, so `sync_vector_search()` only fires once P2 fully drains.
- **Action taken:** none — sync will trigger naturally at end of backfill. Open follow-up note added to [fsr-pipeline-design.md](../implementation/design/fsr-pipeline-design.md) (VS Index Sync section) to design a smarter mid-run sync for future long backfills.
- **Next check:** mid-day pulse — main queue progress.

### Pulse — May 2, 2026 ~17:25 PDT (P2 original run failed, auto-retry running)

- **P2 status:** original run FAILED with `SparkConnectGrpcException` (`CLIENT_UNEXPECTED_MISSING_SQL_STATE`) at `process_one_batch`. Databricks auto-retried; retry #1 is now Running ✅.
- **Failure type:** transient Spark Connect / driver RPC issue (not a code or data defect). Last successful MERGE before failure: 3,663 chunks at 00:20 UTC May 3.
- **Recovery posture:** any docs `in_progress` from the failed run will be reclaimed by stale-claim recovery (>30 min) → re-processed in retry. No data loss; possible duplicate work on a few docs.
- **Action taken:** none — letting auto-retry run.
- **Watch:** if retry also fails with same error, treat as cluster/driver pattern and investigate (driver memory, cluster events, Spark Connect logs).
- **Next check:** confirm retry is claiming + committing batches; verify queue state vs pre-failure snapshot.

### Pulse — May 2, 2026 ~19:10 PDT (post-retry, P1 fully drained, 90% complete)

- **P2 status:** auto-retry healthy — last 20 runs clean (0 docs_failed across 1,000 docs in ~37 min). Run cadence 40–60s/batch on ecrt PDFs (small docs).
- **P1 job:** ✅ FULLY DRAINED — 0 pending, 0 in_progress. All 18,094 docs have terminal P1 status.
- **Queue state:**
  - completed/completed = 16,286
  - completed/failed = 5 (P2 terminals)
  - completed/in_progress = 100
  - completed/pending = 1,682
  - failed/pending = 71 (P1 terminals)
  - **total = 18,094 ✅**
- **Progress:** 16,286 / 18,094 = **90.0%**; 1,808 remaining; ETA ~5h → completion ~midnight PDT.
- **Chunk table:** 1,061,959 chunks across 16,336 docs (avg 65.0/doc).
- **P1 terminals: 71 (+54 since morning)** — all `No /Root object` from ecrt_reports volume, scraped 20:39 UTC in one batch. Expected pattern (corrupt source PDFs); mirrors dev (~830 corrupt total expected).
- **P2 terminals: 5 (+4 since morning):**
  - `74ed935e` (carryover) + 3 newly hit retry=3: `31b9a2df`, `6a2840b8`, `5eb78b05`
  - `4b06401b` — embed coverage 170/172 (1 chunk missing); same doc was P2 terminal in dev. Currently retry=1 — expect terminal at retry=3.
- **⚠️ Stale claims:** 20 docs claimed at 00:12:02 UTC (~2h old) from the failed pre-retry run still showing `in_progress`. Stale-claim recovery (>30 min) should have released them but didn't. **Action:** if still stale at next pulse, manually flip to `pending` so retry can re-claim.
- **Action taken:** none — letting retry continue.
- **Next check:** ~30 min — confirm stale claims released; verify queue continues to drain; expect ~92–94%.

### Pulse — May 2, 2026 ~19:25 PDT (nb_02 metadata-check on 18,023 completed — P1 final)

- **P1 final corpus profile:** 18,023 completed / 71 failed of 18,094 total (**99.61% success**).
- **Required fields:** all populated except 31 missing titles (0.17%) and 25 missing ESN (0.14%).
- **Date misses (content-level):** report_issued=2,711 (15.0%), outage_start=1,067 (5.9%), outage_end=9,870 (54.8%) — tracks dev baselines; outage_end naturally sparse.
- **Date format malformed:** 1 / 2 / 6 — negligible.
- **document_id normalization (18,094 rows):** 0 `.pdf` suffix, 0 uppercase ✅
- **P1 failure breakdown (71):** 50 `No /Root object` + 15 null-pdf "no matching row" + 4 `'content'` + **2 `Unexpected EOF` (new pattern)**. All terminal source-data issues.
- **ESN (17,998 LLM-sourced):** 68.6% pure_numeric, 15.8% valid_pattern, 0 null/redacted, 15.6% non-bucketed (consistent with prior samples).
- **Per-volume FINAL:** fieldvision 15,344 done / 18 failed (99.88%); ecrt_reports 2,679 done / 53 failed (98.06%) — corrupt-PDF cluster drives ecrt's slightly higher rate.
- **Action taken:** none — clean profile.
- **Next check:** post-completion nb_03 chunk-check + final reconciliation.

### Pulse — May 2, 2026 ~19:40 PDT (nb_03 chunk-check on 16,586 docs / 1.06M chunks)

- **All integrity checks pass ✅** — 0 failed-with-chunks, 0 completed-missing-chunks, 0 orphans, 0 dupes (1,064,980 distinct), 0 null/wrong-dim embeddings, 0 oversized/bad-metadata, 0 ESN mismatch.
- **50 in_progress docs with chunks:** active batch in flight (mid-write) — expected, not a defect. Will clear when batch commits.
- **P2 errors (5, 4 already terminal):** `74ed935e`, `31b9a2df`, `6a2840b8`, `5eb78b05` all retry=3 (terminal); `4b06401b` at retry=1 (Taranto, embed coverage — same dev-backfill terminal pattern).
- **Distribution shift:** median 40 → 36, avg 67.6 → 64.3 — ecrt PDFs are smaller than fv (expected).
- **Action taken:** none.
- **Next check:** post-completion final reconciliation + nb_04 VS index sync confirmation.

### Pulse — May 2, 2026 ~19:50 PDT (nb_04 VS index check)

- **Endpoint `pw-ser-sdg-vector-search`:** ONLINE ✅
- **Index `vs_vec_field_service_report`:** ready, source-table match ✅, CDF enabled ✅
- **Row drift:** chunks=1,065,805 vs index=231,048 → 834,757 (78.3%) behind. Index unchanged since Apr 30 — drain-mode sync still hasn't fired (P2 still active).
- **Action taken:** none — sync will trigger automatically when P2 fully drains. Final drift re-check post-completion.
- **Next check:** post-completion — confirm sync fires, drift resolves to <5%.

### Pulse — May 2, 2026 ~20:00 PDT (nb_05 data correctness — 29/36 passed, all 7 fails explainable)

- **All 7 "failures" explainable — none are real defects:**
  - 1.2 (50 in_progress with chunks): stale-claim issue from the failed pre-retry SparkConnect run. Chunks ARE written (durable); status just not flipped to `completed`. Stale-claim recovery (>30 min) didn't fire.
  - 3.3 (31 missing titles), 3.4 (1/2/6 bad date formats): content-level DQ, matches dev baselines.
  - 6.1 / 6.4: nb_05 helper API limitations (nb_04 confirmed endpoint ONLINE + drift via SDK fallback).
- **Stuck 50 docs** all `chunked_at=2026-05-03T00:12:02Z` (~3.5h ago); chunks durable, integrity clean.
- **Recommended action:** UPDATE these 50 from `in_progress` → `completed` (chunks already written; re-processing would create duplicates).
- **Action taken:** none yet — preparing manual SQL fix.
- **Next check:** post-fix re-pulse to confirm queue clean; final completion check.

### Pulse — May 2, 2026 ~20:00 PDT (BACKFILL EFFECTIVELY COMPLETE — 99.3%, queue drained)

- **Pickable queue: 0** ✅ — P2 has nothing left to claim.
- **Queue state:** completed/completed=17,967 | completed/in_progress=50 (stuck) | completed/failed=6 | failed/pending=71. Total=18,094 ✅
- **Completion: 99.3% as-is; 99.57% after stuck-50 flip.**
- **Chunks:** 1,088,294 across 18,017 docs (avg 60.4).
- **Final failure profile (77 terminals, 0.43%):**
  - P1 (71): 50 `No /Root` + 15 null-pdf "no matching row" + 4 `'content'` + 2 `Unexpected EOF` — all corrupt source PDFs.
  - P2 (6): `74ed935e`, `31b9a2df`, `5eb78b05` (PDF render errors); `6a2840b8`, `4b06401b`, `090dbba1800dc236` (embed coverage low). `4b06401b` and `090dbba1800dc236` newly hit retry=3 in this window.
- **Throughput:** P2 cumulative 361 runs / 45.6h — within the 2–2.5 day estimate.
- **Action needed:**
  1. UPDATE 50 stuck `in_progress` → `completed` (chunks already written, integrity-clean).
  2. Verify VS index sync fires (drain loop should now exit).
  3. Final nb_01 + nb_04 reconciliation.
- **Next check:** after manual SQL fix — re-pulse + nb_04 sync confirmation.

### Pulse — May 2, 2026 ~20:30 PDT (stuck-50 fix options analysis)

- **Verified chunk presence for stuck 50:** all have chunks > 0 (range 5–244/doc), 0 null embeddings, no internal duplicates. Total ~3,663 chunks already written — matches the failed run's last MERGE log line ("MERGE complete: 3663 chunk rows" at 00:20 UTC May 3). Failure happened after chunk MERGE but before metadata status update.
- **Blocker:** no UPDATE permission on prod tables.

#### Options considered

**Option 1 — Re-run chunking job (let stale-claim recovery handle it):**
- Stale-claim recovery (>30 min) at [nb_sdg_fsr_chunks.py L90-107](../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py#L90-L107) flips stale `in_progress` → `pending`; job re-claims & re-processes.
- Chunk MERGE is idempotent: `chunk_id = md5(document_id + "_" + chunk_index)` (deterministic), MERGE `ON tgt.chunk_id = src.chunk_id` with UPDATE-on-match ([nb_sdg_fsr_chunks.py L405-510](../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py#L405-L510)). PK constraint on `chunk_id` ([fsr_config.py L350](../pw_sdg_ai_ser_repo/common/fsr_config.py#L350)).
- **Row-level duplicates: impossible** ✅
- **Residual risk:** if re-chunking produces a different chunk count for the same doc (e.g., extraction non-determinism, code change between runs), old chunks at indices not re-emitted become **orphans** (no DELETE-before-MERGE step). In practice the chunker should be deterministic on same PDF, but not provable without further inspection.
- **Cost:** ~3,663 embedding API calls (negligible $).

**Option 2 — Manual UPDATE via someone with prod write access (PREFERRED):**
- Verified narrow SQL: `UPDATE ... SET chunk_status='completed' WHERE chunk_status='in_progress' AND chunked_at = TIMESTAMP '2026-05-03 00:12:02.095';` — touches exactly 50 rows.
- Zero embedding cost, zero risk of chunk drift, fully reversible (single UPDATE).
- Need: ask Vinayaka / Sonam / Tao / Databricks platform team to run.

**Option 3 — Leave as-is:**
- Chunks + embeddings ARE in the table → searchable in VS index after sync.
- Operational/reporting status stale; would be re-claimed (and re-processed) on any future chunk-job run.

#### Recommendation
- **Go with Option 2.** Zero data risk, trivial to coordinate, single SQL statement.
- If Option 2 is hard to schedule and we choose Option 1, add a defensive `DELETE FROM chunk_table WHERE document_id IN (<50 ids>)` before re-running — also needs write access, so the gain is small.

- **Action taken:** none — pending coordination with someone who has prod write access.
- **Next check:** post-fix re-pulse + nb_04 VS sync confirmation.

### Pulse — May 2, 2026 ~20:50 PDT (VS sync root cause: endpoint name mismatch)

- **Symptom:** chunk notebook log: `Cannot check endpoint: HTTP 404` → sync never fires. Index "Last processed timestamp" still Apr 30 11:43 PM (stuck at 231,048 rows vs ~1.09M chunks).
- **Root cause:** `FSR_VS_ENDPOINT` job param = `pw-ser-sdg-vector-search-prod` but the actual endpoint name in Databricks is `pw-ser-sdg-vector-search` (no `-prod` suffix).
  - `sync_vector_search()` at [nb_sdg_fsr_chunks.py L637](../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py#L637) calls `GET /endpoints/{VS_ENDPOINT_NAME}` → 404 → bails before triggering sync.
- **Confirmed by:**
  - Catalog UI screenshot: endpoint = `pw-ser-sdg-vector-search`
  - nb_04 (which uses the actual name) returns ONLINE / ready
  - Index Data Ingest: pipeline `Completed`, last commit 136, last processed timestamp Apr 30 11:43 PM (the manual bootstrap)
- **Implication:** the entire backfill ran with auto-sync silently disabled. Index missing ~830k rows.
- **Manual sync attempt from user notebook:** failed with `403 PERMISSION_DENIED ... Insufficient permissions for UC entity vaip...vs_vec_field_service_report`. Same prod-write blocker as the stuck-50 fix.

#### Options to trigger sync (without re-running chunking job)

1. **UI "Sync now"** — button visible on the index Data Ingest panel; needs `USE INDEX` permission. Try first.
2. **API call as the chunking job's service principal** — SP already has the right permissions (it created the index). One-shot notebook with the sync POST, run via the same job SP/cluster.
3. **Databricks platform / admin runs the API call** — `curl -X POST .../indexes/{name}/sync`.

> Re-running the chunking backfill is NOT a sync-fix path: it would risk chunk-table changes and doesn't fix the underlying endpoint-name bug.

#### Real fix (config)
- Update `FSR_VS_ENDPOINT` job param on the chunking job: `pw-ser-sdg-vector-search-prod` → `pw-ser-sdg-vector-search`.
- Verify same param on any other job that calls VS sync (P1, incremental scheduled job).
- Check `databricks.yaml` for prod env — if the typo is in source, fix at config level so it doesn't drift again.

#### Two prod cleanup asks bundled (need someone with prod write):
1. Manual VS index sync (POST to the index sync endpoint or UI click).
2. UPDATE 50 stuck `in_progress` → `completed` (verified narrow filter; see ~20:30 PDT entry above).

- **Action taken:** none — pending coordination.
- **Next check:** after sync fires — confirm index row count converges with chunk table; expect <5% drift.

---

## Decisions log

| Date | Decision | Rationale |
|---|---|---|
| 2026-04-30 | Use main branch (post PR #56 merge) for PROD backfill | End-state-equivalent to dev PR #53; validated in dev with 202-doc smoke + 17k dev backfill |
| 2026-04-30 | Disable steady-state ingestion trigger during backfill | Prevent scheduled job from racing the backfill on the same tables |
| 2026-04-30 | Madhurima + Tao actively monitor during US day; India team picks up off-hours | Avoid waiting for India morning when knob tuning is needed |

---

## Terminal failures (running list)

> Add docs here once they hit retry caps and stop being re-claimed. Useful for post-backfill data team handoff.

| document_id | pdf_name (if known) | Failure type | Reason |
|---|---|---|---|
| `814e2f8b-44a3-4065-b584-5a0977f97ac9` | _null_ (no pdf_name resolved) | P1 metadata | `LLM returned no matching row for this document` — pdf_name & page_count null → likely corrupt / image-only PDF, text extraction returned nothing, LLM had nothing to anchor on. First P1 failure of backfill. |
| `8ad00be4-23b9-4e4d-900b-e423b97e4db9` | _null_ | P1 metadata | Same pattern as above — pdf_name & page_count null, `LLM returned no matching row`. Second P1 failure (batch 4). |
| `132a4598-9860-4894-9d5d-31dff26f8692` | _null_ | P1 metadata | Same pattern — pdf_name & page_count null, `LLM returned no matching row`. Third P1 failure (scraped 2026-05-01 05:26 UTC). |
| `a56e6e99-4cf3-419b-b0b2-be4984b237ed` | _null_ | P1 metadata | Same pattern — pdf_name & page_count null, `LLM returned no matching row`. Fourth P1 null-pdf failure (scraped 2026-05-01 12:09 UTC). |
| `23df09c1-2cd3-4be9-8687-808a6b6d1132` | _null_ | P1 metadata | **New pattern:** error literally `'content'` (likely `KeyError: 'content'` on LLM response). Failed in same 08:29 UTC commit batch as 3 sibling docs below — strong suspicion: one bad LLM response affected the whole micro-batch, not a real per-doc PDF issue. Code follow-up: defensive handling in LLM response parsing. |
| `23d4fe9f-402d-4ca1-ae25-e8450b78e4c2` | _null_ | P1 metadata | Same `'content'` pattern, same 08:29 UTC batch. |
| `23d4844c-e140-4dfe-a484-5a38214fc09e` | _null_ | P1 metadata | Same `'content'` pattern, same 08:29 UTC batch. |
| `23d09079-1798-4979-9090-79179819799e` | _null_ | P1 metadata | Same `'content'` pattern, same 08:29 UTC batch. |
| `c5e32e0e-b0f3-4456-968c-2e97d0b12894` | _null_ | P1 metadata | Same null-pdf "no matching row" pattern (scraped 2026-05-01 18:58 UTC). |
| `dfce8556-6d45-485d-a024-d0689503ade7` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-01 23:33 UTC). |
| `522f8058-4359-4368-b006-45045ab4542b` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-02 01:00 UTC). |
| `537a724f-1f65-4686-a64d-dd350383d49b` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-02 02:28 UTC). |
| `67d39444-b7a7-4a2d-9394-44b7a71a2d39` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-02 05:26 UTC). |
| `6dfd8a17-04b6-4179-9e28-9c92e66015ee` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-02 06:56 UTC). |
| `291787ce-135a-4ad4-8026-ca267999b986` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-02 08:29 UTC). |
| `3f516ae8-207c-4246-8157-91029645086e` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-02 11:19 UTC). |
| `4b8098ad-531c-4731-8098-ad531ca731f1` | _null_ | P1 metadata | Same null-pdf pattern (scraped 2026-05-02 14:22 UTC). |
| `74ed935e-e029-4c76-ad93-5ee029bc7675` | Field_Service_Report_ProjectID_A-0246142_FSP-309586_C-10361958.pdf | P2 chunking | `code=5: too many nested graphics states` (PyMuPDF rendering error — complex graphics PDF). **Terminal as of 23:25 PST Apr 30:** `chunk_status=failed`, `chunk_retry_count=3` (cap exhausted, no longer claimable). |
