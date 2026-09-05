# Discussion Plan: Tao — FSR / SDG Use Case Onboarding

**Format**: 30-min conversation
**Goal**: Show depth of understanding → earn a specific task to own
**My ask at the end**: Own the `query_fsr` Databricks service implementation

---

## Pre-Meeting Mindset

- Tao asked me to read the 4e docs. I did — and went one level deeper (pipeline reference code, app code)
- Tao already briefed me verbally on the ingestion flow — reference that I heard him and found it in the code
- Don't dump everything I know. Pick 2-3 things that signal real comprehension
- Come with a proposal; don't ask "what should I work on?"
- It's OK if Tao doesn't have all answers — the questions themselves show I understand the project

---

## 30-Minute Runsheet

### [0:00 – 2:00] Open — Set the frame

> "Thanks for the time. You suggested I read the 4e FSR docs to get context. I did that, and I have a good picture of where things are. I wanted to walk you through what I understood, and then share where I think I can add real value — and get your input on a couple of open questions."

**Why this works**: Signals homework done, frames it as a two-way conversation, not a presentation.

---

### [2:00 – 10:00] My Understanding of the FSR Work

*Walk through this section — pick 2-3 points, not all of them. Read the room.*

#### What FSR retrieval is trying to do

> "The core goal is: given an equipment serial number and a question about that unit's service history, retrieve the most relevant chunks from its Field Service Report PDFs — and return them with enough metadata that the LLM can reason about timing, event type, and outage context."

#### ⭐ The ingestion flow — and the two-source document discovery (reference Tao's briefing here)

*This is your strongest moment. Lead with "you mentioned this" — it shows you listened AND validated it.*

> "You mentioned the ingestion flow to me earlier — the DS team reads from the SOT, finds the FSR PDFs, goes to the Databricks Volume, chunks them, and loads them into the Vector Search index. I went and found exactly where this lives in the pipeline code, and I also found the tricky part you mentioned — the LLM bringing in more documents than the SOT has."

> "The SOT — which is the `fsr_pdf_ref` reference view — might say a unit has 2 FSR documents. But the pipeline also runs an LLM call on every PDF in the Volume, asking it to count how many times each equipment serial number is mentioned. If a PDF significantly mentions an ESN — even if it's not formally linked in the SOT — it gets tagged to that unit too. That's how you end up with 5 documents instead of 2. The pipeline then merges both sources and ingests everything."

> "In code, that's `esn_identifier.py` — one LLM call per document using `azure-gpt-4o`, with thresholds: at least 5 mentions and at least 10% of all ESN mentions in that PDF. The Delta write then combines the SOT ESNs with the LLM-found ones as the final set."

**Why this lands well**: You're feeding his own explanation back to him, enriched with the actual implementation detail. That's the difference between someone who read the docs and someone who understood them.

#### Chunking — why V3 recursive hierarchical won

> "There were multiple chunking strategies tested. The winner was recursive hierarchical chunking — `chunk_size=4000`, `chunk_overlap=200`. Two reasons: speed (10–20 seconds per PDF vs hours for section-boundary strategies), and quality — it builds a section hierarchy (`section_1` through `section_5`) so each chunk carries structural context. That metadata is useful at retrieval time for ranking and for giving the LLM section-level grounding."

#### Retrieval — HYBRID + criteria

> "Pure vector search (ANN) was the baseline. Adding BM25 keyword search via Databricks native HYBRID improved it significantly. The real lift came from appending the fault criteria text to the query — that pushes Recall@10 to around 79%. Adding DatabricksReranker on top gets Recall@20 to 86.4%. So the full pipeline should be: embed query → HYBRID VS → rerank → hydrate + join metadata."

#### The metadata join (what makes it complex)

> "The results aren't just chunks — each chunk needs to be enriched with three metadata views: the PDF reference table (filename ↔ report ID), the scraped file mapping, and the field vision report table (event details, outage type, status). That last one needs deduplication — there can be multiple rows per (event_id, ESN), and you prefer Completed status over Started over Hold. The filename normalization across those joins is also non-trivial — GUIDs with and without `.pdf`, path-qualified variants."

#### What I noticed about the current implementation

> "The data-service today has a partial implementation — batch HYBRID retrieval with pre-computed embeddings from the heatmap table. It's missing: on-the-fly embedding for arbitrary queries, reranking, full chunk hydration from Delta, and the three-view metadata joins. The tool spec covers all of that — so there's a clear gap between where things are and where they need to be."

