# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# FSR Scraping & Metadata Extraction Pipeline
# Scans PDF volumes, extracts fields, normalises via LLM, enriches from
# IBAT/Event Vision, and writes to vgpd.fsr_std_views.fsr_scraped_file_mapping_ref
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pdfplumber litellm openpyxl

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import os, sys, json, time, re, warnings, threading, collections, base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote
from queue import Queue, Empty

import requests
import urllib3
import pdfplumber
import litellm
import pandas as pd

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, monotonically_increasing_id, trim, concat, lit,
    upper, regexp_replace, current_timestamp,
)
from pyspark.sql.types import StringType

warnings.filterwarnings("ignore")
urllib3.disable_warnings()
spark = SparkSession.builder.getOrCreate()

print("[OK] imports ready")

# COMMAND ----------

# ── Configuration ────────────────────────────────────────────────────────────

def _get_runtime_param(name: str, default: str = "") -> str:
    """Read runtime setting from env or Databricks job parameter widget."""
    env_val = os.getenv(name, "").strip()
    if env_val:
        return env_val
    try:
        widget_val = dbutils.widgets.get(name)
        if widget_val is not None and str(widget_val).strip() != "":
            return str(widget_val).strip()
    except Exception:
        pass
    return default

VIUD_CATALOG = "viud"
VGPD_CATALOG = "vgpd"

PDF_VOLUME_PATHS = [
    f"/Volumes/{VGPD_CATALOG}/fsr_std_views/fsr_std_vol/FSR_After_2016/FSR_Databricks/",
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fsr_manual/manual_field_service_report/ecrt_reports",
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fsr_manual/manual_field_service_report/UAT_Files/",
    f"/Volumes/{VIUD_CATALOG}/ing_ud_fieldvision/fv_field_service_report",
]

OUTPUT_TABLE = _get_runtime_param("FSR_OUTPUT_TABLE", "main.gp_services_sdg_poc.fsr_scraped_file_mapping_ref")

# LLM settings – reads API key from Databricks secret scope
SECRET_SCOPE = "fsr-pipeline"
try:
    LITELLM_API_KEY = dbutils.secrets.get(scope=SECRET_SCOPE, key="LITELLM_API_KEY")
except Exception:
    LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")
try:
    LITELLM_BASE_URL = dbutils.secrets.get(scope=SECRET_SCOPE, key="LITELLM_BASE_URL")
except Exception:
    LITELLM_BASE_URL = os.getenv("LITELLM_BASE_URL", "https://dev-gateway.apps.gevernova.net")


def _decode_maybe_base64(value: str) -> str:
    """Decode base64-encoded secrets if values were stored encoded by mistake."""
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


LITELLM_API_KEY = _decode_maybe_base64(LITELLM_API_KEY)
LITELLM_BASE_URL = _decode_maybe_base64(LITELLM_BASE_URL)
LLM_MODEL = _get_runtime_param("FSR_LLM_MODEL", "gemini-3-flash")
BATCH_SIZE = int(_get_runtime_param("FSR_BATCH_SIZE", "4"))
MAX_PDFS = None  # set to int for testing, None = all
PDF_EXTRACT_WORKERS = int(_get_runtime_param("FSR_PDF_EXTRACT_WORKERS", "16"))  # threads for Stage 1
LLM_CONCURRENCY = int(_get_runtime_param("FSR_LLM_CONCURRENCY", "3"))      # starting max concurrent LLM calls
LLM_CONCURRENCY_MAX = int(_get_runtime_param("FSR_LLM_CONCURRENCY_MAX", "6")) # ceiling when errors are low
LLM_CONCURRENCY_MIN = 1                                               # floor when errors are high
_ssl_mode = _get_runtime_param("FSR_LLM_VERIFY_SSL", "false").strip()
if _ssl_mode.lower() in ("0", "false", "f", "no", "n", "off"):
    LLM_VERIFY_SSL = False
elif os.path.exists(_ssl_mode):
    LLM_VERIFY_SSL = _ssl_mode
else:
    LLM_VERIFY_SSL = True


class AdaptiveSemaphore:
    """threading.Semaphore whose capacity can be raised/lowered at runtime."""
    def __init__(self, initial: int, min_capacity: int = 1, max_capacity: int | None = None):
        self._cond = threading.Condition(threading.Lock())
        self._min_cap = max(1, min_capacity)
        self._max_cap = max_capacity if max_capacity is None else max(self._min_cap, max_capacity)
        self._capacity = initial
        if self._max_cap is not None:
            self._capacity = min(self._capacity, self._max_cap)
        self._capacity = max(self._min_cap, self._capacity)
        self._in_use = 0

    def acquire(self):
        with self._cond:
            while self._in_use >= self._capacity:
                self._cond.wait()
            self._in_use += 1

    def release(self):
        with self._cond:
            self._in_use -= 1
            self._cond.notify_all()

    def set_capacity(self, new_cap: int):
        with self._cond:
            if self._max_cap is None:
                self._capacity = max(self._min_cap, new_cap)
            else:
                self._capacity = max(self._min_cap, min(self._max_cap, new_cap))
            self._cond.notify_all()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


