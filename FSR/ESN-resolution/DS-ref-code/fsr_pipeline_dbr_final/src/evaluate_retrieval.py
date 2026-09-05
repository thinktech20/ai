"""
FSR Retrieval Evaluation – Ground Truth Validation

Evaluates retrieval quality against expert-curated FSR citations.

Inputs:
    - Heat Map Excel                 → issue_prompt queries (GEN + Rotor rows only)
    - FSR citations workbook         → raw ground truth source
    - results/citations_parsed.csv   → auto-generated cache of parsed citations

For each (esn, issue) pair:
    1. Query VS with generator_serial=esn filter, k=20, ANN, NO reranking
    2. Query VS with generator_serial=esn filter, k=20, ANN, WITH reranking
    3. Query VS with generator_serial=esn filter, k=20, HYBRID, NO reranking
    4. Query VS with generator_serial=esn filter, k=20, HYBRID, WITH reranking
    5. For k=1..20, check if any retrieved chunk is a hit:
       HIT = page-based (pdf_name stem matches AND page_number within GT page ± PAGE_WINDOW)
          OR text-based  (NFKC + alpha-only snippet_in_text, mirrors check_expanded_coverage.py)
    6. Compute Recall@K and Precision@K

Output:
    - results/eval_raw_<variant>_<ts>.csv      – per (serial, issue, mode, k) row
    - results/eval_summary_<variant>_<ts>.csv  – avg metrics by (mode, k)
"""

import os
import re
import time
import json
import requests
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from vector_embeddings import get_query_vector

# ---------------------------------------------------------------------------
# Config imports – graceful fallback for local dev
# ---------------------------------------------------------------------------
try:
    from config import VS_INDEX_NAME, VS_ENDPOINT_NAME
    from utils import setup_logger
except ImportError:
    VS_INDEX_NAME = os.getenv(
        "VS_INDEX_NAME",
        "main.gp_services_sdg_poc.vs_field_service_report",
    )
    VS_ENDPOINT_NAME = os.getenv(
        "VS_ENDPOINT_NAME", "pw-ser-sdg-vector-search"
    )
    import logging

    def setup_logger(name):
        lgr = logging.getLogger(name)
        if not lgr.handlers:
            h = logging.StreamHandler()
            h.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"
                )
            )
            lgr.addHandler(h)
            lgr.setLevel(logging.INFO)
        return lgr


logger = setup_logger("evaluate")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
HEAT_MAP_FILE = PROJECT_DIR / "Heat Map - Unified Structure v0.1.xlsx"
CITATIONS_WORKBOOK = PROJECT_DIR / "FSR_citations_processed_20260305_135321.xlsx"
RESULTS_DIR = PROJECT_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)
# GT citations in long format: issue_name, esn, src_pdf, page, snippet
CITATIONS_FILE = RESULTS_DIR / "citations_parsed.csv"

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------
# Number of pages forward from a chunk's page_number to look for a cited page
# (compensates for not having end_page in VS results; most chunks ≤ 10 pages)
PAGE_WINDOW = 10
RETURN_COLUMNS = [
    "chunk_id", "pdf_name", "page_number", "chunk_text", "generator_serial",
]
CRITERIA_COLUMNS = [
    "severity_criteria_0_no_data",
    "severity_criteria_1_light",
    "severity_criteria_2_medium",
    "severity_criteria_3_heavy",
    "severity_criteria_4_immediate",
]
RAW_RESULT_COLUMNS = [
    "serial",
    "issue_name",
    "query_variant",
    "mode",
    "query_type",
    "reranking",
    "k",
    "num_returned",
    "matches_in_top_k",
    "recall_at_k",
    "precision_at_k",
    "gt_citation_count",
]
SUMMARY_COLUMNS = [
    "query_variant",
    "mode",
    "k",
    "n_queries",
    "avg_recall",
    "avg_precision",
    "total_matches",
]

# Citation parsing regexes for materialising citations_parsed.csv from the
# processed workbook when starting from a clean checkout.
_PDF_RE = re.compile(r"\[(?:FSR File:\s*)?([^\]\[]+?\.pdf)\]", re.IGNORECASE)
_PAGE_RE = re.compile(r"\[Page:\s*([^\]]+?)\s*\]")
_META_TAG_RE = re.compile(r"\[[^\]\[]{1,40}\]")
_QUOT_RES = [
    re.compile(r"\u201c([^\u201d]+)\u201d"),
    re.compile(r'"([^"]+)"'),
    re.compile(r"\u2018([^\u2019]+)\u2019"),
    re.compile(r"'([^']+)'"),
]


