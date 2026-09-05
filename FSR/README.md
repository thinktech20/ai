# FSR (Field Service Report) — design + active workstreams

Single root for FSR design, ESN-resolution workstream, chunking, and related materials. OSA design will land here as a sibling section.

## Layout

| Path | Purpose |
|---|---|
| [fsr-pipeline-design.md](fsr-pipeline-design.md) | Canonical end-to-end pipeline design (P1 metadata → P2 chunks → VS sync). |
| [production-readiness-plan.md](production-readiness-plan.md) | Production hardening plan + rollout. |
| [step8-scale-full-corpus.md](step8-scale-full-corpus.md) | Full-corpus scale-up plan. |
| [chunk-integrity-fix.md](chunk-integrity-fix.md) | Chunk-integrity issue + fix design. |
| [metadata-first-end-to-end-flow.drawio](metadata-first-end-to-end-flow.drawio) | Architecture diagram source. |
| [chunking-fix/](chunking-fix/) | Chunking-strategy workstream (plan, tracker, validation). |
| [ESN-resolution/](ESN-resolution/) | UI-15 active workstream — proper ESN extraction + multi-ESN data model. See [ESN-resolution/design/proposed-multi-ESN-design.md](ESN-resolution/design/proposed-multi-ESN-design.md). |
| [fsr-docs/](fsr-docs/) | External-facing docx artifacts (Confluence design, runbook + guide). |

## Where things live

- **Design** → here (`FSR/`).
- **Day-to-day prod ops** (tracker, daily standup, prod issues, validations) → [`../fsr-prod-ops/`](../fsr-prod-ops/).
- **Pipeline code** → [`../pw_sdg_ai_ser_repo/`](../pw_sdg_ai_ser_repo/).
- **ADRs** (cross-area, promoted from design here) → [`../internal/adr/`](../internal/adr/).

## OSA

OSA (One Service App) design + data-source analysis will land alongside the FSR sections in this root once kicked off. Cross-cutting docs (FSR ↔ OSA boundaries) live at this level too.