_llm_semaphore = AdaptiveSemaphore(
    LLM_CONCURRENCY,
    min_capacity=LLM_CONCURRENCY_MIN,
    max_capacity=LLM_CONCURRENCY,
)

# File suffixes that are never PDFs – skip silently
_SKIP_SUFFIXES = {".crdownload", ".tmp", ".part", ".download", ".DS_Store", ".json", ".txt", ".csv", ".xlsx"}

# FORCE_RESET: True = reprocess all PDFs even if already in output table.
# Leave False for incremental/resumable runs.
FORCE_RESET = False
try:
    _param = dbutils.widgets.get("FORCE_RESET")
    if _param.strip():
        FORCE_RESET = _param.strip().lower() in ("1", "true", "t", "yes", "y", "on")
        print(f"FORCE_RESET overridden via job parameter -> {FORCE_RESET}")
except Exception:
    pass

# IBAT and Event Vision tables
IBAT_EQUIPMENT_TABLE = os.getenv("FSR_IBAT_TABLE", "vgpd.prm_std_views.ibat_equipment_mst")
EVENT_VISION_SOT_TABLE = os.getenv("FSR_EVENT_VISION_TABLE", "vgpd.fsr_std_views.eventmgmt_event_vision_sot")


IBAT_EQUIPMENT_CSV_PATH = _get_runtime_param("FSR_IBAT_CSV_PATH", "")
EVENT_VISION_SOT_CSV_PATH = _get_runtime_param("FSR_EVENT_VISION_CSV_PATH", "")
LOOKUP_SOURCE = _get_runtime_param("FSR_LOOKUP_SOURCE", "auto").strip().lower()  # auto|csv|table|none

print(f"Volumes:          {len(PDF_VOLUME_PATHS)}")
print(f"Output table:     {OUTPUT_TABLE}")
print(f"Extract workers:  {PDF_EXTRACT_WORKERS}")
print(f"LLM model:    {LLM_MODEL}")
print(f"LLM verify SSL: {LLM_VERIFY_SSL}")
print(f"Lookup source: {LOOKUP_SOURCE}")
print(f"IBAT CSV path: {IBAT_EQUIPMENT_CSV_PATH or 'N/A'}")
print(f"EV CSV path:   {EVENT_VISION_SOT_CSV_PATH or 'N/A'}")
print(f"MAX_PDFS:     {MAX_PDFS or 'ALL'}")
print(f"FORCE_RESET:  {FORCE_RESET}")

# COMMAND ----------

# ── Stage 1: PDF field extraction (pdfplumber) ──────────────────────────────

def extract_fields_from_pdf(pdf_path: str) -> dict:
    """Extract key:value fields and title from the first page of a PDF."""
    fields = {"PDF Name / path / identifier": pdf_path}
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            text = first_page.extract_text()
            if not text:
                return fields

            lines = text.splitlines()
            current_key = None

            # Capture title (lines before the first colon-delimited field)
            title_lines = []
            for line in lines:
                if ":" in line:
                    break
                title_lines.append(line.strip())
            if title_lines:
                fields["Title"] = " ".join(title_lines)

            # key:value pairs
            for line in lines:
                if ":" in line:
                    parts = line.split(":", 1)
                    key = parts[0].strip()
                    value = parts[1].strip()
                    current_key = key
                    if key in fields:
                        fields[key] = f"{fields[key]} | {value}"
                    else:
                        fields[key] = value
                else:
                    if current_key:
                        fields[current_key] += " " + line.strip()
    except Exception as e:
        print(f"  [WARN] Error extracting {pdf_path}: {e}")
    return fields


def _get_dbr_auth():
    """Return (ws_url, token) — mirrors utils.py from dbr_final."""
    ws_url = "https://gevernova-ai-dev-dbr.cloud.databricks.com"
    env_token = os.getenv("DATABRICKS_TOKEN", "").strip()
    if env_token:
        return ws_url, env_token
    try:
        from pyspark.dbutils import DBUtils
        _dbutils = DBUtils(spark)
        token = _dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
        return ws_url, (token or "")
    except Exception:
        return ws_url, ""


