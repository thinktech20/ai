# Arch-Hive #2 — slide skeleton (v2)

> **2026-05-23 revision note — read this first.**
>
> The current presentation cut lives in [arch-hive-slides-ppt-content.md](arch-hive-slides-ppt-content.md) — **9 main + 2 backup** (down from 11+2). Two slides dropped, language tightened across the rest. This file still has the long-form intent / body / talk-track / confidentiality notes per slide and is useful as the deeper draft, but the PPT-content file is what should ship.
>
> **What changed in the cut:**
> - **Dropped Slide 2 ("What this talk covers"):** the flow itself is the agenda; the overview slide (now Slide 3) sets scope honestly without a separate agenda slide.
> - **Dropped Slide 9 ("Three patterns that travel"):** the tradeoff tables on Slides 5 and 7 already carry those patterns. Re-listing them was repetition.
> - **Slide 1 title** changed from "what travels, what doesn't" framing to plain "Building a production RAG pipeline on 40 years of field data."
> - **"Tradeoffs that earned their keep" → "calls that mattered" / "calls I'd make again"** across the deck — the original phrasing read polished; the new one reads like someone who actually made the calls.
> - **"The substrate has to be trustable" → dropped.** The tables and the diagram make the point without the editorial line.
> - **Slide 3 ("The setup")** replaces the older "The business problem" — same content, plainer title.
> - **Sub-lines tightened** on every slide. Several were restating the title.
>
> The intent notes, talk tracks, confidentiality checks, and diagram notes below remain accurate in *substance* but reference the older slide numbers and the older phrasing. When second-passing this file, align titles/sub-lines/footers to the PPT-content file; talk tracks need a light renumber pass.

---

> **What changed from v1:** restructured around honest scope and external-takeaway framing. One overview slide showing the full flow with the two components I designed highlighted, then deep-dives on those two components only (FSR pipeline + AdHoc QA agent). Schema details removed. Unit Risk agent dropped from deep-dive — referenced on the overview slide only, with attribution to the team that built it. Patterns slide reframed as *takeaways for the audience*, not engagement-specific claims. **Added Slide 10 — tech stack + build-time tooling**, so the audience knows which technologies they can reach out to me about as SME later.
>
> **Source diagrams to render in PPT:**
> - FSR pipeline → [FSR/metadata-first-end-to-end-flow.drawio](../../../FSR/metadata-first-end-to-end-flow.drawio)
> - AdHoc QA agent → [unit-risk/8. AdHoc QA Agent.pdf](../../../unit-risk/8.%20AdHoc%20QA%20Agent.pdf)
>
> **Audience:** Slalom-internal Arch-Hive #2 — architects + senior engineers across delivery teams. They want *what I built, the design tradeoffs I weighed, what they can apply to their own work.*
>
> **Length target:** 11 main slides + 2 backup, ~22 min talk + 10 min Q&A.
>
> **Anonymization vs. tech-naming split:** the body slides (3–9) describe design and tradeoffs *generically* — no vendor names, no framework names. Slide 10 is the one place tech is named on-screen — that's where the audience finds out which platforms / frameworks / models / build-time tools to come talk to me about. This keeps the architecture story portable and concentrates the SME-signal on one slide.
>
> **Voice:** "I" for design choices, tradeoffs, and what I'd carry forward. "We" only where the engagement team genuinely co-built (e.g. validation harness). "A separate team" for the Unit Risk agent — clearly not my work.
>
> **Anonymization:** large industrial-equipment OEM as the framing. No customer name, no partner-team name, no proprietary detail. No real table names, column names, lookup-source names, or tool names — describe by role only. No schema enumeration. Numbers (18K docs, 1.09M chunks, etc.) are fine — they're scale, not secrets.
>
> **Relationship to Eugene deck:** this is the *architecture* cut. Eugene deck is the *engineering-practice* cut. Bridge near the end of this deck signals the Eugene track for anyone who wants the deeper "what changed in how I build" version.
>
> **Status:** content draft — slide titles + body + talk track + confidentiality checks. Visuals to be drawn before the deck goes live.

---

## Main slides (10)

### Slide 1 — Title

**Title:** *Designing a production RAG pipeline on 40 years of field data — what travels, what doesn't.*

**Sub-line:** One engagement, in prod today. Two components I designed end-to-end, and the tradeoffs that earned their keep at production volume.

**Layout:** title slide. Title centered, sub-line one size smaller below. Speaker name + role + date in the footer. No visual.

---

**Talk track (~30s):**

1. *Read the title (~10s).* Verbatim. Pause briefly on "what travels, what doesn't."
2. *Land the frame (~15s).* "One real engagement — large industrial-equipment OEM, anonymized. In prod today at production scale. Two components I designed; this deck walks both, plus the tradeoffs I'd carry forward."
3. *Move on (~5s).* Don't read the sub-line aloud; let it set expectation visually.

**What NOT to do on this slide:**
- No agenda. The flow is the agenda; slide 2 sets it.
- No speaker bio. Footer is enough for this audience.
- No customer name, no partner-team name. "Large industrial-equipment OEM" is the framing for the whole deck.
- Don't overpromise generality. The sub-line says *"what travels, what doesn't"* on purpose — some choices are corpus-specific.

---

### Slide 2 — What this talk covers

**Intent:** set the new structure — one overview, two component deep-dives, takeaways. Honest scope: this deck covers only what I designed and built. The downstream agent that consumed the same pipeline is acknowledged on the overview slide but not deep-dived (different team).

**Title:** *What this talk covers.*

**Sub-line:** One engagement, two components I designed, takeaways you can lift.

**Layout:** five short bullets, full width. Each bullet maps to a section of the deck.

---

**Slide body — five bullets:**

- **The complete flow in one picture** — pipeline, shared index, downstream agents. Two components highlighted are the ones I designed end-to-end. *(slide 4)*
- **FSR pipeline — architecture + the tradeoffs that earned their keep at production volume.** *(slides 5–6)*
- **AdHoc QA agent — architecture + the design choices that matter when grounding an LLM on a domain corpus.** *(slides 7–8)*
- **Takeaways — three patterns that travel beyond this corpus.** *(slide 9)*
- **The stack — and the build-time AI tooling that shipped it.** Where to come find me as SME later. *(slide 10)*

