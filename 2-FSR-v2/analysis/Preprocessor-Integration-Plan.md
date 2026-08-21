# Preprocessor Integration Plan

**Status:** Ready for implementation post-POC validation (end of week July 18)  
**Scope:** Two jobs + accuracy measurement strategy  
**Timeline:** 3 weeks (integration + backfill + validation)

---

## Job A: Enhanced Pipeline for New Documents

### What Changes
Integrate preprocessor into existing P1/P2 ingestion workflow **as an optional pre-chunking step**.

### Pipeline Flow

```
P1: Metadata Extraction (existing)
  1. Extract PDF text + page_offsets
  ↓
NEW: Preprocessor Step (runs for all FSRs)
  • Input: ctx.full_text, ctx.pages, ctx.page_offsets, ctx.fields (schema)
  • Detect inactive ESNs ("not applicable / no work performed") → exclude from all chunks
  • Detect section boundaries via regex: HEADER pattern + SECTION_HDR numbered TOC headers
  • Fallback (no clear GT/Gen split): per-page form numbers + GE_SIGNATURES keyword scan
  • Output (three parts):
      metadata  → doc-level fields: gt_esn, gen_esn, primary_esn, primary_equip_type,
                  primary_technology_code, inactive_esns, outage_start_date,
                  outage_end_date, report_issued_date
      hints     → text string injected into the LLM extraction prompt for anything
                  the preprocessor couldn't determine (event_type, missed dates)
      regions   → [{"start": <char_offset>, "end": <char_offset>, "metadata": {...}}]
                  per-section char-offset boundaries; each chunk inherits the region
                  it falls in
  • Runtime: ~< 1 sec per document
  ↓
P1 (continued): LLM Metadata Extraction (guided)
  • LLM extraction prompt includes the preprocessor hints
  • Merge priority (region tag wins, LLM fills gaps):
      1. region metadata  (most specific — per-section override)
      2. preprocessor doc-level metadata
      3. AI/LLM extraction value
      4. upload/ingestion tags
  • Store merged metadata row
  ↓
P2: Chunking (Enhanced)
  • For each chunk: find which region its char offset falls in
  • Assign chunk.primary_equip_type from that region's metadata
  • Inactive ESNs excluded — no chunks emitted for inactive equipment
  • Continue: embed → store
```

### Implementation Details

**Where to hook in:**
- P1 (`pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py`):
  - Call `preprocess(ctx)` early — before the LLM extraction call
  - Pass `result['hints']` into the LLM extraction prompt
  - Apply `result['metadata']` as the base doc-level values (before LLM merge)
  - Store `result['regions']` as JSON blob in metadata table (new column)
- P2 (`pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`):
  - Read `regions` JSON from metadata
  - For each chunk: match chunk char offset to a region (`chunk_start >= region.start and chunk_start < region.end`)
  - Assign `chunk.primary_equip_type` from matched region (4-level fallback if no match)
  - Skip emitting chunks whose `primary_esn` is in `inactive_esns`

**Conditional:** Preprocessor runs for all FSRs (single and multi-ESN). The region output may be empty for clean single-equipment docs, in which case the doc-level metadata still applies.

**Schema additions:**
- Metadata table: `preprocessor_regions` (JSON, nullable)
  ```json
  [
    {"start": 0,     "end": 84320,  "metadata": {"primary_esn": "298250",  "primary_equip_type": "Gas Turbine"}},
    {"start": 84320, "end": 198440, "metadata": {"primary_esn": "338X447", "primary_equip_type": "Generator"}}
  ]
  ```
- Metadata table: `inactive_esns` (string/array, nullable) — ESNs with no work performed
- Optional audit column: `preprocessor_version`

**Fallback (4-level merge):** If preprocessor produces no region for a chunk, fall through: preprocessor doc value → LLM value → upload tag.

---

## Job B: Backfill Existing Multi-Equipment FSRs

### What It Does
One-time batch job to correct mislabeled chunks in ~458 existing multi-equipment FSRs.

### Execution Flow

