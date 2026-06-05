# Promo Inputs — User Fill-In

**Fill in plain language, bullets, half-sentences — all fine. I'll polish into the templates. Save when done; just tell me "inputs filled" in chat and I'll pick up.**

---

## 1. GE Vernova / AWS (current 2026 project)

**Role:** AI Engineer / Solutions Architect (working title)
*Targeting **Sr. Solutions Architect — Data & AI** for the promo case. On the GE engagement my charter is broader than the "AI Engineer" badge — I partner with architects on solution + design across the AdHoc QnA Agent (Unit Risk Agent track), the Unit Risk Agent itself, and the FSR data pipeline.*

### 1a. Scope — what is the project?

**GE Vernova — Service Demand Generation (SDG) program.** GE Vernova plans outages on gas turbines and generators 12–18 months in advance. The signals that decide *what work to do and when* live in decades of unstructured Field Service Reports (FSRs), proprietary engineering procedure documents, Engineering Review (ER) cases, and SME judgment. Missing an early warning sign can mean catastrophic failure → 2+ years of unplanned downtime. Catching it early means a planned rewind or repair → 6–7 months. The SDG program is GE's bet on using GenAI to surface those signals consistently across SMEs, customers, and contracts.

**My delivery scope sits in three pieces of the program:**

1. **FSR data pipeline** *(production, mine end-to-end on the Slalom side)* — a Databricks workflow that ingests ~17.8K FSR PDFs from Unity Catalog Volumes, runs P1 metadata extraction (pdfplumber → LLM normalization → IBAT / Event Vision / PSOT enrichment), runs P2 chunking + 3072-dim embeddings, and syncs to a Vector Search index for RAG. Built backfill + incremental on the same code path, claim-based locking for parallel P2 workers, retry caps, run-log telemetry, and a 41-check DQ validation job. In prod, serving downstream agents.

2. **AdHoc QnA Agent** *(part of the Unit Risk Agent suite — solutioning + design partner)* — a RAG agent that lets GE engineers ask free-form questions across the FSR corpus + procedure docs + ER cases, grounded in the pipeline above. The "ad-hoc" path serves non-contract customers who call in when something goes wrong; the agent helps GE engage faster with full historical context.

3. **Unit Risk Agent** *(solutioning + design partner)* — the broader agent that compares FSR test results (e.g., DC leakage per phase) against proprietary procedure-document rules (acceptable / warning / critical ranges) and produces a structured risk recommendation with evidence — factoring in contract responsibility (GE vs customer) for the action call.

**Business problem in one line:** turn 40 years of unstructured outage data + SME knowledge into early, consistent, contract-aware risk recommendations so outages are planned instead of reactive.

### 1b. Client team / stakeholders
*Who do you work with on GEV side? Any names worth dropping (peer, manager-of-manager, exec)? Slalom team — solo or with others?*