---

**Footer line:**

> Companion deck on the engineering-practice side — design → review → operate when AI is in the loop — signaled on slide 11.

---

**Talk track (~1 min):**

1. *Frame (~10s).* "Five threads. One engagement, in prod today. Honest scope: I'll go deep only on the components I designed."
2. *Walk the five bullets (~40s).* ~8s each. Read the bullet; don't expand — the rest of the deck is the expansion.
3. *Close (~10s).* "Last bullet is the tech stack — I keep the body of the deck vendor-neutral, then name the stack at the end so you know what to come ask me about. Bridge to the companion deck right after." Move on.

**What NOT to do on this slide:**
- Don't preview content from individual slides. The slide-number annotations are a visual aid, not a script.
- Don't introduce the speaker here — slide 1 footer is enough.
- Don't tease the takeaways slide (9) — the audience absorbs them better if they earn them by slide 9, not anticipate them by slide 2.

---

### Slide 3 — The business problem

**Intent:** decades of unstructured field data (service reports, procedure docs, engineering review cases) tied to physical equipment units. Long unplanned outages were expensive. Goal: convert reactive failures into planned maintenance windows by making 40 years of unstructured data answerable in seconds. RAG was the right tool — the answer was already written down somewhere; the problem was *finding it across ~18K documents* in time to act on it.

**Title:** *The business problem.*

**Sub-line:** Decades of unstructured field data, sitting in PDFs. The answers were already written down — the problem was finding them across ~18K documents in time to act on them.

**Layout:** three short blocks stacked. Problem → cost → why RAG.

---

**Block 1 — The problem:**

> A large industrial-equipment OEM with decades of field service reports, procedure documents, and engineering review cases. ~18K documents. Tied to physical equipment units in active service. When something failed in the field, the answer was almost always written down somewhere in the corpus — but nobody could find it fast enough.

**Block 2 — The cost:**

> Reactive failures meant unplanned outages. Long ones. Expensive ones. The reliability and outage planning teams were carrying that cost as the *default operating mode* — not because the data wasn't there, but because the data wasn't *findable* under the time pressure that mattered.

**Block 3 — Why RAG:**

> The answer pattern was always *"go find the precedent."* That's a retrieval problem, not a generation problem. RAG was the right tool — the LLM's job was to read what we retrieved, not to invent it. The hard part was making retrieval *trustable* across 18K documents and 1.09M chunks.

---

**Talk track (~1.5 min):**

1. *Frame (~30s).* Walk Block 1. Land the corpus scale (18K docs) and the constraint (tied to real equipment in active service).
2. *Land the cost (~30s).* Walk Block 2. Don't dwell on outage numbers — the qualitative claim (reactive → planned) is the point.
3. *Land why RAG (~30s).* Walk Block 3. The framing matters: RAG is a *retrieval* problem first, generation second. That framing drove every architectural choice that follows.

**Confidentiality checks:**
- "Large industrial-equipment OEM" is the only customer framing on this slide. No vertical detail beyond that.
- No outage dollar figures — qualitative cost only.
- No specific business-unit names. "Reliability and outage planning teams" by role only.

**What NOT to do on this slide:**
- Don't quote the planning team or any customer-side voice. Generic role framing only.
- Don't preview the architecture — slide 4 is the first picture.
- Don't editorialize on "RAG hype" — the frame is *RAG was the right tool for this problem*, not a broader take.

---

### Slide 4 — The complete flow, and what I designed

**Intent:** one picture of the whole system — data pipeline on the left, shared Vector Search index in the middle, downstream agents on the right. **Two components highlighted (visual boxed or color-flagged) are the ones I designed end-to-end:** the FSR pipeline and the AdHoc QA agent. The Unit Risk reasoning agent is shown to complete the picture but flagged as built by a separate team — the deck does not deep-dive on it. This slide sets honest scope before the deep-dives start.

**Title:** *The complete flow — and what I designed.*

**Sub-line:** Pipeline on the left, shared index in the middle, two agents on the right. I'll go deep on the two highlighted components.

**Layout:** one full-width diagram (described below). Scope-callout strip at the bottom — two short lines.

---

**Diagram — left-to-right flow, three groupings (must be drawn before the deck goes live):**

```
[Source PDFs in UC Volumes]                                                  ┌─ [AdHoc QA agent]      ◄ HIGHLIGHTED (my scope)
           ↓                                                                  │   conversational QA
  ┌───────────────────────────────────────────────┐                          │   persona-aware tools
  │  FSR pipeline (my scope) ◄ HIGHLIGHTED            │                          │
  │   • Metadata extraction + registration (Silver)   │                          │
  │   • Chunking + embedding (Gold)                   │ ──► [Vector Search]   ──┼
  │   • Status-driven backfill + incremental         │        index             │
  └───────────────────────────────────────────────┘                          │
                                                                              └─ [Unit Risk agent]     ◄ NOT highlighted
                                                                                  proactive risk signals    (separate team —
                                                                                  on the same substrate      not covered here)
```

*Visual notes for the PPT draw:*
- **Highlight treatment:** the FSR pipeline box and the AdHoc QA agent box get a colored border or a subtle fill tint. Add small "my scope" label-tags on each. The Unit Risk agent box stays plain (or muted) with a small "separate team" tag.
- **Three visual zones:** *Data pipeline (left), Shared index (middle), Agents (right).* Light grouping rectangles around each — keeps the layered architecture readable.
- **Arrows are read-only from agents → index.** No arrows from agents back into the pipeline. The shared substrate is the whole point.

---

**Scope callout (bottom strip):**

> **My scope in this deck (slides 5–8):** the FSR pipeline (architecture + design tradeoffs) and the AdHoc QA agent (architecture + design choices).
> **Acknowledged but not deep-dived:** the Unit Risk reasoning agent — built by a separate team on the same substrate. Its existence matters for the architecture story (one index, multiple consumers); its internals are not mine to walk through.

---

**Talk track (~1.5 min):**

