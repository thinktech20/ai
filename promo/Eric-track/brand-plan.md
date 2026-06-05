# Brand Plan — Visibility for Principal

**Owner:** Madhurima · **PL:** Eric · **Created:** 2026-05-20 · **Horizon:** May 20 → end of June 2026

Single source for the visibility / brand work that closes the one gap Eric + Josh flagged in the May 15 1:1. Everything in [`ai-arch/promo/`](..) ladders to the outcome below. If a workstream doesn't ladder, deprioritize.

---

## 1. The outcome (one line)

> When someone in the practice needs **RAG productionized on Databricks** or **an agent built end-to-end on AWS**, they think of me.

Today the brand is "AWS." Target brand by end of Q3: **AI + Databricks + RAG / agent productionization.**

## 2. Why this is the right brand (proof already exists)

- **FSR pipeline (GEV)** — RAG pipeline in prod on Databricks. 17,967 / 18,094 PDFs backfilled (99.3%), 1.09M chunks, 3072-dim embeddings, Vector Search index live. End-to-end ownership including DDL, run-loop, DQ, SRE handoff.
- **AdHoc QA agent (GEV)** — Agentic AI with dynamic tool selection across multiple data sources, multi-step LLM-controlled iteration. Tao's written feedback (2026-05-20) calls this out specifically.
- **OSA / Unit Risk design partnership** — downstream agents grounded on the FSR layer.

I'm not inventing a story — I'm converting delivery already in flight into visibility artifacts.

## 3. The 6-week plan

| When | Channel | Topic / Deliverable | Audience | Status |
|---|---|---|---|---|
| **2026-05-22** | Arch-Hive talk | FSR pipeline + AdHoc QA agent end-to-end (architecture + tech stack + lessons) | Practice-wide | In flight — deck v2 ready; visuals + md→pptx pending |
| **End of May** | Eugene's AI-in-prod artifact | "What breaks when you put AI in production" — patterns + anti-patterns from FSR | Eugene + leadership | Open — closes Eugene's standing ask |
| **First week of June** | Internal article + Medium | Productionizing a RAG pipeline on Databricks — concrete, opinionated, code-level | Slalom-wide + external | Not started |
| **Mid-June** | Brown bag #1 | Building + productionizing an agent on AWS — live demo with Strands | Practice | Not started |
| **Late June** | Brown bag #2 | Productionizing a RAG pipeline on Databricks — live demo | Practice | Not started |
| **Ongoing** | Brie's AI demo team | Stay in, take a real demo when one lands | Sales / pursuits | Volunteered; awaiting team formation; follow up this week |
| **Ongoing** | Databricks COE (Pragathi, Sownya) + Friday eng sessions (Maya, Emanuel) | Move from attender → contributor; pitch FSR-prod lessons as a session | Cross-practice | Already inside |

## 4. Asks of Eric

- **Reviewer + amplifier**: read the Eugene artifact before it goes out; help push the article internally; intro to the right brown-bag slot.
- **Brand framing**: when my name comes up in his conversations, the line is *"FSR-in-prod / agent productionization"* — not *"AWS"*.
- **Cadence sanity-check**: does May 22 → end-of-June feel right or does he want it tighter?
- **One artifact review per workstream** would help — Eric reads draft, gives a 10-minute steer.

## 5. Asks of me — this week