> *Note: prompt asked GEV-only, but expanded to cover all anchor engagements since 1b is the stakeholder map for the whole promo case.*
>
> **GE Vernova / AWS (2026, current)**
> - **Sreedhar Sannidhanam** — AWS engagement manager. Praised proactive coverage when I picked up the FSR prod-readiness work on short notice and drove it into production. [verbal, recent]
> - **Pranesh / Abhijeet** — GEV client-side technical leads (DS + architecture). Day-to-day design partners on FSR pipeline, ESN resolution, and doc-summary direction. Pranesh routes priorities and pulls me into multi-ESN + OSA scoping calls.
> - **Tao** — GEV/AWS architect on OSA. Surfaced that FSR will be reused at multiple OSA steps; shared OSA design doc for my review/feedback.
> - Slalom team — operating as the Slalom delivery owner for the FSR data pipeline workstream end-to-end (backfill, incremental, validation, prod ops). Partnering with DS and Databricks team on adjacent workstreams.
>
> **Salesforce GIC / ICM (2025, primary delivery story)**
> - **Hongwu Wang** — client Director, peer of manager's-manager. Pulled me into data governance discussions; explicitly asked whether I'd be shaping the plan. [FB-SDSingh-2025-06-12]
> - **Timothy "Tim" Lin** — client Manager. *"I've never seen such data in all my years at Salesforce."* [MID25 / FB-SDSingh-2025-11-12]
> - **SD Singh** — Slalom Account Manager. EOY/mid-year endorsement: *"demonstrated leadership without authority… would have done a reasonably good job of being the engagement lead."* Nominated me for the NorCal H2 Team Mogul Award.
> - **Maya Sandler** — Slalom mentor/peer-level review. Cited the trust I built with the client as the reason the engagement extended into the next phase. [FB-MayaSandler-2025-06-20]
> - **Matt Ngai** — Slalom Manager. Called out analytical/assessment skills driving requirements and future-state visioning. [FB-MattNgai-2025-11-11]
> - Worked across Salesforce enterprise architects on the future-state architecture options + North Star alignment.
>
> **Apple / FruitCo (2023–2024, deep-tech anchor)**
> - **Debra Ameerally** — senior Apple exec, AI/ML org. Awarded me the Customer Impact Award; written feedback called out diligence in advancing the data engineering work. [FB-Brad-2024-04-10]
> - Sole Slalom architect on the engagement; mentored Erika Morris on data engineering practices and pair-programming.
>
> **Slalom Databricks COE (2025–2026, internal investment)**
> - **Pragathi Sharma** — Databricks COE lead. Shoutout for Insurance 360 in-house solution work; called out ramp-up speed and dashboards showcased at the Databricks team review and the London Databricks meetup. [FB-Pragathi-2026-01-26]
> - **Emanuel Ward** — Databricks partnership lead. Recognized growth in Databricks (cert + weekly Databricks Learning sessions) as contributing to Slalom's collective Databricks competency. [FB-EmanuelWard-2025-11-12]
> - **Karthik Mannava** — Data Arch-Hive session host. Recognized the Data Arch-Hive session co-delivered with Raghav on the FruitCo Lakehouse architecture (Airflow + PySpark + Iceberg + AWS + Trino + Tableau + DataHub + AI), highlighting the interactive format and learning value for the audience. [FB-Karthik-2026-05-08]
>
> **Cross-engagement / Slalom community + sales**
> - **Maxine Leu** — Slalom Manager. Cross-project recognition across Salesforce GIC (architectural pivot + North Star), Informatica RFP (initiative + quick turnaround in ambiguous setting), and Google WPA. *"Strong data architect who can lean into both data engineering and solutioning."* [FB-MaxineLeu-2025-11-12, FB-MaxineLeu-2025-06-11]
> - **Raphael Vannson** — Slalom SSL. Pulled me in on short notice to review the data-ingestion portion of a Proofpoint AI/DS pre-sales solution and join the client call; helped credentialize Slalom on the data ingestion side in addition to AI. [FB-Raphael-2025-06-05]
> - **Aprajita Shrivastava** — MTC RFP lead. Recognized contribution to the technical section of the MTC RFP response under tight timeline. [FB-Aprajita-2023-04-27]
> - **Elaine Brekelmans** — GenAI Cohort SO. Capstone partner on the DMV GenAI assistant; called out solution-architecture role + thought leadership on the team. [FB-Elaine-2024-08-27]
>
> **Apple / FruitCo (additional recommenders)**
> - **Pete Obringer** — Slalom Solution Owner / account lead on FruitCo. Multiple appraisal cycles; on the Principal track called out client-centric approach + on-site dedication and pushed on coaching/client-education + relationship depth as growth areas. [FB-PeteObringer-2024-11-26, 2024-06-11, 2023-11-06, 2023-04-25]
> - **Julie Thomson** — Slalom SO on FruitCo. Called out growth into primary architect role, communication + confidence growth, and curiosity around viz tools. [FB-JulieThomson-2023-11-15, 2023-04-21]
> - **Brad Jackson** — Slalom (delivered the Apple Customer Impact Award message from Debra Ameerally). [FB-Brad-2024-04-10]
> - **Erika Morris** — Slalom Data Engineer / mentee on FruitCo. Detailed feedback on mentoring, pair-programming, working-with-difficult-clients, and onboarding support. Useful for "Lead & Develop Others." [FB-Erika-2024-11-22, 2024-07-01, 2024-04-10]
> - **Raghavendiran Nagarajan ("Raghav")** — Slalom DE on FruitCo. Called out foundational AIML pipeline DAG/architecture and being a "trustworthy partner"; pushed on big-impact thinking as a growth area. [FB-Raghav-2024-11-14]
> - **Sean Ipakchi** — Slalom peer on FruitCo. *"Resident NorCal AWS Data Architecture expert"*; turned a Red engagement Green; long-arc D&A unicorn comment. [FB-SeanIpakchi-2023-12-19]
>
> **iRhythm (earlier)**
> - **Nabor Reyna** — *"Empowered team members to ask questions and grow expertise… called out risks and opportunities."* End-to-end AWS + dbt + Tableau + Snowflake delivery. [FB-Nabor-2023-11-28]
> - **Sean Dunning** — Slalom DE peer. AWS + PySpark mentoring; "always willing to lend a helping hand." [FB-SeanDunning-2023-11-22, 2023-07-14]



