# AI Solutions Architect — Learning Plan

Goal: be sharp for interviews and able to talk through the FSR architecture confidently. **Time‑boxed**, not exhaustive. Some things are just *read enough to talk about*; others are *do it once so I actually know*; a few are *practice saying out loud*.

> **Cert prep is now priority #1** (Databricks GenAI Engineer Associate, May 23, 2026). For exam‑shaped material (precise product names, defaults, scenarios), see [cert-prep.md](cert-prep.md). This learning plan stays focused on interview shape (trade‑offs, stories, depth).

> Use the FSR pipeline (`pw_sdg_ai_ser_repo`) and prod‑ops (`fsr-prod-ops/`) as the running example wherever it fits. For things FSR doesn't cover (agents, multi‑tenant, fine‑tuning, advanced eval), read enough to discuss — don't try to build them.

> **Vocabulary scope (for now): Databricks + AWS.** That's where my work lives, and most of my interviews will too. Each section below calls out the right *Databricks* and *AWS* terms to use. Anthropic / OpenAI / GCP vocabulary is parked in §13 below as a forward‑looking add‑on once the core is solid — don't try to boil the ocean.

## Time budget

Target: **~2 days focused, spread across a week is fine.**

| Bucket | Effort | What it produces |
| --- | --- | --- |
| **Read** | ~30% | Mental model, vocabulary, trade‑offs to mention |
| **Do** (hands‑on POC) | ~50% | Real intuition + aha‑moments + demo material |
| **Say** (mock answers / whiteboard) | ~20% | Smooth delivery in the actual interview |

How to read each topic below:
- **R** = read / skim, take a few notes
- **D** = do it hands‑on (in the POC notebook)
- **S** = practice saying it out loud (1–2 min answer)
- **FSR** = anchor with our FSR experience

---

## 1. LLM basics — just enough to sound fluent  ·  R + S

Don't go deep into transformers. Just be comfortable with:

- Tokens, context window, temperature, top‑p, stop sequences (one paragraph each).
- Difference between **prompting**, **fine‑tuning**, and **RAG** — and *when you'd pick each*. This is the question that actually gets asked.
- Structured output: JSON mode / function calling — why it matters for pipelines.
- Cost & latency intuition: input vs. output tokens, big vs. small models.

**Vocabulary to use (Databricks + AWS for now):**

- **Foundation Model / FM** — generic term for hosted base LLMs. Use it instead of "GPT" in mixed audiences.
- **Databricks**: *Foundation Model APIs*, *Mosaic AI Model Serving*, *AI Functions* (`ai_query`, `ai_extract`, `ai_classify`), *external models*, *DBRX* (their own FM).
- **AWS**: *Amazon Bedrock* (managed FM access), *Bedrock model providers* (Anthropic Claude, Meta Llama, Amazon Titan, Cohere), *SageMaker JumpStart* (self‑hosted FMs), *Bedrock Guardrails*, *Bedrock Knowledge Bases* (managed RAG).
- **Inference parameters**: *max output tokens*, *temperature*, *top‑p*, *stop sequences*.
- **Output shaping**: *system prompt*, *tool / function calling*, *JSON mode*, *structured output*.

> Hook for later: add Anthropic (Claude family, prompt caching, tool use) and OpenAI (GPT‑4‑class, Assistants API, JSON schema mode) once Databricks/AWS are solid.

**Say it (S):** "When would you fine‑tune vs. RAG vs. just prompt?" — 90‑second answer.

> Skip: math of attention, training loss curves, RLHF internals. Not interview‑critical for an architect role.

---

## 2. RAG — the one diagram I must own  ·  R + S + FSR

- The canonical pipeline: `ingest → parse → chunk → embed → index → retrieve → (re‑rank) → generate`.
- **Metadata extraction** runs as a side‑channel alongside parse/chunk and rides with each chunk through index → retrieve (used as filters and citations). Not a separate stage in the line, but always present in the picture. See §7.
- Map our FSR bronze/silver/gold onto it.
- Top failure modes and how to spot them (bad chunks, stale index, missing metadata, hallucination).

