# Databricks notebook source
# ─────────────────────────────────────────────────────────────────────────────
# nb_chunker_compare — Side-by-side comparison: production vs new chunker
#
# Loads PDFs from ../test-pdfs/, runs both:
#   - OLD: production logic (PyMuPDF page concat + flat RecursiveCharacterTextSplitter)
#   - NEW: pw_sdg_ai_ser_repo/common/fsr_chunking.py (DS V3 hierarchical)
# and writes a comparison report to ../validation/output/.
#
# Run locally (python) or in Databricks. No table writes, no VS sync — read-only.
# ─────────────────────────────────────────────────────────────────────────────

# COMMAND ----------

# MAGIC %pip install --quiet pdfplumber PyMuPDF langchain-text-splitters

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import json
import sys
import time
from pathlib import Path

# Resolve repo paths (works locally; on Databricks, set REPO_ROOT env var)
import os
REPO_ROOT = Path(os.environ.get(
    "REPO_ROOT",
    "/home/u560060992/dbx",
)).resolve()

PDF_DIR    = REPO_ROOT / "implementation/design/chunking-fix/test-pdfs"
OUT_DIR    = REPO_ROOT / "implementation/design/chunking-fix/validation/output"
CHUNKER_LIB = REPO_ROOT / "pw_sdg_ai_ser_repo/common"

OUT_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(CHUNKER_LIB))

print(f"PDF dir : {PDF_DIR}")
print(f"Out dir : {OUT_DIR}")

# Same defaults as production
CHUNK_SIZE    = 4000
CHUNK_OVERLAP = 200

# COMMAND ----------

# ── Discover test PDFs ──────────────────────────────────────────────────────
# Volume files often have no .pdf extension (file ID = filename), so accept any
# regular file and verify it's a PDF by magic-number check.
def _is_pdf(p: Path) -> bool:
    if not p.is_file() or p.name.startswith("."):
        return False
    try:
        with open(p, "rb") as fh:
            return fh.read(5) == b"%PDF-"
    except Exception:
        return False

pdf_paths = sorted(p for p in PDF_DIR.iterdir() if _is_pdf(p))
print(f"Found {len(pdf_paths)} PDF(s):")
for p in pdf_paths:
    print(f"  {p.name}  ({p.stat().st_size / 1024:.0f} KB)")

if not pdf_paths:
    print("\nNo PDFs found — drop test files into test-pdfs/ and rerun.")

# COMMAND ----------

# ── OLD chunker — verbatim copy of production logic ────────────────────────
import fitz
from langchain_text_splitters import RecursiveCharacterTextSplitter

_old_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
    length_function=len,
)


def chunk_old(pdf_path: str):
    """Production chunker: PyMuPDF per-page extract → concat → flat split."""
    doc = fitz.open(pdf_path)
    try:
        total_pages = len(doc)
        pages = []
        for page_idx in range(total_pages):
            text = doc[page_idx].get_text()
            if text and text.strip():
                pages.append({"page_num": page_idx + 1, "text": text})
    finally:
        doc.close()

    if not pages:
        return [], {"total_pages": total_pages, "extracted_pages": 0, "total_chars": 0}

    full_text = ""
    page_spans = []
    for page in pages:
        start = len(full_text)
        full_text += page["text"] + "\n\n"
        end = len(full_text)
        page_spans.append((start, end, page["page_num"]))

    chunk_texts = _old_splitter.split_text(full_text)
    chunks = []
    search_from = 0
    for ci, ctext in enumerate(chunk_texts):
        idx = full_text.find(ctext, search_from)
        if idx == -1:
            idx = full_text.find(ctext.strip(), max(0, search_from - 200))
        if idx >= 0:
            c_start = idx
            c_end = idx + len(ctext)
            chunk_pages = [pn for (ps, pe, pn) in page_spans if ps < c_end and pe > c_start]
            search_from = idx + 1
        else:
            chunk_pages = [p["page_num"] for p in pages]
        start_page = min(chunk_pages) if chunk_pages else 1
        chunks.append({
            "chunk_index": ci,
            "chunk_text": ctext,
            "page_number": start_page,
        })

    stats = {
        "total_pages": total_pages,
        "extracted_pages": len(pages),
        "total_chars": sum(len(p["text"]) for p in pages),
    }
    return chunks, stats


