# 01 — POC Assessment: Current State

**Status:** Draft — pending review

---

## What This Document Covers

Our understanding of the FSR retrieval POC as it exists today — what has been built, what data is available, and how the pipeline works. This is the baseline before proposing production changes.

---

## 1. What Exists Today

### Data and Tables

| Table | Catalog | Description | Status |
|---|---|---|---|
| `field_service_report` | `main.gp_services_sdg_poc` | Full-corpus FSR chunks (all PDFs, all ESNs) | Exists — POC |
| `field_service_report_gt_litellm` | `main.gp_services_sdg_poc` | 30-ESN ground-truth subset for evaluation | Exists — POC |
| `fsr_scraped_file_mapping_ref` | `main.gp_services_sdg_poc` | 15-field scraped metadata per PDF (3-stage pipeline) | Exists — **not connected to retrieval** |
| `fsr_pdf_ref` | `vgpd.fsr_std_views` | SOT: formal PDF → ESN links | Exists — transform table by data team |
| Production tables (`vaid.*`) | TBD | Production Unity Catalog tables for MVP2 | **Do not exist yet** |

### Vector Search

| Index | Embedding model | Status |
|---|---|---|
| `vs_field_service_report` | `databricks-gte-large-en` (auto-embed at sync) | Exists — full corpus |
| `vs_field_service_report_gt_litellm` | `azure-text-embedding-3-large-1` (LiteLLM at processing time) | Exists — 30-ESN subset |

### Pipeline Code (DS reference)

| Codebase | Purpose | Status |
|---|---|---|
| `fsr_pipeline` | Full-corpus processing (chunk → Delta → VS) + smoke test | Exists — POC, has known issues (see Gaps doc) |
| `fsr_pipeline_gt_direct` | 30-ESN GT subset, full eval harness | Exists — POC, most reliable eval signal |
| `fsr_scraping` | 3-stage metadata extraction pipeline | Exists — POC, output not wired to retrieval |

---

## 2. Processing Flow — Our Understanding

```
Volume (all PDFs — FSRs, TILs, manuals, ERs, etc.)
  ↓
Step 1: Open each PDF — scrape first page + chunk full text
         Chunking: recursive hierarchical, 4000 chars / 200 overlap (V3)
         ESN identification: 4-layer (regex → filename → LLM → SOT ref view)
  ↓
Step 2: Write chunks to Delta table (one row per ESN per chunk)
         Join SOT ref view (fsr_pdf_ref) at write time for ESN + report_date
  ↓
Step 3: Vector Search delta-sync
         VS auto-embeds chunk_text at sync time
  ↓
Step 4: Index ready for HYBRID search
```

**Key detail — document discovery (two sources):**
The pipeline links PDFs to ESNs from two sources and takes the union:
- **SOT** (`fsr_pdf_ref`): formal links maintained by the data team
- **LLM scan**: one GPT-4o call per PDF, qualifies ESN if ≥1 mention AND ≥10% of all ESN mentions in that doc

This recovered 967 PDFs with null ESN in the SOT, linking them to 611 distinct ESNs. These would otherwise be invisible to the retrieval pipeline.

---

## 3. Query Flow — Our Understanding

```
Input: equipment_serial_number + query text
  ↓
Step 1: Embed query (LiteLLM — azure-text-embedding-3-large-1)
  ↓
Step 2: HYBRID Vector Search (dense + BM25 keyword) filtered by generator_serial
  ↓
Step 3: Reranker (DatabricksReranker) — [see Gaps doc: reranking hurts R@1]
  ↓
Step 4: Chunk hydration — secondary Delta SQL lookup by chunk_id
  ↓
Step 5: 3-view metadata join (fsr_pdf_ref + fsr_scraped_file_mapping_ref + fsr_field_vision_psot)
  ↓
Output: Ranked chunks with full metadata (event type, outage details, report date, equipment info)
```

> Steps 4–5 are NOT built in the DS reference code. They are the responsibility of the service wrapper. The DS pipeline validates retrieval only (Steps 1–3).

---

## 4. Evaluation Results (GT Subset — 30 ESNs, 132 query pairs)

| Mode | Recall@1 | Recall@5 | Recall@20 |
|---|---|---|---|
| HYBRID retrieval | **0.432** | 0.667 | 0.841 |
| ANN retrieval | 0.379 | 0.614 | 0.795 |
| HYBRID + reranking | 0.303 | 0.667 | 0.841 |
| ANN + reranking | 0.235 | 0.614 | 0.795 |

**Key finding:** Reranking hurts R@1 by ~30% (0.432 → 0.303) and is neutral at R@5. The spec mandates unconditional reranking — this is an open decision (see Open Questions doc).

> **Caveat:** These results are from `fsr_pipeline_gt_direct` which uses consistent LiteLLM embeddings at both ingest and query time. The full-corpus `fsr_pipeline` has a confirmed embedding model mismatch (different vector spaces at ingest vs query) — its dense retrieval results would be worse.

---

## 5. Metadata Extraction Pipeline — Our Understanding

A separate 3-stage pipeline populates `fsr_scraped_file_mapping_ref`:

1. **Stage 1** — `pdfplumber` extracts key:value pairs from first page of each FSR PDF
2. **Stage 2** — LLM normalizes to a 15-field canonical schema (ESN, equipment IDs, event type, outage dates, project IDs). Controlled vocabulary for Event Type. Batches of 50.
3. **Stage 3** — PySpark enrichment via IBAT Equipment Master + Event Vision SOT to backfill missing fields

Output table exists in `main.gp_services_sdg_poc` (POC catalog). **Not yet promoted to production catalog or connected to retrieval pipeline.**

---

## 6. Access Status

| Resource | URL | Status |
|---|---|---|
| Databricks Dev workspace | TBD | Read + Write access confirmed |
| Databricks Prod workspace | TBD | TBD |
| LiteLLM gateway | `dev-gateway.apps.gevernova.net` | Confirmed |
| Production Unity Catalog tables | — | Do not exist yet |

---

## [PLACEHOLDER] — Areas to Validate

- [ ] Is our understanding of the processing flow correct?
- [ ] Is `fsr_scraped_file_mapping_ref` stable enough to wire up?
- [ ] Which pipeline variant (`fsr_pipeline` vs `fsr_pipeline_gt_direct`) is the production path?
- [ ] Are there other data sources or tables we are not aware of?
