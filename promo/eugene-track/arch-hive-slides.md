# Arch-Hive #2 — slide skeleton

> **Source of truth for content:** [artifact-outline.md](artifact-outline.md) Part A (slides 1–6 of that doc), plus the FSR pipeline architecture and the AdHoc QA Agent architecture from `unit-risk/FSR-pipeline-databricks.pdf` and `unit-risk/8. AdHoc QA Agent.pdf`.
>
> **Audience:** Slalom-internal Arch-Hive #2 — architects + senior engineers across delivery teams. Wider than Eugene's circle. They want *what was built, why these choices, what generalizes.*
>
> **Length target:** 14 main slides + 3 backup, ~20 min talk + 10 min Q&A.
>
> **Voice:** "we" for what was built (team effort with the engagement team + customer-side leads). "I" for the synthesis / lessons preview at the end.
>
> **Anonymization:** large industrial-equipment OEM as the framing. No customer name, no partner-team name, no proprietary detail. **No real table names, column names, lookup-source names, or tool names — and no schema enumeration.** Describe by role only (e.g. "hard equipment-ID field", "reference-data lookup", "query-FSR tool"). Numbers (18K docs, 1.09M chunks, etc.) are fine — they're scale, not secrets.
>
> **Relationship to Eugene deck:** this is the *architecture* cut. Eugene deck is the *lessons* cut. Overlap = 1 slide near the end of this deck that previews the Eugene track for anyone in the room who wants the deeper "what changed in how we build" version.
>
> **Status:** skeleton — slide titles + 1-line intent only. No body content yet.

---

## Main slides (14)

### Slide 1 — Title

**Title:** Building a production RAG platform on 40 years of field data — and what made it stick.
**Intent:** set the frame. This is a real engagement, in prod today, at scale. Not a POC.

**Sub-line (under title):** One engagement, in prod today. ~18K documents, two agents on the same pipeline, what generalized.

**Layout:** title slide. Title centered, sub-line one size smaller below. Speaker name + role + date in the footer. No visual.

---

**Talk track (~30s):**

1. *Read the title (~10s).* Verbatim. Pause briefly on "what made it stick."
2. *Land the frame (~15s).* "One real engagement — large industrial-equipment OEM, anonymized. In prod today at production scale. Not a POC, not a slide-ware reference architecture."
3. *Move on (~5s).* Don't read the sub-line aloud; let it set expectation visually.

**What NOT to do on this slide:**
- No agenda. The flow is the agenda; slide 2 sets it.
- No speaker bio. Footer is enough for this audience.
- No customer name, no partner-team name. "Large industrial-equipment OEM" is the framing for the whole deck.

---

### Slide 2 — What this talk covers

**Intent:** one engagement, in prod today. Walk through the architecture, the design choices we landed on, the two downstream agents that share the same pipeline, and the patterns from this build that other Slalom teams can pick up directly.

**Title:** *What this talk covers.*

**Sub-line:** One engagement, four threads, ~20 minutes.

**Layout:** four short bullets, full width. Each bullet maps to a section of the deck.

---

**Slide body — four bullets:**

- **The architecture in one picture** — a data pipeline and two downstream agents sharing one Vector Search index. *(slides 3–6)*
- **The design choices that paid off later** — five at the architecture level, the ones that earned their keep at production volume. *(slide 7)*
- **The two agents on the same pipeline** — conversational QA (built on this engagement) + unit-risk reasoning (built by a separate team on the same pipeline), and what the second one cost compared to the first. *(slides 8–11)*
- **Patterns worth reusing across engagements** — three architecture-level patterns that travel beyond this corpus. *(slides 12–14)*

---

**Footer line:**

> Companion deck on the engineering-practice side — design → review → operate when AI is in the loop — signaled on slide 13.

---

**Talk track (~1 min):**

1. *Frame (~10s).* "Four threads. One engagement, in prod today."
2. *Walk the four bullets (~40s).* ~10s each. Read the bullet; don't expand — the rest of the deck is the expansion.
3. *Close (~10s).* "There's a companion deck on the engineering-practice side — we'll bridge to it near the end." Move on.

**What NOT to do on this slide:**
- Don't preview content from individual slides. The slide-number annotations are a visual aid, not a script.
- Don't introduce the speaker here — slide 1 footer is enough.
- Don't tease the patterns slide (12) — the audience absorbs the patterns better if they earn them by slide 12, not anticipate them by slide 2.

---

### Slide 3 — The business problem

**Intent:** a customer with decades of field service reports, procedure docs, and engineering review cases was carrying long unplanned outages. Goal: convert reactive failures into planned maintenance windows by making 40 years of unstructured field data answerable in seconds. RAG was the right tool — the answer was already written down somewhere; the problem was *finding it across 18K documents.*

**Title:** *The business problem.*

**Sub-line:** Decades of unstructured field data, sitting in PDFs. The answers were already written down — the problem was finding them across ~18K documents in time to act on them.

**Layout:** three short blocks stacked. Problem → cost → why RAG.

---

**Block 1 — The problem:**

> A large industrial-equipment OEM had 40 years of field service reports, procedure documents, and engineering review cases sitting in PDFs across multiple source systems. Field engineers in the planning loop needed to answer questions like *"has this failure pattern been seen on this equipment unit before, and what was done about it?"* — and the answer was usually buried somewhere across ~18K documents.

---

**Block 2 — The cost of not having it:**

> When the answer couldn't be found in time, the failure that followed was unplanned. Unplanned outages on industrial equipment carry long recovery windows and high downstream cost. The business goal was simple: convert reactive failures into planned maintenance windows by making the existing knowledge answerable in seconds.

---

**Block 3 — Why RAG was the right tool:**

> The answer was already written down. The problem wasn't generation — it was retrieval at scale, across heterogeneous unstructured content, scoped to the right equipment unit. RAG with a pre-filtered vector index over the metadata-enriched chunk store is the shape that fits.

---

**Talk track (~1.5 min):**

