# 05 — Roadmap

**Status:** Draft — pending review
**Note:** Timeline placeholders — to be confirmed with the team.

---

## Overview

Work is organized into four phases. Phases 0 and 1 can run in parallel to some extent. Phases 2 and 3 depend on decisions from Phase 1.

---

## Phase 0 — Immediate (Now)

**Goal:** Establish shared understanding. No blocking decisions needed.

| Task | Status |
|---|---|
| Post gaps doc to Confluence | Ready — pending team approval |
| Build working end-to-end `query_fsr` notebook (Steps 1–6 against POC tables) | In progress |
| Resolve access / coordination questions (Q7, Q10) | [OPEN] |
| Connect with Databricks architect team | [OPEN — intro needed] |

**Deliverable:** Working notebook demonstrating full query pipeline. Gaps doc on Confluence.

---

## Phase 1 — Pre-Build Decisions ([TBD DATE])

**Goal:** Close all blocking decisions so the production build can start.

| Decision | What it unblocks |
|---|---|
| Hosting mechanism (Q1) | Service scaffold, packaging, auth |
| Embedding model (Q2) | VS index configuration, processing pipeline update |
| Reranking policy (Q3) | Service spec update |
| Document type classification approach (Q4) | Processing pipeline new step |
| Production catalog structure (Q6) | Table creation |
| Write access + LiteLLM key (Q7) | Running pipelines end-to-end |

**Deliverable:** ADRs closed. Service scaffold ready. Production table schema agreed.

---

## Phase 2 — Production Processing Pipeline ([TBD DATE])

**Goal:** Build production-quality processing pipeline with document type classification.

| Task | Notes |
|---|---|
| Add document type classification step | Before chunking — approach TBD from Phase 1 |
| Unify embedding model (fix Gap 6) | VS index must use same model as query |
| Run processing pipeline against production Volume | Write to `vaid.*` production tables |
| VS index sync and validation | Confirm index is searchable, recall metrics preserved |
| Metadata extraction pipeline connected | `fsr_scraped_file_mapping_ref` wired to retrieval |

**Deliverable:** Production Delta table + VS index populated. Processing pipeline running on schedule.

---

## Phase 3 — Query Service Updates ([TBD DATE])

**Goal:** Review and adapt the existing `query_fsr` service implementation based on decisions from Phase 1. The service is already implemented — this phase covers targeted modifications only.

| Task | Notes |
|---|---|
| Review existing implementation against gap decisions | Embedding model (Q2), reranking policy (Q3), metadata join (Q9) |
| Update embedding model if changed (Q2) | Must match ingest model |
| Update reranking behavior if policy changes (Q3) | Mandatory vs configurable |
| Wire metadata join if `fsr_scraped_file_mapping_ref` is ready (Q9) | Steps 4–5 of query spec |
| Validate against production tables | Once `vaid.*` tables exist (Phase 2) |

**Deliverable:** Query service validated and updated against production data. End-to-end flow confirmed.

---

## Dependencies

```
Phase 0 ──→ Phase 1 (decisions) ──→ Phase 2 (processing) ──→ Phase 3 (query service)
                                  ↘                       ↗
                                   Phase 1 also unblocks Phase 3 scaffold
```

Phase 2 and Phase 3 can be worked in parallel once Phase 1 decisions are made.

---

## [PLACEHOLDER] — To Confirm

- [ ] Do these phases align with the MVP2 planning timeline?
- [ ] Is Phase 0 notebook work a useful shared artifact for the team?
- [ ] Who reviews / approves the production processing pipeline before it writes to `vaid.*`?
- [ ] Is there a formal MVP2 scope doc we should align this roadmap to?
