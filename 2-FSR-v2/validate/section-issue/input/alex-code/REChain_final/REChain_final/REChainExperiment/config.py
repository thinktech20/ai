"""Unified configuration for the active REChain extracted runtime."""

from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from databricks import sql


def _first_non_empty(*values: Optional[str]) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _normalize_host(value: str) -> str:
    host = value.strip()
    if host.startswith("https://"):
        host = host[len("https://") :]
    elif host.startswith("http://"):
        host = host[len("http://") :]
    return host.rstrip("/")


def _read_secret_file(*paths: Path) -> str:
    for path in paths:
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except OSError:
            continue
    return ""


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
    except OSError:
        pass


def require_setting(
    value: str,
    *,
    name: str,
    env_names: tuple[str, ...],
    file_names: tuple[str, ...] = (),
) -> str:
    cleaned = (value or "").strip()
    if cleaned:
        return cleaned

    hints: list[str] = []
    if env_names:
        hints.append(f"environment or .env ({', '.join(env_names)})")
    if file_names:
        hints.append(f"local secret file ({', '.join(file_names)})")
    suffix = " or ".join(hints) if hints else "the local environment"
    raise RuntimeError(f"Missing {name}. Configure it via {suffix}.")


# -- Directory layout -------------------------------------------------

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
CONFIG_SEARCH_DIRS = [PROJECT_DIR]
for _candidate_dir in list(PROJECT_DIR.parents)[:2]:
    if _candidate_dir not in CONFIG_SEARCH_DIRS:
        CONFIG_SEARCH_DIRS.append(_candidate_dir)

for _dotenv_path in [directory / ".env" for directory in CONFIG_SEARCH_DIRS]:
    _load_dotenv_file(_dotenv_path)

OUTPUT_SUBDIR = _first_non_empty(
    os.getenv("RE_CHAIN_OUTPUT_SUBDIR"),
    "output/10unitSL-chunk20-run1-ervs",
).strip("/\\")
OUTPUT_DIR = PACKAGE_DIR / OUTPUT_SUBDIR

_DATABRICKS_TOKEN_FILES = (
    *(directory / "dbr_token.txt" for directory in CONFIG_SEARCH_DIRS),
)
_LITELLM_TOKEN_FILES = (
    *(directory / "litellm_token.txt" for directory in CONFIG_SEARCH_DIRS),
)

# -- Databricks SQL --------------------------------------------------

DB_HOST = _normalize_host(
    _first_non_empty(
        os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        os.getenv("DB_HOST"),
        os.getenv("DATABRICKS_HOST"),
        "gevernova-ai-dev-dbr.cloud.databricks.com",
    )
)
DB_HTTP_PATH = os.getenv("DATABRICKS_SQL_HTTP_PATH", "/sql/1.0/warehouses/c383216f6af5c7c0")
DB_TOKEN = _first_non_empty(
    os.getenv("DB_TOKEN"),
    os.getenv("DATABRICKS_TOKEN"),
    _read_secret_file(*_DATABRICKS_TOKEN_FILES),
)

HEATMAP_VIEW = "vgpd.fsr_std_views.fsr_unit_risk_matrix_view"
IBAT_EQUIPMENT_VIEW = "vgpd.prm_std_views.IBAT_EQUIPMENT_MST"
IBAT_PLANT_VIEW = "vgpd.prm_std_views.IBAT_PLANT_MST"
IBAT_TRAIN_VIEW = "vgpd.prm_std_views.ibat_train_mst"
ER_TABLE = "vgpp.qlt_std_views.u_pac"
FSR_CHUNK_TABLE = os.getenv(
    "FSR_CHUNK_TABLE",
    "main.gp_services_sdg_poc.field_service_report_gt_litellm",
)
FSR_PDF_REF_VIEW = os.getenv(
    "FSR_PDF_REF_VIEW",
    "vgpd.fsr_std_views.fsr_pdf_ref",
)
FSR_SCRAPED_MAPPING_VIEW = os.getenv(
    "FSR_SCRAPED_MAPPING_VIEW",
    "vgpd.fsr_std_views.fsr_scraped_file_mapping_ref",
)
FSR_REPORT_VIEW = os.getenv(
    "FSR_REPORT_VIEW",
    "vgpd.fsr_std_views.fsr_field_vision_field_services_report_psot",
)

# -- Databricks Vector Search (FSR) ---------------------------------