1. *Set the scene (~30s).* Walk Block 1. Land the persona (field engineers in the planning loop) and the question shape (*"has this been seen before, and what was done about it?"*). The question is what the audience will remember.
2. *Land the cost (~30s).* Walk Block 2. Don't dwell on outage numbers — the qualitative claim (unplanned → planned) is the point.
3. *Land the tool fit (~30s).* Walk Block 3. The line that lands: *"the answer was already written down. The problem wasn't generation; it was retrieval."* Bridge to slide 4: *"Here's the architecture that made it answerable."*

**Confidentiality checks:**
- "Large industrial-equipment OEM" is the only customer framing on this slide. No vertical detail beyond that.
- No outage cost figures, no SLA numbers — qualitative only.
- "Field engineers in the planning loop" — by role; never a real team or persona name.

**What NOT to do on this slide:**
- Don't pitch RAG as universally the right tool. The block 3 framing is specific to this *shape* of problem.
- Don't preview the architecture — slide 4 owns it.
- Don't quote the planning team or any customer-side voice. Generic role framing only.

---

### Slide 4 — Architecture overview *(anchor diagram)*

**Intent:** one diagram. Left = data pipeline (PDFs in Unity Catalog volumes → metadata extraction → chunking + embedding → Vector Search index). Right = two downstream agents sharing the same VS index (AdHoc QA agent, Unit Risk reasoning agent). Data layer and agent layer clearly separated.
**Diagram needed:** yes — the single most important visual in the deck.

**Title:** *One pipeline, two agents, one shared index.*

**Sub-line:** The architecture in one picture. Pipeline on the left builds the index. Agents on the right consume it. The shared index is what makes the platform claim later in the deck possible.

**Layout:** full-width diagram (described below). Three short callouts under the diagram, one per architectural boundary.

---

**Diagram — left-to-right flow, two layers (must be drawn before the deck goes live):**

*Layer 1 — Data pipeline (left half):*

```
[Source PDFs in two UC volumes]
          ↓
  [Process 1 — Metadata extraction (Silver)]
   • LLM-normalized fields
   • Enriched via lookups
   • One metadata table
          ↓
  [Process 2 — Chunking + embedding (Gold)]
   • Recursive PDF chunking
   • 3072-dim embeddings
   • Hard equipment-ID lifted to top-level column
          ↓
  [Vector Search index]
```

*Layer 2 — Agent layer (right half, both arrows originate from the same VS index box):*

```
  [Vector Search index]  ──┐
         │                │
         ↓                ↓
  [AdHoc QA agent]   [Unit Risk reasoning agent]
  (conversational,   (proactive risk signals,
   2 field-eng        narrative + event
   personas)          history reasoning)
```

*Visual emphasis:* a vertical dotted line splits the diagram at the VS index — left = "platform team scope", right = "consumer team scope". That boundary is the slide's point.

---

**Three callouts under the diagram (one line each):**

- **The metadata table is the contract.** Every downstream consumer reads the same enriched fields — no agent does its own PDF parsing.
- **The VS index is the integration point.** Agents don't know about the pipeline; the pipeline doesn't know about the agents.
- **The hard equipment-ID is the pre-filter spine.** Lifted to a top-level column so the VS index can pre-filter before semantic search runs.

---

**Talk track (~2.5 min):**

1. *Frame (~15s).* "One diagram for the architecture. Pipeline on the left, agents on the right, one shared Vector Search index in the middle. Everything else in the deck unpacks one part of this picture."
2. *Walk the pipeline (~50s).* PDFs in two volumes → Process 1 extracts and enriches metadata once → Process 2 chunks and embeds → the index is the output. Land that Process 2 does not re-scan volumes — it reads from Process 1's output. That's the metadata-first design.
3. *Walk the agent layer (~40s).* Both arrows originate from the same VS index. Two agents, different jobs, same retrieval substrate. Name them by role only (conversational QA, proactive risk reasoning) — detail comes on slides 9 and 10.
4. *Land the three callouts (~30s).* Metadata table = contract. VS index = integration point. Hard ID = pre-filter spine. These three are what the rest of the deck is built on.
5. *Bridge (~15s).* "Slides 5 and 6 unpack the pipeline. Slides 9 and 10 unpack the agents. Slide 11 is why this matters — the pipeline is a platform."

**Confidentiality checks (this is the slide most likely to leak detail):**
- No real volume names, catalog/schema names, table names, column names.
- No real lookup-source names — "lookups against reference data" only.
- No real LLM / embedding model names — "a frontier LLM for normalization", "a managed text-embedding model" only.
- No real agent framework / serving stack on this slide — those land on slide 9 with the same role-only treatment.
- Numbers (18K docs, 1.09M chunks, 3072-dim) are scale, not secrets — fine to keep.

**What NOT to do on this slide:**
- Don't put implementation labels on the boxes. The boxes are roles, not products.
- Don't add arrows from the agent layer back into the pipeline. Agents are read-only consumers — that's the platform claim.
- Don't put the persona names on this slide — slide 9 owns that.

---

### Slide 5 — Pipeline · Process 1 — Metadata extraction (Silver)

