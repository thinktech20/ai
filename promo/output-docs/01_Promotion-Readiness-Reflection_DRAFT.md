# Promotion Readiness Reflection — Sr. Consultant → Principal

**Candidate:** Madhurima Saxena
**Target title:** Sr. Solutions Architect — Data & AI (Principal track)
**Draft date:** 2026-05-12 — **EARLY DRAFT for People Leader review**
**Status legend:** ✅ filled · 🟡 partial · ⏳ TO DO (need user/PL input)

---

## How to read this draft

This is an early v0 of the Reflection, mapped to the official Slalom template (`Reflection - To Principal` sheet of `Template - Promotion Readiness Reflection.xlsx`). It is meant to:

1. Show my PL where I'm landing on each Principal-level competency (self-rating + 1–3 supporting bullets).
2. Flag the items I still need help/input on before I move it into the official Excel.
3. Surface the quantitative case ($1M revenue, role mastery) so we can align on framing early.

**What's done:**
- Headline narrative ("why principal", anchor stories) ✅
- Self-rating + evidence bullets across all 13 competency rows ✅ (gut-call, to be refined with PL)
- Quantitative section — utilization, role mastery 🟡 (revenue still needs numbers)

**What's pending from me:**
- Final revenue numbers (Salesforce GIC managed, GEV managed, FruitCo) — will confirm with respective managers
- A couple more direct-quote feedback notes (Sreedhar/Pranesh/Tao requested, not yet received)
- Final calibration of self-ratings with PL

**What I'd like from PL:**
- Your read on each competency (PL Input column) — especially Lead → Lead & Develop Teams, and Grow Slalom → Drive Sales
- Whether the "Pursuit Lead" gap is the right one to anchor the Promotion Plan against
- Sanity check on framing the GEV "FSR pipeline pickup" as the headline Deliver Exceptionally + Lead story

---

## Section 1 — My Why (Reflection Summary)

**What's my why?** I want to operate at the level where I'm not just delivering an architecture but owning the outcome — the trust, the team, the business case, and the recommendation that holds up in front of the customer's executives and our internal leadership. The Principal title formalizes what I've been operating as on Salesforce GIC and GE Vernova: workstream owner who can flex between deep technical execution, advisory, and pre-sales.

**What are my career desires?** Continue as a customer-facing Solutions Architect in the Data & AI space — anchor at Slalom on Databricks + AWS + GenAI agentic patterns, lead pursuits end-to-end, and grow the next layer of Slalom architects through mentoring and the Databricks COE.

**How am I performing at current job expectations?** Per my 2025 EOY appraisal (Manager Evaluation), rated **Above Expectations**, with the manager noting *"her impact to multiply beyond the remit typical of a Senior Consultant"* and *"consistently demonstrated leader-like qualities… beyond those of a more specialized data engineer."* Operating informally at Principal scope on Salesforce GIC (workstream lead) and GE Vernova (Slalom delivery owner for FSR pipeline).

⏳ **TO DO:** Tighten the "why" into 2 sentences (will refine after PL conversation).

---

## Section 2 — Anchor Stories (background for the competency ratings below)

These are the projects I lean on across the rest of the Reflection. Full detail in `evidence-bank.md`.

