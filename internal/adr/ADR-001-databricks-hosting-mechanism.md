# ADR-001: Databricks Service Hosting Mechanism

| Field | Value |
|---|---|
| **Status** | PENDING |
| **Date** | 2026-04-06 |
| **Decision owners** | Databricks team + DEV team |
| **Context** | Each tool (query_fsr, query_er, etc.) is a separate Databricks-hosted REST service. We need to decide how to host it. |

---

## Context

We have decided (see doc 03, doc 05) that retrieval tools will be **separate services hosted on Databricks**, called over HTTP by the data-service running in AWS ECS. We need to choose the hosting mechanism.

The service needs to:
- Expose a REST endpoint (POST)
- Run Python code (FastAPI or equivalent)
- Access Databricks Vector Search, Delta tables, and the built-in reranker directly
- Support authentication (JWT / PAT token / Ping ID passthrough)
- Be callable from the AWS VPC over HTTPS

---

## Options Considered

### Option A: Databricks Model Serving (Custom Endpoint)
- Deploy a Python model or `pyfunc` wrapper as a Model Serving endpoint
- Mature, production-grade, built-in autoscaling and monitoring
- Native access to VS, Delta, and `DatabricksReranker`
- Auth: Databricks PAT or M2M token
- URL pattern: `https://<workspace>/serving-endpoints/<name>/invocations`
- **Con:** Input/output schema is constrained by the serving framework; may require wrapping the FastAPI logic

### Option B: Databricks Apps
- Deploy a full web app (FastAPI/Flask) directly on Databricks
- More flexible — full HTTP server, custom routes, custom response shapes
- Newer feature — GA status and enterprise support level to verify
- Native access to workspace resources
- **Con:** Less mature than Model Serving; operational tooling still evolving

### Option C: Databricks Job + REST Trigger
- Trigger a Databricks Job via the Jobs API; poll for result
- **Con:** High latency (job startup time), not suitable for synchronous retrieval calls

### Option D: External Microservice (non-Databricks hosted)
- Deploy a FastAPI service in AWS ECS that calls Databricks VS + SQL via API
- This is essentially what the current `retriever_service.py` does (partially)
- **Con:** Loses the "inside Databricks" advantage; reranker access is harder; adds network hops

---

## Questions for Databricks Team

1. Is **Databricks Model Serving** the recommended path for hosting a custom REST retrieval service in this workspace?
2. Is **Databricks Apps** GA and supported for production workloads in this environment?
3. What is the recommended authentication mechanism for service-to-service calls from AWS ECS → Databricks endpoint? (PAT token? M2M OAuth? Ping ID passthrough?)
4. Is the VS endpoint (`pw-ser-sdg-vector-search`) accessible from within a Databricks-hosted service, or only from outside?
5. Is `DatabricksReranker` available in the serving / apps runtime, or only in interactive cluster notebooks?
6. What is the network path from Databricks-hosted service → LiteLLM proxy for embedding generation?

---

## Decision

> **[PENDING]** — Awaiting input from Databricks team.

---

## Consequences (once decided)

- Determines project structure for the Databricks layer (`databricks_layer/`)
- Determines how we package and deploy the service (notebook vs Python package vs Docker)
- Determines how auth tokens are passed and rotated
- Informs ADR-006 (service internal structure)
