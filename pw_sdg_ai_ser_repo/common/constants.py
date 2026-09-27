"""Pipeline process and stage constants.

Naming aligned with FSR pipeline for consistency:
- P1 (Process 1): Metadata extraction — parser + profile LLM normalization
- P2 (Process 2): Chunking + embedding — retrieval-ready vectors
- End-to-end: Full pipeline evaluation
"""

# Process names (match til_evaluation_results.stage_name domain)
PROCESS_1 = "process_1"  # Metadata extraction: parser + profile LLM
PROCESS_2 = "process_2"  # Chunking + embedding
END_TO_END = "end_to_end"  # Full RAG pipeline

# Metric groups
METRIC_GROUP_EXTRACTION = "extraction_quality"
METRIC_GROUP_CHUNKING = "chunking_quality"
METRIC_GROUP_EMBEDDING = "embedding_quality"
METRIC_GROUP_RETRIEVAL = "retrieval_quality"

# Evaluator metric names (proxy signals, no gold labels required)
METRIC_CHAR_COUNT = "char_count"
METRIC_WORD_COUNT = "word_count"
METRIC_REQUIRED_FIELD_HITS = "required_field_hits"
METRIC_TABLE_COUNT = "table_count"
METRIC_FORMULA_HITS = "formula_hits"
METRIC_NOISE_RATIO = "noise_ratio"
METRIC_LATENCY_S = "latency_s"
METRIC_PARSE_SUCCESS = "parse_success"
METRIC_FIELD_EXACT_MATCH = "field_exact_match"  # Gold label required
