# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# SDG Shared Utilities
#
# Common helper functions used across all SDG ingestion pipelines (FSR, ER,
# Heatmap). Loaded via: %run ../../../common/sdg_common_utils
#
# Functions extracted from fsr_config.py (DRY) — pipelines should import
# their pipeline-specific config (fsr_config, er_config, heatmap_config)
# which in turn uses these helpers.
# ─────────────────────────────────────────────────────────────────────────────
import os
import re
import base64
from typing import List, Optional


# ─── Runtime Parameter Helpers ───────────────────────────────────────────────

def get_runtime_param(name: str, default: str = "") -> str:
    """Read a runtime setting from env var → Databricks widget → default."""
    env_val = os.getenv(name, "").strip()
    if env_val:
        return env_val
    try:
        widget_val = dbutils.widgets.get(name)  # noqa: F821
        if widget_val is not None and str(widget_val).strip() != "":
            return str(widget_val).strip()
    except Exception:
        pass
    return default


def get_runtime_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean runtime parameter."""
    raw = get_runtime_param(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "t", "yes", "y", "on")


def parse_runtime_list(name: str) -> Optional[List[str]]:
    """Parse a comma/newline/semicolon-delimited runtime parameter into a list."""
    raw = get_runtime_param(name, "")
    if not raw:
        return None
    values = [part.strip() for part in re.split(r"[,;\n]", raw) if part.strip()]
    return values or None


# ─── Secret Access ───────────────────────────────────────────────────────────

def get_secret(scope: str, key: str, env_fallback: str = "") -> str:
    """Try Databricks secret scope, then widget (job param), then env var."""
    try:
        val = dbutils.secrets.get(scope=scope, key=key)  # noqa: F821
        if val:
            return val
    except Exception:
        pass
    try:
        widget_val = dbutils.widgets.get(key)  # noqa: F821
        if widget_val is not None and str(widget_val).strip() != "":
            return str(widget_val).strip()
    except Exception:
        pass
    return os.getenv(key, env_fallback)


def decode_maybe_base64(value: str) -> str:
    """Decode base64-encoded secrets if accidentally stored encoded."""
    text = (value or "").strip()
    if not text:
        return text
    if text.startswith("sk-") or text.lower().startswith(("http://", "https://")):
        return text
    try:
        decoded = base64.b64decode(text).decode("utf-8").strip()
        if decoded:
            return decoded
    except Exception:
        pass
    return text


# ─── Spark Session Recovery ──────────────────────────────────────────────────

def ensure_spark_session():
    """Re-establish the Spark Connect session if it has expired (serverless).

    On Databricks serverless compute, the Spark Connect session can expire due
    to INACTIVITY_TIMEOUT during long non-Spark phases (e.g. embedding HTTP
    calls).  This function attempts a lightweight Spark operation and, on
    failure, rebuilds the session via DatabricksSession.builder.getOrCreate().

    Call this before any Spark-dependent code that follows a long non-Spark gap.
    """
    _log = __import__("logging").getLogger("sdg.spark")
    # noinspection PyUnresolvedReferences
    global spark  # noqa: F811 — Databricks injects `spark` at notebook scope
    try:
        spark.sql("SELECT 1")
    except Exception:
        _log.warning("Spark Connect session expired — rebuilding session")
        try:
            from databricks.connect import DatabricksSession
            spark = DatabricksSession.builder.getOrCreate()
            _log.info("Spark session recovered via DatabricksSession.builder.getOrCreate()")
        except ImportError:
            from pyspark.sql import SparkSession
            spark = SparkSession.builder.getOrCreate()
            _log.info("Spark session recovered via SparkSession.builder.getOrCreate()")


# ─── Databricks Auth ─────────────────────────────────────────────────────────

def get_dbr_auth():
    """Return (workspace_url, token) for Databricks REST API calls.

    Workspace URL is auto-detected from Spark config; token is read from
    the notebook context.  Falls back to env vars for local testing.
    """
    try:
        from pyspark.sql import SparkSession
        spark = SparkSession.builder.getOrCreate()
        ws_host = spark.conf.get("spark.databricks.workspaceUrl")
        ws_url = f"https://{ws_host}"
    except Exception:
        ws_url = os.getenv("DATABRICKS_HOST", "https://gevernova-ai-dev-dbr.cloud.databricks.com")
    token = None
    try:
        token = (dbutils.notebook.entry_point  # noqa: F821
                 .getDbutils().notebook().getContext()
                 .apiToken().get())
    except Exception:
        token = os.getenv("DATABRICKS_TOKEN", "")
    return ws_url, token or ""


# ─── Embedding via LiteLLM Gateway ──────────────────────────────────────────

def _build_request_url(base_url: str, request_path: str) -> str:
    """Build a stable embedding endpoint URL from a base URL + request path."""
    base = base_url.rstrip("/")
    path = (request_path or "/v1/embeddings").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    if base.endswith("/v1") and path.startswith("/v1/"):
        path = path[3:]
    return base + path

def _make_session(verify_ssl, headers: dict) -> "requests.Session":
    import requests
    s = requests.Session()
    s.trust_env = False
    s.verify = verify_ssl
    s.headers.update(headers)
    return s


def embed_texts_batch(
    texts: list,
    *,
    base_url: str,
    api_key: str,
    model: str,
    dimension: int = 3072,
    request_path: str = "/v1/embeddings",
    verify_ssl=False,
    max_retries: int = 3,
    retry_backoff: float = 2.0,
    request_timeout: float = 120.0,
    max_input_chars: int = 24_000,
) -> list:
    """Call LiteLLM /embeddings endpoint and return list of embedding vectors.

    Uses requests with trust_env=False to bypass corporate proxy.
    Shared by all pipelines (FSR P2, ER, Heatmap).

    Safety: texts longer than *max_input_chars* (default 24 000 ≈ ~8 000 tokens
    at ~3 chars/token for technical text) are truncated before sending to stay
    within the model's 8 192-token input limit.

    CDN resilience: the gateway reverse proxy intermittently routes /v1/embeddings
    to a Langfuse Next.js frontend (HTML 404). The bad route is sticky to a
    keep-alive TCP connection. Recovery: close the socket and reconnect on each
    CDN 404 — a new connection gets a fresh routing decision. If inner retries
    are exhausted, sleep 60s to outlast the gateway routing TTL (~300s).
    Non-CDN errors (auth, server errors, network) raise immediately.
    """
    import time
    import urllib3

    _log = __import__("logging").getLogger("sdg.embed")

    # ── Safety truncation ────────────────────────────────────────────────
    if max_input_chars and max_input_chars > 0:
        for i, t in enumerate(texts):
            if len(t) > max_input_chars:
                _log.warning(
                    f"Truncating input[{i}] from {len(t)} to {max_input_chars} chars "
                    f"to stay within model token limit"
                )
                texts[i] = t[:max_input_chars]

    url = _build_request_url(base_url.rstrip("/"), request_path)

    _CDN_MAX_OUTER = 5
    _CDN_OUTER_SLEEP = 60.0

    req_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
    }
    payload = {"model": model, "input": texts}
    if dimension and dimension != 3072:
        payload["dimensions"] = dimension

    if verify_ssl is False:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    session = _make_session(verify_ssl, req_headers)

    for outer in range(_CDN_MAX_OUTER + 1):
        if outer > 0:
            _log.warning(
                f"Gateway routing retry {outer}/{_CDN_MAX_OUTER}: "
                f"sleeping {_CDN_OUTER_SLEEP:.0f}s for routing to recover..."
            )
            time.sleep(_CDN_OUTER_SLEEP)
            session = _make_session(verify_ssl, req_headers)  # fresh socket after sleep

        for attempt in range(1, max_retries + 1):
            try:
                resp = session.post(url, json=payload, timeout=request_timeout)
                if resp.status_code == 404:
                    ct = resp.headers.get("Content-Type", "")
                    is_cdn_404 = "text/html" in ct or "nextjs" in resp.text[:300].lower()
                    if is_cdn_404:
                        _log.warning(
                            f"CDN/Next.js 404 on {url} (attempt {attempt}/{max_retries})"
                        )
                        # Drop bad TCP connection — new socket may route correctly
                        session.close()
                        session = _make_session(verify_ssl, req_headers)
                        if attempt < max_retries:
                            time.sleep(retry_backoff ** attempt)
                            continue
                        break  # inner retries exhausted → outer sleep
                    raise RuntimeError(f"HTTP 404 from {url}: {resp.text[:500]}")
                if resp.status_code == 429:
                    # Rate-limited — honour Retry-After header or default 30s
                    retry_after = int(resp.headers.get("Retry-After", "30"))
                    retry_after = min(retry_after, 120)  # cap at 2 min
                    _log.warning(
                        f"Rate-limited (429) on {url} (attempt {attempt}/{max_retries}) "
                        f"— sleeping {retry_after}s"
                    )
                    time.sleep(retry_after)
                    if attempt < max_retries:
                        continue
                    raise RuntimeError(f"HTTP 429 from {url} after {max_retries} retries: {resp.text[:500]}")
                if resp.status_code >= 400:
                    raise RuntimeError(f"HTTP {resp.status_code} from {url}: {resp.text[:500]}")
                data = resp.json()
                if "data" not in data or not isinstance(data["data"], list):
                    raise RuntimeError(
                        f"Unexpected embedding response structure from {url}: "
                        f"{str(data)[:500]}"
                    )
                return [item["embedding"] for item in data["data"]]
            except RuntimeError:
                raise
            except Exception as e:
                if attempt == max_retries:
                    raise RuntimeError(f"embed_texts_batch network error on {url}: {e}") from e
                time.sleep(retry_backoff ** attempt)

    raise RuntimeError(
        f"embed_texts_batch: gateway routing 404 on {url} did not recover after "
        f"{_CDN_MAX_OUTER} outer retries ({int(_CDN_MAX_OUTER * _CDN_OUTER_SLEEP)}s total). "
        "Gateway may be down."
    )


# ─── Vector Search Sync ─────────────────────────────────────────────────────

def trigger_vs_sync(
    workspace_url: str,
    token: str,
    endpoint_name: str,
    index_name: str,
) -> dict:
    """Trigger a Vector Search index sync via REST API."""
    import json as _json
    import ssl
    import urllib.request

    url = f"{workspace_url.rstrip('/')}/api/2.0/vector-search/indexes/{index_name}/sync"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:  # noqa: S310
        return _json.loads(resp.read())


def check_vs_index_status(
    workspace_url: str,
    token: str,
    index_name: str,
) -> dict:
    """Check Vector Search index status via REST API."""
    import json as _json
    import ssl
    import urllib.request

    url = f"{workspace_url.rstrip('/')}/api/2.0/vector-search/indexes/{index_name}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:  # noqa: S310
        return _json.loads(resp.read())
