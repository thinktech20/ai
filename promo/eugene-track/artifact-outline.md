# AI in Production — Combined Package (Arch-Hive #2 + Eugene Artifact)

> **One source, two slice depths.**
> - **Top half (slides 1–N)** = Arch-Hive #2 talk — wider Slalom audience. Architecture story, what was built, why these choices.
> - **Bottom half (slides N+1 → end + appendix + companion 1–2 page write-up)** = Eugene-grade material — lessons, guardrails, prod patterns, what teams should do differently.
>
> Anchor case study throughout: a recent client engagement — large industrial-equipment OEM, 40 years of unstructured field data, GenAI-driven early-warning signals. Anonymized for Slalom-internal sharing (no client names beyond the anchor framing; no proprietary detail).
>
> **Voice:** "I" for the analysis, the lessons, the synthesis presented here. "We" for what was built — the pipeline was a team effort with the AWS engagement team and client-side leads.

**Status:** outline v0 — sections 1–6 reframed per May 14 review; section 7 split underway (7A current, 7B pending Eugene-transcript pass).

---

## Part A — Arch-Hive #2 (architecture story, ~20 min)

1. **Why this talk.** Most RAG / agent decks talk about *what to build*. This one is about *what happens after you ship* — the failure modes, the retrofits, the patterns that earn their keep in week 6 of production, not in the POC. The case study is one engagement; **the audience is Slalom** — what we can take from one engagement and reuse across many.
2. **The business problem.** A client with decades of field service reports, procedure docs, and engineering review cases was carrying long unplanned outages — reactive failures costing years of equipment downtime. The goal: use 40 years of unstructured field data to convert reactive failures into planned maintenance windows. RAG was the right tool because the answer to most operator questions was already written down somewhere; the problem was *finding it across 18K documents in seconds*.
3. **The architecture.** One diagram. Data pipeline (PDF → parse → enrich → chunk → embed → vector index) + downstream agents (an ad-hoc Q&A agent, a unit-risk reasoning agent). Data and agent layers labeled.
4. **Key design choices.** 4–5 bullets at architecture level: claim-based parallel chunking, single code path for backfill + incremental, metadata-first extraction, pre-filter the vector index on a hard ID field rather than letting the LLM filter, separate DQ validation job (decoupled from ingestion).
5. **What's in prod today.** ~18K documents indexed end-to-end, ~1.09M chunks, 3072-dim embeddings in Vector Search, terminal failure rate under 0.5% (all traced to corrupt source PDFs, audited). The story here is *scale + quality + integrity at production volume* — not throughput optimization.
6. **Where this *pattern* goes next.** The same data pipeline is being reused as the grounding layer for two downstream agents. The point for this audience: *the pipeline is a platform.* Once the parse → enrich → index path is solid for one agent, the second and third agents pay a much smaller cost. Generalizable lesson: build RAG plumbing as a reusable layer, not a per-agent silo.

→ *Stop here for Arch-Hive Q&A.*

---

## Part B — Eugene cut (lessons, guardrails, patterns)

> Tone shift: less "what was built", more "what teams should do differently when building agents / RAG in production." This is the slice Eugene asked for: **issues, practices, guardrails** — broader than just one system. Two categories below:
>
> - **7A** — *Building AI systems that run in production.* The system itself: extraction, retries, secrets, observability, repair tooling.
> - **7B** — *Building **with** AI: how engineering teams develop when agents are in the loop.* Anchored on what I watched the partner team — a ~10-engineer cloud-services team building the unit-risk agent on the FSR pipeline I led — spend on long hours and weekends pushing a feature that read well in dev and broke down on contact with real production data. The templates below would have prevented most of it.

