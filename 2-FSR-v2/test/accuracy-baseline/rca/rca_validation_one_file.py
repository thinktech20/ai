# Databricks notebook source
# MAGIC %md
# MAGIC # FSR v2 RCA Validation for One PDF
# MAGIC
# MAGIC This notebook compares extraction + preprocessing behavior for one file across:
# MAGIC - `pdfplumber` extraction (pipeline-like)
# MAGIC - `PyPDF2` extraction (DS-Guru standard-like)
# MAGIC - `PyMuPDF` (`fitz`) extraction (DS-Guru page-by-page-like, if installed)
# MAGIC
# MAGIC And runs two preprocessors:
# MAGIC - Active shared preprocessor (`pw_sdg_ai_ser_repo/common/fsr_v2/preprocessor.py`)
# MAGIC - Vince reference preprocessor (`2-FSR-v2/analysis/preprocessor_v2_final.py`)
# MAGIC
# MAGIC It prints intermediate counters that matter for RCA:
# MAGIC - `full_text` length
# MAGIC - page count
# MAGIC - detected boundary count (debug approximation using preprocessor constants)
# MAGIC - final region count
# MAGIC - region distribution by `(primary_esn, primary_equip_type)`
# MAGIC
# MAGIC Run all cells top-to-bottom and share the final summary tables/output.

# COMMAND ----------

# Databricks one-time setup for this notebook session.
# Run this cell first, then restart Python and run all cells.

%pip install -q pandas pdfplumber PyPDF2 pypdf PyMuPDF

# COMMAND ----------

from __future__ import annotations

import importlib.util
import json
import re
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

# -------------------------
# USER CONFIG
# -------------------------
PDF_PATH = Path('/Volumes/viud/ing_ud_fieldvision/fv_field_service_report/fcb1511e-596a-4a56-b151-1e596afa569c')

# If left as None, defaults to preprocessor files in the same folder as this notebook.
ACTIVE_PREPROCESSOR_PATH = None
VINCE_PREPROCESSOR_PATH = None

# Optional output folder for JSON debug artifacts
OUTPUT_DIR = Path('./rca_validation_outputs')


def _detect_notebook_dir_fallback() -> Path:
    """Best-effort notebook directory detection for Databricks and local runs."""
    # Databricks workspace notebook path -> /Workspace/... filesystem path
    try:
        nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
        # Example notebookPath: /Users/.../2-FSR-v2/test/accuracy-baseline/rca/rca_validation_one_file
        ws_dir = Path('/Workspace') / str(nb_path).lstrip('/')
        return ws_dir.parent
    except Exception:
        pass

    # Local fallback
    return Path.cwd()


def _default_paths(notebook_dir: Path) -> tuple[Path, Path]:
    active = (notebook_dir / 'preprocessor.py').resolve()
    vince = (notebook_dir / 'preprocessor_v2_final.py').resolve()
    return active, vince


NOTEBOOK_DIR = _detect_notebook_dir_fallback()
if ACTIVE_PREPROCESSOR_PATH is None or VINCE_PREPROCESSOR_PATH is None:
    d_active, d_vince = _default_paths(NOTEBOOK_DIR)

ACTIVE_PREPROCESSOR_PATH = Path(ACTIVE_PREPROCESSOR_PATH) if ACTIVE_PREPROCESSOR_PATH else d_active
VINCE_PREPROCESSOR_PATH = Path(VINCE_PREPROCESSOR_PATH) if VINCE_PREPROCESSOR_PATH else d_vince

print('NOTEBOOK_DIR:', NOTEBOOK_DIR)
print('PDF_PATH:', PDF_PATH)
print('ACTIVE_PREPROCESSOR_PATH:', ACTIVE_PREPROCESSOR_PATH, 'exists=', ACTIVE_PREPROCESSOR_PATH.exists())
print('VINCE_PREPROCESSOR_PATH:', VINCE_PREPROCESSOR_PATH, 'exists=', VINCE_PREPROCESSOR_PATH.exists())

# COMMAND ----------

# -------------------------
# Helpers: dynamic import, extraction, context build
# -------------------------