# ===================================================================== #
#  AUTH & QUERY HELPERS                                                   #
# ===================================================================== #

def _get_auth() -> Tuple[str, str]:
    """Return (workspace_url, bearer_token)."""
    ws = os.getenv(
        "DATABRICKS_HOST",
        "https://gevernova-ai-dev-dbr.cloud.databricks.com",
    )
    token = None
    try:
        from pyspark.sql import SparkSession
        from pyspark.dbutils import DBUtils

        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)
        token = (
            dbutils.notebook.entry_point
            .getDbutils().notebook().getContext().apiToken().get()
        )
    except Exception:
        token = os.getenv("DATABRICKS_TOKEN", "")
    return ws.rstrip("/"), (token or "")


def _find_ge_cert() -> str:
    """Return path to GE Enterprise Root CA cert, or '' if not found."""
    # 1. Already resolved by config.py
    from config import CERT_PATH as _cp
    if _cp and Path(_cp).exists():
        return str(_cp)
    # 2. Relative to this file (src/../GE_Enterprise_Root_CA_2_1.crt)
    _adjacent = Path(__file__).parent.parent / "GE_Enterprise_Root_CA_2_1.crt"
    if _adjacent.exists():
        return str(_adjacent)
    # 3. Workspace path typical in Databricks
    for _ws in [
        "/Workspace/Users/alex.seidel@ge.com/fsr_pipeline/GE_Enterprise_Root_CA_2_1.crt",
        "/Workspace/Repos/alex.seidel@ge.com/fsr_pipeline/GE_Enterprise_Root_CA_2_1.crt",
    ]:
        if Path(_ws).exists():
            return _ws
    return ""


def _ensure_ca_bundle() -> str:
    """Build combined CA bundle (system CAs + GE cert) once; return bundle path."""
    if getattr(_ensure_ca_bundle, "_bundle", ""):
        return _ensure_ca_bundle._bundle

    ge_cert = _find_ge_cert()
    if not ge_cert:
        _ensure_ca_bundle._bundle = ""
        return ""

    try:
        import shutil, tempfile
        combined = Path(tempfile.gettempdir()) / f"fsr_eval_ca_{os.getpid()}.pem"
        if not combined.exists():
            # Start from certifi system bundle, fall back to OS bundle
            system_bundle = ""
            try:
                import certifi
                system_bundle = certifi.where()
            except ImportError:
                for _candidate in [
                    "/etc/ssl/certs/ca-certificates.crt",
                    "/etc/pki/tls/certs/ca-bundle.crt",
                ]:
                    if Path(_candidate).exists():
                        system_bundle = _candidate
                        break
            if system_bundle:
                shutil.copy2(system_bundle, combined)
            else:
                combined.write_bytes(b"")
            with open(combined, "a") as _f:
                _f.write("\n")
                _f.write(Path(ge_cert).read_text())

        bundle = str(combined)
        os.environ["REQUESTS_CA_BUNDLE"] = bundle
        os.environ["SSL_CERT_FILE"]      = bundle
        os.environ["CURL_CA_BUNDLE"]     = bundle
        _ensure_ca_bundle._bundle = bundle
        return bundle
    except Exception as _e:
        logger.warning(f"[WARN] Could not build combined CA bundle: {_e} — falling back to GE cert only")
        os.environ["REQUESTS_CA_BUNDLE"] = ge_cert
        os.environ["SSL_CERT_FILE"]      = ge_cert
        os.environ["CURL_CA_BUNDLE"]     = ge_cert
        _ensure_ca_bundle._bundle = ge_cert
        return ge_cert


