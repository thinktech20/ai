# Arch-Hive Deck — PPT Copy-Paste Content

> **Use:** copy-paste source for the PowerPoint. Slide content only — no intent, talk tracks, diagram notes, or confidentiality checks (those live in [arch-hive-slides-v2.md](arch-hive-slides-v2.md)).
> **Slide count:** 9 main + 2 backup. *(2026-05-23 trim pass: dropped the standalone agenda and the standalone "patterns that travel" slides — the flow is the agenda; the tradeoff tables already carry the patterns. Language pass across the rest to keep it plain.)*

---

## Slide 1 — Title

**Title:** Building a production RAG pipeline and conversational agent on 40 years of field data.

**Sub-line:** An engagement I designed end-to-end — the architecture, the calls that mattered, and what would carry into the next build.

*Footer: presenter name + role + date.*

---

## Slide 2 — The setup

**Title:** The setup.

**Sub-line:** What the OEM was sitting on, and why search alone wasn't cutting it.

**Body — three blocks:**

**The corpus.**
A large industrial-equipment OEM. ~18,000 field service reports going back four decades. PDFs of mixed scan quality and format. Each one tied to a physical unit still in service.

**The pain.**
When a unit failed, the answer was almost always in those reports somewhere. Nobody could find it in time. Manual lookup ran into hours per assessment. Most of the corpus never got read because nobody had the time to.

**Why RAG fit.**
A retrieval problem, not a generation one. The LLM's job was to read what got pulled — not invent it. The hard part was making retrieval reliable across 18K docs and 1.09M chunks, with engineers in the loop who knew the data better than any model.

---

## Slide 3 — What got built

**Title:** What got built.

**Sub-line:** Two components in scope here, sharing one index.

**Body — full-width architecture diagram:**

*Left — data pipeline:*
- Source PDFs in UC Volumes → **FSR pipeline** *(in scope — highlighted)*
  - Metadata extraction + registration (Silver)
  - Chunking + embedding (Gold)
  - Status-driven backfill + incremental

*Middle — shared index:*
- Vector Search index

*Right — agents:*
- **AdHoc QA agent** *(in scope — highlighted)* — conversational QA, persona-aware tools
- Unit Risk agent *(separate team — not covered here)* — proactive risk signals on the same index

**Scope (bottom strip):**

> Slides 5 through 8 go deep on the pipeline and the QA agent. The risk agent runs on the same index but a different team built it; it stays on the diagram because the shared-index story matters, not for a walkthrough of its internals.

---

## Slide 4 — The stack

**Title:** The stack — and what shipped it.

**Sub-line:** What runs in prod, what built it. Vendor-neutral after this — the rest of the deck is patterns.

**Body — two columns:**

### Left column — production stack

**Data + pipeline**
- **Databricks** — Unity Catalog, Workflows, Delta Lake (Bronze/Silver/Gold), Spark, **Databricks Vector Search** (DELTA_SYNC TRIGGERED, manual sync).

**Agent runtime + serving**
- **AWS Strands** — agentic framework. ReAct loop, tool execution, session-store integration.
- **LiteLLM** — one gateway in front of every frontier model. Claude for the QA agent, Gemini for parts of the pipeline. One proxy, one auth, one observability surface.
- **MCP (Model Context Protocol)** — how internal tools and reference-data services are exposed to the agent. Same pattern used build-side for Claude Code.
- **FastAPI on ECS Fargate** — streaming HTTP for the agent service.
- **Amazon S3** — managed session store, scoped per user.
- **Amazon CloudWatch** — logs + metrics.

**Embeddings + retrieval**
- **OpenAI `text-embedding-3-large`** (3072 dims), called through LiteLLM.
- **Databricks Vector Search** with deterministic pre-filtering before semantic ranking.

### Right column — build-time tooling

- **Claude Code** — design scaffolds, larger refactors, multi-file edits, PR review passes. Most of the leverage came from here.
- **GitHub Copilot** — in-editor completion, inline edits, smaller refactors.
- **VS Code + Copilot Chat** — the design and review surface.

