# Internal

This is the canonical working area for the Databricks side of the SDG use case.

Use this folder for detailed technical thinking, decisions, gap analysis, implementation planning, working status, and integration notes.

## What lives here

| Path | Purpose |
|---|---|
| [README.md](README.md) | Internal index and usage rules |
| [current-status.md](current-status.md) | Resume point, current state, and next actions |
| [integration-map.md](integration-map.md) | Cross-repo map to the downstream app workspace |
| [tasks/](tasks/README.md) | Task-based intake for urgent or short-lived requests |
| [adr/](adr/README.md) | Architecture Decision Records |
| [reviews/](reviews/) | Review findings and assessments |
| [notes/](notes/) | Supporting research notes |
| [architecture-assets/](architecture-assets/) | Diagrams and visual assets |
| [summaries/](summaries/README.md) | Concise walkthrough summaries kept under the same canonical docs area |
| [comms/](comms/) | Communication drafts and outbound notes |
| [learnings/](learnings/) | Practical setup/debug notes worth preserving |

For active FSR processing design, use [implementation/design/](../implementation/design/README.md).

## Core document set

| File | Purpose |
|---|---|
| [01-project-overview.md](01-project-overview.md) | Overall scope, personas, tool inventory, and architecture context |
| [02-fsr-findings.md](02-fsr-findings.md) | FSR chunking and retrieval experimentation results and decisions |
| [03-fsr-implementation-plan.md](03-fsr-implementation-plan.md) | Step-by-step plan for building the `query_fsr` Databricks service |
| [04-data-catalog.md](04-data-catalog.md) | Tables, schemas, vector search indexes, and joins |
| [05-app-code-analysis.md](05-app-code-analysis.md) | App-side data-service structure and current Databricks usage |
| [06-pipeline-code-analysis.md](06-pipeline-code-analysis.md) | DS reference pipeline analysis |
| [07-fsr-metadata-extraction.md](07-fsr-metadata-extraction.md) | Metadata extraction pipeline notes |
| [08-known-gaps-and-risks.md](08-known-gaps-and-risks.md) | Detailed internal gap register |
| [task-plan.md](task-plan.md) | Detailed task breakdown and sequencing |

## Working rules

- Internal docs are the source of truth.
- Put durable findings here first, then summarize them into [summaries/](summaries/README.md) when a shorter walkthrough version is useful.
- Do not create new date-based folders for active work.
- Use [tasks/](tasks/README.md) for urgent requests, then merge lasting outcomes into the canonical docs.
- Delete raw session dumps and superseded working sets once their durable content has been merged.

## Status snapshot

| Component | Status |
|---|---|
| FSR chunking and retrieval experiments | Complete as DS reference work |
| `query_fsr` tool spec | Written by DS; implementation decisions still need to be finalized |
| FSR Databricks ingestion pipeline | Not started as production implementation |
| `query_fsr` retrieval service | Partially implemented in the app stack; gaps still exist |
| App code review | Complete |
| DS reference pipeline review | Complete |

## Conventions

- Decisions that are locked are marked `[DECIDED]`.
- Decisions still open are marked `[OPEN]`.
- Items waiting on external input are marked `[BLOCKED]`.
