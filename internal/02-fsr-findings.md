# 02 — FSR Chunking & Retrieval Findings

Source: DS team experimentation (4e). These are the validated results that inform the `query_fsr` implementation.

---

## What are FSRs?

**Field Service Reports (FSRs)** are PDF documents recording equipment service events — outage details, scope of work, findings, and actions taken per unit. Documents range from ~54 to 306+ pages. There are ~230 FSRs in the current corpus.

---

## Chunking

### Strategies Tested

| Strategy | Value | 54-page FSR | 306-page FSR |
|---|---|---|---|
| Page | 0 | 5 min | 10 min |
| Section | 1 | 35 min | 20 min |
| Sub-section L1 | 2 | 1 hr 20 min | 5 hrs |
| Sub-section L2 | 3 | 1 hr 45 min | 6 hrs 30 min |
| Paragraph | 4 | N/A | N/A |
| **Recursive** | custom | **10–20 sec** | **10–20 sec** |

> Note: The Foundation Service endpoint (`upload-file-metadata-extract`) defaults to LLM-based chunking (slow). Setting `textract_result=true` generates chunks in 2–3 min for 200–300 page docs. Recursive chunking runs locally and is fastest regardless.

### [DECIDED] Chunking Strategy: Recursive Hierarchical

**Why:** Preserves document hierarchy (section → subsection → sub-subsection), produces semantically meaningful chunks, and is dramatically faster than all Foundation Service strategies.

**Configuration (from `src/config.py`):**
```python
chunk_size     = 4000      # characters
chunk_overlap  = 200
max_chunk_tokens = 4000
max_chunk_chars  = 20000
max_depth        = 5
min_chunk_size   = 100
preserve_structure = True
separator_patterns = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n"]
```

**Stats across 230 FSRs at chunk_size=4000:**
- Mean chunks per FSR: 48.5
- Mean avg chunk size: 1,767 chars
- Median chunks: 22
- Max chunks: 1,114

**Chunk size trade-off:**
- `2000`: more chunks (mean 74), smaller (~1,150 chars avg)
- `4000`: balanced — fewer chunks, good readability [**recommended**]
- `6000–8000`: fewer chunks but large size may hurt retrieval precision

### Chunk Schema

Each chunk carries:
```
chunk_id          = {pdf_name}_{chunk_index}  (or {pdf_name}_{chunk_index}__{esn} for multi-ESN)
pdf_name          = source PDF GUID
page_number       = chunk start page (not ordinal)
generator_serial  = ESN extracted via LLM + regex (nullable; row duplicated per ESN for multi-ESN chunks)
report_date       = extracted during ingestion (nullable)
chunk_text        = text content (~4,000 tokens max)
embedding         = 3072-dim Azure OpenAI vector (stored at ingestion, NOT returned to callers)
created_at        = ingestion timestamp
uploaded_at       = upload timestamp
```

---

## Retrieval

### Strategies Benchmarked (16 variants)

Tested across custom (local BM25/FAISS/Hybrid) and Databricks built-in (ANN, HYBRID, Reranked), with and without criteria text appended to the query.

**Key results:**

| Strategy | Criteria? | Recall@1 | Recall@5 | Recall@10 | Recall@20 |
|---|---|---|---|---|---|
| DBR HYBRID | Y | **45.5** | **67.4** | **78.8** | 84.8 |
| DBR Reranked | Y | 19.7 | 56.1 | 73.5 | **86.4** |
| Custom Hybrid 70/30 | N | 25.8 | 62.9 | **81.8** | 87.9 |
| Custom Hybrid 70/30 | Y | 28.8 | 59.8 | 76.5 | **88.6** |
| DBR ANN | Y | 31.1 | 62.9 | 74.2 | 81.8 |
| BM25 | N | 19.7 | 44.7 | 62.9 | 70.5 |
| FAISS | N | 25.0 | 62.1 | 75.8 | 87.9 |

### [DECIDED] Production Retrieval: Databricks Native HYBRID + Criteria

**Why:** Strongest low-latency baseline using only Databricks-native components (no custom BM25/FAISS stack to maintain). Adding criteria text to the query improves low-k recall meaningfully.

**How HYBRID works in Databricks:**
- Dense leg: vector similarity against `query_vector` (Azure OpenAI embedding)
- Keyword leg: BM25-style matching against `chunk_text` using `query_text`
- Fusion: Reciprocal Rank Fusion (RRF), scores normalized 0–1

### [DECIDED] Reranking: Databricks Built-in Reranker

Use `DatabricksReranker` on `chunk_text` as a second pass after HYBRID retrieval. Worth applying when deeper recall (k=20) matters more than latency.

### Hit Evaluation Logic (from ground truth validation)
A chunk is a hit if either:
- **Page match**: PDF stem matches AND cited page falls within `[page_number, page_number + PAGE_WINDOW]`
- **Text match**: any GT snippet found in `chunk_text` (after NFKC normalization + alpha-only fallback)

---

## Key Implementation Learnings

1. **Minimal first-pass columns** — VS query returns only `chunk_id`, `pdf_name`, `page_number`, `chunk_text`, `generator_serial`. Metadata enrichment is a separate SQL pass.
2. **Filename normalization is required** — PDF names appear as `guid`, `guid.pdf`, and path-qualified variants. Normalize to stem before joining.
3. **`_psot` deduplication** — `(event_id, esn)` is not unique. Deduplicate by: Completed > Started > Not Started > Hold, then latest end/start date, then report name.
4. **`fsr_pdf_ref` selection** — prefer `(pdf_name, esn)` match over filename-only when multiple rows exist for same PDF.
5. **Multi-ESN chunks** — chunks mentioning multiple ESNs are duplicated (one row per ESN) at ingestion time so that `generator_serial` equality filter works for all tagged units.
6. **`embedding` column excluded from responses** — never return the embedding array to callers.
7. **Pre-flight check** — before evaluation/retrieval, validate that `generator_serial` is populated and GT ESNs are present in the index. Use `merge_ref_view_metadata()` to repair NULL `generator_serial` values.
