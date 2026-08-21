# FSR v2 Metadata Processor Variants

## Overview

Two processor variants available for Stage 3 (Metadata Extraction):
- **metadata_processor.py** — baseline preprocessor
- **metadata_processor_v2.py** — baseline + TOC-based document summary extraction

## Comparison

| Feature | metadata_processor.py | metadata_processor_v2.py |
|---------|----------------------|------------------------|
| **Primary Purpose** | Extract standard metadata fields (ESN, equipment type, dates) | Same + extract document summary from TOC |
| **Preprocessor** | Runs `_preprocessor.preprocess(ctx)` | Same |
| **Output Fields** | primary_esn, primary_equip_type, primary_technology_code, inactive_esns, gt_esn, gen_esn, outage_start_date, outage_end_date, report_issued_date, document_name | All above + `document_summary` |
| **Implementation** | Pass-through to preprocessor | Pass-through + TOC extraction + enrichment |
| **PDF Parsing** | Not performed (uses parsed_doc from Stage 2) | Requires direct PDF file read via `pdfplumber` |
| **Complexity** | ~70 lines | ~250 lines |

## metadata_processor.py (Baseline)

**What it does:**
1. Wraps parsed document into a context object
2. Passes to `_preprocessor.preprocess()`
3. Returns result dict: `{metadata, hints, regions}`

**Code flow:**
```python
ctx = SimpleNamespace(
    pages=parsed_doc.pages,
    page_offsets=parsed_doc.page_offsets,
    full_text=parsed_doc.full_text,
    fields=_FIELDS,
    filename=parsed_doc.filename,
)
return _preprocessor.preprocess(ctx)
```

**Use case:** Standard metadata extraction for all documents; sufficient when doc summary is not needed downstream.

## metadata_processor_v2.py (TOC Summary Variant)

**What it does:**
1. Runs baseline preprocessor (same as metadata_processor.py)
2. Extracts table of contents (TOC) from first few pages
3. Finds "Executive Summary" / "Inspection Summary" / "Summary" sections in TOC
4. Reads PDF directly to extract text from identified summary section(s)
5. Adds `document_summary` field to metadata dict
6. Returns enriched result

**Key helper functions:**
- `_extract_toc_entries(pdf)` — scans first 3–5 pages, extracts TOC title-to-page-number mappings via word-position analysis
- `_detect_page_offset(pdf)` — determines if printed page numbers differ from actual file indices (common in multi-part reports)
- `_build_doc_summary_sections(toc_entries, total_pages)` — identifies which TOC entries are summary sections
- `_extract_section_text(pdf, start_page, end_page, offset)` — extracts text from pages within detected summary range
- `_extract_document_summary(volume_path)` — orchestrates full extraction; returns None if extraction fails

**Detection logic:**
- Scans first 3–5 pages for "Table of Contents" heading
- Extracts text rows grouped by y-coordinate (with 3-pixel tolerance for alignment)
- Parses left-side titles and right-side page numbers from each row
- Filters noise (empty lines, "Contents", etc.) via `DOC_SUMMARY_NOISE_PATTERN`
- Matches section titles against `DOC_SUMMARY_PATTERN` (case-insensitive regex for "executive summary", "inspection summary", "summary")
- Extracts text from identified pages, cropping footer region (bottom 10%) to reduce noise

**Use case:** When documents need summary-level context populated early (e.g., for LLM-based downstream tasks, validation, or chunk-level metadata enrichment).

## Output Differences

### metadata_processor.py result:
```python
{
    "metadata": {
        "primary_esn": "298250",
        "primary_equip_type": "Generator",
        "inactive_esns": ["338X447"],
        "outage_start_date": "2026-07-15",
        # ... other fields
    },
    "hints": "...",
    "regions": [...]
}
```

### metadata_processor_v2.py result:
```python
{
    "metadata": {
        "primary_esn": "298250",
        "primary_equip_type": "Generator",
        "inactive_esns": ["338X447"],
        "outage_start_date": "2026-07-15",
        "document_summary": "Executive Summary\n\nThe inspection identified...",  # ← NEW
        # ... other fields
    },
    "hints": "...",
    "regions": [...]
}
```

## Tuning Parameters (metadata_processor_v2.py)

```python
DOC_SUMMARY_PATTERN = r"\bexecutive\s+summary\b|\binspection\s+summary\b|\bsummary\b"
DOC_SUMMARY_NOISE_PATTERN = r"^[\s_\-\.\|]*$|^table\s+of\s+contents?$|^contents?$"
DOC_SUMMARY_ROW_TOLERANCE = 3                    # pixels; word alignment tolerance
DOC_SUMMARY_FOOTER_CROP_RATIO = 0.90             # exclude bottom 10% of page
DOC_SUMMARY_HEADER_ZONE_RATIO = 0.10             # search for page offset in top 10%
DOC_SUMMARY_FOOTER_ZONE_RATIO = 0.10             # search for page offset in bottom 10%
```

## When to Use

| Scenario | Recommended |
|----------|-------------|
| Standard P1 metadata extraction for all documents | `metadata_processor.py` |
| Need document summary for downstream LLM tasks (e.g., chunk context, validation) | `metadata_processor_v2.py` |
| Processing high volume; summary not required | `metadata_processor.py` (lighter weight) |
| Improving chunk-level retrieval via early summary context | `metadata_processor_v2.py` |

## Migration / Switchover

To switch notebook from one variant to the other:

**In nb_sdg_fsr_v2_metadata.py:**

Before:
```python
proc_meta = metadata_processor.run(parsed_doc)
```

After (to use TOC summary):
```python
import metadata_processor_v2 as metadata_processor  # or direct import
proc_meta = metadata_processor.run(parsed_doc)
```

Both return the same structure, so downstream code does not need changes.
If summary extraction fails, `document_summary` will be `None` (not an error).

## Reference

- Location: `pw_sdg_ai_ser_repo/silver/src/etl/fsr_v2/`
- Related: `nb_sdg_fsr_v2_metadata.py` (Stage 3 entry point in notebook)
- Related: `common/fsr_v2/preprocessor.py` (baseline preprocessor used by both)
