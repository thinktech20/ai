## 2026-05-25 (Mon · D-19 to cert)

### Morning — drop-in log

**Health:** weight **147 lbs** (back to baseline; +1 vs May 17 weigh-in of 146).

**Hours so far:**
- #4 Cert: **~1h** — Udemy course. First non-zero cert block logged since the rebuild.

**Notes:**
- No formal check-in entries logged for May 21–24 (Arch-Hive week + deck polish through the weekend). Tracker top-3 still reads "May 18–22" — needs refresh to current week.

---

## 2026-05-20 (Wed · D-24 to cert · D-2 to Arch-Hive)

### Evening — actuals

**Hours (5 buckets):**
- #1 Weight loss: 0h (no exercise; weight not measured)
- #2 GE work: ~6h — FSR VS-sync hotfix end-to-end (branch + PR raised + CCB ticket-details, test plan, data-validation evidence drafted); FSR operations guide doc work; OSA alignment with Mayank on DS priorities
- #3 Slalom promo: ~2h — Eric 1:1 at 3 pm + brand-plan staged + Tao feedback received & replies sent
- #4 Cert: 0h
- #5 Interview/POC: ~0.5h — shared insights + organized notes
- Sleep last night: not logged

**What got done:**
- [#2 FSR] **UI-22 VS sync hotfix** — branch `hotfix/vs-sync-retention-and-schedule` raised, two commits pushed (HEAD `5322f8d`): 30-day `delta.deletedFileRetentionDuration` on the chunk table + daily safety-net schedule at 11:00 ET on `PW_SDG_FSR_VS_Sync` (live on deploy, no `pause_status`, `timezone_id: America/New_York`). PR shared for review.
- [#2 FSR] CCB ticket package drafted at [`../fsr-prod-ops/comms/2026-05-20/`](../fsr-prod-ops/comms/2026-05-20/) — `vs-sync-ticket-details.md`, `vs-sync-test-plan.md` (TC-1..TC-6), `vs-sync-data-validation.md` (before/after evidence template).
- [#2 FSR] FSR operations guide doc work (continuation of runbook landed May 18). *⚠️ User flag: "actually can we do this now?" parenthetical needs clarification — see notes section.*
- [#2 OSA] Connected with **Mayank** (new contact) on DS priorities — alignment on what feeds the estimation work for the data-science layer.
- [#3a] **Tao feedback RECEIVED** — strong written note (AdHoc QA leadership, FSR pipeline initiative, design partnership, communication). Verbatim quote logged in [`promo/feedback-asks.md`](promo/feedback-asks.md); summary in [`promo/evidence-bank.md`](promo/evidence-bank.md). Email + Slack replies sent same day.
- [#3a/c] **Eric 1:1 (3 pm)** — transcript at [`promo/Eric-track/05-20-transcript`](promo/Eric-track/05-20-transcript). New asks captured into [`promo/Eric-track/brand-plan.md`](promo/Eric-track/brand-plan.md) §9. Key signals: (a) Eric confirmed visibility = #1 lever; (b) easy-cadence outreach pattern (copy-paste-replace-name Slack pings, consistency > complexity); (c) position as AI architecture SME/specialist; (d) Bree follow-up should come from me, not Eric; (e) reach out to Pragathi, Sownya Ghosh, Emanuel Ward (Databricks COE); (f) Monday West-region Leads call is a visibility channel — Eric will surface my name there; (g) capability leadership (vs delivery leadership) is the gap to surface; (h) past promotion guidance (Erica → Raya → Joshua) was kept vague — Eric making it concrete now; (i) Tao's note → Eric will add to Workday with a blurb; (j) Fruitco re-engagement is an open thread; (k) principal role = 85% util + leadership time, so either more hours or reduced delivery cycles.
- [#3c] **brand-plan.md** updated with §9 covering all the above.
- [#5] IW / POC — shared some insights + organized things (per raw log; no specific deliverable named).

**Health:** no exercise · weight **not measured** · food logged in MyFitnessPal · energy 1–10: not logged.

**New inputs:**
- New person: **Mayank** (OSA — DS priorities owner).
- Eric will write his own summary list parallel to brand-plan §6 — keep mine current.
- References for promo case bank: SD, Erica, Maxine, Matt Ngai, Maya, Pragathi, Sownya, Emanuel, plus the Fruitco mentee.

**Carry to tomorrow (Thu May 21):**
- [#2 FSR] **UI-22** — run the manual `ALTER TABLE` + Sync now in prod to recover the OFFLINE_FAILED index; confirm first scheduled run lands (11:00 ET); fill the data-validation evidence template; merge PR after CCB sign-off.
- [#2 FSR] **UI-04 doc-summary** — slipped today; get back to dev validation + prod push path.
- [#2 FSR] UI-16/17/18/19 PR raises (queue continues).
- [#3a/c] Send easy-cadence Slack pings: Bree (demo team status), Pragathi, Sownya, Emanuel — copy-paste-replace-name pattern per Eric's nudge.
- [#3c] Arch-Hive **D-2** — visuals (Slide 4 overview diagram first) + md→pptx for both decks. Talk lands Fri.
- [#4] Cert — D-24, still zero study. Hot risk.

**Anchor risk:** ⚠️ **Cert (#4) — D-24.** Plan handed off; zero blocks done across 8 days now. Mock #1 (Jun 6, D-17) is the gate.

---

## 2026-05-17 (Sun · D-27 to cert · D-13 to Slalom presentation v1)

> Light Sunday — Slalom artifact work + Sunday weigh-in. No GE work, no exercise. Cert unblock work (Udemy material shared) carried over from yesterday's plan rebuild.

### Evening — actuals

**Hours (5 buckets):**
- #1 Weight loss: 0h (rest day — no exercise)
- #2 GE work: 0h
- #3 Slalom promo: ~3h — Eugene artifact review pass + both deck skeletons
- #4 Cert: 0h study (Udemy materials handed off yesterday; D0 Foundations block still pending)
- #5 Interview/POC: 0h
- Sleep last night: not logged

**What got done:**
- [#3c] Eugene artifact — review pass on [`promo/eugene-track/artifact-outline.md`](promo/eugene-track/artifact-outline.md). 5 substantive fixes earlier today (7A.1 ESN stats, scan-quality reframe, 7B opener re-anchored on real Unit-Risk partner team, ambiguous "model" → "AI assistant", offer set 4→3 — design scaffold + combined AI-PR playbook + new AI-ops cheat-sheet).
- [#3c] Eugene deck skeleton created at [`promo/eugene-track/eugene-slides.md`](promo/eugene-track/eugene-slides.md) — 11 main + 3 backup, titles + 1-line intent each. Fill-order locked: Slide 6 → 8 → 2 → rest.
- [#3c] Arch-Hive deck skeleton created at [`promo/eugene-track/arch-hive-slides.md`](promo/eugene-track/arch-hive-slides.md) — 14 main + 3 backup. Mined `unit-risk/8. AdHoc QA Agent.pdf` + `unit-risk/FSR-pipeline-databricks.pdf` for agent + pipeline architecture; pptx was image-only (Google Slides export), logged as open-decision. Confidentiality rule baked in — no real table / field / lookup / tool names anywhere in the deck. Slide 2 framing softened (no implicit "others get it wrong" tone).
- [tracker.md](tracker.md) + [milestones.md](milestones.md) updated to reflect skeleton landing.

**Health:** no exercise · weight **146 lbs** (−1 from May 10 baseline of 147) · food logged in MyFitnessPal · energy 1–10: not logged.

**New inputs:**
- None for tomorrow's standup.

**Carry to tomorrow (Mon May 18):**
- [#2] **UI-21** consumer-search miss for `8fe0793d-...` (file in index; check multi-ESN suffix mismatch).
- [#2] **UI-22** VS index sync staleness (~8 days behind since May 7).
- [#3c] Resume slide content fill — Eugene Slide 6 first (strongest, two-column author/reviewer setup for AI-PR playbook offer).
- [#4] **D-27 cert.** Foundations decks #1–5 (2h) on Udemy. Today's planned D0 block did not happen.
- Await: Vinayaka reply on per-ESN `fsr_pdf_ref` gap (UI-20); Kaif review on OSA WBS hours; Sreedhar steer on OSA centralization + DA dep.

**Anchor risk:** ⚠️ **Cert (#4) — D-27.** Plan rebuilt yesterday against Jun 13 with 42h budget. **Zero study so far.** D-0 block today slipped. If Mon evening doesn't move on Foundations decks, this becomes the week's hot risk.

---



> Note: no `madhu-log` dumps for May 13 / May 14 — those days captured in `tracker.md` session log only.

### Morning — priorities

1. 🚨 **[#2] FSR P0 — missing FSR data prod issue.** New this morning. Investigate root cause, scope of impact, and remediation path. Pulls priority over everything else today.
2. **[#2] OSA — estimate ask (new today).** Requester pinged this morning for an effort estimate on OSA data pipelines. FSR build decomposition + a 26-step new-pipeline implementation list prepared as the sizing reference (delivered in chat). **Next:** get scope from requester (which pipelines / how many sources / deadline / audience), then map FSR phases → S/M/L per OSA pipeline.
3. **[#2] FSR — ESN resolution design + doc-summary PR.** Continue per standup — close out open design questions; address any review feedback on doc-summary PR; extend backfill validation as needed.

**Stretch / send-today:**
- [#3c] Eugene artifact user review pass on [`promo/eugene-track/artifact-outline.md`](promo/eugene-track/artifact-outline.md) → then visuals.
- Send Tao + Sreedhar Anytime-Feedback Slack DMs (drafts ready in [`promo/feedback-asks.md`](promo/feedback-asks.md)).
- [#3a] Readiness doc in Eric's template (track #2 of the Eugene 3-pack).
- **[#2] FSR runbook / handoff doc** — pending writeup for the FSR data pipeline (last in the list — pick up only if P0 + OSA estimate land cleanly).

**Anchor risk:** ⚠️ **Cert (#4) — D-29, exam Sat Jun 13.** Still zero movement; plan rebuild blocked on user sharing Udemy course + materials. With Mock #1 anchored at Jun 6 (D-22), study runway is now 3 weeks — needs to start this weekend or the Jun 6 mock becomes a no-go gate.

**New inputs:**
- 🚨 FSR P0 — missing FSR data prod issue (investigate today).
- OSA estimate ask landed today (requester / scope TBD).
- FSR runbook / handoff doc pending (lower priority).

---

## 2026-05-12 (D-0 to promo first draft · D-11 to cert)

### Morning — priorities

1. **[#2] FSR** — PR for document summary (highest GE priority today).
2. **[#2] FSR** — finalize design for multi-ESN.
3. **[#3a] Slalom promo** — finish and send first draft.

**Stretch:**
- [#4] Cert: start Week 1 only if promo draft is sent today.

**New inputs from slack/meetings:**
- Updated by user: GE priority order for today is doc-summary PR first, then multi-ESN design finalization, then promo first draft.

### Evening — actuals

**Hours (5 buckets):**
- #1 Weight loss: ~1h (treadmill, 3.28 miles, 266 cal)
- #2 GE work — FSR: 4h total (ESN work 2h, doc-summary 2h)
- #3 Slalom promo: ~2h — **initial draft done ✅**
- #4 Cert: 0h (no movement — flagged by user, exam D-11 away)
- #5 Interview/POC: 0h
- Sleep last night: TBD

**What got done:**
- [#3a] Promo — first draft shipped: Reflection (`output-docs/01_Promotion-Readiness-Reflection_DRAFT.md`), Plan (`output-docs/02_Promotion-Plan_DRAFT.md`), and a single .xlsx (`output-docs/Promo-Reflection-and-Plan_DRAFT.xlsx`) covering all 6 sheets (README, Why & Stories, 13 competency rows, Quantitative, Goals & Asks, Plan). Companion build script saved at `output-docs/build_xlsx.py`.
- [#3a] Promo — `evidence-bank.md` reordered (GEV/FSR pickup is now Story #1 — headline). All "Cross-Cutting Manager Statements" verified verbatim against EOY 2025 Manager Evaluation column and citation tag updated to `[EOY25-MgrEval]`. GE-architect-vs-Slalom-architect mix-up corrected.
- [#3a] Promo — `feedback-asks.md` created with three Slack DM drafts (Sreedhar / Pranesh / Tao) for Anytime Feedback to attach to packet.
- [#3a] Promo — `user-inputs.md` Section 2 (revenue) filled where possible: 2e populated from IW.pdf + EOY appraisal ($2–3M D&A pipeline, BayREN-anchored); 2a–2d marked TODO with named owners (SD Singh / Sreedhar / Pete Obringer) for tomorrow's manager conversation.
- [#2] FSR — ESN work 2h, doc-summary work 2h.

**Health:** treadmill ✅ · weight **147 lbs** (flat day-over-day) · energy 1–10: TBD
**Food (from `madhu-log`):** breakfast — tea, sourdough, 2 egg whites, 4 marie biscuits · lunch — baked salmon fillet, 2 cups cut veggies · snack — tea, 3 marie biscuits, 2 dates · dinner — 1 cup white peas cooked, 2 cups broccoli + celery soup, 4 almonds.

**Calories (estimated):**
- Intake: **~1,150–1,350 kcal** (lighter day than Mon — soup/veg-heavy dinner, no yogurt+dry-fruit at lunch)
- Exercise burn: **~266 kcal** (treadmill, 3.28 mi)
- Net intake: **~900–1,100 kcal**
- Confidence: medium-low (salmon fillet size + tea-with-milk vs plain unknown — could shift ~150 kcal either way). If this is the new normal, watch for sustainability — too-low intake long-term backfires on energy + sleep (Phase 1 priorities).

**Anchor risk:** ⚠️ **Cert (#4) — D-11, exam May 23.** Zero movement this week so far. Concrete plan + daily cadence needs to land tomorrow once user shares Udemy course + materials. Currently the cert plan in [`cert-prep.md`](cert-prep.md) assumes a 14-day calendar starting at D-14 — already 3 days behind that schedule. Will need to either compress (tighter daily blocks) or move the no-go gate up.

**Followups noted from user:**
- 📩 Reply to **Eugene** tomorrow — user will share his context in chat first.
- 📚 Databricks cert — user will share Udemy course + materials tomorrow → agent to build a concrete daily plan + followup cadence (anchored against May 23 exam). Track in [`cert-prep.md`](cert-prep.md) + tracker bucket #4.

**Tomorrow Top 3 (carried into May 13 morning):**
1. **[#3a] Slalom promo — manager review** — share first draft, capture his calibration on competency ratings + revenue numbers + Pursuit Lead opportunity. Update `user-inputs.md` Sections 3a/3b/3c + Section 4 ratings post-conversation.
2. **[#4] Cert (#4 anchor risk)** — once user shares Udemy course + materials, agent builds concrete daily plan in `cert-prep.md` (revised D-day schedule for D-10 → exam day, with daily blocks).
3. **[#3c] Eugene reply** — once user shares context, draft response.

**Stretch:**
- [#2] FSR — multi-ESN design close-out (if not finalized today).
- [#2] OSA — follow-up with Mayank on Step 8 if no reply yet.

---

## 2026-05-11 (D-1 to promo first draft · D-12 to cert)

### Morning — priorities

1. **[#3a] Slalom promo** — review step 8 of plan doc was the original Top 3 line; superseded by today's actual focus → set up ADO/standup workflow + start `madhu-log` → promo draft is the **evening stretch**.
2. **[#2] OSA** — Step 8 (auxiliaries) review for Mayank. ✅ Done — Slack draft saved at [`OSA/comms/2026-05-11-slack-mayank-step8-review.md`](../OSA/comms/2026-05-11-slack-mayank-step8-review.md).
3. **[#2] FSR prod** — set up ADO board view ([`ado/stories.md`](ado/stories.md) + [`ado/standup.md`](ado/standup.md)).

**Stretch (evening):**
- [#3a] Slalom promo — fill `promo/user-inputs.md` → draft Reflection + Plan → ship first draft to manager **tomorrow May 12**.
- [#3c] Eugene track — outreach (details TBD).

### Evening — actuals

**Hours (5 buckets):**
- #1 Weight loss: ~1h (treadmill, 3 miles, ~250 cal)
- #2 GE work — OSA: 4h discovery (Step 8 review shipped to Mayank)
- #3 Slalom promo: ~0.5h (Q1 + Q1a filled in `user-inputs.md`) — **draft did not happen tonight, user tired**
- #4 Cert: 0h
- #5 Interview/POC: 0h
- Sleep last night: TBD

**What got done:**
- [#2] OSA — Step 8 doc-vs-demo gap surfaced to Mayank. Slack draft saved at [`../OSA/comms/2026-05-11-slack-mayank-step8-review.md`](../OSA/comms/2026-05-11-slack-mayank-step8-review.md).
- [#2] FSR — ADO board mapped into [`ado/stories.md`](ado/stories.md) (8 stories under epic 655509). Standup script ready at [`ado/standup.md`](ado/standup.md) for Tue 6 AM.
- [meta] Roadmap restructured around 5 goal buckets. Check-in workflow rewired (`madhu-log` → agent writes).
- [#3a] Promo — Q1 (Role) + Q1a (Scope) filled in [`promo/user-inputs.md`](promo/user-inputs.md) using FSR design doc + UnitRiskAgent docs.

**Health:** treadmill ✅ · weight **147 lbs** · energy 1–10: low (user called it a night)
**Food (from `madhu-log`):** 9am — tea ×2, sourdough, 2 egg whites, 4 marie biscuits.

**Calories (estimated):**
- Intake: **~1,840 kcal**
- Exercise burn: **~250 kcal** (treadmill)
- Net intake: **~1,590 kcal**
- Confidence: medium (tea prep, yogurt type, and cup sizes can shift totals by ~200–300 kcal)

**Anchor risk:** ⚠️ **Promo first draft (May 12)** — tonight's drafting window lost. Tomorrow needs the full sequence: finish `user-inputs.md` → Reflection → Plan → ship. Tight but doable if Tue daytime + evening both used.

**Tomorrow Top 3 (carried into May 12 morning):**
1. **[#3a] Slalom promo first draft to manager** — finish `user-inputs.md` Q1b–Q4 → draft Reflection (start with Deliver Exceptionally) → draft Promotion Plan → ship.
2. **[#2] FSR** — sync with Pranesh, start doc-summary script (parent story 661320), decide whether to fold into metadata scraping.
3. **[#2] OSA** — follow up with Mayank on Step 8 questions, ask about umbrella story.

# Check-ins — daily log

Lightweight log to keep [`roadmap.md`](roadmap.md) honest. Goals = the 5 buckets in roadmap.md. Newest entry on top.

## How this works (low effort by design)

The user dumps raw notes into [`madhu-log`](madhu-log) — freeform, fast, no schema. The agent reads `madhu-log` and produces formatted entries here.

**Morning ritual (~2 min for user):**
1. User pastes any new slack/meeting inputs from the morning into chat.
2. Agent reads yesterday's `madhu-log` + today's roadmap anchors + new inputs → produces:
   - Today's **Top 3** (priority, with bucket #)
   - Standup script at [`ado/standup.md`](ado/standup.md) (GE work only)
   - Any anchor-risk flags

**Evening ritual (~3 min for user):**
1. User updates `madhu-log` with the day's actuals (hours, food, weight, what got done — rough is fine).
2. Agent writes the formal evening entry here and updates [`health.md`](health.md) + [`tracker.md`](tracker.md) as needed.

**The user should never have to format a check-in entry by hand.** If the workflow drifts that way, fix it.

---

## Schema per day (what the agent fills in)

```
## YYYY-MM-DD (D-NN to next anchor: <anchor>)

### Morning — priorities
1. [#bucket] ...
2. [#bucket] ...
3. [#bucket] ...
Stretch: ...
New inputs from slack/meetings: ...

### Evening — actuals

**Hours (5 buckets):**
- #1 Weight loss (gym/walk): __h
- #2 GE work: __h
- #3 Slalom promo: __h
- #4 Cert: __h
- #5 Interview/POC: __h
- Sleep last night: __h

**Calories (estimated):**
- Intake: __ kcal
- Exercise burn: __ kcal
- Net intake: __ kcal

**What got done:**
- [#bucket] ...

**Health:** workout ✅/❌ · weight __ lbs (Sun) · energy 1–10 · caffeine cutoff __

**Anchor risk:** ✅ on track / ⚠️ <which + why> / 🔴 <which + replan trigger>

**Tomorrow Top 3:** carried into next day's morning block.
```

---

## Baseline — 2026-05-09 (D-14 to cert)

**Where things actually stand today:**

**Hours done so far this week (May 9 only):**
- ai-arch: ~3h (chunking deep-dive in nb_02b, conceptual Q&A, plan creation)
- Fitness: 0h (gym starts Mon May 12)
- Sleep avg: TBD (assume ~6.5–7h based on recent pattern)

**Anchor progress:**
- ☐ Phase 1 POC v1 runnable (May 14) — at ~40% (nb_01 ✓, nb_02 drafted, nb_02b WIP, nb_03–05 not started)
- ☐ Cert exam (May 23) — Week 1–4 content untouched, plan in cert-prep.md
- ☐ Slalom presentation v1 (May 30) — concept only
- ☐ Slalom promo package (~Jun 9, manager confirms) — template received, not started
- ☐ **Apply-day (Jun 30)** — 30% knowledge, 10% materials, no target company list yet
- ☐ Job offer (Sept 30) — n/a yet
- ☐ −20 lbs (Sept 30) — baseline weight: TBD (record on first weigh-in Sun May 11)

**Weight baseline:** **147 lbs** (Sun May 10 morning, fasted)
- Target: **127 lbs by Sept 30** (−20)
- Stretch: **127 by Aug 31**
- Phase 1 (May–Jun): no weight target, habit + sleep only
- First scale check: Sun May 17, then weekly Sundays

**Decision for next 3–4 days (Sat May 9 → Tue May 12):**
- Continue. No adjustments needed yet.
- Top 3 priorities:
  1. **Sun May 10 morning:** baseline weight (fasted, post-bathroom). Log in this file.
  2. Run nb_02b end-to-end + finish remaining FAISS/retrieval Q&A; draft nb_03/04/05 toward May 14 milestone.
  3. Sleep on schedule starting tonight (lights out 22:30) so gym Mon May 11 (06:00) is real — same morning OSA kicks off.

**Watch items:**
- **OSA starts Mon May 11** — onboarding/context-load first 2 weeks may compress evening cert prep. Flag at next check-in.
- Slalom promo discussion — manager shared template, will confirm exact deadline. Could compress June.
- Slalom-aligned client work alongside GE OSA — daytime bucket; flag if it leaks into evenings.
- Caffeine timing — note when last cup is each day. Sleep quality follows directly.
