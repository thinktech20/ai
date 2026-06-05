# Eugene Deck — Slide Content

> **Source of truth:** [artifact-outline.md](artifact-outline.md) (§7B + §12).
> **Audience:** Eugene first; later a mixed Slalom audience (engineers + non-deep-AI consultants who know the tools but not the stack).
> **Length:** 8–12 slides, ~20 min talk + Q&A.
> **Voice:** Neutral / collective. Avoid "I" framing — no "I'm offering Slalom" or "I'd build this for Slalom" (we're inside Slalom). Use "the artifacts that can help with X are…", "what good looks like…", "we" for what was built.
> **Anonymization:** no client names, no GEV / AWS naming. "Industrial-equipment OEM" framing if needed.
> **Status:** skeleton (titles + intent only). Body content fills in next pass, slide-by-slide.

---

## Slide 1 — Title + position

**Title:** *Building with AI: what teams need that the coding tools don't give them.*
**Intent:** Open with a single-line position. Set the frame: this is about engineering practice around AI coding tools — not the models, not org structure.

**Sub-line (under title):** Patterns from recent work shipping AI-assisted features to production — and three artifacts that close the gaps they expose.

**Layout:** title slide. Title centered. Sub-line one size smaller, directly below. Presenter name + role + date in the footer. No visual.

---

**Talk track (~30s):**

1. *Open with the title line, verbatim.* "Building with AI — what teams need that the coding tools don't give them." Pause.
2. *Land the frame in one sentence.* "This is about engineering practice around the coding tools — not the models, not org change." That's the frame; don't elaborate.
3. *Move on.* Don't read the sub-line aloud — it sets expectation visually and bridges into slide 2.

**What NOT to do on this slide:**
- No agenda slide. The flow is the agenda.
- No personal credentials / bio. Footer is enough.
- Don't preview the artifacts — slide 8 owns that.

---

## Slide 2 — Where this came from

**Intent:** Anchor the talk in one real observation. The partner team on a recent engagement (a ~10-engineer cloud-services team building the unit-risk agent on the FSR pipeline I led) burned long hours and weekends pushing an AI-assisted feature that read well in dev and broke down on real production data. Skilled engineers, current-generation AI tools. What was missing was the scaffolding around the AI — design discipline, review posture, operating practices. That gap is the talk.

**Title:** *Where this came from.*

**Sub-line:** One observation from a recent engagement, repeated across teams the more it gets looked at.

**Layout:** single column, three short paragraphs (or three indented blocks). No visual needed — the story is the visual.

---

**Block 1 — The setup (one sentence):**

> A ~10-engineer cloud-services team at an industrial-equipment OEM was building an AI-assisted feature on top of a data pipeline our team had shipped. Skilled engineers, current-generation AI tools, a real production target. It was a classic setup: **the customer asked the team to use AI for everything, ship fast — no guardrails set on how.**

**Block 2 — What happened (two sentences):**

> The feature read well in dev. It broke down on real production data — wrong outputs in edge cases, behavior the team couldn't explain when pressed, fixes that introduced new bugs. What looked like progress was mostly rework.

**Block 3 — What was actually missing (the pivot):**

> The AI tools weren't the problem — they produced plausible code on demand. What was missing was the practice around them: a design step before code started landing, a review posture that catches the way AI bugs cluster, operating defaults that catch the quiet failures these systems show in prod. That's the gap this talk is about.

---

**Talk track (~1.5 min):**

1. *Set the scene (~30s).* One real engagement, deliberately stripped of names. A ten-person cloud-services team. Real product, real prod target. Strong engineers, current AI tooling. Classic setup — customer directive was "use AI for everything, ship fast" with no guardrails on how. Pause briefly — let the audience picture a team they know.
2. *Land the failure (~30s).* "It read well in dev. It broke down on real production data — wrong outputs in edge cases, behavior nobody could explain when pressed, fixes that introduced new bugs. What looked like progress was mostly rework." Short sentences, no softening. This is the moment that earns the rest of the deck.
3. *Pivot to the real gap (~30s).* The AI tools weren't the problem. The practice around them was — design, review, operate. That's what's missing across teams, not just this one. Bridge to slide 3: *"A handful of patterns kept showing up. Here they are."*

**Anonymization checks (must hold every time this deck is shown):**
- No client name, no industry vertical detail beyond "industrial-equipment OEM."
- No team member names. No partner-team Slack channel names.
- No engagement codename, no internal project name.
- "Our team" = generic; don't name GEV, AWS, or any sub-team. If pushed in Q&A, *"a recent engagement — happy to talk specifics 1:1."*

**What NOT to do on this slide:**
- Don't make it a war story. The story slot is B1 (backup). This slide is one observation, not a case study.
- Don't blame the partner team. The whole frame is "skilled engineers, real tools, missing scaffolding" — keep the empathy.
- Don't preview the artifacts here. Slide 8 owns that.

**If the audience grows beyond Eugene:** consider opening B2 (anonymization disclaimer) before this slide so the framing is explicit up front.

---

## Slide 3 — The patterns

**Intent:** Single slide listing the patterns that keep showing up. Sets up the rest of the deck — each pattern gets one slide after this. Titles only on this slide; no detail.
1. Skipping design because AI fills the silence.
2. The "ask it again" loop.
3. Looks-correct ≠ prod-ready.
4. Reviewing AI-generated code is a different job.
5. AI systems fail quietly in production.

**Title:** *Patterns that kept showing up.*

**Sub-line:** Each one gets one slide. The shape matters more than any single example.

**Layout:** numbered list, full width, large type. Each pattern on its own line. Small label next to each: *(design)*, *(loop)*, *(prod-readiness)*, *(review)*, *(operate)* — reinforces the lifecycle arc that slide 8 will land on.

---

**Slide body — verbatim:**

1. **Skipping design because AI fills the silence.** *(design)*
2. **The "ask it again" loop.** *(loop)*
3. **Looks-correct ≠ prod-ready.** *(prod-readiness)*
4. **Reviewing AI-generated code is a different job.** *(review)*
5. **AI systems fail quietly in production.** *(operate)*

---

**Talk track (~1 min):**

1. *Frame (~10s).* "These kept showing up. Different teams, same shape. One slide each — then the artifacts that close the gaps."
2. *Read the patterns (~40s).* Read each line cleanly. Don't elaborate. The point is the *list*, not any one item. Let the audience scan ahead.
3. *Bridge (~10s).* "Walking them in order — starting with the one that costs the most up front." Move to slide 4.

**What NOT to do on this slide:**
- No examples. Patterns only.
- No artifact preview. Slide 8.
- Don't number them in order of severity — lifecycle order (design → build → review → operate) is what the deck is structured around.

**Diagram note (for visual pass):** optional small icon per pattern, but text-only is fine. The lifecycle labels in parentheses are the only "visual" load-bearing element.

---

## Slide 4 — Pattern 1: Design before code

**Intent:** AI removes the friction that used to *force* design conversations, so teams skip them. The partner-team weekends weren't an AI failure — they were a design absence. What good looks like = a one-page design (inputs, outputs, failure modes, blast radius, what's idempotent) before the assistant writes the first line. Preview the design-scaffold artifact here.

