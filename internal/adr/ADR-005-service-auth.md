# ADR-005: Authentication for Databricks-Hosted REST Endpoints

| Field | Value |
|---|---|
| **Status** | PENDING |
| **Date** | 2026-04-06 |
| **Decision owners** | DEV team + Databricks team |
| **Context** | The Databricks-hosted `query_fsr` (and other tools) are called by the data-service running in AWS ECS. Auth must be secure and operationally manageable. |

---

## Context

The data-service (AWS ECS) will make HTTP POST calls to Databricks-hosted services. The existing app already authenticates users via GEV Ping ID (JWT). The tool spec requires logging the calling identity per request.

Current Databricks access in data-service uses a PAT token (`DATABRICKS_TOKEN`, `VECTOR_DATABRICKS_TOKEN`) stored as env vars (secrets).

---

## Options Considered

### Option A: Databricks PAT token (current pattern)
- Service-to-service: data-service passes a long-lived PAT in the `Authorization: Bearer` header
- Simple; already used today
- **Con:** Long-lived tokens are a security risk; rotation is manual; no per-user identity tracing
- **Con:** Doesn't satisfy "log calling user" requirement in tool spec — all calls look like the same service account

### Option B: M2M OAuth (Machine-to-Machine)
- data-service authenticates with Databricks using OAuth client credentials (service principal)
- Short-lived tokens; automatic refresh; better security posture
- Databricks supports M2M OAuth natively
- **Con:** More setup (register service principal, configure scopes)

### Option C: Ping ID JWT passthrough
- The end-user's Ping ID JWT is forwarded from the React frontend → data-service → Databricks endpoint
- Databricks validates the JWT and logs the actual user identity
- Satisfies "log authenticated user identity" per tool spec
- **Con:** Requires Databricks to trust the GEV Ping ID OIDC provider; token TTL management
- **Con:** Service-to-service calls (e.g. orchestrator → data-service, not triggered by a live user) have no user JWT

### Option D: Hybrid — M2M for service calls, Ping ID for user-initiated calls
- Background / batch calls: M2M OAuth service principal
- User-initiated Q&A / real-time calls: Ping ID JWT passthrough
- Most complete; satisfies both audit logging and security requirements
- **Con:** Two auth paths to implement and maintain

## Additional Context (Apr 17 Walkthrough)

The Databricks team's standard auth pattern for **pipeline execution** (Airflow→Databricks) was confirmed:
- **Functional SSO** → PAT stored in AWS Secrets Manager → `databricks_connection_module` retrieves it at runtime
- Two FSSO types: ETL FSSO (write/processing), Consumption FSSO (read-only)
- **Databricks secret scopes** (not direct AWS calls from notebooks): scope named after functional SSO, secrets stored as key-value pairs, access controlled by group/role membership
- The PAT in Databricks secret scope is NOT synced from AWS Secrets Manager yet (platform team working on it), so they manually maintain both

This applies to the **pipeline auth** path. The **service auth** question (data-service → query endpoint) is a separate concern and remains open per the options above.

---

## Questions for DEV / Databricks Team

1. Does the Databricks workspace already have a registered service principal for the SDG use case?
2. Is GEV Ping ID configured as a trusted OIDC provider in the Databricks workspace?
3. What is the preferred token storage mechanism in AWS ECS? (Secrets Manager? Parameter Store?)
4. Does the tool spec's "log authenticated user identity" requirement apply to all calls, or only user-initiated (Q&A) calls?
5. Is there an existing auth pattern used by other Databricks-hosted services in this workspace that we should follow?

---

## Decision

> **[PENDING]** — Awaiting DEV team + Databricks team alignment.

---

## Consequences (once decided)

- Determines how `DATABRICKS_TOKEN` / `VECTOR_DATABRICKS_TOKEN` env vars evolve
- Determines what the `Authorization` header looks like in data-service → Databricks calls
- Affects query logging implementation (user field in log)
