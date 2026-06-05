# Arch-Hive deck — diagrams folder

Mermaid drafts for the three diagram-heavy slides in [`../arch-hive-slides-v2.md`](../arch-hive-slides-v2.md). Each file is self-contained: spec recap → Mermaid source → PPT-pass notes → open visual decisions.

| Slide | File | What it shows |
|---|---|---|
| **4** | [`slide-04-overview.md`](slide-04-overview.md) | Complete-flow overview — 3 zones (pipeline / shared index / agents), 2 highlighted boxes for my scope, Unit Risk shown muted (separate team). |
| **5** | [`slide-05-pipeline.md`](slide-05-pipeline.md) | FSR pipeline — Bronze/Silver/Gold medallion bands with metadata registry as the spine + work queue. Red dashed status write-back arrow closes the loop. |
| **7** | [`slide-07-adhoc-qa.md`](slide-07-adhoc-qa.md) | AdHoc QA agent — 3 zones (user/context · agent core · tools+data). Retrieval tool lands on the same VS index box used on Slide 4. |

## Iteration workflow

1. **Review the Mermaid render** inline (VS Code preview, or paste into mermaid.live).
2. **Capture feedback in the "Open decisions" section** of each file — don't edit silently, keep the trail.
3. **Iterate the Mermaid source** until the layout reads cleanly.
4. **For PPT export**, screenshot the rendered Mermaid → place on slide → add the floating text labels listed in the PPT-pass notes ("my scope" tags, scope callouts, etc.).
5. **If a slide needs editable shapes** (likely Slide 5 because of the registry spine), convert that one to drawio and use the Mermaid as the structural reference.

## Confidentiality posture (applies to all three)

- Component names by **role only** — no project codenames, no product names, no vendor names except UC Volumes and Vector Search (architecturally relevant).
- No real volume paths, no real table names, no schema fields beyond the generic status/retry pattern.
- LLM and embedding model names — only on Slide 10 (tech stack). Never on diagrams 4 / 5 / 7.