1. *Frame (~15s).* "One picture for the whole system. Pipeline on the left, shared index in the middle, agents on the right. Everything else in the deck unpacks one part of this picture."
2. *Walk the three zones (~45s).* Left zone: PDFs in volumes flow through the pipeline I built. Middle zone: one Vector Search index. Right zone: two agents consume that index. Both agents are read-only consumers — the shared substrate is the point.
3. *Land the scope (~20s).* "The two highlighted boxes are what I designed end-to-end — the FSR pipeline and the AdHoc QA agent. Slides 5–8 go deep on those two. The Unit Risk agent is on the same substrate but a separate team built it; I'll reference it where it matters for the architecture, but I won't walk its internals."
4. *Bridge (~10s).* "Pipeline first. Slide 5."

**Confidentiality checks:**
- Component names by role only: "FSR pipeline", "AdHoc QA agent", "Unit Risk reasoning agent". No product names, no project codenames.
- No real table names, schema, or storage paths in the visual. UC Volumes is the only platform name worth keeping (architectural relevance).
- LLM, embedding model: not named on this slide.

**What NOT to do on this slide:**
- Don't sell the Unit Risk agent's outcomes — it's not your work and the deck doesn't claim it.
- Don't add arrows from the agent layer back into the pipeline. Agents are read-only consumers — that's the architectural point.
- Don't get into status-driven backfill detail here — slide 5 owns the pipeline mechanics.
- Don't apologize for the scope. Honest scope is a credibility move, not a limitation.

**Diagram note (for visual pass):** the strongest version of this slide has the *highlight treatment do the talking* — the eye should go straight to the two boxed components without needing the talk track to point them out. Test in the PPT draw: if the audience can't tell which two are "my scope" within 3 seconds, the highlight isn't strong enough.

---

### Slide 5 — FSR pipeline — architecture

**Intent:** one architecture diagram for the pipeline I built. Bronze → Silver → Gold, with the **metadata registry as the spine** (also the queue that drives backfill + incremental from the same code path). Source diagram: `FSR/metadata-first-end-to-end-flow.drawio`. The slide walks the *shape* of the pipeline — design choices and tradeoffs land on slide 6.

**Title:** *FSR pipeline — architecture.*

**Sub-line:** Bronze → Silver → Gold. A metadata registry that doubles as the work queue. Same code path for backfill and incremental.

**Layout:** full-width architecture diagram. Minimal annotation on the slide itself — the talk track walks it.

---

**Diagram — left-to-right, three medallion bands (must be drawn before the deck goes live):**

