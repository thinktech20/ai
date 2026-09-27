# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# M&D (Monitoring & Diagnostics) Pipeline — Configuration
#
# Runtime parameters for the M&D ingestion pipeline.
# Loaded via: %run ../../../common/mnd_config
#
# Depends on: %run ../../../common/sdg_common_utils  (must be run first)
#
# Production parity with the data-science research notebook (E3_final.py):
#   - Source view, business filters, null proxies, drop list, handoff schema
#   - Boilerplate phrase list, system-email list, PII entities
#   - Chunking thresholds (256 / 512 / 200), embedding model + 3072 dim
#   - Hybrid VS index (dense + BM25)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ./sdg_common_utils

# COMMAND ----------

# ─── Source Table ─────────────────────────────────────────────────────────────
# M&D source of truth (read-only view).

MND_SOURCE_TABLE = get_runtime_param("MND_SOURCE_TABLE", "")

# ─── Environment ─────────────────────────────────────────────────────────────
# Used to guard destructive operations (e.g. FORCE_RESET blocked in prod).

JB_ENV = get_runtime_param("jb_env", "").strip().lower()

# ─── Target Table (Chunks + Embeddings) ──────────────────────────────────────

MND_CHUNK_TABLE = get_runtime_param("MND_CHUNK_TABLE", "")

# ─── Preprocessed Table (PII-redacted record-level data) ─────────────────────
# Written after Presidio + Flair redaction, before chunking.
# Mirrors df_presidio saved to mnd_presidio_cleaned in E3_final.py.
# Optional — if empty, the write step is skipped.

MND_PREPROCESSED_TABLE = get_runtime_param("MND_PREPROCESSED_TABLE", "")

# ─── Vector Search ───────────────────────────────────────────────────────────

MND_VS_ENDPOINT = get_runtime_param("MND_VS_ENDPOINT", "pw-ser-sdg-vector-search")
MND_VS_INDEX = get_runtime_param("MND_VS_INDEX", "")

# Hybrid (dense + BM25) is what the research notebook validated.
MND_VS_INDEX_TYPE = get_runtime_param("MND_VS_INDEX_TYPE", "HYBRID").upper()

# Databricks-managed embedding endpoint used by the VS index for query-time
# embedding (the index also accepts pre-computed vectors written to the
# `embedding` column).  Matches the research notebook configuration.
MND_VS_EMBEDDING_MODEL_ENDPOINT = get_runtime_param(
    "MND_VS_EMBEDDING_MODEL_ENDPOINT", "text-embedding-3-large"
)

# ─── Secrets / LLM Gateway ──────────────────────────────────────────────────

MND_SECRET_SCOPE = get_runtime_param("MND_SECRET_SCOPE", "mnd-pipeline")

_runtime_base_url = get_runtime_param("MND_LITELLM_PROXY_URL", "") \
    or get_runtime_param("LITELLM_BASE_URL", "")
_runtime_api_key = get_runtime_param("MND_LITELLM_API_KEY", "") \
    or get_runtime_param("LITELLM_API_KEY", "")

