# AWS Solutions Architect — AI Technical Round Prep

**Candidate:** Madhurima Saxena  
**Focus:** AI / GenAI / Agentic AI technical round  
**De-emphasized:** Core data engineering topics, since that is already a strength  
**Prep window:** 2–3 days

---

## 1. Goal for the Technical Round

The goal is **not** to memorize every AWS AI service.

The goal is to show that I can:

1. **Design and explain production GenAI systems**
2. **Go deep on RAG, retrieval, evaluation, latency, cost, and reliability**
3. **Connect my real GE Vernova experience to AWS-native patterns**
4. **Reason about agents and autonomous systems**
5. **Discuss Amazon Bedrock confidently**
6. **Show informed architectural knowledge of AgentCore without pretending hands-on experience**
7. **Modernize legacy systems into AI / agentic architectures**
8. **Operate like a Senior Solutions Architect: trade-offs, customer constraints, phased adoption, reliability, security, and business impact**

---

# 2. How to Position My AI Experience

My strongest hands-on AI experience is the **GE Vernova Service Demand Generation program**.

I should position it as a production AI / RAG / agentic architecture, not merely as a PDF ingestion project.

### Current architecture includes

- Large-scale unstructured document ingestion
- Field Service Reports and Engineering Review evidence
- Databricks Delta Lake
- Metadata extraction and enrichment
- Chunking and embeddings
- Vector Search
- Hybrid retrieval
- ESN-scoped metadata filtering
- Structured-data tools
- Unstructured retrieval tools
- LangGraph orchestration
- AWS ECS Fargate application layer
- LiteLLM Enterprise Proxy
- Multi-tool assistants / agents
- MLflow-based retrieval evaluation
- Production retry, resiliency, DQ, lineage, and backfill patterns

### Main message

> I have built and operated production GenAI systems. My strongest hands-on experience is with custom RAG and agentic architectures using LangGraph, Databricks, AWS infrastructure, and LiteLLM. I have not implemented every AWS managed AI service directly, but I understand how to map the architectural problems I have solved to AWS-native services and can reason through the trade-offs.

---

# 3. AgentCore — How to Position It

I **have not implemented AgentCore in production**.

That is okay.

Do not pretend otherwise.

### Preferred positioning

> I haven't implemented AgentCore in production yet. My hands-on agent experience has been with a LangGraph-based orchestration layer running on ECS, where the agent calls separate retrieval and structured-data tools.
>
> I have been studying AgentCore because the problems it addresses are very relevant to what we had to solve ourselves: agent runtime, secure tool access, identity, memory, observability, and production lifecycle.
>
> So I wouldn't claim implementation experience with AgentCore, but I can talk through where I would evaluate using it versus continuing with a custom LangGraph/ECS architecture, and what parts of our current design I would potentially move to managed AgentCore capabilities.

### Key distinction

**Agents ≠ AgentCore**

I can credibly say:

> I have built agentic systems. I have not yet built one specifically using AgentCore.

Do **not** say:

> I don't have agent experience.

---

# 4. Preparation Priorities

## Priority 1 — Must Be Strong

These areas should take approximately **70–75% of prep time**.

| Priority | Topic | Expected Depth |
|---|---|---|
| 1 | GE Vernova AI architecture | Very deep |
| 2 | RAG, retrieval, and evaluation | Very deep |
| 3 | Amazon Bedrock | Strong |
| 4 | Tokens, latency, p95/p99, throughput, cost, throttling | Strong |
| 5 | Agents / autonomous agents | Strong concepts + hands-on mapping |
| 6 | Legacy → GenAI / agentic transformation architecture | Strong |

## Priority 2 — Know Enough to Discuss Intelligently

| Priority | Topic | Expected Depth |
|---|---|---|
| 7 | Amazon Bedrock AgentCore | Conversational / architecture-level |
| 8 | ML / Data Science lifecycle | High-level |

## Priority 3 — Only If Time Remains