def _discover_volume_pdfs_via_api(volume_path: str, ws_url: str, token: str):
    """List top-level volume files via Databricks Files API — mirrors utils.py."""
    encoded_path = quote(volume_path.lstrip("/"), safe="")
    base_url = f"{ws_url}/api/2.0/fs/directories/{encoded_path}"
    headers = {"Authorization": f"Bearer {token}"}

    discovered = []
    skipped_directories = 0
    next_page_token = ""
    while True:
        params = {"page_token": next_page_token} if next_page_token else None
        response = requests.get(base_url, headers=headers, params=params, timeout=60, verify=False)
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


def _discover_volume_pdfs_local(volume_path: str):
    """List top-level files from a locally mounted directory — mirrors utils.py."""
    discovered = []
    skipped_directories = 0
    with os.scandir(volume_path) as entries:
        for entry in entries:
            if entry.is_dir():
                skipped_directories += 1
                continue
            discovered.append(Path(entry.path))
    return discovered, skipped_directories


def discover_volume_pdfs(volume_path):
    """Use Files API on /Volumes/ paths, fall back to local scandir — mirrors utils.py."""
    volume_str = str(volume_path)
    ws_url, token = _get_dbr_auth()
    if volume_str.startswith("/Volumes/") and token:
        return _discover_volume_pdfs_via_api(volume_str, ws_url, token)
    return _discover_volume_pdfs_local(volume_str)


def _should_skip(path: str) -> bool:
    """Return True for file extensions that are never valid PDFs."""
    return Path(path).suffix.lower() in _SKIP_SUFFIXES


def collect_pdf_paths(volume_paths: list, already_processed: set, max_pdfs=None) -> list[str]:
    """List all candidate file paths from volumes via Files API.
    Filters known-bad extensions and already-processed paths.
    Does NOT extract PDF content – that happens per-thread in Stage 1."""
    all_file_paths = []
    for vol in volume_paths:
        print(f"Listing volume: {vol}")
        t = time.time()
        try:
            pdfs, skipped_dirs = discover_volume_pdfs(vol)
        except FileNotFoundError:
            print(f"  [WARN] Volume not found: {vol}")
            continue
        except Exception as e:
            print(f"  [WARN] Failed to scan {vol}: {e}")
            continue
        paths = [str(p) for p in pdfs]
        print(f"  → {len(paths)} files ({skipped_dirs} sub-dirs skipped) in {time.time() - t:.1f}s")
        all_file_paths.extend(paths)

    # Filter known non-PDF extensions
    skipped_ext = [p for p in all_file_paths if _should_skip(p)]
    all_file_paths = [p for p in all_file_paths if not _should_skip(p)]
    if skipped_ext:
        print(f"  Skipped {len(skipped_ext)} non-PDF files by extension")

    # Skip files already present in the output table
    new_paths = [p for p in all_file_paths if p not in already_processed]
    skipped_done = len(all_file_paths) - len(new_paths)
    if skipped_done:
        print(f"  Skipping {skipped_done} already-processed files, {len(new_paths)} remaining")

    if max_pdfs:
        new_paths = new_paths[:max_pdfs]

    print(f"Listing complete – {len(new_paths)} files to process")
    return new_paths


# Load already-processed PDF paths from the output table (for incremental runs)
already_processed: set = set()
if not FORCE_RESET:
    try:
        existing = spark.read.table(OUTPUT_TABLE).select("pdf_name").dropna().distinct()
        already_processed = set(r.pdf_name for r in existing.collect())
        print(f"[OK] {len(already_processed)} PDFs already in output table – will skip these")
    except Exception as e:
        print(f"[INFO] Output table not yet readable (first run?): {e}")
else:
    print("[INFO] FORCE_RESET=True – all PDFs will be reprocessed")

t0 = time.time()
all_pdf_paths = collect_pdf_paths(PDF_VOLUME_PATHS, already_processed, MAX_PDFS)
print(f"Listing elapsed: {time.time() - t0:.1f}s")

# COMMAND ----------

# ── Stage 2: LLM normalisation ──────────────────────────────────────────────

