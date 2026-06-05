# Milestones — progress + on/behind status

Per-goal milestone plan. Aligned with anchor dates in [roadmap.md](roadmap.md). Hours velocity in [velocity.md](velocity.md). Daily work in [tracker.md](tracker.md).

> **Status legend:** ✅ done · 🟢 on-track · 🟡 at-risk (slip likely if nothing changes) · 🔴 behind (already slipped or no path to date) · ⏸ blocked (waiting on someone else) · ❌ cancelled

> **Progress %** is rough — meant to flag drift, not be precise. Updated on Sunday weigh-in / weekly review.

> **Updated:** 2026-05-19

---

## Snapshot — week of May 11–17

| Goal | Anchor | This week's milestone | Status | % |
|---|---|---|---|---|
| #1 Weight | 127 lbs by Sep 30 | Habit phase week 1 — first gym Tue + Sun weigh-in May 17 (146, −1) | 🟢 | 5% |
| #2 AA | _TBD_ | Placeholder — goals + anchor to be defined | 🟡 | TBD |
| #3 Promo | ~Jun 9 final | **Arch-Hive pres ready by Wed May 20** — v2 restructure + PPT-extract files shipped May 19; user review + visuals pass remaining | 🟢 | 88% |
| #4 Cert | Sat Jun 13 | **D0 block carry from Sun** — Foundations (Udemy S1 + S3, 2h) | 🟡 | 0% study (D-26) |
| #5a POC | May 17 v1 | Slip to May 24 — de-scope nb_05 | 🟡 | 40% |
| #6 Interview | Jun 30 first wave | Out of scope until cert done | ⏸ | 0% |