- Fine-tuning internals
- LoRA
- RLHF
- Transformer internals
- GPU architecture
- Deep HNSW tuning
- GraphRAG
- Multi-agent theory beyond core patterns
- Advanced SageMaker training details
- Quantization
- Speculative decoding
- KV-cache internals

---

# 5. Day 1 — Core Architecture + RAG + Bedrock

## Topic A — My GE Vernova AI Architecture

I should be able to whiteboard this from memory.

### Questions to prepare

1. Walk me through the GE Vernova AI architecture end to end.
2. Where does the agent/orchestrator live?
3. Why did you use LangGraph?
4. Why ECS Fargate?
5. Why Databricks Vector Search?
6. Why use separate structured and unstructured tools?
7. Why is retrieval filtered by ESN before vector similarity?
8. Why hybrid retrieval?
9. Why use LiteLLM as a gateway?
10. Where does application state live?
11. What happens when a retrieval tool fails?
12. What is the biggest AI quality risk in the architecture?
13. What is the biggest availability risk?
14. What is the biggest cost driver?
15. What would you redesign today?

### Whiteboard target

Be able to draw:

```text
User
  ↓
Application / API
  ↓
LangGraph Orchestrator / Agent
  ↓
Tools
  ├── FSR Retrieval
  ├── ER Retrieval
  ├── IBAT
  ├── PRISM
  ├── Risk Matrix
  └── Event / structured data tools
  ↓
Databricks + Vector Search / Delta
  ↓
LiteLLM / Foundation Models
  ↓
Grounded response / risk evaluation / narrative
```

---

## Topic B — RAG Architecture

### Core mental model

```text
ingest
→ parse
→ extract metadata
→ chunk
→ embed
→ index
→ retrieve
→ rerank / assemble context
→ generate
→ cite / evaluate
```

### Questions to prepare

1. Walk me through a production RAG architecture.
2. Why RAG instead of putting all documents into the model context?
3. How do you choose chunk size?
4. What is chunk overlap?
5. What is structure-aware chunking?
6. What is parent-child chunking?
7. What is an embedding?
8. Why does changing an embedding model require re-embedding?
9. What is dense retrieval?
10. What is BM25?
11. What is hybrid retrieval?
12. What is metadata pre-filtering?
13. Why can metadata filtering matter more than semantic similarity?
14. What is top-K?
15. What happens when top-K is too small?
16. What happens when top-K is too large?
17. What is reranking?
18. How do you distinguish a retrieval failure from a generation failure?
19. What is context dilution?
20. How do you handle stale vectors or changed documents?
21. How do you support provenance and citations?

### GE anchors

Use these examples when appropriate:

- ESN-scoped retrieval
- Hybrid dense + lexical retrieval
- Metadata filtering before semantic retrieval
- Evidence-level attribution
- Multi-equipment / multi-ESN reports
- Region-first / structure-aware chunking thinking
- Retrieval misses that could not be fixed by prompt engineering

---

## Topic C — Amazon Bedrock

### Questions to prepare

1. What is Amazon Bedrock?
2. Why would a customer use Bedrock instead of hosting models themselves?
3. How would you choose among models in Bedrock?
4. What factors drive model selection?
5. When would you use a smaller model versus a flagship model?
6. What are Bedrock Guardrails?
7. What are Bedrock Knowledge Bases?
8. When would you use Bedrock Knowledge Bases versus custom RAG?
9. How would you architect model portability?
10. What is streaming inference?
11. What happens when Bedrock throttles requests?
12. How would you implement model fallback?
13. How would you control GenAI cost?
14. How would you monitor usage by application or customer?
15. How would you evaluate a new model before switching production traffic?

### What I need to know, but not memorize deeply

- Bedrock model access / inference
- Model selection trade-offs
- Guardrails
- Knowledge Bases
- Streaming
- Quotas
- Cross-region inference
- Prompt caching
- Model routing / fallback concepts

---

# 6. Day 2 — Production AI + Agents + Evaluation

