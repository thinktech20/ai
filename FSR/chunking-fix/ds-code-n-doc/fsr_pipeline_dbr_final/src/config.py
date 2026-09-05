"""
FSR Pipeline Configuration – Databricks DEV
Replaces local file paths with Unity Catalog volumes/tables.
Reads secrets from Databricks Secret Scope (falls back to env vars for local dev).
"""
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


PROJECT_DIR = Path(__file__).resolve().parent.parent
if load_dotenv is not None:
    load_dotenv(PROJECT_DIR / ".env", override=False)


# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================

def _is_databricks() -> bool:
    return (
        "DATABRICKS_RUNTIME_VERSION" in os.environ
        or "DB_HOME" in os.environ
        or os.path.exists("/databricks/python")
    )

IS_DATABRICKS = _is_databricks()


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse bool-ish env vars safely (true/1/yes/on => True)."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


# ============================================================================
# SECRETS  (Databricks Secret Scope → env var → hardcoded default)
# ============================================================================

def _get_secret(scope: str, key: str, env_fallback: str = "") -> str:
    """Try Databricks secret scope first, then OS env var, then default."""
    if IS_DATABRICKS:
        try:
            from pyspark.sql import SparkSession
            from pyspark.dbutils import DBUtils
            spark = SparkSession.builder.getOrCreate()
            dbutils = DBUtils(spark)
            val = dbutils.secrets.get(scope=scope, key=key)
            if val:
                return val
        except Exception:
            pass
    return os.getenv(key, env_fallback)


# Secret scope name – create once in Databricks UI:
#   databricks secrets create-scope fsr-pipeline
#   databricks secrets put-secret fsr-pipeline LITELLM_API_KEY --string-value <key>
SECRET_SCOPE = os.getenv("DBR_SECRET_SCOPE", "fsr-pipeline")

LITELLM_BASE_URL = _get_secret(
    SECRET_SCOPE, "LITELLM_BASE_URL",
    "https://dev-gateway.apps.gevernova.net/",
)
LITELLM_API_KEY = _get_secret(SECRET_SCOPE, "LITELLM_API_KEY", "")


# ============================================================================
# SSL / PROXY
# ============================================================================

# Look for the GE Enterprise CA cert regardless of environment.
# Inside Databricks the cert is uploaded alongside the src/ folder by deploy.py.
CERT_PATH: Optional[Path] = None
_cert = PROJECT_DIR / "GE_Enterprise_Root_CA_2_1.crt"
if _cert.exists():
    CERT_PATH = _cert
    os.environ.setdefault("SSL_CERT_FILE",      str(_cert))
    os.environ.setdefault("REQUESTS_CA_BUNDLE", str(_cert))
    os.environ.setdefault("CURL_CA_BUNDLE",     str(_cert))

CORP_PROXY = "" if IS_DATABRICKS else os.getenv("CORP_PROXY", "")
if CORP_PROXY:
    os.environ.setdefault("HTTP_PROXY",  CORP_PROXY)
    os.environ.setdefault("HTTPS_PROXY", CORP_PROXY)


# ============================================================================
# DATABRICKS CATALOG / VOLUME / TABLE PATHS
# ============================================================================

VIUD_CATALOG = "viud"
VAID_CATALOG = "vaid"
VGPD_CATALOG = "vgpd"

# PDF source volumes (read-only – no new volumes needed)
# Each configured path is scanned non-recursively.
# All top-level files are treated as PDF candidates, so nested folders must be
# listed explicitly here.
PDF_VOLUME_PATHS = [
    f"/Volumes/{VGPD_CATALOG}/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/",
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports",
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fieldvision/fv_field_service_report"
]

# Single Delta table holding chunk rows.
# Historical env var name retained for compatibility with existing jobs.
EMBEDDINGS_TABLE = os.getenv(
    "EMBEDDINGS_TABLE", "main.gp_services_sdg_poc.field_service_report"
)

# Reference table for ESN / report-date enrichment
# Join key: ref.s3_filename == our pdf_name (both are UUID stems)
FSR_REF_VIEW = "vgpd.fsr_std_views.fsr_pdf_ref"