NORMALIZATION_PROMPT_SUFFIX = """Your task is to process JSON input and output a normalized JSON format
with the following fields only:

ESN, Equipment Sys ID, Equipment Type, Equipment Class / Code, Event Type,
EV Project ID, EV Equipment Event ID, OFS Event ID, FSP project ID, xxx project id, PDF Name / path / identifier,
FSR Number (#), Report Issued Date, Outage Start Date, Outage End Date.

If the PDF field contains an Oracle Project Id, map it to OFS Event ID only. But do not include field values that start with "EV" and "EVP" under OFS Event ID.
Map the PDF field containing "EV-" to EV Equipment Event ID only.
Map the PDF field containing "EVP-" to EV Project ID only.
Map the PDF field containing "SY" to Equipment Sys ID only.
If the PDF field contains a Field Service Project Id or "FSP-", map it to FSP project ID only.
If the PDF field contains a project id that starts with "XXX" (i.e. A-, C-, etc.), map it to xxx project id only.

**Strictly adhere to the following instructions while extracting and normalizing data**:
Do not miss any information that is present in the input and try to be as much accurate as possible in retrieving the values for the above fields.
**When extracting data, if a record contains multiple distinct values across ESN and Equipment Sys ID fields, split the record into separate rows by pairing values positionally (first with first, second with second, etc.), while duplicating all other field values unchanged (except for Equipment Type and Equipment Class / Code). Set the Equipment Type and Equipment Class / Code field values to empty strings in the split rows. Do not split or omit any parts for other field values even if multiple distinct values are present.**
If no exact match is found for a field, see if you can infer it from similar labels or context.
If no relevant information is found, output it as an empty string.
Consider as many records as provided in the input batch. Do not omit any records.
Do not include any reasoning or commentary, only valid JSON output.

For the field Event Type, only use values from the following allowed list:
Training Cost Accumulation, Unusual, Training Open Enrollment - Costs, TX Repairs,
Major Inspection (Field Rewind), Major Inspection (MI), Tooling(GE), C Inspection,
null, Training On Site Training, A Inspection, Services Warranty,
Borescope Inspection (BI), Major Inspection (Robotic), Performance Testing,
Upgrade - PMO Billing only, Digital, Non CSA-MMP Billing,
Hot Gas Path Inspection (HGPI), Initial Spares, Combustion Inspection (CI),
Training Open Enrollment - Billing, Stand Alone Small Upgrade, Large Call-Out,
On Site Services, Call-Out, TX Parts, B Inspection, Training Simulation,
Post COD New Unit Warranty, Major Inspection (Rotor Out), Stand Alone Large Upgrade,
OP Spares, Remote Diagnostics, Minor Inspection, Onsite Services SP,
Major Inspection (Stator Rewind)
"""

SYSTEM_PROMPT = (
    "You are an expert in structuring technical data. "
    "Your task is to process the provided input json and output a structured/normalized "
    "JSON format according to user instructions. Focus on clarity, completeness, and "
    "following the JSON schema provided. Do not include any internal reasoning or system "
    "details in the output. Ensure all responses are fact-based, and safe. "
    "Follow responsible AI principles without over-restricting harmless tasks."
)


def call_llm(prompt: str) -> str:
    """Call the LLM via direct OpenAI-compatible HTTP endpoint with retry + backoff.
    A semaphore limits concurrent in-flight calls to avoid gateway connection errors."""
    LLM_MAX_RETRIES = 4
    LLM_RETRY_BASE  = 5  # seconds
    base = LITELLM_BASE_URL.rstrip("/")
    candidate_urls = [f"{base}/chat/completions", f"{base}/v1/chat/completions"]
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {LITELLM_API_KEY}",
        "Content-Type": "application/json",
    }
    verify_opt = LLM_VERIFY_SSL

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            with _llm_semaphore:
                last_error = None
                for url in candidate_urls:
                    resp = requests.post(url, headers=headers, json=payload, timeout=120, verify=verify_opt)
                    if resp.status_code == 404:
                        last_error = RuntimeError(f"HTTP 404 on {url}")
                        continue
                    if resp.status_code >= 400:
                        preview = (resp.text or "").replace("\n", " ")[:500]
                        raise RuntimeError(f"HTTP {resp.status_code} from LLM gateway: {preview}")
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                if last_error is not None:
                    raise last_error
                raise RuntimeError("LLM gateway call failed with no response")
        except Exception as e:
            # If SSL chain fails, immediately retry this call with verify disabled.
            if verify_opt is not False and "CERTIFICATE_VERIFY_FAILED" in str(e):
                print("    [WARN] SSL certificate validation failed; retrying with verify=False")
                verify_opt = False
                continue
            if attempt == LLM_MAX_RETRIES:
                raise
            wait = LLM_RETRY_BASE * (2 ** (attempt - 1))  # 5, 10, 20 s
            print(f"    [WARN] LLM attempt {attempt}/{LLM_MAX_RETRIES} failed ({e}); retrying in {wait}s")
            time.sleep(wait)


