# FSR Retrieval Issues — Deep Dive & Proposed Resolutions

**Date:** 2026-06-26  
**Trigger:** Vince's concerns raised in June 23 Core Team meeting  
**Scope:** Top-K homogeneity, OCR garbage, corpus explosion, and what to do about each

---

## 1. The Four Problems Vince Identified

| # | Issue | Root Cause | Severity |
|---|-------|-----------|----------|
| 1 | **Top-K homogeneity** — all 10 chunks from one large FSR | No per-document diversity constraint in retrieval | CRITICAL |
| 2 | **Weird text / OCR garbage** | Scanned images produce char-by-char text after OCR | HIGH |
| 3 | **Corpus explosion** (8K → 50K+) | 25K new FSRs ingested without quality validation | HIGH |
| 4 | **Missing FSRs for some ESNs** | ESN tagging gaps + IBAT train expansion not live | MEDIUM |

---

## 2. Problem 1: Top-K Homogeneity

### What happens today

```
Query: "Was TIL 1945-R2 performed for ESN 290T434?"
Filter: esn = '290T434'
Top-K: 10

Result: 10 chunks, ALL from the same 440-page FSR
  chunk_1: page 12  (score 0.91) ← same PDF
  chunk_2: page 14  (score 0.90) ← same PDF
  chunk_3: page 15  (score 0.89) ← same PDF
  ...
  chunk_10: page 230 (score 0.82) ← same PDF

Other FSRs with relevant info: MISSED ENTIRELY
```

### Why it happens

- Large FSRs (300–500 pages) produce hundreds of chunks
- Many chunks in the same document are semantically similar (all discussing same outage)
- Vector similarity ranking doesn't consider document diversity
- No "max chunks per source document" constraint exists

### Proposed resolution: Per-Document Max + Round-Robin

**Strategy:** Retrieve top-K×3 candidates, then apply per-document cap before returning to LLM.

```python
def diversified_fsr_retrieval(esn: str, query: str, top_k: int = 10, max_per_doc: int = 3):
    """Retrieve top_k chunks with per-document diversity."""
    # Over-fetch to have enough diversity candidates
    raw_results = vector_search(esn=esn, query=query, k=top_k * 3)
    
    # Round-robin by document, capping per-doc contribution
    doc_counts = {}
    diversified = []
    for chunk in raw_results:
        doc_id = chunk["pdf_name"]  # or document_id stem
        doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
        if doc_counts[doc_id] <= max_per_doc:
            diversified.append(chunk)
        if len(diversified) >= top_k:
            break
    
    return diversified
```

**Parameters:**
- `max_per_doc = 3` — enough context from one FSR without dominating
- Over-fetch factor `3×` — ensures enough unique documents in the candidate pool
- Fallback: if only 1 FSR exists for this ESN, return all K from it (no artificial suppression)

**Impact estimate:** Based on Vince's testing, this alone would surface 3–5 additional FSRs per query that are currently invisible.

### Alternative: MMR (Maximal Marginal Relevance)

Databricks Vector Search supports MMR if configured. MMR penalizes chunks similar to already-selected ones:

```
score(chunk_i) = λ × similarity(query, chunk_i) - (1-λ) × max_similarity(chunk_i, selected_chunks)
```

With λ=0.7 (70% relevance, 30% diversity), this naturally pushes results across documents. However, MMR doesn't guarantee per-document caps — a very relevant single FSR could still dominate.

**Recommendation:** Per-document max is simpler, more predictable, and directly addresses the reported problem. Use MMR as an enhancement later if needed.

---

## 3. Problem 2: OCR Garbage / Weird Text Structures

### What it looks like

```
Chunk text from scanned table/image:
"R\nE\nP\nO\nR\nT\n \nD\nA\nT\nE\n:\n \n1\n2\n/\n1\n5\n/\n2\n0\n2\n4"

What it should be:
"REPORT DATE: 12/15/2024"
```