# Databricks Vector Search
VS_ENDPOINT_NAME = os.getenv("VS_ENDPOINT_NAME", "pw-ser-sdg-vector-search")
VS_INDEX_NAME    = os.getenv(
    "VS_INDEX_NAME", "main.gp_services_sdg_poc.vs_field_service_report_gt_litellm"
)
VECTOR_SEARCH_EMBEDDING_MODEL = os.getenv(
    "VECTOR_SEARCH_EMBEDDING_MODEL", "azure-text-embedding-3-large-1"
)
VECTOR_SEARCH_EMBEDDING_REQUEST_PATH = os.getenv(
    "VECTOR_SEARCH_EMBEDDING_REQUEST_PATH", "/v1/embeddings"
)
_vector_verify_ssl_raw = os.getenv("VECTOR_SEARCH_EMBEDDING_VERIFY_SSL", "").strip().lower()
if _vector_verify_ssl_raw:
    VECTOR_SEARCH_EMBEDDING_VERIFY_SSL: str | bool = _vector_verify_ssl_raw in {
        "1", "true", "t", "yes", "y", "on"
    }
elif CERT_PATH is not None:
    VECTOR_SEARCH_EMBEDDING_VERIFY_SSL = str(CERT_PATH)
else:
    VECTOR_SEARCH_EMBEDDING_VERIFY_SSL = False

# Pipeline run-mode default (overridable at notebook/job submission time)
FORCE_RESET = _env_bool("FORCE_RESET", False)

_cpu_count = os.cpu_count() or 2
PDF_PROCESS_WORKERS = int(
    os.getenv(
        "FSR_PDF_PROCESS_WORKERS",
        str(max(1, min(8, _cpu_count - 1 if _cpu_count > 1 else 1))),
    )
)

# Driver-node temp dir (for any files that must live on disk during a run)
TEMP_DIR = Path(tempfile.gettempdir()) / "fsr_pipeline"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# CHUNKING PARAMETERS
# ============================================================================

@dataclass
class ChunkingConfig:
    chunk_size: int = 4000
    chunk_overlap: int = 200
    max_chunk_tokens: int = 4000
    max_chunk_chars: int = 20000
    max_depth: int = 5
    min_chunk_size: int = 100
    separator_patterns: List[str] = field(default_factory=lambda: [
        "\n## ", "\n### ", "\n#### ", "\n\n", "\n",
    ])
    preserve_structure: bool = True


chunking_config = ChunkingConfig()
# ============================================================================
# RETRIEVAL PARAMETERS  (native hybrid search — no custom weights needed)
# ============================================================================
# Databricks VS hybrid search uses internal RRF fusion.
# Scores are normalised 0–1; ~1.0 = both vector & keyword agree.

RETRIEVAL_NUM_RESULTS = 10    # default k for queries


# ============================================================================
# EXPERIMENT PARAMETERS  (kept for backward compat with experiments.py)
# ============================================================================

@dataclass
class ExperimentConfig:
    weight_configs: List[tuple] = field(default_factory=lambda: [
        (0.5, 0.5, "50/50 Hybrid — native Databricks VS"),
    ])
    sample_size: Optional[int] = None
    enable_timing: bool = True


experiment_config = ExperimentConfig()


# ============================================================================
# EVAL QUERIES
# ============================================================================

EVAL_QUERIES = [
    {"q": "vibration issues during startup",        "cat": "technical",  "kw": ["vibration", "startup"]},
    {"q": "bearing failure root cause",             "cat": "technical",  "kw": ["bearing", "failure"]},
    {"q": "inspection recommendations turbine",     "cat": "inspection", "kw": ["inspection", "turbine"]},
    {"q": "borescope findings compressor",          "cat": "inspection", "kw": ["borescope", "compressor"]},
    {"q": "combustion can cracks hot gas path",     "cat": "technical",  "kw": ["combustion", "cracks"]},
    {"q": "IGV bushing migration",                  "cat": "technical",  "kw": ["IGV", "bushing"]},
    {"q": "crossfire tube alignment issues",        "cat": "technical",  "kw": ["crossfire", "tube"]},
    {"q": "TBC spallation blade coating damage",    "cat": "technical",  "kw": ["TBC", "spallation"]},
    {"q": "FOD impact damage rotor",                "cat": "technical",  "kw": ["FOD", "impact"]},
    {"q": "stator vane rocking issues",             "cat": "technical",  "kw": ["stator", "vane"]},
]