def load_module_from_path(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load module from path: {module_path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_import_pdfplumber():
    import pdfplumber
    return pdfplumber


def safe_import_pypdf2():
    try:
        from PyPDF2 import PdfReader
        return PdfReader
    except ModuleNotFoundError:
        from pypdf import PdfReader
        return PdfReader


def safe_import_fitz():
    import fitz
    return fitz


def extract_pdfplumber(pdf_path: Path) -> dict[str, Any]:
    pdfplumber = safe_import_pdfplumber()
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ''
            pages.append(txt.strip())

    full_text = '\n\n'.join(pages)
    return {'pages': pages, 'full_text': full_text}


def extract_pypdf2(pdf_path: Path) -> dict[str, Any]:
    PdfReader = safe_import_pypdf2()
    reader = PdfReader(str(pdf_path))
    pages = []
    for p in reader.pages:
        txt = p.extract_text() or ''
        pages.append(txt)

    full_text = '\n\n'.join(pages)
    return {'pages': pages, 'full_text': full_text}


def extract_fitz(pdf_path: Path) -> dict[str, Any]:
    fitz = safe_import_fitz()
    doc = fitz.open(str(pdf_path))
    pages = []
    try:
        for i in range(len(doc)):
            txt = doc[i].get_text() or ''
            pages.append(txt)
    finally:
        doc.close()

    full_text = '\n\n'.join(pages)
    return {'pages': pages, 'full_text': full_text}


def build_page_offsets(pages: list[str]) -> list[dict[str, int]]:
    offsets = []
    cursor = 0
    sep_len = 2  # join separator '\n\n'
    for i, p in enumerate(pages):
        start = cursor
        end = start + len(p)
        offsets.append({'page_number': i + 1, 'start': start, 'end': end})
        cursor = end + sep_len
    return offsets


@dataclass
class Ctx:
    filename: str
    pages: list[str]
    page_offsets: list[dict[str, int]]
    full_text: str
    fields: list[dict[str, str]]


DEFAULT_FIELDS = [
    {'name': 'document_name'},
    {'name': 'gt_esn'},
    {'name': 'gen_esn'},
    {'name': 'inactive_esns'},
    {'name': 'primary_esn'},
    {'name': 'primary_equip_type'},
    {'name': 'primary_technology_code'},
    {'name': 'outage_start_date'},
    {'name': 'outage_end_date'},
    {'name': 'report_issued_date'},
]


def build_ctx(pdf_path: Path, pages: list[str], full_text: str) -> Ctx:
    return Ctx(
        filename=pdf_path.name,
        pages=pages,
        page_offsets=build_page_offsets(pages),
        full_text=full_text,
        fields=DEFAULT_FIELDS,
    )


def estimate_boundaries(preproc_module: Any, full_text: str, gen_esn: str | None, gt_esn: str | None):
    # Mirrors the boundary scan logic in preprocess to get a comparable count.
    header_pat = getattr(preproc_module, 'HEADER', None)
    if not header_pat:
        return []

    section_hdr = r'(?im)^\s*#{0,3}\s*\d+[ \t]+(GAS\s+TURBINE|TURBINE|GENERATOR|STEAM\s+TURBINE|EXCITER)\s*$'

    def _canon(name: str) -> str:
        n = name.strip().lower()
        if 'generator' in n:
            return 'Generator'
        if 'exciter' in n:
            return 'Exciter'
        if 'steam' in n:
            return 'Steam Turbine'
        return 'Gas Turbine'

    bounds = []
    for m in re.finditer(header_pat, full_text, re.I):
        bounds.append((m.start(), m.group(1).title(), m.group(2).upper().strip()))

    for m in re.finditer(section_hdr, full_text):
        t = _canon(m.group(1))
        e = gen_esn if t in ('Generator', 'Exciter') else (gt_esn if t == 'Gas Turbine' else None)
        bounds.append((m.start(), t, e))

    # Subsection patterns used in v2 fix path
    subsec_gen = r'(?m)^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?) Generator\b'
    subsec_gt = r'(?m)^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?) (?:Turbine|Compressor|Combustion|Inlet)\b'
    gen_sub = [(m.start(), m.group(1)) for m in re.finditer(subsec_gen, full_text)]
    gt_sub = [(m.start(), m.group(1)) for m in re.finditer(subsec_gt, full_text)]
    if gen_sub and gen_esn:
        for gs_pos, _ in gen_sub:
            end_pos = len(full_text)
            for gt_pos, _ in gt_sub:
                if gt_pos > gs_pos:
                    end_pos = gt_pos
                    break
            bounds.append((gs_pos, 'Generator', gen_esn))
            if end_pos < len(full_text):
                bounds.append((end_pos, 'Gas Turbine', gt_esn))

    bounds.sort(key=lambda x: x[0])
    return bounds


def count_regions_by_key(regions: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in regions:
        md = r.get('metadata', {})
        key = f"{md.get('primary_esn')}|{md.get('primary_equip_type')}"
        out[key] = out.get(key, 0) + 1
    return out


def extract_primary_esns_from_doc(doc_md: dict[str, Any]):
    return doc_md.get('gen_esn'), doc_md.get('gt_esn')


active_mod = load_module_from_path('active_preprocessor', ACTIVE_PREPROCESSOR_PATH)
vince_mod = load_module_from_path('vince_preprocessor', VINCE_PREPROCESSOR_PATH)
print('Loaded preprocessors OK.')

# COMMAND ----------

# -------------------------
# Run validation for one PDF
# -------------------------

if not ACTIVE_PREPROCESSOR_PATH.exists() or not VINCE_PREPROCESSOR_PATH.exists():
    raise FileNotFoundError(
        'Preprocessor file not found. Check NOTEBOOK_DIR and preprocessor paths.\n'
        f'active={ACTIVE_PREPROCESSOR_PATH}\n'
        f'vince={VINCE_PREPROCESSOR_PATH}'
    )

if not PDF_PATH.exists():
    raise FileNotFoundError(
        f'Update PDF_PATH first. File not found: {PDF_PATH.resolve()}'
    )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

extractors: dict[str, Callable[[Path], dict[str, Any]]] = {
    'pdfplumber': extract_pdfplumber,
    'pypdf2': extract_pypdf2,
}

failures: list[dict[str, str]] = []

try:
    _ = safe_import_fitz()
    extractors['fitz'] = extract_fitz
except Exception as e:
    failures.append({'stage': 'import', 'extractor': 'fitz', 'preprocessor': '', 'error': repr(e), 'traceback': traceback.format_exc(limit=3)})
    print(f'fitz unavailable, skipping fitz extraction: {e}')

preprocessors = {
    'active_shared': active_mod,
    'vince_reference': vince_mod,
}

rows = []
detailed = {}

for ext_name, extractor in extractors.items():
    try:
        extraction = extractor(PDF_PATH)
    except Exception as e:
        failures.append({'stage': 'extractor', 'extractor': ext_name, 'preprocessor': '', 'error': repr(e), 'traceback': traceback.format_exc(limit=6)})
        print(f'Extractor failed: {ext_name} -> {e}')
        continue

    pages = extraction['pages']
    full_text = extraction['full_text']

    for prep_name, prep_mod in preprocessors.items():
        try:
            ctx = build_ctx(PDF_PATH, pages, full_text)
            out = prep_mod.preprocess(ctx)
            doc_md = out.get('metadata', {}) or {}
            regions = out.get('regions', []) or []

            gen_esn, gt_esn = extract_primary_esns_from_doc(doc_md)
            bounds = estimate_boundaries(prep_mod, full_text, gen_esn, gt_esn)

            region_key_counts = count_regions_by_key(regions)

            row = {
                'extractor': ext_name,
                'preprocessor': prep_name,
                'pages': len(pages),
                'full_text_len': len(full_text),
                'boundary_count_est': len(bounds),
                'region_count': len(regions),
                'primary_esn': doc_md.get('primary_esn'),
                'primary_equip_type': doc_md.get('primary_equip_type'),
                'gt_esn': doc_md.get('gt_esn'),
                'gen_esn': doc_md.get('gen_esn'),
                'region_key_counts': json.dumps(region_key_counts, sort_keys=True),
            }
            rows.append(row)

            detailed_key = f'{ext_name}__{prep_name}'
            detailed[detailed_key] = {
                'doc_metadata': doc_md,
                'hints': out.get('hints'),
                'region_count': len(regions),
                'region_key_counts': region_key_counts,
                'first_10_boundaries': bounds[:10],
                'first_10_regions': regions[:10],
            }

            with open(OUTPUT_DIR / f'{detailed_key}.json', 'w', encoding='utf-8') as f:
                json.dump(detailed[detailed_key], f, indent=2)

        except Exception as e:
            failures.append({'stage': 'preprocessor', 'extractor': ext_name, 'preprocessor': prep_name, 'error': repr(e), 'traceback': traceback.format_exc(limit=6)})
            print(f'Preprocessor failed: extractor={ext_name}, preprocessor={prep_name} -> {e}')

if not rows:
    if failures:
        print('\nFailure diagnostics (table):')
        display(pd.DataFrame(failures)[['stage', 'extractor', 'preprocessor', 'error']])
        print('\nFailure diagnostics (plain text):')
        for i, f in enumerate(failures, start=1):
            print(f"[{i}] stage={f.get('stage')} extractor={f.get('extractor')} preprocessor={f.get('preprocessor')}")
            print(f"    error={f.get('error')}")
            tb = f.get('traceback', '')
            if tb:
                print('    traceback:')
                for line in tb.splitlines():
                    print('      ' + line)
    raise RuntimeError(
        'No successful runs. Review failure diagnostics above. '
        'Most common fixes: (1) install pdfplumber/PyPDF2, '
        '(2) set absolute PDF_PATH, (3) verify preprocessor paths exist.'
    )

df = pd.DataFrame(rows).sort_values(['extractor', 'preprocessor']).reset_index(drop=True)
display(df)

pivot = df.pivot_table(
    index=['extractor'],
    values=['full_text_len', 'boundary_count_est', 'region_count'],
    aggfunc='first'
).reset_index()

print('\nQuick extraction-level comparison (first preprocessor view):')
display(pivot)

if failures:
    print('\nNon-blocking warnings/failures encountered:')
    display(pd.DataFrame(failures)[['stage', 'extractor', 'preprocessor', 'error']])

print('\nSaved detailed JSON files to:', OUTPUT_DIR.resolve())
print('Share df and pivot outputs + the JSON files if deeper diff is needed.')

# COMMAND ----------

# MAGIC %md
# MAGIC ## If imports fail
# MAGIC
# MAGIC Run this in a new code cell, then rerun all cells:
# MAGIC
# MAGIC ```python
# MAGIC %pip install pandas pdfplumber PyPDF2 PyMuPDF
# MAGIC ```
# MAGIC
# MAGIC Then restart Python (or detach/attach the notebook) and run the notebook again.
# MAGIC
# MAGIC For Databricks, also make sure `PDF_PATH` is an absolute path that exists on the cluster filesystem.