**Come find me on:**
- End-to-end Databricks RAG (Unity Catalog → Workflows → Delta → Vector Search) at multi-million-chunk scale.
- LiteLLM as a single-gateway pattern across multiple frontier-model vendors.
- AWS Strands agents in production with MCP-exposed tools, behind streaming FastAPI on Fargate.
- Running an engineering team where Claude Code + Copilot are part of the daily SDLC.

---

## Slide 5 — FSR pipeline — how it's wired

**Title:** FSR pipeline — how it's wired.

**Sub-line:** Bronze → Silver → Gold. The metadata table is also the work queue.

**Body — full-width medallion diagram:**

*Bronze — raw source:*
- Source PDFs in UC Volumes.
- Reference data sources, read for enrichment downstream.

*Silver — metadata extraction + registration (Process 1):*
- Discover new PDFs against the registry → extract metadata with an LLM → normalize and enrich against reference data → write one row per document into the registry.
- **Registry table** — one row per document. Status fields and retry counters.

*Gold — chunks + vector index (Process 2):*
- Pick up pending documents from the registry → load PDFs → hierarchical semantic chunking → copy metadata onto every chunk → embed in parallel.
- Chunk table — chunks + embeddings + metadata as top-level columns.
- Vector Search index, manually synced from the chunk table.
- Process 2 writes status (completed / failed) back to the registry. **The registry is the queue.**

---

## Slide 6 — FSR pipeline — design calls that held up

**Title:** Five design calls that held up.

**Sub-line:** Each one had a simpler alternative. Here's why the simpler one wouldn't have lasted.

**Body — 5-row table:**

| # | The call | Why it held up |
|---|---|---|
| 1 | **Metadata first.** Extract and enrich it in its own pass before any chunking. One metadata row per document — the contract every consumer reads off. | Inline metadata-during-chunking is less code and quietly drifts: every consumer ends up parsing slightly differently. Doing it once upfront keeps the index and the agent on the same source. New consumers added later pay nothing on data work. |
| 2 | **The registry is the work queue.** Status fields on the metadata table drive what runs next. | A separate orchestration queue splits state in two places — debugging that at 2am is its own job. One table covers backfill, incremental, retries, and replays. |
| 3 | **One code path for backfill and incremental.** First run is backfill; every run after is incremental. | A dedicated backfill job diverges from steady-state code over time — that gap is where bugs live. One path means every fix lands in both. |
| 4 | **Verified IDs, not LLM-extracted ones, drive filtering.** The equipment-ID downstream agents pre-filter on is matched against a system-of-record table at ingest. An audit field records how the match was derived. | LLM-extracted IDs silently shift the day the model updates. Reference-matched IDs don't — deterministic and auditable. A day of integration upfront; pays back the first time a model change would have moved extraction. |
| 5 | **Metadata copied onto every chunk.** Chunks are self-contained. | Metadata only on the parent + joining at query time saves storage and kills pre-filtering — the vector index needs the field on the chunk to filter before semantic ranking. Pre-filter is fast and exact; post-filter is neither. |

---

## Slide 7 — AdHoc QA agent — how it's wired

**Title:** AdHoc QA agent — how it's wired.

**Sub-line:** Three zones — user context, the reasoning loop, tools. Same vector index the pipeline built.

**Body — full-width architecture diagram, three zones:**

*User + context:*
- Engineer (Reliability Engineer or Outage Engineer) opens a session tied to a specific risk assessment.
- Persona and assessment context attached to the session.
- Streaming HTTP API.

*Reasoning loop:*
- Agentic framework running a ReAct loop (Thought → Action → Observe).
- Frontier LLM does the reasoning.
- Per-user session memory, scoped to the assessment.

*Tools (persona-scoped, fixed at startup, exposed over MCP):*
- Retrieval over the Vector Search index, pre-filtered to the right equipment.
- Reference-data lookups via a thin data-services layer.
- Assessment-context reads — findings, narrative summary, event history.