7A. **Five things that bit us in prod — the system side.** Concrete failures, not theory.

   ### 7A.1 LLM extractor regressions are invisible until queries return zero results

   We use one extracted field as the **only pre-filter** on our vector index. When the LLM that produces that field drifts (prompt change, model swap, an edge-case PDF), nothing fails loud — embeddings still compute, the index still syncs, the pipeline reports green. The first signal is a downstream user typing the right question and getting **zero hits**.

   *What we saw in our corpus:*
   - ~166 documents (~1% of the corpus) had short-numeric IDs in the ESN field that turned out to be **project IDs, IBAT IDs, or work-order numbers** leaking through — visible as sequential clusters (`10872`, `10873`, `10874`…) and the same ID repeated across many unrelated documents. Numeric ESNs *can* be valid (non-GT equipment families use numeric serials legitimately), which is exactly why this failure mode is hard to spot from logs — the value looks right.
   - A subset of source PDFs had scan-quality digit misreads baked into the text layer (e.g. `297…` rendered as `277…`). The LLM faithfully read what the text said. Looks valid, passes any format regex — only detectable by cross-checking against a second source for the same document.
   - Documents with redacted fields (`XXXXXX`) wholesale fell back to project IDs, mass-migrating away from the correct value.
   - Privacy template tokens (`{UK_NATIONAL_INSURANCE_NUMBER}`) leaked through as if they were valid IDs.

   *The trap:* every failure mode above produces a **valid-looking string** that passes type checks and writes cleanly. There's nothing to alert on. You only find out when a user complains.

   *Lesson:* if an LLM-extracted field is on the query path, it is not a side-effect — it is your **schema**. Treat changes to it like a schema change: known-good cohort + known-bad cohort + regression sample as a mandatory merge gate. Negative-prompt rules ("reject pure-numeric unless equipment type allows it", "reject template tokens") belong in the prompt, not in the reviewer's head.

   ---

   ### 7A.2 Terminal failures get re-attempted forever if you only have per-run retry caps

   Our pipeline had a per-run `LIMIT` on retries — pulled N failed rows per pass and tried them again. That's fine when failures are transient. It is **wasteful and noisy** when failures are terminal (corrupt source PDF, image-only document, gateway error that's actually permanent).

   *What we saw:*
   - 77 documents were terminally failed (50 corrupt `No /Root`, 2 `Unexpected EOF`, rest split across image-only / parse errors / partial embeddings).
   - The DQ log was re-emitting ~70 rows/day for the same standing 72 docs — every daily run, same failures, fresh log entries. SRE couldn't tell new from old.
   - Compute was being spent re-parsing the same corrupt PDFs every run.

   *Fix:* a **lifetime retry counter** per row (`metadata_retry_count INT`), gated by `COALESCE(retry_count, 0) < MAX_RETRIES`. Increment on failure MERGE, reset to 0 on success MERGE. Once a row exhausts lifetime attempts, it stays terminal — zero compute on subsequent runs, one log entry, then silence.

   *Lesson:* per-run limits answer "how much should I do this run?" — they don't answer "should I have given up by now?" You need both. The lifetime gate also forces a **re-ingestion runbook**: when SRE wants to retry a terminal failure they explicitly reset the counter — that's an audit trail, not a silent accident.

   ---

   ### 7A.3 Secrets in source under deadline pressure — every time, more expensive than expected

   The morning of production backfill, the secret scope wasn't ready. Three LiteLLM API keys (dev / prod / qa+stg) went into `databricks.yaml` to unblock the run. Plan: rotate after launch.

   *What actually happened:*
   - The keys sat in source for two weeks before the secret scope path was ready on the platform side.
   - Three rotation conversations. Each one had to re-verify which deployment had which key.
   - The fix is now a one-line yaml substitution (`${{ secrets.<scope>.<key> }}`) — but the cost was the **review burden** of every PR touching that file in between, and the rotation work itself.

   *Lesson:* the "we'll fix it after launch" path almost always costs more than blocking on the secret scope before launch. The cheapest moment to plumb secret-scope substitution is **before** the first deployment that needs the key — there's no historical key in source to rotate, no audit conversation, no review caveat.

   *Slalom-playbook version:* secret scope, env-templated yaml, and the key-rotation runbook are **launch checklist items**, not post-launch hardening. If the platform team isn't ready, that's the launch blocker — not "let's just hardcode and rotate later."

   ---

   ### 7A.4 A DQ log that's not SRE-ready is observability theater

   We had a 41-check Data Quality validation job writing to a `data_quality_log` table from day one. It looked like observability. In practice it was unusable for the team that would own it after handoff, for three reasons:

   1. **Recurring failures re-logged every run.** 70 rows/day for the same 72 standing failures (see 7.2). SRE couldn't see new failures through the noise.
   2. **No failure category.** Every row was just `(document_id, check_name, error_string)`. SRE had to read the error text to decide whether it was paging-worthy or not — every time, by hand.
   3. **No human-readable doc identifier.** The error rows had `volume_path` (an internal storage path) but not `pdf_name` (the name the business uses). SRE had to join back to a reference table to file a ticket.

   *Fix shipped together as one PR:*
   - **De-dup recurring terminal-failure rows** — pre-load the `(document_id, check_name)` pairs already logged in the last N days, skip them.
   - **`failure_category STRING` enum column** — `corrupt_source`, `image_only_or_no_text`, `pdf_parse_error`, `partial_embed`, `gateway_error`, `unknown`. Only `unknown` pages on-call. Mapping happens at write time via a tiny `_classify_failure()` function on the error string.
   - **`pdf_name` backfill** at write time from a reference view, fallback to `volume_path` basename.

   *Lesson:* "we have observability" is not the same as "the team that owns this in prod can act on it without reading code." Build the SRE handoff into the DQ design from the start: every row has a category, a human identifier, and a de-dup window. The on-call paging rule should be a single SQL filter (`WHERE failure_category = 'unknown'`), not a tribal-knowledge ritual.

   ---

   ### 7A.5 Operator-driven repair without a backout path = changes nobody is willing to make

   Production data is going to need ad-hoc fixes. Wrong field on one document, equipment trio entered against the wrong serial, a row that needs to be rebuilt. If your only options are "edit by hand in Spark" or "write a notebook from scratch every time," the team will avoid making the fix — even when the fix is right — because the **revert path is unclear**.

   *What we built:*
   - One operator-driven repair job (`PW_SDG_FSR_Doc_Repair`) with a strict whitelist of fields it can touch (ESN + equipment trio). Anything else is refused at param validation.
   - **Always takes a full-row JSON snapshot** to a backup table *before* any write — no flag, no opt-in, always.
   - Writes a readable summary to an audit table (operator, run id, before/after).
   - **`DRY_RUN=true` by default.** You opt into making the change; you don't opt out.
   - **Same notebook reverts** via `REVERT_RUN_ID` — diffs the snapshot against current state, replays only the drifted whitelist fields, takes a fresh backup first.
   - Hard cap: **1 doc per run**. PK invariant: `document_id` and `chunk_id` are never modified. Multi-doc bulk fixes route to a different (designed-for-bulk) job.

   *Why this matters more than it looks:* the snapshot + same-notebook revert turns "scary one-way change in prod" into "safe two-way change in prod." That's the difference between fixes happening on the day they're needed vs. accumulating into a quarterly cleanup project.

   *Lesson:* every operator-triggered job that mutates production data should ship with **(1) dry-run default, (2) full-row snapshot before write, (3) a same-notebook revert path, (4) a hard blast-radius cap.** This isn't paranoia — it's what makes the team willing to actually run the job when prod needs it.