---

### [10:00 – 15:00] What I Think Should Be Built

*Propose the plan — keep it crisp. This is not a deep dive, just the shape.*

> "The way I see it, the work splits into two tracks:

> **Track 1 — Ingestion pipeline**: PDF → chunking → ESN extraction → Delta table → VS index sync. The DS team has reference code for this. It's a Databricks job, probably triggered on a schedule or on file arrival. This is more ops/infra.

> **Track 2 — Query service**: The `query_fsr` REST endpoint. This is what the data-service actually calls. It needs to: take a serial number + query, embed the query via LiteLLM, run HYBRID VS, rerank, hydrate chunks from Delta, join the three metadata views, return a structured response. The DS team has reference code for this too — it's working Python — but it needs to be packaged as a proper hosted service."

**Pause here and ask**: "Is that roughly how you're thinking about the scope, or is there a different split?"

---

### [15:00 – 22:00] Open Questions — I Need Your Input

*These show I've thought carefully. Tao may or may not have answers — that's fine.*

#### Hosting mechanism (most critical)
> "The biggest open question for me is how the `query_fsr` service gets hosted on Databricks. Databricks Apps? Model Serving with a pyfunc wrapper? Or something else? That decision drives the packaging — whether we use Docker, a pyproject.toml, or just workspace notebook files."

**Why this matters to you**: Blocks ADR-001, which blocks the actual service structure.

#### Reranking availability
> "DatabricksReranker gave a meaningful recall lift in the experiments, but I want to confirm — is `databricks-rerank` available in the Databricks Model Serving runtime, or does it need to be called separately? The reference code doesn't include it in the query path yet."

#### Ownership and division of labor
> "Before I propose what I take on — can you clarify who owns what right now? Specifically:
> - Ingestion pipeline (PDF → Delta → VS): DS team, DEV team, or Databricks team?
> - The FSR metadata extraction pipeline (the 3-stage scraping/normalization/enrichment): is that DS-owned and already running in prod, or still a POC?
> - The production Unity Catalog tables (`vaid.*`, `vgpd.*`): who has write access and who approves schema changes?
> - The VS endpoint (`pw-ser-sdg-vector-search`): is there an infra/ops owner I need to coordinate with for index changes?"

#### Write access and approvals
> "I have read access to the workspace already. What I need to understand is:
> - Do I have or can I get write access to dev workspace tables when I start building?
> - Access to the LiteLLM gateway (`dev-gateway.apps.gevernova.net`) for query embedding calls — is there a token/key I need?
> Is there a ticket or request process for these, or do you handle it directly?"

#### Priority consumer
> "For the `query_fsr` service — which consumer matters most first? The RE risk evaluation pipeline calls it with specific issue prompts and needs ranked results. The Q&A agent path might call it with free-text queries. The requirements are slightly different (k, latency, response shape). What should I optimize for first?"

---

### [22:00 – 27:00] My Proposal

*Make a specific ask.*

> "Based on everything I've read, here's where I think I can add value immediately:

> I'd like to own the `query_fsr` Databricks service — take the DS reference code, productionize it into a proper hosted REST service, write tests, and get it to the point where the data-service can call it. It's a well-scoped task, the logic is already proven by the DS experiments, and it's exactly the kind of Databricks document-processing work I want to build depth in.

> The one thing I need from you to unblock me is the hosting mechanism decision. Once I know whether we're targeting Databricks Apps or Model Serving, I can set up the folder structure and start scaffolding.

> If the ingestion pipeline is also unowned, I'm happy to look at that in parallel — but I'd start with the query service since that's what unblocks the end-to-end flow."

---

### [27:00 – 30:00] Agree on Next Steps

Close with concrete next steps from both sides:

**My commitments**:
- [ ] Share this conversation plan / written summary after the call if useful
- [ ] Once hosting is decided, scaffold the service structure within the week
- [ ] Set up a follow-up check-in (1 week out?)

**Ask from Tao**:
- [ ] Hosting mechanism decision (or who to ask)
- [ ] Clarity on ownership: ingestion pipeline, metadata extraction pipeline, production tables, VS endpoint
- [ ] Write access to dev workspace tables + LiteLLM gateway key
- [ ] Intro to Databricks team if needed for ADR answers
- [ ] Any existing Slack/Teams channel for SDG use case coordination

