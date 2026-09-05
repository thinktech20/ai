# FSR Chunking Strategy — Production vs. DS Team Prescription

Compares the chunking implementation in `pw_sdg_ai_ser_repo` (Process 2 / Gold) against the DS team's prescribed "V3 hierarchical recursive" strategy.

Sources:
- Production: [pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py), [pw_sdg_ai_ser_repo/common/fsr_config.py](../../../pw_sdg_ai_ser_repo/common/fsr_config.py)
- DS docs: `reference/ds-team/DS-experimentations/4e-fsr-chunking-retrieval-reranking-experimentation.pdf`, `reference/ds-team/DS-experimentations/4e-fsr-chunking-retrieval-reranking/fsr-retrieval-e2e-pipeline-local.pdf`, `.../semantic-chunking-strategy-experimentation.pdf`, `.../section-based-chunking-analysis.pdf`

---

## 1. What's in production today

Process 2 (Gold) reads docs with `metadata_status=completed`, extracts text per page with PyMuPDF, concatenates pages into a single string, then runs LangChain's `RecursiveCharacterTextSplitter`.

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNKING_CONFIG.chunk_size,        # 4000 chars
    chunk_overlap=CHUNKING_CONFIG.chunk_overlap,  # 200 chars
    separators=["\n\n", "\n", ". ", " ", ""],
    length_function=len,
)
```

Per-chunk metadata captured: `chunk_index`, `chunk_text`, `page_number` (first overlapping page only). Other metadata fields on the chunk row are copied from the metadata registry (ESN, equipment, dates, etc.).

`CHUNKING_CONFIG` (`common/fsr_config.py`):

| Param | Value |
|---|---|
| `chunk_size` | 4000 |
| `chunk_overlap` | 200 |
| `min_chunk_size` | 100 |
| `max_chunk_chars` | 20000 |
| `max_chunk_tokens` | 4000 |
| `max_depth` | 5 |
| `separator_patterns` | `["\n## ", "\n### ", "\n#### ", "\n\n", "\n"]` (defined but **not used** by the splitter) |

> Only `chunk_size` and `chunk_overlap` from the config are actually consumed. The hard-coded separators in the splitter call differ from `separator_patterns`.

---

## 2. DS team's prescribed strategy ("V3 hierarchical recursive")

From `4e-fsr-chunking-retrieval-reranking-experimentation.pdf`, the DS function `hierarchical_recursive_chunking(pdf_path, chunk_size, chunk_overlap)`:

1. Extracts text page by page.
2. **Splits hierarchically by regex patterns for section, subsection, sub-subsection.**
3. Applies `RecursiveCharacterTextSplitter` to body text.
4. **Merges small consecutive chunks up to `chunk_size`.**
5. Recomputes `chunk_index` and `chunk_count` per group.
6. **Adds metadata including section titles, indices, page_number, and grouping level.**

DS `ChunkingConfig` (quoted in `fsr-retrieval-e2e-pipeline-local.pdf`):

```
chunk_size = 4000
chunk_overlap = 200
max_chunk_tokens = 4000
max_chunk_chars = 20000
max_depth = 5
min_chunk_size = 100
preserve_structure = True
separator_patterns = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n"]
```

Implementation lives in `src/recursive_chunking_v3.py` of the DS POC. Per-chunk metadata in their output:

```json
{
  "schema_version": 1,
  "chunk_index": 0,
  "chunk_count": 42,
  "chunk_size": 4000,
  "start_page": 5,
  "end_page": 7,
  "section_1": "Background",
  "section_2": "Inspection Findings",
  "section_3": null,
  "section_4": null,
  "section_5": null,
  "chunk_esns": ["297837"],
  "esn_labels": ["297837"]
}
```

Multi-ESN chunks are duplicated — one Delta row per (chunk, ESN), with `chunk_id = {pdf_name}_{chunk_index}__{esn}`.

---

## 3. Side-by-side

| Aspect | DS prescription | Production today |
|---|---|---|
| Splitter | `RecursiveCharacterTextSplitter` | ✅ Same |
| `chunk_size` / `chunk_overlap` | 4000 / 200 | ✅ Same |
| Separators (in actual splitter call) | `["\n\n", "\n", ". ", " ", ""]` — same as prod (markdown patterns in DS `config.py` are unused dead code) | ✅ Same |
| Text source | PyMuPDF page-by-page | ✅ PyMuPDF (`fitz`) |
| **TOC detection / front-matter skip** | Yes | ❌ Not implemented |
| **Boilerplate filtering** (positional headers/footers, lines repeated on ≥20% of pages) | Yes | ❌ Not implemented |
| **Header classification** (TOC match + font-size + bold) | Two-pass | ❌ Not implemented |
| **Hierarchical section split** before recursive split | Yes (regex section / subsection / sub-subsection) | ❌ Whole document concatenated, then split flat |
| **Small-chunk merging** up to `chunk_size` | Described in early experimentation PDF; **NOT present** in production `recursive_chunking_v3.py` (only filters chunks < 20 chars) | ❌ No merge step (matches DS v3) |
| Section path on chunk (`section_1` … `section_5`) | Yes (up to 5 levels) | ❌ Not captured |
| Page tracking | `start_page` + `end_page` | ⚠️ Single `page_number` (first overlapping page) |
| `chunk_id` scheme | `{pdf_name}_{chunk_index}` or `{pdf_name}_{chunk_index}__{esn}` | document_id-based, no ESN suffix |
| Multi-ESN row duplication | Yes (count ≥ 5 AND ≥ 10% of mentions) | ❌ Not done at chunk time |
| Document-level ESN extraction (single LLM call per doc, start/middle/end windows) | Yes (`esn_identifier.py`) | ❌ Page-1 regex + LLM normalization + IBAT join only (in P1) |
| `metadata` JSON blob (`schema_version`, `chunk_count`, `start_page`, `end_page`, `section_1..5`, `chunk_esns`, `esn_labels`) | Yes | ❌ Most fields absent — flatter chunk row copied from registry |

---

## 4. DS alternatives that were tested and rejected

From the DS experimentation docs:

| Strategy | 54-page FSR | 306-page FSR | Outcome |
|---|---|---|---|
| Page (Foundation Service) | 5 min | 10 min | Fast but no semantic grouping |
| Section | 35 min | 20 min | Too slow |
| Sub-section L1 | 1 hr 20 min | 5 hr | Too slow |
| Sub-section L2 | 1 hr 45 min | 6 hr 30 min | Too slow |
| Section-based (non-recursive) | — | — | Avg 25.3 chunks/report but huge variance: median 552 chars, max **218,141** chars. Rejected — embedding model can't handle outliers. |
| Semantic chunking (LangChain `SemanticChunker`, MiniLM-L6-v2, percentile 95) | — | — | Better topic alignment but "significantly more compute-intensive… not thread-safe… justified only if retrieval accuracy materially improves." Not adopted. |
| **Recursive (V3 hierarchical)** | **10–20 sec** | **10–20 sec** | **Chosen** |

DS recursive chunking stats across 230 FSRs at `chunk_size=4000`: mean 48.5 chunks/report, mean avg chunk size 1,767 chars, median 22 chunks, max 1,114 chunks.

---

## 5. Bottom line

Production matches the DS strategy on the **headline parameters** (4000/200, recursive splitter, PyMuPDF) but only implements step 5 of the DS 6-step pipeline. Missing pieces:

1. **TOC detection** + skip front-matter pages.
2. **Boilerplate filtering** (positional headers/footers in outer 10% / 10% page-height zones; lines repeating on ≥20% of pages).
3. **Header classification** (two-pass: TOC match + numbering depth → font-size + bold fallback) producing a section tree up to 5 levels.
4. **Per-section recursive split** (group body text by section path, then `RecursiveCharacterTextSplitter` *per section*, so chunks don't cross section boundaries).
5. **Section metadata** (`section_1..section_5`) and **page range** (`start_page` / `end_page`) on each chunk.
6. **Front Matter** and **Table of Contents** injected as their own sections so cover-page info isn't lost.
7. **Document-level ESN extraction** and **multi-ESN row duplication** at chunk time. *(deferred — see §6/§7)*

Note: separators (`["\n\n","\n",". "," ",""]`) and small-chunk merging are **not** real gaps — DS production code matches what we have today.

Retrieval impact: section path and page ranges are inputs the DS retrieval/reranking design relies on (citations, criteria filtering, page-window hit logic). Without them, vector + BM25 search still works on `chunk_text`, but section-aware reranking and page-range citations don't. Multi-ESN: a chunk shared by two ESNs is currently retrievable only under the single ESN tagged on the metadata row.

---

## 6. Multi-ESN: 1-PDF-to-1-ESN simplification (current vs. DS)

### What changed from DS to current code

DS approach allowed **1 PDF → many ESNs**:

- One LLM call per document scanned start/middle/end windows of full PDF text and returned `{ESN: count}`.
- Any ESN with **count ≥ 5 AND ≥ 10% of all ESN mentions** qualified — a document could have multiple qualifying ESNs.
- At chunk write time, **rows were duplicated**: one Delta row per `(chunk, ESN)`, with `chunk_id = {pdf_name}_{chunk_index}__{esn}`.
- Metadata blob carried `chunk_esns` and `esn_labels` arrays.

Current pipeline collapses this to **1 PDF → 1 ESN**:

- Both metadata and chunk tables have a single scalar `esn STRING` column ([common/fsr_config.py#L318-L319, L358](../../../pw_sdg_ai_ser_repo/common/fsr_config.py#L318-L358)).
- ESN resolution in P1 ([nb_sdg_fsr_metadata.py#L657-L684](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L657-L684)): LLM normalizes **page-1 text only** → regex on page-1 text → IBAT join. First non-empty wins.
- Each chunk row simply copies `meta.esn` — one row per chunk.

Notable: the LLM prompt in P1 ([nb_sdg_fsr_metadata.py#L360](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py#L360)) still instructs the model to split multi-ESN records into separate rows, but the downstream code keeps only the first row per `document_id` and then `dropDuplicates(["document_id"])`. The multi-ESN intent is silently flattened.

### Practical impact

- A 2-ESN PDF is retrievable only under the one ESN that won the precedence tie.
- A query filtered on the secondary ESN won't surface its chunks.
- Schema is simpler: `document_id` is PK, MERGE is straightforward, VS filter is `esn = 'X'`.

---

## 7. Recommendation

**Short answer: restore multi-ESN support, but only if measurement shows multi-ESN FSRs are a meaningful share of the corpus. Otherwise leave it.**

### Step 1 — Quantify the problem first (no code change)

Before changing anything, measure. One-off notebook:

1. Sample ~50 PDFs (or all 230) and run the DS-style **document-level ESN scan** (one LLM call per doc with start/middle/end windows, the `count ≥ 5 AND ≥ 10%` filter).
2. Compare the resulting ESN set per `document_id` against the single `esn` currently in `fsr_metadata`.
3. Report: `% docs with >1 qualifying ESN`, and for those, `% where current esn != primary ESN by mention count`.

Decision rule:

- **<5% multi-ESN** → don't change. Document the limitation.
- **10–30%+ multi-ESN** → do Step 2.

### Step 2 — Minimal fix (if data justifies it)

Don't reintroduce the full DS row-duplication scheme. Use an **array column + `array_contains` filter**:

P1 changes ([nb_sdg_fsr_metadata.py](../../../pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py)):

- Add a full-document ESN scan (start/middle/end windows, single LLM call per doc) — or at minimum, regex-scan the full extracted text for ESN/SY patterns and count occurrences.
- Apply the `count ≥ 5, fraction ≥ 10%` rule.
- Keep `esn` (scalar, primary) for backward compat + display.
- Add `esn_all ARRAY<STRING>` for the full qualified set.
- Stop dropping rows in the LLM normalization step; aggregate split rows into `esn_all` instead.

P2 / chunk table changes ([nb_sdg_fsr_chunks.py](../../../pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py)):

- Add `esn_all ARRAY<STRING>` to the chunk table.
- One row per chunk still — no duplication.
- Vector Search filter becomes `array_contains(esn_all, 'X')` instead of `esn = 'X'`.

Why array over row duplication:

- Half the storage, half the index size.
- No `__esn` suffix in `chunk_id` to maintain.
- DBR Vector Search supports `array_contains` filters.
- DS chose row duplication because their VS schema didn't have arrays at the time — that constraint may not apply now.

### Step 3 — Things NOT to do

- Don't add per-chunk ESN tagging (DS proposed but didn't really use it — `esn_labels` is document-level in their final design too).
- Don't reintroduce the `__esn` chunk_id suffix.
- Don't block on this if Step 1 measurement says the corpus is mostly single-ESN.

### Priority ranking across all chunking gaps

The chunking gaps in §5 are independent of multi-ESN and have **bigger retrieval impact** than multi-ESN for single-unit reports. Suggested order of work:

1. **`start_page` + `end_page` on chunks** — cheap, ~30 min change, fixes citation accuracy.
2. **Section metadata + markdown-aware separators** — medium effort, improves reranker quality.
3. **Multi-ESN handling** — only if Step 1 measurement says it's a real problem.
