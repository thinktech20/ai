"""TIL table contracts.

This module centralizes physical table names and DDL column specs consumed by
jobs and DDL notebooks.
"""

from common.tils.til_config import (
	TIL_CHUNKS_TABLE,
	TIL_ELEMENTS_TABLE,
	TIL_EVALUATION_RESULTS_TABLE,
	TIL_METADATA_TABLE,
	TIL_PIPELINE_RUN_AUDIT_TABLE,
	TIL_PROFILE_TABLE,
	TIL_VALIDATION_RESULTS_TABLE,
)


TIL_METADATA_TABLE_DDL_COLS = """
	document_id STRING NOT NULL COMMENT 'Technical PK: unique per extraction',
	unique_key STRING NOT NULL COMMENT 'Content-based idempotency key (til_number + source_hash + stable attributes)',
	source_path STRING COMMENT 'PDF location (volume path, local, or legacy)',
	source_hash STRING COMMENT 'SHA1 of PDF bytes for change detection',
	pdf_file_hash STRING COMMENT 'MD5 of PDF binary for incremental detection (before parsing)',
	source_system STRING COMMENT 'Source system (e.g., Databricks volume, legacy archive)',
	requested_til_number STRING COMMENT 'User-requested TIL (if specific)',
	matched_til_number STRING COMMENT 'Actual TIL number matched in PDF',
	match_type STRING COMMENT 'exact or base (exact_til_number or base_til_latest_revision)',
	parser_method STRING COMMENT 'Method used (foundation, pdfplumber, auto)',
	parser_name STRING COMMENT 'Parser adapter name',
	parser_version STRING COMMENT 'Parser version',
	profile_found BOOLEAN COMMENT 'Whether LLM extraction succeeded',
	parsed_profile_json STRING COMMENT 'LLM-normalized profile JSON',
	raw_profile_json STRING COMMENT 'Raw profile JSON before normalization',
	content_hash STRING COMMENT 'MD5 of extracted profile JSON (after LLM) for incremental detection',
	extracted_document_method STRING COMMENT 'Method used for document extraction',
	extracted_text_char_count BIGINT COMMENT 'Total chars in extracted text',
	extracted_table_count INT COMMENT 'Number of tables extracted',
	extraction_confidence DOUBLE COMMENT 'Proxy extraction quality signal (0.0-1.0)',
	llm_model STRING COMMENT 'LLM model used for profile extraction (audit/benchmarking)',
	metadata_status STRING COMMENT 'pending | completed | pdf_not_found | llm_parse_failed | failed',
	metadata_retry_count INT DEFAULT 0 COMMENT 'Number of failed attempts',
	chunk_status STRING COMMENT 'pending | completed | failed',
	chunk_retry_count INT DEFAULT 0 COMMENT 'Number of failed chunk attempts',
	error_code STRING COMMENT 'Error code if metadata_status=failed',
	error_message STRING COMMENT 'Error details if metadata_status=failed',
	ingest_ts TIMESTAMP NOT NULL DEFAULT current_timestamp() COMMENT 'When row was inserted',
	metadata_processed_ts TIMESTAMP COMMENT 'When metadata extraction completed',
	chunk_processed_ts TIMESTAMP COMMENT 'When chunking completed',
	run_id STRING COMMENT 'Pipeline run ID for traceability'
"""

TIL_ELEMENTS_TABLE_DDL_COLS = """
	document_id STRING NOT NULL COMMENT 'FK to til_metadata',
	element_id STRING NOT NULL COMMENT 'Unique per document (table_1, table_2, etc)',
	element_type STRING COMMENT 'table | section | image_ocr | formula',
	element_text STRING COMMENT 'Raw extracted text or description',
	page_number INT COMMENT 'Page reference if available',
	bbox_json STRING COMMENT 'Optional bounding box coords as JSON',
	section_path STRING COMMENT 'Document section hierarchy (e.g., scope -> requirements)',
	source_method STRING COMMENT 'Extraction method that found this element',
	parser_version STRING COMMENT 'Parser version when element was extracted',
	run_id STRING COMMENT 'Pipeline run ID',
	processed_ts TIMESTAMP NOT NULL DEFAULT current_timestamp() COMMENT 'When extracted'
"""

TIL_CHUNKS_TABLE_DDL_COLS = """
	chunk_id STRING NOT NULL COMMENT 'Unique chunk PK',
	document_id STRING NOT NULL COMMENT 'FK to til_metadata',
	chunk_text STRING COMMENT 'Retrieval-ready chunk content',
	chunk_type STRING COMMENT 'full_section | excerpt | table | formula',
	section_path STRING COMMENT 'Document section hierarchy',
	page_span STRING COMMENT 'Page range (e.g., 1-3, 5)',
	chunk_index INT COMMENT 'Sequential index per document',
	chunker_name STRING COMMENT 'Chunker algorithm name',
	chunker_version STRING COMMENT 'Chunker version',
	chunker_strategy STRING COMMENT 'Strategy used (e.g., recursive_split, semantic)',
	embedding_model STRING COMMENT 'Embedding model name (e.g., text-embedding-3-small)',
	embedding_model_version STRING COMMENT 'Model version',
	embedding_vector ARRAY<DOUBLE> COMMENT 'Dense vector (typically 1536-dim for OpenAI)',
	validation_status STRING COMMENT 'pending | validated | invalid',
	source_path STRING COMMENT 'Original PDF path',
	source_hash STRING COMMENT 'Source PDF hash (for cache busting)',
	run_id STRING COMMENT 'Pipeline run ID',
	processed_ts TIMESTAMP NOT NULL DEFAULT current_timestamp() COMMENT 'When chunked and embedded'
"""