**Title:** *Pattern 1 — Design before code.*

**Sub-line:** AI removed the friction that used to *force* design conversations. So teams skip them.

**Layout:** two short blocks stacked. Top = the pattern (one paragraph). Bottom = "what good looks like" (5–6 bullets). One-line artifact preview at the very bottom.

---

**Block 1 — The pattern:**

> Before AI, writing the first 200 lines was friction. That friction *forced* a quick design conversation — what are we actually building, what does the input look like, what happens when it breaks. AI removes that friction. The code starts landing before the design exists. The rework from the anchor story wasn't an AI failure; it was a design absence the AI tooling helped hide.

---

**Block 2 — What good looks like — a shared understanding on the page before the assistant writes the first line:**

- **Contract** — inputs (shape, source, volume, edge cases), outputs (downstream consumers, what "done" looks like in prod, not just in dev).
- **Eval** — how we'll know it's working in prod — sample set, scenarios, the criteria a reviewer can re-run on a fresh run.
- **Failure modes** — what can go wrong, what's safe to retry, what's idempotent and what isn't, what fails open vs. fails closed.
- **Blast radius** — what this touches when it fails, who notices first, what gets paged.
- **Out of scope** — what we're explicitly NOT building yet — the guardrail against scope drift the assistant will happily ignore.

---

**Artifact preview (one line under block 2):**

> Packaged as the **AI-assisted design scaffold** — a one-pager teams drop in on day one. Detail on slide 8.

---

**Talk track (~2 min):**

1. *Name the pattern (~20s).* "The friction of writing the first 200 lines used to *force* a design conversation. AI removed that friction. So the design doesn't happen — the code starts landing instead."
2. *Tie back to the anchor (~20s).* "The rework from slide 2 — that wasn't an AI failure. It was a design absence the AI tooling helped hide." One sentence. Don't re-tell the story.
3. *Walk the five (~60s).* Read each item once. Land that none of them require more than a page — the point is *existence* and *shared understanding*, not depth. Eval is the one most teams skip and most regret skipping.
4. *One-line artifact preview (~20s).* "This becomes the AI-assisted design scaffold. Slide 8 has the full set." Move on.

