# Point 1 — section_v2 design: Analysis & Plan

**Decision:** Use the `section` chunking strategy (ported from ds-guru) with pypdf2 as the P2
text source. Enhance it to produce `section_1..section_5` metadata fields matching FSR v1 output.
This is "section_v2".

---

## What the two examples in to-dos show

**section strategy output (fsr_v2_chunk_metadata_v2 schema) — current:**
```json
"section": {
  "section_title": "Rotor Assembly",
  "section_level": 3,
  "section_path": ["Components", "Rotors", "Rotor Assembly"]
}
```

**v1_hierarchical output (FSR v1 flat schema):**
```json
"section_1": "inch extraction valve was disassembled, inspected and reassembled this outage.",
"section_2": "Alignment/Clearances",
"section_3": "Steam Path Internal Clearances",
"section_4": "Wheel Clearance Record",
"section_5": null
```

`section_1` in the v1_hierarchical example contains **body text**, not a heading. That is a known
misclassification bug in the PyMuPDF-based hierarchical chunker — PyMuPDF occasionally promotes a
bold or large-font body sentence as a section heading. The section strategy avoids this because it
only promotes lines that `_inject_pdf_heading_markers` explicitly tagged as headings.

---

## Code path for each strategy

### v1_hierarchical  (common/fsr_v2/chunker.py → _chunk_v1_hierarchical)

1. Opens the PDF with PyMuPDF `load_pdf_snapshot` → gets block/span/font-size data.
2. Runs `hierarchical_semantic_chunking_from_snapshot` (copied from FSR v1 `fsr_chunking.py`).
3. Each raw chunk carries `section_1..section_5` in its metadata (PyMuPDF TOC/font-level classifier).
4. `chunker.py` reads those fields and builds `_last_section_map` entries as `{title, level, path: list}`.
5. `chunking.py` calls `chunker.get_section_metadata(start, end)` and stores result under `chunk["section"]`.

**Key dependency:** section hierarchy comes entirely from PyMuPDF's visual features (font size,
bold, x-position). No dependency on the pypdf2/pdfplumber text that the rest of P2 uses.

### section strategy  (common/fsr_v2/chunker.py → _chunk_by_sections)

Origin: ported from `ds-guru/app/chunker.py` — same `_chunk_by_sections`, `_extract_sections`,
and `get_section_metadata` structure, almost verbatim.

1. Receives `full_text` from P2 (`text_extraction.extract_pages` → **pdfplumber today — this is wrong**).
2. Scans for lines matching `^(#{1,6})\s+(.+)$` — lines with `#` markers from `_inject_pdf_heading_markers`.
3. Builds `sections` list with `{title, level, path}` — where `path` is currently a **`" > "` joined string** (ds-guru origin).
4. `get_section_metadata` returns `{section_title, section_level, section_path: string}`.
5. `chunking.py` stores result under `chunk["section"]`.

**Key dependency:** section headings only come from `#`-marked lines. Those markers exist in
pypdf2 text (P1 injects them via `_inject_pdf_heading_markers`). They do **not** exist in
pdfplumber text. So with today's P2 text source (pdfplumber), the section strategy finds **zero
headings** and falls back to recursive splitting → `section: {}` empty for every chunk.

---

## Schema differences (today)

| Field | v1_hierarchical | section strategy (today) |
|---|---|---|
| path type | list `["A", "B", "C"]` | string `"A > B > C"` (ds-guru origin) |
| level | `int` (depth of list) | `int` (count of `#`) |
| title key | `title` | `section_title` |
| level key | `level` | `section_level` |
| path key | `path` | `section_path` |
| Output fields | `section_1..section_5` in path list | no `section_N` fields |

The field names differ. `chunking.py` stores whatever `get_section_metadata` returns under
`chunk["section"]`, so the metadata JSON `section` block has inconsistent keys across strategies.

---

## Known problems with v1_hierarchical

1. **Body text misclassified as heading** — `section_1 = "inch extraction valve was disassembled..."` is body text, not a heading. PyMuPDF font-size classification is imprecise for FSR docs.
2. **Empty `primary_esn`** — P2 uses pdfplumber text; P1 uses pypdf2 to build `preprocessor_regions`. `chunk_start_char` is in pdfplumber coordinate space, regions are in pypdf2 space → overlap never fires → `region: {primary_esn: "", primary_equip_type: ""}` for all chunks.
3. **Mapping misses** — PyMuPDF chunk text doesn't match verbatim in pdfplumber reference text (whitespace/ligature differences) → `_last_mapping_miss_chunk_indices` populated → region attribution skipped.