- [ ] Send Eugene a Slack with the artifact target date (proactive close on his standing ask).
- [ ] Follow up with Brie on the demo team status — **from me, not Eric** (Eric reinforced 5/20).
- [ ] Lock the Arch-Hive May 22 visuals + md→pptx.
- [ ] Outline the Eugene artifact (the same outline doubles as the article + brown bag #2 spine).
- [ ] **Easy-cadence outreach pings** (per Eric 5/20): one-line Slack/teams DMs to Pragathi, Sownya Ghosh, Emanuel Ward — "have cycles, here's what I'm building, let me know where I can plug in." Copy-paste-replace-name pattern. **Drafts ready at [`outreach-drafts.md`](outreach-drafts.md)** — send Thu May 21 AM.
- [ ] Schedule a short walk-through of FSR + AdHoc QA for Eric in a future 1:1 — he asked for it explicitly.

## 6. What's already in motion (Eric: "document this")

From the 1:1 transcript — Eric was not aware of several of these. Keep this list current so it's ready when Eugene reviews.

- **Databricks COE** — London Summit accelerator with Pragathi + Sownya
- **Databricks Friday engineering sessions + cert cohort** with Maya + Emanuel; held others through their Data Engineering cert
- **RFP solutioning** — Maxine + SD pulled me in on an AI RFP
- **Stage 4 SOW** — resource/allocation work with Erica + Aprajita
- **Arch-Hive presentation** (with Raghav) — first one done
- **Brie's AI demo team** — volunteered
- **Tao written feedback** (2026-05-20) — strong note on AdHoc QA leadership + FSR initiative + design partnership + communication; verbatim in [`../feedback-asks.md`](../feedback-asks.md)
- **Sreedhar verbal feedback** — prod-readiness drive; written ask still out
- **Active networks**: Kashin, Erica, Pete, SD, Maxine, Raya, Aprajita, Eugene, Jay, Tao, Sreedhar, Pranesh, Abhijeet, Pragathi, Sownya, Maya, Emanuel, Raghav, Anu, Amit

## 7. Eric's May 15 1:1 — captured asks

From [`05-15-transcript`](05-15-transcript). Every item folds into §3 or §6.

1. Document everything currently in motion — he wants to read the sheet.
2. Pick a brown bag topic + run it (specific technical demo).
3. Finish Eugene's AI-in-production artifact + send it.
4. Follow up with Brie on demo team (proactive, not waiting).
5. Keep Arch-Hive cadence (not a one-off).
6. Write an article (internal or Medium).
7. Reach into employee communities.
8. Be proactive — don't wait for people to come to you.

## 8. Tracker integration

- [`ai-arch/tracker.md`](../../tracker.md) §3a/3c rolls up to this plan; brand-plan is the single source.
- [`ai-arch/check-ins.md`](../../check-ins.md) evening entries should reference the row in §3 that moved.
- [`ai-arch/promo/output-docs/01_Promotion-Readiness-Reflection_DRAFT.md`](../output-docs/01_Promotion-Readiness-Reflection_DRAFT.md) pulls evidence from §6; readiness narrative aligns with the §1 brand line.

---

## 9. Eric May 20 1:1 — what changed

Source: [`05-20-transcript`](05-20-transcript). Eric reinforced §1, added concrete mechanics, and named new channels.

### 9a. Reinforced (no change to brand)
- **Visibility is the #1 lever** — confirmed again. "I know you can explain ideas, I know you can do the technical work — now we need to elevate that and prepare you to be a people leader."
- Brand framing for Eric in conversations: stays as §1 line — RAG productionization on Databricks + agent on AWS.

### 9b. New mechanics — how visibility actually happens
- **Easy cadence > big effort.** "It never has to be complicated. Send a message, you remember we talked about this, I want to follow up on this, I have cycles available to help with pursuits — ping me anytime. Then copy-paste, send to someone else, replace the name." → Slack/teams ping pattern is the unit of work, not a polished deck.
- **Make presenting easy.** "We need to come to a point where it's easy for you to put together a presentation without spending too much of your time." → invest in a reusable deck/talk-track inventory rather than bespoke one-offs.
- **Initiate, don't wait.** "Don't be hesitant to be the one who initiates the bigger conversation. You send a Slack message and say 'I'm going to schedule a 30-minute call next week to talk about this.'"

### 9c. New visibility channels named
- **West region Leads Monday morning call** — Eric + Bree + Eugene + Kashi + Emanuel on the call. Eric will surface my name there as I do things. → keeps a Mon-cadence audience that hears about output without me needing to be on the call.
- **Outside-of-market = same team now.** No geographic limit. Databricks COE (Pragathi + Sownya) and Friday eng sessions (Emanuel + Maya) are open — just keep in-market leads informed.

### 9d. Explicit nudges (folded into §5)
- Ping **Brie** — from me, not from Eric.
- Ping **Pragathi** — Databricks COE re-engagement.
- Ping **Sownya Ghosh** — Databricks COE.
- Ping **Emanuel Ward** — Databricks COE + Friday eng sessions.

### 9e. Positioning shift — AI architecture SME
- Eric framed it explicitly: present me as **a specialist, not just available bandwidth**. "When you're a SME, you're not asked just because you happen to be there — you're asked because you know something really well."
- Prior SME pattern (Salesforce, ~8h/week as SME for D&A) is the precedent.

### 9f. Capability leadership — the surfacing gap
- Delivery-leadership work I already do (cross-functional coordination, hiring/interviewing, mentoring) **counts** — Eric confirmed.
- The gap is **capability leadership** — improving how the practice works, helping team members across projects, building artifacts that lift others. This is what needs surfacing for principal.
- Promotion narrative: Eric does the talking when the case is presented — my job is to feed him surfaceable artifacts.

### 9g. References bank (for when the case goes up)
People who have seen capability/delivery leadership first-hand and can speak to it:
- **SD** (Salesforce, recent)
- **Erica** (Fruitco)
- **Maxine** (AI RFPs)
- **Matt Ngai** (Salesforce, principal)
- **Maya** (Salesforce)
- **Pragathi**, **Sownya** (Databricks COE / London Summit accelerator)
- **Emanuel** (Databricks Friday eng + cert cohort)
- Fruitco mentee (BA → DE transition; name TBD)

### 9h. Open threads from Eric
- **Tao's feedback → Workday.** Eric will add a blurb at the top and submit. No action on my side beyond keeping the verbatim quote handy.
- **Tao's feedback → account manager (new 2026-05-23).** Short Slack/email to the GE account manager surfacing the verbatim quote + summary. Visibility move — client praise in front of the AM who can amplify upstream. Same pattern as the Workday handoff, different audience.
- **Fruitco re-engagement** — Eric checking fit. I said open to it; not a yes/no commitment yet.
- **Eric will write his own summary list** of what we covered + the leadership track plan. I should keep brand-plan §6 + §9 current so it stays aligned with his version.
- **Principal role reality check** — 85% util target + leadership cycles. Either I add hours or trim delivery to free up leadership time. No decision today; surfaces in weekly planning.

### 9i. Past context
- Promotion guidance prior to Eric (Erica → Raya → Joshua) was "kept vague" — recommendations + cert were good things but pointed at "better consultant," not "leader." Eric making it concrete now.
