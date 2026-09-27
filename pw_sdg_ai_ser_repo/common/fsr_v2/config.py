# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# FSR V2 Pipeline — Shared Configuration
#
# Separate from fsr_config.py — covers v2-only tables, knobs, and model refs.
# All values are parameterized via env vars / Databricks widgets.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# ── Minimal runtime param helper (self-contained — no fsr_config dependency) ──
# P1/P2/P3 orchestrators that need v1 params (LITELLM, IBAT, etc.) must
# explicitly %run ../../../common/fsr_config before %run-ing this file.
import os as _os

def get_runtime_param(name: str, default: str = "") -> str:  # noqa: E302
    # Prefer widget values in notebook execution so ad-hoc/dev overrides are
    # honored even when clusters/jobs inject environment defaults.
    try:
        widget_val = dbutils.widgets.get(name)  # noqa: F821
        if widget_val is not None and str(widget_val).strip() != "":
            return str(widget_val).strip()
    except Exception:
        pass
    env_val = _os.getenv(name, "").strip()
    if env_val:
        return env_val
    return default

JB_ENV = get_runtime_param("jb_env", "").strip().lower()

# COMMAND ----------

# ── V2 Tables ────────────────────────────────────────────────────────────────

METADATA_TABLE_V2  = get_runtime_param("METADATA_TABLE_V2", "")
CHUNK_TABLE_V2     = get_runtime_param("CHUNK_TABLE_V2", "")
DOC_EQUIPMENT_MAP_TABLE_V2 = get_runtime_param("DOC_EQUIPMENT_MAP_TABLE_V2", "")
RUN_LOG_TABLE_V2   = get_runtime_param("RUN_LOG_TABLE_V2", "")
DQ_LOG_TABLE_V2    = get_runtime_param("DQ_LOG_TABLE_V2", "")
FSR_ATTACHMENT_EXECUTION_TABLE = get_runtime_param("FSR_ATTACHMENT_EXECUTION_TABLE", "")
VS_INDEX_V2        = get_runtime_param("VS_INDEX_V2", "")

# COMMAND ----------

# ── Pipeline knobs ────────────────────────────────────────────────────────────

# INPUT_MODE: volume_list (default, scans the configured FSR volume for PDFs)
# TODO: add more modes when known — e.g. csv_list (read PDF names from a CSV in volume)
INPUT_MODE         = get_runtime_param("INPUT_MODE", "volume_list")

# COMMAND ----------

# ── Vector Search (P3) ───────────────────────────────────────────────────────

VS_ENDPOINT_V2 = get_runtime_param("VS_ENDPOINT_V2", "pw-ser-sdg-vector-search")

# INDEX_MODE: create | sync
INDEX_MODE     = get_runtime_param("INDEX_MODE", "sync")

# COMMAND ----------

# ── Batch / concurrency (P2) ──────────────────────────────────────────────────
# Reuse existing P2 knobs from fsr_config (P2_BATCH_SIZE, P2_MAX_ITERATIONS, etc.)
# Add v2-specific overrides below if needed.

# COMMAND ----------

# ── DDL column definitions ────────────────────────────────────────────────────
#
# Changes vs fsr_metadata (v1):
#   RENAMED : esn               → primary_esn
#   RENAMED : equipment_type    → primary_equip_type
#   RENAMED : equipment_sys_id  → primary_equip_sys_id
#   RENAMED : equipment_class_code → primary_equip_class_code
#   NEW     : preprocessor_regions  (JSON char-offset regions for P2 chunk attribution)
#   NEW     : inactive_esns          (JSON array of ESNs not applicable this outage)
#   DROPPED : all_esns               (v1 fan-out artefact)
#   DROPPED : esn_detect_status      (v1 LLM ESN detection, not needed in v2)
#
# Changes vs fsr_chunks (v1):
#   NEW     : primary_equip_type  (top-level column for VS filtering, region-attributed)
#   RENAMED : esn                 → primary_esn (consistent with metadata table)
#   CHANGED : primary_esn         — now region-attributed (not fan-out), one row per chunk
#   CHANGED : metadata JSON       — region_primary_esn + region_primary_equip_type vary per chunk by region