7B. **Five things I'm seeing about how teams use AI to build.** Patterns from this engagement and the engagements next to it.

   *Why this section exists:* the system-side stories above are about one pipeline. This section is about something I keep seeing across teams that build with AI. On the same anchor engagement, the partner team building the unit-risk reasoning agent on the FSR pipeline I led — a ~10-engineer cloud-services team — burned long hours and weekends pushing an AI-assisted feature that read well in dev and broke down on contact with real production data. It was a classic setup: the customer asked the team to use AI for everything and ship fast, with no guardrails set on how. The engineers were skilled. The AI tools were current-generation. What was missing was the engineering scaffolding around the AI — the design discipline, the review posture, the operating practices. I think Slalom has a real opportunity to make those practices explicit and reusable, and that starts with naming the patterns.

   ### 7B.1 Using AI without a design-first scaffold

   The fastest way to ship something that doesn't survive prod is to skip the design step and let the AI assistant fill it in. That team's late-night push wasn't an AI-assistant failure — the assistant produced plausible code on demand. It was a **design absence**: no decided contract for the feature's inputs, no agreed failure modes, no idea what "done" meant before code started landing. AI removes the friction that used to *force* design conversations, so teams skip them.

   *What good looks like:* a one-page design (inputs, outputs, failure modes, blast radius, what's idempotent, what isn't) **before** the AI assistant writes the first line. The design doesn't have to be heavy — it has to exist.

   *Offer:* I'd like to build this as a Slalom-internal asset — a one-page **AI-assisted design scaffold** any engagement can drop in on day one. Pairs with a short Codex session that walks through it with a worked example.

   ### 7B.2 The "ask it again to fix it" anti-pattern

   When the generated code is wrong, the dominant move I see is *"ask the assistant again, paste the error, accept whatever comes back."* Eugene called this the **existential problem** of AI engineering — and I agree. The loop produces something that compiles, the symptom goes away, and nobody understands what changed or why. Two iterations later the code is structurally incoherent. Three iterations later it's unmaintainable.

   *What good looks like:* when the assistant is wrong, **stop and read.** Diagnose the error the way you'd diagnose any bug — hypothesis, evidence, fix. Use the assistant to *implement* the fix, not to *find* it. If you can't explain why the new version works, you didn't fix the bug; you moved it.

   *This is the kind of template we could put in the Slalom delivery playbook.*

   ### 7B.3 "Looks correct" ≠ "prod-ready"

   AI-generated code passes a casual reading. It usually doesn't pass a production reading. The things it skips, by default, are the same things across every codebase: **idempotence, error envelopes, secret handling, retry caps, blast radius, observability hooks.** None of these show up in a happy-path test. All of them show up the first weekend in prod.

   *What good looks like:* a short, explicit checklist that any AI-assisted change has to clear before merge — the same kind of checklist a senior engineer applies in their head, made visible so the whole team applies it. Pre-commit checks for secrets. Required answer to "what happens on retry?" in the PR template. Default-off for anything that mutates state.

   *Offer (part 1 of 2):* I'd like to build this as the **author-side half** of a Slalom-internal **AI-assisted PR playbook** — a short prod-readiness checklist the author runs before requesting review. Drawn from this engagement, generalizable to any team. Part 2 is the reviewer-side half in 7B.4 — the two ship as one artifact.

   ### 7B.4 Code review burden has changed, and review posture hasn't caught up

   Reviewing AI-generated code is not the same job as reviewing human-written code. Human bugs cluster around intent (the engineer misunderstood the requirement). AI bugs cluster around plausibility — **hallucinated APIs, fabricated config keys, libraries used the wrong way, patterns that look like the real pattern but aren't.** Reviewing for "does this look reasonable" misses all of them. Reviewing for "does this actually call something that exists, with the contract it actually has" catches them.

   *What good looks like:* explicit review prompts for AI-assisted PRs — *check every imported symbol exists, check every config key is the real key, check the pattern against an actual reference implementation, run the code path, not just read it.* And the author should run that pass before requesting review.

   *Offer (part 2 of 2):* the **reviewer-side half** of the same Slalom-internal **AI-assisted PR playbook** — explicit prompts the reviewer (and the author, on a self-pass) walks through on any AI-assisted PR. Pairs with a Codex "review-the-review" session where we walk a real (sanitized) AI-generated PR live.

   ### 7B.5 Operating AI systems in prod is a different muscle, and most teams don't build it

   The work doesn't end at merge. Once an AI-generated component is in prod, the on-call posture changes. Failures are quieter — a model drift, a prompt regression, a silent extractor change — don't page like a CPU spike. The on-call rotation that worked for a regular service doesn't catch them. And the operating playbooks teams reach for (rollback, retry, restart) assume failures are loud and stateless. Most of the failures in an AI system are neither.

   *What good looks like:* a small set of operating defaults that teams adopt **on day one of prod**, not after the first incident. Lifetime retry counters (not per-run). Failure-category enums so the on-call paging filter is one SQL line, not a tribal-knowledge ritual. Dry-run defaults on any mutation. Full-row snapshots before any operator-triggered change. A repair job with a same-notebook revert. These aren't speculative — they're the patterns from 7A that earned their keep in prod.

   *Offer:* I'd like to build this as a Slalom-internal **AI-ops cheat-sheet** — a one-page set of operating defaults for any AI-assisted system going to prod. Closes the loop: design (7B.1) → review (7B.3 + 7B.4 playbook) → operate (this). Pairs with a Codex session on "what changes about on-call when AI is in the loop."