## Topic D — Latency, Throughput, Tokens, Cost

This was specifically mentioned by the AWS contact.

### Percentiles to know

- **p50** — median
- **p95**
- **p99**

Focus on these rather than unusual percentiles such as p55 unless specifically asked.

### Questions to prepare

1. What is p50 latency?
2. What is p95 latency?
3. What is p99 latency?
4. Why is average latency insufficient?
5. Why can p99 degrade while p50 remains healthy?
6. What contributes to end-to-end GenAI latency?
7. How would you decompose latency across retrieval, agent, model, and tool calls?
8. What is time-to-first-token?
9. What is tokens-per-second?
10. How does larger retrieved context affect latency?
11. How does output length affect latency?
12. How do agent tool calls affect total latency?
13. How would you troubleshoot a sudden p99 latency spike?
14. What can be cached?
15. How do you trade quality against latency?
16. What should happen if the preferred model is too slow or unavailable?

---

## Topic E — Token Count / Quotas / Burndown

The AWS person specifically mentioned **burndown**.

Prepare the concept in the context of model token quotas, not project management.

### Questions to prepare

1. What is a token?
2. What is the difference between input and output tokens?
3. Why does token count matter for cost?
4. Why does token count matter for latency?
5. Why does token count matter for concurrency and quotas?
6. What is TPM?
7. What is token burndown?
8. Why might an output token consume more quota than one nominal token?
9. Why is quota consumption not necessarily identical to billing?
10. How would you diagnose unexpected throttling?
11. How would you estimate tokens per transaction?
12. How does an agentic workflow change token usage compared with one LLM call?
13. How would you prevent runaway token consumption?
14. What token metrics should be monitored per request / agent run?

---

## Topic F — Agents and Autonomous Agents

I should be strong on **agent architecture**, because my GE experience is relevant.

### Questions to prepare

1. What is an AI agent?
2. How is an agent different from a chatbot?
3. What makes an agent autonomous?
4. What is the basic agent loop?
5. What are reasoning, planning, tools, memory, state, and orchestration?
6. What is ReAct?
7. What is tool calling?
8. When should you use an agent instead of a deterministic workflow?
9. When should you not use an agent?
10. What is a single-agent architecture?
11. When would you consider multiple agents?
12. How do you prevent an agent from taking destructive actions?
13. Where should human approval exist?
14. How do you make tool calls idempotent?
15. How do you handle long-running agent tasks?
16. How do you preserve state?
17. What is short-term versus long-term memory?
18. How do you stop an agent from looping indefinitely?
19. How do you evaluate whether an agent successfully completed a task?
20. What happens when a tool fails?

### GE mapping

Connect these concepts to:

- LangGraph orchestration
- Multiple REST-based tools
- Risk evaluation chain
- Q&A agent
- Structured + unstructured information
- State persisted outside the model
- Tool failure handling
- Evidence grounding

---

## Topic G — RAG / GenAI Evaluation

This is one of my strongest differentiators.

### Questions to prepare

1. How do you know whether a RAG system is good?
2. What does recall@K measure?
3. What does precision@K measure?
4. What is MRR?
5. What is hit rate?
6. What is groundedness / faithfulness?
7. What is answer relevance?
8. How do retrieval metrics differ from generation metrics?
9. What is a golden dataset?
10. How do you create one when SMEs are scarce?
11. What is LLM-as-a-judge?
12. What are its limitations?
13. How do you prevent a prompt/model/chunking change from silently degrading quality?
14. What should block deployment?
15. How do offline evaluation and production feedback differ?
16. How would you use MLflow for AI evaluation?
17. How would you A/B test top-K?
18. How would you compare embedding models?
19. Why is retrieving the correct document not sufficient?
20. How would you evaluate evidence-level correctness?

### GE anchors

- Fixed probe sets
- MLflow experiments
- top-K comparisons
- retrieved-vs-known document coverage
- evidence-level inspection
- document recall can look good while actual evidence is wrong
- regression cases
- retrieval evaluation separate from end-to-end generation evaluation