VS_WORKSPACE_URL = os.getenv(
    "DATABRICKS_HOST",
    f"https://{DB_HOST}",
).rstrip("/")
VS_TOKEN = _first_non_empty(
    os.getenv("VS_TOKEN"),
    os.getenv("DATABRICKS_TOKEN"),
    DB_TOKEN,
)
VS_INDEX_NAME = os.getenv(
    "VS_INDEX_NAME",
    "main.gp_services_sdg_poc.vs_field_service_report_gt_litellm",
)
VS_ENDPOINT_NAME = os.getenv(
    "VS_ENDPOINT_NAME",
    "pw-ser-sdg-vector-search",
)

# -- Databricks Vector Search (ER) ----------------------------------

ER_USE_VECTOR_SEARCH = True

ER_VS_INDEX_NAME = os.getenv(
    "ER_VS_INDEX_NAME",
    "main.gp_services_sdg_poc.vs_engineering_report_chunk_litellm"
)

# -- LiteLLM / LLM ---------------------------------------------------

LITELLM_HOST = os.getenv("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")
LITELLM_TOKEN = _first_non_empty(
    os.getenv("LITELLM_API_KEY"),
    _read_secret_file(*_LITELLM_TOKEN_FILES),
)
LLM_MODEL_NAME = os.getenv("RE_CHAIN_MODEL", "azure-gpt-5-2")
VECTOR_SEARCH_EMBEDDING_MODEL = os.getenv(
    "VECTOR_SEARCH_EMBEDDING_MODEL", "azure-text-embedding-3-large-1"
)
VECTOR_SEARCH_EMBEDDING_REQUEST_PATH = os.getenv(
    "VECTOR_SEARCH_EMBEDDING_REQUEST_PATH", "/v1/embeddings"
)
VECTOR_SEARCH_EMBEDDING_VERIFY_SSL = os.getenv(
    "VECTOR_SEARCH_EMBEDDING_VERIFY_SSL", "false"
).strip().lower() in {"1", "true", "t", "yes", "y", "on"}
VECTOR_SEARCH_EMBEDDING_DIMENSION = int(
    os.getenv("VECTOR_SEARCH_EMBEDDING_DIMENSION", "3072")
)

# -- ER Embedding ----------------------------------------------------

ER_EMBEDDING_HOST = LITELLM_HOST
ER_EMBEDDING_TOKEN = LITELLM_TOKEN
ER_EMBEDDING_MODEL = os.getenv("ER_EMBEDDING_MODEL", VECTOR_SEARCH_EMBEDDING_MODEL)
ER_EMBEDDING_VERIFY_SSL = VECTOR_SEARCH_EMBEDDING_VERIFY_SSL
ER_TOKEN_LIMIT = 4096
ER_OVERLAP_PCT = 10
ER_RETRIEVAL_K = 10
ER_SERIALS = (
    "290T434",
    "290T484",
    "290T503",
    "290T530",
    "290T532",
    "290T543",
    "290T762",
    "337X045",
    "337X330",
    "337X336",
)

# -- Retrieval K (top-k results) ------------------------------------

ER_K = int(_first_non_empty(os.getenv("RE_CHAIN_ER_K"), "20"))
FSR_K = int(_first_non_empty(os.getenv("RE_CHAIN_FSR_K"), "20"))



import time as _time


def get_db_connection(max_retries: int = 3):
    token = require_setting(
        DB_TOKEN,
        name="Databricks SQL token",
        env_names=("DB_TOKEN", "DATABRICKS_TOKEN"),
        file_names=("dbr_token.txt",),
    )
    for attempt in range(1, max_retries + 1):
        try:
            return sql.connect(
                server_hostname=DB_HOST,
                http_path=DB_HTTP_PATH,
                access_token=token,
            )
        except Exception as e:
            if attempt < max_retries:
                wait = 3 * attempt
                print(f"[DB] Connection failed (attempt {attempt}/{max_retries}), retry in {wait}s: {e}")
                _time.sleep(wait)
            else:
                print(f"[DB] Connection failed after {max_retries} attempts: {e}")
                raise


# -- Environment helpers ---------------------------------------------

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def split_csv_arg(raw: Optional[str]) -> Optional[list[str]]:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    items = [p for p in parts if p]
    return items or None


# -- Utilities -------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")


def clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip() if isinstance(value, str) else str(value).strip()


def normalize_issue_name(value: Any) -> str:
    text = clean_scalar(value).replace("\r", " ").replace("\n", " ")
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


# -- Run configuration -----------------------------------------------