def _strip_json_fences(text: str) -> str:
    """Remove ```json … ``` fences that some models wrap around JSON."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def normalise_batch(batch_records: list[dict], batch_num: int, total_batches: int) -> list[dict]:
    """Run Stage 2 for one extraction batch."""
    prompt = (
        f"Here is a JSON list of PDF fields:\n{json.dumps(batch_records, indent=2)}\n\n"
        + NORMALIZATION_PROMPT_SUFFIX
    )
    print(f"  [B{batch_num}/{total_batches}] Stage 2 start ({len(batch_records)} records)")
    raw = call_llm(prompt)
    cleaned = _strip_json_fences(raw)
    parsed = json.loads(cleaned)
    if isinstance(parsed, dict) and "FSR_data" in parsed:
        parsed = parsed["FSR_data"]
    if not isinstance(parsed, list):
        raise ValueError(f"Batch {batch_num}: expected list, got {type(parsed)}")
    print(f"  [B{batch_num}/{total_batches}] Stage 2 done ({len(parsed)} rows)")
    return parsed


# COMMAND ----------

# ── Stage 3: IBAT & Event Vision enrichment ─────────────────────────────────

COLUMN_RENAME_MAP = {
    "ESN": "esn",
    "Equipment Sys ID": "equipment_sys_id",
    "Equipment Type": "equipment_type",
    "Equipment Class / Code": "equipment_code",
    "Event Type": "event_type",
    "EV Project ID": "ev_project_id",
    "EV Equipment Event ID": "ev_equipment_event_id",
    "OFS Event ID": "ofs_event_id",
    "FSP project ID": "fsp_project_id",
    "xxx project id": "xxx_project_id",
    "PDF Name / path / identifier": "pdf_name",
    "FSR Number (#)": "fsr_number",
    "Report Issued Date": "report_issued_date",
    "Outage Start Date": "outage_start_date",
    "Outage End Date": "outage_end_date",
}

FINAL_COLS = [
    "esn",
    "equipment_sys_id",
    "equipment_type",
    "equipment_code",
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
    "pdf_name",
]


def ensure_output_table_exists():
    """Create output table if missing so writes can succeed in main.default."""
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {OUTPUT_TABLE} (
            esn STRING,
            equipment_sys_id STRING,
            equipment_type STRING,
            equipment_code STRING,
            event_type STRING,
            ev_project_id STRING,
            ev_equipment_event_id STRING,
            ofs_event_id STRING,
            fsp_project_id STRING,
            xxx_project_id STRING,
            fsr_number STRING,
            report_issued_date STRING,
            outage_start_date STRING,
            outage_end_date STRING,
            pdf_name STRING
        )
        USING DELTA
    """)


def rows_to_fallback_df(normalised_records: list[dict]):
    """Fallback when lookup schemas are inaccessible: write normalized rows directly."""
    pdf = pd.DataFrame(normalised_records).rename(columns=COLUMN_RENAME_MAP)
    for c in FINAL_COLS:
        if c not in pdf.columns:
            pdf[c] = ""
    base_df = spark.createDataFrame(pdf)
    return base_df.select([col(c).cast(StringType()).alias(c) for c in FINAL_COLS])


def load_lookup_tables():
    """Load static lookup tables once and share across batch workers."""
    if LOOKUP_SOURCE == "none":
        raise RuntimeError("Lookup source set to 'none'")

    if LOOKUP_SOURCE == "csv":
        if not IBAT_EQUIPMENT_CSV_PATH or not EVENT_VISION_SOT_CSV_PATH:
            raise RuntimeError("FSR_LOOKUP_SOURCE=csv requires FSR_IBAT_CSV_PATH and FSR_EVENT_VISION_SOT_CSV_PATH")
        ibat_src = spark.read.option("header", True).csv(IBAT_EQUIPMENT_CSV_PATH)
        ev_src = spark.read.option("header", True).csv(EVENT_VISION_SOT_CSV_PATH)
    elif LOOKUP_SOURCE == "table":
        ibat_src = spark.read.table(IBAT_EQUIPMENT_TABLE)
        ev_src = spark.read.table(EVENT_VISION_SOT_TABLE)
    elif IBAT_EQUIPMENT_CSV_PATH:
        ibat_src = spark.read.option("header", True).csv(IBAT_EQUIPMENT_CSV_PATH)
    else:
        ibat_src = spark.read.table(IBAT_EQUIPMENT_TABLE)

    ibat = ibat_src.select(
        upper(trim(col("equipment_sys_id"))).cast(StringType()).alias("ibat_equipment_sys_id"),
        upper(trim(col("equip_serial_number"))).cast(StringType()).alias("ibat_equip_serial_number"),
        col("equipment_type").cast(StringType()).alias("ibat_equipment_type"),
        col("equipment_sub_class").cast(StringType()).alias("ibat_equipment_code"),
    )

    if LOOKUP_SOURCE in ("csv", "table"):
        pass
    elif EVENT_VISION_SOT_CSV_PATH:
        ev_src = spark.read.option("header", True).csv(EVENT_VISION_SOT_CSV_PATH)
    elif 'ev_src' not in locals():
        ev_src = spark.read.table(EVENT_VISION_SOT_TABLE)

    ev_sot = ev_src.select(
        col("ev_project_id").cast(StringType()).alias("sot_ev_project_id"),
        col("ev_equipment_event_id").cast(StringType()).alias("sot_ev_equipment_event_id"),
        col("ev_gtm_id").cast(StringType()).alias("sot_ev_gtm_id"),
        col("fsp_project_id").cast(StringType()).alias("sot_fsp_project_id"),
        col("ev_event_type").cast(StringType()).alias("sot_event_type"),
        col("p6_outage_start_date").cast(StringType()).alias("sot_outage_start_date"),
        col("p6_outage_end_date").cast(StringType()).alias("sot_outage_end_date"),
    )

    # Force metadata/permission resolution here so caller can fall back cleanly.
    ibat.limit(1).count()
    ev_sot.limit(1).count()
    return ibat, ev_sot


