# Eugene Deck — PPT Copy-Paste Content (short version for first pass)

> **Use:** copy-paste source for the PowerPoint. Slide content only — no intent, talk tracks, or layout notes (those live in [eugene-slides.md](eugene-slides.md)).
> **Slide count:** 4 slides. First-pass version for Eugene review — get the point across, see what pulls, then expand.
> **Full 12-slide version:** [eugene-slides.md](eugene-slides.md) (kept as the deeper draft to draw from when expanding).

---

## Slide 1 — Title

**Title:** Building with AI: what teams need that the coding tools don't give them.

**Sub-line:** Patterns from recent work shipping AI-assisted features to production — and the artifacts that close the gaps they expose.

*Footer: presenter name + role + date.*

---

## Slide 2 — Where this came from

**Title:** Where this came from.

**Sub-line:** One observation from a recent engagement, repeated across teams the more it gets looked at.

**Body — three short blocks:**

**The setup.**
A ~10-engineer cloud-services team at an industrial-equipment OEM was building an AI-assisted feature on top of a data pipeline our team had shipped. Skilled engineers, current-generation AI tools, a real production target. Customer directive: use AI for everything, ship fast — no guardrails on how.

**What happened.**
The feature read well in dev. It broke down on real production data — wrong outputs in edge cases, behavior the team couldn't explain when pressed, fixes that introduced new bugs. What looked like progress was mostly rework.

**What was actually missing.**
The AI tools weren't the problem — they produced plausible code on demand. What was missing was the practice around them: a design step before code started landing, a review posture that catches the way AI bugs cluster, operating defaults that catch the quiet failures these systems show in prod. That's the gap this talk is about.

---

## Slide 3 — Patterns that kept showing up

**Title:** Patterns that kept showing up.

**Sub-line:** Different teams, same shape. Each one is a different point in the lifecycle — design, build, review, operate.

**Body — table:**

| Pattern | The trap | The move |
|---|---|---|
| **Skipping design because AI fills the silence** *(design)* | The friction that used to *force* a design conversation is gone. Code starts landing before the design exists. | One-page design before the assistant writes a line — contract, eval, failure modes, blast radius, what's out of scope. |
| **The "ask it again" loop** *(build)* | Generated code breaks. Paste the error back. Accept the next version. Two iterations in, the code is structurally incoherent and nobody can explain why it works. | Grill the first answer, not the third. Make the assistant defend its assumptions before the code lands. The real design conversation belongs at the first pass. |
| **Looks-correct ≠ prod-ready** *(prod-readiness)* | AI code passes a casual reading. It quietly skips idempotence, error envelopes, secret handling, retry caps, observability — the things that hurt the first time it hits real prod traffic. | An author-side prod-readiness pass before the PR goes up. Same checklist every time. Catches the omissions a happy-path test won't. |
| **Reviewing AI-generated code is a different job** *(review)* | Human bugs cluster around intent. AI bugs cluster around plausibility — hallucinated APIs, fabricated config keys, libraries used the wrong way, patterns shaped like the codebase convention but off by one assumption. | Shift the review question from *"does this look reasonable?"* to *"does this actually call something that exists, with the contract it actually has?"* Run the code path; don't just read it. |
| **AI systems fail quietly in production** *(operate)* | Model drift, prompt regression, silent extractor change, nulls instead of stack traces. None of these page — they show up later as a consumer complaint. | Operating defaults on day one: lifetime retry counters, typed failure-category enums, dry-run defaults, snapshot-before-write, same-notebook revert. |

---

## Slide 4 — Closing the loop, and where this can be automated

**Title:** Closing the loop — and where this can be automated.

**Sub-line:** Three artifacts, one per gap in the lifecycle. v1 is a drop-in template the team can use tomorrow. v2 is an agent that enforces the discipline where the work actually happens — in the IDE, on the PR, on the on-call channel.

**Body — table:**

| Artifact | Manual form (v1 — drop-in template) | Automated form (v2 — agent) |
|---|---|---|
| **AI design scaffold** *(design step)* | One-page design — contract, eval, failure modes, blast radius, scope — the team fills in before the assistant writes a line. | Chat-mode agent that interviews the engineer through the fields, won't let any get skipped, and writes the design doc into the repo. Refuses to start code generation until the gaps are closed. |
| **AI PR playbook** *(review step)* | Two-half checklist. Author runs the prod-readiness half before pushing. Reviewer runs the plausibility-check half on the PR. | Paired agents on the PR. Author-side runs prod-readiness checks on the diff at push time. Reviewer-side posts plausibility comments — hallucinated APIs, fabricated config keys, library misuse — before a human ever opens the PR. |
| **AI ops defaults** *(operate step)* | One-page set of defaults adopted day one of prod — lifetime retry counters, failure-category enums, dry-run defaults, snapshot-before-write, same-notebook revert. | Triage agent that reads the failure-category enum + recent runs and surfaces the matching diagnostic when a quiet failure shows up. The defaults themselves stay a doc — they're code patterns, not agent behavior. |

**Footer:**
Templates ship first because they're faster to validate on a real engagement. Agents follow wherever templates land — same content, new surface. Open question for Eugene: which one has the most pull for the teams you're closest to — and which one is the better first bet for the agent form?
