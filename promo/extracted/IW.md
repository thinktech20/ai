# IW.pdf


## Page 1

HM - Interview

## Page 2

HM Interview 
Greeting 
Ques to ask in the end 
Introduction (45-60 secs) 
Why Solutions Architect? 
SF - influenced a customer architecture (1-2 mins) 
Apple -  Spark and Data Lake / Lakehouse 
Data Governance Exp 
Presales Experience? 
IRhythm - (buzz words - sales POC, 2 weeks workshop) 
BayRen RFP 
AWS MAP Funding 
Spark Job Optimization 
Customer Disagrees (refined layer) 
Calculated Risk -(Speed / best practices first) 
Frustrated/impatient customer (Resetting expectations) 
Failed Architecture: over-engineered (separate jobs/per DS) 
Over-commitment (all dashboards) 
Above and beyond the duty (PM hat) 
Coaching Customer team.(Influencing team) 
Simplifying for customer - Pipeline self-service 
Machine Learning confidence? 
Comfort with databricks stack? 
Top Strength 
Weakness? 
Future: see yourself in 5 years from now? 
What does day to day look like? 
 
Greeting 
“Hi XYZ, it’s really nice to meet you.  
 
 
Ques to ask in the end 
1.​ “What does success look like in the first 3–6 months for someone stepping into this SA 
role—both technically and from a customer-impact standpoint?”

## Page 3

2.​ “Is there anything in my background that you’d like me to elaborate on, or any concerns I 
can help address?” 
Introduction (45-60 secs) 
 
I’m a Solutions Architect focused on Data & Analytics at Slalom.  I’ve been leading the design 
and delivery of distributed data platforms using Spark, Iceberg, and cloud-native services.  
 
And I work directly with business/leadership stakeholders and engineering teams of clients 
across both pre-sales and delivery tracks. 
 
A big part of my role is guiding customers on architecture, governance, performance, and 
cost trade-offs, and building/running POCs in their environment.  
 
I’m passionate about helping customers solve real business problems by strengthening their 
data engineering capabilities so they can move faster, operate efficiently, and get more value 
from their data. 
 
I’m particularly inclined towards Databricks because of its lakehouse platform, its 
open-source leadership, and the customer-facing SA role aligns closely with my experience. 
 
That's a bit about me, and I am happy to discuss more about my experience. 
 
Why Solutions Architect? 
I’ve always gravitated toward roles where I can connect deep technical architecture with 
real business impact.  
“I’m passionate about helping customers solve real business problems by strengthening 
their data engineering capabilities so they can move faster, operate efficiently, and get 
more value from their data.” 
 
This SA role is exactly at the intersection of what I enjoy and what I’m good at — 
customer-facing architecture, data platform modernization, and translating complex technical 
decisions into business value. 
 
I’ve spent the last several years helping customers design and modernize data platforms — 
guiding them from legacy systems to scalable, governed, analytics- and AI-ready architectures. 
What excites me about this role is the opportunity to do that at Microsoft’s scale, using Azure’s 
ecosystem — Databricks, Fabric, Purview — and to influence not just designs, but adoption and 
long-term success.

## Page 4

Why Databricks? 
 
Leaders and inventors in the industry of many data engineering solutions - lakehouse, unity 
catalog,  
 
I’m drawn to Databricks because it consistently solves the advanced data engineering 
problems I see customers struggling with. The Lakehouse architecture and Unity Catalog 
address these challenges in a way that’s both technically strong and straightforward to operate. 
 
I also value Databricks’ open-format, vendor-neutral approach. Customers want 
flexibility, not lock-in, and Databricks enables that while still giving them a unified platform for 
data, analytics, and AI. 
 
For me, joining Databricks means being in a place where technical depth directly translates to 
customer impact—helping teams move faster, reduce complexity, and get more value from their 
data. 
 
SF - influenced a customer architecture (1-2 mins) 
 
One of the most impactful architectures I influenced was for a large CRM company whose 
analytics team was constrained by fragmented data, inconsistent data quality, and 
recurring compliance issues. Their business teams needed a more scalable and reliable 
way to report on compensation data  
 
I started with a discovery phase where I interviewed around 15 stakeholders across 
engineering, analytics, and compliance. I reviewed their end-to-end data flows and found that 
roughly a third of the upstream data feeding their analytics environment wasn’t SOX compliant. I 
consolidated these and many other findings and presented, data-driven assessment to 
their leadership. 
 
I recommended two future-state options — S3 + Snowflake, and an S3-based lakehouse 
— and collaborated  with their enterprise architecture team to make sure the design fit 
the company’s overall platform direction. I presented the architectural options to the 
leadership team and C-level execs and 3v

## Page 5

This was very well received by the customer and their leadership. 
 
I also helped define a phased implementation plan that delivered quick wins. With the new 
architecture and the automation we introduced across ingestion, validation, and reporting 
workflows, the team reduced manual effort significantly and accelerated time-to-insight by 
nearly 80%. 
 
Apple -  Spark and Data Lake / Lakehouse 
 
I worked with an AI/ML org of a top technology company that builds intelligent features for 
their iPhone, and was supported by 6,000 global annotators. Their operations were fully 
data-driven. Metrics like Productivity, quality, and compliance are continuously tracked 
through dashboards and performance analytics. 
 
Their existing data ingestion process was not scalable, another challenge was that the 
upstream data provider team was not consistently delivering data in the structure or 
cadence the data scientists needed for analysis. 
 
I started by proposing a fast MVP using 2–3 important datasets to show quick value and 
set up a foundation for scale.  I designed a lakehouse architecture using AWS Glue + 
PySpark, Iceberg tables, Airflow orchestration, and a medallion layout (raw → refined → 
curated).  
 
I used Great Expectations for data-quality checks, and I worked closely with data scientists 
to curate datasets at the right granularity for their models. 
I demonstrated how Apache Iceberg enables time travel, incremental refresh, schema 
evolution, while giving us stronger observability, and traceability through its metadata 
and versioning. 
The self-service analytics pipeline we built let the business users explore and onboard 
datasets independently, and it drove a 90% improvement in data accuracy.  
This led the customer to adopt this architecture for all datasets and expand the engagement 
with a larger team. It was the same engagement where the a senior stakeholder awarded me 
the “customer impact ward”

## Page 6

Data Governance Exp 
I’ve worked with several customers on data governance, and one thing I’ve learned is that 
priorities vary. Some teams care most about discovery and cataloging, while others focus 
on strict access controls or lineage. But regardless of the priorities, the foundational 
elements—cataloging, classification, ownership, access control, and quality—need to be 
in place for any architecture to work. 
 
In one customer engagement, I was initially brought in to help with data engineering, but as trust 
grew, they depended on me to shape their overall governance approach and ensure it aligned 
with their architecture roadmap. 
 
 I reviewed their existing access controls and redesigned them using Snowflake RBAC, 
introducing clear role hierarchies, least-privilege principles, and standardized permission 
patterns. 
 
A major gap was the ambiguity around data ownership and stewardship. I facilitated alignment 
across analytics, engineering, and business teams and created a simple RACI that 
clarified who owns datasets, who publishes them, and who approves access. This reduced 
friction significantly and higher trust in the data. 
 
 
 
Presales Experience? 
I’ve done quite a bit of pre-sales work, especially in shaping architecture options, running 
short POCs, and contributing to RFPs. My focus is usually on understanding the customer’s 
pain points quickly, proposing a practical approach, and then de-risking the decision with 
something tangible. 
 
For example, with a new health-tech client, I led a four-week sales POC to help them 
evaluate a new data foundation. I scoped the use cases, designed the architecture, and 
demoed capabilities like automated cataloging, PII detection, and data-quality rules. That early 
value accelerated their time-to-insight by about 80% on the first few datasets and helped our 
team win the follow-on work. 
 
Beyond that, I regularly support RFPs—writing the technical architecture sections, solution 
assumptions, and delivery model—and I’ve also secured AWS MAP funding to reduce POC 
cost barriers for clients.

## Page 7

Overall, my pre-sales experience is hands-on: understanding the problem, shaping the right 
solution, validating it quickly, and helping the sales team move the opportunity forward. 
IRhythm - (buzz words - sales POC, 2 weeks workshop) 
I was engaged early with a new health-tech client — a net-new logo for Slalom — whose data 
services organization needed to deliver faster, more reliable insights from large volumes of 
device-generated data. They were in the middle of a Redshift-to-Snowflake migration, but 
lacked a consistent ETL/ELT framework. Data ingestion was driven by new Go-based 
extractors, and data movement, transformation, and validation were slow, manual, and difficult 
to govern. 
After assessing the environment and aligning with key stakeholders, I proposed a focused 
four-week “test-and-learn” proof of concept to demonstrate what a modernized data 
foundation could look like. The POC prioritized three capabilities: 
●​ Automated data discovery and cataloging 
●​ PII-aware metadata tagging and privacy compliance 
●​ Data-quality monitoring across representative datasets​
 
I designed and demoed the solution using AWS Glue for cataloging and schema tracking and 
Amazon Macie for PII detection, integrated with quality rules and remediation workflows. I 
presented the target architecture to both executive and engineering audiences, addressing their 
questions around privacy, security, cost trade-offs, and platform alternatives. 
At the end of the four weeks, we delivered a functioning end-to-end data flow with a metadata- 
and PII-aware catalog dashboard. This accelerated speed-to-insight by ~80% across the initial 
2–3 datasets and gave the client the confidence to move into the next phase of execution with 
Slalom as their strategic partner. 
BayRen RFP 
​
“One of my key pre-sales engagements was with BayREN, a regional agency that runs six 
different energy-efficiency programs. Each program had its own database and reporting 
process, so leadership had no unified way to see performance across the region. The goal of 
the RFP was to design a data aggregation and reporting platform that could automatically pull 
and standardize data from all six programs into one reporting layer. 
 
The main challenges were fragmented systems, inconsistent schemas, and completely manual 
reporting. They needed a common data model, automated pipelines, and a governed 
environment — but this was still at the proposal stage, so the focus was on shaping a practical, 
scalable approach.

## Page 8

My role was as the technical solution lead for the RFP. I worked with our practice leads, 
architects, and the client’s evaluation team to define requirements and shape the architecture. I 
wrote the technical sections of the proposal, including the end-to-end data platform design on 
AWS using S3, Glue, Redshift, and Lake Formation, along with assumptions, constraints, and a 
clear delivery approach. 
 
I also helped draft the SOW, RACI, and staffing model, and joined the orals presentation to walk 
both business and technical stakeholders through the proposed design. This work helped 
Slalom advance to the final selection stage and contributed to about $2–3M in pipeline for the 
Data & Analytics practice.” 
 
AWS MAP Funding 
“We had a healthcare client who wanted to test a new data architecture but didn’t have the 
budget for a proof of concept. We didn’t want to lose momentum, so I was asked to explore 
funding options. I worked with our AWS alliance team and looked at the MAP program, which 
can fund POCs that drive future cloud adoption. 
 
I drafted a short proposal outlining the use case, the AWS services involved, and how it 
would grow their long-term AWS consumption. The proposal was approved, and AWS fully 
funded the POC. I then led a small cross-practice group to build the demo using AWS analytics 
services in the client’s environment. 
 
The client got a working POC at zero cost, it built a lot of trust, and it opened the door for a 
larger engagement. It also strengthened our partnership with AWS for future opportunities.” 
 
 
Spark Job Optimization 
 
In one of my past projects, prior to Slalom, I had a Spark job on AWS EMR processing loan 
events from Kinesis. The job was running on Spark 2.x and was consistently missing its 
5-minute micro-batch window, which caused batch queues, high scheduling delay, and 
ultimately data loss that affected a large set of customers. Upgrading to Spark 3 was the 
long-term plan, but we needed an immediate fix to stabilize production. 
 
I started by profiling the job in the Spark UI — which wasn’t even enabled due to firewall rules, 
so I worked with the networking team to expose it in production. From there, it was clear the 
main issues were data skew and inefficient joins. One dataset had a heavy skew on a few 
key values, so certain partitions were 10–15x larger. I added targeted filtering before joins, 
applied salting to reduce skew, and optimized the aggregation logic.

## Page 9

On the infrastructure side, I recalculated the executor/cores configuration based on the 
actual workload instead of the default EMR settings, which improved parallelism and 
reduced shuffle overhead. 
 
After these changes, the micro-batches consistently completed within the 5-minute window, 
processing time dropped significantly, and we stopped losing customer events.  
 
This stabilized the workload and improved end-to-end processing efficiency by roughly 80%, 
allowing the system to meet the 5-minute SLA while the Spark 3 upgrade was being planned. 
 
Customer Disagrees (refined layer) 
Themes - understand constraint, co-design pragmatic path, trade-offs 
 
When a customer disagrees with a recommendation, I step back and understand the 
constraint — it could be cost, ownership, or complexity. I keep it data-driven and look for a 
solution that aligns with their priorities. 
 
One of my customer’s Data Science & Analytics team was working off nearly a million upstream 
transactions a day, but the raw data had inconsistencies that impacted feature engineering and 
model accuracy. My architecture recommendation had a refined layer for cleansing, but they 
pushed back due to long-term data-engineering costs. Their concern was valid — and waiting 
months for the upstream team to fix the data wasn’t an option because their modeling 
roadmap would stall. 
 
So, I proposed a lighter-weight approach: 
 
Build a YAML-configurable cleansing layer so they get reliable, analysis-ready data immediately 
with minimal engineering. 
 
Automatically generate structured outputs of all cleansing rules and pass them to the 
upstream data owners so the logic can be absorbed into their pipelines over time.** 
 
This gave the Data Science team clean, consistent data quickly without taking on permanent 
maintenance. Within a quarter, data-quality issues dropped by ~95%, and their team could focus 
on feature development and modeling instead of fixing data. 
 
“I focus on aligning with the customer’s constraints and co-designing the most pragmatic 
path forward, rather than defending a single solution.”

## Page 10

Calculated Risk -(Speed / best practices first) 
Themes - architecture hardening later, value fast, Build trust through small, predictable value 
cycles 
 
Give me an example of a calculated risk that you have taken where speed was critical. 
What was the situation and how did you handle it? 
 
An example of a calculated risk was on a project where I joined right after the design 
phase—and the consultant who owned the pipeline architecture had just left. The customer’s 
Senior Director urgently needed a high-priority dataset to unblock both their BI reporting and 
machine-learning modeling, but the infrastructure provisioning—owned by a separate 
team—was delayed by several weeks. 
 
Speed mattered because their forecasting team was stuck with no data. Instead of waiting for 
full CI/CD, networking, and IAM patterns to be finalized, I proposed delivering a lightweight 
MVP ingestion-to-curation pipeline directly in the AWS console using Glue jobs, S3 
staging, and parameterized transformations. It wasn’t the long-term architecture, but it 
allowed us to deliver the critical dataset in under 5 days—versus the 3–4 week delay the 
customer was expecting. 
 
This was a risk, because the Engineering Manager preferred a strict “best-practices-first” 
approach. I aligned him by clearly laying out the two-track plan: 
Track 1: Deliver the urgent dataset so ML and BI teams could begin exploratory 
modeling, which unblocked two downstream workstreams and ~8 analysts. 
Track 2: In parallel, harden the pipeline into a production-grade framework with CI/CD, 
modular jobs, and cost-optimized orchestration. 
 
The outcome: the customer started generating early features and dashboards immediately, 
leadership saw value within the first sprint, and the Engineering Manager supported the 
roadmap because he saw how the MVP accelerated time-to-insight without compromising the 
long-term architecture. 
Frustrated/impatient customer (Resetting 
expectations) 
Most of us at one time or another have felt frustrated or impatient when dealing with customers. 
Can you tell us about a time when you felt this way and how you dealt with it? When do you 
think it’s appropriate to push back or say no to an unreasonable customer request? 
 
Answer: 
In one meeting with a customer, a senior director said, ‘We’ve been waiting months — can’t 
you just pull the data manually and patch the dashboards?’ I could feel their frustration —

## Page 11

and honestly, I felt it too. But I knew saying yes would create permanent technical debt and 
destroy trust later. 
 
First, I acknowledged the frustration, by telling them 
‘I agree this has been painful. You’re not getting what you need to support a 6,000-person global 
annotation workforce — the impact is real.’ 
 
Then I used data to reset expectations. I showed that: 
 
●​ Upstream changes were breaking schemas weekly. 
●​ Without a governance layer, we couldn’t guarantee any dashboard’s accuracy. 
 
I explained that patching would only give them another failure in 2–3 weeks. 
 
So I proposed a fast, low-risk MVP using Iceberg — showing how time travel, schema 
evolution, and metadata tracking would fix quality issues at their root. 
 
I push back when: 
 
●​ The request introduces risk 
●​ It bypasses governance, 
●​ Or it gives short-term relief but long-term pain. 
 
I do not say no bluntly — I explain the ‘why’ with numbers and offer a better path. Customers 
appreciate that level of honesty. 
 
Failed Architecture: over-engineered (separate 
jobs/per DS) 
Themes: Ownership, simplification, redesign, operational efficiency 
“In one engagement, I designed an ingestion framework on AWS Glue where each data 
source had its own job. That pattern is usually helpful because it gives isolation for 
schema differences, SLAs, and independent deployments. 
But after we got further into the build, it became clear that this customer's workload was fairly 
stable and wasn’t expected to grow or evolve frequently. They had about a dozen sources 
with simple transformations that rarely changed. In that context, the one-job-per-source pattern 
created unnecessary overhead — separate schedules, logs, and monitoring points — without 
giving proportional value.

## Page 12

I recognized that the design, while technically correct, wasn’t the best operational fit for a small, 
steady-state workload. I took ownership of that and walked the customer through the trade-offs: 
more modularity versus more operational touchpoints. We aligned on a better approach — a 
metadata-driven, parameterized Glue job orchestrated through Step Functions. This gave them 
a single operational surface area, consistent retries and monitoring, and still allowed 
source-specific logic through parameters. 
After implementing the revised architecture, maintenance became much simpler, and the 
customer appreciated that we optimized the design for their actual long-term needs rather than 
sticking to a pattern just because it’s “best practice.” 
Over-commitment (all dashboards) 
Themes: Scoping, prioritization, exec communication, delivering with quality 
 
To try to meet the high expectations of our customers, we sometimes promise more than 
we can deliver. Tell me about a time when you overcommitted yourself or your company. 
How did you resolve the issue? 
​
One time I overcommitted was with a customer who needed a full reporting suite 
delivered within the quarter. Based on the components already in place, it initially looked 
achievable, so I committed.  
 
But as we got deeper into the dataset and business logic, the scope expanded—more metrics, 
more drill-downs, and stricter data-quality requirements. It became clear we couldn’t deliver all 
12 dashboards at the expected fidelity without risking quality. 
 
I paused the team and did a rapid assessment of effort vs. value across all use cases. We 
identified the top 6 executive dashboards that directly supported the customer’s quarterly 
leadership review and could be delivered with high confidence. The remaining items—mainly 
deeper operational drill-downs—were important but not time-critical. 
 
I discussed this with the customer, walked them through the trade-offs using data 
(complexity, row-level QA effort, refresh SLAs), and proposed a phased plan that preserved 
quality while still meeting their most critical goals. They appreciated the transparency and the 
fact that the priorities were tied to measurable business outcomes. 
 
In the end, we delivered the core dashboards on time and with 99% data accuracy, and we 
sequenced the remaining work into the next sprint cycle. The customer met their leadership 
commitments, and we maintained trust by turning a risky overcommitment into a clearly 
managed plan.

## Page 13

Above and beyond the duty (PM hat) 
Leadership, structure, escalation management, customer obsession 
 