def _get_vs_index():
    """Return (VectorSearchClient, index) — cached after first call."""
    if not hasattr(_get_vs_index, "_idx"):
        from databricks.vector_search.client import VectorSearchClient

        _ensure_ca_bundle()
        ws_url, token = _get_auth()
        kwargs = {"workspace_url": ws_url, "disable_notice": True}
        if token:
            kwargs["personal_access_token"] = token
        client = VectorSearchClient(**kwargs)
        _get_vs_index._idx = client.get_index(
            endpoint_name=VS_ENDPOINT_NAME,
            index_name=VS_INDEX_NAME,
        )
    return _get_vs_index._idx


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def _query_sdk(
    query_text: str,
    serial: str,
    num_results: int = 20,
    query_type: str = "HYBRID",
    use_reranking: bool = False,
) -> List[Dict]:
    """Query VS via SDK with optional DatabricksReranker."""
    idx = _get_vs_index()
    query_vector = get_query_vector(query_text)

    search_kwargs = {
        "columns": RETURN_COLUMNS,
        "query_text": query_text,
        "query_vector": query_vector,
        "filters": {"generator_serial": serial},
        "num_results": num_results,
        "query_type": query_type.upper(),
        # Avoid noisy PAT notices in notebook output.
        "disable_notice": True,
    }
    if use_reranking:
        from databricks.vector_search.reranker import DatabricksReranker
        try:
            search_kwargs["reranker"] = DatabricksReranker(
                columns_to_rerank=["chunk_text"],
                disable_notice=True,
            )
        except TypeError:
            search_kwargs["reranker"] = DatabricksReranker(
                columns_to_rerank=["chunk_text"],
            )

    raw = idx.similarity_search(**search_kwargs)
    col_names = [c["name"] for c in raw.get("manifest", {}).get("columns", [])]
    rows = raw.get("result", {}).get("data_array", [])

    return [{col: row[i] for i, col in enumerate(col_names)} for row in rows]


def _query_rest(
    query_text: str,
    serial: Optional[str],
    num_results: int = 20,
    query_type: str = "HYBRID",
) -> List[Dict]:
    """Query VS via REST API (no reranking). Pass serial=None to skip filter."""
    _ensure_ca_bundle()
    ws_url, token = _get_auth()
    query_vector = get_query_vector(query_text)
    url = f"{ws_url}/api/2.0/vector-search/indexes/{VS_INDEX_NAME}/query"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "query_text": query_text,
        "query_vector": query_vector,
        "columns": RETURN_COLUMNS,
        "num_results": num_results,
        "query_type": query_type.upper(),
    }
    if serial is not None:
        body["filters_json"] = json.dumps({"generator_serial": serial})
    ca_bundle = _ensure_ca_bundle()
    verify = ca_bundle if ca_bundle else True
    resp = requests.post(url, headers=headers, json=body, timeout=60, verify=verify)
    if not resp.ok:
        logger.warning(f"VS query HTTP {resp.status_code}: {resp.text[:300]}")
        return []

    data = resp.json()
    col_names = [c["name"] for c in data.get("manifest", {}).get("columns", [])]
    rows = data.get("result", {}).get("data_array", [])
    return [{col: row[i] for i, col in enumerate(col_names)} for row in rows]


def query_vs(
    query_text: str,
    serial: str,
    num_results: int = 20,
    query_type: str = "HYBRID",
    use_reranking: bool = False,
) -> List[Dict]:
    """Query VS — tries SDK first (supports reranking), falls back to REST."""
    try:
        return _query_sdk(query_text, serial, num_results, query_type, use_reranking)
    except ImportError:
        logger.info("SDK not available — falling back to REST API (no reranking)")
        return _query_rest(query_text, serial, num_results, query_type)
    except Exception as e:
        logger.warning(f"SDK query failed ({e}) — falling back to REST API")
        return _query_rest(query_text, serial, num_results, query_type)


# ===================================================================== #
#  DATA LOADING                                                           #
# ===================================================================== #

def _normalise_issue(name: str) -> str:
    """Collapse whitespace for reliable cross-file join on issue_name."""
    return " ".join(str(name).split()).strip()


def _build_issue_query(row: pd.Series, include_criteria: bool) -> str:
    """Build query text from issue prompt, optionally appending criteria 0-4."""
    prompt = str(row.get("issue_prompt", "")).strip()
    if not include_criteria:
        return prompt

    criteria_parts = [
        str(row.get(col, "")).strip()
        for col in CRITERIA_COLUMNS
        if str(row.get(col, "")).strip()
        and str(row.get(col, "")).strip().lower() != "nan"
    ]
    if criteria_parts:
        return prompt + " " + " ".join(criteria_parts)
    return prompt


