# Framing — RAG / Retrieval Talk: Slalom vs Big-AI Interview

**Created:** 2026-05-20 · captured from chat after Eric 1:1 prep.

Same delivery work (FSR + AdHoc QA), two audiences, two vocabularies. Keep both framings warm.

---

## TL;DR — same proof, different language

| Dimension | Slalom audience (Arch-Hive, brown bag, internal article) | Big-AI interview (Anthropic, Databricks, OpenAI) |
|---|---|---|
| Lead with | Vendor pattern + ship-it lessons | Problem + system trade-offs |
| Use the word "RAG"? | Yes, loudly | Sparingly — show depth instead |
| Anchor proof | "1.5M chunks in prod on Databricks" | "Multi-vector vs single-vector trade-off and why" |
| Failure stories | Sync staleness, citation accuracy | Same — but framed as design choices, not war stories |
| Eval language | Light — "citation accuracy improved" | RAGAS / faithfulness / golden-set / drift |
| What they're testing | Can you run their next client? | Can you reason about retrieval systems at depth? |
| Vibe | Pragmatic, useful | Rigorous, opinionated |

---

## Audience 1 — Slalom folks

**They are:** consulting peers, mostly architects/engineers. Practical, vendor-aware (Databricks, AWS, Azure). Care about *what to do on the next client engagement*.

**Positioning moves:**
- Lead with the pattern, not the term. Say *"Productionizing RAG on Databricks"* — concrete, signals you've shipped it.
- Frame as the boring-but-essential baseline. *"Every client AI ask in 2026 has RAG somewhere in the stack — differentiator is whether you can get it to prod, not whether you can prototype it."*
- Show the production-hard parts: chunking strategy, metadata filters, vector index refresh, sync staleness, embedding cost, citation accuracy, eval.
- Use the vendor surface area they'll meet: Databricks Vector Search, Delta sync, UC, LiteLLM gateway.
- Land it with a story: FSR — 1.5M chunks in prod, 99.3% backfill, what broke and how we fixed it.

**One-liner:**
> *"RAG is the must-do baseline now. I want to share what actually breaks when you put it in production on Databricks — chunking, sync, citations, eval — so you don't learn it on the client's dime."*

---

## Audience 2 — Big-AI interviews (Anthropic, Databricks, OpenAI, frontier labs)

**They are:** ML/infra engineers, applied researchers, staff/principal interviewers. They have seen 500 RAG resumes. *"I did RAG"* is table-stakes — they're calibrating depth and judgment.

**Positioning moves:**
- Don't lead with "RAG." Lead with the problem + trade-offs. *"We had a 1.5M-chunk corpus of field service reports — sparse, noisy, multi-entity per doc — and a Q&A agent that needed citation-accurate answers. Vector search alone wasn't enough."* Then explain the system.
- Show trade-off vocabulary: single-vector vs multi-vector (ColBERT/ColPali), dense vs sparse vs hybrid, re-ranking cost vs recall, chunk-size vs context-window economics, retrieval@k vs answer faithfulness, eval-set construction.
- Demonstrate you know when *not* to do RAG: long-context, structured queries, NER-extraction tasks, agent tool-use replacing retrieval.
- Talk about evaluation seriously: RAGAS, faithfulness, context recall, golden-set construction, offline-vs-online drift. Most candidates skip this.
- Bring failure modes: stale index, vacuum window vs sync interval, partial embeddings, gateway retries, hallucinated citations, multi-tenant filters, PII leakage. Senior signals.
- Frame agent work as *agentic retrieval*, not "RAG plus tools." Dynamic tool selection, multi-step LLM-controlled iteration over multiple sources — that's their internal language.

**One-liner (interview opener):**
> *"My recent work is on productionizing retrieval-augmented systems — both a RAG pipeline grounding a Q&A agent over field service reports, and the agent itself doing dynamic tool selection across structured + unstructured sources. Happy to go deep on retrieval design, eval, or the failure modes we hit in prod — whichever is most useful."*

---

## Vocabulary cheat-sheet for the big-AI track

Worth being fluent before any interview:

- **Retrieval:** dense (bi-encoder), sparse (BM25), hybrid (RRF / weighted), multi-vector (ColBERT, ColPali), late-interaction
- **Re-ranking:** cross-encoder, LLM-as-reranker, MMR for diversity
- **Chunking:** fixed-window, semantic, recursive, parent-child, propositional
- **Eval:** RAGAS (faithfulness, answer relevance, context precision/recall), TruLens, BEIR, custom golden sets, offline vs online metrics
- **Agentic retrieval:** dynamic tool selection, multi-hop, query decomposition, self-RAG, CRAG, ReAct
- **Failure modes:** stale index, retrieval miss, irrelevant top-k, hallucinated citation, lost-in-the-middle, multi-tenant leakage
- **Trade-offs in the room:** latency vs recall, cost vs quality, freshness vs index churn, context-window vs retrieval

## Drawings / artifacts to have ready

- 5-minute whiteboard of FSR pipeline (ingest → chunk → embed → index → query)
- 2-minute whiteboard of AdHoc QA agent (tool list + decision loop)
- 1-slide "what broke + how we fixed it" (VS sync retention story is interview gold)
- 1-slide eval framework (the one we'd build if we were starting over)

## Use this with

- [`../interviews.md`](../interviews.md) prep checklist — this is the "system design — RAG architecture (90s answer)" + chunking trade-off + "doc that broke the pipeline" expansion.
- [`../promo/Eric-track/brand-plan.md`](../promo/Eric-track/brand-plan.md) — Slalom-side framing seeds the Arch-Hive + brown bag content.
