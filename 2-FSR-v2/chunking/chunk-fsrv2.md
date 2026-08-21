1. Merge Priority: upload-level < doc-level < section < region
This describes how per-chunk ESN/equipment metadata is assembled. The priority controls which source wins when multiple sources provide the same field (e.g., primary_esn, equip_type).

In chunking.py → _resolve_chunk_meta_fields(), the cascade is built step-by-step:


What each level represents:

Level	Source	What it provides
upload	upload_meta dict passed into run()	Job-level context: doc_type, priority, file_path
doc	fsr_metadata_v2 row	Document-wide ESN/equip extracted in P1 (e.g., primary_esn, gt_esn, gen_esn)
section	chunker.get_section_metadata(start_char, end_char)	Heading hierarchy (section_1..section_5) for the chunk's position in the text
region	region_utils.attribute_esn(chunk_start_char, preprocessor_regions)	P1 preprocessor spatially-delimited region (e.g., "GT section starts at char 0, Gen section starts at char 8400") — most precise, wins all conflicts
The region level exists precisely to solve the multi-ESN FSR problem described in the design doc: a single document has a Gas Turbine section and a Generator section. The preprocessor (P1) marks those char-offset boundaries as preprocessor_regions. P2 looks at where each chunk falls and assigns it to the right ESN — overriding whatever doc-level default said.

The V2_DOC_SECTION_ONLY merge strategy stops at Step 3 (no region override), used when preprocessor regions are unavailable or unreliable.

2. _chunk_by_sections vs _chunk_v1_hierarchical
These two strategies answer the same question ("how do I split this text?") but from completely different starting points:

_chunk_by_sections — text-only, structure-inferred
Input: raw text string only
How it finds structure: scans lines with _extract_sections_structural() — looks for markdown # headings and 1.2.3 Numbered headings, skipping TOC entries
No external deps — pure Python regex on the text
Section hierarchy: inferred from heading markers in the text itself; stored in _last_section_map so get_section_metadata() can serve section_1..5 for each chunk
Overlap logic: sophisticated — skips overlap at top-level section transitions, TOC/legal boilerplate, and prose boundaries
_chunk_v1_hierarchical — PDF-aware, externally structured
Input: text string plus pdf_path (required)
How it finds structure: delegates to hierarchical_semantic_chunking_from_snapshot() from the legacy v1 chunker, which loads a PDF snapshot (visual/structural PDF analysis, not just regex on extracted text). The PDF snapshot can detect headings that survive poorly through text extraction (e.g., PDFs where heading markers aren't in the text).
Falls back to _chunk_recursive in three cases: no pdf_path, import failure, or chunking failure — tracking the reason in _actual_strategy for data lineage
Section hierarchy: read from metadata.section_1..section_5 fields on the v1 chunk entries — those came from the PDF structure, not text regex
Offset mapping: v1 doesn't return offsets, so _chunk_v1_hierarchical does a two-pass search (exact text match → whitespace-collapsed match → cursor fallback) to map each v1 chunk back to character offsets in the source text. Mapping misses are tracked in _last_mapping_miss_chunk_indices.
Key difference table
_chunk_by_sections	_chunk_v1_hierarchical
Requires PDF	No	Yes (pdf_path)
Heading detection	Regex on extracted text	PDF snapshot (visual structure)
Section metadata	Inferred from text markers	Comes from v1 legacy chunker output
Offset tracking	Native (text slices)	Post-hoc remapping (with fallback)
Fallback	_chunk_recursive if no headings found	_chunk_recursive on import/runtime failure
Data lineage field	_actual_strategy = "section" (always)	_actual_strategy records fallback reason
Overlap	Semantics-aware cross-section overlap	No cross-chunk overlap logic
In practice: section is the default production strategy (FSR_CHUNKING_STRATEGY = "section") because it works on plain extracted text and aligns with P1's pypdf2 text. v1_hierarchical is the compatibility adapter for running legacy v1 PDF chunking within the v2 pipeline when you need its PDF-structure-aware heading detection.