---

## Backup Talking Points

*If conversation goes in a different direction — pull from these.*

### ⭐ On the SOT vs LLM document discovery (Tao's briefing — validate this)

> "You mentioned the DS team does something clever beyond just reading the SOT — when the SOT doesn't have all the documents, the LLM brings in more. I found that in the pipeline code. It's `esn_identifier.py` — one LLM call per PDF, using `azure-gpt-4o`, to count how many times each ESN is mentioned across the document. If a PDF mentions a serial number at least 5 times and it's at least 10% of all serial number mentions in that doc, it gets tagged to that unit — even if the SOT doesn't formally link them. So the final ingested set is the union of what the SOT says and what the LLM found. That's how you go from 2 docs to 5."

*Use this if Tao brings up the LLM/SOT topic, or to proactively show you connected his verbal description to the code.*

---

**⭐ Live demo steps — run these in Databricks before the call and have results ready to share:**

**Step 1 — See SOT PDF counts per ESN**
```sql
SELECT
    esn,
    COUNT(DISTINCT PDF_name) AS sot_pdf_count
FROM vgpd.fsr_std_views.fsr_pdf_ref
GROUP BY esn
ORDER BY sot_pdf_count DESC
```
> What to point out: **1,812 PDFs have null ESN in the SOT** — these can't be linked to any unit via the SOT alone. Also look for "NO ESN" and blank entries. This is why the LLM approach is essential, not optional.

**Step 2 — See LLM-discovered PDF counts per ESN (from the ingested chunk table)**
```sql
SELECT
    generator_serial,
    COUNT(DISTINCT pdf_name) AS llm_pdf_count
FROM main.gp_services_sdg_poc.field_service_report
GROUP BY generator_serial
ORDER BY llm_pdf_count DESC
```
> What to point out: compare `llm_pdf_count` here against `sot_pdf_count` from Step 1 for the same ESN — the difference is documents the LLM found that the SOT didn't link.

**Step 3 — Show ESNs where LLM found MORE PDFs than the SOT**
```sql
SELECT
    s.esn,
    s.sot_pdf_count,
    c.llm_pdf_count,
    c.llm_pdf_count - s.sot_pdf_count AS gap
FROM (
    SELECT esn, COUNT(DISTINCT PDF_name) AS sot_pdf_count
    FROM vgpd.fsr_std_views.fsr_pdf_ref
    WHERE esn IS NOT NULL
    GROUP BY esn
) s
JOIN (
    SELECT generator_serial, COUNT(DISTINCT pdf_name) AS llm_pdf_count
    FROM main.gp_services_sdg_poc.field_service_report
    WHERE generator_serial IS NOT NULL
    GROUP BY generator_serial
) c ON s.esn = c.generator_serial
WHERE c.llm_pdf_count > s.sot_pdf_count
ORDER BY gap DESC
```
> What to say: *"For these ESNs, the LLM found more PDFs than the SOT formally links. The gap column is the number of extra documents recovered."*

**Step 4 — Show PDFs the SOT couldn't link but the LLM did (join via s3_filename)**

> Note: `s3_filename` in `fsr_pdf_ref` stores the bare GUID (e.g. `00576c50-5466-41a7-af6d-070c903e5cbd`) — direct match to `pdf_name` in the chunk table.

```sql
SELECT DISTINCT c.pdf_name, c.generator_serial, s.PDF_name AS human_readable_name
FROM main.gp_services_sdg_poc.field_service_report c
JOIN vgpd.fsr_std_views.fsr_pdf_ref s
    ON c.pdf_name = s.s3_filename
WHERE s.esn IS NULL
AND c.generator_serial IS NOT NULL
ORDER BY c.generator_serial
```
> What to say: *"These are PDFs with no ESN in the SOT at all — the SOT can't link them to any unit. The LLM found ESN mentions inside the PDF text and linked 967 of them to 611 distinct ESNs."*

---

**What these 3 steps prove — the point to make to Tao:**

> "The SOT alone is not enough to know which PDFs belong to which unit. 1,812 PDFs in the SOT have no ESN at all. I ran a query joining those null-ESN PDFs against the chunk table — the LLM successfully linked **967 of them to 611 distinct ESNs**. Without the LLM scanning the full PDF text, those documents would be completely invisible to every unit's retrieval pipeline. The LLM approach isn't just a nice-to-have — it's recovering nearly 1,000 documents the SOT can't account for."