Also: signature blocks, page footers, logos as text, equipment lists rendered as single-char columns.

### Why it happens

- PDF extraction (OCR) on scanned documents produces character-per-line for tables/images
- Chunker doesn't detect garbage — any text gets chunked and embedded
- No quality gate between extraction and embedding
- With 50K FSRs, even 5% OCR issues = 2,500 documents with degraded chunks

### Proposed resolution: Multi-layer quality filtering

**Layer 1: Chunk-level quality score (at ingestion time)**

```python
def chunk_quality_score(text: str) -> float:
    """Score 0-1 for chunk text quality. Low = likely garbage."""
    if len(text) < 20:
        return 0.1  # Too short to be useful
    
    # Character-per-line pattern detection
    lines = text.split('\n')
    single_char_lines = sum(1 for l in lines if len(l.strip()) <= 2)
    if single_char_lines / max(len(lines), 1) > 0.5:
        return 0.2  # Majority single-char lines = OCR garbage
    
    # Word density (meaningful text has 3+ char words)
    words = text.split()
    meaningful_words = [w for w in words if len(w) >= 3]
    word_density = len(meaningful_words) / max(len(words), 1)
    
    # Repetition detection (template boilerplate)
    unique_words = len(set(w.lower() for w in meaningful_words))
    diversity = unique_words / max(len(meaningful_words), 1)
    
    return min(1.0, word_density * 0.6 + diversity * 0.4)
```

**Layer 2: Filter at retrieval time**

```python
# Add quality filter to vector search results
results = [r for r in raw_results if r.get("quality_score", 1.0) > 0.3]
```

**Layer 3: Vince's full-text fallback**

For FSRs where chunk quality is consistently low (mean quality_score < 0.4), bypass chunked retrieval entirely and feed the full document text (or structured summary) to the LLM.

```python
def get_fsr_evidence(esn: str, query: str):
    chunks = diversified_fsr_retrieval(esn, query)
    
    # Check if retrieved chunks are mostly garbage
    avg_quality = mean(c.get("quality_score", 1.0) for c in chunks)
    if avg_quality < 0.4:
        # Fall back to full-text or structured summary
        return get_fsr_full_text_summary(esn, chunks[0]["pdf_name"])
    
    return chunks
```

**Immediate action (no re-ingestion needed):**
- Add quality scoring as a metadata column via batch UPDATE on the 50K rows
- Filter low-quality chunks at retrieval time
- Long-term: re-chunk OCR-heavy PDFs with better extraction (e.g., marker-based layout parser)

---

## 4. Problem 3: Corpus Explosion (8K → 50K+ without validation)

### The timeline

```
Before June 8:  ~8K FSRs in production (well-tested, manually validated)
June 8:         25K+ new FSRs dumped into landing zone
June 12-24:     P1 fire drill to ingest them all
June 24:        48,701 PDFs in metadata table
                = 6× corpus growth with ZERO quality validation
```

### What's unknown about the new 40K

| Question | Answer |
|----------|--------|
| How many have OCR issues? | Unknown |
| How many are multi-language? | Unknown |
| How many have correct ESN tagging? | Unknown |
| How many are duplicates (same content, different filenames)? | Unknown |
| What's the average chunk quality? | Unknown |

### Proposed resolution: Stratified quality audit

**Phase 1: Statistical sampling (this week)**

Sample 200 FSRs stratified across:
- Source: ecrt_reports vs fieldvision (100 each)
- Size: small (<50 pages), medium (50–200), large (200+)
- Age: pre-2020 vs 2020-2024 vs 2024+
- Equipment type: GT vs Generator vs ST

For each sampled FSR, check:
- [ ] Chunk text readability (quality_score > 0.5)
- [ ] ESN in top-level column matches ESN in chunk content
- [ ] Metadata fields populated (event_type, outage_type, dates)
- [ ] Embedding produces meaningful similarity (not clustering with garbage)

**Phase 2: Automated quality pipeline (next week)**