8. **Patterns we landed on** — the practices we'd recommend other teams adopt.
   - **Validation harness as the merge gate** for any extractor / prompt change (UI-07 / UI-13).
   - **Audit table + revert in the same notebook** for any ad-hoc data fix (UI-19).
   - **Separate the DQ job from the ingestion job** — ingestion shouldn't read its own outputs (UI-16).
   - **Lifetime retry counters, not per-run limits** (UI-18 P1, mirrored from P2).
   - **Failure-category enum on every DQ row** — only `unknown` pages on-call.
   - **Dry-run default + idempotent DDL** on any operator-triggered job.
   - **Interim patch + proper fix as separate PRs** (UI-14 vs UI-07/UI-13) — don't let the stop-gap block the real one.

9. **Guardrails for agent / GenAI engineering work** — what we'd put in a Slalom playbook.
   - Pre-filter the vector index on a hard field (ESN). Don't ask the LLM to filter.
   - Every extractor change ships behind a known-good cohort + known-bad cohort + 100-doc regression sample.
   - Schema changes are additive + idempotent; never rename or drop in a hotfix.
   - PK invariant: never modify `document_id` / `chunk_id` in a repair job.
   - Backfill and incremental on the same code path — or you'll diverge.
   - Secrets via secret scope from day one; the "we'll fix it after launch" path costs more.