**Follow-up question to ask Tao (shows production thinking):**

> "Has anyone validated a sample of the LLM-discovered links against ground truth? The ≥5 mentions + ≥10% threshold filters noise, but if the LLM is hallucinating ESNs in some PDFs, we could be surfacing wrong documents to the RE/OE workflow — and wrong documents are harder to catch than missing ones."

*This is worth raising because non-determinism at ingestion time is manageable (it runs once per PDF, not per query), but correctness of the links hasn't been validated from what we've seen in the reference code.*

---

### On LiteLLM / embedding
> "The DS reference code uses on-the-fly LiteLLM embedding at query time — the same model as ingestion (`azure-text-embedding-3-large-1`, 3072 dims). That's good because it handles arbitrary free-text queries, not just the pre-computed heatmap prompts. The current data-service is limited to those pre-computed embeddings."

### On multi-ESN documents
> "One interesting complexity in the data: some FSR PDFs cover multiple generators. The pipeline handles this by writing one Delta row per ESN per chunk — so an equality filter on `generator_serial` correctly surfaces all chunks for that unit even if the PDF covers others."

### On why a separate Databricks service (not extending data-service)
> "The architecture decision is to keep the retrieval logic in Databricks, not pull it into the data-service. That keeps the embedding and VS calls collocated with the data, avoids shipping large result sets over the wire, and means each tool (query_fsr, query_er, etc.) can evolve independently."

### On the 4-table join
> "The full metadata enrichment joins: chunk table → fsr_pdf_ref → fsr_scraped_file_mapping_ref → fsr_field_vision_field_services_report_psot. The last one (psot) is the business-level report with outage details. You need all four to return a result the LLM can reason about — not just raw chunk text."

> "I also now understand what's in `fsr_scraped_file_mapping_ref` — that's the output of a separate 3-stage pipeline: pdfplumber first-page extraction, LLM normalization to a 15-field schema (ESN, equipment IDs, event type, project IDs, outage dates), and then IBAT + Event Vision enrichment to fill blanks. So those 'scraped' metadata fields are actually LLM-normalized and enriched, not just raw scraped text."

### ⭐ On the FSR metadata extraction pipeline (new from DS team docs)

> "Something I didn't know from the reference code alone — the `fsr_scraped_file_mapping_ref` table isn't just scraping. It's a full 3-stage pipeline: Stage 1 uses pdfplumber to extract key:value pairs from the first page of each FSR PDF. Stage 2 sends those in batches of 50 to an LLM — using litellm against the GE gateway — to normalize them into a strict 15-field schema with a controlled vocabulary for Event Type. Stage 3 is PySpark enrichment: left-joins with the IBAT Equipment Master to fill missing equipment attributes, and then the Event Vision SOT to backfill project IDs and outage dates."

> "That means IBAT and Event Vision aren't just consumed by the structured tools (`read_ibat`, `read_event_master`) — they're also baked into the FSR metadata at ingestion time. So even the unstructured path has structured enrichment behind it."

> "One data quality thing worth knowing: the FSR Number field is largely null in pre-2016 FSRs — those documents just didn't include it. The team hasn't identified a way to recover that field yet."

---

## What to Suggest Tao Look At

*If he asks what he should review or share with you.*

1. **ADR-001 answer — hosting mechanism**: This is the #1 unblocking decision. Anything he can share from Databricks team on this.
2. **Write access + LiteLLM gateway key**: Already have workspace read access. Need write access to dev tables and the LiteLLM API key to run the query pipeline end-to-end.
3. **The full tool spec PDF** (`4e-query-fsr-tool-specs.pdf`) — confirm it's the authoritative spec or if there's a newer version.
4. **Who owns the production tables**: `vaid.ai_std_con_field_service_report.*` — understanding the prod catalog vs dev catalog split is important before writing any ingestion code.
5. **Existing Databricks jobs / pipelines**: Is there already a job running for FSR ingestion, or is the index populated ad-hoc? Important for understanding what exists before building.
6. **Status of the metadata extraction pipeline**: The DS team ran a POC of the 3-stage scraping pipeline on 230 FSRs from 2016. Is that pipeline productionized, or is `fsr_scraped_file_mapping_ref` still being populated ad-hoc? This affects whether we need to build/maintain that pipeline or just consume it.