---

# 7. Day 3 — AWS Mapping + System Design

If only 2 days are available, cover this section at a higher level.

## Topic H — AgentCore

### Required depth

Know what problems AgentCore is intended to solve.

Do not memorize APIs.

### Areas to understand

- Agent runtime
- Tool / API access
- Gateway
- Identity
- Memory
- Observability
- Production lifecycle
- How it compares to custom LangGraph + ECS

### Questions to prepare

1. What problem does AgentCore solve?
2. Why would I consider AgentCore instead of running LangGraph directly on ECS?
3. What is AgentCore Runtime?
4. What role does AgentCore Gateway play?
5. How can existing enterprise APIs become agent tools?
6. How does identity flow from users to downstream tools?
7. What problem does AgentCore Memory solve?
8. What belongs in agent memory versus an application database?
9. How do you monitor an AgentCore-based system?
10. How would I evaluate AgentCore for GE?
11. What parts of the current GE architecture would likely stay?
12. What parts might move to AgentCore?

### Important interview behavior

If I do not know a product-specific detail:

> I haven't implemented that capability directly, so I don't want to guess at the exact service behavior. Architecturally, the way I would think about the problem is...

Then reason from first principles and real experience.

---

## Topic I — LiteLLM / Model Gateway

LiteLLM is real hands-on experience and can be a strong differentiator.

### Questions to prepare

1. What problem does LiteLLM solve?
2. Why use an AI gateway?
3. Why not allow every application to call model providers directly?
4. How do you route between multiple models?
5. How do you implement fallback?
6. Where do retries belong?
7. Where should rate limiting happen?
8. How should authentication work?
9. How do you track tokens and cost per application?
10. How do you enforce which models an application can use?
11. What should not be logged?
12. Does the gateway become a single point of failure?
13. How would you make it highly available?
14. When would you use Bedrock directly instead?
15. How would you preserve model portability while increasing use of AWS-native services?

---

## Topic J — Legacy System → Agentic Architecture

This is likely to be an important Senior SA design area.

### Questions to prepare

1. A customer has a 20-year-old legacy system. How do you decide where GenAI should be introduced?
2. What would you migrate first?
3. What would you leave untouched initially?
4. Would you rewrite, refactor, replatform, or wrap the existing system?
5. How do you safely expose legacy capabilities as agent tools?
6. Would you let an agent query a production database directly?
7. How do you turn existing business logic into APIs/tools?
8. What if the legacy application has no APIs?
9. How would you bring decades of legacy documents into a RAG architecture?
10. How do you preserve identity and authorization?
11. How would you phase the migration?
12. How would you run legacy and AI systems side-by-side?
13. What does rollback look like?
14. What metrics would prove the modernization succeeded?
15. How do you prevent the agentic layer from becoming tightly coupled to the legacy platform?

### Whiteboard problem to practice

> A Fortune 100 industrial customer has a 20-year-old maintenance platform containing relational databases, PDFs, business rules, and manually executed workflows. Design a phased migration to an AI / agentic architecture on AWS without disrupting current operations.

---

# 8. ML / Data Science Lifecycle — High-Level Only

I do not need Data Scientist-level depth.

### Questions to prepare

1. Walk me through the lifecycle of a machine learning model.
2. What is the difference between training and inference?
3. What are train, validation, and test datasets?
4. What is feature engineering?
5. What is model evaluation?
6. What is overfitting?
7. What is data drift?
8. What is concept drift?
9. What is model drift?
10. What is a model registry?
11. What triggers retraining?
12. How do you promote a model into production?
13. What is shadow deployment?
14. What is canary deployment?
15. How do you roll back a model?
16. How does traditional ML lifecycle differ from a GenAI application lifecycle?
17. Where does MLflow fit?
18. What needs versioning in GenAI: model, prompt, embedding model, chunker, data, eval set?
19. What would an AI CI/CD pipeline look like?
20. What metrics should block production promotion?