# ── JSON field contracts (v2 canonical + serving) ────────────────────────────
#
# Why this section exists:
#   DDL stores JSON columns as STRING, but writers/readers need a stable contract.
#   These constants document the intended shape used by pipeline code.
#
# Where each contract is produced/consumed:
#   - preprocessor_regions: produced in silver/src/etl/fsr_v2/metadata_enrichment.py,
#       consumed in gold/src/etl/fsr_v2/chunking.py and retrieval helpers.
#   - inactive_esns: produced in silver/src/etl/fsr_v2/metadata_enrichment.py,
#       consumed in gold/src/etl/fsr_v2/chunking.py and serving map builder.
#   - chunk.metadata: produced in gold/src/etl/fsr_v2/chunking.py,
#       consumed by retrieval/diagnostic flows.

# Spark SQL schema literal for preprocessor_regions JSON parsing.
# Used directly in from_json(...) calls in chunking.py and retrieval helpers.
# Notebooks that cannot import this module at runtime must inline the string —
# keep any such inline strings in sync with this constant.
PREPROCESSOR_REGIONS_JSON_SPARK_SCHEMA = (
    "array<struct<"
    "start:bigint,"
    "end:bigint,"
    "metadata:struct<"
    "primary_esn:string,"
    "primary_equip_type:string,"
    "primary_technology_code:string,"
    "heading_confidence:string,"
    "heading_reason_codes:array<string>"
    ">"
    ">>"
)

# Python-level contract (serialized as JSON string in fsr_metadata_v2.preprocessor_regions)
PREPROCESSOR_REGIONS_JSON_CONTRACT = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["start", "end", "metadata"],
        "properties": {
            "start": "int",  # inclusive char offset
            "end": "int",  # exclusive char offset
            "metadata": {
                "type": "object",
                "properties": {
                    "primary_esn": "string",
                    "primary_equip_type": "string",
                    "primary_technology_code": "string (optional)",
                    "heading_confidence": "string (optional)",
                    "heading_reason_codes": "array[string] (optional)",
                },
            },
        },
    },
}

INACTIVE_ESNS_JSON_CONTRACT = {
    "type": "array",
    "items": "string (normalized ESN)",
    "notes": "Stored as JSON array string in fsr_metadata_v2.inactive_esns",
}

# Chunk-level metadata JSON contract.
# Stored as JSON string in fsr_chunks_v2.metadata and assembled in P2 chunking.
# First-class columns remain the VS/filter contract; the JSON region object
# preserves the complete P1 attribution provenance for retrieval and audit.
CHUNK_METADATA_JSON_CONTRACT_VERSION = "fsr_v2_chunk_metadata_v2"

# New/updated consumers should use namespaced fields:
#   - doc.*           -> document-level fields not promoted to chunk columns
#   - chunk_context.* -> chunk-only helper context not stored as top-level columns
CHUNK_METADATA_JSON_REQUIRED_KEYS = [
    "metadata_contract_version",
    "doc",
]

CHUNK_METADATA_JSON_OPTIONAL_KEYS = [
    "region",
    "section",
    "chunk_context",
]

CHUNK_METADATA_JSON_DOC_LEVEL_KEYS = [
    "title",
    "customer",
    "event_type",
    "ev_project_id",
    "ev_equipment_event_id",
    "ofs_event_id",
    "fsp_project_id",
    "xxx_project_id",
    "fsr_number",
    "report_issued_date",
    "outage_start_date",
    "outage_end_date",
    "outage_type",
    "technology_type",
    "inactive_esns",
]

CHUNK_METADATA_JSON_CHUNK_CONTEXT_KEYS = [
    "chunk_start_char",
]

