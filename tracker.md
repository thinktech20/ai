# tracker — track-organized status

One screen per active track. Long-horizon plan in [`roadmap.md`](roadmap.md). **Milestones + progress %** in [`milestones.md`](milestones.md). **Hours velocity** in [`velocity.md`](velocity.md). Daily log in [`check-ins.md`](check-ins.md). Track map in [`track-index.md`](track-index.md). Health in [`health.md`](health.md).

**Updated by the `check-in` chat mode each evening.** Edit manually too, but the check-in agent is the primary writer.

> Status legend: 🔥 hot · ⏳ active · 💤 dormant · ✅ done

---

## Top 3 this week (May 25–29)

1. 🔥 **GE work — four parallel threads.**
   - **(a) ESN-multiple design.** Create + share design doc; reach **Feng** with open questions.
   - **(b) FSR design ↔ OSA impact review.** Review the existing FSR design for OSA implications (feeds OSA estimation work).
   - **(c) OSA data sources — TIL especially.** Unstructured shape + sizing pass (carry from 2026-05-22).
   - **(d) Close-out: UI-04 doc-summary + UI-22 VS-sync.** Follow up on prod landing — D&A handoff completion, prod-access revoke, post-deploy verification.
2. 🔥 **Promo — circulation + visibility plays.**
   - **(a) Share Arch-Hive + Eugene slides.** Post-talk distribution to the channels Eric pointed at.
   - **(b) Account-manager outreach.** Surface Tao's verbatim feedback to the GE AM (per 2026-05-23 stretch item).
   - **(c) Pragathi follow-up.** Per Eric's visibility nudge (5/20). Easy-cadence ping already went out 5/22. **NEW 2026-05-28 — Pragathi asked me to author the GEV / FSR customer success story for Slalom (Databricks Lakehouse + VS powering FSR pipeline + downstream agents).** Build + share — visibility play tied to the Databricks COE partnership.
3. 🔥 **Cert anchor — D-19 (Sat Jun 13).** 1h Udemy logged Mon morning — first non-zero block. **Mock #1 Sat Jun 6 (D-12) is the gate.** Foundations decks #1–5 still pending.

**Carry / stretch:** Readiness doc in Eric's template; FSR robustness open-items PR queue (UI-16/17/18/19); 💬 **Brie reply:** work coming after holidays — **follow up Wed 2026-05-27**; 🗓 **Eugene walkthrough — Wed** (agenda at [`promo/eugene-track/agenda-meeting.md`](promo/eugene-track/agenda-meeting.md)); Sreedhar Anytime-Feedback DM; AA track — user to define goals; **Promotion Plan content → official Slalom pptx template** (Path B remaining half of the promo package).

**Top 3 from last week (May 18–22, closed):**
- ✅ **Arch-Hive deck** — content + visuals shipped through May 24; Fri May 22 talk window covered. Slide-by-slide polish continued through Sun/Mon (combined-deck.pptx).
- ✅ **FSR UI-22 + UI-04** — both PRs approved 2026-05-22. UI-22 hotfix lived in prod; UI-04 doc-summary path verified in dev. Prod close-out moves to this week's Top 3 #1(d).
- ⏳ **Cert** — anchor stayed hot, zero study across the week. Today's 1h Udemy = first move. Stays in Top 3 #3 this week.
- ✅ Tao feedback received in writing 5/20; replies sent same day. Eric 1:1 5/20 produced new visibility mechanics in [`promo/Eric-track/brand-plan.md`](promo/Eric-track/brand-plan.md) §9.
- ✅ Easy-cadence Slack pings (Brie, Pragathi, Sownya, Emanuel) — all 4 sent 2026-05-22.
- ✅ Official Slalom Reflection xlsx filled 2026-05-24 (output at [`promo/output-docs/Promotion-Readiness-Reflection_Madhurima.xlsx`](promo/output-docs/Promotion-Readiness-Reflection_Madhurima.xlsx)).

---

## 1. FSR prod (GE) 🔥

**Where:** [`../fsr-prod-ops/tracker.md`](../fsr-prod-ops/tracker.md) is source of truth.