def _extract_quoted_snippets(block: str) -> List[str]:
    """Return all quoted strings from a citation block, longest-first deduped."""
    found: List[str] = []
    for pat in _QUOT_RES:
        for match in pat.finditer(block):
            snippet = match.group(1).strip()
            if len(snippet) >= 8:
                found.append(snippet)

    seen = set()
    deduped: List[str] = []
    for snippet in found:
        if snippet not in seen:
            seen.add(snippet)
            deduped.append(snippet)
    return deduped


def _parse_citation_cell(cell_str: str) -> List[Tuple[str, Optional[str], str]]:
    """Parse one citations workbook cell to (src_pdf, page_ref, snippet) tuples."""
    pdf_matches = list(_PDF_RE.finditer(cell_str))
    results: List[Tuple[str, Optional[str], str]] = []

    for index, pdf_match in enumerate(pdf_matches):
        src_pdf = pdf_match.group(1).strip()
        block_start = pdf_match.end()
        block_end = pdf_matches[index + 1].start() if (index + 1) < len(pdf_matches) else len(cell_str)
        block = cell_str[block_start:block_end]

        page_match = _PAGE_RE.search(block)
        page_ref = page_match.group(1).strip() if page_match else None
        text_block = block[page_match.end():] if page_match else block

        for meta_match in _META_TAG_RE.finditer(text_block):
            tag = meta_match.group(0)
            if _PAGE_RE.fullmatch(tag) or _PDF_RE.fullmatch(tag):
                continue
            text_block = text_block[:meta_match.start()]
            break

        snippets = _extract_quoted_snippets(text_block)
        if not snippets:
            clean = re.sub(r"\[[^\]]*\]", "", text_block).strip()
            clean = re.sub(r"^and\b", "", clean, flags=re.IGNORECASE).strip()
            clean = " ".join(clean.split())
            if len(clean) >= 8:
                snippets = [clean]

        for snippet in snippets:
            results.append((src_pdf, page_ref, snippet))

    return results


def _ensure_ground_truth_csv() -> Path:
    """Materialise results/citations_parsed.csv from the workbook when absent."""
    if CITATIONS_FILE.exists():
        return CITATIONS_FILE

    if not CITATIONS_WORKBOOK.exists():
        raise FileNotFoundError(
            "Ground-truth citations not found. Expected either "
            f"{CITATIONS_FILE.name} or {CITATIONS_WORKBOOK.name} in the project root."
        )

    logger.info(
        f"Building {CITATIONS_FILE.name} from {CITATIONS_WORKBOOK.name}"
    )
    raw_df = pd.read_excel(str(CITATIONS_WORKBOOK))
    if "issue_name" not in raw_df.columns:
        raise ValueError(
            f"{CITATIONS_WORKBOOK.name} is missing required column 'issue_name'"
        )

    esn_cols = list(raw_df.columns[1:])
    rows: List[Dict[str, Optional[str]]] = []

    for _, df_row in raw_df.iterrows():
        issue_name = str(df_row["issue_name"]).strip()
        for esn in esn_cols:
            cell = df_row[esn]
            if pd.isna(cell) or not str(cell).strip():
                continue
            for src_pdf, page_ref, snippet in _parse_citation_cell(str(cell)):
                rows.append(
                    {
                        "issue_name": issue_name,
                        "esn": str(esn).strip(),
                        "src_pdf": src_pdf,
                        "page": page_ref,
                        "snippet": snippet,
                    }
                )

    out_df = pd.DataFrame(
        rows,
        columns=["issue_name", "esn", "src_pdf", "page", "snippet"],
    )
    CITATIONS_FILE.parent.mkdir(exist_ok=True)
    out_df.to_csv(CITATIONS_FILE, index=False)
    logger.info(f"Wrote {len(out_df)} parsed citation rows -> {CITATIONS_FILE.name}")
    return CITATIONS_FILE