Tell me about a time when you went above and beyond the call of duty for a customer. 
Why did you take the action you did? What was the outcome? 
Midway through an engagement, the customer’s expectations shifted. What started as a purely 
technical role suddenly required heavy project management, tighter coordination, and much 
more proactive communication across their engineering and analytics teams. I realized that if 
we didn’t adapt quickly, delivery velocity and trust would both suffer. 
 
To stabilize the program, I stepped in immediately. I took over and led daily stand-ups, 
reorganized the backlog, and set up a clear delivery cadence so the customer had full visibility 
into progress and risks. This alone improved issue resolution time by about 30%. 
 
At the same time, I partnered closely with our Slalom account and delivery leadership to 
reassess the skill profile needed. It was clear the team needed someone with stronger PM and 
cross-functional coordination experience, so I moved quickly to initiate a fast-track hiring and 
onboarding process for a consultant whose background matched the new scope. 
 
I stayed deeply involved through the transition to ensure zero disruption—maintaining sprint 
commitments and keeping the customer fully informed. 
 
The outcome: the customer saw on-track delivery for the next two sprints, stakeholder 
satisfaction scores improved, and we strengthened our long-term relationship by showing that 
we could adapt rapidly and put their success first. 
 
 
 
 
 
Coaching Customer team.(Influencing team) 
Give me an example of how you have changed the direction or view of a specific 
function/department and helped them embrace a new way of thinking? Why was a 
change needed? 
A strong example is when I helped a customer’s Data & Analytics team shift from ad-hoc 
development to a more scalable, governed data architecture. Their biggest pain point was 
that each analyst and engineer was creating their own schemas, views, and pipelines. This led 
to fragmented logic, duplicated datasets across 4–5 domains, inconsistent KPIs, and 
growing technical debt that made reporting slow and unreliable.

## Page 14

When I reviewed their workflows with the engineers, I showed how a medallion architecture 
(Bronze → Silver → Gold) would create a single, reusable curated layer and reduce 
duplication. I conducted deep-dive sessions to walk them through schema standardization, 
data-quality rules, and how to handle upstream inconsistencies using pattern-based 
transformations. 
Within a few weeks, the team aligned on a canonical schema, reduced duplicate tables by 
80%, and migrated key dashboards to the standardized curated layer—improving both accuracy 
and refresh performance. 
The customer’s Analytics Director told me that I “filled a critical data gap and raised the 
technical bar for the team,” and it helped them adopt a scalable, predictable, 
engineering-led approach to data. 
 
 
Simplifying for customer - Pipeline self-service  
“We made the pipeline self-service by moving the logic out of ad-hoc code and into simple, 
controlled configuration that other teams could own. 
 
In my last project, the data team was getting constant requests to tweak filters, joins, and 
aggregations. Every change meant a Jira ticket and another code deploy. To fix that, I: 
 
Separated logic from code – we moved business rules into YAML configs instead of 
hard-coding them in Spark jobs. Things like which columns to include, filter conditions, and 
basic aggregations were all config-driven. 
 
Standardized patterns – created a small set of reusable templates for common pipelines, so 
new datasets could plug into the same framework instead of starting from scratch. 
 
Added guardrails – we validated configs, logged changes, and monitored runs so users could 
experiment safely without breaking production. 
 
Documented in one place – a simple catalog page showing each pipeline, its config, owner, 
and last run status. 
 
The result was that analysts and data scientists could adjust how their data was processed 
without waiting on engineering every time, and the core platform team just maintained the 
framework and guardrails instead of hand-building every pipeline.”**

## Page 15

Machine Learning confidence? 
I have not built machine learning models,, but I’m very comfortable with the ML lifecycle 
because most of my work has been on the data and feature-engineering side. I’ve partnered 
closely with Data Science teams to build training datasets, create reusable features, and make 
pipelines reproducible for both training and serving.  
I’m strong at enabling ML teams and designing the data and feature layer that makes their 
models work in production. 
 
Comfort with databricks stack? 
I’m very comfortable with the Databricks stack, both conceptually and hands-on. 
In my recent Databricks certification work, I spent a lot of time building on the platform—working 
with Unity Catalog, understanding its governance model, implementing lakehouse architecture 
patterns, and working through Delta tables, ingestion, and basic LakeFlow concepts. 
 
Beyond the certification, I’ve implemented lakehouse-style architectures for customers 
using Spark, Iceberg, and cloud-native services, so the design principles—open formats, 
separation of storage and compute, versioning, governance—are very familiar. The 
Databricks way of operationalizing that aligns naturally with how I already build platforms. 
 
My deeper expertise today is in AWS data solutions—Glue, Athena, EMR, Redshift, 
Kinesis—but over the past few months I’ve been intentionally leveling up on the broader 
Databricks stack, including security models, lineage, performance tuning, and streaming 
patterns. 
 
Overall, I’m confident in the platform, I understand how to apply the architecture in real 
customer scenarios, and I’m excited to go deeper as a Solutions Architect and guide customers 
on best practices across the Databricks ecosystem.” 
 
 
Top Strength 
My top strength is being deeply customer-focused and building trust with even the most 
demanding stakeholders. I’ve learned that strong architecture only works when people trust 
you enough to adopt it, so a big part of my strength is connecting with customers, understanding 
what matters to them, and showing value consistently. 
One example is a very senior stakeholder at a large technology company—someone who had 
been there for more than 30 years and was known for being extremely tough to satisfy. When I

## Page 16

took over the engagement, there was already frustration on both sides. I made it a point to 
establish predictable communication, set clear expectations, and demonstrate progress 
every week through architecture walkthroughs, data previews, and short value cycles. 
Over time, that consistency changed the relationship completely. The customer began to see 
me as a trusted advisor, and eventually recognized me with their Customer Impact Award for 
advancing data engineering practices across their team. For me, that validated my belief: trust is 
built in small moments, and it’s one of the biggest drivers of successful delivery. 
 
Weakness? 
Balancing Technical Depth with Executive Communication 
 
I come from a strong technical background, so in early stakeholder discussions I used to go too 
deep into technical detail. 
 
I’ve learned to adjust my communication style based on the audience — stay high-level with 
execs and go deep only when needed. 
 
It’s something I keep refining, and now I often help junior architects learn how to simplify their 
message for leadership, which has turned this into a growth area for me. 
 
Future: see yourself in 5 years from now? 
In five years, I see myself as a trusted technical advisor to our customers — who drive 
architecture and strategy for multiple customers and help them adapt to data and AI 
solutions of databricks for their business outcomes. 
I want to go much deeper in the Databricks stack — Lakeflow declarative architecture, data 
governance, and the emerging Data Intelligence capabilities — so that when customers have 
complex problems or ambiguous requirements, I’m the person they reach out to first. 
I’m also excited about contributing to reusable accelerators and best-practice patterns that 
make our customers more successful and help other architects internally. 
Long-term, I’d love to grow into someone who shapes strategy across multiple accounts, 
mentors newer SAs, and plays a meaningful role in how customers adopt data + AI on 
Databricks.

## Page 17

What does day to day look like? 
“My day-to-day isn’t the same every day, but most weeks follow a consistent rhythm. 
 
A big part of my role is spending time with client stakeholders—understanding their pain points, 
clarifying requirements, and helping them think through architecture, governance, and 
data-quality challenges. I usually take those conversations back and translate them into 
concrete designs or small proof-of-concepts, especially around Spark, Iceberg, and lakehouse 
patterns. 
 
I also run working sessions where I present architecture options, walk through trade-offs on cost 
and performance, and help the customer align in a direction. 
 
In parallel, I work closely with our internal Slalom team—either shaping RFP responses, 
preparing client workshops, or reviewing solution approaches for in-flight projects. And 
day-to-day I’m partnering with engineers to unblock implementation details, validate pipelines, 
and make sure what we’re building actually ties back to the business need. 
Gen AI Exp 
 I’ve been working directly with GenAI on AWS through an internal GenAI Bootcamp. As part of 
that, my team built a capstone project (a multi-state DMV exam study assistant) using: 
●​ LLMs via AWS Bedrock​
 
●​ RAG architecture with vector databases / Bedrock Knowledge Bases​
 
●​ Data prep pipelines for GenAI use cases​
 
●​ Python, LangChain, boto3, Jupyter, and Streamlit​
 
The focus was very much on end-to-end, real-world GenAI systems rather than demos — from 
data ingestion to retrieval, prompting, and UI. 
This kind of pod-based delivery model and backlog of GenAI use cases does sound aligned with 
my background. Happy to chat more if you’d like to go deeper on specifics or expectations for 
the role.

## Page 18

DBx Hands on Exp (Accelerator) 
I worked on Slalom’s Insurance 360 accelerator, which is being built on a Databricks 
Lakehouse architecture to unify policy, billing, claims, and engagement data into a governed 
Customer 360. The design uses a medallion pattern, with curated gold-layer customer and 
policy entities intended to be reusable across analytics, AI, and activation use cases. One of the 
core capabilities the accelerator is designed to support is proactive retention — identifying 
early churn signals such as missed payments, declining engagement, coverage changes, 
premium increases, and claims friction, and surfacing them as explainable risk scores in the 
Customer 360. The intent is to enable insurers to trigger timely, targeted outreach through 
agents or digital channels, reducing policy lapse risk while improving customer experience and 
operational focus.  
 
============== 
 
 
HM round Tips: 
 
1.​ They will spend 5 mins in intro​
 
2.​ Behavioural questions - 15 mins 
3.​ Architecture tradeoff 
4.​ Customer presence  
5.​ Machine learning - basics or not - 5 min 
6.​ Why databricks  
 
Tips for intro: 
●​ Show customer readiness 
●​ Executive level communication 
●​ Make it tight 
●​ 45 sec rule - max 1 min 
○​ Who am I - 10 sec 
○​ What do I do currently ? Not history - align with job description 
○​ Work directly with whom?  
○​ Talk about your pre-sales exp 
○​ HM - Why databricks? - 10 sec 
 
Answering questions - 
●​ Behavioural - Do not go more than 2 mins. Best (1-2 mins) 
●​ For every answer you should have impact - for example this improved x metric, reduce y 
metrics. 
●​ Leadership (2-3 mins), architecture (2 mins), machine learning questions

## Page 19

●​ Take time - say that - I may take a couple of seconds to gather my thoughts, is it 
okay? (when gathering thoughts, speak them all… i may speak aloud) 
●​ Do not be very story style type 
●​ When a customer disagrees, you should show empathy, not defend yourself. You should 
say - I started with fully understanding their concerns. Most of the time it is cost. , 
complexity, timeline, governance. 
●​ Mention your business constraint - i compared the cost impact of governance with long 
term flexibility and then some data that you brough…with bench marks, presented them 
the cost model.This became objective, and not opinionated. 
●​ My goal was not to win the agreement but to help the customer win. 
●​  
●​ Format: 
○​ Customer pain point 
○​ My recommendation 
○​ Measurable impact 
●​  
●​ 90 secs - max 2 min rule 
●​ (adding data, keeping time limit) 
 
 
 
Follow up questions: 
 
 
What cloud native services you have used? 
What kind of product 
How you interacted with business people - i did training, pocs, eng people training. 
Behavioural -  
 
 
 
 
Metrics 
 
Deduplication percentage 
20% cost reduced - operation overhead.  
Aligned with the six architecture teams 
Accelerated the decision making by 4 weeks. Spoke with 3-4 business people. 
-​
Have at least 3-4 numbers.

## Page 20

Question - how much confident are you on machine learning thing? 
I have not build machine learning models, but I am very comfortable with ML lifecycle, as I have 
worked with teams at customer side and did feature engineering for them. 
 
Q: your approach to learning new things 
 
a.​ I am mostly self-driven. I learn by myself. I follow certain people and (name few people) 
-​
 
 
Top strength and weakness - at 1:09 hour 
 
Strength - more on business side. Scalable , measurable architecture 
I influence customer through my trade off thinking.  
Maybe learn and grow, always 
 
 
Weakness: 
“A weakness I’ve been actively working on is going too deep into architectural detail too early in 
conversations.​
 Early in my career, I would jump straight into patterns, layers, and trade-offs because I was 
excited about the problem. But I learned that not every audience needs that level of depth. 
Over the last year, I’ve been intentional about stepping back first — understanding who’s in the 
room, starting with outcomes, and only going deeper when it’s relevant. With executives I stay at 
the value and decision layer, and with engineering teams I dive into the technical path.​
 It’s helped me communicate more effectively and keep conversations aligned with business 
goals while still bringing depth when needed.”

## Page 21

Detailed Experience

## Page 22

Final EXPerience / Stories 
Intro (45 sec - 1 min mins) 
Salesforce Exp (GIC Analytics) - Priority 1: 
About the Client / Project 
Challenges & Needs 
My Role: Solutions Architect / Data Strategist 
1. Extending the Engagement through built in trust for being the SME for Data Strategy 
and Architecture 
2. Considered as a trusted advisor for North Star Architecture Alignment 
3. Considered as a trusted Advisor for Data Governance 
4. Coaching the Salesforce GIC Analytics Team and Bridging Capability Gaps 
5. Acting with Urgency to Fill a Skill Gap and Maintain Customer Confidence 
Measure/ Quantify: 
Google Project 
FruitCo Exp (AI/ML Ops) - (Priority 2): 
About the client/project 
AI/ML Ops: 
My Role: Solutions Architect 
6. Turning Around an At-Risk Engagement 
7. Using Iceberg to Fix Data Quality and Build Trust 
8. Account Expansion and Extension at FruitCo 
9. Scaling the Architecture to Upstream Data Engineering / DataOps 
Measure/Quantify 
Apple Exp (Sales Ops): 
About the client/project 
My Role: Solutions Architect 
Measure/Quantify 
Results(Impact): 
RFPs 
BayRen - Priority 4 
About the Client / Project 
10. Contributed directly to $2–3M in new D&A pipeline through RFPS and account 
extensions. 
My RFP Role: Technical solutionist 
11. Partner Collaboration & AWS MAP Funding (Pre-Sales, AWS) 
RFP  - Salesforce Informatica Merger - Priority 4 
Key Challenges 
Irhythm - Workshop & POC (Pre-Sales) - Priority 3 
About iRhythm 
Challenges

## Page 23

My Role: Solutions Architect 
Databricks - Slalom Partnership 
13. Databricks Brickbuilder Program Participation (Databricks - Pre sales) 
14. Databricks - COE - accelerators and certifications 
Open AI - Technology partners -partnership (pre-sales) 
15. Generative AI Pilot (OpenAI Codex): 
CMDS - Multiple Technology Partners - Snowflake, Fivetran, Dataiku, ThoughtSpot, and 
Alation. 
16. Slalom CMDS Partnership with Snowflake and Ecosystem Tools (Multiple clients - 
Pre sales) 
Learning and being curious 
18. Constantly Learning and Staying Ahead (Databricks & RAG Architecture) 
ICE Mortgage 
About the client/project & challenges 
My Role: Data Architect / Data Engineer 
19. Performance Optimization with EMR (ICE Product) 
LPs mapping & Keywords 
Intro (45 sec - 1 min mins) 
I’m a Solutions Architect in the Data & Analytics practice, working with some of our 
Slalom’s strategic NorCal accounts. I have been with Slalom for around 3 years now, and 
based out of the East bay. My focus has been advising, guiding, and building scalable data 
solutions for customers — my work spans across both pre-sales and delivery tracks. 
 
On the pre-sales side, I support  
●​ RFPs by providing technical solutions,  
●​ run workshops with new and existing clients to generate leads and opportunities, and 
●​ collaborate with our technology alliance managers to promote partner platforms, 
grow the customer base, and create new opportunities. 
 
On the delivery side, I’ve recently led several architecture engagements. 
 
At Salesforce, I  
●​ led the architecture for their Global Incentive Compensation analytics team — 
making sure it aligned with their North Star vision and enterprise standards. In the 
process,  
●​ I partnered with several business and technical teams to define how the data from 
different systems will flow into Snowflake in a way that was both consumable for 
analytics and compliant with SOX. 
 
For FruitCo— a large consumer electronics and technology company —

## Page 24

●​ I led the design and architecture of their AI/ML operations lakehouse on AWS and 
Iceberg, supporting large-scale model-training and data-quality workflows. 
 
Before Slalom,  
●​ I led the data platform team at ICE Mortgage Technology in Pleasanton, where I worked 
with production workloads — optimizing EMR jobs, optimizing spark performance, 
and modernizing pipelines. 
 
I am also a trusted AWS architecture advisor in our D&A practice —  
●​ helping with sales pursuits and building our team’s skills in the D&A space. Lately, 
I’ve been part of Databricks learning cohorts and GTM enablement sessions with our 
Databricks partners. 
 
So that’s a bit about me and the kind of data architecture and solutioning work I’ve been leading 
across clients. Happy to share more details as needed. 
 
 I lead the design and delivery of end-to-end data platforms for enterprise clients.  
Salesforce Exp (GIC Analytics) - Priority 1: 
About the Client / Project 
●​ One of my customers is a large global CRM platform provider.​
I work with their Global Incentive Compensation (GIC) team, who are  
○​ responsible for building and maintaining the commission logic—the rules that 
determine how sellers get paid.  
○​ Their main challenge was ensuring that every seller’s compensation statement 
was accurate, despite having very complex and frequently changing incentive 
structures. 
Challenges & Needs 
●​ The compensation data is gathered from multiple systems like Workday, and other native 
apps 
●​ The Analytics team relied on the BT group for data, but since BT had global priorities, 
their timelines often didn’t align with the GIC team’s needs. 
●​ They were facing failed audits from the SOX compliance team and were spending a lot 
of time on manual audit tasks—like pulling reports, tracking access, and validating 
controls. 
●​ Overall, leadership needed reliable, automated, and SOX-compliant reporting to gain 
trust and accuracy in the compensation process.

## Page 25

Slalom’s Role: 
●​ Slalom was engaged to perform a discovery phase, assess the current state, 
and define future state recommendations. 
My Role: Solutions Architect / Data Strategist 
Result: 
1.​ Extending the Engagement through built in trust for being the SME for 
Data Strategy and Architecture  
 
Actions: 
●​ I led a Slalom team of 2 members in the initial phase to do the data discovery and 
current state assessment which required: 
○​ interviewing stakeholders across teams and understanding their needs and 
pain points. 
○​ Reviewing existing data assets and infrastructure setup and pipeline 
○​ talking to both the analytics and SOX teams to understand pain points and 
review earlier audit reports. 
●​ I mapped out the data issues, showed the real business impact (33% of the data is 
only provided by DET in SOX compliant way), and helped leadership see where the 
biggest gaps were — which got everyone aligned on improving both process and 
architecture. 
●​ I recommended future-state data architecture options — S3 + Snowflake and an 
S3-based lakehouse — and walked the team through the trade-offs of each. 
 
 
Result2: 
2.​ Considered as a trusted advisor for North Star Architecture Alignment 
Actions: 
●​ I looked into Salesforce’s global technology team (DET) technical architecture and met 
with enterprise architects to understand the overall architecture, and design an 
architecture that fit into the company's overall direction, not just the GIC analytics 
setup. 
○​ The goal was to build on the existing Snowflake instances and create a 
solution that could scale gradually without disrupting business operations, 
while paving the way for a more stable and improved data pipeline. 
■​ Ownership of data 
■​ Defining data flows their key data assets

## Page 26

●​ I worked with executives to align on the GIC Analytics North Star vision and built 
an architecture that aligned with the vision and made compensation data more 
reliable, accurate, and timely. 
○​ For stable, long-lived SOX reports, built and maintained by DET in the 
certified EDW 
○​ Utilizes a "Controlled DEP" for evolving SOX controls, ad-hoc audit 
requests,strategic decision support and compensation modeling 
●​ I presented the architecture to the SOX and DET teams to ensure alignment on how 
it would integrate with upstream data systems. 
 