```python
def fsr_quality_report(sample_size=200):
    """Run quality checks on stratified sample of FSR corpus."""
    sample = stratified_sample(
        table="biz_metadata_field_service_report",
        strata=["source_folder", "page_count_bucket", "report_year"],
        n=sample_size
    )
    
    results = []
    for doc in sample:
        chunks = get_chunks_for_document(doc["document_id"])
        results.append({
            "document_id": doc["document_id"],
            "chunk_count": len(chunks),
            "avg_quality_score": mean(chunk_quality_score(c["chunk_text"]) for c in chunks),
            "esn_grounding_pct": pct_chunks_mentioning_esn(chunks, doc["esn"]),
            "metadata_completeness": count_non_null_fields(doc) / total_fields,
            "language": detect_language(chunks[0]["chunk_text"]) if chunks else "unknown",
        })
    
    return pd.DataFrame(results)
```

**Phase 3: Remediation based on findings**

| Finding | Action |
|---------|--------|
| OCR garbage (quality < 0.3) | Mark chunks as `excluded`; attempt re-extraction with better parser |
| Wrong ESN (grounding < 5%) | Remove false-presence rows; apply IBAT expansion at query time instead |
| Missing metadata | Batch LLM metadata extraction (event_type, outage_type) |
| Duplicate PDFs | Dedup by content hash; keep most recent version |

---

## 5. Problem 4: Missing FSRs for Some ESNs

### Root causes (from IBAT investigation)

| Cause | Scale | Fix |
|-------|-------|-----|
| **Generator work filed under GT ESN** | ~95% of generator FSR evidence is under GT tag | IBAT train expansion at query time |
| **ST ESNs not tagged** | ST ESNs on CC trains get 0 chunks | Expand tagging to include ST tier |
| **Recent FSRs not yet ingested** | Continuous ingestion needed | Airflow job `PW_SDG_FSR_Ingestion` (now running) |

### IBAT train expansion

```python
def expanded_fsr_query(esn: str, query: str, top_k: int = 10):
    """Query FSR with IBAT train expansion for better recall."""
    # Get all ESNs on the same train
    train_esns = ibat_get_train_siblings(esn)  # Returns [esn, sibling1, sibling2, ...]
    
    # Query across all train ESNs
    all_chunks = []
    for train_esn in train_esns:
        chunks = vector_search(esn=train_esn, query=query, k=top_k)
        all_chunks.extend(chunks)
    
    # Deduplicate (same chunk may appear under multiple ESN tags)
    unique_chunks = deduplicate_by_chunk_id(all_chunks)
    
    # Re-rank by relevance and apply per-doc diversity
    return diversified_rerank(unique_chunks, query, top_k=top_k, max_per_doc=3)
```

**Measured impact (May 26 investigation):**
- 500 GT ESNs with Generator siblings sampled
- Average narrow lookup: 0.0 FSRs for Generator ESN
- Average expanded lookup: 1.09 FSRs recovered
- 84 of 500 (17%) zero-result ESNs rescued
- 544 extra FSRs surfaced total

**Deploy complexity:** Low — SQL join to `eu_ibat` at query time; no re-ingestion required.

---

## 6. Two/Three-Way Check Mechanism (Vince's ask)

Vince asked for a mechanism to "ensure no FSRs are missed going forward."

### Proposed: Three-way completeness check

```
Check 1: SOURCE → METADATA (ingestion completeness)
  Count files in landing zone  vs  Count rows in biz_metadata
  Gap = files not yet processed

Check 2: METADATA → CHUNKS (chunking completeness)  
  Count biz_metadata rows with chunk_status='completed'  vs  actual chunk rows
  Gap = metadata exists but chunking failed/pending

Check 3: CHUNKS → RETRIEVAL (search coverage)
  For a sample of ESNs, compare:
    - FSRs known to exist (from biz_metadata WHERE esn=X)
    - FSRs actually returned by vector search for that ESN
  Gap = chunks exist but aren't being retrieved (embedding quality, filter mismatch)
```