**Delivery work (hours-only, not a goal):** GE FSR prod + OSA — see [§Delivery work](#delivery-work-ge--hours-only-not-a-goal) at the bottom.

---

## #1 Weight loss 🟢 *Sep 30 anchor*

Baseline 147 lbs (May 10) → 127 lbs by Sep 30. **Lever per lb: ~0.5 lbs/week sustained.**

| Milestone | Target date | Status | Progress | Notes |
|---|---|---|---|---|
| Habit phase complete (4 wks consistent gym + sleep) | Jun 8 | 🟢 | week 1/4 | First gym Tue May 12. Sleep 22:30 cutoff. |
| **−5 lbs (142)** | Jun 22 | 🟢 | 0/5 | Baseline 147 May 10 |
| **−10 lbs (137)** | Aug 15 | 🟢 | 0/10 | Roadmap anchor |
| **−15 lbs (132)** | Sep 15 | 🟢 | 0/15 | Stretch |
| ★ **−20 lbs (127)** | Sep 30 | 🟢 | 0/20 | Goal |

**Weekly checkpoint:** Sunday weigh-in. Behind = 2 consecutive weeks under 0.4 lbs lost.

---

## #3 Slalom promo 🟡 *~Jun 9 final*

**PL review done May 13.** Visibility = #1 gap, Eugene = gatekeeper.

| Milestone | Target | Status | Progress | Notes |
|---|---|---|---|---|
| 3a Promo first draft to manager | May 12 | ✅ | 100% | Shipped |
| 3a PL review | May 13 | ✅ | 100% | |
| **3c Eugene artifact outline v1** | May 14 | ✅ | 100% | Sections 1–12 + appendix |
| **3c Eugene artifact user review pass** | May 17 | ✅ | 100% | 3 substantive fixes — ESN stats corrected, scan-quality reframed as upstream, 7B opener re-anchored on real Unit-Risk engagement; offer set 4→3 (combined PR playbook + new AI-ops cheat-sheet) |
| **3c Eugene slide content** | **Wed May 20** | ✅ | 100% | Done May 18, refreshed May 19 — Templates→Agents added as Slide 9 (12 main + 3 backup total). At [`promo/eugene-track/eugene-slides.md`](promo/eugene-track/eugene-slides.md). PPT-extract copy-paste at [`promo/eugene-track/eugene-slides-ppt-content.md`](promo/eugene-track/eugene-slides-ppt-content.md). |
| **3c Arch-Hive slide content** | **Wed May 20** | ✅ | 100% | v1 done May 18; **restructured into v2 May 19** at [`promo/eugene-track/arch-hive-slides-v2.md`](promo/eugene-track/arch-hive-slides-v2.md) (11 main + 2 backup) — honest-scope rewrite (only FSR pipeline + AdHoc QA agent; Unit Risk acknowledged as separate-team work), external-takeaway framing, **new Slide 10 tech stack** (Databricks UC/Workflows/Delta/Vector Search, AWS Strands, LiteLLM, OpenAI text-embedding-3-large via LiteLLM, Claude Code + GitHub Copilot) so SME-signal is captured. v1 kept as backup at [`arch-hive-slides.md`](promo/eugene-track/arch-hive-slides.md). PPT-extract at [`promo/eugene-track/arch-hive-slides-ppt-content.md`](promo/eugene-track/arch-hive-slides-ppt-content.md). |
| **3c Both decks — user review pass** | May 19–20 | 🟡 | 0% | User to review v2 + Eugene Slide 9 (Templates→Agents) + both PPT extracts. |
| **3b Arch-Hive pres ready (v1)** | **Wed May 20** | 🟢 | 70% | Content done + v2 restructure done; visuals pass remaining — Slide 4 overview diagram (highest priority), then Slides 5 + 7. md → pptx for both decks. |
| **3c Eugene artifact visuals** | May 28 | 🟢 | 0% | After slide content; convert md → pptx |
| **3c Readiness doc in Eric's template** | May 24 | 🟡 | 10% | Stitch Section 5/6 from May 13 |
| **3b Slalom presentation v1 (Arch-Hive)** | **Wed May 20** | � | 60% | **Pulled left from May 30.** Shares source with 3c. Content done May 18; visuals + pptx pass remaining. |
| 3c Schedule Eugene meeting | After artifact + readiness | 🟢 | — | Don't send before there's something to walk through |
| 3a Promo final package submitted | ~Jun 9 | 🟡 | 60% | Manager confirms exact date |
| 3d Tao + Sreedhar Anytime-Feedback DMs | This week | ✅ | Tao 5/20, Sreedhar 5/28 — both written. Pranesh still pending. | Per Eric |
| 3e Pursuit Lead first opportunity | 2026 H2 | 🟢 | — | Brie's AI demo team likely on-ramp |

**Behind risk:** Wed May 20 v1 still hinges on visuals pass landing in time — Slide 4 overview diagram (Arch-Hive v2) is the gate. If diagram slips past Tue evening, Wed v1 ships text-only.

---

## #2 AA 🟡 *anchor TBD*

**Placeholder.** Goals + anchor + milestones to be defined — user will fill in details. Tracked here so it stays in the weekly review and snapshot.

| Milestone | Target | Status | Progress | Notes |
|---|---|---|---|---|
| Define goals + anchor date | TBD | 🟡 | 0% | Awaiting user input |

---

## #4 Databricks GenAI cert 🔴 *Sat Jun 13 — D-29*

**Real anchor risk.** Unblocked May 17 — Udemy materials in hand, plan rebuilt. **Zero study time logged so far.** D-0 Foundations block missed today.

| Milestone | Target | Status | Progress | Notes |
|---|---|---|---|---|
| Reschedule exam in portal | May 17 | ✅ | done | Booked for Sat Jun 13 |
| Udemy materials shared by user | May 16 | ✅ | done | At [`dbx-genai-course/udemy/`](dbx-genai-course/udemy/) — 17 slide decks + 5-section hands-on notebook repo |
| cert-prep.md rebuilt against Jun 13 | May 17 | ✅ | done | 42h budget, 6h/wk to May 30 then 12h/wk to exam |
| D-0 study block (Udemy S1 + S3 Databricks Fundamentals, 2h) | May 17 | 🔴 | 0% | Missed today — Mon evening carry |
| Week 20 — Udemy S4 (DE/Analytics) + S5 (GenAI Primer) + start S6 (RAG) | May 24 | 🔴 | 0% | 6h budget |
| Week 21 — finish S6 (RAG) + S7 (LangChain Agents) | May 31 | 🔴 | 0% | 6h budget |
| Week 22 — §3 Eval & Govern gap-fill (DASF, MLflow eval, UC) | Jun 7 | 🔴 | 0% | 12h budget; not covered well in Udemy |
| Week 23 — §4 Deploy gap-fill (Model Serving, Inference Tables, AI Gateway) | Jun 12 | 🔴 | 0% | 12h budget; not covered well in Udemy |
| **Mock #1 (go/no-go)** | Sat Jun 6 | 🔴 | — | <65% → push to Jun 21 |
| Mock #2 | Wed Jun 10 | 🔴 | — | |
| ★ **Exam** | Sat Jun 13 | 🔴 | — | Hard date |

**Velocity needed (from roadmap):** 6h/week through May 30, then **12h/week** May 31–Jun 13. Today logged: 0h. **Every week without movement = ~6h debt added** to the final 2 weeks (already pre-loaded to 12h/wk).

---

## #5 Interview / job offer 🟣 *Sep 30 anchor — offer in hand*

Funnel: apply Jun 30 → screens by Aug 15 → loops by Sep 15 → offer by Sep 30.

| Milestone | Target | Status | Progress | Notes |
|---|---|---|---|---|
| **5a Phase 1 POC v1 runnable end-to-end** | May 17 | 🟡 | 40% | nb_01 ✅, nb_02 WIP, nb_02b drafted, nb_03–05 not started. Slip likely this week. |
| 5b Phase 1.5 polish (nb_03–05 + README walkthrough) | Jun 10 | 🟢 | 0% | Phase B |
| 5c Phase 2 ammo — parsing alts | Jun 16 | 🟢 | 0% | 1 day |
| 5c Phase 2 ammo — embedding swap | Jun 18 | 🟢 | 0% | 1 day |
| 5c Phase 2 ammo — chunking variants | Jun 20 | 🟢 | 0% | 1 day |
| 5d STAR stories (5 anchors) polished | Jun 22 | 🟢 | 30% | Source: [evidence-bank.md](promo/evidence-bank.md) |
| 5e System design reps + mocks | Jun 30 | 🟢 | 0% | Parallel with apply soft-start |
| 5f Target company list refined | Jun 9 | 🟢 | — | Post promo final |
| 5g Resume + LinkedIn refresh | Jun 14 | 🟢 | 0% | Day-one Phase B |
| 5g Soft-start apps (2–3) | Jun 15–21 | 🟢 | 0% | |
| 5g Ramp apps (3–5) | Jun 22–28 | 🟢 | 0% | |
| ★ **Apply-day first wave (10–15 cumulative)** | Jun 30 | 🟢 | 0% | |
| ★ Phone screens + take-homes mostly done | Aug 15 | 🟢 | 0% | |
| ★ **Offer in hand** | Sep 30 | 🟢 | 0% | |

---

## Critical-path view (next 4 weeks)

```
May 18 (today) ── Wed May 20 ──────── May 28 ─── Jun 6 ───────── Jun 13
   │                  │                    │           │              │
   ├── 🔥 FSR P0      ├── ★ Arch-Hive       ├── Visuals  ├── ★ Cert    ├── ★ CERT
   │    follow-ups   │     pres v1 ready    │     md→pptx │     Mock#1   │     EXAM
   ├── 🔴 Cert D-0    ├── Eugene slides    │           │   (go/no-go) │
   │    carry        │     filled           │           │              │
   └── Runbook       └── Reach out to       │           │              │
        finalize +         team to schedule
        share              session
                                                                                            
   Cert: D-0 ──── 6h/wk study window ────────────────► 12h/wk ramp ───────────────────────►
   Promo final: ──────────────────────────────────────────────────────────► ~Jun 9
   Weight: 146 ────────────────────────────────────────────────────────────────► −5 lbs Jun 22
   POC v1: 40% ──── slip to May 24 (de-scope nb_05) ─────────►
```

**Three biggest risks right now:**
1. 🔴 **Cert** — D-0 study block missed Sun, now D-26 with 0% study. **Action:** Mon evening Foundations decks #1–5 (2h), non-negotiable.
2. 🟡 **Arch-Hive Wed deadline — visuals pass.** Content done May 18, v2 restructure + PPT extracts done May 19 ahead of schedule. Risk now is Arch-Hive Slide 4 overview diagram + Slides 5 + 7 architecture diagrams + md → pptx. **Action:** Tue — user review of v2 + Eugene refresh, then overview diagram first.
3. 🟡 **POC v1 slip** — only 40%, FSR P0 absorbing days. **Action:** accept slip to May 24, de-scope nb_05.

---

## Delivery work (GE) — hours-only, not a goal

> GE FSR prod + OSA pay the bills and feed AI engineering skills that overlap with goal #5. They're tracked here for visibility — **no anchor dates, no goal-level progress %.** Source of truth lives in the team trackers.

### FSR prod 🔵 *ongoing ops*

Live UI-NN list at [`../fsr-prod-ops/tracker.md`](../fsr-prod-ops/tracker.md).

| Item | Target | Status | Notes |
|---|---|---|---|
| UI-20 consumer comms (P0) | May 15 EOD | ✅ | Sent — Vinayaka email + Rashmin Slack out, awaiting reply |
| UI-21 consumer-search miss for `8fe0793d-...` | May 22 | 🟢 | Mon — file is in index; check multi-ESN suffix mismatch in consumer query |
| UI-22 VS index sync staleness | May 22 | 🟢 | Mon — last commit May 7, ~8 days behind; verify + manual resync if real |
| UI-15 ESN proper resolution | TBD (Pranesh) | 🟢 | In flight, ADO #664259 |
| UI-17 + UI-18 (DQ + P1 retry) | PR + dev validation | 🟢 | Pushed, awaits PR |
| UI-12 LiteLLM secret-scope | Awaiting Databricks team | ⏸ | Pinged 2026-05-12 |
| FSR robustness items list for Abhijeet | May 20 | 🟡 | Carry from May 13 |
| FSR runbook / handoff doc — draft v1 | May 17 | ✅ | 2-page docx at [`../FSR/fsr-docs/FSR Pipeline - Runbook and Guide.docx`](../FSR/fsr-docs/FSR%20Pipeline%20-%20Runbook%20and%20Guide.docx). Page 1 = pre-reqs DEV/PROD + Build & deploy ownership + config touch-points + jobs reference. Page 2 = operations (run schedule, observability, 6-row repair recipes, terminal failures, ownership). Modeled on team's SDG Infra & Build Pipeline Provisioning Guide; complements existing Confluence design + deploy plan (doesn't repeat them). |
| FSR runbook — user review pass | May 18 | ✅ | Done. Removed Setup Steps; added Build & deploy ownership (Bronze=D&A, Silver/Gold=Dev, branch→workspace table, prod deploy flow via CCB); renamed title ("Handoff" dropped). |
| FSR runbook — share with team | May 19 | 🟢 | Tue — then send L1/L2 ask to Sreedhar (drafted morning of May 18). |

### OSA 🔥 *P0 estimate — delivered*

**Delivered May 15.** Doc at [`../OSA/estimation/wbs-review-and-estimates.md`](../OSA/estimation/wbs-review-and-estimates.md).

| Item | Target | Status | Notes |
|---|---|---|---|
| Sizing reference prepared (FSR-anchored) | May 15 | ✅ | |
| Kaif WBS xlsx reviewed + gaps flagged | May 15 | ✅ | Sent in Slack with paste-ready table |
| Risk flag to Sreedhar (DA dep + centralization) | May 15 | ✅ | |
| Internal estimation doc shareable | May 15 | ✅ | `OSA/estimation/wbs-review-and-estimates.md` |
| Kaif review feedback incorporated | May 20 | 🟢 | Await response |
| Sreedhar steer received | May 20 | 🟢 | Await response |
| Customer-facing extract | After internal sign-off | 🟢 | Placeholder section ready |
| OSA tracker.md stood up | When scope firms up | 🟢 | Deferred until feedback in |
