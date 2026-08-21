Hi Tao, reviewed your note in 2-FSR-v2/analysis/FSR_P1_Chunking_Strategy_Evaluation.md. I came to the same conclusion from checking ds-guru offset handling and our FSR v1 hierarchical path.

Quick summary:

recursive: offsets come from recursive splits on the same source text
character: offsets come from direct character-window slicing
markdown: offsets come from markdown section splits on the same source text
section: offsets come from heading-based section boundaries on the same source text

For v1-style hierarchical chunking, I implemented offset mapping by:

1. exact substring match in full text,
2. normalized-text match with index map back to original offsets,
3. deterministic cursor fallback only as last resort.

One difference from your doc: I added a reliability guardrail in pipeline behavior for mapping misses. When chunk-to-raw mapping misses, we skip region-level attribution from approximate offsets, fall back to doc-level metadata for that chunk, and log mapping_miss counters (with sample chunk ids) plus optional threshold-based fail-fast.