LITELLM_BASE_URL = decode_maybe_base64(
    _runtime_base_url
    or get_secret(MND_SECRET_SCOPE, "LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
)
LITELLM_API_KEY = decode_maybe_base64(
    _runtime_api_key or get_secret(MND_SECRET_SCOPE, "LITELLM_API_KEY", "")
)

# ─── Embedding Model ────────────────────────────────────────────────────────

EMBEDDING_MODEL = get_runtime_param("MND_LITELLM_MODEL", "azure-text-embedding-3-large-1")
EMBEDDING_DIMENSION = int(get_runtime_param("MND_EMBEDDING_DIMENSION", "3072"))
MND_EMBEDDING_REQUEST_PATH = get_runtime_param("MND_EMBEDDING_REQUEST_PATH", "/v1/embeddings")

_ssl_mode = get_runtime_param("MND_LLM_VERIFY_SSL", "false").strip()
if _ssl_mode.lower() in ("0", "false", "f", "no", "n", "off"):
    LLM_VERIFY_SSL = False
elif os.path.exists(_ssl_mode):
    LLM_VERIFY_SSL = _ssl_mode
else:
    LLM_VERIFY_SSL = True

# ─── Business Filters (research-notebook parity) ────────────────────────────
# Only records matching u_type AND u_resolution_category AND non-null/non-proxy
# u_ccap_alarm_name are eligible for ingestion.

_DEFAULT_U_TYPES = "Ops Center,Op Center- Trips,Ops Center-Internal Investigation"
MND_FILTER_U_TYPE = parse_runtime_list("MND_FILTER_U_TYPE") or [
    v.strip() for v in _DEFAULT_U_TYPES.split(",") if v.strip()
]

_DEFAULT_RESOLUTION_CATEGORIES = (
    "1. Prior to Continued Operation,"
    "2. At First Opportunity or Next Shutdown,"
    "3. At Next Planned Inspection or Outage,"
    "4. At Next Exposure to Affected System"
)
MND_FILTER_U_RESOLUTION_CATEGORY = parse_runtime_list(
    "MND_FILTER_U_RESOLUTION_CATEGORY"
) or [v.strip() for v in _DEFAULT_RESOLUTION_CATEGORIES.split(",") if v.strip()]

# Optional ESN scope filter — when set, restricts ingestion to these serials.
MND_SERIAL_NUMBERS = parse_runtime_list("MND_SERIAL_NUMBERS")

MND_CUTOFF_DATE = get_runtime_param("MND_CUTOFF_DATE", "")

# Safety limit: cap the number of source records per run (0 = unlimited).
MND_MAX_RECORDS = int(get_runtime_param("MND_MAX_RECORDS", "0"))

# ─── Null Proxies ───────────────────────────────────────────────────────────
# 15 string values that look like NULL but are stored as literals in the
# source.  Step 1 of preprocessing converts every occurrence to true NULL.

MND_NULL_PROXIES = [
    "", "-", "UNKNOWN", "null", "NULL", "N/A", "n/a",
    "na", "NA", "none", "None", "Not Yet Requested",
    "unknown", "Not Set", "not set",
]

# ─── Fields to Exclude ──────────────────────────────────────────────────────
# 46 source columns that EDA proved are empty / no-variation / unreliable /
# ETL-only.  Dropped in Step 2 of preprocessing.

MND_FIELDS_TO_EXCLUDE = [
    "approval_set", "due_date", "expected_start", "u_email_body",
    "work_end", "work_start", "old_number",
    "company", "cmdb_ci", "location_", "parent", "order_",
    "follow_up", "business_duration", "calendar_duration", "time_worked",
    "u_email_event", "u_email_subject_line", "u_reference",
    "u_supplier_name", "u_buddy_list", "u_case_contributors", "group_list",
    "sla_due", "approval", "activity_due", "u_mli_number",
    "u_drawing_part__", "u_follow_up_attempt", "u_problem",
    "urgency", "impact", "source", "sys_class_name", "contact_type",
    "upon_approval", "upon_reject", "u_component_failure",
    "u_supplier_recovery", "knowledge", "made_sla", "reassignment_count",
    "state", "last_updated_date", "approval_history",
]

# ─── Handoff Schema ─────────────────────────────────────────────────────────
# 32 columns that survive into the cleaned tabular layer (df_handoff).
# `sys_created_by` is read for record_origin derivation then dropped (PII).

MND_HANDOFF_FIELDS = [
    "number_", "u_serial_number", "u_status", "priority", "u_type",
    "u_section", "u_component", "u_resolution_category",
    "u_ccap_alarm_name", "assignment_group",
    "u_site_customer_name", "u_site_station_name", "u_equipment_name",
    "u_major_equipment_association",
    "u_speed_at_trip_event_clean", "u_load_at_trip_event_mw_clean",
    "sys_created_on", "opened_at", "closed_at", "u_resolution_date",
    "sys_mod_count_clean",
    "short_description", "description", "close_notes", "u_resolve_notes",
    "comments", "work_notes", "comments_and_work_notes",
    "active", "u_immediate_response_needed", "u_potential_safety_issue",
    "record_origin", "sys_created_by", "created_date",
]

# ─── Free-text Columns ──────────────────────────────────────────────────────
# 7 columns receive boilerplate removal, URL stripping and PII redaction.
MND_TEXT_COLS = [
    "short_description", "description",
    "u_resolve_notes", "close_notes",
    "comments", "work_notes", "comments_and_work_notes",
]

# 4 of those 7 are combined into `merged_free_text` for chunking.
MND_CHUNK_TEXT_FIELDS = [
    "comments_and_work_notes", "description", "close_notes", "u_resolve_notes",
]

# ─── Boilerplate Phrases ────────────────────────────────────────────────────
# 27 hand-curated system-generated template strings that carry no retrieval
# value.  Stripped from the 7 text columns before PII redaction.

MND_BOILERPLATE_PHRASES = [
    "(Case Notes (Comments Visible to All users)) reply from:",
    "(Case Notes (Comments Visible to All users))",
    "(Private Notepad (Comments NOT Visible to Unlicensed Submitters))",
    "- Conversion, GE (ge_conversion) (Private Notepad (Comments NOT Visible to Unlicensed Submitters))",
    "- Administrator, System (admin) (Comments)",
    "Further inputs will follow after feedback review on above given",
    "Further inputs will follow after feedback",
    "REFERENCE: SPECIFIC_DELIVERABLE: Return Unit to Service",
    "Return Unit to Service with 24 hrs. Determine Root Cause by Customer Want Date.",
    "Service with 24 hrs. Determine Root Cause by Customer Want Date.",
    "Determine Root Cause by Customer Want",
    "Request timed out.",
    "Link to Event Report -",
    "Local Time), Trip Counter -",
    "good quality and current timestamp",
    "so our emails get to your address book or safe sender list",
    "Be sure to add gepowerpac@service-now.com<mailto:gepowerpac@service-now.com> to your address book",
    "_TRIP PROFILE Information: NAME: GEPS trips LOCATION: ADDRESS: CITY, STATE, and COUNTRY: PHONE:",
    "CELL PHONE: BEEPER: EMAIL ADDRESS:",
    "Root Cause/Customer Interaction/Corrective Action: Customer Feedback:",
    "Interaction/Corrective Action: Customer Feedback: ***",
    "Action Type: External email Send to:",
    "Packets: Sent = 4, Received =",
    "32 bytes of data: Reply from",
    "Approximate round trip times in milli-seconds: Minimum =",
    "USING: eField Service LOGGED IN",
    "Speed at Trip Event(%): 100 Load at Trip Event(MW):",
    "[OPTIONAL_USER_NOTES]",
]

# URL pattern stripped after phrase removal.
MND_URL_PATTERN = r"(https?://|ftp://|www\.)\S+"

# ─── System Emails (PII pre-clean) ──────────────────────────────────────────
# Known non-personal service addresses removed BEFORE Presidio runs so they
# don't get tagged as personal EMAIL_ADDRESS.

MND_SYSTEM_EMAILS = [
    "gepowerpac@service-now.com",
    "gepowerpac@service-now.com<mailto:gepowerpac@service-now.com>",
    "no-reply@ge.com",
    "noreply@ge.com",
    "servicenow@ge.com",
    "donotreply@ge.com",
    "do-not-reply@ge.com",
    "notification@ge.com",
    "notifications@ge.com",
    "md.center@gevernova.com",
]

# ─── Presidio + Flair PII ───────────────────────────────────────────────────
# Entities redacted via Presidio (EMAIL_ADDRESS, PHONE_NUMBER) + Flair
# (PERSON, NER model `flair/ner-english-large`) + custom regex (SSO_ID =
# 9-digit token).  Each hit becomes `[REDACTED_<ENTITY>]`.

MND_PII_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "SSO_ID"]
MND_FLAIR_MODEL = get_runtime_param("MND_FLAIR_MODEL", "flair/ner-english-large")
MND_SSO_PATTERN = r"\b\d{9}\b"