def enrich_batch(normalised_records: list[dict], ibat_df, ev_sot_df):
    """Run Stage 3 for one normalized batch."""
    pdf = pd.DataFrame(normalised_records).rename(columns=COLUMN_RENAME_MAP)
    for c in FINAL_COLS:
        if c not in pdf.columns:
            pdf[c] = ""

    fsr_df = spark.createDataFrame(pdf)
    fsr_df = fsr_df.select([col(c).cast(StringType()).alias(c) for c in pdf.columns])

    fsr_df = (
        fsr_df
        .withColumn("ev_project_id", trim(col("ev_project_id")))
        .withColumn("ev_equipment_event_id", trim(col("ev_equipment_event_id")))
        .withColumn("ofs_event_id", trim(col("ofs_event_id")))
        .withColumn("fsp_project_id", trim(col("fsp_project_id")))
        .withColumn("fsp_project_id_stripped", regexp_replace(col("fsp_project_id"), "FSP-", ""))
        .withColumn("ev_project_id_stripped", regexp_replace(col("ev_project_id"), "EVP-", ""))
        .withColumn("ev_equipment_event_id_stripped", regexp_replace(col("ev_equipment_event_id"), "EV-", ""))
    )

    enriched = fsr_df.join(
        ibat_df,
        (fsr_df["equipment_sys_id"] == ibat_df["ibat_equipment_sys_id"])
        | (fsr_df["esn"] == ibat_df["ibat_equip_serial_number"]),
        "left",
    )

    enriched = (
        enriched
        .withColumn("esn",
            when((col("esn").isNull()) | (col("esn") == ""), col("ibat_equip_serial_number")).otherwise(col("esn")))
        .withColumn("equipment_sys_id",
            when((col("equipment_sys_id").isNull()) | (col("equipment_sys_id") == ""), col("ibat_equipment_sys_id")).otherwise(col("equipment_sys_id")))
        .withColumn("equipment_type",
            when((col("equipment_type").isNull()) | (col("equipment_type") == ""), col("ibat_equipment_type")).otherwise(col("equipment_type")))
        .withColumn("equipment_code",
            when((col("equipment_code").isNull()) | (col("equipment_code") == ""), col("ibat_equipment_code")).otherwise(col("equipment_code")))
    )

    enriched = enriched.join(
        ev_sot_df,
        (enriched["ev_project_id_stripped"] == ev_sot_df["sot_ev_project_id"])
        | (enriched["ev_equipment_event_id_stripped"] == ev_sot_df["sot_ev_equipment_event_id"])
        | (enriched["ofs_event_id"] == ev_sot_df["sot_ev_gtm_id"])
        | (enriched["fsp_project_id_stripped"] == ev_sot_df["sot_fsp_project_id"]),
        "left",
    )

    enriched = (
        enriched
        .withColumn("ev_project_id",
            when((col("ev_project_id").isNull()) | (col("ev_project_id") == ""), concat(lit("EVP-"), col("sot_ev_project_id"))).otherwise(col("ev_project_id")))
        .withColumn("ev_equipment_event_id",
            when((col("ev_equipment_event_id").isNull()) | (col("ev_equipment_event_id") == ""), concat(lit("EV-"), col("sot_ev_equipment_event_id"))).otherwise(col("ev_equipment_event_id")))
        .withColumn("ofs_event_id",
            when((col("ofs_event_id").isNull()) | (col("ofs_event_id") == ""), col("sot_ev_gtm_id")).otherwise(col("ofs_event_id")))
        .withColumn("fsp_project_id",
            when((col("fsp_project_id").isNull()) | (col("fsp_project_id") == ""), concat(lit("FSP-"), col("sot_fsp_project_id"))).otherwise(col("fsp_project_id")))
        .withColumn("event_type",
            when((col("event_type").isNull()) | (col("event_type") == ""), col("sot_event_type")).otherwise(col("event_type")))
        .withColumn("outage_start_date",
            when((col("outage_start_date").isNull()) | (col("outage_start_date") == ""), col("sot_outage_start_date")).otherwise(col("outage_start_date")))
        .withColumn("outage_end_date",
            when((col("outage_end_date").isNull()) | (col("outage_end_date") == ""), col("sot_outage_end_date")).otherwise(col("outage_end_date")))
    )

    return enriched.select([col(c) for c in FINAL_COLS])