10. **Operating model — what the team actually did.** The human side Eugene cares about.
    - **Picked up the workstream on short notice.** The original architect declined the skillset; I stepped in mid-engagement, learned the existing design, and shipped without restarting it.
    - **Cross-functional partnership.** AWS engagement leads, client-side tech leads (large industrial-equipment OEM), and Slalom delivery — three groups, one merge gate. Decisions ran through one design doc, not three side conversations.
    - **Trust loop.** The first prod outcome (the data pipeline running cleanly at scale) became the warrant for the next pieces — being asked to design the ad-hoc Q&A agent, the unit-risk agent, and to be the reuse partner on the parallel OSA engagement. Trust compounds when the first thing actually runs.
    - **Posture, not heroics.** No weekend firefights on this engagement. The hours other teams burn on prod incidents went into the templates above instead.

11. **What we'd do differently next time** — honest list, not a humility-cosplay list.
    - **Parallelize P1 from the start.** P2 ran parallel; P1 ran sequential. That choice cost real wall-clock on the backfill. The reason was schedule pressure, not design — but the right call was to invest the day to parallelize before launching the run.
    - **Design the DQ log SRE-ready from day one.** We built it for the team that wrote it. Categorizing every row, deduping noise, and writing the on-call paging filter into the schema should have been part of v1 — not a retrofit after the first 70-rows-a-day re-log incident.
    - **Lifetime retry counters before the first run, not after the first overrun.** We caught it in P2 and back-mirrored to P1. It should have shipped with the first version of any retried job.
    - **Validation harness as the merge gate before the first extractor change.** We added it after we needed it. The cost of building it on day one would have been less than the cost of one regression caught in prod.
    - **The single-prefilter-field design is a known fragility.** We pre-filter the vector index on one extracted field. That's fast and clean today; it's also one bad prompt change from a zero-results incident. A cohort-level guard around that field is the right next investment.
    - **Secrets via secret scope from day one.** Every engagement repeats this mistake. We did too. The "we'll fix it after launch" path is always more expensive than the day-one path.