```
┌── BRONZE  (raw source volumes) ───────────────────────────────────────────┐
│                                                                                  │
│    [Source PDFs in two UC volumes — non-recursive, top-level only]               │
│    [Reference data sources — used for enrichment in Process 1]                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
              │                                          │
              ↓ PDFs                                     ↓ (read for enrichment)
┌── SILVER  (metadata extraction + registration) ─────────────────────────────┐
│                                                                                  │
│   Process 1                                                                      │
│   [1A discover new PDFs] → [1B MERGE stub rows] → [1C extract + LLM normalize    │
│    (registry left_anti)     (status = pending)        + reference-data enrich]   │
│                                                          ↓                       │
│                                                       [1D write one metadata     │
│                                                        row per document to       │
│                                                        registry; chunk_status    │
│                                                        = pending]                │
│                                                          ↓                       │
│                                            ┌─────────────────────────────────┐    │
│                                            │  REGISTRY (metadata table)   │    │
│                                            │  one row per document        │    │
│                                            │  metadata_status · chunk_    │    │
│                                            │  status · retry counts       │    │
│                                            └─────────────┬──────────────────┘    │
└─────────────────────────────────────────────────────────│───────────────────┘
                                                          │ reads rows where
                                                          ↓ chunk_status = pending
┌── GOLD  (AI-ready chunks + vector index) ──────────────────────────────────┐
│                                                                                  │
│   Process 2                                                                      │
│   [2A select pending] → [2B load PDFs] → [2C hierarchical semantic chunking]    │
│                                                          ↓                       │
│                          [2D materialize metadata onto chunk rows] →             │
│                          [2E generate embeddings (parallel workers)]             │
│                                                          ↓                       │
│                                              [Chunk table — chunks + embeddings  │
│                                               + metadata as top-level columns]   │
│                                                          ↓                       │
│                                              [Vector Search index (DELTA_SYNC,   │
│                                               TRIGGERED — manual sync)]            │
│                                                                                  │
│   · · ·  Process 2 then writes chunk_status (completed / failed) back to        │
│        the registry. The registry IS the queue. · · ·                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

*Visual notes for the PPT draw:*
- Use the medallion bands (Bronze / Silver / Gold) as horizontal swim-lanes with the color convention already in the source drawio. Reads cleanly even from the back of the room.
- The **registry box sits visually between Silver and Gold** with arrows both ways: Process 1 *writes* it, Process 2 *reads* and *updates* it. That two-way relationship is the heart of the design.
- The dashed/red arrow from Process 2 back to the registry (status update) should be visually distinct — it's the closed loop that makes idempotence work.
- Keep node labels short. The talk track does the explaining.

---

**Talk track (~2 min):**

1. *Frame (~15s).* "One picture. Bronze, Silver, Gold. The thing to watch as I walk this is the registry table in the middle — it's not just a metadata store, it's also the work queue."
2. *Walk Bronze → Silver (~30s).* "Source PDFs land in two UC volumes. Process 1 discovers what's new by doing a left-anti against the registry — we never re-process what we've already seen. For each new doc, it writes a stub row, then extracts metadata using an LLM, enriches it with reference data, and writes one row per document back to the registry."
3. *Walk Silver → Gold (~30s).* "Process 2 reads the registry filtered to rows where chunk_status is pending. Loads the PDFs, chunks them, materializes metadata onto every chunk, generates embeddings in parallel. Writes the chunk table, and — critically — writes status back to the registry. Completed or failed. The registry IS the queue."
4. *Land the index (~15s).* "Vector Search index syncs off the chunk table. DELTA_SYNC with a triggered pipeline — we sync on demand, not continuously. Two reasons: cost, and we want to control *when* downstream agents see new data."
5. *Bridge (~10s).* "That's the shape. Slide 6 is the design tradeoffs — the choices that earned their keep at production volume."

**Confidentiality checks:**
- No real volume paths, no real table names, no real reference-data source names. Describe by role.
- No real LLM / embedding model names. "An LLM for normalization", "an embedding model" if asked.
- Status field names (`metadata_status`, `chunk_status`) are generic enough to keep — they're describing a pattern, not leaking a schema.

**What NOT to do on this slide:**
- Don't enumerate fields. The registry box shows three example status/retry fields; resist the urge to list more.
- Don't go into the four discovery modes here (TARGET / BACKLOG / DISCOVERY / FORCE_RESET) — if asked, it's a one-liner: "the discovery step has four modes for different operating scenarios; the default is incremental discovery."
- Don't preview the takeaways (slide 9). Land the shape and the loop — the takeaways earn their weight better after slide 6.
- Don't apologize for the diagram density. Architects expect it.

---

### Slide 6 — FSR pipeline — design tradeoffs that earned their keep

**Intent:** five architectural choices that travel beyond this corpus, each framed as *the tradeoff I weighed and the call I made* — not as engagement-specific facts. Audience-takeaway framing: every row gives them something they can apply to their own RAG build. This is the strongest slide for the architect audience.

**Title:** *Design tradeoffs that earned their keep.*

**Sub-line:** Five choices, each with the alternative I rejected and why. Generalizable to any production RAG build on a long-tail document corpus.

**Layout:** dense table — 5 rows, 3 columns (Choice / The alternative I rejected / Why this wins at production volume). One-line takeaway at the bottom.

---

**Slide body — 5-row table:**

| # | The choice I made | The alternative I rejected | Why this wins at production volume |
|---|---|---|---|
| 1 | **Metadata first.** Extract and enrich metadata in its own process before any chunking happens. One metadata row per document, persisted as the contract. | Extract metadata inline during chunking. Simpler code, fewer tables. | Every downstream consumer reads the *same* metadata. No drift between what the search index has and what the agent reasons over. Add a new consumer — they pay zero re-extraction cost. |
| 2 | **Registry as the work queue.** Status fields on the metadata table drive what gets processed next. Process 2 reads `chunk_status = pending`; on success/failure it writes status back. | A separate orchestration queue (e.g. event-driven, separate job state store). | One source of truth for *what's done* and *what's left*. Backfill, incremental, retries, and replays all read the same fields. No "state in two places" debugging at 2am. |
| 3 | **Same code path for backfill and incremental.** Backfill is the first run; incremental is every run after. One notebook, one correctness story. | A dedicated backfill job that diverges from the steady-state code. | The divergence is exactly where bugs live. Once you have *one* path, every fix you ship to incremental automatically applies to any future backfill. |
| 4 | **Hard, lookup-matched IDs for the filter spine.** The field downstream agents pre-filter on is *not* what the LLM asserted — it's matched against a reference source and gets an audit-trail field recording how it was derived. | Trust the LLM's extracted ID directly. Faster, simpler. | LLM-asserted filter values *drift* with the model. Filtering on a hard, lookup-matched ID is deterministic and auditable. Day-one cost; pays back the first time a model update silently changes extraction. |
| 5 | **Metadata duplicated as top-level columns on every chunk.** Chunks are self-contained — agent doesn't need to join back to the metadata table to filter. | Keep metadata only on the parent document; agents join at query time. Smaller chunk rows. | Lets the vector index pre-filter before semantic ranking. Pre-filtering on a top-level column is fast and deterministic; post-filtering after retrieval is neither. The duplication is the price you pay for fast, accurate retrieval. |

---

**Takeaway (one line, bottom):**

> The pattern: **metadata is the contract; the registry is the queue; the substrate has to be trustable before any agent is interesting.**

---

**Talk track (~2.5 min):**

1. *Frame (~15s).* "Five choices. Each one had an alternative I considered. I'll walk you through what I rejected and why — the rejected option is usually the simpler one, which is the part worth understanding."
2. *Walk the table (~2 min).* ~25s per row. For each: name the choice, name the rejected alternative, land the production-volume reason in one sentence. Don't expand beyond the cell content — the table is dense on purpose.
3. *Land the takeaway (~15s).* Read the takeaway line. "Metadata is the contract; the registry is the queue; the substrate has to be trustable before any agent is interesting. The rest of the deck — and the AdHoc QA agent on the next two slides — only works because of these five choices."

**Confidentiality checks:**
- No engagement-specific dollar / time figures. Tradeoff framing is the point, not the engagement P&L.
- No real lookup-source names anywhere in the table.
- "LLM" and "embedding model" stay generic.

**What NOT to do on this slide:**
- Don't oversell. Each row is a *tradeoff* — say what you gave up, not just what you gained.
- Don't pretend the choices are novel. They aren't — most of them are well-known RAG patterns. The value is *which five I picked and why they earned their keep here.*
- Don't drift into the agent. The next two slides are the agent; this slide is the substrate.
- Don't list more than five. If a sixth wants to come in, it goes in the talk track only, or it replaces a weaker row.

**Diagram note (for visual pass):** no diagram — the table is the visual. Keep cell text tight. If a cell wraps to more than 2 lines in the rendered PPT, trim the language.

---

### Slide 7 — AdHoc QA agent — architecture

**Intent:** the conversational agent that sits on top of the FSR pipeline. Engineers ask follow-up questions after a risk assessment runs; the agent reasons over the same Vector Search index the pipeline built, plus a set of role-scoped tools that read from upstream systems. Source diagram: `unit-risk/8. AdHoc QA Agent.pdf`. The slide walks the *shape* of the agent — design choices land on slide 8.

**Title:** *AdHoc QA agent — architecture.*

**Sub-line:** Conversational, persona-aware, grounded in tool outputs. A ReAct loop over a persona-scoped tool list, sharing the same vector index the pipeline built.

**Layout:** full-width architecture diagram with three zones: user / persona context (left), agent core (middle), tools + data sources (right). Minimal annotation on the slide.

---

**Diagram — left-to-right, three zones (must be drawn before the deck goes live):**

```
┌── USER + CONTEXT ───────────┐    ┌── AGENT CORE ────────────┐    ┌── TOOLS + DATA ────────────┐
│                            │    │                       │    │                            │
│  [Engineer (RE or OE)]     │    │  [Agentic framework   │    │   Persona-scoped tool list │
│         │                  │    │   ReAct loop:         │    │   (constructed at startup) │
│         ↓                  │    │   Thought → Action    │    │                            │
│  [Persona + assessment_id] │───►│   → Observe]          │───►│   - Retrieval tool over    │
│         │                  │    │         │             │    │     the Vector Search      │
│         ↓                  │    │         ↓             │    │     index (pre-filtered    │
│  [Streaming HTTP API]      │◄───│  [Frontier LLM]       │    │     on hard equipment-ID)  │
│                            │    │         │             │    │   - Reference-data tools   │
│                            │    │         ↓             │    │     (read upstream systems │
│                            │    │  [Session memory      │    │     via a thin data-       │
│                            │    │   keyed on             │    │     services layer)        │
│                            │    │   assessment_id        │    │   - Assessment-context     │
│                            │    │   within user scope]   │    │     tools (findings,       │
│                            │    │                       │    │     narrative summary,     │
└────────────────────────────┘    └──────────────────────┘    │     event history)         │
                                                          └──────────────────────────┘
                                                                       │
                                                                       ↓ reads (no writes)
                                                          [Vector Search index]
                                                          (built by the FSR pipeline)
