# FSR Chunking Strategy (V1 vs V2)

## Purpose

This note explains how chunking changed from FSR v1 to FSR v2, and why.
It is intended for engineering and product stakeholders who need a clear view
of correctness, retrieval impact, and operational behavior.

## Summary

- V1 optimized for throughput and compatibility, but applied mostly doc-level metadata to chunks.
- V2 optimizes for attribution correctness in multi-equipment reports by making chunk labeling region-aware.
- The core change is not only chunk splitter choice; it is alignment between P1 text offsets and P2 chunk offsets.
- v1 P2 = hierarchical section-aware chunking.
- v2 P2 = recursive character chunking with post-attribution from P1 regions.

## What V1 Did

Reference implementation:
- `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_chunks.py`

V1 P2 behavior (high level):
- Claims `pending/failed` docs from metadata table.
- Extracts/chunks document text using the existing hierarchical chunking flow.
- Generates embeddings in batches with retry/bisect behavior.
- Materializes chunk rows and writes with `MERGE`.
- Uses doc-level metadata heavily (including multi-ESN expansion/fan-out behavior where enabled).

Operationally, v1 was robust for large ingestion, but for mixed-equipment FSRs
it could assign chunk context at document scope rather than true local section scope.

## What V2 Does

Reference implementation:
- `pw_sdg_ai_ser_repo/gold/src/etl/nb_sdg_fsr_v2_chunks.py`
- `pw_sdg_ai_ser_repo/gold/src/etl/fsr_v2/chunking.py`

V2 P2 behavior (high level):
- Reads completed rows from `fsr_metadata_v2`.
- Re-extracts full text with `pdfplumber` so P2 text representation aligns with P1 parsing representation.
- Splits text with recursive character chunking and tracks `chunk_start_char` offsets.
- Uses `preprocessor_regions` (from P1) to attribute each chunk to one `primary_esn` and `primary_equip_type`.
- Embeds chunks and writes one row per chunk to `fsr_chunks_v2` via `MERGE`.

## Preprocessor Region Role (Important Clarification)

In v2, preprocessor regions do not decide where chunks are cut.

- Chunking step: text is first split by chunk-size and overlap settings.
- Attribution step: each chunk is then labeled using `preprocessor_regions` from P1.
- Mechanically, P2 uses each chunk's character position (`chunk_start_char`, and chunk end) and maps it to the best-overlap region.
- The mapped region provides chunk-level metadata such as `primary_esn` and `primary_equip_type`.

So the model is:
- cut first (structural split),
- label second (region-based semantic attribution).

This is the key reason v2 improves mixed-equipment retrieval quality: chunk boundaries can remain stable while equipment/ESN attribution becomes locally correct per chunk.

## Why We Changed

Key reason: correctness in multi-equipment documents.

In v1, chunk metadata could drift from true local content when a report contained
multiple equipment contexts. That affected retrieval relevance and downstream
analysis quality.

V2 fixes this by enforcing an attribution contract:
- P1 stores region boundaries (`preprocessor_regions`) in character offsets.
- P2 must chunk using a text representation aligned to those offsets.
- Chunk metadata is assigned by region overlap, not only document-level defaults.

This improves:
- Precision of equipment/ESN filters during retrieval.
- Trustworthiness of chunk-level evidence used by downstream prompts.
- Debuggability (clear preflight + batch logs around claimability and write paths).

## Design Alignment

Related design references:
- `FSR/fsr-pipeline-design.md` (v1 architecture and operational patterns)
- `2-FSR-v2/design/FSR-v2-design.md` (v2 parser/chunk attribution model)

Consistent design intent across docs/code:
- Keep v1 batch reliability patterns (claim/retry/merge).
- Replace v1-style doc-level chunk attribution with v2 region-aware chunk attribution.
- Treat this as a retrieval-quality improvement, not only a code refactor.


==================

In common/fsr_v2/chunker.py, the offsets are deterministic for a given input text and strategy, but the way start and end are computed differs by strategy.

For recursive

This is the cleanest offset model.
_recursive_split() carries relative offsets while splitting the original text, and _merge_segments() preserves those offsets when combining segments.
So start and end are based on positions in the original input text, not by re-searching chunk text later.
Relevant code: common/fsr_v2/chunker.py
For markdown

Same general model as recursive.
It first finds structural sections with offsets in the original text, then recursively splits oversized sections while adding the section base offset back in.
So this is also deterministic and still tied to original-text positions.
It is offset-safe in the same basic way as recursive.
For section
Same idea again.
Sections are extracted directly from heading match positions in the original text, then oversized sections are recursively split and their offsets are rebased to document coordinates.
So start/end are deterministic and document-based here too.
For character

This one is different.
_chunk_character() first collapses whitespace with _collapse_whitespace(), then chunks the cleaned text.
That means its start and end are offsets in the cleaned text representation, not strictly the original raw text.
So it is deterministic, but not aligned to original document character positions the same way the other three are.

