# 01 — Project Overview

## What We're Building

A multi-tool RAG platform for GE Vernova, serving two engineering personas, built on top of **Databricks** (Vector Search, Delta Lake, Model Serving) and deployed as REST endpoints consumed by an AWS-hosted application layer.

---

## Personas & Their Workflows

### RE — Reliability Engineering
Assesses equipment risk and generates summaries.

| Step | Tool(s) |
|---|---|
| Read unit risk matrix | `read_risk_matrix` |
| Retrieve FSR evidence | `query_fsr` |
| Retrieve ER evidence | `query_er` |
| Read structured data | `read_ibat`, `read_prism` |
| Evaluate risk | RE Risk Evaluation Chain |
| Generate narrative | RE Narrative Summary |
| Q&A | RE AdHoc Q&A Agent |

### OE — Outage Engineering
Generates event history and risk assessments for outages.

| Step | Tool(s) |
|---|---|
| Read event master | `read_event_master` |
| Retrieve FSR evidence | `query_fsr` |
| Retrieve ER evidence | `query_er` |
| Read structured data | `read_ibat` |
| Evaluate risk | OE Risk Evaluation Chain |
| Generate event history | Event History & Key Findings |
| Generate narrative | OE Narrative Summary |
| Q&A | OE Q&A Agent |

---

## Tool Inventory (MVP1)

| Tool | Type | Data Source | Status |
|---|---|---|---|
| `query_fsr` | RAG retrieval | FSR PDFs → Delta + VS | In progress (4e) |
| `query_er` | RAG retrieval | ER documents → Delta + VS | Experiments done (4d) |
| `read_risk_matrix` | Structured read | Excel in Box → Databricks volume | Spec done (4a) |
| `read_ibat` | Structured read | Gold table in Databricks | Spec done (4c) |
| `read_prism` | Structured read | Gold table in Databricks | Spec done (4b) |
| `read_event_master` | Structured read | Gold table in Databricks | Spec done (4h) |
| `read_re_table` | Structured read | RE output table in Databricks | Spec done (4g) |
| `read_re_report` | Structured read | RE narrative in Databricks | Spec done (4j) |
| `read_oe_table` | Structured read | OE output table in Databricks | Spec done (4n) |
| `read_oe_report` | Structured read | OE narrative in Databricks | Spec done (4p) |

---

## Data Source Inventory

| Source System | Data Type | Ingestion Method | Tools That Use It |
|---|---|---|---|
| Event Reports (ER DB) | Structured SQL | Batch JDBC | `query_er` |
| FieldVision / Box | Unstructured PDF | API / Cloud Storage | `query_fsr` |
| IBAT Equipment Master | Structured | API | `read_ibat`, FSR enrichment |
| PRISM | Structured SQL | SQL Connect | `read_prism` |
| Event Vision | Structured | API | `read_event_master`, FSR enrichment |
| OSA Tool | Semi-structured DOCX | File Ingestion | Milestone context |
| Process Docs | PDF | Cloud Storage | Technical manuals, GEK, TILs |

---

## Databricks Medallion Architecture

Data flows through four Unity Catalog layers:

```
Bronze (VIUD — raw)  →  Silver (VIUP — OCR/normalized)  →  Gold/RAG (VAID)  →  Gold/App (VAIP)
```

| Layer | Catalog | Content |
|---|---|---|
| Bronze | VIUD (Unstructured Ingestion) | Raw FSR PDFs, ER JSONs, Word docs — exact copies for traceability |
| Silver | VIUP (Processed Unstructured) | OCR output, ISO-normalized metadata, standardized ER numbers |
| Gold (RAG) | VAID (AI Curated) | Vector embeddings, chunk tables, AI-ready datasets |
| Gold (App) | VAIP (AI Consumption) | Pre-computed risk profiles, fleet heat maps, narrative outputs |

---

## Architecture Overview

### Platform Infrastructure
```
Web Client (GEV Ping ID)
  → Application Load Balancer
    → ECS Fargate (AWS)
        ├── UI Application (React)
        ├── LangGraph Orchestrator
        ├── Data Services
        └── Assistants:
            ├── Risk Evaluation Assistant
            ├── Narration Summarization Assistant
            ├── Event History Assistant
            └── Question & Answer Agent
  → DynamoDB (state, outputs, summaries, reports)
  → Amazon S3 (checkpointing, agent memory)

LangGraph Orchestrator → Data Services → Databricks (private subnet)
                                           ├── Naksha REST Endpoint
                                           └── Unstructured REST Endpoint

Shared AWS Account (Foundation Services)
  ├── LiteLLM Enterprise Proxy (embeddings + LLM calls)
  ├── Foundation Services API
  └── OpenSearch Interface Endpoint
```

### Databricks Role
- **Delta Lake**: chunk storage, structured gold tables, output tables
- **Vector Search**: FSR and ER embedding indexes
- **Hosted Services**: each tool (`query_fsr`, `query_er`, etc.) is a **separate Databricks-hosted REST service** — NOT implemented inside the data-service
- **Embedding**: Azure OpenAI `azure-text-embedding-3-large-1` (3072-dim) via LiteLLM

### Tool Interface
- All tools are **REST endpoints only** — no MCP
- Tools are **hosted on Databricks** (Model Serving, Databricks Apps, or similar)
- The data-service (AWS ECS) calls these Databricks endpoints over HTTP
- DEV team owns URL paths, HTTP methods, and auth mechanism

---

## Key Design Principles (from DS team)
1. **ESN-scoped retrieval** — every retrieval tool filters by `generator_serial` (Equipment Serial Number) first
2. **Two-stage assembly** — Vector Search returns minimal columns; metadata is enriched in a second SQL pass
3. **Criteria-augmented queries** — appending severity criteria text to the user query improves recall
4. **REST-first** — all tool interfaces implemented as REST for the time being
5. **Hybrid retrieval as default** — Databricks native HYBRID (dense + BM25 via RRF) is the production baseline