---

# 9. Production Reliability / Observability

Use my actual production experience wherever possible.

### Questions to prepare

1. What should you monitor in a production GenAI system?
2. What should an AI trace contain?
3. How do you distinguish model errors from application errors?
4. What happens when model inference times out?
5. How should retries work?
6. When should you not retry?
7. How do you handle HTTP 429 / throttling?
8. What is exponential backoff?
9. What is a circuit breaker?
10. When would you fall back to another model?
11. What happens if retrieval is unavailable?
12. What happens if one agent tool fails?
13. How do you avoid duplicate actions during retries?
14. How do you monitor cost per successful task?
15. How do you detect AI quality regression?
16. What are the most important production SLOs for an AI application?

### GE examples

- Bounded retry
- Terminal failures / quarantine
- Idempotent MERGE
- Claim-based processing
- Stale-claim recovery
- DQ validation
- Run logs
- Backfill restartability
- Failure isolation
- Vector index synchronization issues

---

# 10. AI Security — High-Level but Important

### Questions to prepare

1. What is prompt injection?
2. What is indirect prompt injection?
3. How can malicious instructions enter through RAG documents?
4. How do you restrict which tools an agent can call?
5. How do you enforce least privilege?
6. How do you isolate customer data?
7. How do you prevent cross-user retrieval?
8. What is authentication versus authorization in agent systems?
9. How should user identity propagate to tools?
10. What should and should not be logged?
11. How do you handle PII?
12. What role do Bedrock Guardrails play?
13. Are guardrails alone enough?
14. Which actions should require human approval?
15. How would you audit autonomous-agent actions?

---

# 11. The Five Questions That Matter Most

If I can answer these deeply, most of the smaller questions become branches of the same mental model.

## 1. Design a production enterprise RAG solution on AWS.

Need to cover:

- ingestion
- parsing
- metadata
- chunking
- embeddings
- vector index
- retrieval
- model invocation
- security
- observability
- evaluation
- scaling
- latency
- cost

---

## 2. Design an autonomous enterprise agent and make it safe and operable.

Need to cover:

- agent vs workflow
- tools
- planning
- state
- memory
- identity
- authorization
- guardrails
- human approval
- retries
- observability
- cost
- evaluation

---

## 3. Migrate a legacy enterprise application to an agentic architecture.

Need to cover:

- discovery
- phased migration
- API/tool wrappers
- data and documents
- coexistence
- authorization
- rollback
- managed vs custom services
- success metrics

---

## 4. p99 latency and token consumption suddenly spike. Diagnose it.

Need to cover:

- retrieval latency
- tool latency
- model inference
- context length
- output length
- agent steps
- throttling
- token quotas / burndown
- caching
- model routing
- fallback
- observability

---

## 5. Redesign GE Vernova using Bedrock / AgentCore.

Need to cover:

### What stays

- customer workflow
- domain tools
- retrieval requirements
- structured-data services
- metadata / provenance
- evaluation framework
- existing high-quality enterprise data

### What I would evaluate changing

- model invocation → Bedrock
- agent runtime → AgentCore
- tool exposure → AgentCore Gateway
- identity → AWS-managed agent identity patterns
- memory → AgentCore Memory where appropriate
- observability → AWS-native agent traces/metrics
- model governance / Guardrails
- model routing / fallback

Most important:

> Do not redesign merely to use AWS services. Explain why each managed component improves security, operability, scalability, time-to-value, or total cost.

---

# 12. Suggested 2-Day Schedule

## Day 1

### Morning
- GE architecture
- RAG architecture
- retrieval
- chunking
- embeddings
- hybrid search
- top-K

### Afternoon
- Bedrock
- model selection
- tokens
- token burndown
- p50 / p95 / p99
- latency
- cost
- throttling

### End of Day
Whiteboard twice:

1. GE current architecture
2. Generic enterprise RAG on AWS