This one is different.
_chunk_character() first collapses whitespace with _collapse_whitespace(), then chunks the cleaned text.
That means its start and end are offsets in the cleaned text representation, not strictly the original raw text.
So it is deterministic, but not aligned to original document character positions the same way the other three are.

===

In v1_hierarchical flow, start/end are calculated in the adapter, not inside the legacy hierarchical chunker itself.

The legacy code in common/fsr_v2/hierarchical_chunking_v1.py produces chunk text plus metadata (section/page info).
Char offsets are then assigned in common/fsr_v2/chunker.py inside _chunk_v1_hierarchical.

How it computes offsets, in order:

Exact text match from a moving cursor
It tries text.find(chunk_text, raw_cursor).
If found:
start = raw_pos
end = raw_pos + len(chunk_text)
advance cursor: raw_cursor = end
Normalized-whitespace match fallback
If exact match fails:
normalize chunk text via collapse-whitespace
search in normalized full text (text_normalized) from norm_cursor
convert normalized indices back to original-text indices using the index map from _collapse_with_index_map
If found:

start = norm_to_orig[norm_pos]
end = norm_to_orig[norm_end] + 1
advance norm_cursor with overlap-aware step
set raw_cursor = end
Final deterministic fallback
If both matches fail:
place chunk at current cursor window
start = min(raw_cursor, max(len(text)-1, 0))
end = min(len(text), start + len(chunk_text))
advance raw_cursor = end
So for v1_hierarchical, offsets are deterministic adapter-derived offsets based on:

exact substring match first
normalized match second
cursor fallback last

====================
how is start and end calculated in hierrachical_v1

In v1_hierarchical flow, start/end are calculated in the adapter, not inside the legacy hierarchical chunker itself.

The legacy code in common/fsr_v2/hierarchical_chunking_v1.py produces chunk text plus metadata (section/page info).
Char offsets are then assigned in common/fsr_v2/chunker.py inside _chunk_v1_hierarchical.

How it computes offsets, in order:

Exact text match from a moving cursor
It tries text.find(chunk_text, raw_cursor).
If found:
start = raw_pos
end = raw_pos + len(chunk_text)
advance cursor: raw_cursor = end
Normalized-whitespace match fallback
If exact match fails:
normalize chunk text via collapse-whitespace
search in normalized full text (text_normalized) from norm_cursor
convert normalized indices back to original-text indices using the index map from _collapse_with_index_map

If found:

start = norm_to_orig[norm_pos]
end = norm_to_orig[norm_end] + 1
advance norm_cursor with overlap-aware step
set raw_cursor = end
Final deterministic fallback
If both matches fail:

place chunk at current cursor window
start = min(raw_cursor, max(len(text)-1, 0))
end = min(len(text), start + len(chunk_text))
advance raw_cursor = end
So for v1_hierarchical, offsets are deterministic adapter-derived offsets based on:

exact substring match first
normalized match second
cursor fallback last
If you want, I can also add a debug log mode to record which method was used per chunk (exact, normalized, fallback) so you can evaluate offset quality on a sample doc.

===============

Yes, exactly right on both counts.

The other four strategies — character, recursive, markdown, section — all live in common/fsr_v2/chunker.py because they work directly on the input text string and track char offsets as a natural byproduct of how they split. No adapter needed.

v1_hierarchical is separate for two reasons, as you said:

Size — hierarchical_chunking_v1.py is ~900 lines of PDF-layout logic: TOC detection, font/indent heuristics, line classification, boilerplate filtering, section hierarchy building. Embedding all of that inside chunker.py would make the file unreadable.

No native offsets — V1 hierarchical was never designed around char offsets. It produces:

chunk text
section path (section_1..section_5)
start_page / end_page
It has no concept of character position in the source string. So _chunk_v1_hierarchical in chunker.py is purely an adapter: it runs the V1 engine, then post-maps each chunk text back to (start, end) positions in the full document string so the rest of the v2 pipeline can treat it identically to the other strategies.

So yes — the separation is a direct consequence of the offset mismatch, not just a code-size choice.

==========================

Correct, none of them use an LLM.

All five strategies are pure algorithmic text splitting:

character — regex whitespace collapse + sentence boundary search
recursive — regex separator cascade (headings → paragraphs → sentences → words)
markdown — regex heading/code/table detection + recursive fallback
section — regex heading markers (#) + recursive fallback
v1_hierarchical — PyMuPDF font/indent/TOC heuristics + LangChain RecursiveCharacterTextSplitter for the final text split step
LLM is only involved later in the pipeline, in the embedding step inside gold/src/etl/fsr_v2/chunking.py, where chunk text is sent to the embedding model via LiteLLM. That is completely separate from chunking strategy.

===============