**What NOT to do on this slide:**
- Don't sell heavy design process. The point is *a page that exists*, not formal architecture review.
- Don't repeat the anchor story — one sentence callback is enough.
- Don't dwell on the artifact — slide 8 owns it.

**Diagram note (for visual pass):** none. Text density is the right load. If a designer pass happens, a small "30 min before code" stopwatch in the corner could land the cost vs. benefit — optional.

---

## Slide 5 — Pattern 2: The "ask it again" anti-pattern

**Intent:** When the generated code is wrong, the dominant move is *"paste the error, accept whatever comes back."* Eugene's "existential problem of AI engineering" quote on this slide. Stop and read. Diagnose first, then use the assistant to implement — not to find — the fix.

**Title:** *Pattern 2 — The "ask it again" loop.*

**Sub-line:** The dominant move when AI-generated code breaks: paste the error, accept whatever comes back. Two iterations later the code is structurally incoherent.

**Layout:** single column. Three short blocks stacked: the loop → why it's expensive → the better move. A pulled quote sits between blocks 1 and 2.

---

**Block 1 — The loop:**

> Generated code throws an error. The reflex move: paste the error back to the assistant, accept the new version, ship it. Symptom goes away. Nobody understands what changed or why.

---

**Pulled quote (large, mid-slide):**

> *"This is the existential problem of AI engineering."*
> — Eugene

---

**Block 2 — Why it's expensive:**

> Two iterations in, the code is structurally incoherent. Three iterations in, it's unmaintainable. The bug isn't fixed — it's moved, often somewhere harder to find. By PR review time, nobody on the team can explain why the working version works.

---

**Block 3 — The better move:**

> The fix isn't a sharper error message back to the assistant. It's grilling the first answer hard enough that the loop never starts. Make it walk through its assumptions. Ask what it didn't consider, what it's guessing at, where the design could break. The real design conversation happens at the first pass — not after three broken iterations.
>
> If the answer survives that, then when something does break, **stop and read.** Diagnose like any other bug — hypothesis, evidence, fix. Use the assistant to *implement* the fix, not to *find* it. If you can't explain why the new version works, you didn't fix the bug.

---

**Talk track (~1.5 min):**

1. *Name the loop (~20s).* Walk Block 1 verbatim. Slow on "nobody understands what changed or why" — that's the line the audience recognizes.
2. *Land the quote (~15s).* Read Eugene's line. Pause. Don't explain it — it carries.
3. *Cost (~30s).* Walk Block 2. Land the "bug moved, not fixed" framing. Use "by PR review time, nobody can explain why the working version works" as the line that lingers.
4. *The shift (~25s).* Walk Block 3. The pivot is one phrase: *grill the first answer, not the third.* The real design conversation belongs at the first pass — push back, ask what it's guessing at, ask what it didn't consider. That's the takeaway.

**What NOT to do on this slide:**
- Don't make the assistant the villain. The loop is a *human* habit; the tool just enables it.
- No code example. The pattern is behavioral, not syntactic.
- Don't propose an artifact here — this pattern is the only one without a dedicated artifact (it's a posture shift, not a checklist). If asked, route to the design scaffold and PR playbook — both reinforce the discipline indirectly.

**Diagram note (for visual pass):** a small circular arrow on the side titled "error → ask → accept → error" — reinforces the "loop" framing. Optional.

---

## Slide 6 — Pattern 3 + 4 combined: Looks-correct ≠ prod-ready, and reviewing it