# ─── Chunking Thresholds (research-validated) ───────────────────────────────
# Pipeline: timestamp-boundary split → merge < MIN → split > MAX → merge < TINY backward.

MND_CHUNK_MIN_TOKENS = int(get_runtime_param("MND_CHUNK_MIN_TOKENS", "256"))
MND_CHUNK_MAX_TOKENS = int(get_runtime_param("MND_CHUNK_MAX_TOKENS", "512"))
MND_CHUNK_TINY_TOKENS = int(get_runtime_param("MND_CHUNK_TINY_TOKENS", "200"))

# Timestamp boundary pattern (ServiceNow comment log header).
MND_CHUNK_TS_BOUNDARY = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - "

# ─── Run Log Table ──────────────────────────────────────────────────────────

MND_RUN_LOG_TABLE = get_runtime_param("MND_RUN_LOG_TABLE", "")

# ─── Failed Records Table ───────────────────────────────────────────────────

MND_FAILED_RECORDS_TABLE = get_runtime_param("MND_FAILED_RECORDS_TABLE", "")
MND_MAX_RECORD_ATTEMPTS = int(get_runtime_param("MND_MAX_RECORD_ATTEMPTS", "5"))

# ─── Backfill Audit Mode ────────────────────────────────────────────────────

MND_BACKFILL_AUDIT = get_runtime_bool("MND_BACKFILL_AUDIT", False)
MND_BACKFILL_RECORD_IDS = parse_runtime_list("MND_BACKFILL_RECORD_IDS")
MND_BACKFILL_DATE_FROM = get_runtime_param("MND_BACKFILL_DATE_FROM", "")
MND_BACKFILL_DATE_TO = get_runtime_param("MND_BACKFILL_DATE_TO", "")

