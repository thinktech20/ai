# FSR v2 Chunking Strategies Reference

## Chunking Strategies Overview

| Strategy | One-line Description | Offset Calculation |
|----------|----------------------|-------------------|
| **character** | Collapses whitespace, then chunks text by fixed character size with sentence boundary detection. | Offsets calculated in collapsed-text representation (whitespace normalized). Deterministic but not strictly aligned to raw document character positions. |
| **recursive** | Cascading regex separator strategy: headings → paragraphs → sentences → words, recursively splitting oversized segments. | Offsets tracked directly during recursive split via relative position tracking. Rebased back to original-text coordinates as segments merge. Deterministic and original-text aligned. |
| **markdown** | Detects markdown structural elements (headings, code blocks, tables) with regex; recursively splits oversized sections. | Sections extracted directly from heading match positions in original text. Oversized sections split recursively with offsets rebased to document coordinates. Deterministic and original-text aligned. |
| **section** | Identifies section boundaries via regex heading markers (#); recursively splits sections exceeding size threshold. | Section positions extracted from heading matches in original text. Recursive splits applied with offsets rebased to document coordinates. Deterministic and original-text aligned. |
| **v1_hierarchical** ⭐ default | PyMuPDF font/indent/TOC heuristics to extract hierarchy; LangChain RecursiveCharacterTextSplitter for final text split. | Post-mapped adapter: (1) exact substring match from cursor, (2) normalized-whitespace match fallback, (3) cursor position fallback. Deterministic via three-tier matching strategy. Original-text aligned. |

## Offset Calculation Details by Strategy

### Character
- Text is first normalized via `_collapse_whitespace()` to remove excess whitespace
- Chunks are split at fixed character size with sentence boundary detection
- **Start/End:** Offsets are positions in the **collapsed text**, not original raw text
- **Implication:** When mapping back to original document, some character-offset correspondence may be approximated

### Recursive
- Input text is split recursively via separator cascade: headings (##) → paragraphs (\\n\\n) → sentences (.) → words ( )
- Each recursive split maintains relative position tracking through the recursion depth
- Segments are then merged, with all offsets rebased to original-text coordinates
- **Start/End:** Document-based absolute character positions
- **Alignment:** Original-text aligned (safe for P1 region matching)

### Markdown  
- Regex detects markdown structural elements: headings, code fences, tables
- Each detected section is extracted with its position in original text
- Sections exceeding chunk size are recursively split with offsets rebased
- **Start/End:** Document-based absolute character positions
- **Alignment:** Original-text aligned (safe for P1 region matching)

### Section
- Regex searches for heading markers (#) to identify section boundaries
- Sections are extracted directly from match positions in original text
- Oversized sections are recursively split with offsets rebased to document coordinates
- **Start/End:** Document-based absolute character positions
- **Alignment:** Original-text aligned (safe for P1 region matching)

### V1 Hierarchical (Adapter Pattern)
- Legacy `hierarchical_chunking_v1.py` produces chunk text + section metadata (no native char offsets)
- Adapter `_chunk_v1_hierarchical()` post-maps each chunk back to (start, end) positions via three-tier matching:
  1. **Exact match:** `text.find(chunk_text, cursor)` — if chunk text found exactly, use position directly
  2. **Normalized match:** Collapse whitespace in both chunk and full text, search normalized representation, convert back via index map
  3. **Cursor fallback:** If both matches fail, place chunk at current cursor position window with length-based estimate
- **Start/End:** Document-based absolute character positions (derived post-hoc)
- **Alignment:** Original-text aligned via deterministic fallback logic

## Offset Alignment & Extraction Tool

All strategies in v2 rely on **pdfplumber** for text extraction in P1 and P2, ensuring char-offset consistency:
- P1 extracts via pdfplumber (parsing.py)
- P2 extracts via pdfplumber (text_extraction.py)
- Preprocessor regions are anchored to pdfplumber text offsets
- All chunking strategies operate on pdfplumber-extracted text
- Note: v1_hierarchical uses PyMuPDF internally for structure detection, but the adapter post-maps offsets back to pdfplumber coordinates for consistency

This single-tool approach for P1/P2 eliminates extraction mismatches and ensures region attribution reliability.

All five strategies feed into P2 chunk attribution:
- Each chunk is positioned via `[chunk_start_char, chunk_end_char]` in the original document text
- P1 preprocessor regions (from `preprocessor_regions` in metadata table) are compared via **best-overlap matching**
- Highest overlap wins → chunk inherits `primary_esn`, `primary_equip_type`, and other region metadata
- This is decoupled from chunking strategy; all strategies support region attribution equally

## Reference Implementation

- **chunker.py:** `common/fsr_v2/chunker.py` — Contains logic for character, recursive, markdown, section strategies
- **v1_hierarchical adapter:** `common/fsr_v2/chunker.py` / `_chunk_v1_hierarchical()` — Post-mapping adapter for legacy hierarchical chunker
- **P2 usage:** `gold/src/etl/fsr_v2/chunking.py` — Loads chunks from selected strategy, performs region attribution, embeds, writes to fsr_chunks_v2