**Intent:** Strongest slide. Two columns. **Left (author-side, pattern 3):** the things AI-generated code skips by default — idempotence, error envelopes, secret handling, retry caps, blast radius, observability. **Right (reviewer-side, pattern 4):** AI bugs cluster around plausibility (hallucinated APIs, fabricated config keys, patterns that look right but aren't); review for "does this actually call something that exists with the contract it has." Preview the **AI-PR playbook** offer as the artifact that packages both halves.

**Title:** *Looks-correct ≠ prod-ready. And reviewing it is a different job.*

**Sub-line (one line under title):** AI-generated code passes a casual reading. It usually doesn't pass a production reading — and the review posture most teams use was built for a different kind of bug.

**Layout:** two columns, equal width. Single visual at the bottom spans both: a thin arrow from "Author" → "Reviewer" with the playbook artifact name in the middle.

---

**Left column — Author-side: what AI code skips by default**

*Header:* The same gaps show up in every codebase.

- **Idempotence** — what happens if this runs twice?
- **Error envelopes** — does failure return a typed result, or a stack trace?
- **Secret handling** — keys in env/secret scope, never in code or yaml.
- **Retry caps** — bounded? Per-run or lifetime?
- **Observability** — can on-call see this failed without reading driver logs?

*Footer line:* None of these show up in a happy-path test. All of them show up the first time it hits prod traffic.

---

**Right column — Reviewer-side: AI bugs cluster differently**

*Header:* Human bugs cluster around intent. AI bugs cluster around plausibility.

- **Hallucinated APIs** — method exists in the docs, not in the version pinned.
- **Fabricated config keys** — reads like the real key, isn't.
- **Libraries used the wrong way** — right import, wrong contract.
- **Patterns that look like the real pattern but aren't** — shaped like the codebase convention, off by one assumption.

*Shift in review question:*
~~"Does this look reasonable?"~~ → **"Does this actually call something that exists, with the contract it actually has?"**

*Footer line:* Reviewing for plausibility means running the code path, not just reading it.

---

**Bottom strip (spans both columns) — the artifact:**

> **AI-assisted PR playbook** — one artifact, two halves. The author runs the left side before requesting review. The reviewer runs the right side on the PR. Pairs with a Codex "review-the-review" session walked through a real (sanitized) AI-generated PR.

---

**Talk track (~3 min, the longest slide of the deck):**

1. *Set up the gap (~30s).* AI-generated code reads cleanly. That's the trap. Casual reading passes; production reading doesn't. The things it skips are the same across every codebase — and they're the things that hurt the first time it hits real prod traffic.
2. *Walk the left column (~60s).* Five items, fast. Land each with one beat: idempotence, error envelopes, secret handling, retry caps, observability. Tie back to 7A war stories only if asked — don't tell them here.
3. *Pivot to the reviewer side (~30s).* "But this isn't only an author problem — review posture hasn't caught up either." That's the bridge.
4. *Walk the right column (~45s).* Frame the shift: human bugs vs AI bugs. Plausibility is the new failure mode. The four examples are recognizable to anyone who's reviewed AI code recently — let them nod. Land the review-question shift visibly (cross out the old one).
5. *Land the artifact (~15s).* "These two halves are one artifact — the AI-assisted PR playbook. Author runs the left, reviewer runs the right." Point to the bottom strip. Don't sell it further — slide 8 will.

**Anchor quote to keep in your back pocket:** "The reviewer's job changed when the author started using AI, and most teams haven't said that out loud yet."

**What NOT to do on this slide:**
- No code samples. The slide is about review posture, not syntax.
- Don't name the engagement, the language, or the framework. Keep it cross-cutting.
- Don't tell a war story here — slide intent is the *pattern*, not the proof. War stories live in B1 if asked.

**Diagram note (for the visual pass):** simple two-column layout, no icons per item — text density is the point. The author→reviewer arrow at the bottom is the only visual element. If a designer pass happens, the only thing worth illustrating is the strike-through on the old review question.

---

## Slide 7 — Pattern 5: Operating AI in prod is a different muscle

**Intent:** Failures are quieter — model drift, prompt regression, silent extractor change — don't page like a CPU spike. The on-call posture for a regular service doesn't catch them. Operating defaults that earn their keep: lifetime retry counters, failure-category enums, dry-run defaults, snapshot-before-write, same-notebook revert. Preview the **AI-ops cheat-sheet** artifact.

**Title:** *Pattern 5 — Operating AI in prod is a different muscle.*

**Sub-line:** AI failures are quieter. They don't page like a CPU spike — and the on-call posture most teams use was built for the loud kind.

**Layout:** two short blocks stacked. Top = how AI failures look in prod (3–4 bullets). Bottom = operating defaults that catch them (5 bullets). One-line artifact preview at the bottom.

---

**Block 1 — The kinds of failures that slip through:**

- **Model drift** — outputs degrade slowly; no alert fires.
- **Prompt regression** — a config change shifts behavior; existing tests still pass.
- **Silent extractor change** — upstream format moves; pipeline keeps running, populates the wrong field.
- **Quiet enrichment failures** — nulls in the output, not stack traces in the logs.

*Footer line:* None of these page. All of them show up later as a consumer complaint. The on-call posture for a regular service was built for the loud kind of failure — these are the quiet kind.

---

**Block 2 — Operating defaults that earn their keep (adopt on day one):**

- **Lifetime retry counters** — not per-run; bound the loop before it costs real money.
- **Failure-category enums** — typed reason codes, so the on-call paging filter is one SQL line.
- **Dry-run defaults** — anything that mutates state defaults to off.
- **Snapshot-before-write** — full-row snapshot before any operator-triggered change.
- **Same-notebook revert** — the repair job carries its own undo.

---

**Artifact preview (one line under block 2):**

> Packaged as the **AI-ops cheat-sheet** — a one-page set of operating defaults for any AI-assisted system going to prod. Detail on slide 8.

---

**Talk track (~2 min):**

1. *Frame the gap (~25s).* "The work doesn't end at merge. Once an AI-generated component is in prod, on-call posture changes — and most teams haven't changed it."
2. *Walk block 1 (~40s).* Four failure modes, fast. Land the closer: "None of these page. All of them show up later as a consumer complaint." That's the sentence that earns block 2.
3. *Walk block 2 (~45s).* Five defaults, fast. Each one is concrete — lifetime counters, typed enums, dry-run defaults, snapshots, same-notebook revert. Don't justify them individually; the failure-mode block already did that.
4. *Artifact preview (~10s).* "Packaged as the AI-ops cheat-sheet. Slide 8 brings the three artifacts together."

**What NOT to do on this slide:**
- Don't name the engagement or the specific incidents. Cross-cutting framing only.
- Don't claim these defaults are universal — they're a starting set drawn from prod, not theory.
- Don't sell the artifact here — slide 8 does the consolidation.

**Diagram note (for visual pass):** a small graphic contrasting "loud failure (CPU spike, pager fires)" vs. "quiet failure (nulls in output, no alert)" could land block 1 fast — optional. Otherwise text-only is fine.

---

## Slide 8 — Artifacts that close the loop

**Intent:** Section 12 condensed onto one slide. Three templates that close the loop: **design → review → operate.** One row per template — name, one-line description, the failure it prevents.
1. AI-assisted design scaffold (from pattern 1).
2. AI-assisted PR playbook (from patterns 3 + 4 combined).
3. AI-ops cheat-sheet (from pattern 5).
Each ships as a one-pager + paired Codex session.

**Title:** *Three artifacts that close the loop: design → review → operate.*

**Sub-line:** Each one is a one-page template plus a paired Codex session. The three together cover the lifecycle gaps the five patterns surfaced.

**Layout:** three-row table, full width. Visual at the top: a thin horizontal loop — *Design → Review → Operate → (back to Design)* — with each artifact labeled under the matching arc.

---

**Table — one row per artifact:**

| Artifact | What it is | The failure it prevents | Maps to |
|---|---|---|---|
| **AI-assisted design scaffold** | One-page design (inputs, outputs, failure modes, blast radius, what's idempotent) the team fills in before the assistant writes a line. | Shipping a feature that reads well in dev and breaks down on real data — the "design absence" failure from the anchor story. | Pattern 1 |
| **AI-assisted PR playbook** | Two-half checklist: author-side prod-readiness pass + reviewer-side plausibility prompts. Author runs the first half before requesting review; reviewer runs the second on the PR. | Merging AI-generated code that *looks* correct but skips idempotence, secrets, retry caps — and reviews that miss hallucinated APIs and fabricated config keys. | Patterns 3 + 4 |
| **AI-ops cheat-sheet** | One-page set of operating defaults adopted on day one of prod — lifetime retry counters, failure-category enums, dry-run defaults, snapshot-before-write, same-notebook revert. | The quiet failures — model drift, prompt regression, silent extractor change — that don't page like a CPU spike and slip past a standard on-call posture. | Pattern 5 |

---

**Footer line (under the table):**

> Each artifact ships as a one-page template + a paired Codex session walking it through on a real (sanitized) example.

---

**Talk track (~2 min):**

1. *Frame (~20s).* The five patterns surfaced gaps at three points in the lifecycle — before code is written, at review, and once the system is live. Three artifacts, one per gap. Together they close the loop.
2. *Walk the table (~75s).* One row at a time, fast — name, one-line description, the failure it prevents. Don't re-tell the patterns; the audience just saw them. Lean on the failure column — that's what makes each artifact concrete.
3. *Close with the format (~20s).* Each artifact is small on purpose — a one-pager teams can drop in. Bridge: "These ship first as templates, but they don't have to stay that way — that's the next slide."

**What NOT to do on this slide:**
- Don't pitch any single artifact harder than the others — Slide 12 lets Eugene pick the one with the most pull.
- Don't repeat the pattern descriptions. The "Maps to" column is the only callback needed.
- No personal framing ("I'd like to build these"). The artifacts are the subject of the slide, not the author.

**Diagram note (for the visual pass):** the loop visual at the top is the only graphic — three arcs labeled *Design / Review / Operate*, each tagged with the matching artifact name. Keep the table dense and plain; the loop carries the visual weight.

---

## Slide 9 — From templates to agents

**Intent:** Pre-empt the obvious "why a template and not an agent?" question. Frames v1 (templates + Codex sessions) as the validate-first move, and v2 (agents that enforce them in the IDE and the PR) as the natural next step. Shows forward-thinking without overcommitting on a delivery date.

**Title:** *Templates today. Agents next.*

**Sub-line:** The artifacts work as one-pagers. They work harder as agents that enforce themselves inside the IDE and the PR.

**Layout:** two-column table (v1 vs v2) plus a one-line footer. Same dense, plain style as slide 8.

---

**Slide body — table:**

| Artifact | v1 — template form (today) | v2 — agent form (next) |
|---|---|---|
| **Design scaffold** | One-page doc the engineer fills in before code. | Chat-mode agent that interviews the engineer through the fields and won't let any be skipped. Outputs the design doc into the repo. |
| **PR playbook** | Two-half checklist run by author and reviewer. | Two paired agents on the PR. Author-side agent runs prod-readiness checks on the diff at push time. Reviewer-side agent posts plausibility-check comments — hallucinated APIs, fabricated config keys, library misuse. |
| **Ops cheat-sheet** | One-page set of operating defaults. | The defaults stay a doc *(they're code patterns, not agent behavior)*. Add a triage agent that reads the failure-category enum + recent runs and suggests the matching diagnostic. |

**Footer (one line under the table):**

> v1 ships first because templates are faster to validate. v2 follows on the engagements that adopt v1 — agents enforce what templates only suggest.

---

**Talk track (~90s):**

1. *Frame (~15s).* "The obvious question on slide 8 is — why a template and not an agent? Short answer: both, in that order."
2. *Walk the table (~60s).* Row by row. For each, name the v1 form in five words, then name the v2 agent form. Don't oversell the agents — the v1 form is what gets validated first.
3. *Close on the footer (~15s).* "Templates validate the *content*. Agents make it stick. The engagements that adopt v1 are where v2 earns its keep." Bridge to slide 10 (formats): "And here's how the v1 form lands — three delivery formats."

**What NOT to do on this slide:**
- Don't commit to a build timeline for the agents. "Next" is on purpose.
- Don't position agents as replacing the Codex sessions. The sessions teach the *thinking*; agents enforce the *output*.
- Don't add a fourth row. The ops cheat-sheet partial-agent treatment is the honest answer — say it.

**Anonymization checks:**
- ✅ No client / product / team names.
- ✅ Generic technology references only (chat-mode agent, PR agent, triage agent).

**Diagram note (for the visual pass):** small arrow between the two columns labeled *"validates content" → "enforces output"*. Optional.

---

## Slide 10 — The Codex track + lighter-weight formats

**Intent:** These templates are most useful when taught, not just filed. The three pair into a coherent "production-readiness for AI engineering" Codex track. Two additional formats on the slide: **"war-story" session** (walk through one of the 7A prod failures live — engineers remember stories) and **office hours** (lower-commitment signal channel for engagements that hit these issues mid-flight).

**Title:** *Three formats, depending on how teams want to absorb it.*

**Sub-line:** The artifacts work as drop-in templates. They land harder when they're taught. Three delivery formats, each with a different commitment level.

**Layout:** three blocks stacked (or three columns if width allows), one per format. Each block: name — what it is — when it fits.

---

**Block 1 — Codex track (highest depth):**

> **"Production-readiness for AI engineering"** — the three artifacts as a coherent multi-session track. One session per artifact, walked through with a worked (sanitized) example. Fits teams that want to build the muscle, not just receive a checklist.

---

**Block 2 — War-story session (medium depth, highest stickiness):**

> Walk one real (sanitized) prod failure end-to-end — what shipped, what broke, what changed, the one-line lesson. Engineers remember stories. Fits lunch-and-learn slots, new-engagement kickoffs, anywhere the audience is mixed-experience.

---

**Block 3 — Office hours (lowest commitment):**

> A signal channel for engagements that hit one of the five patterns mid-flight. Drop a question, get a one-pager pointer + a 30-min slot if needed. Fits teams that don't want a full track but want a place to ask.

---

**Footer line:**

> The three formats step down in depth and step up in reach. Most engagements will start with one and expand into another.

---

**Talk track (~1.5 min):**

1. *Frame (~15s).* "The artifacts are useful when filed. They're better when taught. Three delivery formats, depending on how much depth a team wants."
2. *Walk the three (~60s).* One block at a time. Land each with the *fit* line — that's what helps the audience picture where each one lives.
3. *Close (~15s).* "Step down in depth, step up in reach. Most teams will start with one and move into another over time." Bridge to slide 11.

**What NOT to do on this slide:**
- Don't commit to a schedule or session count here. That's a downstream conversation.
- Don't position office hours as "lite" — it's the catch-net for the patterns, not a fallback.
- Don't list named potential pilots — slide 11 owns that.

**Diagram note (for visual pass):** a thin horizontal bar showing depth → reach axis with the three formats placed on it could land block 1–3 fast. Optional.

---

## Slide 11 — First conversations to validate

**Intent:** Three named people, one specific ask each — not name-drops.
- **Dave Messina** — 15 min to validate the "production-readiness for AI engineering" framing against existing Slalom delivery practice.
- **Christian** — name 2 engagements that could be the first pilot for the AI-PR playbook.
- **Chris Temple** — co-design the first Codex session (start with the war-story format).

**Title:** *First conversations to validate.*

**Sub-line:** Three people, one specific ask each. Not name-drops — each one closes a different open question.

**Layout:** three rows, full width. Each row: name — the specific ask — what it de-risks.

---

**Table:**

| Who | The specific ask | What it de-risks |
|---|---|---|
| **Dave Messina** | 15 min to validate the "production-readiness for AI engineering" framing against existing Slalom delivery practice. | Avoids landing on a framing that already exists under a different name, or that conflicts with a current point of view. |
| **Christian** | Name 2 engagements that could be the first pilot for the AI-PR playbook. | Moves the playbook from idea to a real-team test. The two halves only get sharper when run on a real PR queue. |
| **Chris Temple** | Co-design the first Codex session — start with the war-story format. | Stories land before checklists do. Co-design with Codex up front shortens the path to a session that actually gets booked. |

---

**Footer line:**

> Three conversations, three different gaps closed. None of them are "socialize broadly" — each one has a deliverable.

---

**Talk track (~1 min):**

1. *Frame (~10s).* "Three first conversations, each with one specific ask. Not name-drops — each one closes a real open question."
2. *Walk the three (~40s).* One row at a time. Read the name, the ask, and what it de-risks. Slow on "de-risks" — that's the column that earns the slide.
3. *Close (~10s).* "None of these are 'socialize broadly.' Each one ends with a deliverable." Bridge to slide 12.

**What NOT to do on this slide:**
- Don't add more names. Three is the cap — each one earns its row.
- Don't promise outcomes from the asks. The asks are the deliverable; what they produce is downstream.
- Don't position any of the three as gatekeepers. Each ask is *useful input*, not an approval.

**Diagram note (for visual pass):** none. The table is the visual.

---

## Slide 12 — Close: a question for Eugene

**Intent:** End on a question, not a statement. *"Of the three templates, which one has the most pull for the engagements you're closest to?"* Lets Eugene shape priority instead of receiving a finished plan.

**Title:** *One question to close on.*

**Sub-line:** The deck named the gaps and the artifacts. Priority is the open question — and the better person to answer it is in the room.

**Layout:** mostly empty slide. Large centered question. Small footer with the three artifact names as a memory aid.

---

**Slide body (large, centered):**

> *Of the three artifacts — design scaffold, PR playbook, ops cheat-sheet — which one has the most pull for the engagements you're closest to?*

---

**Footer (small, under the question):**

> 1. AI-assisted design scaffold &nbsp;·&nbsp; 2. AI-assisted PR playbook &nbsp;·&nbsp; 3. AI-ops cheat-sheet

---

**Talk track (~30s):**

1. *Frame (~10s).* "One question to close on." Pause. Let the slide load.
2. *Read the question (~10s).* Read it slowly, exactly as written. Don't paraphrase.
3. *Stop talking (~10s).* The slide is a prompt for Eugene, not a closing statement. Stay quiet. Let the conversation start.

**What NOT to do on this slide:**
- Don't summarize the deck. The deck just happened.
- Don't pre-rank the three artifacts. The whole point is to let Eugene shape priority.
- Don't add a "thank you" slide after this. This *is* the close.
- If Eugene's first response is "all three" — don't accept it. Follow up with "which one starts in the next 30 days?" Priority requires picking.

**Diagram note (for visual pass):** none. White space is the design.

---

## Backup slides (only if asked)

**B1 — One 7A war story in full.** Likely 7A.3 (secrets-in-yaml) — most universally relatable, shortest to tell. Format: what we shipped → what broke → what we changed → the one-line lesson.

**Title:** *War story — secrets in yaml.*

**Sub-line:** One real (sanitized) incident. Four beats: what shipped → what broke → what changed → the lesson.

**Layout:** four short blocks stacked. Each block is one beat.

- **What we shipped.** An AI-assisted pipeline config landed with credentials inline in a yaml file. Code reviewed, tests passed, deployed to dev. Reviewer skimmed for plausibility — the yaml read like every other yaml.
- **What broke.** Config promoted to a shared environment. Secret was now in a checked-in file inside a workspace that more than one team could read. No incident page fired — by design, secrets don't page when they leak quietly.
- **What we changed.** Pre-commit hook for secret patterns. Reviewer prompt: *check every credential-shaped string against the secret scope, not the file.* Rotate-and-replace runbook added to the ops cheat-sheet.
- **The lesson (one line).** *AI-generated config reads like working config. Reviewing for plausibility is the same as not reviewing at all when the failure mode is silent.*

**Talk track (~2 min):** Walk the four beats in order; ~30s each. Don't editorialize between blocks. Land the one-line lesson last and stop.

**When to use:** if the audience asks for a concrete example, or if mid-deck a slide isn't landing and a story would re-anchor. Don't volunteer it — it costs slide time elsewhere.

---

**B2 — Anonymization disclaimer.** Single slide stating the engagement is anonymized for Slalom-internal sharing only; do not forward externally. Use if presenting beyond the Eugene 1:1.

**Title:** *A note on what's in this deck.*

**Sub-line:** This deck is anonymized for Slalom-internal sharing. Please don't forward it outside Slalom.

**Slide body:**

> The patterns and the war story in this deck are drawn from a real engagement. Client name, team names, product names, and any identifying technical detail have been removed. The framing — industrial-equipment OEM, ~10-engineer team — is the only context kept.
>
> This deck is **Slalom-internal**. Please don't forward it externally, post it, or quote it outside this room without checking first.

**When to use:** open the deck with this slide whenever the audience is more than 1:1 with Eugene. Skip for the Eugene 1:1 itself — he already knows the context.

**Talk track (~20s):** read the second paragraph verbatim. Don't soften it.

---

**B3 — Scope of this artifact (what's NOT being claimed).** Pre-empts the "but…" question — the templates aren't tested at Slalom scale yet, the patterns aren't claimed to be exhaustive, the framing isn't claimed to be the only model.

**Title:** *What this deck is — and isn't — claiming.*

**Sub-line:** Three things worth being explicit about, in case the room is asking them silently.

**Slide body — three short blocks:**

- **Not claiming the patterns are exhaustive.** Five patterns from one engagement, sharpened by what kept showing up elsewhere. There are more. These are the ones that hurt the most.
- **Not claiming the artifacts are tested at Slalom scale yet.** They're drawn from prod, but they haven't been run across multiple engagements as a Slalom asset. That's what the pilots in slide 11 are for.
- **Not claiming this is the only model.** Other framings of the same problem space exist. The Dave Messina conversation on slide 11 is partly to find them and reconcile.

**Footer line:**

> Naming the boundary makes the artifact stronger, not weaker.

**When to use:** add this slide if the audience is broader than Eugene and skews skeptical or senior-engineer. Skip for the Eugene 1:1.

**Talk track (~45s):** read the three claim boundaries cleanly. End on the footer line.

---

## Open decisions before filling content

- **Slide count:** skeleton sits at 12 + 3 backup. Comfortable for ~20 min. If Eugene wants tighter, collapse slides 4–7 into one "five patterns" slide with rotating focus → 9 slides total. Decide after first draft.
- **Visual identity:** plain Slalom template, or custom? Default = Slalom template.
- **Diagrams needed:** slide 6 needs a 2-column layout sketch. Slide 8 needs a "design → review → operate" loop visual. Slide 3 might want a small icon-per-pattern strip. Decide during content pass.
- **War-story slide (B1) — promote to main deck?** If yes, becomes slide 7.5; pushes Pattern 5 → slide 8, etc. Recommend keep as backup unless Eugene's audience is mostly engineers.

---

## Next step

Fill slide-by-slide, starting with the strongest = **Slide 6** (Patterns 3+4 — the AI-PR playbook setup). Then slide 8 (the offer). Then slide 2 (the anchor). Then the rest in order.