**Intent:** non-recursive scan of two Unity Catalog volumes → LLM-normalized metadata → enriched via lookups against reference data → one Silver metadata table. **Key architectural concept:** a hard, lookup-matched equipment-ID is the spine for everything downstream (not the LLM's assertion), and every row carries an audit trail of how that ID was derived. **Design call:** metadata first — extract once, enrich once, reuse for every downstream consumer.

**Title:** *Process 1 — Metadata extraction (Silver).*

**Sub-line:** Two volumes in. One enriched metadata table out. Every downstream consumer reads it; nobody re-parses PDFs.

**Layout:** flow diagram (described below), then a short callout for the one schema concept that matters architecturally. One-line design call at the bottom.

---

**Diagram:**

```
[Two UC volumes — non-recursive scan]
            ↓
[LLM normalization — frontier model, page-1 extraction]
            ↓
[Enrichment — lookups joined in parallel against reference data]
            ↓
[Silver metadata table — one row per document]
```

*Visual note:* the enrichment box shows lookups joining in parallel — not sequential. The LLM output is the seed; the lookups fill the rest.

---

**The one schema concept that matters (callout, no field-list):**

> Downstream filtering rides on a **hard, lookup-matched equipment-ID** — not what the LLM asserted. Every row also carries an **audit trail** field that records how its ID was derived (LLM, lookup, fallback). That pair is what makes the substrate trustable at production volume.

---

**Design call (one line, bottom of slide):**

> **Metadata first.** Extract once, enrich once. Every downstream consumer reads the same table. The metadata table is the contract.

---

**Talk track (~1.5 min):**

1. *Frame (~15s).* "Process 1 is metadata extraction. Two volumes in, one enriched table out. Non-recursive scan — we know exactly what we'll find."
2. *Walk the flow (~45s).* Volumes → LLM normalization on page-1 content → lookups joined in parallel against reference data → one Silver table. Land that the LLM output is *the seed*, not the source of truth — the lookups are.
3. *Land the one schema concept (~20s).* Read the callout. Lean on the contrast: *hard ID, not LLM-asserted*. That's the substrate trustability claim in one sentence — and the field most slides downstream call back to.
4. *Land the design call (~10s).* Metadata first. Extract once, enrich once. The table is the contract. Bridge to slide 6.

**Confidentiality checks:**
- No lookup source names — "lookups against reference data" only. Don't characterize what they look up.
- No field names anywhere — the callout is the only schema reference and it stays at the role level.
- LLM = "a frontier model"; no product name.

**What NOT to do on this slide:**
- Don't show a sample row. The role-level callout is enough; sample rows leak detail.
- Don't enumerate the schema. The hard-ID + audit-trail pair is the only field-level point worth making.
- Don't claim 100% extraction quality — the < 0.5% terminal rate lives on slide 8.
- Don't preview the chunking decisions — slide 6 owns those.

---

### Slide 6 — Pipeline · Process 2 — Chunking + embedding (Gold)

**Intent:** does **not** scan volumes — reads Process 1 output filtered to rows still pending or previously failed. Recursive PDF chunking → 3072-dim embeddings via a managed text-embedding model → Delta table backed by Databricks Vector Search. **Design calls:** (a) the hard equipment-ID field lifted to a top-level column so the vector index can pre-filter on it, (b) full metadata duplicated into each chunk for self-containment, (c) parallel claim-based chunking, (d) same code path for backfill + incremental.

**Title:** *Process 2 — Chunking + embedding (Gold).*

**Sub-line:** Reads Process 1's output, not the volumes. Four design calls underneath that single choice.

**Layout:** left = flow diagram. Right = the four design calls, one short block each. One-line consequence at the bottom.

---

**Diagram (left):**

```
[Silver metadata table — filter: status in (pending, failed)]
            ↓
[Recursive PDF chunking — full-document]
            ↓
[Embedding — 3072-dim, managed text-embedding model]
            ↓
[Gold chunk table — Delta]
            ↓
[Databricks Vector Search index]
```

*Visual note:* the input arrow comes from the **Silver metadata table**, not from the volumes. That's the slide's first point — Process 2 never touches the volumes.

---

**Right — the four design calls:**

- **(a) Hard equipment-ID lifted to a top-level column.** Vector Search can pre-filter on it before semantic ranking runs. Filtering on an LLM-generated attribute drifts; filtering on a hard ID is auditable.
- **(b) Full metadata duplicated into each chunk.** Every chunk is self-contained — a retrieval result can be reasoned over without a second lookup. Storage is cheap; second-lookups in agent loops are not.
- **(c) Claim-based parallel chunking.** Workers claim a batch of pending rows, process, release. Predictable throughput at corpus scale; adding workers is linear.
- **(d) Same code path for backfill + incremental.** Backfill is the first run; incremental is every run after. One notebook, one correctness story.

---

**Consequence (one line, bottom of slide):**

> Process 2 reads Process 1. That single boundary is what lets the metadata be the contract — and what lets the second agent on slide 10 ship without re-paying the data work.

---

**Talk track (~2 min):**

1. *Frame the boundary (~20s).* "Process 2 does not scan volumes. It reads Process 1's output — filtered to rows still pending or previously failed. That boundary is the slide's first point."
2. *Walk the flow (~30s).* Silver table → chunk → embed (3072-dim, managed model) → Gold chunk table → Vector Search index. Fast.
3. *Walk the four design calls (~60s).* ~15s each. Lean on (a) — hard-ID pre-filter — since it shows up again on slides 7 and 12. (d) is the *single code path* claim, also recurring.
4. *Land the consequence (~10s).* "Process 2 reads Process 1. That boundary is what lets the metadata be the contract — and what makes slide 10 possible."

**Confidentiality checks:**
- "Hard equipment-ID field" — never the real column name.
- "Databricks Vector Search" is a product name we *can* use; it's the platform, not a proprietary asset. Confirm in dry-run if unsure.
- Embedding model = "a managed text-embedding model, 3072-dim"; no provider name.

**What NOT to do on this slide:**
- Don't dive into the chunking strategy (size, overlap). Implementation-level; not what this audience needs.
- Don't claim end-to-end numbers here — slide 8 owns scale.
- Don't preview the VS sync behavior. If asked, route to slide 8 + the B1 backup.

---

### Slide 7 — Key design choices

**Intent:** 5 bullets at architecture level — the choices that paid off later.
1. **Pre-filter the vector index on a hard equipment-ID field**, not on LLM-generated filters.
2. **Single code path for backfill + incremental** — no divergence between catch-up and steady state.
3. **Metadata-first extraction** — extract once, enrich once, every downstream consumer reads the same fields.
4. **Decoupled DQ job** — separate from ingestion; ingestion shouldn't read its own outputs.
5. **Claim-based parallel chunking** — predictable throughput at corpus scale.

**Title:** *Five design choices that paid off later.*

**Sub-line:** None of these were obvious at the start. All of them earned their keep at production volume.

**Layout:** five rows, full width. Each row: *the choice* — *what it bought* — *what it would have cost not to do it*.

---

**Table:**

| # | The choice | What it bought | The cost of not doing it |
|---|---|---|---|
| 1 | **Pre-filter the vector index on a hard equipment-ID field.** Not on LLM-generated filters. | Deterministic retrieval scope at query time. The agent narrows the search space *before* semantic ranking, not after. | LLM filters drift; recall and precision both move with the model. Filtering by a hard field is auditable and stable. |
| 2 | **Single code path for backfill + incremental.** Same notebook, same logic, claim-based. | Backfill is just a one-time first run of the incremental job. No divergence to maintain. | Two code paths means two correctness stories and two sets of bugs. Most corpus regressions come from this split. |
| 3 | **Metadata-first extraction.** Extract once, enrich once. Downstream consumers all read the same fields. | Every new agent costs less than the last — the enrichment work is already done. The contract is the metadata table. | Each agent re-parses PDFs and re-enriches independently. Three agents in, you have three subtly different versions of the same field. |
| 4 | **Decoupled DQ job.** Validation runs separately from ingestion; ingestion never reads its own outputs. | DQ can fail loudly without blocking the ingestion path. The DQ log is SRE-readable: one row per check, per run. | Ingestion that audits itself is a circular dependency. When DQ slows, ingestion slows. When DQ is wrong, ingestion silently agrees. |
| 5 | **Claim-based parallel chunking.** Workers claim a batch of pending rows, process, release. | Predictable throughput at corpus scale. Adding workers is linear; no coordinator bottleneck. | Without claim semantics, parallel workers either duplicate work or starve. Both break at corpus scale. |

---

**Footer line:**

> Of the five, the *single code path* and the *hard-ID pre-filter* are the two we'd port to a new engagement on day one.

---

**Talk track (~2.5 min):**

1. *Frame (~15s).* "Five design choices that paid off. None were obvious at the start — all of them earned their keep at production volume."
2. *Walk the five (~110s).* ~20s per row. Lean on the *cost of not doing it* column — that's what makes each choice concrete. Don't editorialize between rows.
3. *Land the footer (~15s).* "Of the five, single code path and hard-ID pre-filter are the two we'd port to a new engagement on day one." That sets up slide 12.
4. *Bridge (~10s).* "Slide 11 is the consequence of these five. Slide 12 is the two that travel."

**Confidentiality checks:**
- "Hard equipment-ID field" — never the real column name.
- "Metadata table", "VS index", "DQ log" — generic terms, fine.
- No model names, framework names, or product names anywhere in the table.

**What NOT to do on this slide:**
- Don't expand any of the five into a sub-slide. Each one is one row — detail lives in slides 5, 6, 11, 12 as needed.
- Don't rank them by importance. The numbering is lifecycle order, not priority order.
- Don't apologize for design choices that took iteration to land on. The slide reads as "these worked" — the journey isn't the point here.

---

### Slide 8 — What's in prod today

**Intent:** the scale + quality + integrity numbers.
- ~18K documents indexed end-to-end.
- ~1.09M chunks, 3072-dim embeddings.
- Terminal failure rate **< 0.5%** — all traced to corrupt source PDFs, audited.
- Daily incremental running clean; DQ log SRE-ready.

**Note:** story here is scale + integrity at production volume — not raw throughput.

**Title:** *What's in prod today.*

**Sub-line:** Scale and integrity, not throughput. The numbers that matter for trusting the substrate.

**Layout:** four large metrics in a 2×2 grid. Each tile: the number, the unit, one short qualifier line.

---

**Metric grid:**

| | |
|---|---|
| **~18K** documents indexed end-to-end *Full historical corpus, plus daily incrementals.* | **~1.09M** chunks, **3072-dim** embeddings *Backed by Databricks Vector Search, pre-filtered on a hard equipment-ID.* |
| **< 0.5%** terminal failure rate *All traced to corrupt source PDFs. Audited — not unknown.* | **Daily incremental running clean** *DQ log is SRE-ready: one row per check, per run.* |

---

**Footer line:**

> The story isn't raw throughput. It's that the substrate is *trustable* at production volume — enough that a second agent could ship on top of it without re-validating the data.

---

**Talk track (~1.5 min):**

1. *Frame (~15s).* "What's in prod today, in four numbers. The story isn't throughput — it's integrity at scale."
2. *Walk the grid (~60s).* ~15s per tile. Lean on two: the < 0.5% terminal rate (with the *audited* qualifier — it's known causes, not unknowns), and the DQ log being SRE-ready (the operational claim, not a quality claim).
3. *Land the footer (~15s).* "The point is the substrate is trustable. That's why agent #2 could ship without re-validating the data." Bridge to slide 9.

**Numbers verification (must re-run before deck goes live):**
- 18K docs, 1.09M chunks — re-confirm against `fsr-prod-ops/` trackers in the week of the talk.
- 3072-dim — stable, won't change.
- < 0.5% terminal — re-confirm against the latest DQ log; if it's drifted, update before the talk.

**Confidentiality checks:**
- Numbers are scale, not secrets — fine to keep.
- "Audited" needs to be true in the dry-run — if anyone challenges, the audit trail needs to be one click away.
- No throughput numbers (rows/min) — they invite tooling/cost comparisons this deck isn't trying to make.

**What NOT to do on this slide:**
- Don't add a fifth metric. Four is the visual cap.
- Don't put a dollar figure on cost — not the point of this slide or this deck.
- Don't tell the war story behind the 0.5% here — B1 (silent extractor regression) owns it if Q&A pulls it in.

---

### Slide 9 — Downstream agent #1 — AdHoc QA Agent

**Intent:** conversational agent for two field-engineering personas. **Stack:** Strands agentic framework + Strands workflow, a frontier reasoning model, FastAPI on ECS Fargate, S3-backed session memory, tools exposed via MCP, CloudWatch Logs. **Key design call:** **persona-based tool list at agent construction** — the tools available depend on who's asking. Tool categories (by role, not by name): equipment-master read, FSR retrieval, engineering-cases retrieval, risk-matrix read, assessment-findings read, narrative read, event-master read, event-history read. System prompts maintained per persona by the DS team in Git.

**Title:** *Agent #1 — conversational QA for two field-engineering personas.*

**Sub-line:** Same retrieval substrate as the pipeline. Different reasoning layer per persona, including which tools are even available.

**Layout:** left = agent stack diagram. Right = the persona-based tool design call + tool categories. One-line takeaway at the bottom.

---

**Diagram (left):**

```
[User — one of two field-engineering personas]
            ↓
[FastAPI on ECS Fargate]
            ↓
[Agentic framework — Strands + Strands workflow]
            ↓
[Frontier reasoning model]
   ↔ [Tools exposed via MCP — persona-scoped]
   ↔ [Session memory — S3-backed]
            ↓
[Vector Search index]  ← (shared with the pipeline; same index as slide 4)
            ↓
[CloudWatch Logs — observability]
```

*Visual emphasis:* the VS index box is the same box drawn on slide 4 — reinforces "shared retrieval substrate".

---

**Right — the key design call:**

> **Persona-based tool list at agent construction.** The tools available to the reasoning model depend on who's asking. A persona that can read narratives doesn't necessarily have access to risk matrices. The check happens at agent *construction*, not at tool call time.

**Tool categories (by role, never by name):**

- Equipment-master read
- FSR retrieval
- Engineering-cases retrieval
- Risk-matrix read
- Assessment-findings read
- Narrative read
- Event-master read
- Event-history read

**Operational note:** system prompts are maintained **per persona** by the DS team in Git — versioned, reviewed, and rolled out the same way code is.

---

**Takeaway (one line, bottom):**

> Authorization-by-construction. The agent can't call a tool it wasn't given. The persona shape is enforced before the reasoning loop starts.

---

**Talk track (~2.5 min):**

1. *Frame (~15s).* "Agent #1 is the conversational QA agent. Two personas inside the field-engineering org. Same retrieval substrate as the pipeline — the VS index on this diagram is the same VS index from slide 4."
2. *Walk the stack (~45s).* FastAPI on ECS Fargate → Strands agentic framework + workflow → frontier reasoning model with tools via MCP and S3-backed session memory → VS index → CloudWatch for observability. Keep it brisk — the stack isn't the point; the design call is.
3. *Land the persona-based tool design (~45s).* This is the slide's strongest idea. The tools the model can call depend on who's asking. Persona-scoped at construction time, not at runtime. Read the eight tool categories quickly — the *number* and *granularity* are what land, not each name.
4. *Operational note (~20s).* System prompts per persona, maintained in Git by the DS team. Same review discipline as code. That's the operating story for prompt change management.
5. *Land the takeaway (~15s).* Authorization-by-construction. The agent can't call a tool it wasn't given. Bridge to slide 10.

**Confidentiality checks (this slide has the most named tooling on it):**
- Strands, FastAPI, ECS Fargate, S3, CloudWatch, MCP, Git, Databricks Vector Search are open ecosystem names — fine to use.
- LLM = "a frontier reasoning model". No product/vendor name on the slide.
- Persona names — by role only ("field-engineering personas"); never the real persona names.
- Tool categories — by role only; never the real tool names from the AdHoc QA implementation.

**What NOT to do on this slide:**
- Don't deep-dive MCP plumbing. If asked, route to a 1:1 after the talk.
- Don't promise a specific latency number on this slide — talk it in Q&A only if a number can be quoted accurately.
- Don't enumerate the persona tool lists side-by-side. The eight-category list is enough; the *difference* between personas isn't the talk's point.

**Diagram split decision:** if architects want MCP detail, B-section split (9a stack, 9b persona tool design) is the fallback — flagged in open decisions at the top of the file. Default = single slide.

---

### Slide 10 — Downstream agent #2 — Unit Risk reasoning agent

**Intent:** the second agent on the same pipeline — **built by a separate team**, on the same metadata table and same Vector Search index. Reasons over assessment results, narratives, and event history to surface unit-level risk signals before an outage. **Why it matters for this deck:** it shipped on a **much smaller marginal cost** than agent #1, because the pipeline was already production-ready *and* because a different team could pick it up without re-validating the data. That's the platform claim, made concrete.

**Title:** *Agent #2 — Unit Risk reasoning. Built by a different team. Shipped on a fraction of the cost.*

**Sub-line:** Second agent on the same pipeline, built by a separate team. Same metadata table, same Vector Search index. Their marginal data work was effectively zero — they focused on the reasoning layer.

**Layout:** two short blocks. Top = what the agent does (paragraph + 3-bullet input list). Bottom = the cost contrast with agent #1 (side-by-side compare).

---

**Block 1 — What it does:**

> The Unit Risk agent reasons over the same field-data substrate from a different angle. Instead of answering a question on demand, it surfaces unit-level risk signals — *which equipment units are showing patterns that historically preceded an outage* — so the planning team can convert a reactive failure into a planned maintenance window.

**Inputs (all read from the existing pipeline outputs):**

- Assessment findings (from the metadata + chunk tables)
- Narratives (the unstructured story content already chunked + embedded)
- Event history (joined via the same hard equipment-ID field)

---

**Block 2 — The cost contrast (the platform claim made concrete):**

| | Agent #1 (AdHoc QA) | Agent #2 (Unit Risk) |
|---|---|---|
| Pipeline work | Built it. Parse, enrich, index, validation, prod hardening. | Reused it as-is. No re-parsing, no re-enrichment, no new index. |
| Marginal data effort | Full cost of the pipeline. | Effectively zero. |
| Built by | This engagement team. | A separate team — picked up the pipeline as a substrate. |
| Team focus | Pipeline + retrieval + agent. | Reasoning layer only. |
| Time to ship | Months. | A fraction of that. |

---

**Takeaway (one line, bottom):**

> The pipeline carried agent #1. Agent #2 carried itself — the pipeline was already there. That's the platform claim on slide 11, made concrete.

---

**Talk track (~1.5 min):**

1. *Frame (~20s).* "Agent #2 is the Unit Risk reasoning agent — built by a separate team, on the same pipeline. Same metadata, same vector index. Instead of answering on demand, it surfaces unit-level risk signals before an outage — the planning team uses it to convert reactive failures into planned windows."
2. *Walk inputs (~20s).* Three inputs, all reused from the existing pipeline. Assessment findings, narratives, event history. All joined via the same hard equipment-ID field from slide 5. *Land it: the other team didn't re-parse, didn't re-enrich, didn't build a new index — they read from what was already there.*
3. *Walk the cost contrast (~40s).* Five rows. ~10s each. Land the contrast — agent #1 built the pipeline; agent #2, a different team, reused it. Marginal data effort was effectively zero.
4. *Bridge to slide 11 (~10s).* "That contrast is the platform claim on the next slide, made concrete — and it's strongest *because* a different team picked it up."

**Confidentiality checks:**
- Agent name "Unit Risk" is a role label, not a product name. Fine.
- Inputs by role only — "assessment findings", "narratives", "event history". No real source-system names.
- No specific outage numbers, no specific dollar savings. The contrast is structural, not financial.

**What NOT to do on this slide:**
- Don't show the agent's stack — it's not the point. The point is that the *data work was already done.*
- Don't claim agent #2 was "easy". Its reasoning layer was hard; the platform claim is that the *pipeline didn't have to be re-paid*.
- Don't put time-to-ship in weeks or months on the slide — "months" vs "a fraction of that" is enough. Specific numbers invite scrutiny that doesn't help the point.

---

### Slide 11 — The pipeline is a platform

**Intent:** the generalizable point for this audience. Once parse → enrich → index is solid for *one* agent, the second and third agents pay a fraction of the cost. The reusable layer is what makes that possible. Concrete angle other Slalom engagements can lift directly.

**Title:** *The pipeline is a platform.*

**Sub-line:** The second agent shipped on a fraction of the marginal cost of the first — because the pipeline was already production-ready. That's the platform claim, made concrete.

**Layout:** two short blocks stacked. Top = the claim (one paragraph). Bottom = the concrete evidence (three bullets with rough proportions).

---

**Block 1 — The claim:**

> Once *parse → enrich → index* is solid for one agent, the second agent doesn't re-pay the data work. It picks up the same metadata table and the same Vector Search index, adds its own reasoning layer, and ships. The pipeline stops being a feature of agent #1 and starts being a platform that the next N agents consume.

---

**Block 2 — What that looked like in this engagement:**

- **Agent #1 (AdHoc QA)** — carried the full cost of the pipeline. Parse, enrich, index, validation, prod hardening. Months of work.
- **Agent #2 (Unit Risk)** — reused the metadata table and the VS index as-is. The marginal data work was effectively zero. The team focused on the reasoning layer, not on the corpus.
- **The reusable layer:** the metadata table (one schema, every consumer), the VS index (one retrieval substrate, every consumer), the DQ log (one source of truth on data quality).

---

**Footer line:**

> The claim isn't that the pipeline is generic. It's that for *this corpus shape* — long-tail unstructured field documents with a hard ID spine — the platform paid for itself the second time it was used.

---

**Talk track (~2 min):**

1. *Frame the claim (~30s).* "This is the part of the talk that matters for the people in this room. The pipeline is a platform — once it's solid for one agent, the next agents pay a fraction of the cost." Walk Block 1.
2. *Make it concrete (~60s).* Walk Block 2. Lean on the contrast — agent #1 carried the full cost; agent #2's marginal data work was effectively zero. That's what the platform claim looks like when it's true.
3. *Add the boundary (~20s).* Land the footer. The claim isn't that this pipeline is generic for every corpus — it's that for *this shape of corpus* (long-tail unstructured docs with a hard ID spine), the second use case paid for the first.
4. *Bridge (~10s).* "Slide 12 is the three patterns from this build that travel beyond this engagement."

**Confidentiality checks:**
- Agent names by role only — "AdHoc QA", "Unit Risk reasoning" are framing labels, not product names. Fine.
- No numbers attached to the marginal cost claim — say "effectively zero" and "a fraction of the cost", not a dollar or hour figure.
- Don't name the team that built agent #2.

**What NOT to do on this slide:**
- Don't overclaim. "Pipeline is a platform" is true *for this corpus shape*; the footer holds that line.
- Don't sell the pattern as a Slalom asset here — slide 12 is the patterns slide; slide 13 is the bridge to the Eugene track. This slide is the engagement-specific evidence.
- Don't list the cost numbers from agent #1. The contrast is the point, not the absolute.

---

### Slide 12 — Three patterns worth reusing across engagements

**Intent:** the design-level lessons that travel. Keep this at *architecture-pattern* depth, not implementation depth (the implementation-level lessons live in the Eugene deck).
- **Pre-filter the vector index on a hard ID field, not an LLM-generated filter.**
- **Same code path for backfill + incremental.**
- **Decouple DQ from ingestion; design the DQ log SRE-ready from day one.**

**Title:** *Three patterns worth reusing across engagements.*

**Sub-line:** Architecture-level, not implementation. The implementation-level lessons live in the companion deck on slide 13.

**Layout:** three rows. Each row: *the pattern* — *when it applies* — *what it prevents*.

---

**Table:**

| The pattern | When it applies | What it prevents |
|---|---|---|
| **Pre-filter the vector index on a hard ID field.** Not on an LLM-generated filter. | Any RAG workload where retrieval needs to be scoped to a known entity — a customer, a unit, a project, an equipment item. | LLM-generated filters drift with the model. Hard-ID pre-filter is auditable and stable. Recall and precision stop moving when the model moves. |
| **Same code path for backfill + incremental.** Backfill is the first run; incremental is every run after. | Any pipeline with a large historical corpus and an ongoing daily flow. | Two code paths means two correctness stories and two sets of bugs. Most corpus regressions come from this split. |
| **Decouple DQ from ingestion. Design the DQ log SRE-ready from day one.** | Any data pipeline whose consumers will eventually treat it as a contract. | Ingestion that audits itself is a circular dependency. DQ that runs separately can fail loudly without blocking the ingestion path — and the log is the on-call's first place to look. |

---

**Footer line:**

> Three patterns. None are unique to this engagement — they're the ones that earned their keep here and would earn it again on a different corpus.

---

**Talk track (~2 min):**

1. *Frame (~15s).* "Three patterns worth reusing. Architecture-level only — the implementation-level lessons are the next slide's companion deck."
2. *Walk the three (~90s).* ~30s each. For each row, land all three columns: *the pattern, when it applies, what it prevents*. The *when it applies* column is what makes the pattern portable; the *what it prevents* column is what makes it convincing.
3. *Land the footer (~15s).* "None unique to this engagement. They earned their keep here and would earn it again." Bridge to slide 13.

**Confidentiality checks:**
- Patterns are framed in role terms, not in this engagement's specifics. Fine.
- "A customer, a unit, a project, an equipment item" in the *when it applies* column — generic examples, not real entities.

**What NOT to do on this slide:**
- Don't list more than three. Three is what the audience will remember; five dilutes.
- Don't tie each pattern back to a specific slide number from this deck — the audience just saw them; reinforcement is enough.
- Don't claim these patterns are exhaustive. They're the ones that travel — not the full list of choices made in this build.

---

### Slide 13 — There's a second cut of this for the "how we build" side

**Intent:** signal the Eugene track without re-presenting it. One line: there's a companion deck on what changes in how engineering teams *develop* when AI is in the loop — design-first scaffold, AI-assisted PR playbook, AI-ops cheat-sheet. Available to anyone interested after this talk. Keeps Arch-Hive focused on the architecture story without losing the broader thread.

**Title:** *There's a second cut of this — on how engineering teams build with AI in the loop.*

**Sub-line:** This deck was the architecture story. The companion deck is the engineering-practice story — what changes in design, review, and on-call when AI is in the loop.

**Layout:** single column. One short framing paragraph. Three artifact names listed below. One-line CTA at the bottom.

---

**Slide body:**

> The architecture story is one half of this engagement. The other half is *how the team built it* — the engineering-practice patterns that kept the pipeline shippable while AI assistants were in the loop. The companion deck covers three artifacts that close that loop: design → review → operate.

**The three artifacts (one line each):**

- **AI-assisted design scaffold** — a one-page design teams fill in before the assistant writes a line. Prevents the "design absence" that hides inside AI-assisted work.
- **AI-assisted PR playbook** — author-side prod-readiness checklist + reviewer-side plausibility prompts. Two halves of one artifact.
- **AI-ops cheat-sheet** — operating defaults for AI systems in prod, adopted on day one. Catches the quiet failures that don't page.

---

**CTA (one line, bottom):**

> Available to anyone interested after this talk — ping the speaker for the deck.

---

**Talk track (~1 min):**

1. *Frame (~20s).* "There's a second cut of this engagement. This deck is the architecture story. The companion deck is the engineering-practice story — what changes in design, review, and on-call when AI is in the loop."
2. *List the three (~25s).* Read each artifact name once. Don't unpack — the *names* signal there's a coherent set; that's enough for this audience.
3. *CTA (~15s).* "Available after the talk — grab me if you want it." Don't dwell.

**What NOT to do on this slide:**
- Don't re-present the Eugene deck content here. The whole point is *signal, don't deliver*.
- Don't position the companion deck as more important than this one. They're two cuts of the same engagement, different audiences.
- Don't put the artifact details on the slide — the names are enough; depth lives in the Eugene deck.

---

### Slide 14 — Close + Q&A

**Intent:** one-line summary, one ask, open the floor. Ask: *which of your engagements has a "data exists but isn't answerable" problem? — happy to compare notes.*

**Title:** *Close.*

**Sub-line:** One sentence on what this engagement was. One question for the room.

**Layout:** mostly empty slide. Two centered lines. Q&A label at the bottom.

---

**Slide body (large, centered):**

> **What we built:** 40 years of unstructured field data, answerable in seconds, on a pipeline that two agents already share and a third can pick up cheaply.
>
> **What I'd love to hear:** *which of your engagements has a "data exists but isn't answerable" problem? — happy to compare notes.*

---

**Q&A label (small, bottom):**

> Q&A.

---

**Talk track (~30s + Q&A):**

1. *Read the summary line (~10s).* Verbatim. Don't paraphrase.
2. *Read the ask (~10s).* Slow on "data exists but isn't answerable." That's the phrase that surfaces engagements from the audience.
3. *Open the floor (~10s).* "Happy to take questions — or compare notes 1:1 after." Stop talking.

**Q&A anticipated questions — pre-rehearsed routes:**

- *"How do you handle prompt drift on the metadata LLM?"* → route to B2 (validation harness as merge gate). Known-good cohort + known-bad cohort + regression sample run on every merge.
- *"What broke in prod?"* → route to B1 (silent extractor regression — the ~166 docs / ~1% story). Honest about scale, lean on the *what we changed* beat.
- *"Can we get the source diagrams / can this be shared externally?"* → route to B3 (anonymization disclaimer). Slalom-internal only.
- *"Could the platform handle a different corpus shape — e.g. customer support tickets?"* → Yes for any corpus with a hard ID spine and long-tail unstructured content. The pre-filter pattern (slide 12) is what makes that portable. Avoid promising it works on every shape.
- *"Why Strands and not [other framework]?"* → the choice was made by the AWS engagement team for reasons specific to that engagement — happy to connect anyone interested in that conversation 1:1. Don't litigate the choice on stage.
- *"What's the cost?"* → not on this slide, not in this talk. Route to 1:1.

**What NOT to do on this slide:**
- Don't summarize the deck slide-by-slide. The summary line and the ask are the whole close.
- Don't add a "thank you" slide. This is it.
- Don't accept "all of them" as an answer to the ask — follow up with "which one is closest?"

---

## Backup slides (3)

### B1 — Failure-mode example: silent extractor regression

**Intent:** if Q&A goes deep on "what breaks in prod" — the ~166 docs (~1% of the corpus) with bad equipment-ID values story (no loud failure, only signal is zero-results). One-slide version of artifact §7A.1.

**Title:** *Failure-mode example — silent extractor regression.*

**Sub-line:** A model update shifted how equipment-IDs were extracted. No error fired. The only signal was zero-results on the agent side, three weeks later.

**Slide body — four short beats:**

- **What shipped.** A routine update to the metadata-extraction model rolled into prod. Tests passed — the test corpus didn't exercise the failure mode.
- **What broke.** On the next daily incremental, ~166 documents (~1% of the corpus) had their equipment-ID field populated with a near-correct but invalid value. No loud failure. The pipeline ran clean.
- **How it was caught.** Three weeks later, the QA agent on slide 9 returned zero results for an equipment unit a field engineer knew had documents. That was the *only* signal.
- **What we changed.** The validation harness (B2) became a merge gate for any change to the extraction step. Known-good + known-bad + a regression sample, run before the change can land. The DQ log added a zero-rate alert on the equipment-ID field.

**The one-line lesson:**

> *Silent failures don't page. They show up as a consumer who asks a question and gets nothing back. The validation harness has to be a merge gate, not a post-deploy check.*

**Talk track (~2 min):** four beats, ~25s each. Land the lesson and stop.

**When to use:** Q&A on "what breaks in prod", "how confident are you in the metadata", or anything around quiet failures. Don't volunteer — the main deck is about what works.

**Confidentiality checks:** numbers (~166, ~1%) are scale, not secrets. No real field/column names. "A routine update" — don't say which model, which version, which date.

---

### B2 — Validation harness as merge gate

**Intent:** if Q&A goes deep on "how do you keep an LLM-extracted field stable" — known-good cohort + known-bad cohort + regression sample as a merge gate. One-slide version of the validation pattern.

**Title:** *Validation harness as merge gate.*

**Sub-line:** Three cohorts, run on every change to the extraction step. The harness blocks the merge — it doesn't just observe the deploy.

**Slide body — the three cohorts:**

- **Known-good cohort.** A held-out set of documents with manually verified extractions. Any change to the extraction step must reproduce these results within tolerance. Drift on the known-good cohort = merge blocked.
- **Known-bad cohort.** A held-out set of documents we *know* the extractor used to get wrong. The bar is *no regressions* — a change can fix or maintain, but not re-break a known-bad case.
- **Regression sample.** A random sample from the live corpus, re-extracted on every change and compared to the production result. Drift above a threshold = manual review before merge.

**The operating principle:**

> *The harness is a merge gate, not a post-deploy alarm. A change to the extraction step is blocked at PR review until the three cohorts pass.*

**Why it matters:**

> Without this, every model update is a "hope it works" event. With it, the regression on slide B1 would have been caught before the change landed — not three weeks later via zero-results on the agent.

**Talk track (~1.5 min):** walk the three cohorts (~20s each), land the merge-gate principle (~15s), close on the B1 connection (~15s).

**When to use:** Q&A on "how do you keep an LLM-extracted field stable", "how do you handle model updates", or anything around quality discipline on extraction.

**Confidentiality checks:** cohort sizes (if quoted) are scale numbers — fine. No real test-data identifiers, no real cohort filenames.

---

### B3 — Anonymization disclaimer

**Intent:** for any "can you share this externally" question. Slalom-internal only, anonymized as industrial-equipment OEM, no proprietary detail, numbers are scale.

**Title:** *A note on what's in this deck.*

**Sub-line:** This deck is anonymized for Slalom-internal sharing. Please don't forward it externally.

**Slide body:**

> The architecture, the design choices, and the failure modes in this deck are drawn from a real engagement. Customer name, engagement team names, source-system names, table and field names, lookup-source names, and tool names have been removed. The framing — large industrial-equipment OEM, two agents on a shared pipeline — is the only context kept.
>
> Numbers (~18K documents, ~1.09M chunks, < 0.5% terminal failure) are scale figures, not proprietary detail.
>
> This deck is **Slalom-internal**. Please don't forward it externally, post it, or quote it outside this room without checking first.

**When to use:** open the deck with this slide whenever the recording is on, the audience is broader than Arch-Hive regulars, or the deck is being shared after the talk. Skip for an in-room Arch-Hive session with no recording.

**Talk track (~20s):** read the last paragraph verbatim. Don't soften it.

---

## Open decisions before content fill

1. **Slide count.** 14 main feels right for 20 min. If we need to compress to 12, slides 5 + 6 collapse into one "pipeline architecture" slide and slide 12 folds into slide 11. Confirm 14 vs 12.
2. **Visual identity.** Slalom Arch-Hive template, or custom? Affects diagram styling.
3. **Diagrams needed.**
   - Slide 4 — anchor architecture diagram (pipeline + two agents on shared VS index). **Highest priority.**
   - Slide 5 — Process 1 flow (volumes → LLM extract → lookup enrichment → table).
   - Slide 6 — Process 2 flow (metadata table → chunk → embed → VS index).
   - Slide 9 — AdHoc QA agent diagram (FastAPI / Strands / MCP tools / Claude / session memory).
4. **Numbers verification.** 18K docs / 1.09M chunks / 3072-dim / <0.5% terminal — last verified against `fsr-prod-ops/` trackers in May; re-confirm before deck goes live.
7. **Confidentiality scrub.** No real table names, column names, lookup-source names, or tool names anywhere in the deck. Describe everything by role (e.g. "equipment-master lookup", "hard equipment-ID field"). If a question in dry-run pulls a real name out, that's a content-fix flag, not a Q&A answer.
5. **AdHoc QA detail depth.** Slide 9 has a lot in it (Strands, MCP, persona tools, session memory). Consider splitting into 9a + 9b if architects in the room want the MCP detail.
6. **PPTX source.** `unit-risk/GEV Gen AI Platform Architecture.pptx` was image-only — content not extractable. If we need diagrams from it, we'll need to OCR or get the source file. Decision: do without it for now, request source only if needed for slide 4 diagram.

---

## Next step

Fill slide content in this order — locks the spine first:
1. **Slide 4** — anchor architecture diagram + slide content. Without this slide the deck doesn't work.
2. **Slide 7** — the 5 design choices (most quotable, drives the rest).
3. **Slide 11** — the platform claim (the takeaway for this audience).
4. **Slides 5 + 6** — pipeline detail.
5. **Slides 9 + 10** — agent detail.
6. **Slides 8, 12, 13, 14** — scale numbers, patterns, bridge to Eugene deck, close.
7. **Slides 1, 2, 3** — framing slides last (easier to write once the body is locked).
8. **Backup slides** — write only if a question in dry-run pulls them in.