**Vocabulary:**

- **RAG** = *Retrieval‑Augmented Generation*. Variants people drop in conversation: *naive RAG*, *advanced RAG*, *modular RAG*, *agentic RAG*.
- **Grounding** — answers backed by retrieved context. **Citations / sources** — the chunks shown to the user.
- **Context window** vs. **retrieved context** — different things, don't conflate.
- **Top‑k retrieval**, **re‑ranking**, **query rewriting / expansion**, **multi‑query**, **HyDE** (hypothetical document embedding).
- **Databricks**: *Mosaic AI Agent Framework*, *Vector Search*, *Feature Serving*, *Model Serving endpoint*, *AI Gateway*.
- **AWS**: *Bedrock Knowledge Bases* (managed end‑to‑end RAG), *Bedrock Agents*, *OpenSearch Serverless* (vector store), *Kendra* (enterprise search, can complement RAG).
- **Failure mode names**: *hallucination*, *retrieval miss*, *context dilution*, *lost‑in‑the‑middle*, *stale index*, *prompt drift*.

**Do (S):** whiteboard the FSR RAG pipeline in **under 5 minutes** from memory. Photo it. Redo until clean.

---

## 3. Parsing & ingestion  ·  D + FSR

Best learned by hand. In the POC notebook:

- Open one clean text PDF and one ugly/scanned/table‑heavy FSR. Compare extracted output.
- See what OCR adds (or breaks). Look at one table — does it survive?
- Note 2–3 concrete failure cases from the prod‑ops work (`FSR/ESN-resolution/`, `prod-issues/`).

**Vocabulary:**

- **Document understanding** umbrella: *layout parsing*, *OCR*, *table extraction*, *form extraction*, *reading order*.
- **Open‑source parsers** worth naming: *PyPDF / pdfplumber* (basic), *Unstructured*, *PyMuPDF*, *Marker*, *Docling* (IBM), *LlamaParse*.
- **Databricks**: *Volumes* (Unity Catalog file storage), *Auto Loader* (incremental file ingestion), *ai_parse_document* (Mosaic AI doc parsing), *Delta tables* as the bronze landing zone.
- **AWS**: *Amazon Textract* (OCR + tables + forms; *AnalyzeDocument*, *AnalyzeExpense*, *Queries* feature), *Amazon Comprehend* (entities, PII), *S3* + *EventBridge* triggers for ingestion.
- **Ingestion patterns**: *idempotent ingestion*, *content hash / dedup*, *document id*, *versioning*, *change data feed (CDF)* on Delta, *medallion architecture* (bronze/silver/gold).

**Say it (S):** "Tell me about a doc that broke your pipeline." — have one real story ready.

---

## 4. Chunking  ·  R + D + S

**Read (industry practices) — be able to name and contrast these:**

- **Fixed‑size** (by tokens or characters), with/without overlap — the baseline.
- **Sliding window** — overlap to avoid cutting context at boundaries (typical 10–20% overlap).
- **Sentence / paragraph** splitting — natural boundaries, variable size.
- **Recursive character splitting** (LangChain‑style) — try paragraphs → sentences → words until under size limit. Common default.
- **Structure‑aware / layout‑aware** — split by headings, sections, pages, tables. Best when docs have real structure (FSRs do).
- **Semantic chunking** — split where embedding similarity drops. Smarter, more expensive, sometimes worth it.
- **Parent–child / small‑to‑big** — embed small chunks for precision, return the larger surrounding chunk for context. Increasingly common.
- **Propositional / sentence‑window** — embed atomic facts; retrieve neighbors at query time.

Rules of thumb to know:
- Typical chunk sizes: **200–1000 tokens**, overlap **10–20%**. Smaller = better precision, more chunks, more cost.
- Always carry **metadata on every chunk** (doc id, page, section, source URL, plus domain fields like serial/ESN).
- Chunk size interacts with the **embedding model's max tokens** and the **LLM's context window** — don't pick in isolation.

**Where this lives in tools:**