def load_queries(include_criteria: bool = False) -> List[Dict]:
    """Load issue prompts from heat map, filtered to GEN + Rotor."""
    df = pd.read_excel(str(HEAT_MAP_FILE))
    filt = df[
        (df["equipment_type"] == "GEN") & (df["component"] == "Rotor")
    ]
    queries = []
    for _, row in filt.iterrows():
        queries.append(
            {
                "issue_name": _normalise_issue(row["issue_name"]),
                "issue_prompt": _build_issue_query(row, include_criteria),
                "issue_grouping": str(row.get("issue_grouping", "")),
            }
        )
    mode_label = "with criteria 0-4" if include_criteria else "prompt only"
    logger.info(f"Loaded {len(queries)} queries ({mode_label}, GEN + Rotor from heat map)")
    return queries


def load_ground_truth() -> Tuple[
    Dict[Tuple[str, str], Optional[Dict]],
    List[str],
]:
    """
    Load ground truth from citations_parsed.csv.

    If the parsed CSV is missing, it is generated from the processed citations
    workbook shipped with the project.

    Returns
    -------
    gt : dict  (normalised_issue_name, esn) →
            {"page_hits": {pdf_stem: set(cited_pages)}, "snippets": [str, ...]}
         or None if no citations exist for that pair (abstain).
    serials : sorted list[str]  — unique ESNs from GT file.
    """
    from collections import defaultdict
    gt_path = _ensure_ground_truth_csv()
    df = pd.read_csv(str(gt_path))
    logger.info(f"Loaded {len(df)} GT citation rows from {gt_path.name}")

    gt: Dict[Tuple[str, str], Optional[Dict]] = {}
    for _, row in df.iterrows():
        issue = _normalise_issue(str(row.get("issue_name", "")))
        esn   = str(row.get("esn", "")).strip() if not pd.isna(row.get("esn", "")) else ""
        src   = str(row.get("src_pdf", "")) if not pd.isna(row.get("src_pdf", "")) else ""
        page_raw  = row.get("page", "")
        snippet   = str(row.get("snippet", "")) if not pd.isna(row.get("snippet", "")) else ""

        key = (issue, esn)
        if key not in gt:
            gt[key] = {"page_hits": defaultdict(set), "snippets": []}
        entry = gt[key]

        stem = _pdf_stem(src)
        for p in _cited_pages(page_raw):
            entry["page_hits"][stem].add(p)

        if snippet and snippet not in entry["snippets"]:
            entry["snippets"].append(snippet)

    # Convert inner defaultdicts to plain dicts
    for entry in gt.values():
        if entry is not None:
            entry["page_hits"] = dict(entry["page_hits"])

    serials = sorted({esn for (_, esn) in gt.keys() if esn})

    n_valid = sum(1 for v in gt.values() if v is not None)
    logger.info(f"GT: {n_valid} (issue, ESN) pairs  |  {len(serials)} unique ESNs")
    return gt, serials





# ===================================================================== #
#  TEXT NORMALISATION + SNIPPET MATCHING  (mirrors check_expanded_coverage)
# ===================================================================== #

_SEP_RE = re.compile(r'\u2022|\u00b7|\u2026|\.{2,}')


def _norm(t: str) -> str:
    """NFKC-normalise, lowercase, collapse whitespace."""
    from unicodedata import normalize as _uninorm
    return re.sub(r'\s+', ' ', _uninorm('NFKC', t).lower().strip())


def _alpha_norm(t: str) -> str:
    """Keep only [a-z0-9 ] — strips encoding artefacts (PyPDF2 vs PyMuPDF)."""
    return re.sub(r'[^a-z0-9 ]', '', _norm(t))


def _split_parts(snippet: str) -> List[str]:
    """Split on bullet/ellipsis separators; return normalised non-empty parts."""
    parts = _SEP_RE.split(snippet)
    result = [_norm(p) for p in parts if len(_norm(p)) >= 4]
    if not result:
        n = _norm(snippet)
        if len(n) >= 3:
            result = [n]
    return result


def snippet_in_text(snippet: str, text: str) -> bool:
    """Two-pass: NFKC normalisation, then alpha-only fallback."""
    parts = _split_parts(snippet)
    if not parts:
        return False
    text_norm = _norm(text)
    for part in parts:
        if part in text_norm:
            return True
    text_alpha = _alpha_norm(text)
    for part in parts:
        pa = _alpha_norm(part)
        if len(pa) >= 4 and pa in text_alpha:
            return True
    return False


# ===================================================================== #
#  PAGE + PDF HELPERS
# ===================================================================== #