1. **GE Vernova / AWS — SDG / FSR pipeline (2026, current)** — Picked up the FSR data pipeline end-to-end on short notice when the GE architect raised to the PM that the team did not have the Databricks skillset, and the upstream-data gap had put production at risk. Delivered the production backfill (17,967 / 18,094 docs = **99.3%**, 1.09M chunks, 0.43% failure rate, all corrupt-source PDFs). Now active design partner on the AdHoc Q&A Agent (Strands ReAct + Claude 4.6 Sonnet + MCP tools) and Unit Risk Agent.
2. **Salesforce GIC / ICM (2025–present)** — Workstream Lead on multi-quarter analytics modernization. Surfaced ~33% of upstream data wasn't SOX-compliant. Authored the North Star Architecture, presented two future-state options to C-level + enterprise architects, drove ~80% reduction in manual effort. Engagement extended; client requested me back; **NorCal H2 Mogul Award nomination**.
3. **Apple / FruitCo (2023–2024)** — Sole Slalom architect ~12 months. Lakehouse on AWS Glue + PySpark + Iceberg + Airflow + Trino + Tableau. **90% data-accuracy improvement**, customer adopted the architecture for all datasets (scope expansion), **Customer Impact Award from Debra Ameerally (Apple)**.
4. **Pre-sales + Internal Slalom (cross-year)** — BayREN RFP (~$2–3M D&A pipeline contribution per IW), Salesforce–Informatica Merger RFP, Genentech gRED, Proofpoint, MTC RFP, AWS MAP funding. Internal: Data Arch-Hive (May 2026), Databricks COE Insurance 360, weekly Databricks L&L sessions, Databricks Data Engineer Associate cert (2025).

---

## Section 3 — Competency Self-Reflection (Sr. Consultant → Principal)

Format mirrors the official template: **Self Reflection** rating + bullets for **Examples and Feedback**. PL Input column left blank for the manager. Ratings: **4 = Consistently Demonstrates · 3 = Sometimes Demonstrates · 2 = Improvement Needed · 0 = Not Started.**

### 3.1 Deliver Exceptionally

#### Execute Effectively
**Principal expectation:** Responsible for solution and/or overall project outcomes · Credits others publicly · Proactively removes obstacles (self & others) · Ensures multiple POVs are integrated · Creates clarity of roles and functions.

**Self-rating: 4 — Consistently Demonstrates**

**Examples:**
- **GEV / FSR (2026):** Took end-to-end ownership of the production FSR data pipeline when the GE architect declined the Databricks scope to the PM. Drove backfill to **99.3% success (17,967 / 18,094 docs)** in the planned 2–2.5 day window; hardened the run-loop (claim-based locking, retry caps, P1 telemetry, 41-check DQ validation). Owned the outcome, not just the deliverable.
- **Salesforce GIC (2025):** Operated as workstream lead on a multi-quarter ICM modernization. SD Singh: *"You have demonstrated leadership without authority… would have done a reasonably good job of being the engagement lead."* [FB-SDSingh-2025-06-12]
- **2025 EOY Manager Evaluation:** *"award-winning client delivery, and demonstrated ability to flex between data engineering, architectural, and stakeholder management responsibilities."* [EOY25-MgrEval]

#### Develop High-Impact Solutions
**Principal expectation:** Applies best practices to accomplish project and organizational objectives · Enlists expertise to determine "best fit" solutions · Guides work (self & others) for prioritization, quality, accuracy.

**Self-rating: 4 — Consistently Demonstrates**

**Examples:**
- **GEV / FSR:** Designed the run-loop architecture so backfill and incremental run on the same code path; introduced claim-based parallel chunking, lifetime retry gate, run-log telemetry, and a 41-check standalone DQ job for SRE handoff.
- **Salesforce GIC:** Designed two future-state architecture options (S3 + Snowflake vs S3 Lakehouse) and authored the **North Star Architecture** aligned with the client's enterprise platform direction. Presented to C-level + enterprise architects.
- **Apple / FruitCo:** Lakehouse build on AWS Glue + PySpark + Iceberg + Airflow + Trino + Tableau, medallion architecture, Great Expectations for DQ. **90% data-accuracy improvement**, customer adopted for all datasets.

#### Know & Serve Our Customers
**Principal expectation:** Creates authentic, trusting relationships at many levels · Understands informal org structures and constraints · Displays executive presence · Navigates discrepancies in customer and Slalom needs.

**Self-rating: 3 — Sometimes Demonstrates** *(strong relationship-building; executive-presence is the consistent growth thread)*