Result 3: 
3.​ Considered as a trusted Advisor for Data Governance  
Actions: 
●​ Over time, the customer trusted me more and started depending on me to shape the 
data governance approach and make sure it fit into the overall architecture and 
roadmap. 
●​ Reviewed the existing access controls and defined the improvements using the 
RBAC in Snowflake, as well as defining data ownership 
●​ Removing the ambiguity of ownership, and stewardship of data 
 
Result 4: 
4.​ Coaching the Salesforce GIC Analytics Team and Bridging Capability 
Gaps 
Actions: 
●​ created detailed technical specs explaining each layer of the architecture — 
why it existed, how data should flow through it, and what best practices to follow 
for scalability and governance. 
●​ held several working sessions and walkthroughs with their data engineers to 
explain implementation details, answer questions, and reinforce best architecture 
practices 
●​ The client’s analytics director had mentioned that I helped fill a critical data gap 
and raised the technical bar for the team. 
Result 5: 
5.​ Acting with Urgency to Fill a Skill Gap and Maintain Customer 
Confidence 
Actions:

## Page 27

●​ Mid phase, The customer’s expectations had shifted — the role had become 
much more project-management heavy, requiring strong coordination and 
proactive communication. 
●​ I worked closely with our account and delivery leadership to assess the 
situation and quickly align on the right profile for replacement. 
●​ I moved fast to hire someone who was a better fit for the role’s new scope, while 
making sure the transition didn’t impact delivery. 
Measure/ Quantify: 
●​ Data from 10 different sources systems like Salesforce, Workday, and other native 
apps. 
●​ 20+ different compensation programs 
●​ Documented the 80+ reports and their sources 
●​ Co-ordinated/ collaborated with 2 BT teams, 3 Upstream Teams, 2 Enterprise 
architects, and Managers and SOX compliance team 
●​ Coordination with Account team people and Slalom leadership 
●​ Presented to 5 different groups 
Google Project 
●​ On the Google WPA project, I established the technical foundation by designing the 
end-to-end data architecture, resolving PII and security requirements for the Google 
WEPS UX team, and delivering a clear requirements document and solution design that 
aligned all stakeholders on the implementation path. I operated with minimal direction, 
translated ambiguity into structured deliverables, and built strong rapport with Hong and 
Sarah. My technical solutioning, productivity, and ability to communicate across technical 
and business audiences were key in moving the project forward despite infrastructure 
and dependency challenges. 
FruitCo Exp (AI/ML Ops) - (Priority 2): 
About the client/project 
AI/ML Ops: 
FruitCo’s AI & Machine Learning (AIML) organization powers intelligent features across core 
applications such as Siri, Mail, Calendar, Music, and Photos. 
Within this group, the Annotation Operations (Annotation Ops) team provides the 
human-in-the-loop foundation for Fruitco’s machine learning — a 6,000-person global workforce 
responsible for labeling and validating data that trains Apple’s ML models.

## Page 28

Data-Driven Operations: Productivity, quality, and quota compliance are tracked 
continuously through dashboards and performance analytics. 
Challenges: 
 
●​ The existing data ingestion process was not scalable or standardized, leading to 
frequent failures and manual interventions. 
●​ Multiple disjointed pipelines and embedded transformation logic within Tableau made 
reporting unreliable and hard to maintain. 
●​ The upstream data provider teams were not aligned or supportive in delivering data in 
the required structure and cadence for the BI team. 
 
My Role: Solutions Architect  
6.​ Turning Around an At-Risk Engagement 
 
●​ Brought into an at-risk engagement after consultant left mid-project 
●​ Discovery phase was complete but lacked direction and next steps 
●​ Partnered with orgs DataOps team to clarify requirements and infrastructure 
needs 
●​ Identified key data sources to ingest and curate first 
●​ Proposed fast-track MVP: start with one dataset to show quick value and set 
foundation for scale 
●​ Delivered MVP successfully — restored client confidence and rebuilt trust in the 
account 
 
7.​ Using Iceberg to Fix Data Quality and Build Trust 
●​ Designed data-engineering approach using Apache Iceberg for time travel, 
incremental refresh, and upstream update tracking 
●​ Implemented schema-evolution standards to handle upstream data changes smoothly 
●​ Improved data quality, traceability, and reliability through Iceberg’s metadata and 
versioning​
 
8.​ Account Expansion and Extension at FruitCo 
●​ Built a self-service analytics pipeline enabling business users to explore and onboard 
datasets independently 
●​ Focused on scalable ingestion and transformation pipelines with downstream analytics 
and ML use in mind for around 6000 or so global workforce doing 100 annotations 
per day.

## Page 29

●​ Collaboration with data scientists to curate datasets at the right granularity and 
privacy standards 
●​ Outcome: engagement expanded into a larger, long-term partnership for continued 
platform scaling 
●​ Received a Customer Impact Award from a senior, long-time Apple stakeholder in 
recognition of the results (you can start with - i do want to mention)​
 
9.​ Scaling the Architecture to Upstream Data Engineering / DataOps 
●​ Integrated data workflows with MLOps pipelines for automated retraining and 
deployment via Airflow and CI/CD 
●​ Designed standards for incremental data refresh and tracking of upstream changes 
adopted by DataOps team 
●​ Established foundation for scalable, governed data platform supporting both analytics 
and ML initiatives 
●​  
Measure/Quantify 
●​ 6,000-person global workforce 
●​ 100 annotations daily by an analyst 
●​  
Apple Exp (Sales Ops): 
About the client/project 
 
Challenges: 
 
 
My Role: Solutions Architect  
●​ Apple sales - I led the data-harmonization workstream — met with teams across 
retail, digital, and carrier sales, documented pain points, and defined how data 
would be ingested and transformed. 
Measure/Quantify 
●​

## Page 30

Results(Impact): 
 
 
RFPs 
 BayRen - Priority 4 
About the Client / Project 
●​ BayREN manages six separate energy and water efficiency programs across the Bay 
Area. 
●​ Each program had its own database — no central repository or unified reporting. 
●​ The goal was to build a Data Aggregation and Reporting Tool to automatically pull, 
transform, and consolidate data across all six programs into a single reporting layer.​
 
Key Challenges 
1.​ Six disconnected databases with different schemas and data formats (PostgreSQL, 
Excel, and CSV exports). 
2.​ Manual, time-intensive reporting with inconsistent metrics and no automation. 
3.​ Needed a common data model and reliable refresh mechanism to generate unified 
metrics and dashboards. 
 
10.​
Contributed directly to $2–3M in new D&A pipeline through RFPS 
and account extensions. 
 
My RFP Role: Technical solutionist 
●​ Worked with client executives, practice leads, and the pursuit team to define 
requirements and shape the technical solution. 
●​ Wrote the technical sections of the RFP, including: 
○​ Approach for the Technical Solution 
○​ Example of a Cloud-Hosted Data Platform on AWS 
○​ Assumptions and Constraints in Selecting the Solution​
 
●​ Designed a scalable AWS data architecture using S3, Glue, Redshift, and Lake 
Formation, ensuring it met both governance and scalability needs.

## Page 31

●​ Helped draft the SOW, RACI, and delivery plan, aligning technical scope, 
staffing, and pricing with the proposal. 
●​ Joined the orals presentation to walk the both technical and business audiences 
on the customer side through the proposed architecture and delivery approach. 
●​ Contributed to $2–3M in new pipeline for the Data & Analytics practice. 
 
11.​
Partner Collaboration & AWS MAP Funding (Pre-Sales, AWS) 
“We had a client who wanted to test a new data architecture, but they didn’t have 
any budget for a proof of concept, and we didn’t want to lose momentum. 
I was asked to find a way to fund the POC so we could move forward and still show 
quick value. 
I reached out to our AWS alliance team and explored options through the MAP 
program — the Migration Acceleration Program.​
 I drafted a short proposal explaining the use case, the AWS services involved, and 
how it could increase their cloud consumption over time.​
 Once the funding was approved, I led a small cross-practice team — data 
engineers — to run the POC and integrate with AWS analytics services. 
The POC was completely funded by AWS, so the client didn’t have to pay a thing 
but still got a working demo in their environment.​
 That success built trust with the client, opened the door for a larger engagement, 
and also strengthened our partnership with AWS for future projects.” 
RFP  - Salesforce Informatica Merger - Priority 4 
 
About: 
●​ Objective: plan the integration of Informatica systems and data into Salesforce’s 
ecosystem post-merger 
●​ Focus on system mapping, data flow consolidation, and risk-aware migration roadmap​
 
Key Challenges 
●​ Large number of overlapping systems and data integrations between both 
companies 
●​ Lack of unified inventory of critical systems and dependencies 
●​ High risk of business disruption during migration without clear prioritization

## Page 32

●​ Need for a multi-phase roadmap balancing quick wins and long-term stability 
 
My Role: 
 
●​ Proposed migration-readiness assessment using structured scoring (complexity, data 
volume, business criticality) 
●​ Documented risks, assumptions, and mitigation plans for inclusion in the RFP 
response 
●​ Approach for below outcomes: 
○​ Identify and prioritize the most critical systems, data flows, and 
integrations for migration to support core business processes 
○​ Reduce risk by flagging migration challenges and high-impact dependencies 
early 
○​ Accelerate implementation with a migration readiness report and multi-horizon 
migration roadmap 
 
Salesforce is seeking proposals from qualified consulting firms to support Informatica M&A 
integration planning program.  
 
Systems and Data Flow Assessment - detailed out assessment approach and acceleration methods 
 
 
Irhythm - Workshop & POC (Pre-Sales) - Priority 3 
About iRhythm 
●​ iRhythm is a health-tech company developing wearable cardiac-monitoring 
devices to detect heart rhythm disorders. 
●​ This was a new logo for Slalom, so it was important for us to make a first 
impression. 
●​ Their Data Systems & Services group needed to generate faster, more reliable 
insights from the vast amount of device data being collected — to improve both 
operational efficiency and patient outcomes. 
Challenges 
●​ At the time, iRhythm was in the middle of a major platform transition: 
○​ They were moving their data warehouse from Redshift to Snowflake. 
○​ Data ingestion relied on new Go-based extractors, still in development. 
○​ There was no established ETL/ELT framework, which made data movement, 
transformation, and validation slow and inconsistent.

## Page 33

My Role: Solutions Architect  
Led a two-week discovery and assessment of iRhythm’s data platform.​
 
12.​
Data Discovery & Demo Workshop Leading to Extended 
Engagement (iRhythm - Pre-Sales) 
●​ Proposed and delivered a four-week test-and-learn POC to demonstrate:​
 
○​ Automated data discovery and cataloging. 
○​ PII-aware metadata tagging and privacy compliance. 
○​ Data-quality monitoring across representative datasets. 
●​ Designed and demoed the solution using AWS Glue (cataloging, schema tracking) 
and Amazon Macie (PII detection), integrated with quality rules and remediation 
workflows. 
●​ Presented the architecture to both executive and engineering teams, resulting in 
the acceptance and leading it to extended engagement 
●​  
Measure/ Quantify: 
●​ Tea size: 6 
●​ Duration: 6 weeks (2 week discovery, 4 weeks, test and learn) 
 
Databricks - Slalom Partnership 
●​ With growing client demand for modern data platforms, Slalom has been deepening its 
co-selling and solution-development partnership with Databricks. The focus is on 
building industry accelerators and repeatable Lakehouse frameworks that quickly 
demonstrate business value. 
My Role 
●​ Partner Enablement & Accelerator Development 
●​ I’ve been collaborating closely with Databricks partner managers to identify high-impact 
industry accelerators — focused on Lakehouse and Unity Catalog — and to enhance 
existing assets or design new ones aligned to customer use cases. 
●​ These accelerators aim to shorten delivery time, improve governance, and help clients 
adopt the Databricks Lakehouse more effectively. 
●​

## Page 34

BrickBuilder Series 
●​  
●​ I participated in the Databricks BrickBuilder program, which strengthens go-to-market 
alignment and co-selling opportunities between Databricks and its partners. 
●​ The program showcases partner-developed solution assets — either horizontal technical 
solutions or industry-specific offerings — and includes partner-led enablement sessions 
where Databricks architects share best practices for Delta Lake, Unity Catalog, and 
Lakehouse governance. 
●​ I also earned Databricks badges through this program, deepening my technical 
proficiency in these areas. 
●​  
Data Engineering Cohort Development 
●​ Participating in Slalom’s internal Data Engineering cohort to upskill teams on Databricks 
Lakehouse architecture, earning Data Engineer and pursuing professional certifications 
to enable future Databricks-based client engagements. 
 
13.​
Databricks Brickbuilder Program Participation (Databricks - Pre 
sales) 
14.​
Databricks - COE - accelerators and certifications 
Open AI - Technology partners -partnership 
(pre-sales) 
About -  Slalom is participating in an early pilot with OpenAI’s Codex, an AI-powered 
code composition and agentic development tool. A small internal cohort (including you) 
will be granted Codex licenses to experiment, provide structured feedback, and 
shape Slalom’s long-term adoption strategy for generative AI in software and data 
engineering. 
 
15.​
Generative AI Pilot (OpenAI Codex): 
●​ Participating in an early internal pilot with OpenAI’s Codex, an AI-powered code 
composition and agentic development tool. As part of a small cohort, I’m experimenting 
with its applications in data engineering and solution development, providing structured 
feedback to shape Slalom’s generative AI adoption strategy.

## Page 35

CMDS - Multiple Technology Partners - 
Snowflake, Fivetran, Dataiku, ThoughtSpot, and 
Alation. 
16.​
Slalom CMDS Partnership with Snowflake and Ecosystem Tools 
(Multiple clients - Pre sales) 
“As part of Slalom’s Cloud Modern Data Stack (CMDS) initiative, I worked on a 
partnership effort with Snowflake and several ecosystem vendors — including 
Fivetran, Dataiku, ThoughtSpot, and Alation.​
 The goal was to design and present a modern data-architecture blueprint that 
showed how these partner tools could work together to accelerate data 
modernization for our clients. 
I collaborated with our Snowflake partner team and vendor solution architects to 
evaluate how each tool fit into the end-to-end data flow — ingestion, transformation, 
governance, and visualization.​
 We defined reference architectures that showcased Fivetran for ingestion, 
Snowflake for storage and compute, Dataiku for machine learning and data 
science workflows, Alation for cataloging and governance, and ThoughtSpot 
for self-service analytics. 
I helped document and present this architecture to both internal teams and 
prospective clients, positioning it as a ready-to-deploy accelerator for cloud data 
modernization.​
 It not only demonstrated how these technologies complement each other but also 
helped Slalom and Snowflake co-sell the joint value proposition to clients.” 
 
 
17.​OpenAI  partnership - codex tool evaluation 
Learning and being curious 
18.​
Constantly Learning and Staying Ahead (Databricks & RAG 
Architecture) 
“With more of our clients asking for Databricks-based solutions, I’ve been very 
intentional about continuing to upskill and stay ahead of what’s coming next in the 
data space.

## Page 36

I recently completed several Databricks certifications and participated in 
partner-led enablement sessions focused on Lakehouse architecture, Delta Live 
Tables, and governance with Unity Catalog.​
 It’s helped me better understand how Databricks positions its platform end-to-end 
— not just for analytics, but also for machine learning and real-time data 
engineering. 
At the same time, I joined an internal learning cohort where we explored 
Retrieval-Augmented Generation (RAG) architecture — combining vector search, 
LLMs, and Databricks’ AI capabilities.​
 I worked hands-on to build a small proof of concept using this pattern and later 
presented it to our internal team to share learnings and discuss how we could 
extend it for client use cases. 
For me, continuous learning is part of the job — it’s what helps me bring fresh, 
relevant perspectives to client conversations and stay aligned with how the data 
and AI landscape is evolving.” 
1.​  
ICE Mortgage 
 
About the client/project & challenges 
ICE Mortgage’s Data Connect transforms complex, high-volume Encompass loan data into 
structured, queryable datasets for lenders — but faces challenges around real-time data 
consistency, schema evolution, massive scale, and multi-tenant orchestration while 
maintaining performance and reliability. 
 
My Role: Data Architect / Data Engineer 
 
Stories: 
19.​
Performance Optimization with EMR (ICE Product) 
“While working on the ICE data product for one of our major clients, we started 
noticing performance bottlenecks in their reporting layer — queries were running 
slowly, and the customer was getting frustrated with long refresh times. 
I dug into the issue and realized that some of the large-scale transformations were 
running inefficiently on their existing setup.​

## Page 37

To address this, I proposed moving the heavy workloads to AWS EMR, where we 
could take advantage of distributed processing and better resource tuning. 
I worked with the team to reconfigure the data pipelines, optimize Spark jobs, and 
fine-tune the cluster settings to balance performance and cost.​
 Once deployed, the query times improved by nearly 40%, and the customer 
immediately noticed the difference. 
This optimization not only made the ICE product much faster and more reliable, but 
it also earned strong trust from the customer, who started involving us in deeper 
discussions about scaling their platform and performance strategy going forward.” 
a.​ Drove 60% cost reduction in EMR streaming workloads and 80% faster Athena 
query performance through Spark tuning and architectural redesign.​
 
b.​ Implemented observability frameworks (Spark UI in private subnet, EMR 
monitoring) and benchmarked all critical releases to ensure SLA compliance. 
20.​Architected the Enterprise Data Platform at Ellie Mae (ICE) 
a.​ Created a generic ingestion architecture migrating from RabbitMQ to Kafka, 
enabling scalable, real-time data delivery. 
○​ Acted as bridge between engineering, QA, and product management teams to 
align technical design with business objectives. 
 
LPs mapping & Keywords 
 
Keywords-LPs-Questions
 
 
Team Moghul Award 
 
You were nominated for Team Mogul NorCal H2. Below nomination information! 
From SD Singh "Salesforce ICM Modernization Team": 
"Slalom team is an integral part of the SPIFF Implementation team at Salesforce. Has been able 
to address key capability gaps to achieve program goals including experience design, process 
re-engineering, SOX program management as well as workstream and program leadership. 
Slalom team members have demonstrated excellence in delivery and subject matter knowledge 
to assist Salesforce leaders in implementing key capabilities related to compensation planning 
and operations, next-generation analytics and payee experience."

## Page 38



## Page 39

ARCHIVED

## Page 40

ARCHIVED

## Page 41

Other Behavioural Questions

## Page 42

Other Behavioural Questions 
1. Tell me about yourself​
1 
2. What is your top strength?​
2 
3. What is your weakness?​
2 
Intro (2 mins)​
3 
✅ 2. How does your day-to-day look like?​
4 
✅ 3. Salary expectations (the safest framing)​
5 
Questions​
5 
Mind Map​
5 
 
 
 
1.​Tell me about yourself 
​
⏪ Past: 
 
I started my career as a data engineer, working hands-on with pipelines, data modeling, and 
analytics delivery. Over time, I moved into architecture because I found myself naturally 
connecting business goals with technical solutions — understanding not just how to build 
something, but why it matters to the end users. 
 
⏸ Present: 
 
Today, as a Senior Solutions Architect in Slalom’s Data & Analytics practice, I work across both 
pre-sales and delivery. I create technical solution documents, lead client discovery workshops, 
and coordinate between account teams, engineers, and partner architects — especially for 
AWS-based data platforms. 
 
Recently I’ve been involved with a large CRM company to design an incentive analytics 
architecture, and a consumer-electronics client to unify their global sales data. My day-to-day 
revolves around aligning stakeholders, documenting current-state gaps, and defining 
architectures that are feasible and governed from the start. 
 
⏩ Future: 
 
Going forward, I want to continue in architecture roles that bridge strategy and implementation 
— working on complex, multi-team data ecosystems. I’m also investing time in deepening my 
Databricks and AI expertise.

## Page 43

