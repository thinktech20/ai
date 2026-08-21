# Week of 2026-07-28

---

## Accomplished

- Finished FSR v2 implementation end-to-end — preprocessor integrated into P1, per-chunk ESN attribution wired through P2, vector index synced in P3
- Ingested a set of docs and shared with SME for validation (7 confirmed failing docs + 5 ESNs from Abhinaya's list)

---

## Next Week

- Review SME validation feedback and implement fixes
- Work through Xujin's pre-processor edge cases — identify handling logic for each category, review with Vince before implementing
- Set up MLflow experiment for top-K / retrieval strategy testing in Databricks

### Action Items

| Owner | Action |
|---|---|
| Madhurima + Xujin | Design logic for preprocessor edge cases; review with Vince before implementing |
| Madhurima | Set up MLflow experiment for top-K / retrieval strategy testing |
| Tao | Check if current fix covers same-type dual-ESN tagging issue |
| Abhinaya | Investigate ER case date discrepancy in dev URA |
| Vince | Look at the ST-with-hidden-Generator edge case document |
| Madhurima | Persist text extracts to Databricks volume (next rechunking cycle) |

### Preprocessor Edge Cases to Design (from Xujin)

1. Multiple same-type ESNs in one doc — wrong boundary reset after the second section
2. Generator subsection nested under a GT section — content after the generator subsection re-attributed incorrectly
3. "Electrification" section header as a generator signal — not currently recognized
4. Generator ESN absent from body text but content is clearly generator evidence
5. Steam turbine doc with embedded generator evidence — no ESN or keyword signal visible; may need IBOT train tool
