# Daily standup — 6 AM

Keep it to 3 lines: **yesterday / today / blockers**. Read aloud verbatim.

Blockers = real blockers only. Follow-ups and pending replies aren't blockers.

---

## Today — Thu May 21, 2026

**Yesterday:**
- FSR: raised the hotfix PR for the vector-index sync — 30-day retention on the chunk table + a daily safety-net schedule on the sync job at 11 AM ET (after ingestion). Shared for review and put together the change-control package (ticket details, test plan, data-validation evidence).
- FSR: updated the operations guide with the production deployment flow — the General CCB Workflow reference plus a sample deployment package (Databricks PR + Airflow PR + CCB request links).
- OSA: aligned with the DS lead on priorities so the estimation work threads through cleanly.

**Today:**
- FSR: run the manual recovery on the chunk table + trigger the sync to clear the failed state; track the first scheduled run and fill in the validation evidence so the change can land.
- FSR: get back to the doc-summary changes — dev validation through to the prod push path.
- FSR: keep the open-items PRs moving (next batch from the robustness list).

**Blockers:**
- None.

---

## Wed May 20, 2026

**Yesterday:**
- FSR: dug into the vector-index sync gap — root cause is short file retention on the chunk table making the daily sync drop behind whenever it slips past the retention window. Built the fix on a hotfix branch and validated it.
- FSR: confirmed via direct query that the one consumer-flagged file is fully present in metadata, chunks, and the index — search-query mismatch on the consumer side, not a pipeline gap.

**Today:**
- FSR: raise the PR for the vector-index sync fix and walk it through change control.
- FSR: continue the operations guide write-up.
- OSA: align with the DS lead on priorities.

**Blockers:**
- None.

---

## Tue May 19, 2026

**Yesterday:**
- FSR: monitored prod and hit two issues — the metadata job failed on the run, and the vector index sync has been lagging; reached out for help on both.
- FSR: tested the doc-summary changes in dev — looking good so far.


**Today:**
- FSR: stay on the metadata job failure and the vector-index sync — push for a fix and confirm new docs are flowing through the daily cycle.
- FSR: move the doc-summary changes toward a prod push once dev validation is clean.
- FSR: start the short writeup on the new-PDF ingestion path — where files land, what picks them up, how to verify end-to-end.


**Blockers:**
- None.

---

## Mon May 18, 2026

**Yesterday (Friday):**
- FSR: closed out the missing-FSR P0 — verified all five reported ESNs are short upstream in the reference view; sent the consumer reply with the per-ESN gap and asked the data team to confirm what's needed to bring them in.
- FSR: while verifying, found that one file the consumer flagged as missing is actually fully ingested and in the vector index — likely a search-query mismatch on multi-ESN docs; opened a separate dig for today.
- FSR: also flagged that the vector index hasn't synced since May 7 (~8 days behind); opened a separate item to verify and trigger a manual sync if real.
- OSA: reviewed the data-pipelines WBS, added missing tasks based on FSR experience, and shared per-task hour estimates (H/M/L) for the team to plug into the estimation sheet. Flagged two risks separately: source-of-truth clarity on what lands in Databricks, and the data-team handshake on landing dates.

**Today:**
- FSR: dig into why the consumer can't find the one file in search even though it's in the index — check the multi-ESN row format vs how the search query is built.
- FSR: verify the vector-index sync gap, check the sync job history since May 7, and trigger a manual resync if needed; add a freshness check to the daily DQ job.
- FSR: build the open robustness items list to share for ticketing.
- OSA: incorporate any feedback that comes back on the estimates; clarify the in-flight vs planned items on the source list.

**Blockers:**
- None.

---

## Fri May 15, 2026

**Yesterday:**
- FSR: worked on the ESN resolution design.
- FSR: updated and tested the doc-summary PR.
- FSR: built a doc-summary backfill validation notebook to spot-check the run.

**Today:**
- FSR: picking up a P0 prod issue around missing FSR data — investigating root cause and impact first.
- FSR: continue ESN resolution design and follow through on doc-summary PR feedback once the P0 is in a good spot.
- FSR: runbook / handoff writeup for the data pipeline if time allows.

**Blockers:**
- None.

---

## Wed May 13, 2026

**Yesterday:**
- FSR: worked on doc-summary derivation from TOC and the multi-ESN implementation approach.
- FSR: pulled into a prod issue around missing FSRs — followed up with the requester for more information.
- FSR: aligned with Abhijeet on failure-handling — agreed to put together the open list of items needed to make the pipeline more robust.

**Today:**
- FSR: pull together the open-items list (failure handling, observability, ESN, repair tooling) so we can ticket what's missing.
- FSR: finish raising the document-summary PR; pick up multi-ESN design finalization next.
- FSR: monitor the missing-FSRs ticket for the requester's reply.

**Blockers:**
- None.

---

## Yesterday — Tue May 12, 2026

**Yesterday:**
- FSR: discussed an approach for the multi-ESN. Worked on implementaion for doc summary derivation from TOC.
- OSA: completed a first-pass review of Step 8 (auxiliaries), surfaced a doc-vs-demo gap to Mayank with 6 questions for DS.

**Today:**
- FSR: priority 1 is to raise the PR for document summary. Priority 2 is to finalize the multi-ESN design.
- Slalom promo: after GE priorities, finish and send the first draft.

**Blockers:**
- None.

---

## Template (next day)

**Yesterday:**
- FSR: …
- OSA: …

**Today:**
- FSR: …
- OSA: …

**Blockers:**
- None / …