Keywords: data architecture, AWS, cross-functional coordination, discovery, RFPs, governance, 
practical solutions. 
2.​How is your day going so far? 
Ans: It’s going great, thanks for asking! I’ve been really looking forward to our chat today - how’s 
your day going so far? 
 
3.​ Where do you see yourself in 5 years?  
 
 
 
Intro (2 mins) 
I’m a Solutions Architect in the Data & Analytics practice, working with some of our 
Slalom’s strategic NorCal accounts. I have been with Slalom for around 3 years now, and 
based out of the East bay. My focus has been advising, guiding, and building scalable data 
solutions for customers — my work spans across both pre-sales and delivery tracks. 
 
On the pre-sales side, I support  
●​ RFPs by providing technical solutions,  
●​ run workshops with new and existing clients to generate leads and opportunities, and 
●​ collaborate with our technology alliance managers to promote partner platforms, 
grow the customer base, and create new opportunities. 
 
On the delivery side, I’ve recently led several architecture engagements. 
 
At Salesforce, I  
●​ led the architecture for their Global Incentive Compensation analytics team — 
making sure it aligned with their North Star vision and enterprise standards. In the 
process,  
●​ I partnered with several business and technical teams to define how the data from 
different systems will flow into Snowflake in a way that was both consumable for 
analytics and compliant with SOX. 
 
For FruitCo— a large consumer electronics and technology company —  
●​ I led the design and architecture of their AI/ML operations lakehouse on AWS and 
Iceberg, supporting large-scale model-training and data-quality workflows. 
 
Before Slalom,

## Page 44

●​ I led the data platform team at ICE Mortgage Technology in Pleasanton, where I worked 
with production workloads — optimizing EMR jobs, optimizing spark performance, 
and modernizing pipelines. 
 
I am also a trusted AWS architecture advisor in our D&A practice —  
●​ helping with sales pursuits and building our team’s skills in the D&A space. Lately, 
I’ve been part of Databricks learning cohorts and GTM enablement sessions with our 
Databricks partners. 
 
So that’s a bit about me and the kind of data architecture and solutioning work I’ve been leading 
across clients. Happy to share more details as needed. 
 
●​  
 
✅ 2. How does your day-to-day look like? 
Version to Say Out Loud (30–40 sec)​
 “My days are a mix of pre-sales architecture work, hands-on technical solutioning, and partner 
collaboration. I support Slalom pursuit teams on in-flight deals — doing discovery, designing 
architectures, running workshops, or building demos. 
With dedicated customers, I work closely with their engineering and data teams, helping them 
evaluate current-state platforms and shaping the right modern data solution — often across 
AWS, Databricks, or Snowflake. 
I also spend a meaningful amount of time learning and upskilling — I’m part of the Databricks 
cohort at Slalom and actively working on Lakehouse certifications. So overall, it’s a balance of 
customer-facing work, technical deep dives, and continuous learning.” 
●​  
 
✅ 3. Salary expectations (the safest 
framing)

## Page 45

“I’m very flexible. For me, the most important thing is the right role, team, and growth path. I 
trust that Databricks offers competitive, top-of-market compensation for its Solutions Architect 
roles, so I’m comfortable aligning with your bands once we determine that it’s a mutual fit.” 
Use this to maintain boundaries while staying cooperative: 
“I completely understand. My priority is finding the right role and team. I’m confident we can land 
on something fair once we move further in the process.” 
 
Questions 
1. “What does success look like for a Solutions Architect on the Digital Native team in the first 90 
days?” 
 
 
“Before we wrap, I’d love to get your guidance on what to expect in the upcoming interview 
rounds so I can prepare effectively. What does the interview sequence typically look like for this 
team?” 
======= 
 
 
Mind Map 
 
1.​ Give me an example of a time you used customer feedback to drive improvement or 
innovation. What was the situation and what action did you take? 
 
 
2.​ Tell me about the most innovative thing you’ve done and why you thought it was 
innovative (can also probe with: That sounds more evolutionary than revolutionary – tell 
me about something you’ve done you feel was truly revolutionary? Ask for one or two 
additional examples to see if it’s a one off or pattern.) 
 
3.​ Tell me about a time you were able to make something significantly simpler for 
customers. What drove you to implement this change? 
Talk about self service pipeline

## Page 46



## Page 47

Apply:

## Page 48

Newer: 
You will guide customers in designing advanced cloud-based data architectures, implementing 
innovative technologies across AWS services (including Amazon RDS, Aurora, Redshift, Athena, EMR, 
Glue, Kinesis, MSK), partner solutions (Snowflake, Databricks), and open-source frameworks (Spark, 
Flink, Trino), while adopting the best cloud practices for databases, storage, and analytics services.  
 
Sr Data Solutions Architect, Strategic Accounts - AWS 
 
https://www.databricks.com/company/careers/field-engineering/solutions-architect-retail-64566750
02?gh_jid=6456675002&gh_src=62a881d62 
 
https://www.databricks.com/company/careers/-field-engineering---indirect/sr-specialist-solutions-ar
chitect---aws-partner-solution-architect-8108693002?gh_jid=8108693002&gh_src=62a881d62 
 
 
https://www.databricks.com/company/careers/field-engineering/solutions-architect-retail-64566750
02?gh_jid=6456675002&gh_src=62a881d62 
https://www.databricks.com/company/careers/-field-engineering---indirect/sr-specialist-solutions-ar
chitect---aws-partner-solution-architect-8108693002?gh_jid=8108693002&gh_src=62a881d62 
 
 
 
 
 
Older: 
 
Apply: 
https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4321885578&originToLa
ndingJobPostings=4335531262%2C4321885578%2C4317369432%2C4335511113%2C432173
9937 
 
https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4335511113&originToLa
ndingJobPostings=4335531262%2C4321885578%2C4317369432%2C4335511113%2C432173
9937 
 
https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4321739937&originToLa
ndingJobPostings=4335531262%2C4321885578%2C4317369432%2C4335511113%2C432173
9937 
 
https://www.linkedin.com/jobs/view/4312177404/?eBP=CwEAAAGac_-qdLS_SSMp94FO58PZo
ybWDmMecXa2L9Bxn18h9pd7_tY92Xewrs3x6tNn8VqhmGB_hAmn3nuP_HLbej7n2QWXHb1fc
hhRd196Qfvj9Pu6stx0--CoL-kuIQ3feXLfHeOffliE2QfSLowmCW4sSJ84ccMfTqH2T5MJdmJfHno
9xiNZ4J9S0o_UV0ZGF5txzS8OVmZMM6BblSF9CfsDAdhiM0PV3hQYj6obWnXpA-GNBVMhw
Xt_3ASOWn1XrWESJVTW4PcgxvQqA9PcJ7mDlzjD1J8RUyQEZd7sJntphTz9OLXpDjh-5Z-X-3

## Page 49

xFqTGFaqRo8cFYL6ym6yIsqw2HfrUQCQlXmzBHby0N3an7EKGcq_Ry5pyBJfq8rIImeJxIJk55w
a7hpgfI56wjnWK-6S3m6L1d3b9QPv270z3p5eccyrKCPkMmPHALzpT11BcxLMxcEyiaTi03efNK
d7nHv2ckuhuoOSgzU_x0&trk=flagship3_jobs_discovery_jymbii&refId=gm%2F%2FDjuTS4cdfE
2SZ4Cirw%3D%3D&trackingId=8vx7Je755piMOeVb8A08yQ%3D%3D 
 
https://www.linkedin.com/jobs/view/4321885578 
 
 
 
 
 
Asheesh: 
https://www.linkedin.com/jobs/collections/recommended/?currentJobId=4321885578&originToLa
ndingJobPostings=4335531262%2C4321885578%2C4317369432%2C4335511113%2C432173
9937 
 
 
 
 
Apply: 
 
 
 
https://www.databricks.com/company/careers/field-engineering/solutions-architect---digital-nativ
e-business-6117719002?gh_jid=6117719002&gh_src=si050rvy2us 
 
 
https://www.databricks.com/company/careers/-field-engineering---indirect/sr-specialist-solutions-
architect---aws-partner-solution-architect-8108693002?gh_jid=8108693002&gh_src=62a881d62 
 
https://www.databricks.com/company/careers/field-engineering---fe-direct-regulated/solutions-ar
chitect-8243221002?gh_jid=8243221002&gh_src=62a881d62 
 
 
 
https://www.linkedin.com/in/ericjonhenderson/ 
 
 
https://partner-academy.databricks.com/pages/91/agents-bricks-catalog-partners

## Page 50

●​ Expertise in data governance systems and solutions that may 
span technologies such as Unity Catalog, Alation, Collibra, 
Purview, etc. 
●​ Experience with high-performance, production data processing 
systems (batch and streaming) on distributed infrastructure.

## Page 51

Stripe

## Page 52

Stripe 
 
https://stripe.com/jobs/listing/partner-solutions-architect/7251505 
 
 
https://www.linkedin.com/jobs/view/4318720474 
 
 
As a member of the team, the Solutions Architect will build highly consultative trusted relationships 
with c-level executives and technical decision makers in the customer’s organization to provide 
business and technical thought leadership, and become a trusted advisor in solving mission-critical 
business challenges. She/he will architect business models with them so they can drive new 
monetization opportunities and growth for both the user and Stripe. 
 
Responsibilities 
 
●​
Be a key member of a Stripe account team with deep involvement in defining the customer 
strategy 
●​
Identify and close new complex opportunities, and accelerate solution adoption. Understand 
and align with the customer’s product and business roadmap and uncover opportunities for 
Stripe to accelerate their progress on that roadmap. 
●​
Drive thought leadership and be a trusted advisor for key business and technical 
stakeholders including CIO, CTO, COO, CRO, CDO, Head of Product Engineering and Head of 
Payments. 
●​
Work to deeply understand the customer’s business objectives, and then design and apply 
Stripe’s solutions to their challenges. Develop and articulate the end to end customer 
transformation journey and create future roadmaps and architectures with deep 3rd party 
integrations in play. 
●​
Conduct business analysis and background research on customers, industries, and 
competitors with a view to support growth for the user's business. 
●​
Lead strategy engagements with users to align to business priorities, design solutions and 
secure the technical win by performing in-depth customer discovery, evangelizing the 
proposed solutions through executive briefings, readouts, presentations, workshops and 
solution demos. 
●​
Expand Stripe’s footprint within existing accounts to new global markets and business units 
by introducing new capabilities and local payment methods. 
●​
Act as the “Voice of the Customer” to bring insights, trends and opportunities to the 
leadership, product and engineering teams from the forefront and prioritized for delivery. 
●​
Participate in sales forecasting, Quarterly Business Reviews and account/territory planning 
to strategically and tactically align for success 
●​
Approximately 25% travel is anticipated to help you connect in-person in a meaningful way 
with users and collaborate internally​

## Page 53

Final Stories-backup

## Page 54

Final Stories 
 
2.​ What i want to tell : Turned Around an At-Risk Engagement (Apple).  
S: I was brought in in an urgent distrust situation when a consultant had left. The 
discovery phase was completed, with no clarity of what work needed to be done 
T: I was supposed to quickly understand and stabilize the next phase to design and 
subsequently lead  a team for implementation 
A: I did deep to understand the current state, discovery of data that needed to be 
ingested and curated, and proposed / presented an architecture with all the different key 
use cases, and their ecosystem, which was well received by the client, along with an 
approach to move fast and quickly to deliver MVP, with a particular dataset, and leading 
teh team to build an end to end use case. 
R:The customer gained more trust in slalom and further, relied on me as SME consulting 
and looking for solutions for the data issues 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
 
 
 
3.​ What i want to tell: Iceberg utilization and advanced DE knowledge to handle data issues 
S: At the beginning of the last year, the customer was frustrated by unexpected issues 
and changes stemming from the data sources upstream, which were introducing data 
quality issues into their leadership reports.  
T: Bring in capabilities to address the data quality issues and increase trust in data 
A: designed and presented to seek alignment with the team and leaders. Design 
addressed issues like late arrival of data, time travel, incrementally refresh data and 
tracking updates of the data upstream . used Iceberg for implementation and  
R: The critical datasets were handled specifically for these nuances, and these are now 
continuously running in production with failure logs.This increased the trust in data for BI 
analysts and data scientists to use this platform which kept on increasing with more 
datasets for a longer term. Customer Impact Award from Apple Executive 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
 
4.​ What I want to tell:  Acted as a technical advisor to the data governance workstream of 
the customer at salesforce. 
S: The GIC team was facing a lot of compliance issues w.r.t. SOX compliance, and also 
they did a lot of manual work providing audit reports to the sox team

## Page 55

T: I was asked by the customer to provide guidance and lead to their data governance 
needs, and define and suggest best practices for the data access patterns in snowflake, 
and .. and the roadmap and path for long term, SOX compliance,  
 
A: navigated and discovered the pain points and their existing state of data access and 
ownership patterns.Spoke to SOX compliance team and reviewed the earlier compliance 
reports, to understand what is going on. Suggested specific measures like RBAC and 
granular access controls, with automated audit controls to give trust to sox compliance 
team, and  
R: generate trust in the data pipelines that GIC analytics team was suing. The team was 
doing less manual efforts to provide manual reports to ensure compliance and increased 
focus and productivity on data analysis and BI activities of the team 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
 
5.​ What I want to tell: Extended the engagement with the customer(Salesforce) to help 
advise on data strategy and meeting long term vision & goal and providing technical 
solution for the same  
S: Slalom was hired for the discovery phase and was finishing up with findings and key 
gaps and future state recommendations. 
T: to provide the best future state recommendation and roadmap based on assessment 
A: Based on the discovery we did at customer’s eco-system, I went ahead and 
generated numbers in terms of highlighting the key data gaps, and its impact on 
business.  I led discovery workshops, defined architecture options, and presented 
data-governance and ingestion frameworks that were later approved by executives. 
Those conversations helped shape the final engagement 
 
R: The presentation led the customer to be more interested in slalom and an interest to 
continue the engagement for taking the architectural recommendations further. 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
6.​ What I want to tell: presented to enterprise level architects and VPs the architecture and 
roadmap to architecture to meet the north star vision and goals of gic with tradeoff and 
got alignment. 
S: The GIC analytics team was very much dependent on various BT (Business 
technology) teams to provide the data in shape and form that is useful for them to 
generate meaningful insights and make critical decisions on sales compensation. There 
was a delay caused because of misalignment of priorities for BT team and was affecting 
overall key business decisions and insights in the GIC analytics team. Identified that the 
team was bringing in their data manually on their own to meet the business needs.

## Page 56

T: i was tasked with sharing the requirements and future state required to meet the north 
star vision  
A: Based on the initial discovery phase, I designed and presented future state scalable 
architecture to the BT architects emphasizing the need for this architecture and as well 
VPs to help understand the business value we get out of it. 
R:The future state architecture vision helped the VPs make a decus=ion to invest in 
pieces in the same quarter and plan pieces of this in the coming quarters. 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
7.​ What I want to tell: Did a data discovery and demo workshop with a health client 
resulting in larger engagement with the client. 
S:  Irythm was a new logo for the slalom team, new client. Salom was in 3rd week of 
strategy engagement - lot of moving parts, they don't have full fledged ETL or ELT tool , 
they were writing their GoLang extractor, they have decided to move from redshift to 
snowflake. iRhythm’ s service delivery team has embarked upon a journey toward 
next-generation data services platform to support the company’s rapid growth.  Slalom 
will support the service delivery team to establish strategy and roadmap for the platform 
and help with execution of one “test & learn” experiment in a non-production 
environment for the data services platform. 
T: i was brought in the test and learn phase, where the primary objective was to do 
suggest architecture options based on the outcomes from exploration phase, and then a 
do a poc for end to end for a particular use case in their environment  to evaulate and 
confirm on the architecture. 
A:did evaluate architectural options and did poc in their environment, and at the end of 4 
week, did a demo presentation to customer on data cataloging service, schema 
monitoring and privacy catalog using glue in aws. Also used Macie for data quality 
integration. Purpose: 
Central catalog that shows detail about data sources in Snowflake Data Warehouse 
This catalog is automatically triggered when data lands in S3 Data Lake 
Snowflake uses this data catalog for Data Masking 
 
Who:  
Anyone who uses data in Snowflake to understand the contents of the data they are 
using (data types, PII identification) 
 
Test & Learn: 
Created Glue workflows to create data catalogs with 2 different data sources:  
Salesforce Account  
Data Science (ztrans device data) 
 
1 re-usable script for any data source

## Page 57

R: Led to a x dollar extended engagement with slalom with a team of engineers. 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
 
8.​  RFP & Pre-Sales Solutioning 
 
Situation: 
We had a few big RFPs come in — some from existing clients and some new logos — 
and our D&A practice was trying to grow its pipeline for the next fiscal year. I was pulled 
in as the solution architect to shape the technical proposal. 
 
Task: 
My role was to understand the business pain points, come up with a solid AWS-based 
data solution, and make sure the proposal included a clear architecture, timeline, and 
delivery plan. 
 
Action: 
I worked closely with the client exec, practice leads, and pursuit team to break down the 
RFP. 
I designed the data platform using AWS services like S3, Glue, Redshift, and 
LakeFormation, and made sure it fit their governance and scaling needs. 
I also ran discovery sessions to confirm the assumptions, helped draft the SOW, outlined 
the RACI and deliverables, and joined the orals to present our solution. 
Throughout the process, I made sure the pricing, staffing, and technical scope all tied 
together cleanly. 
 
Result: 
Those efforts contributed to about $2–3 million in new pipeline for our practice through a 
few successful RFP wins. It also strengthened our position with the client, leading to 
follow-on work. 
 
Keywords to use: 
RFP cycle • Pre-sales • AWS data architecture • SOW definition • Discovery workshops • 
Pipeline growth • Solution alignment 
 
Leadership principles (optional tie-ins): 
Earn Trust • Dive Deep • Deliver Results • Customer Obsession 
 
9.​ Partner Collaboration & AWS MAP Funding 
 
Situation:

## Page 58

We had a client who wanted to test a new data architecture, but there wasn’t any budget 
for a proof of concept. We didn’t want to lose momentum. 
 
Task: 
I needed to find a way to fund the POC so we could move forward and show quick value. 
 
Action: 
I reached out to our AWS alliance team and explored MAP funding options. 
I put together a short proposal explaining the use case, expected AWS workload, and 
how it could grow cloud consumption for AWS. 
Once funding was approved, I led a small cross-practice team — data and Salesforce — 
to run the POC and integrate Salesforce Data Cloud with AWS analytics services. 
 
Result: 
We got the POC fully funded by AWS, so the client paid nothing but still got a working 
demo. It built trust, opened up a larger engagement, and strengthened our AWS 
partnership. 
 
Keywords to use: 
AWS MAP • Partner funding • POC enablement • Alliance collaboration • Cost 
optimization • Cross-practice teamwork 
 
Leadership principles (optional): 
Think Big • Invent and Simplify • Ownership • Earn Trust 
 
10.​What I want to tell: Building capability gaps through coaching GIC salesforce analytics 
team for the best de practices, was called out by hongwu by customer bridging critical 
data gaps  
S: The GIC analytics team was facing a lot of challenges with data  
T: I was brought in as an architect to pener\trate the proposed architecture and best 
practices in the existing team and  
A: I provided detailed technical specs and also had multiple sessions with the client team 
to help understand the impl level details and the need each layer served and best 
practices to follow to have a more robust and scalable data platform 
R: Adoption of the architecture grew, the lead data engineer was more equipped with 
taking the data needs with the core eng team, and also have their team follow the 
standards for implementation, This led to faster and more reliable data insights of teh 
compensation program. Key client GIC analytics director also acknowledged that I have 
filled in the critical data gap in the team. 
Keywords while being interviewed: 
LPs: 
Questions it can address to:

## Page 59