# COMMAND ----------

# ── Stage 2+3+4 threaded execution by batch ────────────────────────────────

MAX_THREADS = int(_get_runtime_param("FSR_BATCH_THREADS", "4"))
WORKER_CONCURRENCY_START = int(_get_runtime_param("FSR_BATCH_THREADS_START", "2"))
THREAD_RAMP_SECONDS = int(_get_runtime_param("FSR_BATCH_THREAD_RAMP_SECONDS", "10"))
WORKER_CONCURRENCY_START = max(1, min(MAX_THREADS, WORKER_CONCURRENCY_START))
_worker_semaphore = AdaptiveSemaphore(
    WORKER_CONCURRENCY_START,
    min_capacity=1,
    max_capacity=MAX_THREADS,
)
# Worker concurrency is adaptive; LLM concurrency remains fixed via _llm_semaphore.

# Rolling window of recent batch outcomes (True=success, False=fail)
_outcome_window: collections.deque = collections.deque(maxlen=20)
_outcome_lock = threading.Lock()
_last_worker_adjust_ts = 0.0


def _record_outcome(success: bool, llm_error: bool = False):
    """Record outcomes and adapt worker concurrency from observed LLM failures."""
    global _last_worker_adjust_ts
    with _outcome_lock:
        if success:
            _outcome_window.append(True)
        elif llm_error:
            _outcome_window.append(False)
        else:
            return

        if len(_outcome_window) < 3:
            return  # not enough data yet

        error_rate = _outcome_window.count(False) / len(_outcome_window)
        now = time.time()
        if now - _last_worker_adjust_ts < THREAD_RAMP_SECONDS:
            return

        current = _worker_semaphore.capacity
        if error_rate > 0.4 and current > 1:
            _worker_semaphore.set_capacity(current - 1)
            _last_worker_adjust_ts = now
            print(f"  [ADAPTIVE] llm_error_rate={error_rate:.0%} → worker concurrency ↓ {_worker_semaphore.capacity}")
        elif error_rate < 0.1 and current < MAX_THREADS:
            _worker_semaphore.set_capacity(current + 1)
            _last_worker_adjust_ts = now
            print(f"  [ADAPTIVE] llm_error_rate={error_rate:.0%} → worker concurrency ↑ {_worker_semaphore.capacity}")


def _recent_error_rate() -> float:
    with _outcome_lock:
        if not _outcome_window:
            return 0.0
        return _outcome_window.count(False) / len(_outcome_window)


write_lock = threading.Lock()
stats_lock = threading.Lock()
pipeline_stats = {
    "batches_total": 0,
    "batches_success": 0,
    "batches_failed": 0,
    "rows_written": 0,
    "started_at": None,
}


def _format_seconds(total_seconds: float) -> str:
    secs = max(0, int(total_seconds))
    hours, rem = divmod(secs, 3600)
    mins, s = divmod(rem, 60)
    if hours:
        return f"{hours}h {mins}m {s}s"
    if mins:
        return f"{mins}m {s}s"
    return f"{s}s"


def _log_eta(batch_num: int):
    with stats_lock:
        total = pipeline_stats["batches_total"]
        done = pipeline_stats["batches_success"] + pipeline_stats["batches_failed"]
        started_at = pipeline_stats.get("started_at")
    if not started_at or done <= 0 or total <= 0:
        return

    elapsed = time.time() - started_at
    rate = done / max(elapsed, 1e-6)
    remaining_batches = max(0, total - done)
    eta_seconds = remaining_batches / rate if rate > 0 else 0
    print(
        f"  [ETA] after B{batch_num}/{total}: done={done}/{total}, "
        f"rate={rate * 60:.2f} batches/min, elapsed={_format_seconds(elapsed)}, "
        f"remaining~{_format_seconds(eta_seconds)}"
    )