```

*Visual notes for the PPT draw:*
- **Three zones, clearly separated.** The boundary between *agent core* and *tools* is the most important visual — it's the grounding boundary. Tools return data; the LLM reasons over it. No tool, no fact.
- The arrow from tools → Vector Search index should land on the *same* index box shown on Slide 4 (the shared substrate). Reinforce the platform claim visually.
- **Persona context flows into the agent at construction time** — not at every request. The tool list is fixed once the agent starts; persona doesn't switch mid-session.
- Keep technology names off the diagram. Roles only — "agentic framework", "frontier LLM", "session memory". The talk track can mention vendor choices if asked.

---

**Talk track (~2 min):**

1. *Frame (~15s).* "Three zones. User and context on the left, agent core in the middle, tools and data on the right. The thing to watch is the boundary between the agent core and the tools — that's the grounding boundary."
2. *Walk USER + CONTEXT (~20s).* "An engineer — a Reliability Engineer or an Outage Engineer — starts a session after a risk assessment runs. The persona and the assessment ID get attached to the session. That persona decides which tools the agent gets."
3. *Walk AGENT CORE (~40s).* "The core is a ReAct loop on top of an agentic framework. Thought → Action → Observe. The framework manages the loop; I didn't write orchestration code. An LLM does the reasoning. Session memory is keyed on the assessment ID but scoped to the user — two engineers asking about the same assessment get separate conversations."
4. *Walk TOOLS + DATA (~30s).* "Tools fall in three buckets: retrieval over the vector index the pipeline built, lookups into upstream reference systems, and reads of the assessment context. The retrieval tool pre-filters on the hard equipment-ID from slide 6 — that's where the pipeline's design choice pays off."
5. *Land the grounding boundary (~15s).* "Every fact the agent states comes from a tool result. The LLM reasons — it doesn't assert. If a tool didn't return it, the agent doesn't claim it. That boundary is the design of this agent."
6. *Bridge (~10s).* "Slide 8 is the design choices — what I'd carry forward."

**Confidentiality checks:**
- No real framework name (the source PDF names a specific framework; on the slide it stays "an agentic framework with a built-in ReAct loop").
- No real LLM name. "A frontier LLM" is enough.
- No real upstream system names. Tools by role only: "retrieval tool", "reference-data tool", "assessment-context tool".
- No vendor names for compute / storage / observability — they're not architectural points.
- Personas (RE / OE) are role names, not customer naming. Keep.

**What NOT to do on this slide:**
- Don't enumerate every tool. Three buckets is enough; the actual tool list would leak source systems.
- Don't talk about the data-services layer in detail. It's a thin proxy — mention it exists, don't deep-dive.
- Don't claim the agent is novel. It isn't — it's a clean application of well-known agentic patterns. The value is *which patterns and why*.
- Don't compare to other agent frameworks by name. Stays out of vendor-comparison territory.

---

### Slide 8 — AdHoc QA agent — design choices that matter

**Intent:** five design choices for grounding an LLM agent on a domain corpus. Same audience-takeaway framing as slide 6 — each row gives the architect something they can apply to their own agent build. Strongest slide for the second half of the deck.

**Title:** *Design choices that matter when grounding an agent on a domain corpus.*

**Sub-line:** Five choices, each with the alternative I rejected and why. Applicable to any LLM agent that has to be trustable inside an enterprise workflow.

**Layout:** dense table — 5 rows, 3 columns (Choice / The alternative I rejected / Why this wins in a regulated / production setting). One-line takeaway at the bottom.

---

**Slide body — 5-row table:**

| # | The choice I made | The alternative I rejected | Why this wins in a production setting |
|---|---|---|---|
| 1 | **Tools are the grounding boundary.** Every fact the agent states comes from a tool result. The LLM reasons; it does not assert. | Let the LLM answer freely and patch hallucinations with prompt engineering. | Hallucinations don't survive contact with engineers who know the data. "Tool result or it didn't happen" is the only posture that earns trust on day one. |
| 2 | **Persona-scoped tool list, built at agent construction.** Each engineer role sees only the tools relevant to their job. Tool list is fixed at startup, not negotiated per turn. | One shared tool list for all roles; let the LLM pick what's relevant. | Access control isn't a prompt concern — it's an architecture concern. Fixed-at-construction means the wrong tool literally cannot be called. Also: smaller tool list = better tool selection by the LLM. |
| 3 | **Session = assessment_id within a user namespace.** Two engineers asking about the same assessment get separate conversation histories. | Globally shared session per assessment (one shared chat per assessment ID). | Conversation context is *user-private* by default. Shared sessions would leak one engineer's exploratory questions into another's transcript. Privacy is a default, not a feature. |
| 4 | **ReAct loop on a managed agentic framework.** I did not write orchestration. The framework owns the loop; I own the tools and the prompts. | Roll a custom agent loop — more control, more flexibility. | Custom orchestration is where most agent builds spend time and ship bugs. The framework's loop is battle-tested. Spend the time on tools and grounding, not on re-implementing ReAct. |
| 5 | **Retrieval pre-filtered on the hard equipment-ID from the pipeline.** The retrieval tool calls the vector index with a deterministic filter before semantic ranking runs. | Semantic-only retrieval over the whole corpus; rely on top-k to surface the right unit's docs. | Semantic ranking alone isn't precise enough at corpus scale — you get adjacent-unit results bleeding in. Hard pre-filter scopes the search to *this* unit's documents before ranking. That's why the pipeline's design choice 4 (hard ID as spine) matters here. |

---

**Takeaway (one line, bottom):**

> The pattern: **tools ground the agent, persona scopes the tools, the framework owns the loop — and the substrate the pipeline built is what makes any of it accurate.**

---

**Talk track (~2.5 min):**

1. *Frame (~15s).* "Five choices. Same shape as slide 6 — what I picked, what I rejected, why it wins in a production setting where the engineers using this know the data better than the model does."
2. *Walk the table (~2 min).* ~25s per row. Lean on row 1 (grounding boundary) — it's the most important. Lean on row 5 (hard-ID pre-filter) — it's the callback to slide 6 that makes the platform story concrete.
3. *Land the takeaway (~15s).* Read the takeaway line. "Tools ground the agent, persona scopes the tools, the framework owns the loop — and the substrate the pipeline built is what makes any of it accurate. Take any of these five home and apply it."

**Confidentiality checks:**
- Same as slide 7. No framework names, no LLM names, no upstream system names.
- Personas (RE / OE) are role names — fine to keep.
- No specific accuracy or latency numbers. Tradeoff framing is the point.

**What NOT to do on this slide:**
- Don't oversell the grounding posture. It's not novel — it's discipline. Say that.
- Don't recommend specific frameworks by name. The audience will ask in Q&A; that's a 1:1 conversation, not a slide.
- Don't list more than five rows. If a sixth wants in, it goes into Q&A.
- Don't drift into evaluation framing. Eval is a deck of its own — acknowledge if asked.

**Diagram note (for visual pass):** no diagram — the table is the visual. Match Slide 6's table styling exactly. The two tradeoff slides should feel like a matched pair.

---

### Slide 9 — Three takeaways that travel

**Intent:** the patterns from this build that generalize beyond *this* corpus. Audience-takeaway framed. Three patterns only — each one big enough to lift directly into another engagement, each one already proven in slides 6 and 8.

**Title:** *Three patterns that travel beyond this build.*

**Sub-line:** What I'd carry into the next production RAG build, regardless of corpus or industry.

**Layout:** three short blocks stacked. One headline + one paragraph + one *"how to spot whether your build needs this"* tag per pattern.

---

**Pattern 1 — Metadata is the contract.**

> Extract and enrich metadata in its own process before any chunking happens. Persist it as one row per document, with status fields that double as the work queue. Every downstream consumer reads the same metadata; nobody re-parses; the substrate stays consistent across producers and consumers.
>
> *You need this when:* you have more than one downstream consumer of the same corpus, or you expect to add one in the next year. The cost is one extra table and one extra pass at ingest. The payoff is *every consumer added later pays zero data work.*

**Pattern 2 — Hard, lookup-matched IDs as the filter spine.**

> Whatever field your agents pre-filter on — don't let it be what the LLM asserted. Match it against a reference source at ingest, carry an audit-trail field that records how it was derived, and lift it to a top-level column on every chunk so the vector index can pre-filter on it before semantic ranking runs.
>
> *You need this when:* retrieval has to be scoped to a *specific* entity (a unit, an account, a project, a patient) and "close enough" semantic match isn't good enough. Common in regulated, technical, or operational domains. The cost is a day of integration with the reference source. The payoff is auditable, deterministic retrieval scope at query time.

**Pattern 3 — Tools are the grounding boundary.**

> Build agents where every fact comes from a tool result. The LLM reasons; it does not assert. Persona-scope the tool list at agent construction so the wrong tool literally cannot be called. Let a managed agentic framework own the loop — spend your time on tools and prompts, not on re-implementing ReAct.
>
> *You need this when:* your agent operates inside an enterprise workflow where the users will catch hallucinations the moment they happen. Which is most enterprise agent builds, honestly. The cost is more upfront tool design. The payoff is the agent earns trust on day one, not after three months of prompt-patching.

---

**Closing line (small, bottom):**

> Three patterns, three different lifecycle stages — ingest, retrieval, agent. None of them are novel. All of them are what *did the work* at production volume on this build.

---

**Talk track (~2 min):**

1. *Frame (~15s).* "Three patterns. Not novel — worth picking up because they're what actually carried the load when this hit production volume."
2. *Walk Pattern 1 (~30s).* Read the headline. Read the *you need this when* line. Land: "if you have more than one consumer on the same corpus, this pays for itself the first time you add the second one."
3. *Walk Pattern 2 (~30s).* Read the headline. Land the callback: "this is the choice from slide 6 that makes the agent on slide 7 actually accurate. The pipeline did the work so the agent could be precise."
4. *Walk Pattern 3 (~30s).* Read the headline. Land: "the discipline is more important than the framework choice. Don't pick a framework first — pick the grounding posture first."
5. *Close (~15s).* Read the closing line. "Take any of the three. They're not a set — each one earns its keep on its own."

**Confidentiality checks:**
- No engagement-specific framing in the *you need this when* lines — they're written for the audience's builds, not this one.
- No vendor names.
- No numbers from this engagement.

**What NOT to do on this slide:**
- Don't add a fourth pattern. Three is what fits in 2 minutes; a fourth waters down the takeaway.
- Don't claim these as Slalom patterns. They're industry patterns; the value is naming them clearly and showing where they earn their keep.
- Don't recommend specific tools / frameworks. Patterns first; tooling is a downstream conversation.
- Don't sell the engineering-practice deck here. That's slide 11's job.

**Diagram note (for visual pass):** light. Maybe a single small icon per pattern (gear, magnet, shield). Otherwise text-only.

---

### Slide 10 — The stack, and the build-time tooling that shipped it

**Intent:** the one slide where tech is named on-screen. Two jobs: (1) give the audience the SME-signal — which platforms / frameworks / models I can speak to from real production experience, not slideware. (2) Name the build-time AI tooling (Claude Code, GitHub Copilot) — because *how* this was built is part of why two components shipped to prod at this scale with the team size it had. This is also the natural lead-in to the engineering-practice companion deck on slide 11.

**Title:** *The stack — and the build-time AI tooling that shipped it.*

**Sub-line:** Vendor-neutral until now on purpose. Here's what's actually under the hood — come find me if any of it is on your roadmap.

**Layout:** two columns. Left column = *production stack* (what runs in prod). Right column = *build-time AI tooling* (what I used to design, write, and review the code). Each column is a short grouped list with one-line role tags. Logos optional if Slalom template has them; otherwise plain text is fine.

---

**Left column — production stack:**

> **Data + pipeline platform**
> - Databricks — Unity Catalog (governance + lineage), Workflows (orchestration), Delta Lake (Bronze/Silver/Gold tables), Spark (pipeline compute), Databricks Vector Search (DELTA_SYNC TRIGGERED, manually synced from a Delta table).
>
> **Agent runtime + serving**
> - AWS Strands — agentic framework (ReAct loop, tool execution, session-store integration).
> - LiteLLM — single LLM gateway in front of frontier models (Claude family for the QA agent; Gemini family for parts of the pipeline). One proxy, one auth, one observability surface for every model call across both components.
> - FastAPI — streaming HTTP API (Streamable HTTP transport for tool/agent events).
> - Amazon ECS on Fargate — container runtime for the agent service.
> - Amazon S3 — managed session store (assessment-scoped within a user namespace).
> - Amazon CloudWatch — logs + operational metrics.
>
> **Embeddings + retrieval**
> - Embedding model: OpenAI `text-embedding-3-large` (3072 dims) called through the same LiteLLM gateway — same auth and observability path as every other model call.
> - Index: Databricks Vector Search, DELTA_SYNC TRIGGERED, pre-filter on the hard equipment-ID column before semantic ranking.

---

**Right column — build-time AI tooling:**

> **Coding co-pilots used in this build**
> - **Claude Code** — primary agent for design scaffolds, larger refactors, multi-file edits, and PR review passes. Where most of the leverage came from on this engagement.
> - **GitHub Copilot** — in-editor completion, inline edits, smaller refactors. Steady-state authoring.
> - **VS Code with Copilot Chat** — the design + review surface; this is where the engineering-practice patterns on the companion deck actually ran.
>
> **What I'd reach out to me about as SME:**
> - End-to-end Databricks RAG (Unity Catalog → Workflows → Delta → Vector Search) at multi-million-chunk scale.
> - LiteLLM as a single-gateway pattern in front of multiple frontier-model vendors — why it earned its keep on a multi-component build.
> - AWS Strands agents in production behind a streaming HTTP API on ECS Fargate, with managed session memory in S3.
> - Running a real engineering team where Claude Code + GitHub Copilot are part of the day-to-day SDLC — what worked, what changed in code review, what changed in design.

---

**Footer line (small, full-width):**

> The deck stayed vendor-neutral so the *patterns* could travel. This slide names the stack so the *expertise* can be reached.

---

**Talk track (~2 min):**

1. *Frame (~15s).* "Last content slide before the close. I kept the body of the deck vendor-neutral on purpose — patterns travel better that way. This is the one slide where I name the stack, so you know what I can actually speak to from production experience."
2. *Walk the left column (~45s).* Group by group. "Pipeline side — Databricks end to end: Unity Catalog for governance, Workflows for orchestration, Delta Lake for the medallion tables, Vector Search for the index — DELTA_SYNC TRIGGERED, so we control when it syncs, not the platform. Agent side — AWS Strands as the agentic framework, LiteLLM as the single gateway in front of every frontier model we use, FastAPI for streaming, ECS Fargate for the runtime, S3 for session memory, CloudWatch for ops. Embedding model is OpenAI `text-embedding-3-large` — same LiteLLM path as everything else, which is the point."
3. *Walk the right column (~45s).* "On the build side — Claude Code did most of the heavy lifting for design scaffolds, refactors, and PR reviews. GitHub Copilot was the steady-state in-editor tool. VS Code with Copilot Chat was the surface where the design and review patterns from the companion deck actually ran. The companion deck on slide 11 is the *how* this got built; this slide is the *what* it runs on."
4. *Close (~15s).* "If anything here is on your roadmap — Databricks Vector Search at scale, Strands agents in prod, Claude Code in a real SDLC — come find me. Slide 11 next."

**Confidentiality checks:**
- Tech vendor names are fine — they're publicly available, and the audience needs them to reach out for SME advice.
- No customer name, no partner-team name on this slide.
- No internal config — no cluster sizes, no model IDs, no account IDs, no IAM roles.
- No proprietary frameworks built on top — describe by role, not by internal name.
- The frontier LLM family is named at vendor level ("Claude family", "Gemini family" via LiteLLM) not at exact model version — model versions change; the SME-signal is the family + the gateway pattern.

**What NOT to do on this slide:**
- Don't turn it into a logo wall — it's a *capability inventory*, not a marketing slide.
- Don't claim depth on tech I touched lightly. Everything listed is something I designed-with or built-on directly, not something I read about.
- Don't pitch Slalom services here — this is personal SME-reach, not a sales slide.
- Don't compare vendors ("X vs Y"). Audience asks comparisons in Q&A; on the slide, just name what's in the build.
- Don't add a third column. Two columns is the visual contract — *runs in prod* and *built it*.

**Diagram note (for visual pass):** clean two-column layout. Optional small platform logos beside each group heading on the left column. Right column stays text-only — the *what I'd reach out for* sub-block is what the audience photographs.

---

### Slide 11 — Close: bridge + question

**Intent:** two jobs in one slide. (1) Signal the companion deck on the engineering-practice side — *design → review → operate when AI is in the loop* — for anyone in the room who wants the deeper "what changed in how I build" version. (2) End with one question that turns the deck into a conversation. Don't summarize; the deck just happened.

**Title:** *One bridge, one question.*

**Sub-line:** The architecture cut is what you just saw. There's a companion cut on the engineering practice that shipped it.

**Layout:** two short blocks. Top = bridge (one paragraph + the companion deck name). Bottom = the closing question, large and centered.

---

**Top block — the bridge:**

> This deck was the architecture cut. There's a companion cut on the engineering practice that produced it — *design → review → operate when AI is in the loop* — covering the five engineering patterns and three artifacts (design scaffold, PR playbook, ops cheat-sheet) that came out of this build. If today's three takeaways landed for you, that one will too. Ping me afterwards.

---

**Bottom block — closing question (large, centered):**

> *Which of the three patterns — metadata as contract, hard-ID spine, or tools as grounding boundary — is the one your next build needs most?*

---

**Talk track (~45s):**

1. *Bridge (~20s).* "Quick signal before the close. This was the architecture cut. There's a companion deck on the engineering practice that shipped it — same engagement, the engineering-discipline angle. Five patterns, three artifacts. Talk to me afterwards if you want it."
2. *Read the question (~15s).* Read slowly. Don't paraphrase. Pause.
3. *Stop talking (~10s).* The slide is a prompt, not a closing statement. Let the room speak first.

**What NOT to do on this slide:**
- Don't summarize the deck. The deck just happened.
- Don't pitch the engineering-practice deck hard. One sentence is enough — architects who want it will ask.
- Don't accept "all three" as the answer to the question. If pushed, follow up with "which one starts in your next sprint?"
- Don't add a thank-you slide after this. *This* is the close.

**Diagram note (for visual pass):** none. White space carries the close.

---

## Backup slides (only if asked)

### Backup B1 — War story: silent ID drift

**Intent:** if Q&A goes deep on "what breaks in prod with AI in the loop" — a real (sanitized) incident where a model update silently shifted how an extracted ID was populated. No loud failure. The only signal was zero-results on the agent side, weeks later. One-slide version.

**Title:** *War story — silent ID drift.*

**Sub-line:** A model update shifted how IDs were extracted. No error fired. The only signal was zero-results on the agent side, three weeks later.

**Layout:** four short blocks stacked. Each block is one beat.

---

- **What shipped.** A routine model update on the metadata extraction step. The validation harness on the change said *"looks fine"* — happy-path tests passed.
- **What broke.** On the next daily incremental, ~166 documents (~1% of the corpus) had their hard equipment-ID field populated with a near-correct but invalid value. No loud failure. The pipeline ran clean. The chunks landed. The vector index synced.
- **What we changed.** The validation harness became a *merge gate* for any change to the extraction step — known-good + known-bad + a regression sample, run before the change can land. The data-quality log added a zero-match-rate alert on the hard equipment-ID field. Same code path for backfill let us re-process the affected ~166 docs from the registry with one notebook run.
- **The lesson (one line).** *AI-generated output reads like working output. "Looks fine" passes happy-path tests. The only way to catch silent failures is a validation contract that runs before the change can land.*

---

**Talk track (~2 min):** walk the four beats in order; ~30s each. Don't editorialize between blocks. Land the one-line lesson last and stop.

**When to use:** if Q&A asks for a concrete prod-failure example, or if the audience is heavy on engineers who'll want the "what broke" detail. Don't volunteer it — it costs slide time elsewhere.

**Confidentiality checks:** ~166 docs / ~1% of corpus is a scale ratio, not a customer number — fine. "Hard equipment-ID field" stays role-level. No model name, no validation-tool name.

---

### Backup B2 — Anonymization disclaimer

**Intent:** open the deck with this slide if presenting to an audience broader than Arch-Hive #2 (e.g. external partners, recordings that may leave Slalom). Skip for the Arch-Hive room itself.

**Title:** *A note on what's in this deck.*

**Sub-line:** This deck is anonymized for Slalom-internal sharing. Please don't forward it outside Slalom.

**Slide body:**

> The architecture, the design choices, and the failure modes in this deck are drawn from a real engagement. Customer name, engagement team names, source-system names, table and field names, lookup-source names, framework names, model names, and tool names have been removed. The framing — large industrial-equipment OEM, two components I designed end-to-end — is the only context kept.
>
> This deck is **Slalom-internal**. Please don't forward it externally, post it, or quote it outside this room without checking first.

**When to use:** open the deck with this slide whenever the audience is broader than Arch-Hive #2.

**Talk track (~20s):** read the second paragraph verbatim. Don't soften it.

---

## Open decisions before filling content

- **Slide count:** eleven main + two backup. Comfortable for ~22 min talk + 10 min Q&A. If the slot is tighter, two collapses are available: (a) merge slides 6 and 8 (the two tradeoff tables) into a single "ten design choices" slide — doable but loses the *pipeline / agent* separation; (b) move slide 10 (tech stack) to a closing reference slide left up during Q&A, and skip walking it live — only if the slot is very tight, because the SME-signal is the point of being in the room.
- **Visual identity:** plain Slalom template. The two architecture diagrams (slides 5 and 7) carry the visual weight; everything else is text or table.
- **Diagram-draw priority order:** Slide 4 overview first (it's the most-referenced visual). Then Slide 5 (FSR pipeline) — source already exists in drawio, lift directly with anonymization edits. Then Slide 7 (AdHoc QA agent) — source exists in PDF, redraw cleanly.
- **Backup B1 (war story) — promote to main deck?** If audience skews "engineering-curious", promote between slides 8 and 9. Pushes everything down one. Decide after first dry-run.
- **Slide 10 vendor-naming scope** — currently names: Databricks (Unity Catalog, Workflows, Delta, Vector Search, Spark), AWS (Strands, ECS Fargate, S3, CloudWatch), LiteLLM (single gateway), OpenAI `text-embedding-3-large` (embedding model), Claude + Gemini families (frontier LLMs via LiteLLM), FastAPI, Claude Code, GitHub Copilot, VS Code. Review before the deck goes live: anything to add, anything to drop (e.g. CloudWatch if too ops-detailed for this audience).

---

## Next step

Fill the two architecture diagrams (slides 5 and 7) into PPT-ready visuals using the source drawio + PDF as starting points, with anonymization edits applied. Then dry-run slides 4 → 6 → 8 in order — those three carry the deck's argument. The rest reads cleanly once those three land.