# ─── Batch Tuning ───────────────────────────────────────────────────────────

MND_EMBEDDING_BATCH_SIZE = int(get_runtime_param("MND_EMBEDDING_BATCH_SIZE", "20"))
MND_EMBEDDING_CONCURRENCY = int(get_runtime_param("MND_EMBEDDING_CONCURRENCY", "4"))
MND_MAX_RETRIES = int(get_runtime_param("MND_MAX_RETRIES", "3"))

# Number of source cases per micro-batch (extract → preprocess → PII → chunk
# → embed → write).  Keeps driver memory bounded by batch size, not by the
# full extract volume.  Presidio + Flair are slow per-record, so small batches
# also yield more frequent watermark checkpoints.
MND_RECORD_BATCH_SIZE = int(get_runtime_param("MND_RECORD_BATCH_SIZE", "500"))

FORCE_RESET = get_runtime_bool("FORCE_RESET", False)
FORCE_RESET_CONFIRM = get_runtime_bool("FORCE_RESET_CONFIRM", False)
if FORCE_RESET and not FORCE_RESET_CONFIRM:
    import logging as _lr
    _lr.getLogger("mnd.config").warning(
        "FORCE_RESET=true but FORCE_RESET_CONFIRM=false — "
        "reset will NOT execute.  Set both to true to confirm."
    )
    FORCE_RESET = False

# ─── DDL ────────────────────────────────────────────────────────────────────

MND_RUN_LOG_DDL_COLS = """
    run_id              STRING      NOT NULL    COMMENT 'Primary key — uuid4 or timestamp-based run identifier',
    pipeline            STRING                  COMMENT 'Pipeline name — always mnd_ingestion',
    run_started_at      TIMESTAMP               COMMENT 'When this pipeline run started',
    run_completed_at    TIMESTAMP               COMMENT 'When this pipeline run completed',
    status              STRING                  COMMENT 'completed / failed / in_progress / backfill_audit',
    records_extracted   INT                     COMMENT 'Raw cases extracted from source',
    chunks_written      INT                     COMMENT 'Chunk rows written to chunk table',
    watermark_ts        STRING                  COMMENT 'MAX(sys_updated_on) of extracted records — used as floor on next run'
"""

