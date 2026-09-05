"""
PDF Processing – Databricks
Reads PDFs from Unity Catalog volumes and returns chunk payloads for the main
pipeline to write into Delta.
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import fitz  # PyMuPDF – already available on the cluster

from config import ChunkingConfig, chunking_config
from esn_identifier import (
    analyze_prepared_document_text_for_esn_counts,
    load_document_text_for_esn,
    prepare_document_text_for_esn,
)
from pymupdf_guard import hold_pymupdf_lock
from utils import setup_logger, count_tokens
from recursive_chunking_v3 import (
    document_text_from_snapshot,
    hierarchical_semantic_chunking_from_pdf,
    hierarchical_semantic_chunking_from_snapshot,
    load_pdf_snapshot,
    page_text_from_snapshot,
)

logger = setup_logger("pdf_processor")


# ============================================================================
# ESN EXTRACTION FROM RAW PDF (cover / front-matter page)
# ============================================================================

# Regex patterns for ESN, ordered by specificity.
# The cover page typically contains key:value pairs like "ESN: 290T658".
# Some FSRs use "ESN/SY: 297837 | SY0069758" format where ESN is before the pipe.
_ESN_PATTERNS = [
    # "ESN/SY: 297837 | SY0069758" → capture the first alphanumeric token after ':'
    re.compile(r'\bESN/SY\s*:\s*([A-Z0-9]{4,12})\b', re.IGNORECASE),
    # "ESN: 290T658" or "ESN : 290T658"
    re.compile(r'\bESN\s*[:=]\s*([A-Z0-9]{4,12})\b', re.IGNORECASE),
    # "Equipment Serial Number: 337X233"
    re.compile(r'Equipment\s+Serial\s+(?:Number|No\.?)\s*[:=]\s*([A-Z0-9]{4,12})\b', re.IGNORECASE),
    # "Serial Number: 761X004" or "Serial No.: 850096"
    re.compile(r'Serial\s+(?:Number|No\.?)\s*[:=]\s*([A-Z0-9]{4,12})\b', re.IGNORECASE),
    # "Generator Serial: 290T658"
    re.compile(r'Generator\s+Serial\s*[:=]\s*([A-Z0-9]{4,12})\b', re.IGNORECASE),
    # "Unit Serial Number: 337X380"
    re.compile(r'Unit\s+Serial\s+(?:Number|No\.?)\s*[:=]\s*([A-Z0-9]{4,12})\b', re.IGNORECASE),
    # "GAS TURBINE (297837 | SY0069758)" → section header with ESN in parens
    re.compile(r'GAS\s+TURBINE\s*\(\s*([A-Z0-9]{4,12})\b', re.IGNORECASE),
]

# Pattern that a valid ESN token must satisfy when parsed from a filename.
# Must be 4-12 chars, start with a digit or uppercase letter, no pure-numeric
# strings longer than 8 digits (avoids matching dates like '20140716').
_FILENAME_ESN_RE = re.compile(r'^[A-Z0-9]{4,12}$', re.IGNORECASE)
_DATE_RE = re.compile(r'^\d{6,}$')  # avoid matching date-only tokens


def _extract_esn_from_filename(pdf_path: str) -> Optional[str]:
    """Last-resort ESN extraction from the PDF filename itself.

    Some non-standard FSRs (Flux Probe, Robotic, HNI Test, Rotor Out) have no
    ESN on their cover pages, but the serial is embedded at the start of the
    filename, e.g. '337X380 2014-07-16 Robotic.pdf'.  We split on spaces and
    underscores, and accept the first token that looks like an ESN.
    """
    stem = Path(pdf_path).stem
    # Split on spaces and underscores to get tokens
    tokens = re.split(r'[\s_]+', stem)
    for token in tokens:
        token = token.strip()
        if _FILENAME_ESN_RE.match(token) and not _DATE_RE.match(token):
            return token.upper()
        # After the first non-ESN-looking token, stop — the serial is always first
        break
    return None


def _extract_esn_from_pdf(pdf_path: str) -> Optional[str]:
    """Open the raw PDF and extract ESN from the first 2 pages (cover / title).

    The recursive chunker deliberately skips front-matter pages, so the ESN
    that lives on the cover page never appears in chunk text.  This function
    reads the raw PDF independently, extracts text from pages 0-1, and
    applies the same regex patterns used elsewhere.

    Returns the first matched ESN string, or None.
    """
    try:
        with hold_pymupdf_lock():
            doc = fitz.open(pdf_path)
            try:
                # Scan the first 2 pages (cover + possible TOC with header info)
                pages_to_scan = min(2, len(doc))
                text_parts = []
                for page_idx in range(pages_to_scan):
                    text_parts.append(doc[page_idx].get_text())
            finally:
                doc.close()

        combined_text = "\n".join(text_parts)

        for pattern in _ESN_PATTERNS:
            m = pattern.search(combined_text)
            if m:
                esn = m.group(1).strip().upper()
                return esn
    except Exception as e:
        logger.debug(f"[ESN-PDF] Failed to extract ESN from {Path(pdf_path).name}: {e}")

    return None


def _extract_esn_from_snapshot(snapshot: List[Dict[str, object]]) -> Optional[str]:
    """Extract ESN from the first 2 pages of an already-loaded PDF snapshot."""
    try:
        combined_text = "\n".join(
            page_text_from_snapshot(snapshot[page_idx])
            for page_idx in range(min(2, len(snapshot)))
        )

        for pattern in _ESN_PATTERNS:
            m = pattern.search(combined_text)
            if m:
                return m.group(1).strip().upper()
    except Exception:
        pass

    return None


def process_single_pdf_from_snapshot(
    pdf_path: str,
    snapshot: List[Dict[str, object]],
    config: ChunkingConfig,
) -> Tuple[str, List[Dict], Dict]:
    """Chunk one PDF using a preloaded snapshot. Returns (doc_id, chunks, stats)."""
    doc_id = Path(pdf_path).stem

    esn = _extract_esn_from_snapshot(snapshot)
    if esn:
        logger.debug(f"  [ESN-PDF] {doc_id}: extracted ESN = {esn} (from PDF cover)")
    else:
        esn = _extract_esn_from_filename(pdf_path)
        if esn:
            logger.debug(f"  [ESN-PDF] {doc_id}: extracted ESN = {esn} (from filename)")
        else:
            logger.debug(f"  [ESN-PDF] {doc_id}: no ESN found on cover page or filename")

    chunks = hierarchical_semantic_chunking_from_snapshot(
        snapshot,
        pdf_path,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        verbose=False,
        split_subsections=config.preserve_structure,
    )

    for i, chunk in enumerate(chunks):
        chunk.setdefault("metadata", {})
        chunk["metadata"]["document_id"] = doc_id
        chunk["metadata"]["chunk_index"] = i
        chunk["metadata"]["chunk_size"]  = len(chunk.get("text", ""))
        chunk["metadata"]["token_count"] = count_tokens(chunk.get("text", ""))
        if esn:
            chunk["metadata"]["generator_serial"] = esn

    stats = {
        "chunk_count":  len(chunks),
        "total_chars":  sum(len(c.get("text", "")) for c in chunks),
        "total_tokens": sum(c["metadata"].get("token_count", 0) for c in chunks),
    }
    return doc_id, chunks, stats


# ============================================================================
# SINGLE PDF
# ============================================================================

def process_single_pdf(pdf_path: str, config: ChunkingConfig) -> Tuple[str, List[Dict], Dict]:
    """Chunk one PDF. Returns (doc_id, chunks, stats)."""
    snapshot = load_pdf_snapshot(pdf_path)
    return process_single_pdf_from_snapshot(pdf_path, snapshot, config)


def process_single_pdf_with_background_doc_analysis(
    pdf_path: str,
    config: ChunkingConfig,
    doc_analysis_fn: Optional[Callable[[str], Dict[str, int]]] = None,
    chunk_fn: Optional[Callable[[str, ChunkingConfig], Tuple[str, List[Dict], Dict]]] = None,
    text_loader_fn: Optional[Callable[[str], str]] = None,
) -> Tuple[str, List[Dict], Dict, Dict[str, int], Dict[str, float]]:
    """Load a PDF once, prepare the LLM snippet, then overlap the call with chunking."""
    doc_analysis_fn = doc_analysis_fn or analyze_prepared_document_text_for_esn_counts
    text_loader_fn = text_loader_fn or load_document_text_for_esn

    use_single_snapshot = chunk_fn is None and text_loader_fn is load_document_text_for_esn

    text_started_at = time.time()
    prepared_document_text = ""
    snapshot = None
    try:
        if use_single_snapshot:
            snapshot = load_pdf_snapshot(pdf_path)
            document_text = document_text_from_snapshot(snapshot)
        else:
            document_text = text_loader_fn(pdf_path)
        prepared_document_text = prepare_document_text_for_esn(document_text)
    except Exception as exc:
        logger.debug(
            "  [ESN-TEXT] %s: skipping doc-level analysis (%s)",
            Path(pdf_path).name,
            exc,
        )
    text_elapsed = time.time() - text_started_at

    def _run_doc_analysis(prepared_text: str) -> Tuple[Dict[str, int], float]:
        started_at = time.time()
        counts = doc_analysis_fn(prepared_text)
        return counts, time.time() - started_at

    executor = None
    doc_future = None
    if prepared_document_text:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="doc-esn")
        doc_future = executor.submit(_run_doc_analysis, prepared_document_text)

    try:
        chunk_started_at = time.time()
        if use_single_snapshot and snapshot is not None:
            doc_id, chunks, stats = process_single_pdf_from_snapshot(pdf_path, snapshot, config)
        else:
            active_chunk_fn = chunk_fn or process_single_pdf
            doc_id, chunks, stats = active_chunk_fn(pdf_path, config)
        chunk_elapsed = time.time() - chunk_started_at

        if doc_future is not None:
            doc_counts, doc_elapsed = doc_future.result()
        else:
            doc_counts, doc_elapsed = {}, 0.0

        return (
            doc_id,
            chunks,
            stats,
            doc_counts,
            {
                "chunk_elapsed": chunk_elapsed,
                "esn_elapsed": text_elapsed + doc_elapsed,
            },
        )
    except Exception:
        if doc_future is not None:
            doc_future.cancel()
        raise
    finally:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
