# Integration Map

This note connects the Databricks work in this repository to the downstream application repository that consumes the resulting data.

## Scope split

- This repository owns Databricks-side analysis, pipeline planning, reference code review, and future production pipeline implementation.
- The sibling app repository owns services, agents, assistants, and orchestration that consume the resulting data.

## Sibling repository

Path:

`/home/u560060992/uai3071390-genai-services-demand-generation-usecase`

## Recommended way to work across both repos

1. Open both repositories in one multi-root VS Code workspace when you need end-to-end tracing.
2. Keep design decisions and pipeline notes in this repository.
3. Inspect consumption behavior in the sibling repo without copying its code here.
4. If you learn something durable about the integration, document it here and optionally link back to the exact app-side location in your working notes.

## First places to inspect in the app repo

| Path | Why start here |
|---|---|
| `README.md` | High-level runtime and service topology |
| `backend/services/data-service/` | Most likely data access and retrieval integration surface |
| `backend/agents/orchestrator/` | Downstream coordination layer |
| `backend/agents/question-answer-agent/` | Likely consumer for retrieval-backed interactions |
| `docs/` | App-level technical notes |

## When to update this note

Update this file whenever you confirm where Databricks tables, vector search endpoints, or retrieval outputs are being consumed by the app stack.