def _pdf_stem(cited: str) -> str:
    """Normalise a cited PDF filename to a bare stem for comparison."""
    name = str(cited)
    for prefix in ("FSR - ", "FSR: ", "FSR "):
        if name.startswith(prefix):
            name = name[len(prefix):]
    name = name.replace(
        "Field_Service_ReportProjectID",
        "Field_Service_Report_ProjectID",
    )
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return name


def _cited_pages(page_str) -> List[int]:
    """Parse a page string like '191' or '348-349' to a list of ints."""
    if page_str is None or (isinstance(page_str, float) and pd.isna(page_str)):
        return []
    nums = [int(x) for x in re.findall(r'\d+', str(page_str))]
    if not nums:
        return []
    lo, hi = min(nums), max(nums)
    return list(range(lo, hi + 1))


# ===================================================================== #
#  HIT CRITERIA  (page-based primary, snippet text fallback)
# ===================================================================== #

def check_match_page(result: Dict, gt_entry: Dict) -> bool:
    """
    True if the retrieved chunk covers any GT-cited page in the right PDF.

    Uses page_number (chunk start page) + PAGE_WINDOW to approximate the
    chunk's page range, since end_page is not returned by the VS endpoint.
    """
    pdf_stem = _pdf_stem(result.get("pdf_name", ""))
    page = result.get("page_number")
    if page is None:
        return False
    page_hits = gt_entry.get("page_hits", {})
    cited_pages_for_pdf = page_hits.get(pdf_stem)
    if not cited_pages_for_pdf:
        return False
    # Cited page must fall within [page_number, page_number + PAGE_WINDOW]
    return any(page <= cp <= page + PAGE_WINDOW for cp in cited_pages_for_pdf)


def check_match_text(result: Dict, gt_entry: Dict) -> bool:
    """True if chunk_text contains any GT snippet (NFKC + alpha-only two-pass)."""
    chunk_text = result.get("chunk_text", "")
    return any(snippet_in_text(s, chunk_text) for s in gt_entry.get("snippets", []))


def check_match(result: Dict, gt_entry: Optional[Dict]) -> bool:
    """
    Less-strict hit: page-based match (PDF name + page window) OR
    text-snippet match (NFKC + alpha-only normalisation).
    """
    if not gt_entry:
        return False
    return check_match_page(result, gt_entry) or check_match_text(result, gt_entry)


# ===================================================================== #
#  EVALUATION LOOP                                                        #
# ===================================================================== #

