# Retrieval Layer MLflow Experiments — FSR v2

Targeting two failure modes in multi-equipment FSRs:
1. **Retrieval miss** — Generator ESN query returns zero results (~17% of cross-ESN queries)
2. **Wrong label** — Generator chunks labeled "Gas Turbine" → bad LLM risk recommendations

---

## Exp 1 — Cross-ESN Generator Retrieval Miss Rate

**Measures Problem 1 directly.**

The existing Layer 2 probe set samples ESNs by FSR count bucket, which doesn't specifically target Generator ESNs on multi-equipment docs — exactly where the miss occurs.

### Probe set
Filter `fsr_document_equipment_map_v2` for:
- `equip_type = 'Generator'`
- `is_primary_esn = false`

These are Generator ESNs that are secondary on cross-equipment docs — the exact ESNs returning zero results in v1. For each, set `known_doc_ids` = all docs with that ESN in the equipment map.

### Metrics (extend `log_p2_experiment_end` in `mlflow_logger.py`)
```
generator_esn_probe_count       — total Generator ESN probes run
retrieval_miss_count            — probes returning 0 results
retrieval_miss_rate             — miss_count / probe_count  (target: ~0.17 → ~0)
cross_esn_recall_at_k           — for non-zero results, fraction of known docs returned
```

### A/B setup
Run identical probes against the v1 VS index and the v2 VS index. The miss rate delta is the signal. Pin the probe table (Delta version) so both runs use the same ESN population.

### Hooks into existing code
- `fsr_document_equipment_map_v2.equip_type` + `is_primary_esn` → probe source
- Probe-set pinning pattern from `eval/fsr/probe_set.py`
- Logging via `mlflow_logger.py` `log_p2_experiment_start/end`

---

## Exp 2 — ESN Attribution Accuracy at Chunk Level (Layer 1.5)