CHUNK_METADATA_JSON_EXAMPLE = {
    "metadata_contract_version": "fsr_v2_chunk_metadata_v2",
    "doc": {
        "title": "Outage report",
        "customer": "site-a",
        "event_type": "Call-Out",
        "ev_project_id": "EV-123",
        "ev_equipment_event_id": "EV-456",
        "ofs_event_id": "OFS-789",
        "fsp_project_id": "FSP-101",
        "xxx_project_id": "",
        "fsr_number": "FSR-001",
        "report_issued_date": "2026-07-18",
        "outage_start_date": "2026-07-01",
        "outage_end_date": "2026-07-05",
        "outage_type": "Planned",
        "technology_type": "GT",
        "inactive_esns": ["ABC123"],
    },
    "region": {
        "primary_esn": "337X581",
        "primary_equip_type": "Generator",
        "esn_confidence": "high",
        "esn_source": "parent_inherit",
        "equip_type_source": "heading",
        "region_source": "section_span",
        "section_path": ["GENERATOR", "3 Generator"],
        "fallback_chain": ["local", "parent", "single_type", "ibat_train", "none"],
    },
    "section": {
        "section_title": "GENERATOR",
    },
    "chunk_context": {
        "chunk_start_char": 18240,
    },
}

METADATA_TABLE_V2_DDL_COLS = """
    document_id             STRING      NOT NULL    COMMENT 'Normalized UUID stem from volume path — primary key',
    pdf_name                STRING                  COMMENT 'Human-readable PDF name',
    volume_path             STRING      NOT NULL    COMMENT 'Full /Volumes/... path to the source PDF',
    title                   STRING                  COMMENT 'Report title extracted from the PDF',
    customer                STRING                  COMMENT 'Customer / site name',
    primary_esn             STRING                  COMMENT 'Primary ESN — doc-level, resolved via preprocessor + enrichment. Used for IBAT/Event Vision lookup.',
    primary_equip_type      STRING                  COMMENT 'Primary equipment type (e.g. Generator, Gas Turbine) — doc-level for primary ESN only',
    gt_esn                  STRING                  COMMENT 'Doc-level Gas Turbine ESN anchor emitted by preprocessor (non-exhaustive if multiple GT ESNs exist)',
    gen_esn                 STRING                  COMMENT 'Doc-level Generator ESN anchor emitted by preprocessor (non-exhaustive if multiple Generator ESNs exist)',
    st_esn                  STRING                  COMMENT 'Doc-level Steam Turbine ESN anchor emitted by preprocessor (non-exhaustive if multiple ST ESNs exist)',
    primary_equip_sys_id    STRING                  COMMENT 'Equipment system ID from IBAT — primary ESN only. TODO: extend to per-ESN lookup for secondary ESNs.',
    primary_equip_class_code STRING                 COMMENT 'Equipment sub-class / code from IBAT — primary ESN only. TODO: extend to per-ESN lookup for secondary ESNs.',
    event_type              STRING                  COMMENT 'Event type (e.g. Call-Out, Inspection)',
    ev_project_id           STRING                  COMMENT 'Event Vision project ID',
    ev_equipment_event_id   STRING                  COMMENT 'Event Vision equipment event ID',
    ofs_event_id            STRING                  COMMENT 'OFS event ID',
    fsp_project_id          STRING                  COMMENT 'FSP project ID',
    xxx_project_id          STRING                  COMMENT 'Additional project ID (pipe-separated if multiple)',
    fsr_number              STRING                  COMMENT 'FSR document number',
    report_issued_date      STRING                  COMMENT 'Date the FSR was issued — format: YYYY-MM-DD',
    outage_start_date       STRING                  COMMENT 'Outage start date — format: YYYY-MM-DD',
    outage_end_date         STRING                  COMMENT 'Outage end date — format: YYYY-MM-DD',
    job_start_date          STRING                  COMMENT 'Job start date from cover page — format: YYYY-MM-DD',
    approved_date           STRING                  COMMENT 'Approved date from cover page — format: YYYY-MM-DD',
    doc_date                STRING                  COMMENT 'Resolved canonical document date — first non-empty of outage_start_date > job_start_date > approved_date > report_issued_date.',
    doc_year                INT                     COMMENT 'Year derived from doc_date. Legacy date_filtered rows may contain a year captured by the retired page-1 probe.',
    doc_date_source         STRING                  COMMENT 'Which field doc_date/doc_year came from: outage_start_date | job_start_date | approved_date | report_issued_date | missing. Legacy rows may include a :page1_scan suffix.',
    outage_type             STRING                  COMMENT 'Outage type — resolved from PSOT table',
    technology_type         STRING                  COMMENT 'Technology type — resolved from PSOT table',
    prepared_by             STRING                  COMMENT 'Name of the person who prepared the report',
    approved_by             STRING                  COMMENT 'Name of the person who approved the report',
    document_summary        STRING                  COMMENT 'LLM-generated full-document summary',
    page_count              INT                     COMMENT 'Number of pages in the PDF',
    file_size_bytes         LONG                    COMMENT 'File size in bytes',
    file_last_modified      TIMESTAMP               COMMENT 'Last modified timestamp from volume listing',
    parsed_volume_path      STRING                  COMMENT 'Volume path to persisted parsed.json used by P1/P2 parse-once flow',
    parsed_parser_version   STRING                  COMMENT 'Parser version used to produce parsed_volume_path (e.g. pypdf2_v1.0, pymupdf_v1.0)',
    preprocessor_regions    STRING                  COMMENT 'JSON array of char-offset regions with per-region ESN + equip_type metadata — used by P2 for chunk attribution',
    inactive_esns           STRING                  COMMENT 'JSON array of ESNs marked inactive (not applicable this outage)',
    extractor_method        STRING                  COMMENT 'P1 text extraction method (e.g. pypdf2_v1.0) — experiment tracking',
    preprocess_method       STRING                  COMMENT 'P1 preprocessor version (e.g. preprocessor_v2_final) — experiment tracking',
    llm_model_extraction    STRING                  COMMENT 'P1 LLM model for doc-level field extraction (e.g. gpt-4-turbo, claude-3-sonnet) — experiment tracking',
    llm_extraction_prompt_version STRING             COMMENT 'P1 LLM prompt template version (e.g. v1, v2_with_hints) — experiment tracking',
    pipeline_version        STRING                  COMMENT 'Overall FSR v2 pipeline version (e.g. fsr_v2.0) — experiment tracking',
    run_id                  STRING                  COMMENT 'Unique run identifier (e.g. run_2026-07-18_exp_001) for grouping across documents in single run — experiment tracking',
    metadata_status         STRING      NOT NULL    COMMENT 'P1 status: pending / completed / failed. Legacy rows may be date_filtered until reclaimed.',
    metadata_error          STRING                  COMMENT 'Error message if P1 failed',
    metadata_retry_count    INT                     COMMENT 'Number of P1 attempts on this document',
    chunk_status            STRING      NOT NULL    COMMENT 'P2 status: pending / in_progress / completed / failed',
    chunk_error             STRING                  COMMENT 'Error message if P2 failed',
    chunk_retry_count       INT                     COMMENT 'Number of P2 attempts on this document',
    ingested_at             TIMESTAMP               COMMENT 'When this row was first created (file discovery)',
    scraped_at              TIMESTAMP               COMMENT 'When P1 last completed or failed',
    chunked_at              TIMESTAMP               COMMENT 'When P2 last completed or failed',
    updated_at              TIMESTAMP               COMMENT 'When any field was last modified (status, error, retry count, etc.)'
"""