def evaluate_all(
    max_k: int = 20,
    max_issues: int = None,
    include_criteria: bool = False,
) -> pd.DataFrame:
    """
    Run full evaluation.

        Makes four VS calls per (serial, issue) pair:
            - ANN without reranking
            - ANN with reranking
            - HYBRID without reranking
            - HYBRID with reranking
        Each call requests *max_k* results, then slices
    the ordered result list at every k=1..max_k to compute metrics.

    Args:
        max_k: Maximum k to evaluate (metrics computed for k=1..max_k).
        max_issues: If set, limit evaluation to the first N issues (useful
                    for quick smoke tests). None = all issues.

    Returns the raw DataFrame (also saved to disk).
    """
    query_variant = (
        "issue_prompt_plus_criteria_0_4"
        if include_criteria
        else "issue_prompt_only"
    )
    queries = load_queries(include_criteria=include_criteria)
    if max_issues is not None:
        queries = queries[:max_issues]
    gt, serials = load_ground_truth()

    # Build lookup: normalised issue_name → query dict
    query_by_issue = {q["issue_name"]: q for q in queries}

    # Only evaluate serials that appear in BOTH the GT and the query set
    gt_issue_names = {issue for (issue, _) in gt.keys()}
    total_pairs = len(serials) * len([q for q in queries if q["issue_name"] in gt_issue_names])
    eval_configs = [
        {"mode": "ann_retrieval", "query_type": "ANN", "use_reranking": False},
        {"mode": "ann_reranking", "query_type": "ANN", "use_reranking": True},
        {"mode": "hybrid_retrieval", "query_type": "HYBRID", "use_reranking": False},
        {"mode": "hybrid_reranking", "query_type": "HYBRID", "use_reranking": True},
    ]
    print(
        f"Evaluation: {len(serials)} ESNs x {len(queries)} issues "
        f"= {total_pairs} relevant pairs (x {len(eval_configs)} modes)  [GT from {CITATIONS_FILE.name}]",
        flush=True,
    )
    print(f"Query variant: {query_variant}", flush=True)

    # ── Diagnostic probe ─────────────────────────────────────────────────────
    # Query the index WITHOUT any filter to verify data exists and reveal
    # what generator_serial values are actually stored (may differ from GT).
    print("\n[DIAGNOSTIC] Probing VS index (no filter)...", flush=True)
    try:
        _probe = _query_rest(
            query_text="insulation resistance test",
            serial=None,           # no filter
            num_results=10,
        )
        if _probe:
            _serials_seen = sorted(
                {r.get("generator_serial") or "NULL" for r in _probe}
            )
            _null_count = sum(1 for r in _probe if not r.get("generator_serial"))
            print(f"[DIAGNOSTIC] Index returned {len(_probe)} chunks (unfiltered). "
                  f"generator_serial values seen: {_serials_seen}  "
                  f"(NULL/empty: {_null_count}/{len(_probe)})", flush=True)
            _r0 = _probe[0]
            print(f"[DIAGNOSTIC] Sample chunk keys: {list(_r0.keys())}", flush=True)
            print(f"[DIAGNOSTIC] Sample row: serial={_r0.get('generator_serial','?')}  "
                  f"pdf={_r0.get('pdf_name','?')}  page={_r0.get('page_number','?')}",
                  flush=True)
        else:
            print("[DIAGNOSTIC] WARNING: unfiltered query returned 0 results — "
                  "index may be empty or sync is pending.", flush=True)
    except Exception as _probe_err:
        print(f"[DIAGNOSTIC] probe failed: {_probe_err}", flush=True)

    # Also test one filtered query and log the raw status
    print(f"\n[DIAGNOSTIC] Probing with filter generator_serial={serials[0]}...", flush=True)
    try:
        _filtered = _query_rest(
            query_text="insulation resistance test",
            serial=serials[0],
            num_results=5,
        )
        print(f"[DIAGNOSTIC] Filtered query returned {len(_filtered)} chunks.", flush=True)
    except Exception as _fe:
        print(f"[DIAGNOSTIC] filtered probe failed: {_fe}", flush=True)
    print("", flush=True)
    # ─────────────────────────────────────────────────────────────────────────

    all_rows: List[Dict] = []
    done = 0
    eval_start = time.time()

    for s_idx, serial in enumerate(serials, 1):
        serial_start = time.time()
        serial_evaluated = 0
        serial_skipped = 0

        for q in queries:
            issue = q["issue_name"]
            prompt = q["issue_prompt"]
            gt_entry = gt.get((issue, serial))

            done += 1

            if gt_entry is None:
                serial_skipped += 1
                continue

            serial_evaluated += 1

            # ------ Four calls: ANN/HYBRID x reranking on/off ------
            for cfg in eval_configs:
                mode = cfg["mode"]
                query_type = cfg["query_type"]
                use_rr = cfg["use_reranking"]

                try:
                    results = query_vs(
                        query_text=prompt,
                        serial=serial,
                        num_results=max_k,
                        query_type=query_type,
                        use_reranking=use_rr,
                    )
                except Exception as e:
                    logger.error(f"    QUERY FAILED [{mode} | {serial}/{issue[:30]}]: {e}")
                    results = []

                # Pre-compute per-result match flags
                # Hit = page-based (PDF name + page window) OR text-snippet (NFKC)
                match_flags = [
                    check_match(r, gt_entry)
                    for r in results
                ]

                # Evaluate at each k
                cumulative_matches = 0
                for k in range(1, max_k + 1):
                    if k <= len(match_flags) and match_flags[k - 1]:
                        cumulative_matches += 1

                    recall = 1.0 if cumulative_matches > 0 else 0.0
                    precision = cumulative_matches / k

                    all_rows.append(
                        {
                            "serial": serial,
                            "issue_name": issue,
                            "query_variant": query_variant,
                            "mode": mode,
                            "query_type": query_type,
                            "reranking": use_rr,
                            "k": k,
                            "num_returned": len(results),
                            "matches_in_top_k": cumulative_matches,
                            "recall_at_k": recall,
                            "precision_at_k": precision,
                            "gt_citation_count": len(gt_entry.get("snippets", [])),
                        }
                    )

                # Small pause between VS calls to be polite
                time.sleep(0.2)

        # Per-serial progress line
        elapsed = time.time() - eval_start
        serial_time = time.time() - serial_start
        avg_per_pair = elapsed / max(done, 1)
        remaining = avg_per_pair * (total_pairs - done)
        print(
            f"  [{s_idx}/{len(serials)}] {serial}: "
            f"{serial_evaluated} evaluated, {serial_skipped} skipped "
            f"({serial_time:.0f}s) | "
            f"Overall {done}/{total_pairs} pairs, "
            f"~{remaining/60:.0f}min remaining",
            flush=True,
        )

    total_time = time.time() - eval_start
    print(f"\nEvaluation queries complete ({total_time:.0f}s)", flush=True)

    # ----- persist -----
    df = pd.DataFrame(all_rows, columns=RAW_RESULT_COLUMNS)
    if df.empty:
        print(
            "[EVALUATION] No evaluable (issue, ESN) pairs were produced. "
            "The pipeline data loaded successfully, but the heat map query set "
            "did not overlap with the ground-truth citation pairs used by evaluation.",
            flush=True,
        )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    raw_path = RESULTS_DIR / f"eval_raw_{query_variant}_{ts}.csv"
    df.to_csv(str(raw_path), index=False)
    print(f"Raw results -> {raw_path}", flush=True)

    summary = _compute_summary(df)
    sum_path = RESULTS_DIR / f"eval_summary_{query_variant}_{ts}.csv"
    summary.to_csv(str(sum_path), index=False)
    print(f"Summary     -> {sum_path}", flush=True)

    # Expose paths to notebook callers without changing return type.
    df.attrs["raw_path"] = str(raw_path)
    df.attrs["summary_path"] = str(sum_path)
    df.attrs["query_variant"] = query_variant

    _print_summary(df)
    return df