# COMMAND ----------

# ── NEW chunker — ported DS V3 ─────────────────────────────────────────────
import fsr_chunking  # noqa: E402  (sys.path was set above)


def chunk_new(pdf_path: str):
    """New chunker: DS V3 hierarchical."""
    snapshot = fsr_chunking.load_pdf_snapshot(pdf_path)
    chunks = fsr_chunking.hierarchical_semantic_chunking_from_snapshot(
        snapshot,
        pdf_path,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        verbose=False,
        split_subsections=True,
    )
    # Mirror old format keys for easy comparison while keeping the rich metadata
    flat = []
    for ci, ch in enumerate(chunks):
        m = ch.get("metadata", {})
        flat.append({
            "chunk_index": ci,
            "chunk_text": ch.get("text", ""),
            "start_page": m.get("start_page"),
            "end_page": m.get("end_page"),
            "section_1": m.get("section_1"),
            "section_2": m.get("section_2"),
            "section_3": m.get("section_3"),
            "section_4": m.get("section_4"),
            "section_5": m.get("section_5"),
        })

    # Document-level stats from the snapshot
    total_pages = len(snapshot)
    total_chars = sum(len(fsr_chunking.page_text_from_snapshot(p)) for p in snapshot)
    stats = {
        "total_pages": total_pages,
        "extracted_pages": total_pages,  # V3 reads all then filters internally
        "total_chars": total_chars,
    }
    return flat, stats


# COMMAND ----------

# ── Per-doc metrics ─────────────────────────────────────────────────────────
import statistics


def chunk_size_stats(chunks):
    sizes = [len(c["chunk_text"]) for c in chunks]
    if not sizes:
        return {"n": 0, "min": 0, "p25": 0, "p50": 0, "p75": 0, "p95": 0, "max": 0, "mean": 0, "total": 0}
    sizes_sorted = sorted(sizes)
    def pct(p):
        k = max(0, min(len(sizes_sorted) - 1, int(round(p / 100 * (len(sizes_sorted) - 1)))))
        return sizes_sorted[k]
    return {
        "n": len(sizes),
        "min": min(sizes),
        "p25": pct(25),
        "p50": pct(50),
        "p75": pct(75),
        "p95": pct(95),
        "max": max(sizes),
        "mean": round(statistics.mean(sizes), 1),
        "total": sum(sizes),
    }


def section_coverage(new_chunks):
    """% of new chunks that have at least section_1 populated."""
    if not new_chunks:
        return 0.0
    n_with_section = sum(1 for c in new_chunks if c.get("section_1"))
    return round(100 * n_with_section / len(new_chunks), 1)


def page_range_breadth(new_chunks):
    """Avg (end_page - start_page + 1) across chunks — how many pages a chunk spans."""
    spans = [
        (c["end_page"] - c["start_page"] + 1)
        for c in new_chunks
        if c.get("start_page") is not None and c.get("end_page") is not None
    ]
    if not spans:
        return None
    return round(statistics.mean(spans), 2)


# COMMAND ----------

# ── Run comparison ──────────────────────────────────────────────────────────
results = []