11.​What I want to tell: Slalom CMDS - partnered with snowflake to place fivetran, dataIQ, 
thoughts[pot, alation and others to define teh architecture and present to , p-lacing their 
value and and pitch for customers 
S: 
T: 
A: 
R: 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
 
12.​What I want to tell: Account expansion and extension at frruitco and salesforce 
S: Slalom was finishing the  
T: Presenting to the client about data discovery adn assessment, and talking through the  
A: 
R: 
Keywords while being interviewed: 
LPs: 
Questions it can address to: 
 
 
 
13.​Taking PM hat when the team member was under performing and showing urgency to 
hire and train the best to meet the needs of customer 
 
 
14.​Constantly learning - with the growth of asking for databricks by customers, I recently did 
some databricks certifications  and also part of partner training. Have recently completed 
a cohort doing some hands on with rag architecture with proof of concept presenting this 
our internal group. 
 
 
15.​Performance optimization - I used EMR to optimize which improved query time by 40% 
and earned trust with the customers using the ICE product

## Page 60

—---------

## Page 61

Aprajita -2

## Page 62

Aprajita -2  
 
FruitCo and Salesforce 
 
Co-ordinate with business process people, identifying process gaps, how these business 
process gaps were filled by technology. 
 
During the discovery we did not only look from teh technology side of things, but also looked at 
the process gaps, how you were not leading only from the architecture perspective, but 
how you were leading teh business processes. Where the  business processes working 
with them and to identify how these gaps can be overcome with the technology perspective. 
 
(BT team, talking to architects) 
 
While the team was working on the discovery phase, i went ahead and spoke to the key 
stakeholders on how they can benefit from … hwat are the things you can proritize to get 
immediate benefits. (talk about low hanging/ high hanging fruits) - curated layer first… bringing 
in governance in curated zone. 
 
How we can integrate with other teams and benefit from  
 
Benefits - quality or quantify. 
 
DG - piled on teh last, while you were doing the interviews, you found the process gaps, 
captured and created the future phase. 
 
They got excited, they wanted to get into the next phase. 
 
 
I created the opportunity and generated the roadmap, how much TCV? Check from SOW. ( 
2million - 5 year, 3 year deal - 1 million) 
BASICALLY - for selling you need to know the numbers, how many people, how much 
you coordinated, different teams, high level ballpark num ber is good. 
 
Junior resource - 150 per day 
 
ADVISORY ROLE - phase 1 sell, while the team did wrap up, you extended as an SME. 
Taking the vision and strategy alignment with exec leaders. 
FRUITCO - leading the while thing, closely working with key stakeholders to give them a 
vision, to strategize with tehm, that generated the prop. 
 
 
As a leader, you need to show how you are able to co-ordinate

## Page 63

RFP 
Why AWS? They were on AWS cloud already. AWS MAP funding.  
 
We are technology agnostic. We helped them evaluate based on their environment, and data 
volume, …(for audit purpose they wanted to keep 5 years of dat) 
 
We were getting good funding from AWS MAP funding from AWS for the engagement, that also 
drove the decision. 
 
Account team gets involved,  
 
IRhythm 
In our case, there are multiple account leaders who are involved in getting initial lead, and then 
the process… we understand the requirements, we give initial proposal, what it will take, it 
involves solutioning, and trade-offs, and then if tehy go with us, this is the team and timeline that 
we propose. 
 
You worked on the logo.  
 
When I joined Slalom, this was my very first project, which was a new logo, and we 
wanted to make a good impression and build a long term relationship with the customer. 
As a senior person I was responsible to lead the solutioning, and the problem statement 
was given to me. - discovery and workshop 
 
 
Show: 
1.​ Working with two deals at a time, also working as SME overseeing few 
deliverables. Helping out the junior resources if they have any specific challenge. 
2.​ Defining strategy with the leaders at the client side 
3.​ Architecture suggestion, and helping the team overcome challenges as they 
executed the project. 
4.​ Say if ask about percentile (only if needed) - 60:40. Dont be so specific. 
 
 
What were the most difficult technical challenge you faced? 
WHo has been your most difficult client? How did you convince them? 
How do you help your team come out of a problem - technical business?

## Page 64

Trying to win a deal with proper solutioning, highlihing risks and any assumptions made 
during the process. 
Top down solution - high level soln when i dont have many data points 
Bottoms up - you have all the data… and then you design 
What kind of automation can i bring,how to increase the productivity, make the soln 
better 
Business problem solving 
Spound techno functional

## Page 65

Final Exp - Notes

## Page 66

My Experience 
 
Summary (Elevator Pitch) 
1. Delivery clients/projects (post sales) 
2. RFP Technical solutioning (pre-sales) 
5. Client Workshop: iRHYTHM data platform foundation AWS Workshop 
3. Slalom Alliance Partners led growth (pre-sales) 
 
 
Summary (Elevator Pitch) 
Being part of the D&A practice one of the senior solutions architect who knows AWS very well, I 
was part of multiple proposals, which involves certain….i was creating technical solution 
documents, engaged in doing workshops with the client to try and understand, collect the data 
point to do initial assessment, to do initial discovery to make sure my solution aligns with the 
long term delivery plan. In that phase I have impacted 2-3 million dollars of proposals through 
RFPs. 
My work spans both post and pre-sales — I lead solution design during RFPs and strategy 
sessions, then guide those same solutions through implementation and adoption. For example, I 
recently helped a global tech firm build their AI/ML Lakehouse platform to improve data trust 
and scalability. 
 
 
1.​Delivery clients/projects (post sales) 
My Recent teams (reverse order) and customers & brief of what they do, and slalom’s role: 
a.​ Salesforce Global incentive Compensation team -  
i.​
Business  
The ICM team defines the “how and what” of sales incentives — from 
compensation plan design to ensuring the correct calculation and 
accounting of commissions. 
GIC Analytics & Ops Reporting Team -Providing data transparency and 
reporting across incentive compensation — ensuring leaders can track 
performance, payouts, and compliance.

## Page 67

ii.​
Business challenges: 
The GIC Analytics team’s core business challenge is to transform 
fragmented, complex incentive-compensation data into a single, reliable, 
and compliant reporting ecosystem that leadership can trust for 
decision-making and financial governance. 
iii.​
Slalom’s Role: 
Slalom’s Role in the GIC Analytics Engagement 
1. Discovery and Current-State Assessment 
Slalom was brought in to understand and document the current state of 
Salesforce’s GIC reporting, analytics, and data architecture landscape. 
This involved identifying reporting gaps, data dependencies, pain points in 
the existing SPIFF-driven data model, and inefficiencies in how 
compensation analytics were being produced and consumed by 
leadership. 
The team worked closely with GIC stakeholders to capture the "as-is" 
state of reporting workflows, systems, and compliance dependencies 
(SOX, revenue accounting, etc.). 
2. Recommendations and Future-State Vision 
Based on findings from discovery, Slalom developed recommendations 
for the “North Star” future state of GIC Analytics — defining what a 
modernized, reliable, and scalable reporting ecosystem should look like. 
This included data architecture recommendations (how SPIFF data 
should flow into analytical schemas), reporting layer redesign, and 
process improvements to reduce manual intervention and ensure 
audit-ready data. 
3. Collaboration with BT and GIC Teams 
Slalom’s role extended to aligning with the internal BT (Business 
Technology) team to ensure that the recommended analytics and 
architecture roadmap fit within Salesforce’s enterprise data strategy. 
They acted as a bridge between the GIC business teams (who defined 
the reporting needs) and BT technical teams (who owned data systems 
and integration pipelines).

## Page 68

The goal was to jointly define a North Star vision and architecture — a 
unified approach for data ingestion, transformation, and reporting that 
could scale across all 17+ compensation plans and ensure financial 
compliance. 
iv.​
My Role (Elevator Pitch):  
I led the discovery and architecture strategy for Salesforce’s Global 
Incentive Compensation (GIC) Analytics transformation — a 
cross-functional initiative aimed at unifying how Salesforce manages, 
calculates, and reports on global sales compensation. 
My role centered on conducting a current-state assessment across the 
SPIFF platform, data pipelines, and reporting layers to identify 
architectural and reporting gaps. I partnered with GIC business leads and 
the BT (Business Technology) team to define the “North Star” data and 
reporting architecture, ensuring the new ecosystem could deliver 
SOX-compliant, scalable, and automated analytics across 17+ incentive 
plans and thousands of sellers. 
In short, I helped Salesforce move from manual, fragmented reporting to 
a centralized, governed, and architecture-aligned incentive analytics 
platform that leadership can trust for performance and financial decisions. 
b.​ Apple - Global Sales Team -  
i.​
Business: 
Apple Sales Operations – Business Overview 
Mission & Scope 
Apple’s Global Sales Operations team, particularly Ben’s US Channel 
group, is responsible for enabling Apple’s consumer and carrier sales 
partners (Amazon, Best Buy, Target, Costco, Walmart, AT&T, Verizon, 
T-Mobile, etc.) to drive revenue growth through data-driven insights, tools, 
and operational excellence. 
Core Responsibilities 
Performance Tracking & Reviews: Deliver weekly, monthly, and quarterly 
sales reviews to monitor channel performance, highlight trends, and 
identify sales opportunities. 
Partner & Marketplace Insights: Provide visibility into how Apple products 
are performing across major online and retail channels.

## Page 69

Digital Sales Enablement: Expand capabilities in digital sales analytics — 
understanding traffic, conversion, and deal performance across digital 
storefronts. 
Operational Support: Equip field sales teams with dashboards, 
scorecards, and tools (e.g., Tableau, Salesforce D360 Digital, Rocket) to 
understand short-term performance and inform sales strategies. 
Governance & Data Access: Manage data ownership, access control, and 
permissions across teams and tools. 
🚧 Business Challenges 
1. Data Fragmentation & Inconsistency 
Data is sourced from multiple partners and third-party providers (Amazon, 
Best Buy, SimilarWeb, etc.), each with different formats, time scales, and 
update cadences. 
Much of the data is manually pulled or partially structured, making it 
difficult to harmonize into a unified dataset. 
Impact: Incomplete and inconsistent data undermines trust in reports and 
limits Apple’s ability to make timely, data-driven sales decisions. 
2. Lack of Harmonized Digital View 
The team’s “North Star” goal is to build a cohesive, weekly digital sales 
dashboard showing traffic, search trends, and sales across all partners. 
However, achieving this requires standardized ingestion, cleaning, and 
transformation pipelines that don’t yet exist. 
Impact: Apple lacks a single source of truth for digital sales performance 
— making it hard to link web traffic and search data to actual sales 
outcomes. 
 
3. Limited Tool Adoption & Data Trust 
Sales teams underutilize tools like Tableau, Salesforce D360 Digital, and 
Rocket, often due to complex dashboards and low confidence in the 
underlying data quality. 
Without consistent adoption, insights fail to translate into action.

## Page 70

Impact: Operational inefficiency and missed opportunities for proactive 
sales management. 
 
4. Insights vs. Reporting Gap 
 
Current focus remains on report production, while the long-term vision is 
to deliver actionable insights that drive decisions (“what to do next,” not 
just “what happened”). 
There’s also a need to improve data literacy and build a culture of 
self-service analytics among field teams. 
Impact: Sales operations remain reactive rather than strategic, limiting 
Apple’s agility in a fast-moving retail and carrier landscape. 
5. Alignment & Governance Complexity 
Organizational alignment is needed across consumer, carrier, and digital 
sales operations, with stakeholders  owning key parts of the process. 
Data ownership and access governance are bespoke and siloed, slowing 
down standardization and cross-channel visibility. 
Impact: Slow progress toward a unified data strategy and difficulty scaling 
analytics capabilities across regions. 
ii.​
Slalom’s Role 
 
Conduct a comprehensive current-state assessment of Apple’s Sales Operations 
data ecosystem, processes, and reporting tools. 
Engage stakeholders across Consumer and Carrier sales functions to capture 
key business requirements, KPIs, and success metrics. 
Define the future-state architecture for unified digital sales reporting — outlining 
both short-term quick wins and long-term strategic recommendations. 
Enable and educate Apple’s internal engineering and analytics teams on the 
proposed architecture, data harmonization strategy, and implementation 
roadmap.

## Page 71

iii.​
My Role (Elevator Pitch – Draft) 
I led the data and architecture strategy for Apple’s Sales Operations 
transformation — focusing on harmonizing fragmented digital sales data across 
major retail and carrier partners. 
Through stakeholder interviews and technical assessments, I defined the 
future-state reporting architecture and established a roadmap to transition from 
manual, partner-specific reporting to a standardized, insight-driven analytics 
platform. 
My role also included guiding Apple’s internal engineering team on data 
integration best practices, governance, and scalable implementation patterns to 
ensure lasting adoption and measurable business impact. 
c.​ Apple - AIML Annotations Operations team 
📈 Business Overview 
 
Apple’s AI & Machine Learning (AIML) organization powers intelligent features 
across core applications such as Siri, Mail, Calendar, Music, and Photos. 
Within this group, the Annotation Operations (Annotation Ops) team provides the 
human-in-the-loop foundation for Apple’s machine learning — a 6,000-person 
global workforce responsible for labeling and validating data that trains Apple’s 
ML models. 
 
Key Business Functions 
 
Human-Guided Machine Learning: Analysts annotate text, images, audio, and 
video to improve model performance and accuracy. 
Massive Operational Scale: Hundreds of millions of annotation records are 
produced daily across multiple global sites. 
Structured Workforce Model: Multi-tier hierarchy (Analyst → Team Lead → Site 
Lead) operating under strict throughput and quality metrics. 
Data-Driven Operations: Productivity, quality, and quota compliance are tracked 
continuously through dashboards and performance analytics.

## Page 72

Slalom’s Role: Building data pipelines, curated datasets, and high-performance 
Tableau dashboards to monitor quality, throughput, and operational efficiency 
across this massive ecosystem. 
i.​
Slalom’s Role: 
🧭 6. Slalom’s Role & Apple’s Environment 
 
Slalom’s role has evolved from data visualization (Tableau) to data 
engineering, curation, and performance optimization. 
 
Apple’s AWS and Snowflake environments are customized, highly secure, 
and integrated with Apple’s private infrastructure — not standard cloud 
setups. 
 
Emphasis on simplifying data consumption for Apple teams while 
maintaining trust in data quality. 
 
ii.​
My Role (Elevator Pitch): 
Work with the  
d.​ Genentech  (Jan 23 ) -  
i.​
Business: 
​
the company's Research and Early Development (gRED) group is 
responsible for discovering and developing new medicines. Its work involves 
fundamental scientific research, tackling complex diseases like cancer and 
multiple sclerosis, and using advanced computational tools and data science to 
create breakthrough therapies. 
gRED scientists need a cloud-enabled computing environment that 
enables seamless collaboration with our external collaborator, Recursion, 
and our Roche colleagues in pRED. They wish for computational scale on 
demand with data, methods and infrastructure sharing that will speed the 
generation of insights and the identification of novel targets and small

## Page 73

molecules.  gRED and Recursion will work together in partnership to 
achieve this vision. 
Most of gRED’s data is on premises and fragmented. This aspect of the 
current state of gRED’s data landscape could slow down cloud adoption 
and should be factored in when measuring the pace of adoption. This risk 
is likely to materialize in scenarios where new applications scheduled to 
be deployed to the cloud need to integrate with current on premises 
datasets. Deployment of such applications may require additional design 
considerations to address security and performance challenges related to 
the transfer of data between on-premises and the cloud. This is 
particularly true for any new cloud application which would need to 
integrate with gRED’s large Oracle instances such as TAPIR, BioPRod, 
ACCPRD2 or SSP or datasets located on NFS and GPFS. 
Finally, while gRED users have expressed an interest in improved dataset 
management practices, a culture of systematic data management is 
currently not established within gRED. Ideally, gRED’s cloud offering 
should provide solutions to help users adopt these practices and develop 
such a culture and keep its cloud as a clean and organized space from 
the data standpoint. This could pay dividends once a large number of 
datasets and applications are deployed and it is possible to list out most 
datasets along with their metadata. 
 
ii.​
Slalom’s Role: 
iii.​
My Role (Elevator Pitch): 
e.​ IRhythm (oct 22 - dec 22)-  
i.​
Business -Based on the sources, the company, referred to as "rhythm" 
(and the subject of the audio file "Irhytm.mp3"), appears to be involved in 
heart-related technology. 
In simple terms, the company is described as being like a "Samsung 
smart watch or Apple Eyewatch but specifically made for heart". 
The sources also detail the current scope of the consulting engagement 
with the company, which focuses on their data infrastructure and strategy: 
• Data Strategy: The current engagement is a strategy engagement that 
involves developing a data strategy for services for the self-serve sort of 
environment. 
• Infrastructure: The company uses AWS. They have decided to move 
from Red Shift to Snowflake.

## Page 74

• Data Handling: The engagement involves work on data injection. 
Currently, they are writing their own extractors in Golang because they do 
not have a full-fledged ETL or ELT tool yet. 
• Project Goals: A specific job during this engagement is to build an 
architecture and a framework where people can onboard data sources in 
a consistent fashion onto the data lake. There is also a mention of reading 
about Argo workflows for orchestrating containers. 
ii.​
Slalom’s role - new logo for slalom team, new client. Salom was in 3rd 
week of strategy engagement - a lot of moving parts, they don't have full 
fledged ETL or ELT tool , they were writing their GoLang extractor, they 
have decided to move from redshift to snowflake - that aspect also. We 
are doing data strategy for data services - catalog service. Build an 
architecture where people for …workflow orchestration. 4 phase explore, 
design and develop, do a test and learn experiment, define a roadmap 
f.​
ICE Mortgage Data Connect -  
i.​
Business: 
Data Connect 
 
ICE Mortgage’s Data Connect transforms complex, high-volume 
Encompass loan data into structured, queryable datasets for lenders — 
but faces challenges around real-time data consistency, schema 
evolution, massive scale, and multi-tenant orchestration while 
maintaining performance and reliability.

## Page 75

ii.​
DE Team’s Role: 
iii.​
My Role (Elevator Pitch): 
Leading the data connect team, for building the dta aconnect products, 
working with product managers on requirements and feature releases, 
and also work with AWS Sa for architecting and designing the data lake. 
2.​RFP Technical solutioning (pre-sales) 
Elevator Pitch: 
Being part of the D&A practice one of the senior solutions architect who knows 
AWS very well, I was part of multiple proposals, which involves certain….i was 
creating technical solution documents, engaged in doing workshops with the 
client to try and understand, collect the data point to do initial assessment, to do 
initial discovery to make sure my solution aligns with the long term delivery plan. 
In that phase I have impacted 2-3 million dollars of proposals through RFPs. 
How did you do it - i worked with the pod, i worked with the account team, i 
worked with RFP timelines, depending on what their requirements is, we 
responded in a certain way,

## Page 76

I have also helped with the SOW, writing down the activities, what deliverables, 
how the RACI will be defined, what are the technical components or automation, 
which should be involved in the solution. 
Impact - it generates the pipelines for our D&A,brings business to the company, 
helping Slalom grow. 
 - Examples 
RFP Responses
1.​ Informatica Integration Planning Program 
a.​ Client: Salesforce 
b.​ Date: Aug-2025 
c.​ Description: The acquisition of Informatica is currently under 
regulatory review and is expected to close in Q1 FY27. Integration 
planning activities have begun pre-Close to get ahead of 
impending scale & complexity of the deal. The Salesforce 
Customer Success org is looking for consultants to help us with 
pre-Close preparatory work with the goal of faster and smoother 
integration post-Close. 
Scope of work details: 
Note: Below scope applies to all functions under the ‘Customer 
Experience’ organization at Informatica viz. Customer Support, 
Customer Success, Renewals, Professional Services (Education 
Services only) and Strategy & Operations:​
Business Process Analysis & Customer Journey Mapping 
Systems and Data Flow Assessment 
Employee Role Mapping 
d.​ My Role: Contributed to Systems & data : Approach and Deep 
Dive slides and presentation for below slides:

## Page 77

2.​ Data Aggregation and Reporting Tool RFQ – Energy-RFP 
a.​ Metropolitan Transportation Commission 
b.​ March-2024 
c.​ Description: BayREN currently administers a portfolio of six 
energy and water efficiency programs. Each program has a 
designated Program Manager/Lead who maintains a separate 
database housing their program’s data. A central 
database/repository does not exist; instead, there are currently six 
isolated datasets requiring manual, time-intensive processes to 
display the impacts of multiple programs (i.e., multiple databases).  
This project seeks to create a Data Aggregation and Reporting 
Tool that reduces this burden by automatically interacting with the 
six existing databases to retrieve data on a predetermined 
frequency (e.g., monthly), transform the data into common 
metrics, and consolidate data from multiple programs into 
customizable reports.  
The resulting tool should be hosted by ABAG/MTC and accessible 
to approximately 25 users, including staff from ABAG/MTC and 
each of the nine counties. It is desirable that permissions be 
structured to permit a small subset of users with the ability to 
create and edit reports, while the majority of users would only be 
able to run preset reports. 
d.​ My role: Writing technical specs for the RFP response for following 
sections: 
i.​
Approach for the Technical Solution 
ii.​
 Example of a Cloud Hosted Data Platform Using Amazon 
Web Services (AWS) 
iii.​
Assumptions / Constraints in Selecting the Technical 
Solution

## Page 78

Links: 
Solutions, Insights and Experiences - Slalom 
https://lucid.co/blog/mckinseys-three-horizons-of-growth 
3.​ data strategy workshop proposal (CCC) 
4.​  
5.​Client Workshop: iRHYTHM data 
platform foundation AWS Workshop 
 
Project Description: Client is interested in exploring options for establishing data analytics 
platform and jump start implementation of high priority use cases. Client needs to define a 
roadmap for its future data and analytics capabilities which potentially require AWS data 
analytics & machine Learning capabilities and services. With the focus on 
 
A-​
Basics functional and non-functional needs for establishing an MVP for the data 
foundation platform. 
B-​
Ability to collect data from multiple sources and ingest into the analytics workspace

## Page 79

C-​
Build a roadmap for building a foundational data analytic capabilities/service that 
enables the client to create self-service BI and analytics ecosystem for the business users. 
D-​
Analyze requirements for data quality and governance requirements  
 
 
Slalom / AWS Outcome 
client on their data cloud journey roadmap, starting point and the MVP of the data 
. 
el requirements for data collection, storage, governance and analytics solution and 
l leveraging AWS services. 
el architecture/component for the target ecosystem 
Customer Outcome 
the starting stages of the client’s data transformation journey mainly driven based 
uture need for leveraging specific data analytics and machine learning services and 
ies that are required for MVP of the data platform and learning about the AWS 
es and funding the program and reduces the initial cost of the business. 
 
3. Slalom Alliance Partners led growth (pre-sales) 
I also have experience working with our alliance partners within Slalom, in which I have worked 
to get some MAP funding, or funding from technology partners, which we have invested in 
doing small POCs, or trying out use cases at the client side. 
 
You also worked with multiple practices. I have worked with Salesforce practice, to talk about 
the salesforce data cloud integration,  
 
1.​ Brickbuilder Specialization 
2.​ Contribution  in CMDS 
3.​ AWS MAP 
 
16. SOW Building 
 
============ 
 
 
3.​ Discovery of data and current state and putting lens of gaps compared to best practices 
4.​ Evaluating and Presenting architectural options 
5.​ Technical advisor for data architecture and governance 
6.​ Build SOW 
7.​ Provide technical solution in RFP responses 
8.​ Workshops with customer

## Page 80

9.​ Stakeholder interviews and building requirements specs 
10.​Partner growth and funding 
11.​You work alongside account executives or partner managers before the deal closes 
12.​You understand client needs, design technical solutions, build prototypes/demos, 
and present architecture diagrams that lead to adoption. 
13.​You translate business pain points into technical proposals and influence buying 
decisions. 
14.​You enable partners — helping them co-sell and co-deliver .

## Page 81

companies-buiness

## Page 82

ARCHIVED - NOTES 
Index 
a. Salesforce Global incentive Compensation team 
 
Index 
 
a.​Salesforce Global incentive Compensation team 
• Incentive Comp Plans: Salesforce utilizes incentive comp plans. It is 
believed that the company has 17 different comp plans and incentive 
comp plans. 
• Commissions Logic Architecture: The SPIFF Proserve team is 
responsible for the commission's logic architecture. This team's job is to 
set up the commissions logic so that the end result—the comp statement 
delivered to every seller—is accurate. 
• Compensation and Revenue: Commissions are based on a sold 
opportunity or ACV (Annual Contract Value). The Accounting and Payile 
Process (led by Dan Riley within GIC) handles the accounting for these 
commissions, ensuring compliance with revenue recognition rules, as a 
sold opportunity generates revenue over time rather than immediately. 
 
The GIC (Global Incentive Compensation) team owns several 
workstreams, one of which is Analytics and Ops Reporting. This 
workstream is led by **The GIC (Global Incentive Compensation) team 
owns several workstreams, one of which is Analytics and Ops Reporting. 
This workstream is led by Tim Lynn. 
Based on the sources, the primary responsibilities and functions of the 
GIC Analytics and Ops Reporting workstream include: 
• Building Reports: The people involved in this area (the two individuals 
being addressed) will "build the reports that the leaders will see" and 
"figure out what needs to be done" based on those reports. 
• Servicing Leaders' Reporting Needs: The end goal of the overall 
program is for a group of sales leaders and finance leaders to "receive

## Page 83

these daily reports, monthly reports, quarterly reports, all the different 
report types". The work done by Tim Lynn and the team has to be 
"serviced or... rendered by the BT team" to deliver these reports 
accurately and seamlessly. 
• Addressing Reporting Gaps: A critical starting point for the people 
joining this workstream is to determine the "reporting gaps piece of it" and 
figure out "where is the state of affairs when it comes to reporting needs 
and gaps". 
The overall context of the GIC's work, which includes analytics, is focused 
on the accuracy and delivery of compensation-related information: 
• Data Architecture Dependency: The ability to deliver these reports is 
heavily dependent on the data architecture. Mark, the GIC leader, brought 
in external support due to challenges with the architecture piece. The 
analytics and reporting work ties into understanding how the data from 
SPIFF is stored into the schema, tables, and made "ready for all the 
reporting". 
• Compliance and Financial Reporting: Some of the reports generated 
must be Sox compliant and are intended to "feed the financial flow 
statements", meaning there is "no room for error". 
• Leadership Oversight: The team is expected to meet with Tim Lynn to 
"nail down" the state of reporting needs and gaps. The expectation is that 
they will look at existing work to understand what has been done 
regarding reporting gaps. 
In summary, GIC analytics is the team responsible for building and 
ensuring the accurate delivery of compensation and operations reports to 
sales and finance leaders, a task that currently requires significant focus 
on addressing reporting gaps and underlying data architecture challenges 
b.​ Apple - Global Sales Team -  
 
Team Focus & Responsibilities: 
•​
Ben's team is focused on the US channel, covering both consumer and carrier 
reseller partners. This includes major retailers like Amazon, Best Buy, Target, Costco, 
and Walmart, as well as carriers like AT&T, Verizon, and T-Mobile. 
•​
The team supports sales operations by providing tools, insights, and strategy to 
help sales teams understand marketplace dynamics and improve sales performance. 
 
Sales Operations and Functions:

## Page 84

•​
The team is responsible for preparing weekly, monthly, and quarterly sales 
reviews, helping sales teams understand short-term performance (current quarter + one 
quarter) and identifying trends and areas of opportunity. 
•​
Ben emphasized that digital sales operations are relatively new for his team, and 
they are still building up their capabilities in that space. 
•​
A key responsibility of sales operations is helping sales teams analyze the 
performance of specific sales deals and understanding why certain deals may have 
underperformed. 
 
Challenges with Data: 
 
The team faces significant challenges with the inconsistency and disparate nature of the 
data they receive. Data comes from various sources (e.g., partners like Amazon, Best 
Buy, third-party providers like SimilarWeb), and it's often in different formats, on different 
time scales, and sometimes needs to be manually pulled. 
Harmonizing the data is a major goal, with the aim of building a cohesive view of digital 
sales across all partners. This includes correlating sales data with digital traffic and 
understanding the factors driving sales. 
 
Key Project Goals: 
 
The "North Star" for the project is to be able to report digital metrics (sales, traffic, search 
trends) across all partners in the US channel on a weekly basis. 
There is a strong need to develop standardized processes for ingesting and harmonizing 
the data, which is currently incomplete and unstructured. 
Success will be measured by how well the sales teams adopt and rely on these insights. 
A key indicator of success is if sales teams use the tools regularly and can take 
actionable insights from the data. 
 
Tools & Data Consumption: 
 
The team uses several tools for data visualization and reporting, including Tableau and 
Salesforce (D360 Digital, which integrates data from various sources). There is also a 
tool called Rocket for sales teams. 
One challenge is that the existing tools and dashboards are underutilized by the sales 
teams, often due to a lack of trust in the data or complexity in the reports. 
 
Long-Term Vision: 
 
The goal is to transition from merely producing reports to providing actionable insights 
that can drive sales decisions. Ben emphasized that insights should suggest actions and 
not just present raw data.

## Page 85

Adoption of these tools by the sales teams, with superusers acting as champions for the 
data, is critical to success. The project aims to improve data literacy and encourage the 
use of self-service reporting tools. 
 
Organizational Alignment: 
 
Ben sees the project as building a roadmap to harmonize data and solve the challenges 
around sales operations. He believes that creating a detailed plan over the next eight 
weeks will provide a strong foundation for future work. 
He mentioned key stakeholders like Joel and Jigger, who are leaders in the US channel 
sales organization, as well as the need for alignment across the sales operations and 
consumer/carrier sales functions. 
Data Ownership & Governance: 
 
Ownership and access to the data are managed by the sales operations team, with 
permissions often being bespoke to the needs of the carrier and consumer teams. 
Salesforce and Tableau handle the technical provisioning of access. 
 
Apple AIML team: 
i.​
Business:  
The discussion explains how Apple’s AIML (AI & Machine Learning) 
organization — originally focused on Siri — now supports a wide range of 
intelligent features across apps like Mail, Calendar, Music, and Photos. 
The focus is on the Annotation Operations (Annotation Ops) team, their 
structure, data scale, and the role Slalom plays in supporting data 
analytics and platform performance. 
 
🧩 1. AIML & Annotation Ops Structure 
 
AIML Group: Handles all ML-enabled features (voice, text, image, etc.) 
across Apple products. 
 
Annotation Ops: A 6,000-person global workforce providing “guided 
machine learning” — humans labeling data (e.g., drawing boxes around 
objects, transcribing audio, translating text) to train and validate models.

## Page 86

Tasks: Range from labeling images and video frames to audio 
transcription and translation. 
 
Example: tagging whether a music feature correctly removes vocals or 
identifying text in multiple languages. 
 
Nature of work: 
 
Highly repetitive and measurable — throughput and quality are key 
metrics. 
 
Workers are often early in their careers; high churn due to monotony. 
 
Teams operate like a factory assembly line with quotas and performance 
dashboards. 
 
🌍 2. Organizational Hierarchy 
 
Regions: Americas, Europe, and Asia-Pacific. 
 
Each region has regional leads and multiple sites. 
 
Each site has: 
 
Analysts → Team Leads → Senior Team Leads → Site Leads.

## Page 87

Analysts are grouped by locale/language expertise (e.g., English, 
Chinese, Japanese). 
 
Sites are selected for multilingual capacity and data security — most work 
is done on-site, not remotely. 
 
💬 3. Workflows & Quality Measurement 
 
Tasks are broken into projects requiring specific quantities of labeled data 
(e.g., “10,000 data points in a week”). 
 
Performance is tracked via throughput and accuracy metrics. 
 
Outlier detection identifies workers who may be underperforming or 
gaming the system. 
 
Analysts can “level up” to more complex tasks or QA roles if they 
consistently perform well. 
 
Those who drop in quality are retrained or reassigned. 
 
📊 4. Data, Scale, and Tooling 
 
The data volume is massive — hundreds of millions of records from 
annotation tasks logged daily across thousands of workers. 
 
Slalom supports Apple in building data pipelines, curation layers, and 
Tableau dashboards to track performance and quality metrics.

## Page 88

Performance tuning is essential — dashboards must handle massive 
datasets efficiently at the database layer. 
 
👩‍💻 5. Key Stakeholders & Roles 
 
Deborah (Apple): Senior leader (29 years at Apple) overseeing annotation 
ops analytics; values Slalom’s data partnership. 
 
Bryce (Slalom): Focused on Tableau performance and design 
optimization. 
 
Chad / Karen / Sean / Tully: Slalom team members supporting different 
parts of the analytics pipeline and transition planning. 
 
 
 
🧱 7. Key Takeaways 
 
Apple’s AIML annotation system is industrial-scale human-in-the-loop ML 
— labeling, QA, and model validation. 
 
Organizational complexity reflects language diversity, massive scale, and 
sensitivity of data. 
 
Slalom’s challenge is building scalable, performant, and trustworthy 
analytics to help Apple leaders understand and improve global annotation 
operations.

## Page 89

Culturally, many analysts aim for “average” performance to avoid scrutiny, 
creating an analytical need for outlier detection and motivation 
frameworks. 
ICE Mortgage (Data Connect) 
 
The loan data gets originated on Encompass. Customers want that loan 
data. They can get making API calls to getLoan, they can use the SDK, 
they could go through developer connect, but they would have to get the 
loan, parse it and do some work to get that data.  
 
Sometime back, why don't we get that data, break it apart and save it to 
database, and give the jdbc uri endpoint, so that they can pull it. It started 
off as SQL, also supported by Postgres. 
 
Gist is you get the endpoint, and the data would reside in the database. 
That database would have around 200 tables, a lot of columns, and the 
way it works, we internally take that json, that json has nested structure, 
so we say that these child would go in table 1, these thing going to table 
2, another many-many, in other words, every section of the loan is 
translated automatically to a table, and all the properties inside of these 
map to column. 
 
We get the loan, we do the processing and split the loan, and we insert it 
into database, and we keep only the latest version of the loan in db, in 
other words if you see loan guid 12345, you are going to see one row for 
that loan, in all these tables, some of these tables might have  
 
 
You are not going to see loan 12345 at 1 pm, loan 12345 1:05, you are 
not going to see multiple rows, you are going to see only one row, and the 
timestamp that happens is the latest one, or the most recent one. We 
update the older version, we do a lot of updates

## Page 90

A loan changes around 90/80 times per minute or per hour. Multiple loans 
are worked on, we insert and update those many loans.  
 
 
EBS publish the loan change event writing to rabbit mq. We have one 
component called LQI - loan queue ingestor, that guy takes it from rabbit 
mq and passes it to Kinesis. It does not do much processing, it is kind of 
bridge, from this Kinesis the loan queue processor (LQP) kicks that loan 
id that is there in that message (the full loan is not there, it is just a 
wakeup call that this loan changed). The payload of the event has basic 
meta data, (loan id, timestamp, clientid, instanceid), with that info this guy 
goes and does the GetLoan call. Once it gets the loan, it sends the full 
payload of the loan to the Kinesis. 
 
From there, there are 2 branches,  
 
one branch goes to the lambda archiver - it compresses and encrypts that 
loan and it saves it in the Global data lake. Global data lake is nothing but 
S3, with some sort of a partitioning strategy, like a file system path 
structure, clientid, instanceid, year, month, days, very common way of 
storing data in S3. People talk about it as partitioning strategy, why is it 
partitioning, because you have effectively segregated the way you are 
saving data, and you are partitioning your data, you are slicing your data 
by client id, instanceid, year, month, date, that is like a bucket, all the 
loans that match this go into this bucket. There would be many loans 
matching this strategy, many loans are saved on a daily basis. The 
partition strategy kind of dictates how large is gonna be the number of 
loans on those buckets meaning how many loans are saved per day, 
imagine that your partition strategy was not up to the date, but upto a year 
- that would be too many.  
 
As a data engineer, you need to think about how you partition and slice 
your data so you can process it in manageable chunks, how do you divide

## Page 91

and conquer this terabytes of data, you cannot, you have to have 
partitioning instead of buckets. 
 
So we store this data here, here we have JSON compressed and 
encrypted,  
 
and we also send these payloads to the forwarder lambda, ( confusion - 
this guy encrypts the data), it can be encrypted here or here. 
 
Lambda forwarder also picks up from Kinesis, and it is called forwarder, 
because each data connect customer has his own swimming lane, 
independent path with infrastructure that belongs to that customer, that 
process the data for that customer only, so this is what they call PDL 
Kinesis, this is a Kinesis stream only for that customer, its independent 
from these other Kinesis.  
 
 
And then there is a loan processor, this is an ECS containerized 
application, this is a Java application, this is the one that does the Json 
split into tables, it generates a bunch of INsert/update commands, and 
then goes to the database and says execute this batch.  
 
Then there is a RDS instance, SQL server or Postgres, and the forwarder 
is kind of a router, it sees one loan and it has like basic metadata like 
clientid, instanceid, where should I send you, oh based on metadata, 
lookups table, it knows it has to send it to this customer, that routing is 
pretty much the work that it does,  
 
Loan processor picks up does splitting, does insertion, and this is what 
kind of data connect is.

## Page 92

The output to the customer is the database with loan data. The way they 
use the database is usually by select * from a loan where the modified 
timestamp is later than the last timestamp i queried. I remember the last 
query time (say 3 o clock), next time i query is tell me anything that 
changed after 3 o clock. Sometimes they could be running queries 
against 200 tables, or they may be running against specific tables, we 
don't control that, 
 
We keep the latest version of the loan, but that version keeps on updating 
modified, timestamp.  
 
There is another microservice which is not highlighted here which is 
called DPS - data platform service. What we just saw is a real time 
streaming pipeline, but data connect is not all about this. One question is 
how are these things created, or provisioned, well all these things are 
created dynamically, automatically, when there is a customer onboard, for 
which we need another component called DPS. 
 
DPS provides a rest endpoint, and the customer signing up for data 
connect, that customer was already provisioned on Salesforce, somebody 
on Salesforce said you have access to data connect and I am going to 
give you a skew or entitlement that authorizes you to use that, so when 
you login into that UI, we go to PSS there is a … there, that gives you a 
token, that entitlement tells that you are a data connect person, in that 
you have form, in that form you say that I want to access my database, 
with username and password. At that time, the database did not exist. 
When they fill the form, DPS starts provisioning, go and create the PDL 
kinesis, go and create the ECS loan processor, go and create the RDS 
instance for this customer. 
 
Second thing that happens is you need to create the older tables, that 
needs to be there, for you to start inserting data,  
 
The flow we talked about is about inserting data, but who created the 
tables for us to insert the data, DPS creates the table. How does it know 
that it needs to create 200 tables or 201 or 203 and these many columns.

## Page 93

Encompass has a loan schema, description of 19.3, 19.4, 20.1. Every 
single release of Encompass has a schema. These guys look at the 
schema, and they translate that into a bunch of tables. That's the second 
step, first step is we provision all these things, then we set up the tables, 
now we need to replay your last three years worth of data and put them 
into database, because if you only do this real time thing, you are going to 
start seeing fresh data as it happened right now, you are not only 
interested in that, you are also interested in historical data, so we need to 
do what we call data replay. 
 
Data replay is a separate service, it exposes an API. Data replay is 
orchestrated by DPS, so DPS calls replays service, it says replay the last 
three years of data, it takes a data range. This guy goes to EBS, fetches 
the loan, sends it to Kinesis again, and from that Kinesis, it starts flowing. 
Data lake gets refreshed as a side effect, but the point is that it uses the 
same kind of infrastructure, so that is good and is bad. Sometimes we 
take a week's worth of data, and reply to it. That happens when we 
onboard a customer, as well as everytime the customer switches a new 
Encompass version, 20.1, 201. For multiple reasons, the schema might 
change, that may require us to replay historical data to make it look 
exactly like your latest version of data. So we do a data replay effectively 
every quarter for every customer. 
 
Hot swap mechanism for these kinds of scenarios.  
 
Historical data get stored in RDS, at the same time new loans coming up, 
every time you save a loan, you have a new version on the loan, it's like 
an index that keeps on increasing and you also have modified UTC 
timestamp, Data Connect uses that to prevent overriding fresh data with 
old data. 
 
 Let's say that in this pipeline you have the latest version of this loan, you 
are also doing data replay and so how you got an older version of that 
loan, you are going to lose the fresh data that came first? NO - because 
you are going to check what version it is, when was it produced/modified. 
Oh this thing, this is older, so I am not gonna update it. So it takes off not 
inserting old data.

## Page 94

There is also a hash involved. And the purpose of the hash is following - 
you have a new json document every single time, not everything on this 
json changes, it turns out that maybe 80% of the loan did not change, 
only 20% of the loan changed, so the way they manage that, they do not 
want to do a full insert/update on the whole thing, because that would be 
a waste, so for these things, they calculate for every single loan, of these 
json document, they calculate hash, I believe we are using MD5, and they 
compare the hash, if nothing changed, hash is same, I am  not gonna do 
an update on these tables.  
 
Two mechanisms - one is the version and the timestamp, to prevent 
updating information that is older, and the second mechanism is the hash 
to prevent updating things which have not changed, so those are two 
things. 
 
We talked about - 
provisioning,  
Creating the tables 
Data replay 
Real time streaming 
 
 
The only thing that is missing is hot swap. 
 
Hot swap - initially without hot swap, what's gonna happen is data replay 
might take a week so imagine that your schema changed, you now have 
three more tables, or maybe something changed, and we need to replay 
your data for last 3 years, but you also use your database, so we are now 
loading that bunch of data with new columns with something and that 
might affect your scripts, might slow down your queries, it is disruptive.

## Page 95

What these guys did was why don't we just create second RDS instance, 
we populate everything here, according to the new schema, and once it is 
up to date, and we ask, customer do you want to switch from 19.2 to 19.3 
- we switch the dns endpoint, and now we point to the new schema, and 
the old database, is there around for a week or so, and we say you have 
it, I am going to tear it down, I am not going to pay for the db… its some 
sort of blue green deployment, that is faster than replay and it is less 
intrusive, and you are not affected meanwhile while I am doing data 
replay.  
 
Data replay happens during onboarding and it happens every quarter, but 
again think about data replay as a building block, data replay for what 
when. It might happen for different reasons,  but data replay refers to the 
process of going to EBS, get the loan, replay it through here, so it flows 
here, 
 
On the second database, on the hot swap, we do both…. 
 
Loan Audit - as a product its dc…. Athena spark, is more challenging. 
 
Break the components 
What are the challenges?

## Page 96

Interviewing Techniques

## Page 97

Interviewing Techniques 
 
 
Question Type 
Target 
Time 
What Interviewers Expect 
Behavioral (STAR) 
2–3 
minutes 
Full story with Situation, Task, Action, 
Result — concise but complete. 
Technical Design / Scenario 
4–6 
minutes 
Talk through approach, trade-offs, 
architecture diagram (verbally), and 
reasoning. 
Follow-ups / Deep dives 
1–2 
minutes 
Quick, direct answers with 1 supporting 
detail. 
“Tell me about yourself” intro 
1.5–2 
minutes 
Enough to show trajectory, impact, and 
relevance without rambling. 
Closing questions (“Why 
Databricks?” “Any questions for 
us?”) 
1 minute 
each 
Strategic, thoughtful, and high-level. 
 
🎙️ Behavioral Question (2–3 minutes total) 
Example: “Tell me about a time you led a difficult project.” 
Here’s what usually happens: 
1.​ You talk for 90 seconds → set up Situation, Task, and part of Action.​
 
2.​ Interviewer interrupts: “Why did you take that approach?” or “How did you handle 
conflict?”​
 
3.​ You respond briefly (20–30 sec).​
 
4.​ You finish with the Result and reflection (30–45 sec).​
 
🧩 So it’s still your 2–3 minutes of speaking time, but over a 4–5 minute total interaction. 
 
🧩 How to Fit Technical Detail Into 2–3 Minutes

## Page 98

Use this time structure (the “hybrid STAR + Design” model I coach candidates on): 
Section 
Time 
What to Focus On 
Exampl
e 
Situation 
(30 sec) 
Set technical & 
business 
context 
“The client’s streaming pipeline was dropping 
messages due to inconsistent schema evolution.” 
 
Task (30 
sec) 
Clarify your 
ownership & 
challenge 
“My role was to stabilize ingestion and redesign 
the Lakehouse pattern without disrupting 
production jobs.” 
 
Action (90 
sec) 
Blend technical 
and leadership 
narrative 
“I redesigned the schema validation layer using 
Auto Loader’s cloudFiles schema evolution… 
involved multiple teams, presented trade-offs 
between append vs merge, and gained client 
sign-off on phased rollout.” 
 
Result (30 
sec) 
Outcome + 
learning 
“We reduced ingestion failures by 80%, cut 
pipeline latency by half, and built team alignment 
on a scalable framework.” 
 
→ Total 2.5 minutes​
 → Enough to show technical depth + leadership impact 
 
 
⚙️ Technical Design Question (4–6 minutes speaking) 
Example: “How would you design a scalable ingestion framework for streaming and batch 
data?” 
Breakdown:

## Page 99

1.​ Minute 1: Clarify scope & ask smart questions (show structured thinking).​
 
2.​ Minutes 2–3: Lay out high-level architecture (talk through ingestion → processing → 
storage → governance).​
 
3.​ Minutes 4–5: Deep dive into trade-offs (e.g., Spark Streaming vs Auto Loader, Delta 
caching, cluster types).​
 
4.​ Minute 6: Wrap up with results, cost/performance trade-offs, or possible extensions.​
 
💬 The interviewer may jump in — that’s good.​
 You want a conversational design session, not a monologue. 
 
🗣️ Best Practice: Build Natural Pause Points 
Add soft breaks where the interviewer can engage, like: 
“At this point, I’d validate if the data latency requirement fits this design — would 
you like me to expand on that part?” 
This keeps it interactive and lets you control pacing gracefully.

## Page 100

OpenAI partnership

## Page 101

OpenAI partnership 
 
Scope of Work: OpenAI Codex Pilot 
What’s happening:​
 Slalom is participating in an early pilot with OpenAI’s Codex, an AI-powered code 
composition and agentic development tool. A small internal cohort (including you) will be 
granted Codex licenses to experiment, provide structured feedback, and shape Slalom’s 
long-term adoption strategy for generative AI in software and data engineering. 
Core objectives: 
1.​ Hands-on experimentation: Use Codex for internal or personal projects to understand 
its capabilities in real-world development workflows.​
 
2.​ Insight generation: Document strengths, gaps, productivity impact, and edge cases 
across different languages and engineering roles.​
 
3.​ Operational readiness: Develop early thinking on playbooks, best practices, and 
governance for future enterprise rollout.​
 
4.​ Strategic assessment: Evaluate ROI, delivery acceleration potential, and developer 
comfort levels to inform a broader enablement plan.​
 
Guardrails: 
●​ Use only for non-client or explicitly approved work.​
 
●​ No client data; focus on internal experimentation.​
 
●​ Expect to share qualitative and quantitative feedback after trial use.​
 
 
Strategic Impact on Slalom 
1. Workforce Enablement & AI Fluency 
●​ Builds AI-native habits among consultants and architects, strengthening Slalom’s 
reputation as an early adopter of generative development.​

## Page 102

●​ Equips delivery teams to intelligently use and govern AI assistants in engineering and 
analytics contexts.​
 
2. IP & Methodology Development 
●​ Generates internal IP (prompt libraries, reusable templates, workflow standards) that can 
be productized into internal accelerators.​
 
●​ Positions Slalom to standardize AI-augmented development workflows for future internal 
and client projects.​
 
3. Business & Delivery Efficiency 
●​ Early data on productivity lift (e.g., code generation time, defect reduction, onboarding 
speed) will inform whether Codex adoption drives material delivery savings.​
 
●​ Establishes an internal case for potential enterprise licensing if value is proven.​
 
4. Talent & Brand Advantage 
●​ Builds consultant visibility in “next-gen delivery” initiatives — a differentiator in promotion, 
recruiting, and client perception.​
 
●​ Showcases Slalom’s commitment to staying ahead of the curve on AI-driven delivery 
models.​
 
 
Impact on the OpenAI Partnership 
1. Co-Development of Enterprise Use Cases 
●​ OpenAI gains structured feedback on Codex performance, user experience, and 
enterprise integration needs — data they rarely get from consultants.​
 
●​ Slalom becomes a trusted design partner, bridging the gap between model capability 
and real-world delivery workflows.​
 
2. Strategic Positioning for Future GTM

## Page 103

●​ Positions Slalom as a preferred OpenAI implementation partner for enterprise clients 
exploring AI-assisted engineering, code intelligence, or agentic systems.​
 
●​ Creates pathways for joint GTM offerings — e.g., AI-assisted engineering workshops, 
AI code governance frameworks, or “AI-Augmented Delivery” accelerators.​
 
3. Revenue & Influence Potential 
●​ If the pilot demonstrates ROI, Slalom may advocate for enterprise Codex adoption 
internally and across clients — directly expanding OpenAI’s commercial footprint.​
 
●​ Strengthens Slalom’s voice in shaping OpenAI’s enterprise roadmap (security, 
compliance, fine-tuning features, IDE integrations).​
 
4. Trust & Responsible AI Governance 
●​ Reinforces mutual credibility: OpenAI as a responsible tech provider; Slalom as a trusted 
system integrator ensuring safe and ethical AI deployment.​
 
 
Summary in One Line 
The Codex pilot makes Slalom a hands-on design partner to OpenAI — generating 
actionable insights on AI-assisted development, accelerating internal delivery 
innovation, and deepening a strategic alliance that positions Slalom at the forefront 
of enterprise GenAI enablement.

## Page 104

Aprajita

## Page 105

Aprajita - PreSales Talk 
 
RFPs Details 
 
Account extension, expansion are done to generate a healthy pipeline. 
There are 2 parts to it - current and next fiscal year target, all the leaders do projection who is 
generating how much pipeline 
 
 
Pipeline - leads -  
While u r in the project, teher are more requirements coming up - it could be new services, or 
there is legacy system, fragmented data sources, they want to setup a new warehouse.  
 
Business drives these requirements, because they do not get the information that they 
want.(my KPIs do not answer). The IT people generate projects - so whatever leads are with 
customer (e.g. salesforce, the customer says that i have these challenges in IT, how can slalom 
help), i will go i will create a lead, i will talk to practice and open up a oppty in salesforce, that is 
what is called a pipeline. 
 
Multiple phases -  
●​ New logo - not the existing customer,  
●​ You are doing an extension in Existing account , no expansion (not as valued as 
expansion) 
●​ Extension + Expansion : In your existing account, you are extending the piece of work 
+ you are generating new scope of work which is getting generated from the existing 
work or new BU. 
●​ RFPs - Either from existing customers, it can be from a new logo or new customer.  
If the project becomes bigger - 100 million + or 50 million + etc. Then the procurement 
team tells them to do RFP, do not give it to one single vendor. Its an internal process 
 
 
As a solution architect , my role in pre-sales cycle: 
While leaders are generating pipeline, you are brought in for solutioning. There are two phases 
to it: 
1.​ Initially top down - we have some points on business pain points, technical pain points. 
We will tell you at high level point, and we provide a capability kind of view to it with little 
customization 
2.​ Bottoms Up - it happens when leaders are aligned to a top down solution. At stage 1, 2 
or 3, we ask the customer whether they like the solution, in that case, then solutions 
architect and delivery people are involved. Besides solutioning, you do estimation 
and timelines and how many people are involved, what skillset is needed. That

## Page 106

creates pricing and timeline. When you have to give the actual proposal then you do 
solutions architecting, where you want solutions architect to say - you know the problem 
statement and you can use these aws services, so it's templatised as well as 
personalized based on the data points given. 
 
Timeline - staggered approach, not everything ata start and end 
Actual vs Forecasting - When you are in delivery, you create a timeline to estimate, 
how much of governance you need, hands-on, sme 
T&M and Fixed Price - no need to get the details 
 
 
RFP Cycle 
1st phase - respond to RFP, if they like you they invite you 
2nd Phase - You go for Orals (optional) - where you define and actually present the sluion( 
client does 3-4 orals in a day - apprx 2 hrs long), (people - CE client executive, practice lead 
(e.g. slaesforce _+ daata lead, pursuit load, enterprise architect, SME for technology ….close to 
3-4 people), and then they ask you questions and then get satisfaction 
3rd Phase - If the project is too big, they do a due diligence workshop with you where tehy get 
into details and specifics, based on the facts from this workshop, you can refine your solution 
and present the final proposal. 
 
Then the procurement and MSA happen and legal stuff. 
 
—- 
 
Impact/Results of RFP, pre-sales work: 
 
As a part of the solutions team, / solutions architect of D&A practice, I have contributed to 2 
million amounts of the D&A pipeline working on multiple pre-sales deals and accounts. 
 
Position of soln architect SME  
I was part of the pre-sales account, where I was involved in responding to a proposal from the 
technical perspective where I have impacted close to 2-3 million dollars.  
 
Multiple ways to get that target: 
 
As a part of the delivery, as a project/pursuit lead, the team under you in that project, some 
factor accounts to your target. 
If you have responded to multiple RFPs, and you have won the RFP, and you are part of that 
team, you will get credit that you were able to sell a certain amount. 
 
Project yourself  
 
My pitch:

## Page 107

Being part of the D&A practice one of the senior solutions architect who knows AWS very well, I 
was part of multiple proposals, which involves certain….i was creating technical solution 
documents, engaged in doing workshops with the client to try and understand, collect the data 
point to do initial assessment, to do initial discovery to make sure my solution aligns with the 
long term delivery plan. In that phase i have impacted 2-3 million dollar of proposals through 
RFPs. 
 
How did you do it - i worked with the pod, i worked with the account team, i worked with RFP 
timelines, depending on what their requirements is, we responded in a certain way,  
 
 
i have also helped with the SOW, writing down the activities, what deliverables, how the RACI 
will be defined, what are the technical components or automation, which should be involved in 
the solution. 
 
Impact - it generates the pipelines for our D&A,bring business to company, helping Slalom grow. 
https://en.wikipedia.org/wiki/Responsibility_assignment_matrix 
 
 
Partners 
 
Alliance Partners -  
 
 
Sometimes we have do POC or discovey with the client and we need to be funded. Since we do 
not want to charge the client, we reach ut to our technology partners to get funding from them. 
Our technology partners fund us when we are proposing a good workload, may be aws or GCP 
or something, what services we are proposing, what is the data volume, what integrations are 
involved, how much data volume is expected in future etc. 
 
Basically aws, gcp etc, try to understand how muhc we are helping to increase their business. 
There is some benchmark to it (for small workload - x amount, bigger workload - y amount). 
 
My pitch: 
I also have experience working with our alliance partners within Slalom, in which I have worked 
to get some MAP funding, or funding from technology partners, which we have invested in 
doing small POCs, or trying out use cases at the client side. 
 
You also worked with multiple practices. I have worked with Salesforce practice, to talk about 
the salesforce data cloud integration,  
 
You should show - you can coordinate with multiple things, you can pull multiple threads to get a 
proposal done.

## Page 108

Funding Details: 
 
For partners to do the business, they can do it in 2 ways 
Directly go to the customer - challenge is they can buy the solution but who will implement it, 
that is where consultant companies come in. Slalom partners  
 
Partners want us to propose our solution, do POCs, we will fund you to try out our capabilities. 
You know how to implement, you know the pain points of the customer, you sell to me, and we 
will sell to you. 
 
Sometimes the clients go for projects to aws, then aws will say we will give you so much 
discount, if you work with Slalom. That's the role of alliance partners, to create that relationship. 
 
As a solns architect: 
You reach out to multiple alliance partners, to vet out a  solution from different aspects - 1. 
Technical aspect to compare solns. 2. From a licensing perspective what is better from a cost 
perspective.  
 
(Licensing - services use .. cost etc, subscription cost - aws, gcp, vs azure discount. For 
hyperscale - multicloud, the license cost are mostly same, the main difference that comes is 
licensce …how much slalom can get discount for us. ) 
 
As a solns architect, I need to make sure that with the given data points, at a high level its 
doable, feasible, scalable for the future, and sustainable.  
 
Also you need to think end-to-end , which apps are integrating into cloud, in muti cloud, when 
two styetems talk to each other, sap or aws charges its own. At an enterprise level, you are 
looking into integration perspective, and costing perspective,  
 
So what - if you partner with alliance partner, your motive is to get money from them, and you 
give  
 
Price to win - we maintain a margin to project, 20% , 30% if the project is not finishing up on 
time, then margin helps.  
 
We are getting ur poc or discovery free as we are getting partner funding. With that partner 
funding slalom are paid. With the commitment that you use my solution and going to get 
business for long terms. 
 
 
Dont take client name -  
 
Salesforce - big CRM company

## Page 109

Apple - fruitstand 
 
It maybe aws is - Banking sector company gets more discount vs small company, it depends on 
what band they have put the company in.  
Gold partner - base don how much business has sloam done to aws… 
 
EXamples:: 
 
extension/expansion to generate the lead 
What kind of RFPs you worked on (example of RFPs) 
Have a fact in your mind 
 
 
Work with all whom - projects , RFPs, client interaction - any opportunity generated 
 
 
 
===================== 
I just wanted to share an achievement that I’m proud of... 
 
 
 
 
 
11:02 
I recently completed the data discovery and recommendations phase and presented my findings 
to the customer. The feedback was very positive! The primary contact on the customer side 
even mentioned that this was the first time in their tenure at Salesforce that they’ve been able to 
put together this type of documentation, given how complex and challenging the ecosystem is. 
11:04 
Also, it looks like we might be able to secure more people for the project. Check out this 
message: 
Hongwu Wang 
  5:15 PM 
Hi @Madhurima SaxenaThank you for walking us through the recommendations on our data. 
We just kicked off a project on revamping our data environment in preparation for the future spiff 
data. I wonder if someone from the team can help us PM the project, as well as acting as the 
consultant? Also, I will set up a separate meeting to learn more about the team. 
—------------------------ 
 
AWS MAP 
 
The AWS Migration Acceleration Program (MAP) is a program offered by Amazon Web Services 
(AWS) designed to help businesses accelerate their journey to the cloud. It provides a

## Page 110

comprehensive set of services, best practices, tools, and financial incentives to facilitate 
migration projects. Here are some key aspects of the AWS MAP program: 
 
Assessment Phase: This initial phase helps organizations evaluate their readiness for cloud 
migration. It involves assessing current IT environments, identifying the business case for 
migration, and creating a detailed migration plan. AWS and its partners provide tools and 
resources to help with cost modeling and identifying potential savings. 
 
Mobilization Phase: During this phase, organizations focus on building the necessary foundation 
for a successful migration. This includes setting up a Cloud Center of Excellence (CCoE), 
developing operational skills, and addressing any gaps in security, compliance, and governance. 
 
Migration and Modernization Phase: The final phase involves executing the migration plan, 
which includes moving workloads to the AWS cloud. AWS and its partners provide tools and 
services to automate and accelerate the process. This phase also includes modernizing 
applications to take full advantage of cloud-native features and services. 
 
Training and Support: AWS MAP offers training resources to help teams build cloud skills and 
knowledge. AWS and its partners provide ongoing support throughout the migration process to 
ensure a smooth transition. 
 
Financial Incentives: To offset migration costs, AWS MAP provides financial incentives, which 
can include AWS service credits and funding for partner-led services. 
 
Partner Network: AWS collaborates with a network of partners who are experienced in cloud 
migrations. These partners can provide additional expertise and support during the migration 
process. 
 
The AWS MAP program is particularly beneficial for organizations looking to migrate large-scale 
workloads or complex IT environments to the cloud. It's designed to reduce risk, enhance 
efficiency, and accelerate the time to realize the benefits of cloud adoption. If you are 
considering utilizing the AWS MAP program, it is recommended to work with an AWS 
representative or an AWS Partner to tailor the program to your specific needs and goals.

## Page 111

stripe

## Page 112

The expectation is that you're working with them on deals that are in flight that they have where they 
need stripe help in the deal. 
or that you're helping them build solutions or white papers or whatever it might be because a lot of 
white people's at AI right now. I see that's like we might be contributing to their AI strategy from a 
payments and kind of like money movement perspective. So getting in and plugging in and working 
with them, and that's 2 or 3 things, right, that's one deep knowledge of stripe, 2, that's deep 
knowledge or deep relationships with people at Slalom, and then 3, that is, uh, like an actual target 
test case use case like want be an industry, it might be a specific customer, it might be like 
there has to be someone who's actually going to be the target for this. And having enough 
knowledge to know who that is, to go like, OK, slalom are in this place, they're going to do some AI 
agentic commerce thing or whatever it is. 
I know they're really good at automotive, so I'm going to make sure that on my side of the stripe end 
I've got whoever's good at automotive to help with this, but I'm the lead architect on what that might 
look and feel like. So it's not like a day to day thing, it's more just like quarter over quarter, we're 
constantly working on that type of stuff. 
And then there's also like slightly more reactionary, like, there's deals coming in from those partners, 
we're working with them on that, that might mean like helping them with the demos, helping them 
with their presentations, whatever it might be, um, and then the other one is making sure that we're 
at the forefront of enabling those partners to have strike resources that are certified, that are good, 
that are capable, that are able to like bring scale to stripe, because like we're not gonna, we're not 
gonna fill buildings around the world with people who go to market for us or do implementation for 
us, we're going to have to leverage partners for that. So that's kind of like 
our job is to be the technical like field CTO that is out there with those partners making sure that 
they're all capable of doing that, so that's why we were measured on those white pipeline and all 
those kind of things are kind of standard operating metrics because that's the best like lagging 
indicator that's the stuff that we're doing this today is working. 
Does that, does that answer that? Does that make sense?

## Page 113

Links

## Page 114

Links 
 
https://www.kdnuggets.com/top-sql-patterns-from-faang-data-science-interviews-with-code 
https://www.databricks.com/company/careers/interview-prep 
 
 
Important Notes 
 
Rejected Again? Here’s the Truth Nobody Tells You About Hiring | by George J. Ziogas | 
Psychology of Workplaces 
 
 
https://skillroads.com/free-resume-review 
 
Databricks IW 
 
1.​ Know about Databricks - Lunch and Learn is important. Compared with Snowflake. 
2.​ Do DBx professional 
3.​ References/Links: 
a.​ https://www.youtube.com/watch?v=hahPTeXJEBk 
b.​
 
How to Ace the Databricks Solutions Architect Technical Interview | Tips fro…
c.​ https://www.glassdoor.com/Interview/Databricks-Solutions-Architect-Interview-Qu
estions-EI_IE954734.0,10_KO11,30_IP2.htm?filter.jobTitleFTS=Solutions+Archit
ect 
d.​ https://www.reddit.com/r/salesengineers/comments/1iawyr3/databricks_solution_
architect_interview/ 
e.​  
f.​
https://www.reddit.com/r/salesengineers/comments/1iawyr3/databricks_solution_
architect_interview/ 
g.​ https://twodegrees1.sharepoint.com/:p:/t/TNCRFP/EZMNpZ0OYjxCuZ7KEzAffzE
B0f4pGImsAVgjMO7WyrN5rw?e=NsM8wd&ovuser=9ca75128-a244-4596-877b-f
24828e476e2%2Cmadhurima.saxena%40slalom.com&clickparams=eyJBcHBOY
W1lIjoiVGVhbXMtRGVza3RvcCIsIkFwcFZlcnNpb24iOiI1MC8yNTEwMDIxMzgxM
SJ9 
h.​  
4.​ Take notes at 
a.​ Jeffs intro - been with slalom - 12:57 min 
 
https://www.youtube.com/watch?v=Tfpdwf45eK8 
https://youtu.be/iHmCysEsp5o?si=bqr72ubCspj_bpAP

## Page 115

MS

## Page 116

“What’s your experience with Azure?” 
Use this script: 
“My hands-on experience has primarily been with AWS and Databricks, but the core 
of my work has been cloud-agnostic data architecture — designing lakehouse 
platforms, modernizing legacy warehouses, enabling analytics and AI, and guiding 
customers through adoption. 
I’ve worked closely with Azure-based teams and solutions, and I’m very comfortable 
transferring these patterns to Azure. What’s important to me is choosing the right 
architecture for the customer, and I ramp very quickly on cloud-specific services.” 
Why Microsoft? 
I want to work at Microsoft because of the impact — Microsoft is shaping how enterprises 
responsibly adopt data and AI at global scale. This role excites me because it combines 
customer-facing architecture, data modernization, and business impact. It’s where I do my best 
work: helping customers design secure, scalable, AI-ready platforms and guiding them from 
idea to production and adoption. 
 
Azure’s competitive advantage 
Azure’s competitive advantage really comes down to how well it serves enterprise customers 
end-to-end. 
First, Azure has a very strong enterprise and hybrid story. Many organizations already run 
Microsoft across identity, productivity, and core systems, and Azure integrates naturally into that 
environment. That lowers migration risk and makes hybrid and regulated workloads much easier 
to support compared to a cloud-only approach. 
Second, Azure offers a unified data and AI platform. Customers can move from data 
ingestion and analytics to BI and AI within a single ecosystem — using services like Databricks, 
Fabric, Power BI, and Azure AI. That reduces tool sprawl and accelerates time to value, 
especially for AI-driven use cases. 
Third, governance and security are built in from the start. Azure’s identity, access control, 
and compliance capabilities are enterprise-grade and deeply integrated, which is critical as 
customers start putting more sensitive data and AI workloads into production. 
Finally, Azure benefits from the broader Microsoft ecosystem. Integration with tools people 
already use every day — like Microsoft 365 and Power BI — drives adoption and makes 
insights more actionable across the business.

## Page 117

Overall, Azure differentiates itself by combining enterprise trust, hybrid flexibility, and a cohesive 
data-to-AI platform that helps customers modernize responsibly and at scale. 
 
 
●​ How did you discuss the value of the solution, including ROI and TCO?  
●​ What was your solution’s value proposition in comparison to other competitor solutions? 
 
When discussing value, I always start by anchoring the conversation on the 
customer’s business goals rather than the technology itself. In this case, the 
primary objectives were faster time to insight, scalability for future analytics and AI 
use cases, and reducing the operational overhead of managing fragmented data 
systems. 
From an ROI perspective, we focused on both hard and soft returns. On the hard 
side, we quantified cost savings from consolidating legacy systems, reducing 
infrastructure and licensing spend, and lowering operational effort through managed 
services and automation. On the soft side, we highlighted faster delivery of 
analytics, improved data trust, and the ability for teams to self-serve insights — 
which directly impacted decision-making speed and productivity. 
For TCO, we looked beyond just compute costs. We evaluated total 
ownership across infrastructure, operations, maintenance, and future 
scalability. The proposed architecture reduced long-term costs by simplifying the 
platform, minimizing manual data pipelines, and allowing the customer to scale 
usage up or down based on demand rather than over-provisioning. 
When comparing against alternative solutions, our value proposition was flexibility 
and future readiness. Competing options either locked the customer into a more 
rigid architecture or required significant custom engineering to support analytics and 
AI at scale. Our solution provided an open, scalable data foundation that could 
evolve as the customer’s needs grew — without a major re-architecture. 
Ultimately, the decision came down to balancing cost, risk, and long-term value. 
The customer chose our approach because it delivered near-term ROI while also 
positioning them for future innovation, particularly around advanced analytics and 
AI.

## Page 118

AWS Data Engineering

## Page 119

AWS Data Engineering 
 has 4 levels to it: 
 
– Level 1: Ingesting & Storing Data 
Start by learning the foundations of AWS data services: 
- S3 for data lakes (folders, prefixes, lifecycle policies) 
- AWS Glue Crawlers + Data Catalog for schema discovery 
- Kinesis / AWS DMS for streaming + CDC ingestion 
- IAM basics (roles, policies, S3 bucket access) 
 
With just these basics, you can already build working ETL pipelines. 
 
– Level 2: Transforming & Querying Data 
Move from storing data to making it usable: 
 
- Glue ETL & PySpark jobs (batch transformation) 
- AWS Lambda for lightweight event-driven processing 
- Athena + S3 for serverless SQL on data lakes 
- Redshift for warehousing and complex analytics 
 
This is where your data becomes queryable and structured for analytics 
 
– Level 3: Building Scalable Data Platforms 
Upgrade from pipelines to full data platforms: 
 
- Lakehouse architecture with Iceberg/Delta on S3 
- Glue Workflow/Step Functions for orchestration 
- Data partitioning, file formats (Parquet, ORC, Avro) 
- Performance tuning (compaction, distribution keys, sort keys) 
 
Here’s where you shift from “data exists” to “data is optimized and reliable.” 
 
– Level 4: Operating at Scale 
Finally, learn to make your platforms efficient, secure, and enterprise-ready: 
 
- EMR + Spark clusters for high-volume processing 
- Data quality + observability (Great Expectations, Deequ, CloudWatch) 
- Cost optimization (S3 tiers, Redshift RA3, Glue job tuning) 
- Security & compliance (KMS encryption, VPC endpoints, Lake Formation, GDPR/SOC2) 
- Streaming at scale with Kinesis Data Streams / Firehose / MSK

## Page 120

ML

## Page 121

1. Explain the ML lifecycle on Databricks in under 60 
seconds. 
30-sec answer:​
 “On Databricks the ML lifecycle is unified across data, 
features, training, and deployment.​
 We ingest raw data into Delta Lake so it’s versioned and 
reproducible.​
 Feature engineering happens in notebooks, pipelines, 
or Delta Live Tables and those features are stored in 
the Feature Store.​
 MLflow tracks experiments, models, and parameters.​
 When a model is ready, it goes into the Model Registry 
where we manage staging → production promotion with 
CI/CD.​
 Finally, we serve it through Model Serving or batch jobs, 
and use Unity Catalog & monitoring to track drift, quality, 
and lineage end-to-end.” 
 
3. How would you scale training on TBs of data? 
30-sec answer:​
 “I use Databricks’ distributed compute — Spark for data 
prep, and MLflow + distributed training libraries like 
Horovod or PyTorch DDP for model training.​

## Page 122

Because the data lives in Delta Lake, we can optimize 
with partitioning, Z-Ordering, and caching, then run 
parallel hyperparameter tuning with Spark-based trials.​
 So instead of trying to train on one machine, the workload 
scales horizontally across the cluster.” 
 
4. Batch scoring vs online scoring — when and how? 
30-sec answer:​
 “Batch scoring is best when predictions are needed 
periodically at scale — like nightly risk scores.​
 It runs as a scheduled job reading from Delta Lake and 
writing predictions back.​
 Online scoring is for low-latency use cases like 
recommendations or fraud.​
 Databricks Model Serving exposes the model as a REST 
endpoint with auto-scaling.​
 Both use the same model in MLflow Registry to keep 
governance consistent.” 
 
5. How does MLflow help enterprise ML teams? 
30-sec answer:​
 “MLflow standardizes experiments, model packaging, and 
lifecycle governance.​

## Page 123

Teams can track metrics, compare runs, reproduce 
results, and version models in the Registry.​
 It becomes the central nervous system for ML because 
data scientists, engineers, and SREs all operate from the 
same model registry and lineage — which avoids shadow 
models, manual handoffs, and deployment 
inconsistencies.” 
 
6. Explain point-in-time correctness in the Feature 
Store. 
30-sec answer:​
 “It means features are computed using only the data that 
was available at that exact timestamp.​
 When you build a training set, the Feature Store performs 
a time-aware join so future information cannot leak into the 
model.​
 This solves one of the biggest problems in enterprise ML 
— reproducible, leakage-free datasets.” 
 
7. How do you evaluate a RAG pipeline? 
30-sec answer:​
 “I evaluate RAG on three levels:

## Page 124

1.​Retrieval metrics: precision@k, recall@k, coverage.​
 
2.​Generation metrics: faithfulness, hallucination rate, 
groundedness.​
 
3.​System metrics: latency, cost, token usage.​
 On Databricks, Lakehouse Monitoring tracks these 
automatically and logs them to MLflow so teams can 
compare versions and detect drift.”​
 
 
8. When should a customer NOT use deep learning? 
30-sec answer:​
 “When the dataset is small, tabular, or when 
interpretability is more important than raw accuracy.​
 Tree-based models like XGBoost often outperform deep 
learning on structured data with less cost and complexity.​
 Deep learning makes sense for unstructured modalities or 
when scale gives a real advantage — otherwise, it’s 
overkill.” 
 
9. How do you handle schema drift in ML pipelines?

## Page 125

30-sec answer:​
 “I design pipelines to be schema-aware.​
 Delta Lake’s schema evolution and expectations can 
validate incoming data.​
 Feature engineering code should be defensive — missing 
columns default to null or fallback logic.​
 We track schema versions in MLflow so when a new 
schema appears, we retrain or branch the model.​
 This avoids silent degradation.” 
 
10. How do you operationalize a model with CI/CD? 
30-sec answer:​
 “Code, features, and models all live in Unity Catalog.​
 A Git-triggered workflow runs tests, builds features, trains 
the model, and registers it in MLflow.​
 Promotion from Staging → Production is gated through 
approval or automated tests.​
 Production models are served through Model Serving or 
batch jobs, and monitored for drift using Lakehouse 
Monitoring.” 
 
11. Explain difference between feature engineering at 
inference vs training.

## Page 126

30-sec answer:​
 “At training time you compute features over historical 
data — often aggregated or windowed.​
 At inference time you only use data available right 
now.​
 The Feature Store ensures both use the same code path 
so features stay consistent.​
 If these diverge even slightly, you get poor real-world 
accuracy.” 
 
12. What would you do if a model’s performance 
dropped unexpectedly? 
30-sec answer:​
 “First check data drift, schema changes, or missing 
features — those cause most drops.​
 Then compare current inference features with training 
features using MLflow logs.​
 Next check model drift using statistical monitoring.​
 If the issue is real, we retrain using the latest Delta 
snapshots and promote a new version through the 
Registry.”

## Page 127

✅ Part 2 — A full mock customer scenario where you 
design an ML platform end-to-end 
Here’s a polished, interview-ready scenario that makes 
you sound like a strong Databricks SA. 
 
⭐ Mock Customer Scenario (Databricks SA Case 
Study) 
Customer: 
RetailCo, a global retail chain with 2,000 stores. 
Goal: 
They want to build a real-time recommendation and 
forecasting platform to improve: 
●​product recommendations​
 
●​demand forecasting​
 
●​store workforce planning​
 
●​supply-chain optimization​
 
Their pain points:

## Page 128

●​Data is split across Snowflake, S3, and on-prem SQL 
Server​
 
●​DS teams manually build training datasets → no 
reproducibility​
 
●​Production ML is ad-hoc: notebooks emailed around, 
no CI/CD​
 
●​They want to explore GenAI for store-manager Q&A​
 
 
⭐ Your Proposed Architecture (End-to-End) 
1. Data Ingestion & Storage 
●​Ingest structured & unstructured data using Auto 
Loader into Delta Lake on Databricks.​
 
●​Use DLT (Delta Live Tables) for quality checks, 
expectations, and schema inference.​
 
●​All data is governed through Unity Catalog.​
 
2. Feature Engineering & Feature Store

## Page 129

●​Build reusable features:​
 
○​customer embeddings​
 
○​RFM metrics​
 
○​transaction sequences​
 
○​store-level aggregations​
 
●​Store all features in the Databricks Feature Store.​
 
○​ensures point-in-time correctness​
 
○​eliminates leakage​
 
○​shared across DS teams​
 
3. Model Training 
●​Use MLflow to track all experiments.​
 
●​Distributed training using:​
 
○​XGBoost for forecasting​

## Page 130

○​Deep Learning (PyTorch Lightning) for 
recommendations​
 
●​Hyperopt or SparkTrials for scalable hyperparameter 
tuning.​
 
●​Save the best model to the MLflow Model Registry.​
 
4. Deployment 
Two paths: 
Batch Scoring 
●​Nightly forecasts written back into Delta.​
 
●​BI tools (Tableau/PowerBI) read from Delta for 
dashboards.​
 
Real-Time Serving 
●​Deploy recommendation model via Databricks Model 
Serving.​
 
●​Low-latency endpoints backed by autoscaling 
clusters.​

## Page 131

5. Monitoring & Governance 
●​Use Lakehouse Monitoring for:​
 
○​data drift​
 
○​model drift​
 
○​feature skew​
 
○​latency & cost metrics​
 
●​Alerts back to Slack or PagerDuty.​
 
6. GenAI Add-On (Execs love this) 
RetailCo wants a store-manager assistant that answers 
questions like:​
 “Why is forecast down for Store #812?” 
Proposed RAG pipeline: 
●​Documents stored in Delta (PDFs, SOPs, plans)​
 
●​Chunk → embed → store embeddings in Databricks 
Vector Search​

## Page 132

●​Use DBRX or Llama-3 fine-tuned using Mosaic AI​
 
●​Serve through Model Serving with built-in monitoring​
 
●​Track hallucination rate + groundedness with MLflow​
 
 
⭐ 30-Second Summary You Could Say in the 
Interview 
“We unified RetailCo’s ML lifecycle on Databricks.​
 All raw data lands in Delta Lake through Auto Loader.​
 We built reusable features in the Feature Store with 
point-in-time correctness, then trained models for 
forecasting and recommendations with MLflow.​
 The models move through Model Registry into batch 
pipelines or real-time Model Serving.​
 Everything — data, features, models, lineage — sits 
under Unity Catalog so governance is automatic.​
 We added a RAG assistant using Vector Search + DBRX 
so store managers get contextual answers.​
 This gives RetailCo an end-to-end, governed, scalable 
ML platform.” 
 
If you want, I can also prep:

## Page 133

✅ 30-second “Why Databricks for ML?” pitch​
 ✅ 10 deep-dive questions you should ask them​
 ✅ A second mock scenario for a healthcare or financial 
customer​
 ✅ A version of the answers in your storytelling / 
conversational style

## Page 134

Phrases to use

## Page 135

Phrases to use 
 
1.​  Delta’s versioning also guarantees reproducibility so 
we can rebuild the exact training dataset if needed.” 
2.​  Databricks Model Serving exposes the model as a 
REST endpoint with auto-scaling. 
3.​DS teams manually build training datasets → no 
reproducibility 
4.​ Everything — data, features, models, lineage — sits 
under Unity Catalog so governance is automatic. 
5.​ Data is split across Snowflake, S3, and on-prem SQL 
Server 
6.​