DOC_EQUIPMENT_MAP_TABLE_V2_DDL_COLS = """
    document_id             STRING      NOT NULL    COMMENT 'FK to fsr_metadata_v2.document_id',
    esn                     STRING      NOT NULL    COMMENT 'Normalized ESN (uppercase, trimmed)',
    equip_type              STRING                  COMMENT 'Equipment type mapped for this ESN in the document',
    technology_code         STRING                  COMMENT 'Technology/frame code when available',
    is_primary_esn          BOOLEAN                 COMMENT 'True when esn == metadata_table.primary_esn for this document',
    is_active               BOOLEAN                 COMMENT 'False when ESN is in metadata_table.inactive_esns',
    source_region_count     INT                     COMMENT 'Number of preprocessor regions mapped to this (document_id, esn)',
    created_at              TIMESTAMP               COMMENT 'Row creation timestamp',
    updated_at              TIMESTAMP               COMMENT 'Row update timestamp'
"""

CHUNK_TABLE_V2_DDL_COLS = """
    chunk_id                STRING      NOT NULL    COMMENT 'Primary key — md5(document_id + "_" + chunk_index)',
    chunk_index             INT                     COMMENT 'Chunk position within document',
    document_id             STRING      NOT NULL    COMMENT 'FK to fsr_metadata_v2 — UUID filename stem of the source PDF',
    pdf_name                STRING                  COMMENT 'Human-readable PDF name',
    page_number             INT                     COMMENT 'Page number where this chunk originates',
    chunk_text              STRING      NOT NULL    COMMENT 'Plain text content of the chunk',
    region_primary_esn      STRING                  COMMENT 'ESN attributed to this chunk via preprocessor_regions (region-scoped for VS filtering)',
    region_primary_equip_type STRING                COMMENT 'Equipment type attributed to this chunk via preprocessor_regions (region-scoped for VS filtering)',
    active_esns             ARRAY<STRING>           COMMENT 'Sorted array of normalized active ESNs for this document — supports VS array-contains filtering',
    report_date             DATE                    COMMENT 'Report issued date (from report_issued_date)',
    outage_start_date       DATE                    COMMENT 'Outage start date — top-level column for VS date-range filtering',
    chunk_embedding         ARRAY<DOUBLE>           COMMENT 'Pre-computed embedding vector (3072 dimensions)',
    chunk_strategy          STRING                  COMMENT 'Fixed production behavior: region_first:recursive',
    embedding_model         STRING                  COMMENT 'Embedding model used (e.g. text-embedding-3-large, voyage-3) — experiment tracking',
    merge_strategy          STRING                  COMMENT 'Merge logic version (e.g. v2_4level_cascade) — experiment tracking',
    region_attribution_method STRING                 COMMENT 'Region attribution method (e.g. char_offset_max_overlap) — experiment tracking',
    embedding_dimension     INT                     COMMENT 'Actual embedding vector dimension (e.g. 3072 for text-embedding-3-large) — experiment tracking',
    pipeline_version        STRING                  COMMENT 'Overall FSR v2 pipeline version (e.g. fsr_v2.0) — experiment tracking',
    run_id                  STRING                  COMMENT 'Unique run identifier (e.g. run_2026-07-18_exp_001) for grouping across documents in single run — experiment tracking',
    metadata                STRING                  COMMENT 'Contextual fields serialised as JSON — region_primary_esn + region_primary_equip_type vary per chunk based on region attribution',
    created_at              TIMESTAMP               COMMENT 'When this chunk row was written'
"""