12. **Where this goes next at Slalom** — the offer back.

    The case study above is one engagement. The value to Slalom is in **what generalizes** — to other Slalom teams, to other Slalom clients, to engagements that haven't started yet. Concretely, I'm proposing to build and contribute the following, drawn from this engagement and shaped for reuse:

    **Three templates (Slalom-internal assets):**
    1. **AI-assisted design scaffold** (from 7B.1) — one-page design any engagement can drop in on day one. Inputs, outputs, failure modes, blast radius, what's idempotent, what the AI assistant is *not* allowed to do without human review.
    2. **AI-assisted PR playbook** (combines 7B.3 + 7B.4) — a two-part artifact: author-side prod-readiness checklist (idempotence, error envelopes, secret handling, retry caps, blast radius, observability) and reviewer-side prompts (verify imports exist, config keys are real, patterns match an actual reference). One playbook, two halves — the author runs the first, the reviewer runs the second.
    3. **AI-ops cheat-sheet** (from 7B.5) — one-page operating defaults for any AI-assisted system going to prod. Lifetime retry counters, failure-category enums, dry-run defaults, snapshot-before-write, same-notebook revert. Closes the design → review → operate loop.

    Each is ~1 page. Each is drawn from a real failure mode I've seen in prod or on adjacent engagements. None require a research lab to maintain.

    **Codex alignment.** These templates are most useful when they're taught, not just filed. Each one can ship as a paired **Codex session** (~45 min: framing, the template, a worked example from this engagement, hands-on). Together they form a coherent **"production-readiness for AI engineering"** Codex track — the gap between *"I can use Copilot"* and *"I can ship Copilot output to prod."* I'd also like to offer a **"war-story" session format**: walk through one of the 7A failures live (what we shipped, what broke, what we changed) — engineers remember stories, not bullet lists.

    **A lighter-weight offer:** Codex / production-readiness **office hours** for engagements that hit these issues mid-flight — lower commitment, faster signal on which templates teams actually reach for.

    **Next conversations to validate the offer:**
    - **Dave Messina** — align on the "production-readiness for AI engineering" framing and where it slots into existing Slalom delivery practice.
    - **Christian** — validate the three templates against what other engagements are running into; find the first pilot team.
    - **Chris Temple** — align with Codex on the session formats and the "war-story" / "review-the-review" formats.

    None of this is contingent on the artifact landing perfectly. The templates are useful regardless. The offer is to build them, teach them, and stay close to the engagements that adopt them.

---

## Appendix (Eugene-only, not for Arch-Hive)

- **A1.** UI-NN issue inventory (themes: failure handling, observability, ESN, repair tooling, doc-summary, security) — already consolidated in `fsr-prod-ops/tracker.md`, lift the table.
- **A2.** Two before/after snippets — DQ log (before: 70 rows/day re-log; after: dedup + category enum) and ad-hoc fix (before: no revert; after: snapshot + same-notebook revert).
- **A3.** One-page companion write-up — distilled version of sections 7–9 for Eugene to forward / share.

---

## Source material to mine (next pass)

- `../../fsr-prod-ops/tracker.md` — UI-11, 12, 14, 16, 17, 18, 19; ESN issue map.
- `../../FSR/ESN-resolution/design/` — extractor + multi-ESN + watermark design docs.
- `../../fsr-prod-ops/backfill-pulse-log.md` — real backfill incidents.
- `../../internal/learnings/` — Databricks CLI setup learnings.
- `../evidence-bank.md` — Story #1 (GEV/FSR) framing, numbers, quotes.
- `../../FSR/fsr-pipeline-design.md` — architecture diagram source.

---

## Decisions locked (May 14)

- **Format:** content first, deck later. Build the written outline + sections fully, then convert to slides.
- **Date:** TBD — May 30 is the working target; confirm later.
- **GEV review:** **No.** Only GE-related delivery work goes through Pranesh / Abhijeet. The lessons / patterns / playbook framing is Slalom-internal — do not route this artifact to GEV. When writing sections 7–11, frame anonymously where needed (no client names, no proprietary detail beyond what's already public-facing in the architecture story).
- **Readiness doc (#2):** Eric's templates live at `../input-docs/Template - Promotion Plan.pptx` and `../input-docs/Template - Promotion Readiness Reflection.xlsx`. Already shared current draft (`../output-docs/Promo-Reflection-and-Plan_DRAFT.xlsx`) with Eric — needs conversion into Eric's exact template format. Track #2 runs in parallel to this artifact.