def process_batch(batch_num: int, total_batches: int, batch_paths: list[str], ibat_df, ev_sot_df, enrichment_enabled: bool):
    try:
        # Stage 1: extract fields from each PDF in this batch
        raw_records = [extract_fields_from_pdf(p) for p in batch_paths]
        print(f"  [B{batch_num}/{total_batches}] Stage 1 done ({len(raw_records)} extracted)")

        # Stage 2: LLM normalisation
        normalised_rows = normalise_batch(raw_records, batch_num, total_batches)
        if not normalised_rows:
            print(f"  [B{batch_num}/{total_batches}] Stage 2 produced 0 rows, skipping")
            with stats_lock:
                pipeline_stats["batches_success"] += 1
            _log_eta(batch_num)
            return

        # Stage 3: IBAT + Event Vision enrichment (or fallback if lookup access is denied)
        if enrichment_enabled and ibat_df is not None and ev_sot_df is not None:
            enriched_df = enrich_batch(normalised_rows, ibat_df, ev_sot_df)
        else:
            enriched_df = rows_to_fallback_df(normalised_rows)
        batch_count = enriched_df.count()
        print(f"  [B{batch_num}/{total_batches}] Stage 3 done ({batch_count} rows)")

        # Stage 4: write batch to Delta table
        with write_lock:
            enriched_df.write.mode("append").saveAsTable(OUTPUT_TABLE)
        print(f"  [B{batch_num}/{total_batches}] Stage 4 done (appended)")

        with stats_lock:
            pipeline_stats["batches_success"] += 1
            pipeline_stats["rows_written"] += batch_count
        _record_outcome(True)
        _log_eta(batch_num)
    except Exception as exc:
        print(f"  [B{batch_num}/{total_batches}] ERROR: {exc}")
        with stats_lock:
            pipeline_stats["batches_failed"] += 1
        err_text = str(exc).lower()
        llm_error = any(token in err_text for token in ("llm", "gateway", "chat/completions", "model", "choices"))
        _record_outcome(False, llm_error=llm_error)
        _log_eta(batch_num)


def chunk_paths(paths: list[str], size: int) -> list[list[str]]:
    return [paths[i:i + size] for i in range(0, len(paths), size)]


batches = chunk_paths(all_pdf_paths, BATCH_SIZE)
pipeline_stats["batches_total"] = len(batches)
pipeline_stats["started_at"] = time.time()

if not batches:
    print("No new records to process after Stage 1 skipping logic.")
else:
    ensure_output_table_exists()
    if FORCE_RESET:
        try:
            spark.sql(f"TRUNCATE TABLE {OUTPUT_TABLE}")
            print(f"[OK] FORCE_RESET cleared table {OUTPUT_TABLE}")
        except Exception as exc:
            print(f"[WARN] FORCE_RESET truncate failed (continuing): {exc}")

    enrichment_enabled = True
    try:
        ibat_lookup_df, ev_sot_lookup_df = load_lookup_tables()
    except Exception as exc:
        print(f"[WARN] Lookup table access failed ({exc}). Continuing without Stage 3 enrichment.")
        ibat_lookup_df, ev_sot_lookup_df = None, None
        enrichment_enabled = False

    q: Queue = Queue()
    for idx, path_slice in enumerate(batches, 1):
        q.put((idx, path_slice))

    def worker_loop(worker_name: str):
        while True:
            _worker_semaphore.acquire()
            try:
                item = q.get_nowait()
            except Empty:
                _worker_semaphore.release()
                return
            except Exception:
                _worker_semaphore.release()
                return
            try:
                batch_num, batch_paths = item
                process_batch(batch_num, len(batches), batch_paths, ibat_lookup_df, ev_sot_lookup_df, enrichment_enabled)
            finally:
                _worker_semaphore.release()
                q.task_done()

    worker_count = min(MAX_THREADS, len(batches))
    workers = []

    t_pipeline = time.time()
    print(
        f"[INFO] Worker autoscaling enabled: start={WORKER_CONCURRENCY_START}, max={worker_count}, "
        f"ramp_interval={THREAD_RAMP_SECONDS}s"
    )
    for n in range(worker_count):
        wname = f"worker-{n + 1}"
        t = threading.Thread(target=worker_loop, args=(wname,), daemon=True)
        t.start()
        workers.append(t)
        print(
            f"[INFO] Started {wname} ({n + 1}/{worker_count}) "
            f"worker_cap={_worker_semaphore.capacity} llm_concurrency={_llm_semaphore.capacity}"
        )

    for t in workers:
        t.join()

    verify_count = spark.read.table(OUTPUT_TABLE).count()
    print(
        "\n✅ Pipeline complete"
        f"\n  batches_total:   {pipeline_stats['batches_total']}"
        f"\n  batches_success: {pipeline_stats['batches_success']}"
        f"\n  batches_failed:  {pipeline_stats['batches_failed']}"
        f"\n  rows_written:    {pipeline_stats['rows_written']}"
        f"\n  table_rows:      {verify_count}"
        f"\n  elapsed:         {time.time() - t_pipeline:.1f}s"
    )


# COMMAND ----------

# ── Quick preview ────────────────────────────────────────────────────────────
display(spark.read.table(OUTPUT_TABLE).limit(20))