*All tools read the shared Vector Search index. Agents don't write to it.*

**Footer:**

> Every fact the agent states comes from a tool result. The LLM reasons; it doesn't assert.

---

## Slide 8 — AdHoc QA agent — design calls that held up

**Title:** Five design calls that held up.

**Sub-line:** Same shape as the pipeline slide — each one had a simpler alternative that wouldn't have lasted.

**Body — 5-row table:**

| # | The call | Why it held up |
|---|---|---|
| 1 | **Tools are the grounding line.** Every fact comes from a tool result. The LLM reasons; it doesn't claim. | Letting the LLM answer freely and patching with prompts is a treadmill — engineers spot the wrong answer the second it shows up, and trust never recovers. Tool-result-or-nothing is the only posture that earns trust on day one. |
| 2 | **Persona-scoped tool list, fixed at startup.** Each role gets only the tools relevant to their job. | A shared tool list with a prompt telling the LLM what to pick puts access control in the wrong place. Fixed at construction means the wrong tool literally can't be called. Smaller list also makes tool selection more reliable. |
| 3 | **Per-user session, scoped to the assessment.** Two engineers on the same assessment get separate transcripts. | A shared session would leak one engineer's exploratory questions into another's view. Conversation context is private by default. |
| 4 | **Managed framework owns the ReAct loop.** The build owns tools and prompts — not orchestration code. | Custom agent loops sound like more control and become where most agent builds burn time and ship bugs. The framework's loop is solved; time better spent on tools and grounding. |
| 5 | **Retrieval pre-filtered to the right equipment.** The retrieval tool calls the index with a deterministic filter before ranking runs. | Semantic-only retrieval at this corpus size bleeds in adjacent-unit docs — top-k alone isn't precise enough. Pre-filtering scopes the search before ranking, which is why the verified-IDs call on the pipeline slide matters here. |

---

## Slide 9 — Close

**Title:** One bridge, one question.

**Top block — the bridge:**

> This was the architecture cut. There's a companion deck on the engineering practice that produced it — design, review, and operate, when AI is in the loop. Five patterns, three artifacts. Ping me afterwards if that's the one you want.

**Bottom block — closing question (large, centered):**

> *Which of these calls would your next build use first?*

---

## Backup B1 — War story: silent ID drift

**Title:** War story — silent ID drift.

**Sub-line:** A model update shifted how IDs were extracted. No error fired. The only signal was zero-results on the agent side, three weeks later.

**Body — four stacked blocks:**

- **What shipped.** A routine model update on the metadata extraction step. The validation harness on the change said *"looks fine"* — happy-path tests passed.
- **What broke.** On the next daily incremental, ~166 documents (~1% of the corpus) had their hard equipment-ID field populated with a near-correct but invalid value. No loud failure. The pipeline ran clean. The chunks landed. The vector index synced.
- **What changed.** The validation harness became a *merge gate* for any change to the extraction step — known-good + known-bad + a regression sample, run before the change can land. The data-quality log added a zero-match-rate alert on the hard equipment-ID field. The single code path for backfill let the team re-process the affected ~166 docs from the registry with one notebook run.
- **The lesson (one line).** *AI-generated output reads like working output. "Looks fine" passes happy-path tests. The only way to catch silent failures is a validation contract that runs before the change can land.*

---

## Backup B2 — Anonymization disclaimer

**Title:** A note on what's in this deck.

**Sub-line:** This deck is anonymized for Slalom-internal sharing. Please don't forward it outside Slalom.

**Body:**

> The architecture, the design choices, and the failure modes in this deck are drawn from a real engagement. Customer name, engagement team names, source-system names, table and field names, lookup-source names, framework names, model names, and tool names have been removed. The framing — large industrial-equipment OEM, two components designed end-to-end — is the only context kept.
>
> This deck is **Slalom-internal**. Please don't forward it externally, post it, or quote it outside this room without checking first.