TIL_VALIDATION_RESULTS_TABLE_DDL_COLS = """
	validation_run_id STRING NOT NULL COMMENT 'Unique validation run ID',
	document_id STRING NOT NULL COMMENT 'FK to til_metadata',
	rule_name STRING COMMENT 'Rule identifier (e.g., extracted_title_present, completeness_check)',
	rule_category STRING COMMENT 'Rule type (extraction_quality | content_integrity | compliance)',
	status STRING COMMENT 'pass | review | fail',
	severity STRING COMMENT 'info | warning | error',
	metric_name STRING COMMENT 'Metric being validated',
	metric_value DOUBLE COMMENT 'Actual value observed',
	threshold_value DOUBLE COMMENT 'Expected threshold',
	detail_json STRING COMMENT 'Extra context as JSON',
	run_id STRING COMMENT 'Pipeline run ID',
	validated_ts TIMESTAMP NOT NULL DEFAULT current_timestamp() COMMENT 'When validation ran'
"""

TIL_EVALUATION_RESULTS_TABLE_DDL_COLS = """
	evaluation_run_id STRING NOT NULL COMMENT 'Unique evaluation run ID',
	dataset_slice STRING COMMENT 'Dataset used (curated_subset, full_corpus, canary_set)',
	document_id STRING NOT NULL COMMENT 'FK to til_metadata',
	stage_name STRING COMMENT 'process_1 | process_2 | end_to_end',
	method_name STRING COMMENT 'Method evaluated (foundation, pdfplumber, auto, etc)',
	method_version STRING COMMENT 'Method version',
	metric_group STRING COMMENT 'extraction_quality | chunking_quality | embedding_quality',
	metric_name STRING COMMENT 'Metric name (char_count, table_count, parse_success, etc)',
	metric_value DOUBLE COMMENT 'Metric value',
	metric_detail_json STRING COMMENT 'Extra diagnostic info as JSON',
	evaluator_version STRING COMMENT 'Evaluator code version',
	mlflow_run_id STRING COMMENT 'MLflow run ID for lineage',
	run_ts TIMESTAMP NOT NULL DEFAULT current_timestamp() COMMENT 'When evaluation ran'
"""

TIL_PIPELINE_RUN_AUDIT_TABLE_DDL_COLS = """
	pipeline_run_id STRING NOT NULL COMMENT 'Unique run identifier',
	job_name STRING NOT NULL COMMENT 'Job that created this run (e.g., til_metadata_extraction)',
	run_mode STRING COMMENT 'discovery | target | backfill | evaluation',
	input_scope STRING COMMENT 'Scope of work (e.g., 50 curated TILs, full corpus)',
	status STRING COMMENT 'in_progress | completed | failed',
	claimed_count INT COMMENT 'Documents claimed by this run',
	success_count INT COMMENT 'Successfully processed',
	failed_count INT COMMENT 'Failed (may retry)',
	skipped_count INT COMMENT 'Skipped (already done or excluded)',
	retry_count INT COMMENT 'Number of retries for failed docs',
	error_code STRING COMMENT 'Overall error code if status=failed',
	error_message STRING COMMENT 'Overall error details if status=failed',
	mlflow_run_id STRING COMMENT 'MLflow run ID for traceability',
	start_ts TIMESTAMP NOT NULL COMMENT 'When job started',
	end_ts TIMESTAMP COMMENT 'When job completed',
	duration_ms BIGINT COMMENT 'Total elapsed time in milliseconds'
"""

TIL_PROFILE_TABLE_DDL_COLS = """
	til_number STRING NOT NULL COMMENT 'TIL identifier or source filename when no identifier was found',
	til_base_number STRING COMMENT 'Base TIL number without revision suffix',
	til_revision_number STRING COMMENT 'TIL revision number',
	pdf_path STRING COMMENT 'Source PDF path',
	parsed_profile_json STRING COMMENT 'Normalized TIL profile extraction as JSON',
	extracted_doc_json STRING COMMENT 'Raw parser output and extraction diagnostics as JSON'
"""


__all__ = [
	"TIL_METADATA_TABLE",
	"TIL_ELEMENTS_TABLE",
	"TIL_CHUNKS_TABLE",
	"TIL_VALIDATION_RESULTS_TABLE",
	"TIL_EVALUATION_RESULTS_TABLE",
	"TIL_PIPELINE_RUN_AUDIT_TABLE",
	"TIL_PROFILE_TABLE",
	"TIL_METADATA_TABLE_DDL_COLS",
	"TIL_ELEMENTS_TABLE_DDL_COLS",
	"TIL_CHUNKS_TABLE_DDL_COLS",
	"TIL_VALIDATION_RESULTS_TABLE_DDL_COLS",
	"TIL_EVALUATION_RESULTS_TABLE_DDL_COLS",
	"TIL_PIPELINE_RUN_AUDIT_TABLE_DDL_COLS",
	"TIL_PROFILE_TABLE_DDL_COLS",
]