- **Databricks**: chunking is custom code in a notebook / workflow that writes a *chunked Delta table* feeding *Vector Search*. Common helpers: LangChain `RecursiveCharacterTextSplitter`, LlamaIndex node parsers.
- **AWS**: *Bedrock Knowledge Bases* exposes built‑in chunking strategies — *fixed‑size*, *hierarchical (parent–child)*, *semantic*, and *no chunking* (one chunk per doc). Worth naming these by the AWS terms.

**Hands‑on (D):** take one FSR, chunk it 3 ways (fixed 500 / fixed 1000 with overlap / structure‑aware by section). Run the same 2–3 questions against each. Eyeball which retrieves better. Note what surprised me.

**Say it (S):** "How did you pick chunk size?" — answer with the trade‑off (recall vs. precision vs. cost vs. context window), not just a number. Bonus: name 2 alternatives I considered and why I didn't pick them.

---

## 5. Embeddings  ·  D + R

- Hands‑on: embed the same chunk with **2 different models** (e.g., one Databricks/Bedrock embedding model + one open‑source). Compare top‑k retrieval for the same query.
- Read enough to explain: cosine vs. dot, dimension, why model swap = re‑embed everything.

**Vocabulary:**

- **Dense embeddings** vs. **sparse embeddings** (BM25 / SPLADE) vs. **hybrid**.
- **Dimension** (e.g., 384, 768, 1024, 1536, 3072), **max input tokens**, **normalization** (L2), **similarity metric** (cosine, dot, L2).
- **Model versioning** and **re‑embedding / backfill** when the model or tokenizer changes.
- **Databricks**: *bge‑large‑en* (commonly served), *gte‑large*, *databricks‑gte‑large‑en*, served via *Foundation Model APIs* or *external models*; wired into *Vector Search* as the embedding endpoint for a *delta sync index*.
- **AWS Bedrock embedding models**: *Amazon Titan Embeddings (v1, v2; G1)*, *Cohere Embed (English/Multilingual, v3)*. Used by *Bedrock Knowledge Bases* or directly via the Bedrock InvokeModel API.
- **Quality references** people cite: **MTEB** (Massive Text Embedding Benchmark) leaderboard.

**Say it (S):** "Why did changing the embedding model trigger a backfill?" — use our actual FSR backfill as the example.

---

## 6. Vector search & retrieval  ·  D + R + FSR

- Hands‑on: stand up one Databricks Vector Search index in dev on the POC chunks. Query it. Try a metadata filter.
- Read about: ANN vs. exact, HNSW one‑liner, hybrid (dense + BM25), re‑ranking — concept level only.

**Vocabulary:**

- **ANN** (approximate nearest neighbor) vs. **exact / k‑NN**. Algorithms to name: *HNSW*, *IVF‑Flat / IVF‑PQ*, *DiskANN*.
- **Recall vs. latency trade‑off**, **ef / efConstruction / M** (HNSW knobs — know they exist).
- **Hybrid search** = dense + sparse (BM25) with score fusion (e.g., **RRF** — reciprocal rank fusion).
- **Re‑ranking**: *cross‑encoder* (e.g., Cohere Rerank, BGE reranker), *LLM‑as‑reranker*. Latency vs. quality trade‑off.
- **Metadata filtering / pre‑filtering**, **post‑filtering**, **MMR** (maximal marginal relevance) for diversity.
- **Query‑side techniques**: *query rewriting*, *multi‑query*, *HyDE*, *step‑back prompting*.
- **Databricks**: *Mosaic AI Vector Search*, *Delta Sync index* (auto‑syncs from Delta) vs. *Direct Vector Access index*, *similarity_search* API, *filters* on metadata columns, *hybrid search* support.
- **AWS**: *OpenSearch Serverless (vector engine)* — most common with Bedrock; alternatives Bedrock supports out of the box for Knowledge Bases — *Amazon Aurora PostgreSQL pgvector*, *Pinecone*, *Redis Enterprise Cloud*, *MongoDB Atlas*. Good to name a couple.

**Say it (S):** trace a query "issue with ESN X" through the FSR system end‑to‑end (filter → vector search → top‑k → response).

---

## 7. Metadata extraction  ·  D + FSR