---

## Creative Moves — How to Make the Work Land for You

*These are things you can proactively offer that don't require Tao to make a decision. They create momentum and put your name on something visible immediately.*

---

### Move 1 — "I can have a working notebook by end of week" ⭐ (strongest move)

The hosting decision (ADR-001) is blocking the full service build. But nothing blocks you from writing a **working Databricks notebook** that does the full `query_fsr` pipeline end-to-end: embed query → HYBRID VS → chunk hydration → metadata joins → structured response.

Say this:
> "While the hosting decision is being figured out, I don't want to sit still. I can take the DS reference code and wire it into a working notebook that runs the full query pipeline against the actual Vector Search index. It won't be a hosted service yet, but it'll be a working, shareable proof of concept that the team can run and verify. I can have that by end of week — does that sound useful?"

**Why this works**: It's concrete, time-boxed, doesn't block on anyone else, and it puts your name on the first working end-to-end demo of the full spec. That's a memorable contribution. It also naturally leads to "now let's productionize it" — which is the task you want.

---

### Move 2 — Offer the architecture diagram (creates a shareable artifact)

Turn what you learned — especially the two-source ingestion flow Tao described — into a clean visual the whole team can use. Most engineers love having someone else do this.

Say this:
> "One thing I noticed is that the ingestion flow — the SOT plus LLM document discovery — isn't drawn up anywhere cleanly. I can put together a simple architecture diagram covering ingestion and the query pipeline. Something the team can use in design reviews or when onboarding the DEV team. Would that be useful to share in the project channel?"

**Why this works**: It's low-risk for Tao to say yes, it's visible to more people than just him, and it positions you as the person who understands the architecture well enough to draw it.

---

### Move 3 — Ask to be added to the inner loop (gets you in the room)

The most important career move in a project like this is being in the room where decisions happen. Don't wait to be invited.

Say this:
> "Is there a Slack channel or Teams space where the SDG use case work is being coordinated? I want to make sure I'm seeing the Databricks team's answers to the open questions as they come in, so I'm not blocked."

**Why this works**: Gets you access to information before it gets filtered. You'll hear about decisions, blockers, and priorities in real time — and you can react faster than someone waiting for a summary.

---

### Move 4 — Offer to take the ADR questions to the Databricks team yourself

You've already written up the open questions (ADR-001 through ADR-005). Instead of waiting for Tao to relay them, offer to own that conversation.

Say this:
> "I've written up the open questions we need answered from the Databricks team — hosting mechanism, reranking availability, auth pattern, ingestion trigger. If it's helpful, I'm happy to take those questions directly to whoever owns that on the Databricks side, rather than having them filter through you. Would you be comfortable making that intro?"

**Why this works**: It shows initiative, removes work from Tao's plate, and gets you a direct relationship with the Databricks team. That's how you become indispensable — you're the person who talks to everyone.

---

### Move 5 — Name a specific gap only you can fill right now

There's one thing you know that probably no one else on the DEV team does: the reference pipeline code. The DS team wrote it but the DEV team likely hasn't read it carefully. You have.

Say this:
> "I also went through the DS team's reference pipeline code — not just the docs, but the actual Python. There's a lot in there that isn't obvious from the docs alone — the ESN extraction logic, how the Delta schema is structured, the multi-ESN row duplication pattern, the filename normalization quirks. I can write that up as a technical handoff doc so the DEV team doesn't have to reverse-engineer it. That would save real time when implementation starts."

**Why this works**: You're offering to translate the DS team's work into something the DEV team can use — that's a bridge role, and bridge roles are hard to argue against. It also makes your name synonymous with "the person who understands the pipeline."

---

### The One Line That Ties It Together

If you can only say one thing to make the work land, say this at the end:

> "I don't want to wait for all the decisions to be made before I start contributing. Point me at the thing I can move on right now, and I'll have something to show you by next week."

That's the line that gets you a task.

---

## After the Call — Refinement Checklist

- [ ] Note which questions Tao answered / didn't answer
- [ ] Update ADRs with any decisions from this conversation
- [ ] Update this doc with agreed next steps
- [ ] If hosting decided → set up `databricks_layer/services/query_fsr/` scaffold

---

*File: `internal/comms/tao-discussion-plan.md` — update after each discussion*