**Examples (strong):**
- Tim Lin (Salesforce client Manager): *"I've never seen such data in all my years at Salesforce."* [MID25]
- Hong Wu (Salesforce client Director): *"Will Madhurima have insight into it? Will she provide input into what that plan looks like?"* — pulled into senior-level data-governance planning. [FB-SDSingh-2025-06-12]
- Debra Ameerally (Apple senior exec): Customer Impact Award + *"stands out for her quiet and diligent work."* [FB-Brad-2024-04-10]
- Maya Sandler: *"Her ability to build a strong, trusting relationship with the client was particularly evident when it directly led to the project's extension for the next phase."* [FB-MayaSandler-2025-06-20]

**Growth area I own:** Tailoring communication for executive audiences — succinct, visually-engaging stories that "connect the dots" for execs. Called out in feedback from Matt Ngai, Maxine Leu, SD Singh, and the 2025 EOY Manager Evaluation. ⏳ Goal in the Promotion Plan.

⏳ **TO DO:** Awaiting written feedback from Sreedhar Sannidhanam (GEV) — will add a direct quote here when received.

### 3.2 Grow Expertise

#### Deepen & Broaden Expertise
**Principal expectation:** Deepens and/or broadens in Functional / Technical roles · Recognized for expertise · Mentors others · Builds mastery in Pursuit & Engagement roles; increases exposure to Business roles.

**Self-rating: 4 — Consistently Demonstrates**

**Examples:**
- **Data Architect — Advanced+** (per peer + manager validation). Sean Ipakchi: *"Resident NorCal AWS Data Architecture expert."* [FB-SeanIpakchi-2023-12-19]
- **Active broadening into GenAI / agentic patterns:** Strands ReAct framework, Claude 4.6 Sonnet via FastAPI / Streamable HTTP, MCP-exposed data services, S3SessionManager, persona-based tools — solutioning + design partner on the GEV AdHoc Q&A Agent and Unit Risk Agent.
- **Databricks Data Engineer Associate certification (2025);** AWS Certified Data Analytics – Specialty (2021); active across Databricks Lakehouse + Vector Search + Unity Catalog.
- **Mentoring** — Erika Morris (Apple/FruitCo, end-to-end DE upskilling), Maya Sandler (AWS pipelines), Slalom colleagues for Databricks + AWS certifications.

#### Broaden Slalom Knowledge
**Principal expectation:** Expands knowledge of Slalom business · Ensures Slalom stories are captured timely and accurately.

**Self-rating: 3 — Sometimes Demonstrates**

**Examples:**
- **Data Arch-Hive session (May 2026)** — co-presented FruitCo end-to-end Lakehouse + AI walkthrough with Raghav. Karthik Mannava: *"the back-and-forth with the audience turned it into a genuine learning conversation… everyone walked away having learned something new."* [FB-Karthik-2026-05-08]
- **Databricks COE — Insurance 360** — supported in-house solution build; dashboards showcased to the Databricks team and at the **London Databricks meetup**. [FB-Pragathi-2026-01-26]

⏳ **Growth:** more proactive Slalom-story capture (account anecdotes → reusable internal artifacts).

#### Build Slalom Capabilities
**Principal expectation:** May lend expertise to enhance capabilities · May contribute to cross-market community.

**Self-rating: 3 — Sometimes Demonstrates** *(could be 4 with the Databricks COE work)*

**Examples:**
- **Databricks COE** — weekly Databricks Learning sessions + Insurance 360 in-house solution. Emanuel Ward: *"contributes to the Databricks Learning sessions on a weekly basis… key to supporting and growing our partnership with Databricks."* [FB-EmanuelWard-2025-11-12]
- **Cross-market reach:** dashboards from Insurance 360 showcased at the London Databricks meetup (cross-geo).
- **GenAI Cohort capstone (2024)** — solution architect on the DMV-prep GenAI assistant.

### 3.3 Grow Slalom

#### Build Community
**Principal expectation:** Intentionally grows and manages professional network in delivery environments and/or area of expertise · Encourages others to engage in Slalom events · Models Slalom brand stewardship.

**Self-rating: 3 — Sometimes Demonstrates**