**Status (mirror):** ongoing prod ops. UI-15 ESN work (ADO #664259) in flight. Backfill monitoring ongoing. **New thread May 13:** Abhijeet asked how we handle failures → consolidating open robustness items into a shareable list for ticketing. **May 15 P0:** missing-FSR consumer ticket verification done — original "10/1 split" was wrong (file `8fe0793d-...` is in metadata + chunks + VS index; the run-log gap was instrumentation lag, not a discovery skip). All 5 ESNs revised to upstream `fsr_pdf_ref` shortage. Two follow-ups opened: UI-21 (consumer-search miss for that one file) + UI-22 (VS sync ~8 days stale, last commit May 7).

**Open:**
- See [`../fsr-prod-ops/tracker.md`](../fsr-prod-ops/tracker.md) for live status.
- [x] **UI-20 (today)** — Vinayaka email + Rashmin Slack sent May 15 EOD. Awaiting Vinayaka's reply on the per-ESN `fsr_pdf_ref` gap.
- [ ] **UI-21 (Mon)** — dig into why consumer can't find `8fe0793d-...` in search even though it's in the index. Top hypothesis: multi-ESN suffix mismatch (`document_id = 8fe0793d-..._324X043` vs base UUID). Check via direct `similarity_search` with `document_id` + `esn` filters, then walk consumer query construction.
- [ ] **UI-22** — VS index sync staleness. **Root cause confirmed:** chunk-table `delta.deletedFileRetentionDuration` was at the 7-day default, so the daily sync fell behind whenever it slipped past the window. **Hotfix PR raised May 20** on branch `hotfix/vs-sync-retention-and-schedule` (HEAD `5322f8d`): bumped retention to 30 days + added daily safety-net schedule at 11:00 ET on `PW_SDG_FSR_VS_Sync` (live on deploy, `timezone_id: America/New_York`). CCB package at [`../fsr-prod-ops/comms/2026-05-20/`](../fsr-prod-ops/comms/2026-05-20/). **Tomorrow:** manual `ALTER` + Sync now in prod to recover OFFLINE_FAILED index; file CCB; merge after sign-off; verify first scheduled run at 11:00 ET; fill data-validation evidence template.
- [ ] **Carry from May 13:** build FSR robustness open-items list for Abhijeet — group by theme: failure handling (UI-17, UI-18, UI-11) · observability (UI-16, UI-17 SRE runbook, **UI-22 VS sync freshness, new**) · ESN (UI-14, UI-15, UI-07, UI-13) · repair tooling (UI-19) · doc-summary (UI-04) · security (UI-12) · **consumer-search contract gap (UI-21, new)**. Flag robustness gaps not yet ticketed (orphan VS-row drift, source-PDF replacement workflow for corrupt `No /Root` docs).
- [ ] **Carry:** update FSR docs — ask from Naresh, details TBD (user will share).
- [ ] Finish raising FSR doc-summary PR (carry from May 12).
- [x] **FSR runbook / handoff doc — draft v1 done May 17.** 2-page docx at [`../FSR/fsr-docs/FSR Pipeline - Runbook and Guide.docx`](../FSR/fsr-docs/FSR%20Pipeline%20-%20Runbook%20and%20Guide.docx). Modeled on team's SDG Infra & Build Pipeline Provisioning Guide. Page 1 = provisioning (pre-reqs DEV/PROD, build & deploy ownership added May 18). Page 2 = operations (run schedule, observability, 6-row repair recipes, terminal failures, ownership).
- [x] **FSR runbook — user review pass (May 18) done.** Setup-steps section removed. Build & deploy ownership section added with branch→workspace table + prod deploy flow. Title renamed ("Handoff" dropped).
- [x] **FSR runbook shared with FSR team — May 18.**
- [x] **Missing-FSR Infy handoff note — May 18/19.** Short note covering jobs to run + verification query.
- [ ] **NEW today (May 19) — prod metadata job failing.** Triage + fix. Could be actively dropping new docs through incremental cycle. Timeboxed under Top 3 #1.
- [ ] **NEW today (May 19) — doc-summary (UI-04) validate + push to prod.** Scenario B (TOC flow). Dev sample → P1 incremental smoke → prod rollout. Folds in the carry from May 12.
- [ ] **NEW today (May 19) — validate incremental ingestion in prod.** Confirm daily P1+P2 cycle picks up new docs cleanly post-backfill. Tightly coupled to the metadata-job fix above.
- [ ] **NEW today (May 19) — new-PDF ingestion process write-up.** Operator path: where PDFs land, what triggers discovery, how to verify P1 → P2 → VS index. Likely a new runbook section.
- [ ] **Later — Databricks ↔ VSCode integration** (GE Confluence: [Integration of Databricks With VSCode](https://confluence.apps.gevernova.net/devspace/spaces/HKPLL/pages/358842396/Integration+of+Databricks+With+VSCode)). Set up local VSCode → Databricks dev workflow for faster notebook/job iteration. Parked.
- [ ] **NEW 2026-05-22 — prod access revoke follow-up.** Standing prod access for our team — chase owner + timeline. D&A / security thread.

---

## 2. OSA (GE) 🔥

**Where:** [`../OSA/`](../OSA/) — estimation doc at [`../OSA/estimation/wbs-review-and-estimates.md`](../OSA/estimation/wbs-review-and-estimates.md). Comms drafts under [`../OSA/comms/`](../OSA/comms/).

**Status:** **P0 estimate delivered May 15.** Kaif shared his WBS xlsx (`OSA/ref-docs/dev-team/datasources-pipeline/Data Pipelines estimation.xlsx`); reviewed + added 10 gap tasks (run log, DQ, UC perms, multi-env, multi-key fan-out, VS sync, design doc, runbook, cost monitoring) + hour estimates per H/M/L bucket anchored to FSR actuals + per-source rollup (~70–105 FTE-weeks with buffer; ~24 calendar weeks with assumed team) + 8-item risk register. Hour table handed to Kaif to paste into his xlsx. Risk flag sent to Sreedhar.

**Open:**
- [ ] Kaif review of WBS gaps + hour estimates → incorporate feedback into estimation doc.
- [ ] Sreedhar steer on (a) DA-team landing-date alignment, (b) centralization confirmation per source.
- [ ] Kaif to confirm with Binayak whether ER needs incremental-ingestion work (Tao unsure).
- [ ] Kaif to clarify "Target: Sprint 3 / 4" entries — built / in-progress / planned?
- [ ] **Mayank (new, May 20)** — connected on DS-side priorities; thread alignment into the estimation work for the DS layer. Confirm scope of his ask + how it overlays the source-list rollup.
- [ ] **NEW 2026-05-22 — review unstructured TIL data for OSA.** Sizing + shape pass to feed into the estimation/scope work.
- [x] **NEW 2026-05-27 — identify OSA data sources for data-pipeline work.** Enumerated in [`../OSA/data-sources.md`](../OSA/data-sources.md) (31 sources across 7 buckets, sourced from DS methodology doc §2/§4.4/§4.5/§4.6). Headline: 13 already-landed (preprocessing only), 4 need Bronze ingest, 6 need chunk+embed, 2 external API, 4 EV-config, 1 IBAT, 1 conditional. Eight open questions feed back into estimation hour buckets.
- [ ] Once scope firms up, stand up `../OSA/tracker.md` and roll estimates into a per-sprint plan.
- [ ] Customer-facing extract (placeholder section in estimation doc) — produce after internal sign-off.

---

## 3. Slalom promo ⏳

**Where:** [`promo/`](promo/) — [`evidence-bank.md`](promo/evidence-bank.md), [`user-inputs.md`](promo/user-inputs.md), [`output-docs/`](promo/output-docs/) (drafts shipped).

**Status:** **First draft shipped May 12 ✅.** PL review **done May 13** — see [`promo/pl-conversation-2026-05-13.md`](promo/pl-conversation-2026-05-13.md). Headline: visibility/brand is the #1 gap; **Eugene is the gatekeeper**. Reflection / Plan / xlsx in `output-docs/`. **Eugene track now active** — last Slack exchange (early May): Eugene 👍'd plan to set up time + share readiness doc + AI engineering insights. Ball is in our court to drive.

**Open — Eugene track (3c) 🔥:**

> All Eugene-track work ladders to the brand line in [`promo/Eric-track/brand-plan.md`](promo/Eric-track/brand-plan.md): *"when someone in the practice needs RAG productionized on Databricks or an agent built end-to-end on AWS, they think of me."* Anything that doesn't ladder, deprioritize.
- [ ] **#1 — AI-in-production artifact** (combined Arch-Hive talk + Eugene artifact). One package, two slice depths: top slides = Arch-Hive (architecture story), deeper slides + appendix = Eugene (lessons / guardrails / patterns from FSR prod). **May 23 update — Eugene deck pivot:** user said 12 slides is too much for an initial pass; goal for Eugene = get the point + value across, expand from his input. **Done 2026-05-23:** (a) content review pass on [`eugene-slides.md`](promo/eugene-track/eugene-slides.md) slides 1–6 — dropped "five" framing, removed weekend overuse, sharpened pattern #5, added Eval to design list, rewrote loop "better move" around grilling the first answer; (b) [`eugene-slides-ppt-content.md`](promo/eugene-track/eugene-slides-ppt-content.md) rebuilt as 4-slide first-pass (Title / Anchor / Patterns table / Closing the loop + automation table); long 12-slide form preserved at [`eugene-slides.md`](promo/eugene-track/eugene-slides.md). **Next:** user reviews Arch-Hive slides → second pass on Eugene 4-slide content → md → pptx for both decks → stitch arch-hive front-half into Eugene 4-slide for end-to-end story before the call. Open: long-deck slide 4 ↔ slide 6 idempotence/retry overlap, slide 6 reword pending if needed.
- [ ] **#2 — Readiness doc in Eric's new template** — stitch in PL-aligned Section 5 goals + Section 6 asks already finalized May 13.
- [ ] **#3 — Schedule meeting with Eugene** — short Slack with target date once #1 outline + #2 first pass are in hand. Don't send before there's something concrete to walk through.
- [ ] Reach out to Eugene's named connections when artifact is ready: **Dave Messina, Christian, Chris Temple** (each scoped in artifact section 12).

**Open — promo package (3a):**
- [ ] **NEW 2026-05-23 — share client feedback with account manager.** Short Slack/email to the GE account manager surfacing Tao's verbatim quote + summary (already in [`promo/feedback-asks.md`](promo/feedback-asks.md) and [`promo/evidence-bank.md`](promo/evidence-bank.md)). Visibility play — get client praise in front of the AM who can amplify upstream. Same pattern as the Eric/Workday handoff, different audience.
- [x] **Anytime-Feedback recos from Tao and Sreedhar** 🔥 (per Eric's recommendation, May 14). **Tao: RECEIVED 2026-05-20** (email + Slack) — strong written note covering AdHoc Q&A leadership, FSR pipeline initiative, design partnership, communication, blocker-pushing. **Sreedhar Sannidhanam (AWS Sr. Engagement Manager): RECEIVED 2026-05-28** — written note on Customer Obsession (working backwards from customer requirements), cross-team coordination + blocker removal, root-cause focus through UAT, Deliver Results with quality bar. Replies sent same day. Both verbatim quotes logged in [`promo/feedback-asks.md`](promo/feedback-asks.md) and integrated into [`promo/evidence-bank.md`](promo/evidence-bank.md) Story #1 and into the official Reflection xlsx (Principal tab, G14/G36/G71). **Still open:** Pranesh ask. **Next:** log both notes formally in the Slalom Anytime-Feedback tool (or attach screenshots) and pull quotes into [`promo/user-inputs.md`](promo/user-inputs.md) §1e GE Vernova / AWS subsection.
- [ ] User fills `user-inputs.md` Section 2a–2d revenue numbers post-manager (TODOs in place with named owners).
- [ ] User fills Section 3a/3b/3c (sanity checks, additional quotes, "why principal" 2-sentence).
- [ ] User fills Section 4 self-ratings (gut calibration with PL).
- [x] **Official Slalom Reflection xlsx filled — 2026-05-24.** Output at [`promo/output-docs/Promotion-Readiness-Reflection_Madhurima.xlsx`](promo/output-docs/Promotion-Readiness-Reflection_Madhurima.xlsx) — `Reflection - To Principal` tab: 13 sub-competency self-ratings (F-col dropdowns, 4× Consistently / 8× Sometimes / 1× Have not Started for optional PL row) + 4 grouped Examples cells (G14/G36/G54/G71, one per core competency) + 5 quantitative dropdowns (Util Meets, Revenue Does Not Meet Yet — pending numbers, Tech Role Meets, Eng Lead Meets, Pursuit Lead Does Not Meet Yet) + notes. Template untouched. Fill script at [`../local-scratch/fill_promo_template.py`](../local-scratch/fill_promo_template.py). **Open questions for user** stashed in session memory (conditional-formatting verify, summary-tab fill, Why/Goals placement).
- [ ] Move Promotion Plan content into the official Slalom pptx template (Path B remaining half).

---

## 4. Databricks AI cert 🔥

**Where:** [`cert-prep.md`](cert-prep.md), [`dbx-genai-course/`](dbx-genai-course/).

**Status:** **Exam rescheduled May 23 → Sat Jun 13** (D-31 today). Anchor risk released for now — still 🔥 because zero study has happened. Plan in `cert-prep.md` to be rebuilt against Jun 13 once user shares Udemy course + materials. Mock #1 Sat Jun 6 = go/no-go gate.

**Open:**
- [ ] **Reschedule exam** in Databricks portal (May 23 → Sat Jun 13).
- [ ] **User shares Udemy course + materials** → agent rebuilds [`cert-prep.md`](cert-prep.md) with daily blocks (May 14 → Jun 13) + Mock #1 Jun 6, Mock #2 Jun 10.
- [ ] Week 1 content + lab (Retrieval / Parsing / Chunking / Embeddings / Vector Search / MLflow / Knowledge Assistant)
- [ ] Week 2 content + lab (Agent Framework / UC Functions as tools / Agent Bricks)
- [ ] Week 3 content + lab (Eval & Governance, DASF 2.0)
- [ ] Week 4 content + lab (Model Serving / Inference Tables / Monitoring / MLOps vs LLMOps)
- [ ] **Mock exam #1 — Sat Jun 6** (go/no-go gate; <65% → push to Jun 21)
- [ ] **Mock exam #2 — Wed Jun 10**
- [ ] Final vocabulary review (Jun 11–12)
- [ ] **Exam — Sat Jun 13**

---

## 5. AI learning / POC ⏳

**Where:** [`code/`](code/), [`learning-plan.md`](learning-plan.md).

**Status:** Phase 1 POC at ~40%. nb_01 ✓, nb_02 drafted, nb_02b WIP, nb_03–05 not started.

Pipeline: `ingest → parse → chunk → embed → index → retrieve → (re-rank) → generate`
(metadata extraction runs alongside parse/chunk and rides with every chunk — filters & citations downstream)

### Phase 1 checklist (one doc, simplest path)

| # | Stage | Status | Notes / aha‑moments |
| - | --- | --- | --- |
| 1 | Pick the FSR doc + workspace path | ✅ | `sample-docs/fsr-sample-01.pdf` (~13 MB real FSR) |
| 2 | Ingest (load PDF, local path; UC Volume later for cert) | ✅ | `code/bronze/nb_01_ingest_parse.ipynb` reads from local path |
| 3 | Parse (PDF → text) | ✅ | PyMuPDF baseline. Page 1 clean, mid pages noisy. |
| 3.5 | **Metadata** (alongside parse/chunk) | WIP | Drafted in `nb_02_chunk.ipynb`. Pending: flatten `extra`, add operational fields. |
| 4 | Chunk (one simple strategy first) | WIP | `nb_02_chunk.ipynb` drafted: baseline 1000/200 + variants. Pending: user reading + run. |
| 4b | **Retrieval demo** (learning aid, not part of canonical pipeline) | WIP | `nb_02b_retrieval_demo.ipynb` drafted. Pending: user run; query exploration. |
| 5 | Embed (one model first) |  | `azure-text-embedding-3-large-1` via LiteLLM gateway. Demo above promoted into `nb_03_embed.ipynb`. |
| 6 | Index (FAISS local first) |  | Then mirror with Databricks Vector Search (cert). |
| 7 | Retrieve (top‑k, eyeball results) |  |  |
| 8 | Re‑rank (skip on first pass) |  |  |
| 9 | Generate (one prompt, structured answer) |  | `gemini-3-flash` via gateway. |
| 10 | End‑to‑end runnable cell |  |  |

### Phase 2 — interview ammo (Jun)

| Stage (1 day each) | Status | Notes |
|---|---|---|
| Parsing alts (PyMuPDF/pdfplumber/Unstructured) | not started | |
| Embedding swap (large vs small) | not started | |
| Chunking variants (recursive vs structure-aware vs semantic) | not started | |

### Interview‑readiness check (weekly)

- [ ] When to fine‑tune vs. RAG vs. just prompt?
- [ ] Whiteboard the FSR RAG pipeline in <5 min.
- [ ] A doc that broke the pipeline — story.
- [ ] How did you pick chunk size? (trade‑off, not a number)
- [ ] Why does swapping embedding model trigger a backfill?
- [ ] Trace a query "issue with ESN X" end‑to‑end.
- [ ] ESN extraction case study (3 min).
- [ ] How would you evaluate before shipping a change?
- [ ] FSR backfill story (3 min).
- [ ] 3 risks of ingesting customer FSRs + mitigations.
- [ ] 12‑month roadmap toward an agentic assistant.

### Open questions / parking lot

- Page‑26 vertical char‑soup from PyMuPDF — quantify (count of single‑char lines per page). Becomes a chunk‑quality gate.
- Whether Phase 1 should mirror end‑to‑end on Databricks (Vector Search + Model Serving) once locally working — yes, double duty for cert.
- **Metadata flattening decision** — keep nested `extra` dict in notebook for readability, but flatten to top-level fields before persisting. Decide at Step 6.
- **Operational metadata fields** to add before persist: `embedding_model_name/version`, `chunker_name/version`, `content_hash`, `ingest_ts`.

---

## 6. Interviews / job hunt 💤

**Where:** [`interviews.md`](interviews.md).

**Status:** Stub. Ramps Jun 30 (apply-day). Out of scope until then except: STAR stories naturally generated by promo work.

---

## 7. Health & fitness ⏳

**Where:** [`health.md`](health.md) (plan), weight + workouts logged in [`check-ins.md`](check-ins.md).

**Status:** Baseline 147 lbs (May 10). Target 127 by Sep 30. **Habit phase begins Tue May 12** (first gym morning).

**Open:**
- [ ] First gym morning Tue May 12 06:00
- [ ] Sleep on 22:30 cutoff starting tonight
- [ ] Weekly Sunday weigh-in (next: May 17)

---

## 8. AA 🟡

**Placeholder.** Goals + scope + anchor to be defined by user. Tracked here so it shows up in weekly review and standup planning.

**Status:** Awaiting user input on what AA is, what the goals are, and what the anchor date is. Agent should ask about this during the next check-in.

**Open:**
- [ ] User to define AA goals + anchor + first concrete milestones.

---

## Session log

Short notes per working session — date, what I did, what's next. Newest on top.

- 2026-05-19 — **Arch-Hive deck restructured into v2 + PPT-extract files shipped for both decks + Eugene deck got Templates→Agents slide (new Slide 9).** Arch-Hive v1 hit three rounds of feedback: (a) anonymization pass (drop "client", "AWS team"); (b) attribution fix — only FSR pipeline + AdHoc QA agent are mine, Unit Risk built by a separate team; (c) customer-data strip on Slide 5 (named lookups + 6-field schema removed). User then asked for full structural rewrite around honest scope + external-audience takeaways. v2 created at [`promo/eugene-track/arch-hive-slides-v2.md`](promo/eugene-track/arch-hive-slides-v2.md) — 11 main + 2 backup: overview with my-scope highlighted (Slide 4), FSR pipeline architecture + tradeoffs (5–6), AdHoc QA agent architecture + design choices (7–8), three patterns that travel (9), **new Slide 10 tech stack** (Databricks UC/Workflows/Delta/Vector Search, AWS Strands, LiteLLM single-gateway, OpenAI text-embedding-3-large via LiteLLM, Claude Code + GitHub Copilot — added so the audience knows where to reach me as SME later), close (11). Voice = "I" for design choices, "a separate team" for Unit Risk. Anonymization vs tech-naming split documented in the header: body stays vendor-neutral so patterns travel, Slide 10 names the stack so expertise can be reached. v1 kept as backup at [`arch-hive-slides.md`](promo/eugene-track/arch-hive-slides.md). PPT copy-paste extracts shipped for both decks: [`eugene-slides-ppt-content.md`](promo/eugene-track/eugene-slides-ppt-content.md) (12 main + 3 backup — Templates→Agents added as Slide 9) and [`arch-hive-slides-ppt-content.md`](promo/eugene-track/arch-hive-slides-ppt-content.md) (11 main + 2 backup). Embedding model confirmed from code (`pw_sdg_ai_ser_repo/common/fsr_config.py`): `azure-text-embedding-3-large-1` via LiteLLM (Azure OpenAI text-embedding-3-large, 3072 dims) — *not* Databricks Model Serving; Databricks-experience signal carried via UC/Workflows/Delta/Spark/Vector Search instead. LiteLLM (not Bedrock) named as the single gateway in front of Claude family (QA agent) + Gemini family (parts of pipeline). **Next:** user review of v2 → visuals pass on Arch-Hive Slides 4 / 5 / 7 (Slide 4 overview diagram first) → md → pptx for both decks; cert D-25 tonight (Udemy S1 + S3, 2h, non-negotiable).

- 2026-05-18 — **Eugene + Arch-Hive deck content fully drafted + FSR runbook review pass done.** All 11 Eugene slides (incl. B1–B3) and all 14 Arch-Hive slides (incl. B1–B3) filled with titles, sub-lines, body, talk tracks with timing, confidentiality guardrails, and "what NOT to do" notes. Voice convention shifted to neutral/collective across Eugene deck (no "I'm offering Slalom" framing — we're inside Slalom); Slide 8 retitled "Artifacts that close the loop". Arch-Hive confidentiality discipline enforced — every real table/field/lookup/tool/model name described by role only. FSR runbook: removed Setup Steps section (no provisioning steps — DA team owns deploy), added Build & deploy ownership section (Bronze=D&A, Silver/Gold=Dev, branch→workspace table dev/qa/main→ai-dev-dbr/ai-qa-dbr/ai-dbr, prod deploy flow via CCB), renamed title ("Handoff" → "Guide"). File now at `FSR/fsr-docs/FSR Pipeline - Runbook and Guide.docx`. Sreedhar L1/L2 Slack reviewed + sent earlier; Vinayaka follow-up reviewed. **Next (Tue):** user review both decks → visuals pass (Arch-Hive Slide 4 anchor diagram first) + share runbook with FSR team + Infy handoff note draft + cert D-0 carry tonight (Udemy S1 + S3, 2h, non-negotiable).

- 2026-05-17 (late evening) — **FSR runbook / handoff doc draft v1 landed.** 2-page docx at [`../FSR/fsr-docs/FSR Pipeline - Runbook and Guide.docx`](../FSR/fsr-docs/FSR%20Pipeline%20-%20Runbook%20and%20Guide.docx). Triggered by team-shared sample (SDG Infra & Build Pipeline Provisioning Guide). Read existing Confluence pages first (design + prod deploy plan in `FSR/fsr-docs/`) + `pw_sdg_ai_ser_repo` README to identify gaps; new doc fills provisioning (Page 1) + operations/repair (Page 2) without repeating Confluence content. Brought May 22 milestone forward by 5 days — user review Mon May 18. **Next (Mon):** user review pass on runbook; UI-21 + UI-22 FSR dig; cert D-0 carry (Udemy S1 + S3, 2h, non-negotiable).

- 2026-05-17 (evening) — **Eugene + Arch-Hive deck skeletons landed.** Created [`promo/eugene-track/eugene-slides.md`](promo/eugene-track/eugene-slides.md) (11 main + 3 backup slides; titles + 1-line intent each; recommended fill-order Slide 6 → 8 → 2 → rest) and [`promo/eugene-track/arch-hive-slides.md`](promo/eugene-track/arch-hive-slides.md) (14 main + 3 backup; fill-order Slide 4 anchor diagram → 7 → 11 → rest). Mined `unit-risk/8. AdHoc QA Agent.pdf` and `unit-risk/FSR-pipeline-databricks.pdf` for the agent + pipeline architecture; `unit-risk/GEV Gen AI Platform Architecture.pptx` was image-only (Google Slides export) so no text extractable — logged as open-decision in the skeleton, will OCR or request source only if needed for the slide-4 anchor diagram. **Confidentiality rule baked into the Arch-Hive skeleton:** no real table names, column names, lookup-source names, or tool names — describe by role only ("equipment-master lookup", "hard equipment-ID field", etc.). Slide 2 framing softened away from any implicit "others get it wrong" tone (no comparison to other RAG decks). User mid-review of arch-hive skeleton. **Next:** fill Eugene Slide 6 first (strongest, two-column author-side / reviewer-side setup for the AI-PR playbook offer).

- 2026-05-17 (afternoon) — **Eugene artifact review pass + offer-set restructure.** User-led review on [`promo/eugene-track/artifact-outline.md`](promo/eugene-track/artifact-outline.md). Substantive fixes: (1) 7A.1 ESN extractor stats corrected — "68% pure numeric" reframed as ~166-doc / ~1% Pattern-C cohort (project/IBAT/work-order leakage), with the caveat that numeric ESNs can be valid for non-GT equipment; (2) scan-quality `9→7` misread reframed as upstream PDF text-layer issue (phase 1 doesn't run OCR), keeping the cross-source-validation lesson intact; (3) 7B opener re-anchored from a fabricated "45-engineer weekend" framing onto the real Unit-Risk Agent partner-team engagement (~10-engineer client cloud-services team, long hours/weekends on a feature that broke on real production data); (4) ambiguous "model" replaced with "AI assistant" throughout 7B.1/7B.2 to avoid collision with Part A's embedding/foundation-model usage; (5) **offer set collapsed 4→3 templates** — dropped use-case×tool decision matrix (high maintenance, dates fast), combined 7B.3+7B.4 into a single AI-PR playbook (author checklist + reviewer prompts as two halves), added new 7B.5 = AI-ops cheat-sheet anchored on the 7A operational patterns (lifetime retry counters, failure-category enum, dry-run defaults, snapshot+revert). §12 templates list rewritten to match. Tracker May 14 entry corrected to log the May 17 re-anchor. Milestones #2-Reschedule-exam row marked ✅ done (booked Jun 13). **Next:** create slide content — Eugene deck at `promo/eugene-track/eugene-slides.md`, then Arch-Hive deck at `promo/eugene-track/arch-hive-slides.md`; both new docs with `artifact-outline.md` as durable source.
- 2026-05-15 (afternoon) — **FSR P0 missing-FSR investigation — verification done.** Built [`prod-issues/missing-FSRs/nb_missing_fsr_source_check.ipynb`](../fsr-prod-ops/prod-issues/missing-FSRs/nb_missing_fsr_source_check.ipynb), ran on Databricks prod (`vaip` catalog). Result: 10 of 11 file-name reports across 324X043 + 338X415 are bucket-E (not on either source volume → DA-team scope), **1 is bucket-D** (`8fe0793d-aef7-4ab0-80b2-7f5b6ebc1559` — on volume + in `fsr_pdf_ref` but never ingested across 367 P1 runs since 2026-04-30). Outputs (5 CSVs) in [`prod-issues/missing-FSRs/output/`](../fsr-prod-ops/prod-issues/missing-FSRs/output/). Vinayaka email + Rashmin Slack drafts in [`comms/2026-05-15/`](../fsr-prod-ops/comms/2026-05-15/) — **send today**. Tracker UI-20 closed-path; **UI-21 opened** for the bucket-D pipeline-discovery skip with a 4-step root-cause plan. Next: send the two messages → start UI-21 blast-radius query.
- 2026-05-15 (morning) — **Two new items landed before standup:** (a) 🚨 **FSR P0 — missing FSR data prod issue** (investigate today, pulls priority), (b) **OSA estimate ask** for OSA data pipelines (sizing reference prepared from FSR build — 12-phase decomposition + 26-step new-pipeline implementation list, delivered in chat; pending scope from requester). **FSR runbook / handoff doc** also added as a pending writeup (lower priority — last in queue). **Top 3 today:** (1) FSR P0 investigation, (2) OSA estimate scoping, (3) FSR ESN design + doc-summary PR follow-through. **Stretch:** Eugene artifact user review pass, runbook doc. **Standup for May 15 updated** to lead with the P0. **Anchor risk:** cert (D-29 to Jun 13) still zero movement.
- 2026-05-14 (late evening) — **Eric intro takeaway logged.** Per Eric's recommendation, get Anytime-Feedback recos from **Tao + Sreedhar** — elevated as a named open item under §3a. Refreshed Slack drafts (tighter than v1 in `feedback-asks.md`, no "Principal" / no Eric mention, soft 1-week window, concrete anchor per recipient, easy out). Drafts shared in chat — ready to send when user is.
- 2026-05-14 (evening) — **Artifact v1 drafted end-to-end.** Sections 1–6 reframed per review (anonymized, dropped 2.5-day backfill window, dropped 41-check number, softened "very few teams" language). Section 7 split into **7A** (system-side, 5 prod failure stories — ~1,200 words) and **7B** (engineering-with-AI patterns, 5 items, ~750 words — opener re-anchored May 17 onto the real Unit Risk Agent partner-team engagement, ~10-engineer client cloud-services team, long-hours/weekends on a feature that broke on contact with real production data; Eugene's "existential problem" quote landed in 7B.2). **Four explicit Offers** added in 7B.1, 7B.3, 7B.4, 7B.5 — design scaffold, prod-readiness checklist, AI-PR review prompt sheet, use-case × tool decision matrix. **Section 10** rewritten + anonymized + added "posture, not heroics" line. **Section 11** filled with honest 6-item "what we'd do differently" (incl. P1-not-parallelized honesty). **Section 12** rewritten with Slalom-as-audience lens, 4 named offers, Codex track + war-story / review-the-review / office-hours formats, named next conversations (Dave Messina, Christian, Chris Temple). **Voice convention locked:** "I" for synthesis/lessons, "we" for what was built. **Anonymization rule applied throughout** (no GEV name, no ESN jargon). **Pending:** user review pass → visuals.
- 2026-05-14 (morning) — **Eugene track activated.** Captured Eugene context from prior ChatGPT thread into tracker + roadmap. Three next moves locked: (1) outline AI-in-production artifact — *combined* with the Arch-Hive talk into one package (top slides = Arch-Hive architecture; deeper slides + appendix = Eugene lessons/guardrails/patterns); (2) readiness doc in Eric's new template (stitch in PL-aligned Section 5/6 from May 13); (3) schedule Eugene meeting once (1)+(2) are in hand. Started #1 — outline at [`promo/eugene-track/artifact-outline.md`](promo/eugene-track/artifact-outline.md). **Promo folder reorganized** (README + `conversations/` + `eugene-track/` + `_scripts/`).
- 2026-05-13 (afternoon) — **PL promo review at 3 PM done.** Notes in [`promo/pl-conversation-2026-05-13.md`](promo/pl-conversation-2026-05-13.md). Headline: visibility/brand is the #1 gap; Eugene is the gatekeeper. Pursuit experience confirmed strong. Section 5 (Goals) + Promotion Plan in xlsx rewritten around 3 PL-aligned goals: (1) Visibility/Brand — Databricks + GenAI/Agents, (2) Pursuit Lead in 2026 H2, (3) People-Leader Readiness. Section 6 asks updated to 6 items (added visibility/brand endorsement). Open items list refreshed with proactive follow-ups (Brie, Eugene artifact). Multi-ESN design doc updated with `esn_details` struct array (per-ESN equipment trio).
- 2026-05-13 (morning) — Priority-set for the day. Top 3: (1) Slalom manager review at 3 PM — pre-meeting prep + capture feedback, (2) FSR robustness open-items list for Abhijeet — consolidate UI-NN inventory into ticket-ready themes, (3) cert anchor risk (D-10) still blocked on Udemy materials. Carry: finish FSR doc-summary PR raise. Standup for May 13 written in [`ado/standup.md`](ado/standup.md).
- 2026-05-11 (evening) — **OSA Step 8 review shipped** to Mayank (Slack draft saved at [`../OSA/comms/2026-05-11-slack-mayank-step8-review.md`](../OSA/comms/2026-05-11-slack-mayank-step8-review.md)). **ADO workflow built** at [`ado/`](ado/) (README + stories.md + standup.md) — 8 FSR prod stories captured under epic 655509; standup script ready for Tue 6 AM. **Roadmap restructured** around 5 goal buckets (#1 Weight, #2 GE work, #3 Slalom promo a/b/c, #4 Cert, #5 Interview/POC). **Check-in workflow rewired**: user dumps in [`madhu-log`](madhu-log), agent writes formal entries — schema documented in [`check-ins.md`](check-ins.md). **Promo Q1+Q1a filled** in [`promo/user-inputs.md`](promo/user-inputs.md). User stopped here — tired. **Tomorrow (May 12):** finish `user-inputs.md`, draft Reflection + Plan, ship to manager. FSR sync with Pranesh + start doc-summary script also on the day.
- 2026-05-10 — Promo surprise injection. Manager template received. Built `promo/extract_inputs.py`, extracted 7 source docs to plain text under `promo/extracted/`. Built `promo/evidence-bank.md` (4 anchor stories + 30+ quotes + quant snapshot). Built `promo/user-inputs.md` for GEV/revenue/self-ratings. Pushed Phase 1 POC from May 14 → May 17.
- 2026-05-09 (evening) — User read nb_02 intro, asked how retrieval actually works — walked through index-time vs query-time. Drafted `code/demos/nb_02b_retrieval_demo.ipynb`. Notebook moved into `code/demos/`. **When resuming:** (1) run nb_02 top-to-bottom, (2) run nb_02b (slow embed cell ~2 min), (3) play with `QUERY` values, (4) move to step 5 — promote the demo into `nb_03_embed.ipynb`.
- 2026-05-09 — Added cert as priority. Drafted [`cert-prep.md`](cert-prep.md) mapped to course Weeks 1–4. Removed git from `ai-arch/` (local-only).
- 2026-05-08 — Set up `ai-arch/`. Wrote `learning-plan.md`, `tracker.md`, `decisions.md`. Picked FSR sample. Drafted `nb_01_ingest_parse.ipynb`. Created venv. Wired LiteLLM gateway.
