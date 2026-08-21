# Root Cause: Spurious UNNUMBERED Equipment Blocks Corrupting Section Hierarchy

**Document:** `af693a98-1e5c-499d-aa10-cccc54885c64`
**Symptom:** Turbine subsections showing Generator ESN in `section_path` despite correct `resolved_esn`.

---

## What Was Observed

Region metadata showed `primary_equip_type: Generator`, `primary_esn: 337X766`, `esn_source: parent_inherit` for intervals that fell entirely within Gas Turbine-named subsections (`2.4.2 Combustion`, `2.5.1 Turbine`, etc.).

---

## Root Cause

### Phase 2 — Hierarchy build

The `UNNUMBERED_EQUIP_HDR` pattern (`^(GAS TURBINE|GENERATOR|...)\s*$`) matched standalone equipment-name lines in the overview/summary pages of the document. In this document, two spurious `Generator` UNNUMBERED matches appeared at char offsets ~9257 and ~9364 — immediately before the numbered sections beginning at ~9509.

Span builder stack trace at the time `2 Turbine` (level=0, Gas Turbine) was processed:

```
idx 2: GAS TURBINE (297652) HEADER  level=-1  start=8883  — popped by idx 3
idx 3: Gas Turbine UNNUMBERED        level=-1  start=9028  — popped by idx 4
idx 4: Generator   UNNUMBERED        level=-1  start=9257  — popped by idx 5
idx 5: Generator   UNNUMBERED        level=-1  start=9364  ← stack top
idx 6: 2 Turbine   SECTION_HDR       level=0   parent_idx=5  ← wrong parent
```

Each incoming level=-1 span pops the previous level=-1 off the stack. By the time `2 Turbine` (level=0) is processed, the stack holds only the **Generator** UNNUMBERED block at 9364, which becomes its parent.

### Phase 3 — ESN resolution

Because `2 Turbine` has `equipment_type = "Gas Turbine"` (from `SECTION_HDR`), Phase 3 does **not** use `parent_inherit` — it falls through to `single_type` and correctly resolves to `297652`. All downstream Gas Turbine subsections also resolve to `297652` correctly.

**The ESN output is correct. The `parent_idx` structural link is wrong.**

### Downstream effect

`_section_path_for_span` walks the `parent_idx` chain and shows `Generator` at the root instead of `Gas Turbine` for Gas Turbine subsections. This is misleading in region metadata `section_path` even though `primary_esn` and `primary_equip_type` are correct.

The deeper appendix subsections (`## 5.1 Combustion`, idx 29-32) also acquire convoluted parent chains through the Generator subsection (`### 2.6.1 Generator`) via the `level_conflict` path, but again resolve via `single_type` so the ESN is unaffected.

---

## Why It Doesn't Corrupt ESN (Currently)

The single-turbine-ESN document (`active_by_type["Gas Turbine"] = ["297652"]`) triggers `single_type` for all typed Gas Turbine spans regardless of parent. If a document had **two active Gas Turbine ESNs**, these spans would fall through to IBAT or `esn_confidence=none`, and the wrong parent would matter more.

---

## Fix Direction

In `_build_hierarchical_spans`, when assigning a level=-1 parent to a typed numbered section, prefer the level=-1 ancestor whose `equipment_type` matches the candidate. Skip Generator UNNUMBERED anchors when the section is typed Gas Turbine (and vice versa).

Alternatively, gate `UNNUMBERED_EQUIP_HDR` matches to a minimum char offset (past the front-matter/overview pages) using a similar `toc_cutoff` guard already applied to `SUBSEC_GEN` and `SUBSEC_GT`.

---

## Status

- ESN output for this document is correct in the current run.
- `section_path` in region metadata shows incorrect ancestry (Generator root instead of Gas Turbine root).
- Fix is pending — tracked as a structural Phase 2 issue.
- The temporary `SPAN_DUMP` debug logging in `preprocessor_v2.py` should be removed before the next production run.