### Implementation as a monitoring dashboard

```sql
-- Check 1: Ingestion completeness
SELECT 
  source_folder,
  COUNT(DISTINCT volume_path) as files_in_volume,
  COUNT(DISTINCT CASE WHEN metadata_status = 'completed' THEN volume_path END) as metadata_done,
  COUNT(DISTINCT volume_path) - COUNT(DISTINCT CASE WHEN metadata_status = 'completed' THEN volume_path END) as gap
FROM biz_metadata_field_service_report
GROUP BY source_folder;

-- Check 2: Chunking completeness
SELECT 
  m.chunk_status,
  COUNT(DISTINCT m.document_id) as metadata_docs,
  COUNT(DISTINCT v.document_id) as chunked_docs,
  COUNT(DISTINCT m.document_id) - COUNT(DISTINCT v.document_id) as gap
FROM biz_metadata_field_service_report m
LEFT JOIN vec_field_service_report v ON m.document_id = v.document_id
GROUP BY m.chunk_status;

-- Check 3: Retrieval spot-check (run for sample ESNs)
-- Compare biz_metadata ESN count vs vector_search result count
```

**Run frequency:** Daily (automated via Airflow alongside ingestion job).  
**Alert threshold:** If Check 1 gap > 100, or Check 2 gap > 50, or Check 3 gap > 20% → alert.

---

## 7. Summary: Resolution Roadmap

### Immediate

| # | Resolution | Problem addressed | Effort | Impact |
|---|-----------|-------------------|--------|--------|
| 1 | **Per-document max (max_per_doc=3)** in retrieval | Top-K homogeneity |  | HIGH — surfaces 3–5 additional FSRs per query |
| 2 | **IBAT train expansion** at query time | Missing FSRs for generators |  | MEDIUM — 17% recall rescue |
| 3 | **Three-way completeness check** SQL queries | Missing FSR detection |  | LOW (monitoring, not fixing) |

### Short-term

| # | Resolution | Problem addressed | Effort | Impact |
|---|-----------|-------------------|--------|--------|
| 4 | **Chunk quality scoring** (batch UPDATE) | OCR garbage in results |  | HIGH — filter garbage at retrieval |
| 5 | **Stratified quality audit** (200 FSR sample) | Unknown corpus quality |  | HIGH — data-driven remediation plan |
| 6 | **Full-text fallback** for low-quality FSRs | OCR-heavy docs unusable |  | MEDIUM — alternative path when chunks fail |

### Medium-term

| # | Resolution | Problem addressed | Effort | Impact |
|---|-----------|-------------------|--------|--------|
| 7 | **esn_list migration** | Multi-ESN 10× duplication |  | HIGH — eliminates false-presence chunks |
| 8 | **Re-extraction** of OCR-heavy PDFs with better parser | Source quality |  | HIGH — fixes root cause |
| 9 | **Automated quality monitoring** on new ingestions | Prevent future quality regression |  | MEDIUM — continuous confidence |

---

## 8. Key Insight for Architecture

The fundamental issue isn't just "top-K is wrong" — it's that the retrieval layer has **no concept of information diversity**. All four problems stem from the same root:

> **The system optimizes purely for similarity, not for coverage.**

A CPM reviewing an outage scope needs evidence from **multiple FSRs** (prior outages, different components, different time periods). Getting 10 highly-similar chunks from one document is like reading the same paragraph 10 times — it doesn't build a complete picture.

The fix isn't just changing a number. It's adding a **coverage objective** to retrieval:
- Cover multiple time periods (recent + historical)
- Cover multiple document sources (different FSRs = different outages)
- Cover the specific ESN's work (not its IBAT siblings' boilerplate)
- Exclude noise (OCR garbage, template repetition, signature blocks)

This is what Vince means by "2000% improvement potential" — the data is there, it's just not being surfaced correctly.