RUN_LOG_TABLE_V2_DDL_COLS = """
    run_id                  STRING      NOT NULL    COMMENT 'Unique ID for this v2 pipeline run',
    job_name                STRING                  COMMENT 'Databricks job or notebook name',
    start_time              TIMESTAMP   NOT NULL    COMMENT 'When the run started',
    end_time                TIMESTAMP               COMMENT 'When the run finished',
    duration_seconds        DOUBLE                  COMMENT 'Wall-clock duration of the run',
    docs_claimed            INT                     COMMENT 'Number of docs discovered or claimed for processing',
    docs_succeeded          INT                     COMMENT 'Number of docs successfully processed',
    docs_failed             INT                     COMMENT 'Number of docs that failed',
    chunks_written          INT                     COMMENT 'Total chunk rows written in this run',
    p1_workers              INT                     COMMENT 'FSR_V2_P1_WORKERS used for this run — serverless does not return driver stdout, so concurrency settings are only verifiable from here',
    llm_batch_count         INT                     COMMENT 'Number of LLM batches issued by P1 in this run',
    docs_date_filtered      INT                     COMMENT 'Legacy date-filter metric; zero for runs after the year filter was retired',
    error_summary           STRING                  COMMENT 'Aggregated error summary if any failures',
    created_at              TIMESTAMP               COMMENT 'When this log row was written'
"""