```python
# Pseudocode for backfill job

def backfill_fsr_chunk_labels():
    """
    For each multi-ESN FSR in production:
      1. Extract PDF from storage
      2. Run preprocessor → get regions
      3. Generate UPDATE statements for chunk table
      4. Execute updates (one doc at a time for safety)
      5. Log before/after statistics
    """
    
    multi_esn_fsrs = query_metadata("WHERE len(all_esns) >= 2")
    
    audit_log = []
    
    for doc_id, metadata in multi_esn_fsrs:
        try:
            pdf_bytes = fetch_pdf(doc_id)
            pdf_text, page_offsets = extract_text_with_offsets(pdf_bytes)
            
            # Run preprocessor
            result = preprocess(ctx={
                'full_text': pdf_text,
                'pages': pages,
                'page_offsets': page_offsets,
                'fields': metadata_schema,
            })
            
            regions   = result['regions']    # [{start: char_offset, end: char_offset, metadata: {...}}]
            doc_meta  = result['metadata']    # doc-level: gt_esn, gen_esn, inactive_esns, dates, ...
            inactive  = set((doc_meta.get('inactive_esns') or '').split(','))
            
            # Translate char offsets → page ranges using page_offsets
            # page_offsets = [{page, start, end}] from pdfplumber extraction
            def char_to_page(char_offset, page_offsets):
                for po in page_offsets:
                    if po['start'] <= char_offset < po['end']:
                        return po['page']
                return None
            
            region_page_ranges = []
            for region in regions:
                start_page = char_to_page(region['start'], page_offsets)
                end_page   = char_to_page(region['end'] - 1, page_offsets)
                equip_type = region['metadata'].get('primary_equip_type')
                esn        = region['metadata'].get('primary_esn')
                if start_page and end_page and equip_type and esn not in inactive:
                    region_page_ranges.append({
                        'start_page': start_page,
                        'end_page':   end_page,
                        'primary_equip_type': equip_type,
                        'primary_esn': esn,
                    })
            
            # Generate UPDATEs using page ranges (chunk table stores page numbers)
            for region in region_page_ranges:
                sql = f"""
                    UPDATE chunk_table
                    SET primary_equip_type = '{region['primary_equip_type']}'
                    WHERE doc_id = '{doc_id}'
                      AND start_page >= {region['start_page']}
                      AND end_page   <= {region['end_page']}
                """
                
                # Count before
                count_before = execute(f"SELECT COUNT(*) FROM chunk_table WHERE doc_id='{doc_id}'")
                
                # Execute update
                rows_affected = execute(sql)
                
                # Count after
                count_after = execute(f"SELECT COUNT(*) FROM chunk_table WHERE doc_id='{doc_id}'")
                
                # Log
                audit_log.append({
                    'doc_id': doc_id,
                    'region': region,
                    'rows_affected': rows_affected,
                    'status': 'success'
                })
        
        except Exception as e:
            audit_log.append({
                'doc_id': doc_id,
                'error': str(e),
                'status': 'failed'
            })
    
    # Write audit log to S3 / Delta
    write_audit_log(audit_log)
    return audit_log
```

### Implementation

**Location:** `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_backfill_chunks.py` (new notebook)

**Triggers:**
- Manual: `python nb_sdg_fsr_backfill_chunks.py --mode=dry-run` (initial validation)
- Manual: `python nb_sdg_fsr_backfill_chunks.py --mode=execute` (production)
- Or: Scheduled once after POC sign-off

**Safety mechanisms:**
- Dry-run mode: No writes, just reports what *would* change
- Transaction isolation: One doc at a time (if one fails, others continue)
- Audit log: Every change logged with before/after counts
- Rollback capability: Audit log enables reverting via script if needed

**Output:**
- Audit log saved to: `s3://fsr-prod/backfill-audit/backfill-{timestamp}.json`
- Summary stats: docs processed, chunks updated, errors, success rate

---

## Accuracy Measurement

### Strategy: Two-Scorer Approach (from Vince's POC)

**Scorer 1: Page-Range Scorer** (primary)
- Ground truth: curated page ranges per document (e.g., "pages 1-160 = Gas Turbine, 161-300 = Generator")
- Method: For each chunk, check if its page falls in the correct range
- Coverage: ~98% of chunks (page metadata always available)
- Metric: `accuracy = correct_chunks / total_chunks`

**Scorer 2: Content-Density Scorer** (secondary)
- Ground truth: keyword density heuristic (GT-specific keywords vs Gen-specific keywords)
- Method: Scan chunk for equipment-specific signals (compressor/combustion vs stator/rotor)
- Coverage: ~15% of chunks (only larger chunks have enough content)
- Metric: Cross-validates against page-range scorer; flags disagreements

### Measurement Workflow

#### Pre-Backfill Baseline (Week 1)
```
1. Select 7 test FSRs (Vince's existing test set)
2. Run Scorer 1 + Scorer 2 on current chunks
3. Record baseline accuracy:
   - Iter 1: 82.6% (before any fix)
   - Iter 2: 86.7% (Fix 1 applied)
   - Current (production): likely 82.6% unless Fix 1 already deployed
```

#### Post-Backfill Validation (Week 3, before rollout)

