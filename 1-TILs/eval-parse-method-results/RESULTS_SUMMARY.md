# TIL Parser Evaluation Results

**Test Date:** June 23, 2026  
**Sample:** 5 curated TILs (1502-2R1, 1603-R2, 1937-R2, 1945-R2, 2284)  
**Parsers Tested:** foundation, pdfplumber, databricks_ai  

---

## Executive Summary

| Parser | Parse Success | Avg Latency | Strength | Weakness |
|--------|---------------|-------------|----------|----------|
| **pdfplumber** | 100% (5/5) | 1.35s | Fast, stable, strong field coverage | Lower table depth, weaker formula capture |
| **databricks_ai** | 100% (5/5) | 12.11s | Highest text extraction, strongest table capture, better formula capture | Much slower, slightly weaker field-hit coverage |
| **foundation** | 0% (0/5) | N/A | N/A | DNS unreachable (network issue) |

---

## Detailed Metrics

### Parse Success Rate
- **databricks_ai:** 5/5 ✓
- **pdfplumber:** 5/5 ✓
- **foundation:** 0/5 ✗ (DNS resolution failure)

### Character Count (Text Extraction)
- **databricks_ai:** 23,320.4 avg
- **pdfplumber:** 17,864 avg (natural variation)
- **foundation:** 0 (failed)

**Observation:** databricks_ai still extracts more text overall than pdfplumber.

### Required Field Hits (TIL Nomenclature Detection)
- **databricks_ai:** 16.0 avg
- **pdfplumber:** 19.8 avg
- **foundation:** 0 (failed)

**Observation:** pdfplumber is stronger on direct TIL field-term coverage in this run.

### Table Extraction
- **databricks_ai:** 5.4 avg tables per document
- **pdfplumber:** 1.8 avg tables per document
- **foundation:** 0 (failed)

**Observation:** databricks_ai is now clearly extracting tables and does so more aggressively than pdfplumber.

### Formula/Numeric Expression Detection
- **databricks_ai:** 6.0 avg
  - 2284: 29 formula hits
- **pdfplumber:** 5.4 avg
- **foundation:** 0 (failed)

**Observation:** databricks_ai is slightly stronger overall on formula-like patterns and notably better on TIL 2284.

### Latency per PDF
- **pdfplumber:** 1.35s avg (fastest)
  - Range: 0.73s—1.83s
- **databricks_ai:** 12.11s avg (8.83s—15.73s)
- **foundation:** 0.003s (attempted, failed immediately)

**Observation:** pdfplumber is still much faster, while databricks_ai has improved but remains materially slower for batch processing.

### Noise Ratio (Duplicate Line Indicator)
- **databricks_ai:** 0.283 avg (higher noise on large docs)
- **pdfplumber:** 0.251 avg (cleaner output)
- **foundation:** 0 (failed)

**Observation:** pdfplumber has lower boilerplate/duplicate content.

---

## Recommendations

### **For Production v1: pdfplumber is still the simpler default**
- ✓ 100% reliability (proven across all 5 TILs)
- ✓ Fast (1.35s per PDF average)
- ✓ Better required-field coverage in this run
- ✓ Lower noise, cleaner output
- ✗ Fewer extracted tables than databricks_ai
- ✗ Slightly weaker formula detection

**Confidence:** High for a speed-first v1. If the main requirement is reliable metadata extraction with low runtime cost, pdfplumber remains the pragmatic choice.

---

### **databricks_ai: Strong candidate when table richness matters**
- ✓ Strongest text extraction overall
- ✓ Extracts substantially more tables than pdfplumber
- ✓ Slight edge on formula-like pattern capture, especially on TIL 2284
- ✗ Slower (12.1s per PDF — much slower than pdfplumber)
- ✗ Slightly lower required-field-hit coverage in this run
- ✗ Higher noise ratio on larger documents

**Use Case:** If downstream processes depend heavily on table extraction or richer technical content capture, databricks_ai is now a real option and should be considered in an A/B validation against pdfplumber.

---

### **Foundation Service: Monitor, Not Production-Ready**
- ✗ DNS unreachable from all Databricks clusters (ai-dev-dbr, nrc-workspace)
- No current deployment or network access
- Recommend: Follow up with DS/DevOps on availability; may unblock later

---

## Action Items

1. **Immediately:** Switch workflow default to `PARSER_METHOD=pdfplumber` in `pw_sdg_til_metadata.yml`
2. **Design doc update:** Document that databricks_ai now extracts tables successfully and changes the quality/speed tradeoff
3. **Code freeze:** Keep all three parser implementations in codebase; may be needed for future environments
4. **Decision checkpoint:** Choose between `pdfplumber` and `databricks_ai` based on whether speed or richer table extraction matters more for Process 1

---

## Test Artifacts

- Detailed per-TIL metrics: `nb_til_parser_eval.csv`
- Aggregated method-level metrics: `nb_til_parser_eval (1).csv`
- Notebook: `pw_sdg_ai_ser_repo/validation/tils/nb_til_parser_eval.ipynb`