**Examples:**
- Active in NorCal AWS + Databricks community across delivery and L&L.
- **Networks built and maintained across:** Salesforce GIC (Hongwu Wang, Tim Lin, SD Singh, Maya, Matt Ngai), Apple/FruitCo (Debra Ameerally, Pete Obringer, Julie Thomson, Erika), GEV (Sreedhar, Pranesh, Abhijeet, Tao), Slalom Databricks COE (Pragathi, Emanuel, Karthik), cross-eng (Maxine, Raphael, Aprajita).
- Ongoing engagement with Slalom Databricks partnership team and AWS alliance team.

⏳ **Growth:** more outward Slalom brand stewardship (blog posts, public speaking, external community).

#### Manage Business Operations
**Principal expectation:** Proactively maximizes staffability (self & others) · Responsible for aspects of project financial & operational health (margin, managed revenue, staffing, engagement).

**Self-rating: 3 — Sometimes Demonstrates**

**Examples:**
- **Utilization: 86.3% (2025), 93% (H1 2025).** Above the 80%+ Principal bar.
- **Staffing leadership on Salesforce GIC** — Maxine Leu: *"Acted with high urgency to screen several Slalom candidates for a backfill / team expansion staffing need and is taking the lead to onboard the new Slalom team members."* [FB-MaxineLeu-2025-06-11]
- **Operating as the Slalom delivery owner** for the FSR data pipeline workstream on GEV (engagement health partnership with Sreedhar).

⏳ **Growth / TO DO:** confirm managed-revenue numbers for Salesforce GIC and GEV with PL + account leads — see Section 4 Quantitative.

#### Drive Sales
**Principal expectation:** Proactively identifies opportunities for Slalom in delivery environments and/or area of expertise · Begins leading and/or solutioning for pursuits.

**Self-rating: 3 — Sometimes Demonstrates** *(approaching the "lead a pursuit end-to-end" bar)*

**Examples:**
- **~$2–3M in D&A pipeline influenced** through pre-sales (per IW.pdf, anchored on BayREN RFP — technical solution lead, advanced Slalom to final selection).
- **Pre-sales contributions across:** Salesforce–Informatica Merger RFP, Genentech gRED Sales, California Community Colleges, Proofpoint (data-ingestion review on short notice), MTC RFP, AWS MAP funding (zero-cost POC for healthcare client).
- Raphael Vannson (Proofpoint pre-sales): *"Madhurima quickly pivoted and helped reviewing the data ingestion approach… Slalom was able to make a confident and relevant presentation to the client and credentialize us on the data ingestion portion in addition to the AI portion of the solution."* [FB-Raphael-2025-06-05]
- **Account extension wins** I've contributed to: Apple/FruitCo (architecture adopted for all datasets → scope expansion), Salesforce GIC (engagement extended on client request), Apple (engagement extended through end-of-FY into next FY).

⏳ **Honest gap:** I have not yet **led** a pursuit end-to-end as Pursuit Lead — that is the Principal-bar gap I'd like to anchor a Promotion Plan goal against.

### 3.4 Lead

#### Lead & Develop Self
**Principal expectation:** Builds skills to identify and mitigate personal biases · Proactively manages self to protect energy, drive efficiency · Experiments with new approaches; fails fast and applies learnings · Openly and authentically shares values, assumptions, imperfections.

**Self-rating: 4 — Consistently Demonstrates**

**Examples:**
- **Stretched into GenAI / agentic patterns** in 2025–2026 from a data-engineering / lakehouse foundation — Strands ReAct, MCP, Vector Search, embeddings + chunking strategies — and brought that into delivery on GEV.
- **Continuous learning:** Databricks DE Associate (2025), AWS Data Analytics Specialty (2021), GenAI Cohort capstone (2024), weekly Databricks L&L participation.
- 2025 EOY Manager Evaluation: highly engaged on professional development as an ongoing topic in 1:1s; *"interest and time investment has been apparent and demonstrable."* [EOY25-MgrEval]

