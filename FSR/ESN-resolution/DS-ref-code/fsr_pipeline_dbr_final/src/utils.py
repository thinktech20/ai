"""
FSR Pipeline Utilities – Databricks
Logging, text helpers, and progress tracking.
Pickle / local-file helpers removed (replaced by Delta tables).
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import quote


# ============================================================================
# LOGGING
# Databricks captures stdout/stderr from all cells and driver logs,
# so a simple console handler is sufficient.
# ============================================================================

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:          # already configured – avoid duplicate handlers
        return logger
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(ch)
    return logger


# ============================================================================
# METADATA
# ============================================================================

def clean_metadata(metadata: Dict) -> Dict:
    """Strip None values and coerce non-primitives to str for Delta compatibility."""
    clean = {}
    for k, v in metadata.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


# ============================================================================
# TEXT / TOKEN HELPERS
# ============================================================================

def count_tokens(text: str) -> int:
    """Fast word-based token estimate (avoids tiktoken dependency)."""
    return max(1, int(len(text.split()) * 1.3))


# ============================================================================
# PROGRESS TRACKING
# ============================================================================

class ProgressTracker:
    def __init__(self, total: int, name: str = "Progress"):
        self.total = total
        self.completed = 0
        self.name = name
        self.start_time = datetime.now()
        self._line_active = False

    def update(self, n: int = 1):
        self.completed += n
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = (self.completed / elapsed * 60) if elapsed > 0 else 0
        pct  = (self.completed / self.total * 100) if self.total > 0 else 0
        print(
            f"\r{self.name}: {self.completed}/{self.total} ({pct:.1f}%) "
            f"@ {rate:.1f}/min",
            end="", flush=True,
        )
        self._line_active = True

    def close(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if self._line_active:
            print()
        print(f"{self.name}: completed in {elapsed:.1f}s")


# ============================================================================
# VOLUME VALIDATION
# ============================================================================

def _get_dbr_auth() -> Tuple[str, str]:
    """Return Databricks workspace URL and bearer token when available."""
    ws_url = os.getenv("DATABRICKS_HOST", "https://gevernova-ai-dev-dbr.cloud.databricks.com")
    env_token = os.getenv("DATABRICKS_TOKEN", "").strip()
    if env_token:
        return ws_url.rstrip("/"), env_token

    try:
        from pyspark.sql import SparkSession
        from pyspark.dbutils import DBUtils

        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)
        token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
        return ws_url.rstrip("/"), (token or "")
    except Exception:
        return ws_url.rstrip("/"), ""


def _discover_volume_pdfs_via_api(volume_path: str, ws_url: str, token: str) -> Tuple[List[Path], int]:
    """List top-level volume files through the Databricks Files API."""
    import requests

    encoded_path = quote(volume_path.lstrip("/"), safe="")
    base_url = f"{ws_url}/api/2.0/fs/directories/{encoded_path}"
    headers = {"Authorization": f"Bearer {token}"}

    discovered: List[Path] = []
    skipped_directories = 0
    next_page_token = ""

    while True:
        params = {"page_token": next_page_token} if next_page_token else None
        response = requests.get(base_url, headers=headers, params=params, timeout=60)
        if response.status_code == 404:
            raise FileNotFoundError(volume_path)
        response.raise_for_status()

        payload = response.json()
        for entry in payload.get("contents", []):
            if entry.get("is_directory"):
                skipped_directories += 1
                continue

            entry_path = entry.get("path") or f"{volume_path.rstrip('/')}/{entry.get('name', '')}"
            if entry_path.startswith("dbfs:"):
                entry_path = entry_path[5:]
            discovered.append(Path(entry_path))

        next_page_token = payload.get("next_page_token") or ""
        if not next_page_token:
            break

    return discovered, skipped_directories


def _discover_volume_pdfs_local(volume_path: str) -> Tuple[List[Path], int]:
    """List top-level files from a locally mounted directory."""
    discovered: List[Path] = []
    skipped_directories = 0

    with os.scandir(volume_path) as entries:
        for entry in entries:
            if entry.is_dir():
                skipped_directories += 1
                continue
            discovered.append(Path(entry.path))

    return discovered, skipped_directories

def discover_volume_pdfs(volume_path: Path | str) -> Tuple[List[Path], int]:
    """Discover top-level files in a configured source folder.

    We intentionally avoid recursive scans and header sniffing. On Databricks,
    prefer the Files API over FUSE-mounted pathlib iteration because large
    volume directories can be much slower through the local mount. The
    configured folder is treated as already curated: every top-level file is a
    PDF candidate and any nested subfolder must be listed explicitly in
    config.py.
    """
    volume_str = str(volume_path)
    ws_url, token = _get_dbr_auth()
    if volume_str.startswith("/Volumes/") and token:
        return _discover_volume_pdfs_via_api(volume_str, ws_url, token)

    return _discover_volume_pdfs_local(volume_str)


def validate_pdf_volume(volume_paths: List[str]) -> str:
    """Return the first volume path that contains discoverable files."""
    for vpath in volume_paths:
        try:
            pdfs, _ = discover_volume_pdfs(vpath)
        except FileNotFoundError:
            continue
        if pdfs:
            print(f"[OK] Found {len(pdfs)} files in {vpath}")
            return vpath
    print(f"[WARN] No PDFs found in configured volume paths: {volume_paths}")
    return ""


def collect_pdfs_from_volumes(volume_paths: List[str]) -> Tuple[List[Path], List[str], List[str]]:
    """Return merged PDFs from all configured volumes, skipping duplicate stems."""
    all_pdfs: List[Path] = []
    active_volumes: List[str] = []
    duplicate_doc_ids: List[str] = []
    seen_doc_ids = set()

    for vpath in volume_paths:
        scan_start = time.time()
        print(f"[INFO] Scanning source folder: {vpath}")

        try:
            volume_pdfs, skipped_directories = discover_volume_pdfs(vpath)
        except FileNotFoundError:
            print(f"[WARN] Volume path not found: {vpath}")
            continue
        except Exception as exc:
            print(f"[WARN] Failed to scan {vpath}: {exc}")
            continue

        if not volume_pdfs:
            print(f"[INFO] No PDFs found in {vpath} (elapsed={time.time() - scan_start:.1f}s)")
            continue

        active_volumes.append(vpath)
        details = []
        if skipped_directories:
            details.append(f"skipped_dirs={skipped_directories}")
        details.append(f"elapsed={time.time() - scan_start:.1f}s")
        suffix = f" ({', '.join(details)})" if details else ""
        print(f"[OK] Found {len(volume_pdfs)} files in {vpath}{suffix}")

        for pdf_path in volume_pdfs:
            doc_id = pdf_path.stem
            if doc_id in seen_doc_ids:
                duplicate_doc_ids.append(doc_id)
                continue

            seen_doc_ids.add(doc_id)
            all_pdfs.append(pdf_path)

    if not all_pdfs:
        print(f"[WARN] No PDFs found in configured volume paths: {volume_paths}")

    return all_pdfs, active_volumes, duplicate_doc_ids