### 1c. Tech stack — one-liner
*e.g. "AWS Bedrock + Databricks + LangChain agents + RAG over Field Service Reports + Airflow orchestration"*

> **Headline (Sr. Solutions Architect — Data & AI):** Spark / Lakehouse on AWS + Databricks, with GenAI agents (Strands ReAct loop, MCP tools) over RAG-indexed Field Service Reports — end-to-end from PDF ingestion to grounded conversational Q&A.
>
> **GE Vernova SDG (current, 2026)**
> - **Data platform:** Databricks (Unity Catalog Volumes, Delta, Vector Search) on AWS, orchestrated as Databricks workflows.
> - **FSR pipeline (mine, end-to-end):** pdfplumber → LLM normalization (LiteLLM gateway) → IBAT / Event Vision / PSOT enrichment → claim-based parallel chunking → 3072-dim embeddings → Vector Search index sync. Python, PySpark, Delta MERGE, 41-check DQ validation job.
> - **AdHoc Q&A Agent (solutioning + design partner):** Strands agentic framework (ReAct loop), Claude 4.6 Sonnet via FastAPI / Streamable HTTP, S3SessionManager for chat memory, MCP-exposed data services (IBAT, PRISM, FSR retriever, ER cases, risk matrix, assessment findings, RE narrative, event history), persona-based tool access (Reliability vs Outage Engineer), ECS Fargate, CloudWatch.
> - **Unit Risk Agent (solutioning + design partner):** rules-from-procedure-docs + FSR test-result reasoning, contract-aware recommendation, evidence-grounded outputs.
>
> **Cross-engagement core stack (career arc):**
> - **Cloud / data engineering:** Spark, PySpark, Apache Iceberg, Delta, Airflow, AWS (S3, Glue, Kinesis, EMR, Redshift, Athena, ECS Fargate, CloudWatch, SQS/SNS), Databricks (Unity Catalog, Lakehouse), Snowflake, Trino, Kafka, Tableau / ThoughtSpot, Terraform, Jenkins, CI/CD.
> - **AI / GenAI:** RAG over enterprise PDFs, Databricks Vector Search, embeddings + chunking strategies, LLM gateways (LiteLLM, Bedrock), agentic frameworks (Strands ReAct), MCP tool integration, prompt + persona design.
> - **Governance / observability:** Unity Catalog, Lake Formation, Alation, Collibra, RBAC redesign, Great Expectations, run-log + DQ audit tables, DataHub.
> - **Consulting:** solution engineering, RFP / SOW, executive presentations, North Star architecture, current-state assessment, pre-sales workshops + accelerators (AWS, Databricks COE, Snowflake).