---

## Day 2

### Morning
- agents
- autonomous agents
- tool use
- state / memory
- evaluation
- MLflow

### Afternoon
- AgentCore high level
- LiteLLM gateway
- legacy modernization
- security
- reliability / observability

### End of Day
Whiteboard twice:

1. Legacy → agentic modernization
2. GE redesign using Bedrock / AgentCore

---

# 13. Optional Day 3

Use Day 3 for **depth, not new breadth**.

### Morning

Deep dives on weak areas from Days 1–2.

Examples:

- token quotas / burndown
- Bedrock architecture
- AgentCore
- autonomous agent failure modes
- p99 diagnosis

### Afternoon

Mock technical interviews.

Practice answering questions in this order:

1. **High-level architecture**
2. **Assumptions**
3. **Key architectural decisions**
4. **Trade-offs**
5. **Failure modes**
6. **Security**
7. **Scale**
8. **Latency**
9. **Cost**
10. **What I would measure**

---

# 14. How Deep Should I Answer?

Use three levels.

## Level 1 — 30 seconds

Explain what the thing is.

## Level 2 — 90 seconds

Explain:

- what it does
- why it matters
- one trade-off
- one example

## Level 3 — Deep dive

If the interviewer probes:

- implementation
- failure modes
- alternatives
- performance
- security
- scale
- cost
- what I personally did

This prevents me from dumping five minutes of detail before knowing what the interviewer wants.

---

# 15. Rules for the Technical Round

### Rule 1

Lead with the architecture/problem, not with AWS service names.

### Rule 2

Explain **why**, not merely **what**.

Instead of:

> We used Vector Search.

Say:

> We first narrowed the candidate corpus using equipment metadata, then used hybrid retrieval within that equipment scope because pure semantic similarity could retrieve semantically related evidence from the wrong machine.

### Rule 3

Say what **I personally did**.

### Rule 4

Separate what is implemented from what I would recommend.

Use:

> In our current architecture we...

versus:

> If I were redesigning this on AWS today, I would evaluate...

### Rule 5

Do not fake AWS product experience.

Use:

> I haven't implemented that specific managed service yet, but I have solved the underlying architectural problem. Here is how I would compare the approaches...

### Rule 6

Always mention trade-offs.

Examples:

- managed vs custom
- precision vs recall
- quality vs latency
- quality vs cost
- autonomy vs control
- flexibility vs operational simplicity
- centralized gateway vs direct access
- large model vs small model

### Rule 7

For every architecture, be ready to discuss:

- Scale
- Availability
- Security
- Latency
- Cost
- Observability
- Evaluation
- Failure modes

---

# 16. Final Readiness Checklist

Before the interview, I should be able to do all of these without notes.

- [ ] Draw GE architecture in <5 minutes
- [ ] Explain a RAG pipeline end to end
- [ ] Explain retrieval failure vs generation failure
- [ ] Explain hybrid retrieval
- [ ] Explain metadata pre-filtering
- [ ] Explain top-K trade-offs
- [ ] Explain my MLflow retrieval evaluation
- [ ] Explain p50 / p95 / p99
- [ ] Break down GenAI latency
- [ ] Explain input/output token cost
- [ ] Explain token quotas / burndown concept
- [ ] Explain Bedrock at architecture level
- [ ] Explain when I would use managed Bedrock KB vs custom RAG
- [ ] Explain what makes a system agentic
- [ ] Explain agent vs deterministic workflow
- [ ] Explain autonomous-agent safety
- [ ] Explain my real LangGraph agent experience
- [ ] Explain AgentCore honestly without claiming hands-on experience
- [ ] Explain LiteLLM's role
- [ ] Design legacy → agentic modernization
- [ ] Discuss retries / throttling / fallback
- [ ] Discuss security / prompt injection / least privilege
- [ ] Explain ML lifecycle at high level
- [ ] Explain what I would redesign in GE using AWS-native AI services