**Dry-run phase:**
```python
def validate_backfill():
    # 1. Run backfill in dry-run mode on 10 test FSRs
    audit_log = backfill_fsr_chunk_labels(mode='dry-run', sample_size=10)
    
    # 2. For each test FSR, show before/after label distribution
    for doc_id in test_fsrs:
        before = query("SELECT primary_equip_type, COUNT(*) FROM chunks WHERE doc_id=? GROUP BY primary_equip_type")
        after = simulate_update(audit_log, doc_id)
        print(f"{doc_id}: before {before}, after {after}")
    
    # 3. Run retrieval tests with updated chunks
    test_queries = [
        ('338X447', 'Generator ESN'),  # Should now find Gen chunks
        ('298250', 'GT ESN'),          # Should still find GT chunks
    ]
    
    for esn, expected_type in test_queries:
        results = retriever.search(esn, top_k=10)
        labels = [chunk.primary_equip_type for chunk in results]
        purity = labels.count(expected_type) / len(labels)
        print(f"{esn}: {purity:.0%} labeled {expected_type}")
```

**Accuracy measurement:**
```
For each of 7 test FSRs:
  1. Run preprocessor → get regions
  2. Simulate UPDATE
  3. Run Scorer 1 on simulated chunks
  4. Expected result: ~90-93% accuracy (from Vince's Iter 2/3)
  5. If ≥90%: proceed to full backfill
  If <90%: investigate, iterate on preprocessor
```

#### Full Rollout Phase (Week 3, after validation)

**Execute backfill on all 458 FSRs:**
```
1. Run backfill_fsr_chunk_labels(mode='execute') on full corpus
2. Monitor:
   - Success rate (% of docs processed without error)
   - Label distribution shift (% chunks flipped from GT to Gen, vice versa)
   - Audit log completeness
3. Post-execution checks:
   - Run random sample of retrieval tests (100 ESN queries)
   - Measure zero-result rate before/after
   - Expected: 17% zero-result queries → <5%
4. Run Scorer 1 on sample (1000 random chunks from updated docs)
   - Expected accuracy: ≥90%
```

**Post-production monitoring (Week 4+):**
```
- Daily: Monitor "zero-result ESN queries" rate (should drop from 17% to <5%)
- Daily: Monitor risk evaluation recommendations (should see fewer equipment-confusion errors)
- Weekly: Spot-check 10 random FSRs via Scorer 1 (ensure no drift)
- Monthly: Curate new evaluation set for ongoing regression testing
```

---

## Measurement Metrics & Targets

| Metric | Baseline | Target | Method |
|---|---|---|---|
| Equipment label accuracy | 82.6% | ≥90% | Page-range scorer on test set |
| Zero-result ESN queries | ~17% | <5% | Query log analysis |
| Single-equipment FSR regressions | 0% | 0% (no change) | Scorer 1 on clean docs |
| Backfill success rate | N/A | ≥99% | Audit log count_success / count_total |
| Retrieval latency impact | baseline | <5% increase | Query response times pre/post |

---

## Timeline

| Week | Milestone | Owner | Status |
|---|---|---|---|
| Week 1 (Jul 18) | Validate Fix 2 + Fix 3 in POC | Vince | ◻ In progress |
| Week 1 (Jul 18) | Finalize preprocessor logic | Vince | ◻ |
| Week 2 (Jul 25) | Integrate Job A into P1 workflow | Data eng + Vince | ◻ Blocked on Fix validation |
| Week 2 (Jul 25) | Stage Job B backfill script | Data eng | ◻ Ready after POC |
| Week 3 (Aug 1) | Dry-run Job B on 10 test FSRs | Data eng + Vince | ◻ |
| Week 3 (Aug 1) | Validate accuracy ≥90% | Vince (scoring) | ◻ |
| Week 3 (Aug 8) | Execute Job B on all 458 FSRs | Data eng | ◻ |
| Week 4 (Aug 8+) | Monitor retrieval + risk-eval metrics | Ops + Product | ◻ |

---

## Rollback Plan

If accuracy drops below target (< 90%) or retrieval metrics regress:

1. **Immediate:** Revert chunk table to backup (metadata UPDATE is reversible via audit log)
2. **Investigation:** Run Scorer 1 on failed batch to identify pattern
3. **Decision:**
   - If preprocessor bug: fix logic, re-validate on test set, retry backfill
   - If data quality issue: mark problematic FSRs, exclude from backfill, investigate root cause
4. **Re-attempt:** Only after post-mortem + fix validated on test set

Estimated rollback time: < 2 hours (pure metadata UPDATE).

---

## References

- Vince's Preprocessor: `ds-guru/FSR_PREPROCESSOR.md`, `ds-guru/app/preprocessor.py`
- POC Results: `FSR-v2/analysis/Vince-POC/ASSESSMENT_REPORT_ITER*.md`
- Current P1/P2 Code:
  - P1: `pw_sdg_ai_ser_repo/silver/src/etl/nb_sdg_fsr_metadata.py`
  - P2: `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`
