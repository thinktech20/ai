# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# Heatmap Issue-Prompt Embedding Pipeline — Configuration
#
# Runtime parameters for the Heatmap ingestion pipeline.
# Loaded via: %run ../../../common/heatmap_config
#
# Depends on: %run ../../../common/sdg_common_utils  (must be run first)
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %run ./sdg_common_utils

# COMMAND ----------

# ─── Source View ─────────────────────────────────────────────────────────────
# Risk matrix source — D&A/DBR team manages Box → Delta ingestion into
# vgpp.fsr_std_views.fsr_unit_risk_matrix_view.  Our pipeline reads from
# this view and embeds each issue_prompt.

HEATMAP_SOURCE_VIEW = get_runtime_param("HEATMAP_SOURCE_VIEW", "vgpp.fsr_std_views.fsr_unit_risk_matrix_view")

# ─── Target Table (Embeddings) ───────────────────────────────────────────────

HEATMAP_EMBEDDING_TABLE = get_runtime_param("HEATMAP_EMBEDDING_TABLE", "")

# ─── Secrets / LLM Gateway ──────────────────────────────────────────────────

HEATMAP_SECRET_SCOPE = get_runtime_param("HEATMAP_SECRET_SCOPE", "fsr-pipeline")

_runtime_base_url = get_runtime_param("HEATMAP_LITELLM_PROXY_URL", "")
_runtime_api_key = get_runtime_param("HEATMAP_LITELLM_API_KEY", "")

LITELLM_BASE_URL = decode_maybe_base64(
    _runtime_base_url
    or get_secret(HEATMAP_SECRET_SCOPE, "LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
)
LITELLM_API_KEY = decode_maybe_base64(
    _runtime_api_key or get_secret(HEATMAP_SECRET_SCOPE, "LITELLM_API_KEY", "")
)

# ─── Embedding Model ────────────────────────────────────────────────────────

EMBEDDING_MODEL = get_runtime_param("HEATMAP_LITELLM_MODEL", "azure-text-embedding-3-large-1")
EMBEDDING_DIMENSION = int(get_runtime_param("HEATMAP_EMBEDDING_DIMENSION", "3072"))
HEATMAP_EMBEDDING_REQUEST_PATH = get_runtime_param("HEATMAP_EMBEDDING_REQUEST_PATH", "/v1/embeddings")

_ssl_mode = get_runtime_param("HEATMAP_LLM_VERIFY_SSL", "false").strip()
if _ssl_mode.lower() in ("0", "false", "f", "no", "n", "off"):
    LLM_VERIFY_SSL = False
elif os.path.exists(_ssl_mode):
    LLM_VERIFY_SSL = _ssl_mode
else:
    LLM_VERIFY_SSL = True

# ─── Filters ─────────────────────────────────────────────────────────────────
# Optional runtime filters for subset processing.

HEATMAP_EQUIPMENT_TYPES = parse_runtime_list("HEATMAP_EQUIPMENT_TYPES")
HEATMAP_PERSONAS = parse_runtime_list("HEATMAP_PERSONAS")

# ─── Batch Tuning ────────────────────────────────────────────────────────────

HEATMAP_EMBEDDING_BATCH_SIZE = int(get_runtime_param("HEATMAP_EMBEDDING_BATCH_SIZE", "100"))
HEATMAP_MAX_RETRIES = int(get_runtime_param("HEATMAP_MAX_RETRIES", "3"))

FORCE_RESET = get_runtime_bool("FORCE_RESET", False)
FORCE_RESET_CONFIRM = get_runtime_bool("FORCE_RESET_CONFIRM", False)
if FORCE_RESET and not FORCE_RESET_CONFIRM:
    import logging as _lr
    _lr.getLogger("heatmap.config").warning(
        "FORCE_RESET=true but FORCE_RESET_CONFIRM=false — "
        "reset will NOT execute.  Set both to true to confirm."
    )
    FORCE_RESET = False

# ─── DDL ─────────────────────────────────────────────────────────────────────

HEATMAP_TABLE_DDL_COLS = """
    row_id                  STRING      NOT NULL    COMMENT 'Primary key — md5 of source row key columns',
    equipment_type          STRING                  COMMENT 'Equipment type from source view',
    persona                 STRING                  COMMENT 'Persona identifier (RE, OE, etc.)',
    issue_prompt            STRING      NOT NULL    COMMENT 'Issue prompt text that was embedded',
    issue_prompt_embedding  ARRAY<DOUBLE>           COMMENT 'Pre-computed embedding vector',
    metadata                STRING                  COMMENT 'All source columns serialised as JSON',
    created_at              TIMESTAMP               COMMENT 'When this row was written'
"""

# ─── Required Parameter Validation ───────────────────────────────────────────

_REQUIRED_PARAMS = {
    "HEATMAP_SOURCE_VIEW": HEATMAP_SOURCE_VIEW,
    "HEATMAP_EMBEDDING_TABLE": HEATMAP_EMBEDDING_TABLE,
}

_missing = [name for name, val in _REQUIRED_PARAMS.items() if not val]
if _missing:
    _msg = (
        f"MISSING REQUIRED HEATMAP JOB PARAMETERS: {', '.join(_missing)}\n"
        f"Set them in the workflow YAML or pass as job parameters."
    )
    raise ValueError(_msg)
