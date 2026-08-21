## Detailed Explanation

When we say **"re-chunking selected ESNs"**, we mean:

- For some reports, we can keep existing chunks and only fix metadata tags.
- For other reports, we need to re-create chunks because one old chunk contains both Gas Turbine and Generator content.

### When Re-Tagging Is Enough

- If a chunk already aligns to the correct equipment section, we can keep the chunk text and just correct metadata.
- In that case, the issue is only wrong labeling, not chunk structure.

### Why Some Reports Need Re-Chunking

- In multi-equipment FSRs, an old chunk can cross GT and Generator boundaries.
- If the chunk itself is mixed, changing only the label does not fix the content problem.

This causes two risks:

- **Retrieval misses**: Generator queries may not return the right chunks.
- **Wrong context**: Generator findings can appear in GT-tagged chunks (or vice versa).

### One Important Technical Point

- We need the same text extraction tool in metadata extraction and chunking (now **pdfplumber for both**) so region offsets map correctly.
- If extraction representations differ, region-to-chunk mapping becomes unreliable.
- **This is a key design requirement.** Per-chunk region attribution depends on `preprocessor_regions` char offsets from the P1 text representation. Parser-aligned chunking + re-embedding provides the most reliable attribution for v2 — for new v2 documents.

### Extraction Consistency (v2 Design)

- **v2 uses pdfplumber for P1 and P2** to ensure metadata regions and chunking operate on the same text representation.
- This eliminates extraction mismatch risks between P1 region boundaries and P2 chunk positions.
- Region offsets are anchored to pdfplumber text in both P1 (parsing.py) and P2 (text_extraction.py), ensuring reliable char-offset matching during chunk attribution.

## Short Answer

- For **new v2 documents**: parser-aligned re-chunking and re-embedding provides optimal attribution. This approach ensures consistent region-to-chunk mapping for v2 accuracy.
- For **existing v1 chunk rows not being re-ingested**: deriving boundaries post-hoc is higher effort and less reliable at scale. Metadata tag corrections are still valid for improving retrieval filters without full re-chunking, but will not fix chunks that contain genuinely mixed-equipment content.

## Inflation Concerns

The v1 pipeline had a fan-out behavior: for multi-equipment documents, it could produce one chunk row per ESN, regardless of whether that chunk's content was actually about that equipment. This resulted in duplicated rows with different ESN labels for the same chunk text.

- **Performance impact**: duplicated/fanned-out rows increase index size, query latency, and storage/compute cost.
- **Data reliability impact**: duplicate chunk variants with different ESN labels create noisy ranking, inconsistent filtering, and harder root-cause analysis.

The v2 path eliminates fan-out by attributing each chunk to exactly one ESN based on which region the chunk's character offset falls in (best-overlap wins).

## Proposed Solution

- Keep two indexes during transition:
	- New v2 index (primary)
	- Old index (fallback)
- Query v2 first.
- Only fallback to old index when:
	- v2 returns low-confidence/low-coverage results, or
	- result count is below a minimum threshold.
- Log fallback usage so we can measure when old index can be retired.