This is one of our strongest stories — invest here.

- Hands‑on: extract ESN/serial, model, date from a few FSRs three ways: regex, LLM (structured output), hybrid. Compare accuracy on a handful of docs.
- Pull 2–3 real edge cases from the ESN‑resolution work.

**Industry pattern (always say this out loud):** metadata lives **on every chunk record**, not in a side table. Same shape across stacks — LangChain `Document.metadata`, LlamaIndex `TextNode.metadata`, Vector Search **filterable columns** (Delta columns alongside `text`), Pinecone/Weaviate/Qdrant chunk-`metadata` dict, Bedrock KB `metadata.json` sidecar flattened onto each chunk. Three tiers worth carrying: **identity** (`chunk_id`, `doc_id`, `source_uri`, `version`/`ingest_ts`), **locator** (`page`, `section`, `chunk_idx`) for citations, **domain filters** (`doc_type`, `tenant_id`, FSR-style `esn`/`serial`/`equipment_type`) for pre-filter at retrieve. Plus operational fields people miss: `embedding_model_name/version`, `chunker_name/version`, `content_hash`. Anti-patterns: nested-blob metadata that can't be filtered, metadata only at doc level (kills pre-filtering), shoving metadata into the embedded text instead of typed columns.

**Vocabulary:**

- **Information extraction (IE)**, **named entity recognition (NER)**, **key‑value extraction**, **schema‑guided extraction**.
- **Structured output** approaches: *JSON mode*, *function / tool calling*, *Pydantic / JSON schema constraint*, *Instructor*, *Outlines*, *guidance*.
- **Hybrid extraction** = deterministic (regex / rules) + LLM fallback; **confidence scoring**, **validators**, **human‑in‑the‑loop (HITL)**.
- **Databricks**: *AI Functions* — `ai_extract`, `ai_classify`, `ai_query` (run LLM extraction directly in SQL over Delta tables); results land in a silver/gold Delta table.
- **AWS**: *Textract Queries* (ask natural‑language questions of a doc), *Comprehend* custom entity recognition, *Bedrock* with Claude/Titan + a JSON schema in the prompt or via tool use.

**Say it (S):** ESN extraction as a 3‑minute case study — problem → approaches tried → trade‑offs → what I'd do next.

---

## 8. Evaluation  ·  R + light D

This is where most teams (and mine) are weakest — being honest about it lands well.

- Read: recall@k, precision@k, MRR, faithfulness, groundedness — one line each, know what each measures.
- Light do: build a 5–10 question golden set on the POC docs. Run it after any chunking/embedding change.
- Note where FSR has eval gaps and what I'd add first.

**Vocabulary:**

- **Retrieval metrics**: *recall@k*, *precision@k*, *MRR* (mean reciprocal rank), *nDCG*, *hit rate*.
- **Generation metrics**: *faithfulness / groundedness* (answer supported by context), *answer relevance*, *context relevance*, *context recall*, *citation correctness*.
- **LLM‑as‑judge** — use a strong model to grade outputs; pair with a small human‑labeled set to calibrate.
- **Golden / eval set**, **regression set**, **A/B comparison**, **online metrics** (thumbs‑up/down, deflection rate, time‑to‑answer).
- **Frameworks** to name: *Ragas*, *TruLens*, *DeepEval*, *Promptfoo*, *LangSmith evals*.
- **Databricks**: *Mosaic AI Agent Evaluation* (formerly *Agent Eval / RAG Studio eval*) — built‑in judges for groundedness, relevance, safety; *MLflow evaluate* with `evaluators="default"` for LLM tasks; *MLflow Tracing* for inspection.
- **AWS**: *Bedrock model evaluation jobs* (built‑in + human eval), *Knowledge Bases retrieval evaluation*, *SageMaker Clarify* for model eval, *CloudWatch* for online metrics.

**Say it (S):** "How would you evaluate this pipeline before shipping a change?" — 2 minutes.

---

## 9. Productionization (where I'm strongest)  ·  S + FSR

Mostly already have the experience — just package the stories.