**Measures the root cause of both problems.** Scores chunk-level `primary_esn` and `primary_equip_type` against what `preprocessor_regions` says they should be. No SME labels needed — `attribute_esn()` in `common/fsr_v2/region_utils.py` is already the oracle (it's the same function P2 uses to write these values).

### Core SQL to produce the scored dataset
```sql
SELECT
    c.chunk_id,
    c.document_id,
    c.primary_esn                                                      AS stored_esn,
    c.primary_equip_type                                               AS stored_equip_type,
    get_json_object(c.metadata, '$.chunk_context.chunk_start_char')    AS chunk_start_char,
    m.preprocessor_regions
FROM fsr_chunks_v2 c
JOIN fsr_metadata_v2 m USING (document_id)
WHERE m.document_id IN (
    SELECT document_id FROM fsr_document_equipment_map_v2
    GROUP BY document_id HAVING count(*) > 1   -- multi-ESN docs only
)
```

Then apply `attribute_esn(chunk_start_char, preprocessor_regions)` in Python per row to get `expected_esn` / `expected_equip_type` and diff against stored values.

### Metrics (new `log_attribution_accuracy_experiment()` in `mlflow_logger.py`)
```
multi_esn_doc_count                     — docs with > 1 ESN in scope
chunks_evaluated                        — chunk rows scored
esn_attribution_accuracy                — fraction where stored_esn == expected_esn
equip_type_accuracy                     — fraction where stored_equip_type == expected_equip_type
pct_generator_chunks_mislabeled_as_gt   — generator-region chunks with equip_type='Gas Turbine'
pct_unattributed_chunks                 — chunks where primary_esn = '' (Step 2b fallback exposure)
```

`pct_generator_chunks_mislabeled_as_gt` is the single most direct metric for Problem 2. In v1 (doc-level fan-out) it will be high; in v2 (region attribution) it should be near zero.

### Hooks into existing code
- `common/fsr_v2/region_utils.attribute_esn()` — reuse as oracle directly
- `fsr_metadata_v2.preprocessor_regions` + `fsr_chunks_v2.metadata.chunk_context.chunk_start_char` — both already written by the pipeline

---

## Exp 3 — Keyword-Based Equipment Type Precision Check

**Validates Problem 2 from the content side.** Uses domain keyword signals (from Xujin's edge case list and the preprocessor) as a content-based pseudo-oracle. This catches cases where `preprocessor_regions` itself has gaps — e.g., docs where generator content exists but no generator ESN appears in the text at all.

Generator keyword signals: `DC leakage`, `electrification`, `stator`, `rotor`, `field winding`, `generator bearing`

### Approach
For chunks where `chunk_text` matches the keyword pattern, check `primary_equip_type = 'Generator'`. Reuse the keyword regex already in the preprocessor rather than defining a new one.

**Important**: this is precision-only. A chunk about GT combustion liner won't have generator keywords, so false negatives from the keyword oracle are expected — don't penalize for them. Only keyword hits are used as positive evidence.

### Metrics (new `log_label_precision_experiment()` in `mlflow_logger.py`)
```
keyword_positive_chunks              — chunks matching at least one generator keyword
keyword_precision                    — fraction of keyword-positive chunks labeled Generator
keyword_labeled_gt_count             — keyword-positive chunks incorrectly labeled Gas Turbine
keyword_labeled_unattributed_count   — keyword-positive chunks with empty primary_equip_type
```

---

## Run Structure (A/B)

```
Parent run: fsr_retrieval_accuracy_vN
├── Exp 1 (generator_retrieval_miss_rate)
│   ├── baseline: v1 VS index, Generator ESN probes
│   └── candidate: v2 VS index, same pinned probes
├── Exp 2 (esn_attribution_accuracy)
│   ├── baseline: fsr_chunks_v1 + fsr_metadata_v1 regions
│   └── candidate: fsr_chunks_v2 + fsr_metadata_v2 regions
└── Exp 3 (keyword_equip_type_precision)
    ├── baseline: fsr_chunks_v1 keyword scan
    └── candidate: fsr_chunks_v2 keyword scan
```

---

## Labeled Data Requirements

None of the three experiments require external labeled or SME-reviewed data. But they have different oracle sources, and what each one actually proves differs:

| Experiment | Oracle source | What it proves | What it can't catch |
|---|---|---|---|
| Exp 1 | `fsr_document_equipment_map_v2` (pipeline-derived, P1 output) | Generator ESNs known to the equipment map are retrievable | Generator ESNs the preprocessor missed at doc level — they won't be in the map and won't be probed |
| Exp 2 | `preprocessor_regions` via `attribute_esn()` (pipeline-derived) | Chunk table is internally consistent with what the preprocessor emitted | Region boundary errors — if the preprocessor drew a boundary in the wrong place, both oracle and stored value are wrong the same way |
| Exp 3 | Keyword heuristic (no pipeline dependency) | Keyword-positive chunks have the right equip_type label (precision only) | Generator chunks with no matching keywords — recall is unmeasurable without labels |

All three run immediately without SME involvement. What they collectively validate is internal pipeline consistency and retrieval coverage, not whether the preprocessor's region boundaries are factually correct against the PDF content.

### If region boundary accuracy becomes a priority

To validate whether the preprocessor correctly identifies where Generator sections start and end, a small SME-reviewed labeled set is needed. The 3 confirmed ESNs from the fix plan are a natural seed — they already have verified doc IDs and confirmed generator content:

| ESN | Verified doc ID | Notes |
|---|---|---|
| `290T483` | `35803273-...`, `37211_270t483-...` | Generator content confirmed in 2 of 12 PDFs |
| `316X914` | `5b688732-...` | 27 chunks confirmed, 1 PDF |
| `337X581` | `fcb1511e-...`, `bdd56c7a-...` | Confirmed in 7 of 9 PDFs |

An SME could annotate region start/end page numbers for these docs, which would turn Exp 2 into a true accuracy check (oracle = SME labels rather than preprocessor self-report).

---

## Not in scope now (future Layer 3)

End-to-end LLM judge experiment — retrieve chunks for Generator ESN queries, feed to a mock LLM judge, check if recommendations are equipment-type-specific. This directly measures the downstream impact of Problem 2, but it's expensive and hard to make reproducible without a frozen LLM version + fixed prompt. Track for later.