# Preprocessed table — 30-column PII-redacted record-level schema.
# Matches the Excel schema verified against E3_final.py (mnd_preprocessed_data).
MND_PREPROCESSED_TABLE_DDL_COLS = """
    number_                        STRING      NOT NULL    COMMENT 'M&D case number — primary key',
    active                         STRING                  COMMENT 'Source active flag',
    assignment_group               STRING                  COMMENT 'Assignment group',
    close_notes                    STRING                  COMMENT 'Close notes (PII redacted)',
    closed_at                      TIMESTAMP               COMMENT 'Case closed timestamp',
    comments_and_work_notes        STRING                  COMMENT 'Combined comments + work notes (PII redacted)',
    description                    STRING                  COMMENT 'Case description (PII redacted)',
    opened_at                      TIMESTAMP               COMMENT 'Case opened timestamp',
    priority                       STRING                  COMMENT 'Priority',
    short_description              STRING                  COMMENT 'Case short description (PII redacted)',
    sys_created_on                 TIMESTAMP               COMMENT 'Source create timestamp',
    sys_mod_count                  INT                     COMMENT 'Source modification count',
    u_ccap_alarm_name              STRING                  COMMENT 'CCAP alarm name',
    u_component                    STRING                  COMMENT 'Component metadata',
    u_equipment_name               STRING                  COMMENT 'Equipment name',
    u_immediate_response_needed    STRING                  COMMENT 'Immediate response flag',
    u_load_at_trip_event_mw_       DOUBLE                  COMMENT 'Load at trip event (MW) — cleaned',
    u_potential_safety_issue       STRING                  COMMENT 'Safety issue flag',
    u_resolution_category          STRING                  COMMENT 'Resolution category',
    u_resolution_date              TIMESTAMP               COMMENT 'Resolution date',
    u_resolve_notes                STRING                  COMMENT 'Resolve notes (PII redacted)',
    u_section                      STRING                  COMMENT 'Section metadata',
    u_serial_number                STRING                  COMMENT 'Equipment serial number',
    u_site_customer_name           STRING                  COMMENT 'Customer name',
    u_site_station_name            STRING                  COMMENT 'Station name',
    u_speed_at_trip_event          DOUBLE                  COMMENT 'Speed at trip event — cleaned',
    u_status                       STRING                  COMMENT 'Authoritative status field',
    u_type                         STRING                  COMMENT 'Case type',
    record_origin                  STRING                  COMMENT 'migrated_supportcentral / native_servicenow',
    u_major_equipment_association  STRING                  COMMENT 'Major equipment association',
    created_at             TIMESTAMP               COMMENT 'Timestamp when this record was first inserted by the pipeline',
    updated_time                   TIMESTAMP               COMMENT 'Timestamp when this record was last updated by the pipeline'
"""

# Chunk table mirrors the columns produced by the data-science notebook's
# final write (vec_monitoring_diagnostics) so that downstream VS + retrieval code
# does not have to change.  All metadata columns are STRING because Vector
# Search rejects `void` types on creation.
MND_CHUNK_TABLE_DDL_COLS = """
    chunk_id                       STRING      NOT NULL    COMMENT 'Primary key — md5(mnd_case_number + "_" + source_field + "_" + chunk_index)',
    serial_number                  STRING                  COMMENT 'Equipment serial number — VS filter key',
    mnd_case_number                STRING                  COMMENT 'M&D case number from source (number_)',
    chunk_index                    INT                     COMMENT 'Chunk position within case',
    chunk_text                     STRING      NOT NULL    COMMENT 'Plain-text chunk content (post-PII redaction)',
    u_ccap_alarm_name              STRING                  COMMENT 'CCAP alarm name — VS filter key',
    u_component                    STRING                  COMMENT 'Component metadata',
    u_resolution_category          STRING                  COMMENT 'Resolution category — business filter',
    u_major_equipment_association  STRING                  COMMENT 'Major equipment association',
    created_at                     TIMESTAMP               COMMENT 'Case opened timestamp (opened_at from source)',
    embedding                      ARRAY<DOUBLE>           COMMENT 'Pre-computed embedding vector (3072-dim)',
    updated_time                   TIMESTAMP               COMMENT 'Timestamp when this chunk was last updated by the pipeline'
"""

MND_FAILED_RECORDS_DDL_COLS = """
    mnd_case_number     STRING      NOT NULL    COMMENT 'Primary key — M&D case number (source number_)',
    sys_updated_on      TIMESTAMP               COMMENT 'Source sys_updated_on at time of failure (used for retry extract)',
    first_failed_at     TIMESTAMP               COMMENT 'When this record first failed processing',
    last_attempted_at   TIMESTAMP               COMMENT 'Most recent retry attempt timestamp',
    attempts            INT                     COMMENT 'Number of failed attempts (record stops retrying at MND_MAX_RECORD_ATTEMPTS)',
    last_error          STRING                  COMMENT 'Truncated error message from the most recent failure',
    last_run_id         STRING                  COMMENT 'run_id of the most recent attempt — joins to mnd_run_log'
"""

# ─── Required Parameter Validation ──────────────────────────────────────────

_REQUIRED_PARAMS = {
    "MND_SOURCE_TABLE": MND_SOURCE_TABLE,
    "MND_CHUNK_TABLE": MND_CHUNK_TABLE,
}

_missing = [name for name, val in _REQUIRED_PARAMS.items() if not val]
if _missing:
    _msg = (
        f"MISSING REQUIRED MND JOB PARAMETERS: {', '.join(_missing)}\n"
        f"Set them in the workflow YAML or pass as job parameters."
    )
    raise ValueError(_msg)