- Bronze/silver/gold for unstructured.
- Workflows / Airflow orchestration.
- Backfill: idempotency, partitioning, restartability — use our actual backfill.
- Observability + drift / freshness.
- Cost levers (batching, caching, model tiering).

**Vocabulary:**

- **MLOps / LLMOps**, **medallion architecture**, **lakehouse**, **data contract**, **idempotent pipeline**, **incremental processing**, **backfill**, **replay**.
- **Observability**: *tracing* (request → retrieval → generation), *prompt logging*, *token usage*, *cost per query*, *latency p50/p95/p99*, *drift*.
- **Cost levers**: *prompt caching*, *response caching*, *batching*, *model tiering / routing* (small model first, escalate), *distillation*.
- **Databricks**: *Workflows / Jobs*, *DLT* (Delta Live Tables) for streaming/incremental, *Unity Catalog* (governance, lineage, volumes), *MLflow* (tracking, registry, deployments), *Mosaic AI Gateway* (rate limit, payload logging, PII detection across model endpoints), *Lakehouse Monitoring*, *system tables* for usage/cost.
- **AWS**: *Step Functions* (orchestration), *EventBridge* + *S3* events (ingestion triggers), *Lambda* (glue), *SageMaker Pipelines*, *Bedrock model invocation logging* (to S3/CloudWatch), *CloudWatch metrics + dashboards*, *Cost Explorer* / tags on Bedrock usage.
- **Patterns to name**: *blue/green model deployment*, *shadow traffic*, *canary*, *circuit breaker*, *fallback model*.

**Say it (S):** 3‑minute "how the FSR backfill worked and why" story. Practice it.

---

## 10. Safety, security, governance  ·  R + S

Read‑level depth is fine. Be ready to name:

- Prompt injection (incl. indirect via documents) + 1–2 mitigations.
- PII handling, what to log vs. not.
- Doc/row‑level access tied to user identity.
- Output guardrails (schema validation, refusal).

**Vocabulary:**

- **Prompt injection** (direct vs. *indirect* / via retrieved content), **jailbreak**, **data exfiltration via tool use**, **system prompt leakage**.
- **Guardrails**: *input filters*, *output filters*, *topic restriction*, *toxicity / PII detection*, *grounding check / refusal when unsupported*.
- **Identity & access**: *row‑level / column‑level security*, *attribute‑based access control (ABAC)*, *document‑level ACLs propagated to the index*.
- **Compliance words**: *SOC 2*, *HIPAA*, *GDPR*, *data residency*, *PII / PHI*, *redaction*, *audit log*.
- **Reference frameworks**: *OWASP Top 10 for LLM Applications*, *MITRE ATLAS*, *NIST AI RMF*.
- **Databricks**: *Unity Catalog* (single governance layer for data + models + functions), *AI Gateway* (PII detection, payload logging, rate limits), *Lakeguard*, *secrets* / *service principals*, *MLflow Model Registry* permissions.
- **AWS**: *Bedrock Guardrails* (denied topics, content filters, sensitive‑information filters, contextual grounding check), *IAM* + *resource policies*, *KMS* (encryption), *PrivateLink / VPC endpoints* (no public internet to Bedrock), *Macie* (PII discovery in S3), *CloudTrail* (audit).

**Say it (S):** "3 risks of ingesting customer FSRs and how you'd mitigate each."

---

## 11. Architect‑level system design  ·  R + S

Where interviews go for senior roles. Practice **drawing**, not just describing.

