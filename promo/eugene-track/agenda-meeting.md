# Meeting agenda — Madhurima ↔ Eugene

**Purpose:** Close the loop on Eugene's standing ask about patterns/templates for AI in production. Walk through what came out of the FSR client delivery, share the draft artifacts, and get his input on shape + where it could plug in for other teams.

**Duration:** 30 min (45 if we go deep on the playbook)
**Format:** Walkthrough + discussion. Deck optional, can send ahead.

---

## Short invite text (keep open + short)

> Hi Eugene — wanted to set up a quick 30 min to walk you through the AI-in-production patterns work I've been pulling together from the client delivery. Picking up on the thread you'd started a while back — would also love your thoughts on where I can take this next. Will share more details + deck ahead of the call. Pick whatever slot works on your calendar.

---

## Agenda (full, for the actual meeting)

### 1. Context — what I've been working on (5 min)
- Quick brief on the AI build at the client (FSR — financial services regulatory doc pipeline on Databricks)
- My role: AI architecture + production delivery — design, build, validation, prod ops
- Why this is the right base for the patterns conversation: shipped real AI to prod, hit and resolved real issues, now have lessons worth packaging

### 2. The five patterns (15 min)
Patterns pulled from what actually broke / what actually worked in production:
1. **Design** — AI-assisted design scaffold (one-pager that catches gaps early)
2. **AI iteration loop** — how to debug when the AI is the system
3. **Looks-correct ≠ prod-ready** — what slips past dev validation
4. **Reviewing AI-generated code is a different job** — author-side + reviewer-side responsibilities
5. **Operate** — what production AI needs that traditional systems don't

### 3. The two artifacts (10 min)
- **Design scaffold (one-pager)** — for teams kicking off AI builds
- **AI-assisted PR playbook** — author half + reviewer half
- Eugene's input wanted on:
  - Does the framing land?
  - What to sharpen / cut
  - Where it should plug in (which teams, which forums)
  - Format — internal article, brown bag, template repo, etc.

### 4. Close (2 min)
- Next step + target date for v1 of the artifacts
- Cadence — more frequent touch points going forward (per Eric's 5/20 input)

---

## Reference material to have open
- [arch-hive-slides-v2.md](arch-hive-slides-v2.md) — Friday Arch-Hive deck (5-pattern spine)
- [eugene-slides.md](eugene-slides.md) — Eugene-cut variant of the same spine
- [artifact-outline.md](artifact-outline.md) — Combined Package outline (Part A Arch-Hive + Part B Eugene artifact)
- [../Eric-track/brand-plan.md](../Eric-track/brand-plan.md) — "End of May" milestone row