#### Lead & Develop Others
**Principal expectation:** Celebrates uniqueness and empowers others · Models the habit of regularly requesting and providing feedback · Encourages conversations that empower open dialogue · Supports others in defining their path forward.

**Self-rating: 3 — Sometimes Demonstrates**

**Examples:**
- **Erika Morris (Apple/FruitCo mentee):** *"Madhurima has devoted time and effort to upskill me in data engineering by being extremely available for trouble-shooting, answering questions, and pair-programming whenever I encounter issues. She has been patient and understanding at all times, reserving judgement and making me feel very comfortable asking any questions I may have."* + *"This demonstrated Madhurima's potential as a future people leader."* [FB-Erika-2024-07-01, FB-Erika-2024-11-22]
- **Maya Sandler:** *"Is a true leader in the AWS community in Slalom, inspiring and mentoring others."* [FB-MayaSandler-2024-10-16]
- **Salesforce GIC** — onboarded new Slalom team members during backfill / team expansion (per Maxine Leu feedback).
- **Nabor Reyna (iRhythm):** *"Empowered team members to ask questions, and grow their expertise. When teammates were confused she helped lead working sessions and helped remove obstacles."* [FB-Nabor-2023-11-28]

⏳ **Growth / honest:** No formal direct reports. Mentoring is ad-hoc rather than structured.

#### Lead & Develop Teams
**Principal expectation:** Anticipates risks and proactively addresses obstacles to unblock the team, delegating as needed · Proactively removes barriers for productive conflict · Co-creates team vision, strategy, targeted outcomes · Establishes norms for open-mindedness and non-judgement.

**Self-rating: 3 — Sometimes Demonstrates**

**Examples:**
- **GEV / FSR:** unblocked the team by taking the Databricks pipeline scope when it had no owner; designed the run-loop so the team can operate it without me in the critical path (telemetry, DQ validation job, claim-based locking, retry caps).
- **Salesforce GIC:** SD Singh: *"That is how Slalom is perceived — we come in, make a significant impact, and leave the client better than where they started. You are doing that."* [FB-SDSingh-2025-06-12]
- 2025 EOY Manager Evaluation: *"consistently demonstrated leader-like qualities within her delivery teams, and the adaptability to support both engineering and architectural outcomes, beyond those of a more specialized data engineer."* [EOY25-MgrEval]

⏳ **Growth area I own:** more proactive **risk flagging to the broader team** (not just 1:1s) and **diplomatically challenging clients** earlier when expectations are misaligned. Called out by Maxine, Pete Obringer, Erika.

#### Serve As Formal People Leader (Optional)
**Principal expectation:** *Optional w/ mastery & business need.* Proactively connects employees to development experiences · Defines how directs' work connects to Slalom's goals · Ensures performance expectations + feedback · Translates org change.

**Self-rating: 0 — Have not Started** *(no formal direct reports)*

**Note:** Optional row at Principal level. Informal mentoring is captured under Lead & Develop Others. Open to discussing whether to pursue formal PL responsibilities post-promotion.

---

## Section 4 — Quantitative Expectations & Role Mastery (Principal bar)

| Item | Principal Bar | My Position | Status | Note |
|---|---|---|---|---|
| Utilization (Self) | 80%+ | **86.3% (2025), 93% (H1)** | ✅ Meets | Above bar consistently. |
| Revenue (Primarily Sold or Managed) | $1M | Salesforce GIC managed revenue (multi-quarter, workstream lead) + GEV managed revenue (current) + ~$2–3M influenced pre-sales pipeline (BayREN-anchored, per IW) | 🟡 Partial — **need numbers** | ⏳ TO DO: confirm $ figures with SD Singh (Salesforce), Sreedhar Sannidhanam (GEV), Pete Obringer (FruitCo). Frame as managed revenue + influenced pipeline. Gap = leading a sold pursuit end-to-end. |
| 1+ Functional / Technical Roles: Advanced+ | Yes | Data Architect — Advanced+ (peer + manager validated); broadening into GenAI / agentic patterns | ✅ Meets | |
| Engagement Lead or Delivery Solution Lead: Foundational+ | Foundational+ | Operating as workstream lead on Salesforce GIC; Slalom delivery owner for FSR pipeline on GEV | 🟡 Meets (informal) | SD Singh: *"would have done a reasonably good job of being the engagement lead."* Open question: formalize the title. |
| Pursuit Lead or Sales Solution Lead: Foundational+ | Foundational+ | Contributor on BayREN, Informatica RFP, iRhythm POC, Proofpoint, MTC RFP, Cal Comm Colleges, Genentech | 🟡 Approaching | Gap = lead a pursuit end-to-end as Pursuit Lead — anchoring this as a Promotion Plan goal. |
| People Leader: Proficient+ | Optional | No formal directs; informal mentoring (Erika, Maya, Slalom colleagues for certs) | 0 | Optional at Principal — not a blocker. |