- Reference patterns: enterprise RAG, multi‑tenant RAG, agentic workflows (read 1–2 good blog posts, that's plenty).
- Build vs. buy trade‑offs (managed vs. self‑hosted).
- Where the bottlenecks live (embedding throughput, retrieval latency, generation cost).
- A simple cost model: tokens × queries × users.

**Vocabulary:**

- **Patterns**: *naive RAG*, *advanced RAG*, *agentic RAG*, *tool‑using agent*, *ReAct*, *plan‑and‑execute*, *multi‑agent*, *graph RAG*, *long‑context vs. RAG*, *fine‑tune + RAG hybrid*.
- **Multi‑tenancy**: *namespace per tenant*, *index per tenant*, *metadata‑filtered shared index*, *tenant‑scoped IAM*, *noisy‑neighbor* / *throttling*.
- **Scaling levers**: *throughput vs. latency*, *batch embedding*, *async generation*, *streaming responses*, *speculative decoding*, *prompt caching*, *KV cache*, *quantization* (INT8/INT4) — concept level.
- **Cost modeling**: *$ per 1k input tokens / 1k output tokens*, *embeddings $ per 1M tokens*, *vector index storage*, *queries × users × avg tokens*. Always include input + output separately.
- **Databricks reference architecture words**: *Mosaic AI*, *Agent Framework*, *Vector Search*, *Model Serving*, *AI Gateway*, *Unity Catalog*, *Delta Sharing* (cross‑org), *Lakehouse Apps*.
- **AWS reference architecture words**: *Bedrock + Knowledge Bases + Agents + Guardrails*, *OpenSearch Serverless*, *Lambda + API Gateway* front door, *Step Functions* orchestration, *S3 + Textract* for ingestion, *CloudFront + WAF* edge.
- **Build‑vs‑buy axis**: managed RAG (Bedrock KB / Mosaic Agent) vs. assembled (your own chunker + index + serving). Trade‑off = control / portability vs. time‑to‑value.

**Do (S):** sketch a 12‑month roadmap from today's FSR pipeline → agentic assistant. Bullet form, on paper.

---

## 12. Interview craft  ·  S only

- Whiteboard RAG cleanly in <5 min.
- Always say assumptions and trade‑offs out loud.
- Have **3 stories** locked in:
  1. A hard bug (e.g., ESN / multi‑serial).
  2. A design choice with a real trade‑off (e.g., chunk size or embedding model).
  3. A measurable win (e.g., backfill or a quality fix).
- Be honest about what didn't work.

**Do (S):** record a 10‑minute FSR architecture walk‑through. Listen back. Re‑record once.

---

## 13. Forward‑looking: Anthropic / OpenAI / GCP  ·  R later

Park here. Pick up after Databricks + AWS feel solid. Just enough to not look surprised when they come up.

- **Anthropic (Claude)**: *Claude 3 family* (Haiku / Sonnet / Opus, plus 3.5 / 3.7 lines), *200k context*, *prompt caching*, *tool use*, *Computer Use*, *Constitutional AI*, *Artifacts*. Available in *Bedrock* and *Databricks external models*.
- **OpenAI**: *GPT‑4 / GPT‑4o / o‑series (reasoning models)*, *Assistants API*, *Responses API*, *Structured Outputs (JSON schema)*, *Function calling*, *Batch API*, *Realtime API*, *Embeddings (text‑embedding‑3‑small/large)*.
- **GCP**: *Vertex AI*, *Gemini family*, *Vertex AI Search* (managed RAG), *Vector Search* (Matching Engine), *Document AI* (parsing/OCR).
- **Open‑source / serving** (cross‑cloud): *vLLM*, *TGI*, *Ollama*, *llama.cpp*, *Hugging Face Inference Endpoints*, *Together AI*, *Groq*, *Fireworks*.
- **Frameworks / agents**: *LangChain*, *LangGraph*, *LlamaIndex*, *Haystack*, *DSPy*, *CrewAI*, *AutoGen*.

**Goal here:** be able to recognize and discuss, not implement.

---

## Suggested 2‑day shape (rough)

**Day 1 — get hands dirty (D‑heavy)**
- Morning: §3 parsing + §4 chunking on one FSR (POC notebook).
- Afternoon: §5 embeddings + §6 vector search end‑to‑end in Databricks dev.

**Day 2 — round it out (R + S heavy)**
- Morning: §7 metadata extraction hands‑on; §1, §2, §8 reading + notes.
- Afternoon: §9–§12 — write the stories, do the whiteboard practice, record the walk‑through.

## How I'll track progress

For each section, when I'm done I want **one short paragraph** answering: "If asked about this in 90 seconds, what do I say?" That paragraph is the real deliverable — not the reading.
