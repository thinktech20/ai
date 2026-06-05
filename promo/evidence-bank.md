# Evidence Bank — Promotion to Principal

**Purpose:** Single source of truth for stories, metrics, and quotes used in the Reflection + Plan. Pulled from 2023–2026 appraisals, peer feedback, and interview prep doc. Refer back here when drafting; do not re-mine sources.

**Sources cited as:** `[EOY25]` `[MID25]` `[FB-name-date]` `[IW]` `[Role]` `[2026-user]`

---

## Story Bank — Top 4 Anchor Stories

These are the projects we lean on across the Reflection. Each one hits multiple competencies.

### 1. GE Vernova / AWS (2026, ongoing) — CURRENT, **HEADLINE STORY**
**Role:** AI Engineer / Solutions Architect (working title) — targeting Sr. Solutions Architect — Data & AI
**Engagement:** GE Vernova Service Demand Generation (SDG) program — GenAI-driven early-warning signals from 40 years of unstructured Field Service Reports + procedure docs + Engineering Review cases, to convert reactive outages (2+ yrs downtime) into planned outages (6–7 months).

**My delivery scope (3 pieces):**
1. **FSR data pipeline** — production, end-to-end on Slalom side. Databricks workflow: ~17.8K FSR PDFs → pdfplumber → LLM normalization (LiteLLM) → IBAT / Event Vision / PSOT enrichment → claim-based parallel chunking → 3072-dim embeddings → Vector Search sync. Backfill + incremental on same code path, 41-check DQ validation job. Post-backfill (May 2026): drove the operational-maturity wave — multi-ESN fan-out patch (one metadata row per ESN with IBAT-resolved equipment type), VS-sync hotfix with retention + daily safety-net schedule (UI-22), doc-summary path (UI-04), ESN resolution design (UI-15), and a shareable Pipeline Runbook & Guide for the downstream D&A and SRE teams.
2. **AdHoc Q&A Agent** — solutioning + design partner. Strands ReAct, Claude 4.6 Sonnet, FastAPI / Streamable HTTP, S3SessionManager, MCP-exposed data services, persona-based tools (RE vs OE), ECS Fargate. Led the Agentic AI design with dynamic tool selection across multiple data sources and multi-step LLM-controlled iteration (per Tao's written feedback below). Ongoing partnership with AWS ProServe on metadata-tagging strategy for retrieval quality (Jon / Tao alignment, May 2026) — surfaced chunk-level evidence that GT-tagged chunks were carrying generator content, which is shaping the next round of tagging + filter design.
3. **Unit Risk Agent** — solutioning + design partner. Rules-from-procedure-docs + FSR test-result reasoning, contract-aware recommendation with grounded evidence.

**HEADLINE STORY — "Picked up FSR pipeline on short notice when prod was at risk" (Deliver Exceptionally + Lead):**
- **Situation:** Late in the program, the client realized there was a major gap — upstream FSR data had not been delivered to the team as planned. With production launch approaching, this was a real risk of missing the go-live.
- **Complication:** The GE architect on the engagement raised to the product manager that the team did not have the Databricks skillset to take this on. The work needed an owner.
- **Action:** I volunteered to pick up the Databricks pipeline work end-to-end. Partnered with the AWS engagement manager (Sreedhar Sannidhanam) and GEV client-side tech leads (Pranesh, Abhijeet) to scope and unblock the path to prod.
- **Result:**
  - **Production backfill: 17,967 / 18,094 FSR PDFs processed (99.3%)** in the planned 2–2.5 day window (Apr 30 – May 2, 2026). 1.09M chunks + 3072-dim embeddings written to Vector Search. Failure rate 0.43% (77 docs, all traced to corrupt source PDFs, audited in tracker).
  - **Incremental + backfill on the same code path** — one workflow handles daily ops and bulk loads.
  - **Hardened the run-loop:** claim-based locking for parallel P2 workers, retry caps + lifetime retry gate, P1 run-log telemetry (previously absent), DQ log de-dup + failure-category enum, 41-check standalone DQ validation job for SRE handoff.
  - **Trust:** now active design partner on AdHoc Q&A + Unit Risk + OSA reuse conversations — FSR pipeline is the grounding layer downstream agents are built on.
- **Why it matters for promo:** end-to-end ownership of a production-critical workstream that the original architect had declined as out-of-scope-skillset; converted a project risk into a delivered prod outcome on the planned timeline. Cross-functional partnership with AWS engagement manager + GEV client leads. Operating as the Slalom delivery owner for the workstream.

**Feedback so far:**
- **Sreedhar Sannidhanam (AWS Sr. Engagement Manager, GEV) — written feedback received 2026-05-28:** *"Madhurima demonstrated strong Customer Obsession by proactively working backwards from the customer's requirements to understand the end-to-end data ingestion process, ensuring the pipeline design was aligned with what the customer truly needed rather than making assumptions. She took ownership of coordinating across multiple teams—navigating dependencies and removing blockers—to keep the implementation on track, which reflects her commitment to delivering outcomes that matter to the customer. Her persistence in figuring out the customer-side processes, often in ambiguous situations, ensured that the data delivered for UAT was accurate, complete, and fit for purpose. During UAT, data inconsistencies were identified, and Madhurima recognized that streamlining the ingestion pipeline is crucial for resolving most of these UAT issues and ultimately securing UAT signoff—demonstrating her focus on root-cause resolution rather than surface-level fixes. By driving this complex, cross-team effort toward production readiness while keeping the customer's success at the center, she exemplified both Customer Obsession and Deliver Results with a high quality bar."*
- **Tao (Taojian Feng, AWS ProServe Tech Lead) — written feedback received 2026-05-20** (full quote in [`feedback-asks.md`](feedback-asks.md)): called out leading role on the AdHoc Q&A agent (dynamic tool selection, multi-step LLM iteration), proactive pickup of the FSR pipeline design + implementation, highly impactful design discussions, proactive technical-advice seeking, willingness to take on challenging work, push through blockers, excellent communication, and helping the team gain support from cross-functional teams and leadership.
- Pranesh ask still pending.

**Stakeholders:**
- Sreedhar Sannidhanam — AWS engagement manager
- Pranesh, Abhijeet — GEV client-side tech leads (DS + architecture)
- Tao — GEV/AWS architect on OSA (FSR reuse across OSA steps)

---

### 2. Salesforce GIC / ICM (2025–present, ongoing) — PRIMARY DELIVERY STORY
**Role:** Workstream Lead / Solutions Architect / Data Strategist (operating as engagement lead in practice)
**Client:** Large global CRM platform — Global Incentive Compensation team
**Scope:** Multi-quarter, started as 2-person discovery, expanded to broader engagement
**What I led:**
- Discovery phase: interviewed 15+ stakeholders across engineering, analytics, SOX/compliance
- Surfaced that ~33% of upstream data feeding analytics wasn't SOX-compliant
- Designed two future-state architecture options (S3 + Snowflake vs S3 Lakehouse), presented to C-level + enterprise architects
- Authored North Star Architecture aligned with their enterprise platform direction
- Defined end-to-end data flows, ownership, governance models for stable SOX reporting
- Redesigned Snowflake RBAC + clarified data stewardship (RACI)
- Led BRD development (taken on beyond original scope)
- Onboarded new Slalom team members during backfill / team expansion

**Measurable impact:**
- ~80% reduction in manual effort / time-to-insight on initial datasets
- Client extended engagement (scope expansion) and explicitly requested her back
- Team Mogul Award (NorCal H2 nomination by SD Singh)

**Quotes:**
- Tim Lin (client): *"I've never seen such data in all his years at Salesforce"* [MID25]
- Hong Wu (client, peer of manager's-manager): *"Will Madhurima have insight into it? Will she provide input into what that plan looks like?"* [FB-SDSingh-2025-06-12]
- SD Singh: *"You have demonstrated leadership without authority… even if this was a standalone engagement, I think you would have done a reasonably good job of being the engagement lead."* [FB-SDSingh-2025-06-12]
- SD Singh: *"Hong Wu is bringing you into data governance discussions because he believes you have things to add to those conversations."*
- Matt Ngai: *"Madhurima's analytical and assessment skills played a critical part in driving requirements and future state visioning... Mentioned by client by name as someone to support ongoing work due to expertise and experience with project, demonstrating client trust in her abilities."* [FB-MattNgai-2025-11-11]
- Maya Sandler: *"Her ability to build a strong, trusting relationship with the client was particularly evident when it directly led to the project's extension for the next phase."* [FB-MayaSandler-2025-06-20]
- Manager (EOY): *"her impact to multiply beyond the remit typical of a Senior Consultant"* [EOY25]

---

### 3. Apple / FruitCo AI/ML Annotation Ops (2023–2024) — DEEP TECH + MENTORING STORY
**Role:** Solutions Architect (sole architect)
**Client:** Top consumer electronics company, AI/ML org supporting iPhone intelligent features, 6,000 global annotators downstream
**Scope:** ~12 months, end-to-end lakehouse build
**What I led:**
- Designed lakehouse architecture: AWS Glue + PySpark + Iceberg + Airflow + Trino + Tableau, medallion (raw→refined→curated)
- MVP-first approach with 2–3 priority datasets
- Great Expectations for data quality
- Self-service analytics pipeline for business users
- Mentored Erika Morris on data engineering best practices, pair-programming

**Measurable impact:**
- 90% improvement in data accuracy
- Customer adopted architecture for **all** datasets → engagement expansion
- **Customer Impact Award from Debra Ameerally (Apple)**

**Quotes:**
- Debra Ameerally (Apple): *"Madhurima Saxena stands out for her quiet and diligent work in getting her work done to advance the data engineering work for the project."* [FB-Brad-2024-04-10]
- Sean Ipakchi: *"the Greenfield GitHub + AWS + AirFlow + Trino + Tableau data architecture she's developed is a testament to the delivery excellence & capabilities she's infused into NorCal Slalom"* … *"D&A Unicorn you're already on your way to be"* [FB-Sean-2023-12-19]
- Raghavendiran Nagarajan: *"Madhurima's foundational work on the AML project, particularly the DAG design and architecture is very much appreciated. Her contributions have made it easier for new team members to onboard… Madhurima led discussions, got agreements, and implemented solutions all when guiding junior engineers in the team."* [FB-Raghav-2024-11-14]
- Erika Morris: *"Madhurima has devoted time and effort to up skill me in data engineering by being extremely available for trouble-shooting, answering questions, and pair-programming"* [FB-Erika-2024-07-01]
- Maya Sandler: *"is a true leader in the AWS community in Slalom, inspiring and mentoring others"* [FB-MayaSandler-2024-10-16]

---

### 4. Pre-Sales & Internal Slalom Brand (cross-year) — GROW SLALOM STORY
**RFPs / Pursuits:**
- **Informatica–Salesforce Merger RFP** — system mappings, data-flow consolidation, risk-aware migration roadmap [EOY25]
- **BayRen RFP** — *"$2–3M in new D&A pipeline through RFPs and account extensions"* [IW]
- **Genentech gRED Sales** — architectural guidance contribution [EOY25]
- **California Community Colleges** — data strategy workshop proposal [EOY25]
- **Proofpoint** — data ingestion architecture review (Raphael Vannson asked for help on short notice) [FB-Raphael-2025-06-05]
- **iRhythm** — 4-week sales POC, designed architecture + demoed cataloging/PII/DQ rules, accelerated time-to-insight ~80%, won follow-on [IW]
- **MTC RFP** (2023) — Aprajita: *"Your hard work and dedication to complete the technical section speaks volume to your depth of knowledge"* [FB-Aprajita-2023-04-27]
- **AWS MAP funding** secured to reduce POC cost barriers [IW]

**Slalom Internal — 2026:**
- **Data Arch-Hive series** (May 2026) — co-presented with Raghav, walkthrough of client Lakehouse (Airflow, PySpark, Iceberg, AWS Glue/Athena/SQS/SNS, Trino, Tableau, DataHub, CI/CD + AI layer)
  - Karthik Mannava: *"the back-and-forth with the audience turned it into a genuine learning conversation rather than a one-way presentation. Everyone who attended walked away having learned something new."* [FB-Karthik-2026-05-08]
- **Databricks COE — Insurance 360 in-house solution** (Dec 2025–early 2026)
  - Pragathi Sharma: *"helped create the necessary views, supported dashboard development showcased to the Databricks team and at the London Databricks meetup"* … *"ability to ramp up fast, deliver with quality, and stay committed to the outcome made a significant difference"* [FB-Pragathi-2026-01-26]
- **Databricks weekly L&L sessions** — ongoing contributor, helping colleagues prep for certs
  - Emanuel Ward: *"contributes to the Databricks Learning sessions on a weekly basis… key to supporting and growing our partnership with Databricks"* [FB-Emanuel-2025-11-12]
- **Databricks Data Engineer Associate cert** earned 2025
- **GenAI Cohort** capstone (Aug 2024) — solution architect role on DMV prep GenAI tool
  - Elaine Brekelmans: *"a thought leader in how we could build out our solution"* [FB-Elaine-2024-08-27]

---

## Cross-Cutting Manager Statements (use anywhere)

From **2025 EOY appraisal — Manager Evaluation column** [EOY25-MgrEval]. Overall rating: **Above Expectations**.

- *"her impact to multiply beyond the remit typical of a Senior Consultant"* — Manager Evaluation, Core Competencies → Grow Slalom narrative
- *"beyond the scope of what we expect of our Senior Consultants"* — Manager Evaluation, Core Competencies → Deliver Exceptionally narrative (re: pre-sales contributions to Genentech, Salesforce–Informatica, California Community Colleges)
- *"award-winning client delivery, and demonstrated ability to flex between data engineering, architectural, and stakeholder management responsibilities"* — Manager Evaluation, overall-rating rationale
- *"positioned her as a reliable strategic partner, and allowed her impact to multiply beyond the remit typical of a Senior Consultant"* — Manager Evaluation, Grow Slalom narrative
- *"consistently demonstrated leader-like qualities within her delivery teams, and the adaptability to support both engineering and architectural outcomes, beyond those of a more specialized data engineer"* — Manager Evaluation, Lead narrative

---

## Honest Growth Areas (for "Goals + Support Needs" + Promotion Plan)

These show up consistently across feedback — own them, don't hide them:

1. **Tailoring communication to executive audiences** — "connect the dots" for execs; succinct, visually engaging stories
   - Matt Ngai, Manager (EOY), Maxine Leu, SD Singh all mention this
2. **Proactive risk flagging to broader team** (not just 1:1s)
   - Pete Obringer, Erika Morris (FruitCo retrospective)
3. **Diplomatically challenging clients** — calling out misalignment / unrealistic expectations earlier
   - Maxine, Pete Obringer
4. **Big-impact thinking over low-hanging fruit**
   - Raghav 2024
5. **Project-management / solution-owner side of delivery** — surfacing blockers, driving clarity
   - Maxine
6. **Sales/revenue ownership** — *"begins leading and/or solutioning for pursuits"* is the Principal bar. Has contributed to many pursuits; needs to **lead** one end-to-end.

---

## Quantitative Snapshot (for the Quant section of Reflection)

| Metric | Principal Bar | Current State | Position |
|---|---|---|---|
| Utilization (Self) | 80%+ | **86.3% (2025), 93% H1** | **Exceeds** |
| Revenue ($1M sold or managed) | $1M | Managed revenue from Salesforce GIC engagement extension + multi-quarter delivery lead role; pre-sales contributions ($2–3M influenced pipeline per IW); no formally sold revenue credit | **Partial — frame as managed-revenue + named pre-sales pipeline; gap = lead a sold pursuit end-to-end** |
| 1+ Functional/Technical Roles: Advanced+ | Yes | Data Architect — Advanced+ (peer + manager validated); AWS expert recognized | **Meets** |
| Engagement Lead or Delivery Solution Lead: Foundational+ | Foundational+ | Operating as workstream lead on Salesforce GIC ("would have done a reasonably good job of being the engagement lead" — SD Singh) | **Meets (informal title; case for elevating)** |
| Pursuit Lead or Sales Solution Lead: Foundational+ | Foundational+ | Contributor on Informatica RFP, BayRen, iRhythm POC, Proofpoint, MTC RFP, Cal Comm Colleges, Genentech — not formal Pursuit Lead | **Approaching — gap = lead a pursuit end-to-end as Pursuit Lead** |
| People Leader: Proficient+ (Optional) | Optional | No formal directs. Informal mentoring: Erika Morris (AWS), Slalom colleagues for Databricks/AWS certs, junior engineers on Apple project, Maya Sandler (AWS) | **Optional — note informal mentoring; not a blocker** |

---

## Open Items Before Drafting

1. **Need from user:** GE Vernova / AWS 2026 details (Story #3 above) — role, stack, stakeholders, impact, quotes if any
2. **Need from user:** Actual revenue numbers for Salesforce GIC managed revenue (if known) and any other "managed" engagement values — to make the $1M case concrete
3. **Drop:** Google REWS (per user)
4. **Keep handy when drafting:** the "Honest Growth Areas" list — these become the Promotion Plan rows and the "Goals + Support Needs" column of the Reflection