for pdf_path in pdf_paths:
    name = pdf_path.name
    print(f"\n=== {name} ===")
    row = {"pdf": name, "size_kb": round(pdf_path.stat().st_size / 1024)}

    # OLD
    try:
        t0 = time.time()
        old_chunks, old_stats = chunk_old(str(pdf_path))
        old_elapsed = time.time() - t0
        old_sz = chunk_size_stats(old_chunks)
        row.update({
            "old_pages": old_stats["total_pages"],
            "old_text_chars": old_stats["total_chars"],
            "old_n_chunks": old_sz["n"],
            "old_chunk_p50": old_sz["p50"],
            "old_chunk_p95": old_sz["p95"],
            "old_chunk_max": old_sz["max"],
            "old_total_chars": old_sz["total"],
            "old_elapsed_s": round(old_elapsed, 2),
            "old_error": None,
        })
        print(f"  OLD: {old_sz['n']} chunks, p50={old_sz['p50']}, max={old_sz['max']}, {old_elapsed:.1f}s")
    except Exception as e:
        row.update({"old_error": str(e)[:200]})
        old_chunks = []
        print(f"  OLD: FAILED — {e}")

    # NEW
    try:
        t0 = time.time()
        new_chunks, new_stats = chunk_new(str(pdf_path))
        new_elapsed = time.time() - t0
        new_sz = chunk_size_stats(new_chunks)
        row.update({
            "new_pages": new_stats["total_pages"],
            "new_text_chars": new_stats["total_chars"],
            "new_n_chunks": new_sz["n"],
            "new_chunk_p50": new_sz["p50"],
            "new_chunk_p95": new_sz["p95"],
            "new_chunk_max": new_sz["max"],
            "new_total_chars": new_sz["total"],
            "new_section_coverage_pct": section_coverage(new_chunks),
            "new_avg_page_span": page_range_breadth(new_chunks),
            "new_elapsed_s": round(new_elapsed, 2),
            "new_error": None,
        })
        print(f"  NEW: {new_sz['n']} chunks, p50={new_sz['p50']}, max={new_sz['max']}, "
              f"section_cov={row['new_section_coverage_pct']}%, "
              f"avg_page_span={row['new_avg_page_span']}, {new_elapsed:.1f}s")
    except Exception as e:
        row.update({"new_error": str(e)[:200]})
        new_chunks = []
        print(f"  NEW: FAILED — {e}")

    # Text-loss check (NEW total_chars vs OLD total_chars)
    if row.get("old_total_chars") and row.get("new_total_chars"):
        loss_pct = round(100 * (1 - row["new_total_chars"] / row["old_total_chars"]), 1)
        row["text_loss_pct_new_vs_old"] = loss_pct
        flag = " ⚠️" if loss_pct > 10 else ""
        print(f"  Text loss (NEW vs OLD chunked chars): {loss_pct}%{flag}")

    # Persist per-doc chunk dumps for manual inspection
    stem = pdf_path.stem
    (OUT_DIR / f"{stem}__old.json").write_text(json.dumps(old_chunks, indent=2, ensure_ascii=False))
    (OUT_DIR / f"{stem}__new.json").write_text(json.dumps(new_chunks, indent=2, ensure_ascii=False))

    results.append(row)

# COMMAND ----------

# ── Summary report ──────────────────────────────────────────────────────────
import csv

summary_path = OUT_DIR / "comparison_summary.csv"
if results:
    keys = sorted({k for r in results for k in r.keys()})
    with summary_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(results)
    print(f"\nSummary written: {summary_path}")
else:
    print("\nNo results to write.")

# COMMAND ----------

# ── Quick console summary ───────────────────────────────────────────────────
print("\n" + "=" * 80)
print(f"{'PDF':<40} {'OLD#':>6} {'NEW#':>6} {'Δ%':>7} {'sec%':>6} {'loss%':>7}")
print("-" * 80)
for r in results:
    pdf = r["pdf"][:38]
    on = r.get("old_n_chunks") or 0
    nn = r.get("new_n_chunks") or 0
    delta = round(100 * (nn - on) / on, 1) if on else None
    sec = r.get("new_section_coverage_pct")
    loss = r.get("text_loss_pct_new_vs_old")
    print(f"{pdf:<40} {on:>6} {nn:>6} {str(delta) + '%' if delta is not None else '—':>7} "
          f"{str(sec) + '%' if sec is not None else '—':>6} "
          f"{str(loss) + '%' if loss is not None else '—':>7}")
print("=" * 80)