### 1d. Concrete impact / metrics so far
*Anything goes: docs processed, hours saved, deployed-to-UAT, exec demo, stakeholder buy-in, scope expansion conversations…*

> **GE Vernova / AWS (current, 2026)**
> - **Took over FSR pipeline on short notice when upstream data wasn't ready** — partnered with the AWS engagement manager + GEV client team to unblock the path to prod. Volunteered to own end-to-end after the data-source gap surfaced; turned a scope-shifted ask into a delivered production pipeline.
> - **Production backfill — 17,967 / 18,094 FSR PDFs successfully processed (99.3%)** in the planned 2–2.5 day window (Apr 30 – May 2, 2026). 1.09M chunks + 3072-dim embeddings written to the Vector Search index. Failure rate 0.43% (77 docs, all traced to corrupt source PDFs, audited in tracker).
> - **Incremental + backfill on the same code path** — one workflow handles both daily operations and bulk loads; backfill design choices (Spark `LIST`, stub-row durability, drain-loop P2) carry over for free to the steady-state daily run.
> - **Hardened the run-loop after dev backfill** — added claim-based locking for parallel P2 workers, retry caps + lifetime retry gate, run-log telemetry on P1 (previously absent), DQ log de-dup + failure-category enum, and a 41-check standalone DQ validation job for SRE handoff.
> - **Active design partner on two downstream agents (AdHoc Q&A + Unit Risk)** — the FSR pipeline is the grounding layer; pulled into design conversations on multi-ESN resolution, doc-summary direction, and now OSA reuse where FSR will plug into multiple steps.
>
> **Salesforce GIC / ICM (2025, primary delivery story)**
> - **Workstream Lead on a multi-quarter ICM Analytics modernization.** Surfaced that ~33% of upstream data feeding analytics wasn't SOX-compliant; ran the discovery (15+ stakeholder interviews) that established the future-state baseline.
> - **Two future-state architecture options (S3 + Snowflake vs S3 Lakehouse) presented to C-level + enterprise architects.** Authored the North Star Architecture aligned with the client's enterprise-platform direction; socialized with immediate and extended teams to drive alignment.
> - **~80% reduction in manual effort / time-to-insight** on initial datasets after the redesign.
> - **Engagement extended for the next phase, client explicitly asked to keep me on** — cited in written feedback as directly tied to the trust built with the client lead.
> - **Pulled into senior-stakeholder conversations** — client Director (peer of manager's-manager) brought me into data-governance discussions and explicitly asked whether I'd be shaping the plan.
> - **NorCal H2 Team Mogul Award nomination** for the Salesforce ICM workstream.
>
> **Apple / FruitCo (2023–2024, deep-tech anchor)**
> - **90% improvement in data accuracy** after lakehouse redesign (AWS Glue + PySpark + Iceberg + Airflow + Trino + Tableau, medallion architecture).
> - **Scope expansion: client adopted the architecture for ALL datasets**, not just the initial 2–3 priority ones — meaningful account growth out of an MVP-first delivery.
> - **Customer Impact Award from the senior Apple AI/ML exec** (Debra Ameerally), via the 2023 customer survey — direct, named client recognition.
> - **Engagement extended through end of FY + into the next fiscal year** based on delivery + trust built.
> - **Mentored a junior engineer end-to-end** on data engineering practices, working-with-difficult-clients, and pair-programming through the project lifecycle.
>
> **Cross-engagement / pre-sales + community (2023–2026)**
> - **$3M+ new AWS / Snowflake opportunities influenced** via pre-sales architecture reviews, RFP responses, customer workshops (per resume / IW.pdf — confirm wins to call out by name).
> - **GenAI Cohort capstone** — solution architect on the DMV-prep GenAI assistant; co-built the team's backlog and shipped a working capstone product.
> - **Data Arch-Hive session (May 2026)** — co-delivered the FruitCo end-to-end Lakehouse + AI walkthrough internally; recognized for the interactive format and learning value to attendees.
> - **Databricks COE — Insurance 360** — supported in-house solution build, dashboards showcased to the Databricks team and at the London Databricks meetup.
> - **Weekly Databricks Learning sessions** + Databricks Certified Data Engineer Associate (2025) — recognized as contributing to Slalom's collective Databricks competency.


### 1e. Notable feedback / quotes / recognition (if any)
*Internal Slalom feedback, client off-hand comments, any moments where someone said "this is great"*

> *1b mapped the stakeholders; 1e is the actual quotes and named recognition I'd want surfaced in the Reflection. Curated, not exhaustive.*
>
> **Direct client recognition (named)**
> - **Debra Ameerally (Apple, senior exec, AI/ML org)** — *"Madhurima Saxena stands out for her quiet and diligent work in getting her work done to advance the data engineering work for the project."* → **2023 Apple Customer Impact Award.** [FB-Brad-2024-04-10]
> - **Timothy "Tim" Lin (Salesforce, client Manager)** — *"I've never seen such data in all my years at Salesforce."* [MID25 / FB-SDSingh-2025-11-12]
> - **Hongwu Wang (Salesforce, client Director — peer of manager's-manager)** — *"Will Madhurima have insight into it? Will she provide input into what that plan looks like?"* (asked unprompted in a leadership planning conversation, signaling she's seen as a critical team member). [FB-SDSingh-2025-06-12]
>
> **Manager / Account Manager assessments**
> - **SD Singh (Slalom Account Manager, Salesforce GIC)** —
>   - *"You have demonstrated leadership without authority… even if this was a standalone engagement, I think you would have done a reasonably good job of being the engagement lead."*
>   - *"Hong Wu is bringing you into data governance discussions because he believes you have things to add to those conversations."*
>   - *"You're not just focusing on the very myopic version of Tim Lin not being able to execute his queries… you're thinking about the whole architecture."*
>   - *"That is how Slalom is perceived — we come in, make a significant impact, and leave the client better than where they started. You are doing that."* [FB-SDSingh-2025-06-12]
> - **Maxine Leu (Slalom Manager)** — *"You're a strong data architect who can lean into both data engineering and solutioning. You bring strong technical acumen, good slide work, collaboration, ownership of outcomes, and a consistently high level of productivity across everything you take on."* [FB-MaxineLeu-2025-11-12]
> - **Maxine Leu (re-staffing leadership on Salesforce GIC)** — *"Acted with high urgency to screen several Slalom candidates for a backfill / team expansion staffing need and is taking the lead to onboard the new Slalom team members… demonstrates her ownership in the success of the engagement and the client."* [FB-MaxineLeu-2025-06-11]
> - **Matt Ngai (Slalom Manager, Salesforce GIC)** — *"Madhurima's analytical and assessment skills played a critical part in driving requirements and future state visioning — a workstream that our client was struggling with — and unblocking downstream steps. Mentioned by client by name as someone to support ongoing work due to expertise and experience with project, demonstrating client trust in her abilities."* [FB-MattNgai-2025-11-11]
> - **Maya Sandler (Slalom DE, Salesforce GIC peer review)** — *"Her ability to build a strong, trusting relationship with the client was particularly evident when it directly led to the project's extension for the next phase."* [FB-MayaSandler-2025-06-20]
>
> **Pre-sales / sales-driven recognition**
> - **Raphael Vannson (Slalom SSL, Proofpoint pre-sales)** — *"Madhurima quickly pivoted and helped reviewing the data ingestion approach… Slalom was able to make a confident and relevant presentation to the client and credentialize us on the data ingestion portion in addition to the AI portion of the solution."* [FB-Raphael-2025-06-05]
> - **Aprajita Shrivastava (MTC RFP lead)** — *"Hard work and dedication to complete the technical section speaks volume to your depth of knowledge."* [FB-Aprajita-2023-04-27]
>
> **Build community / thought leadership**
> - **Karthik Mannava (Data Arch-Hive session host)** — *"What really set the session apart was how interactive you kept it; the back-and-forth with the audience turned it into a genuine learning conversation rather than a one-way presentation. Everyone who attended walked away having learned something new."* [FB-Karthik-2026-05-08]
> - **Emanuel Ward (Slalom Databricks partnership lead)** — *"Madhurima… contributes to the Databricks Learning sessions on a weekly basis. These activities have not only made her and other Slalomers more knowledgeable and effective as Data Engineers, but also play a critical role in shoring up Slalom's collective Databricks competency, which is key to supporting and growing our partnership with Databricks."* [FB-EmanuelWard-2025-11-12]
> - **Pragathi Sharma (Databricks COE lead)** — *"Her ability to ramp up fast, deliver with quality, and stay committed to the outcome made a significant difference."* (Insurance 360 dashboards showcased to the Databricks team and the London Databricks meetup.) [FB-Pragathi-2026-01-26]
>
> **Lead & Develop Others (mentorship — direct quotes from mentees)**
> - **Erika Morris (Slalom DE, FruitCo mentee)** — *"Madhurima has devoted time and effort to upskill me in data engineering by being extremely available for trouble-shooting, answering questions, and pair-programming whenever I encounter issues. She has been patient and understanding at all times, reserving judgement and making me feel very comfortable asking any questions I may have."* + *"This demonstrated Madhurima's potential as a future people leader."* [FB-Erika-2024-07-01, FB-Erika-2024-11-22]
> - **Maya Sandler (community)** — *"Is a true leader in the AWS community in Slalom, inspiring and mentoring others."* [FB-MayaSandler-2024-10-16]
>
> **Deep-tech peer recognition**
> - **Sean Ipakchi (Slalom peer, FruitCo)** — *"Resident NorCal AWS Data Architecture expert… her expertise, thoughtfulness, and clear communication with the client & our Slalom team led us to turn a Red rated engagement into a Green one."* [FB-SeanIpakchi-2023-12-19]
>
> **Awards / formal recognition**
> - **2023 Apple Customer Impact Award** (Debra Ameerally, via the customer survey).
> - **NorCal H2 Team Mogul Award nomination** (SD Singh, Salesforce ICM Modernization Team, Sep 2025).
> - **Databricks Certified Data Engineer Associate (2025).**
> - **AWS Certified Data Analytics – Specialty (2021).**
>
> *Other recommenders held in 1b (Pete Obringer, Julie Thomson, Brad Jackson, Raghav, Bryce Larsen, Nabor Reyna, Sean Dunning, Elaine Brekelmans) for stakeholder context but not pulled into 1e to keep the quote list tight.*

---

## 2. Revenue numbers (for the $1M Principal bar)

### 2a. Salesforce GIC managed revenue
*Multi-quarter engagement where you're operating as workstream lead. Even rough range is fine. If unknown, say "ask manager" — I'll leave a placeholder.*

> **TODO — ask SD Singh (Account Manager).** Multi-quarter ICM Analytics modernization (2025), workstream lead, engagement extended into next phase based on client request. Rate × duration unknown from any internal doc.

### 2b. GE Vernova managed revenue
*If known. Pick any: "$XK / quarter", "$XM annual", "don't know"*

> **TODO — ask Sreedhar Sannidhanam (AWS engagement manager).** Current 2026 engagement; took over FSR pipeline workstream end-to-end. No $ figure in any workspace doc.

### 2c. Apple / FruitCo (2023-2024)
*You were sole architect ~12 months. Order-of-magnitude?*

> **TODO — ask Pete Obringer (Solution Owner / FruitCo account lead).** Sole Slalom architect ~12 months (2023 → into FY24); engagement extended through end of FY + into the next fiscal year.

### 2d. Other Slalom engagements where you led delivery (managed revenue)
*ICE Mortgage was pre-Slalom — doesn't count. Any others between 2022 and now?*

> **Candidates from 2025 EOY appraisal — confirm which count:**
> - **Google WPA (REWS team)** — designed end-to-end data architecture, resolved PII/privacy, delivered requirements + solution design that aligned WEPS UX stakeholders. *Led architecture; was it "led delivery"?*
> - **iRhythm (2023)** — end-to-end AWS + dbt + Tableau + Snowflake delivery; Nabor Reyna feedback called out leadership + working sessions. *Was this delivery lead role, or peer DE?*
> - **TODO — confirm with manager(s)** which of these to claim as managed revenue and rough $.

### 2e. Pre-sales pipeline you influenced (won or unwon)
*IW.pdf mentions "$2-3M D&A pipeline through RFPs and account extensions" — confirm or refine. Specific wins: BayRen? Informatica? iRhythm follow-on?*

> **~$2–3M D&A pipeline influenced** across pre-sales and account-extension work (per IW.pdf, anchored on BayREN). Specific pursuits:
> - **BayREN RFP** — technical solution lead; wrote technical sections (AWS S3 / Glue / Redshift / Lake Formation), drafted SOW + RACI + staffing, joined orals. *"Helped Slalom advance to the final selection stage and contributed to about $2–3M in pipeline for the D&A practice."* [IW.pdf]
> - **Salesforce–Informatica Merger RFP** — designed system mappings, data-flow consolidation, risk-aware migration roadmap. [2025 EOY appraisal]
> - **Genentech gRED Sales initiative** — architectural guidance + inputs. [2025 EOY appraisal]
> - **Proofpoint** — data-ingestion approach review on short notice; joined client call; credentialized Slalom on data ingestion in addition to AI. [FB-Raphael-2025-06-05]
> - **California Community Colleges** — data strategy workshop proposal participation. [2025 EOY appraisal]
> - **MTC RFP** — technical section contribution under tight timeline. [FB-Aprajita-2023-04-27]
> - **AWS MAP funding (healthcare client)** — drafted proposal, AWS fully funded the POC at zero cost to client; opened door for larger engagement. [IW.pdf]
> - **TODO — confirm named wins** (BayREN advanced to final selection; any of the above that converted to SOW?).

---

## 3. Quick sanity checks (one-word answers fine)

### 3a. Anything in the Evidence Bank you want me to drop?
*e.g. "drop FruitCo Pete Obringer 2024-11 — too much improvement language"*

> _your answer here_

### 3b. Anyone you'd want quoted that's NOT in my list?
*Any verbal feedback, Slack messages, client emails worth mining?*

> _your answer here_

### 3c. Career narrative — what's your "why principal"?
*Two sentences. What makes you ready, what do you want to do at this level. I'll use this in the Reflection summary.*

> _your answer here_

---

## 4. Self-rating gut check (saves us iteration)

For each competency area at the Principal level, what's your gut rating?
- **4 = Consistently Demonstrates** (your default for strengths)
- **3 = Sometimes Demonstrates** (honest middle — most areas land here)
- **2 = Improvement Needed** (be honest where real)
- **0 = Have not Started** (use sparingly)

| Competency | My gut rating |
|---|---|
| Deliver Exceptionally → Execute Effectively | _3 or 4?_ |
| Deliver Exceptionally → Develop High-Impact Solutions | _3 or 4?_ |
| Deliver Exceptionally → Know & Serve Our Customers | _3 or 4?_ |
| Grow Expertise → Deepen & Broaden Expertise | _3 or 4?_ |
| Grow Expertise → Broaden Slalom Knowledge | _2 or 3?_ |
| Grow Expertise → Build Slalom Capabilities | _3?_ |
| Grow Slalom → Build Community | _3?_ |
| Grow Slalom → Manage Business Operations | _2 or 3?_ |
| Grow Slalom → Drive Sales | _2 or 3?_ |
| Lead → Lead & Develop Self | _3 or 4?_ |
| Lead → Lead & Develop Others | _3?_ |
| Lead → Lead & Develop Teams | _3?_ |
| Lead → Serve As Formal People Leader (optional) | _0 (no directs) — confirm?_ |

*Don't overthink — gut. We'll calibrate together.*

---

**When done, message me "inputs filled" and I'll start drafting Reflection Section 1 (Deliver Exceptionally).**