---

## Section 5 — Goals + Support Needs

These are the gaps surfaced by my self-reflection + recurring growth themes from feedback. They feed into the **Promotion Plan** (separate doc).

| Opportunity Area | Goal to Address | What I'd Need |
|---|---|---|
| **Drive Sales — Lead a Pursuit end-to-end** | Take Pursuit Lead role on at least one D&A / GenAI pursuit in 2026 H2 (lead solutioning, write technical sections, own the pricing conversation, present to client). | PL to surface a fit-for-me pursuit; partnership with a Slalom Sales Lead. |
| **Tailoring communication to executive audiences** | Build a personal pattern for "exec-ready" deliverables — succinct, visually engaging, "connect the dots" framing. | Pair with a Principal/Director on 1–2 exec readouts in next 6 months; feedback loop with PL. |
| **Diplomatically challenging clients earlier** | Flag misalignment / unrealistic expectations to clients sooner (not just 1:1s with Slalom team). | Coaching from PL or peer Principal on "hard conversations" framing. |
| **Big-impact thinking** (vs low-hanging fruit) | Frame architectural recommendations against the bigger business outcome up-front, not after MVP. | Sounding board on GEV / Salesforce architectural decisions before they go to client. |
| **Project-management / Solution-Owner side** | Strengthen blocker-surfacing + clarity-driving cadence on workstreams I lead. | Pair with a SO on one engagement to observe the SO motion. |
| **Slalom story capture + brand stewardship** | Convert one delivery into a reusable internal artifact (Data Arch-Hive #2 or COE asset). | 4–6 hours of bench time + PL endorsement. |

---

## Section 6 — What I Need From PL (for our conversation)

1. **Calibration** — your read on each competency rating, especially Lead & Develop Teams + Drive Sales.
2. **Anchor confirmation** — is the GEV / FSR pickup the right headline for Deliver Exceptionally + Lead?
3. **Pursuit Lead opportunity** — can you help surface a fit-for-me pursuit in 2026 H2 so I can close the "led a pursuit end-to-end" gap?
4. **Revenue numbers** — guidance on Salesforce GIC + GEV managed-revenue figures, or who I should ask.
5. **Title framing** — Sr. Solutions Architect — Data & AI vs. other Principal-level title options.

---

## Open Items I'm Working On (after this conversation)

- ⏳ Receive written feedback from Sreedhar Sannidhanam (GEV), Pranesh, Tao — drafts in `feedback-asks.md`.
- ⏳ Confirm managed-revenue numbers (Salesforce GIC, GEV, FruitCo).
- ⏳ Tighten "why principal" to 2 sentences for the Reflection Summary slide.
- ⏳ Write the Promotion Plan (separate doc — `02_Promotion-Plan_DRAFT.md`).

---

*References: `evidence-bank.md` (full quote sources), `user-inputs.md` (in-progress raw inputs), `feedback-asks.md` (pending GEV feedback drafts), `extracted/previous-recommendation__Feedback_Received.md` (verified quote source), `extracted/previous appraisal__Saxena, Madhurima 2025 EOY.md` (Manager Evaluation source).*