CERT_PATH = next(
    (
        directory / "GE_Enterprise_Root_CA_2_1.crt"
        for directory in CONFIG_SEARCH_DIRS
        if (directory / "GE_Enterprise_Root_CA_2_1.crt").exists()
    ),
    CONFIG_SEARCH_DIRS[0] / "GE_Enterprise_Root_CA_2_1.crt",
)


def _resolve_ssl_verify() -> str | bool:
    if CERT_PATH.exists():
        return str(CERT_PATH)
    return _env_bool("RE_CHAIN_VERIFY_SSL", True)


def ensure_ca_bundle() -> str:
    """Build a CA bundle for SDK-based HTTPS clients and export it via env vars."""
    cached = os.getenv("RE_CHAIN_CA_BUNDLE", "").strip()
    if cached and Path(cached).exists():
        return cached

    if not CERT_PATH.exists():
        return ""

    ge_cert = str(CERT_PATH)
    try:
        bundle_path = Path(tempfile.gettempdir()) / f"rechain_ca_{os.getpid()}.pem"
        if not bundle_path.exists():
            system_bundle = ""
            try:
                import certifi  # type: ignore

                system_bundle = certifi.where()
            except Exception:
                system_bundle = ""

            if system_bundle and Path(system_bundle).exists():
                shutil.copy2(system_bundle, bundle_path)
            else:
                bundle_path.write_bytes(b"")

            with bundle_path.open("a", encoding="utf-8") as handle:
                handle.write("\n")
                handle.write(Path(ge_cert).read_text(encoding="utf-8"))

        bundle = str(bundle_path)
    except Exception:
        bundle = ge_cert

    os.environ["REQUESTS_CA_BUNDLE"] = bundle
    os.environ["SSL_CERT_FILE"] = bundle
    os.environ["CURL_CA_BUNDLE"] = bundle
    os.environ["RE_CHAIN_CA_BUNDLE"] = bundle
    return bundle


@dataclass
class RunConfig:
    # LLM
    model_name: str = LLM_MODEL_NAME
    litellm_base_url: str = LITELLM_HOST
    temperature: float = float(os.getenv("RE_CHAIN_TEMPERATURE", "0.1"))
    request_timeout_sec: int = _env_int("RE_CHAIN_TIMEOUT_SEC", 30)
    request_path: str = os.getenv("RE_CHAIN_REQUEST_PATH", "/v1/chat/completions")

    # Chunk limits
    max_fsr_chunks: int = _env_int("RE_CHAIN_MAX_FSR_CHUNKS", 20)
    max_er_chunks: int = _env_int("RE_CHAIN_MAX_ER_CHUNKS", 20)
    max_chunk_chars: int = _env_int("RE_CHAIN_MAX_CHUNK_CHARS", 10000)

    # Batch control
    max_workers: int = _env_int("RE_CHAIN_MAX_WORKERS", 10)
    force_rerun: bool = _env_bool("RE_CHAIN_FORCE_RERUN", False)
    dry_run: bool = _env_bool("RE_CHAIN_DRY_RUN", False)
    serials: Optional[list[str]] = None
    issues: Optional[list[str]] = None
    max_serials: Optional[int] = None
    max_issues: Optional[int] = None

    # Paths
    output_csv: Path = OUTPUT_DIR / "re_chain_results.csv"
    system_prompt_path: Path = PACKAGE_DIR / "system_prompt.txt"

    # SSL / proxy
    verify_ssl: str | bool = field(default_factory=_resolve_ssl_verify)
    corp_proxy: str = os.getenv("CORP_PROXY", "").strip()
    secret_scope: str = os.getenv("DBR_SECRET_SCOPE", "fsr-pipeline")

    # Ground truth
    ground_truth_csv: Path = PACKAGE_DIR / "ground_truth.csv"

    def resolve_api_key(self) -> str:
        """Try local config first, then Databricks secrets if running in DBR."""
        if LITELLM_TOKEN:
            return LITELLM_TOKEN
        try:
            import importlib

            dbutils_module = importlib.import_module("pyspark.dbutils")
            sql_module = importlib.import_module("pyspark.sql")
            DBUtils = getattr(dbutils_module, "DBUtils")
            SparkSession = getattr(sql_module, "SparkSession")
            spark = SparkSession.builder.getOrCreate()
            dbutils = DBUtils(spark)
            val = dbutils.secrets.get(scope=self.secret_scope, key="LITELLM_API_KEY")
            if val:
                return val
        except Exception:
            pass
        return ""

    def ensure_output_dir(self) -> None:
        self.output_csv.parent.mkdir(parents=True, exist_ok=True)