# ===================================================================== #
#  SUMMARY / REPORTING                                                    #
# ===================================================================== #

def _compute_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Average metrics grouped by (mode, k)."""
    if df.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    group_cols = ["mode", "k"]
    if "query_variant" in df.columns:
        group_cols = ["query_variant", *group_cols]
    return (
        df.groupby(group_cols)
        .agg(
            n_queries=("serial", "count"),
            avg_recall=("recall_at_k", "mean"),
            avg_precision=("precision_at_k", "mean"),
            total_matches=("matches_in_top_k", "sum"),
        )
        .reset_index()
    )


def _print_summary(df: pd.DataFrame):
    """Pretty-print summary to cell output."""
    if df.empty:
        print("No results to summarise")
        return

    n_pairs = df[["serial", "issue_name"]].drop_duplicates().shape[0]
    query_variant = "unknown"
    if "query_variant" in df.columns and not df["query_variant"].empty:
        query_variant = str(df["query_variant"].iloc[0])
    print(f"\n{'=' * 72}")
    print(f"EVALUATION SUMMARY   ({n_pairs} evaluated query-serial pairs)")
    print(f"QUERY VARIANT        {query_variant}")
    print(f"{'=' * 72}")

    mode_order = (
        "ann_retrieval",
        "ann_reranking",
        "hybrid_retrieval",
        "hybrid_reranking",
    )
    for mode in mode_order:
        mdf = df[df["mode"] == mode]
        if mdf.empty:
            continue
        print(f"\n  {mode.upper()}:")
        print(f"  {'k':>3s}  {'Recall@K':>10s}  {'Precision@K':>12s}")
        print(f"  {'---':>3s}  {'--------':>10s}  {'-----------':>12s}")
        for k in (1, 3, 5, 10, 15, 20):
            kdf = mdf[mdf["k"] == k]
            if kdf.empty:
                continue
            r = kdf["recall_at_k"].mean()
            p = kdf["precision_at_k"].mean()
            print(f"  {k:3d}  {r:10.4f}  {p:12.4f}")

    print(f"\n{'=' * 72}", flush=True)


# ===================================================================== #
#  ENTRY POINT                                                            #
# ===================================================================== #

if __name__ == "__main__":
    evaluate_all(max_k=20)
