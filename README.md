# ai-arch

Personal space for AI architecture learning, prep, and showcase work. FSR is the running example, but the goals are broader.

## Three goals

1. **Databricks Certified Generative AI Engineer Associate — exam 2026-05-23.** Nearest, hardest deadline. See [cert-prep.md](cert-prep.md).
2. **Interview prep** — be ready for AI Solutions Architect interviews: fundamentals (chunking, embedding, retrieval, evaluation, guardrails), system design, trade‑offs, and being able to explain choices clearly.
3. **Slalom presentation** — present the FSR architecture and design to a wider Slalom audience, including aha‑moments and highlights from the production support / backfill work.

## Contents

- [tracker.md](tracker.md) — **start here.** Where I am right now, what's next, session log. I steer; this is the source of truth for state across chat sessions.
- [cert-prep.md](cert-prep.md) — Databricks GenAI cert: syllabus map, must‑knows, 14‑day study plan, vocabulary cheat sheet.
- [SETUP.md](SETUP.md) — local venv + LiteLLM gateway setup. Run notebooks in VS Code Jupyter.
- [decisions.md](decisions.md) — running log of tech choices and trade-offs, written as interview-ready talk tracks.
- [learning-plan.md](learning-plan.md) — reference: concepts, vocabulary, "say it" prompts. Not a strict order — dip in as needed.
- [asks.md](asks.md) — the hands‑on POC framing (parse → chunk → embed → retrieve → metadata) on real FSR docs.
- [code/](code/) — step‑by‑step notebooks, organized **bronze / silver / gold** to mirror prod.
- [sample-docs/](sample-docs/) — the FSR PDFs we run the POC on.
- [dbx-genai-course/](dbx-genai-course/) — official Databricks training material (Weeks 1–4).
- _(later)_ `presentation/` — Slalom deck outline, narrative, diagrams, demo notes.

## Order of work

1. **Cert prep (priority — hard deadline May 23).** Tracked in [cert-prep.md](cert-prep.md). 14‑day study plan.
2. **Phase 1 POC** — get one FSR through the full loop end‑to‑end. Tracked in [tracker.md](tracker.md). Doubles as hands‑on for cert + interview + presentation.
3. **Phase 2 POC** — revisit each stage, try alternative methods, capture learnings.
4. Fill in interview talking points as concepts solidify.
5. Build the Slalom presentation using the architecture from `pw_sdg_ai_ser_repo` + stories from `fsr-prod-ops/` + aha‑moments captured during the POC.