DQ_LOG_TABLE_V2_DDL_COLS = """
    dq_id                   STRING      NOT NULL    COMMENT 'Unique ID for this finding (md5 of run_id + document_id + check_name)',
    run_id                  STRING                  COMMENT 'Pipeline run ID that produced this finding',
    document_id             STRING                  COMMENT 'Document with the issue (NULL for global checks)',
    pdf_name                STRING                  COMMENT 'Human-readable PDF name or source file name',
    check_name              STRING      NOT NULL    COMMENT 'Name of the validation or pipeline check',
    severity                STRING      NOT NULL    COMMENT 'FAIL or WARN',
    failure_category        STRING                  COMMENT 'Routing hint for failure class; open enum for v2 operations',
    detail                  STRING                  COMMENT 'Description of the issue',
    created_at              TIMESTAMP               COMMENT 'When this finding was logged'
"""


FSR_ATTACHMENT_EXECUTION_TABLE_DDL_COLS = """
    pdf_name                     STRING     COMMENT 'The name of the uploaded PDF file, used to identify and track specific attachments.',
    upload_date                  TIMESTAMP  COMMENT 'The date and time when the file was uploaded, marking the beginning of the processing pipeline.',
    dag_run_id                   STRING     COMMENT 'A unique identifier for the DAG run that processed the attachment, useful for tracing and debugging.',
    esn                          STRING     COMMENT 'The equipment serial number associated with the uploaded file, providing context for the attachment''s origin.',
    uploaded_by                  STRING     COMMENT 'The user or entity responsible for uploading the file, helping to track accountability and access.',
    ingestion_refresh_timestamp  TIMESTAMP  COMMENT 'The timestamp when the ingestion stage was last refreshed, indicating the progress and update time for this stage.',
    chunking_refresh_timestamp   TIMESTAMP  COMMENT 'The timestamp when the chunking stage was last refreshed, showing when this specific processing step was updated.',
    embedding_refresh_timestamp  TIMESTAMP  COMMENT 'The timestamp when the embedding stage was last refreshed, highlighting the completion or update time for this particular stage.',
    last_stage_processed_at      TIMESTAMP  COMMENT 'The timestamp of the last stage that was successfully processed, providing insight into the attachment''s processing history and current state.',
    current_stage                STRING     COMMENT 'The current processing stage of the attachment, indicating where in the pipeline it is currently being worked on.',
    status                       STRING     COMMENT 'The overall status of the attachment''s processing, such as pending, in progress, completed, or failed, giving a quick overview of its state.',
    timeline_metadata            STRING     COMMENT 'Additional metadata capturing key events and milestones in the processing timeline of the attachment, useful for detailed analysis and auditing.'
"""


def dq_log_schema_v2():
    from pyspark.sql.types import StructField, StringType, StructType, TimestampType

    return StructType([
        StructField("dq_id", StringType(), False),
        StructField("run_id", StringType(), True),
        StructField("document_id", StringType(), True),
        StructField("pdf_name", StringType(), True),
        StructField("check_name", StringType(), False),
        StructField("severity", StringType(), False),
        StructField("failure_category", StringType(), True),
        StructField("detail", StringType(), True),
        StructField("created_at", TimestampType(), True),
    ])