---

## section_v2: two code changes

### Change 1 — `text_extraction.py`: switch pdfplumber → pypdf2

`text_extraction.py`'s `extract_pages` currently uses pdfplumber. Its docstring even says "same as
P1" but P1 uses `parse_pypdf2` with heading marker injection — that is wrong. Fix:

```python
# today
import pdfplumber
with pdfplumber.open(volume_path) as pdf:
    pages.append(page.extract_text() or "")

# section_v2
from silver.src.etl.fsr_v2.parsing import parse_pypdf2
parsed = parse_pypdf2({"document_id": ..., "volume_path": volume_path, ...})
pages = parsed.page_texts
page_offsets = parsed.page_offsets
```

Effect:
- `full_text` now has `#`-injected headings → section strategy finds headings.
- `chunk_start_char` is now in pypdf2 coordinate space → matches `preprocessor_regions` offsets from P1 → `primary_esn` populates correctly.
- No more systematic mapping misses (both extraction paths use the same text).

### Change 2 — `chunker.py`: output `section_1..section_5` from section strategy

`_extract_sections` builds a `heading_stack` as `list[(level, title)]`. Change `path` from a
joined string to a list, then map to `section_1..section_5` in `get_section_metadata`:

**In `_extract_sections`** — one line change:
```python
# today (ds-guru origin)
path = " > ".join(t for _, t in heading_stack)

# section_v2
path = [t for _, t in heading_stack]   # list, not string
```

**In `get_section_metadata`** — return `section_1..section_5`:
```python
# today (ds-guru origin)
return {
    "section_title": sec["title"],
    "section_level": sec["level"],
    "section_path": sec["path"],      # string "A > B > C"
}

# section_v2 — matches FSR v1 output schema
path = sec["path"]   # now a list
return {
    "section_1": path[0] if len(path) > 0 else None,
    "section_2": path[1] if len(path) > 1 else None,
    "section_3": path[2] if len(path) > 2 else None,
    "section_4": path[3] if len(path) > 3 else None,
    "section_5": path[4] if len(path) > 4 else None,
}
```

Result — `section` block in chunk metadata JSON:
```json
"section": {
    "section_1": "Gas Turbine",
    "section_2": "Stage 1 Nozzle Inspection",
    "section_3": null,
    "section_4": null,
    "section_5": null
}
```

Same structure as FSR v1's flat fields, now nested under `section` per the v2 contract.

---

## section_v2 vs v1_hierarchical: final comparison

| | v1_hierarchical | section_v2 |
|---|---|---|
| PDF extraction library | PyMuPDF (font/position data) | pypdf2 (`_inject_pdf_heading_markers`) |
| Heading detection | Font size + bold flags (visual) | `#`-prefixed lines (heuristic text) |
| Catches unnumbered visual headings | Yes (e.g. bold "EXECUTIVE SUMMARY") | Only if ALL-CAPS → got `## ` injected |
| Body text misclassified as heading? | Yes (known bug) | No |
| Offset alignment with P1 regions | Broken (pdfplumber mismatch) | Fixed (same pypdf2 text as P1) |
| `primary_esn` populated? | Empty | Populated |
| Mapping misses | Present | Zero |
| PyMuPDF dependency in P2 | Yes | No |
| Output fields | `section_1..section_5` | `section_1..section_5` (same) |

---

## Comparison to run

Run both strategies on the same 3–5 representative FSR PDFs (GT+GEN combo, ST-only, single-equipment):

1. Does `section_1..section_5` from section_v2 correctly reflect the document TOC hierarchy?
2. Are there headings v1_hierarchical catches that section_v2 misses (unnumbered, visually styled headings)?
3. Does section_v2 have false positives (ALL-CAPS non-heading lines tagged as `## `)?
4. Is `primary_esn` populated in section_v2 chunks where it was empty under v1_hierarchical?

Suggested test doc: `5b688732-39f2-48d2-a887-3239f258d28b` (already has known v1_hierarchical output for comparison).
