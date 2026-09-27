"""Stage 2 — Document Parsing.

Extracts raw text from a PDF using pypdf2.
Returns per-page text and char-offset map needed by the preprocessor.

Input:  document reference dict (document_id, volume_path)
Output: ParsedDocument dataclass with full_text, pages, page_offsets
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("fsr.v2.parsing")

_PAGE_NUM_RE = re.compile(r"\bpage\s*\d+\s*(of|/)\s*\d+\b", re.IGNORECASE)
_LEGAL_RE = re.compile(
    r"proprietary and confidential|all rights reserved"
    r"|no part of this document may be|shall not be used or disclosed"
    r"|reproduced.*transmitted.*stored|expressed? written consent"
    r"|not to be copied, reproduced or distributed without"
    r"|confidential and proprietary information subject to a confidentiality agreement"
    r"|unauthorized export or re-export"
    r"|information contained in this document may also be controlled by the us export control laws"
    r"|general electric international|general electric company"
    r"|\u00a9\s*general electric",
    re.IGNORECASE,
)
_HEADING_NUMBERED_RE = re.compile(r"^(\d+\.[\d.]*|[A-Z]\.[\d.]*)\s+\S")
_HEADING_GUARD_RE = re.compile(r"^(form|page|revision|rev|copyright|confidential)$", re.IGNORECASE)
_TOC_MARKER_RE = re.compile(r"^table\s+of\s+contents\b", re.IGNORECASE)
_TOC_LINE_RE = re.compile(
    r"(_{3,}|\.{3,}|\b\d{1,4}\s*$|^[\d\s]{3,}$"
    r"|^(summary|technical|components|appendix|attachments?)\b)",
    re.IGNORECASE,
)


@dataclass
class ParsedDocument:
    document_id: str
    filename: str
    volume_path: str
    full_text: str
    parser_version: str = ""
    parsed_volume_path: str = ""
    pages: list[str] = field(default_factory=list)         # cleaned per-page text
    raw_pages: list[str] = field(default_factory=list)     # raw per-page text from parser
    page_offsets: list[dict] = field(default_factory=list) # [{start: int, end: int}, ...]


def parse(doc: dict) -> ParsedDocument:
    """Compatibility wrapper — delegates to parse_pymupdf()."""
    return parse_pymupdf(doc)


def extract_page1_text(volume_path: str) -> str:
    """Read only page 1's text.

    Retained as a utility for targeted diagnostics or a future dedicated
    date-scoped backfill. The incremental P1 path does not call it.
    """
    import fitz  # noqa: PLC0415

    pdf = fitz.open(volume_path)
    try:
        if pdf.page_count == 0:
            return ""
        return pdf[0].get_text("text") or ""
    finally:
        pdf.close()


def build_parsed_volume_path(parsed_root: str, document_id: str, parser_version: str) -> str:
    # parsed_root already includes the parser version directory
    return f"{parsed_root.rstrip('/')}/{document_id}.json"


def save_parsed_document(parsed_doc: ParsedDocument, parsed_root: str, parser_version: str) -> ParsedDocument:
    """Persist ParsedDocument to a volume-backed parsed.json path and return updated doc."""
    if not parsed_root:
        return parsed_doc

    target_path = Path(build_parsed_volume_path(parsed_root, parsed_doc.document_id, parser_version))
    payload = {
        "document_id": parsed_doc.document_id,
        "filename": parsed_doc.filename,
        "volume_path": parsed_doc.volume_path,
        "parser": parser_version,
        "pages": parsed_doc.pages,
        "raw_pages": parsed_doc.raw_pages,
        "page_offsets": parsed_doc.page_offsets,
    }
    target_path.write_text(json.dumps(payload), encoding="utf-8")
    parsed_doc.parsed_volume_path = str(target_path)
    parsed_doc.parser_version = parser_version
    return parsed_doc


def load_parsed_document(parsed_volume_path: str) -> ParsedDocument:
    try:
        payload = json.loads(Path(parsed_volume_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Corrupt or partial parsed JSON at {parsed_volume_path}: {exc}") from exc
    pages = list(payload.get("pages") or [])
    page_offsets = list(payload.get("page_offsets") or [])
    full_text = "\n".join(pages)
    return ParsedDocument(
        document_id=payload.get("document_id") or Path(parsed_volume_path).stem,
        filename=payload.get("filename") or "",
        volume_path=payload.get("volume_path") or "",
        full_text=full_text,
        parser_version=payload.get("parser") or "",
        parsed_volume_path=parsed_volume_path,
        pages=pages,
        raw_pages=list(payload.get("raw_pages") or pages),
        page_offsets=page_offsets,
    )


def _normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


_DOC_DATE_RE = re.compile(
    r"(outage\s+start\s+date|job\s+start\s+date|approved\s+date|report\s+issued)"
    r".{0,80}?(20\d{2}|19\d{2})",
    re.IGNORECASE,
)

# Maps the page-1 regex label back to the metadata column it corresponds to, so a
# year found by the page-1 scan reports the same provenance vocabulary as
# determine_doc_date().
_PAGE1_LABEL_TO_FIELD = {
    "outage start date": "outage_start_date",
    "job start date": "job_start_date",
    "approved date": "approved_date",
    "report issued": "report_issued_date",
}


def extract_doc_year_with_source_from_page1(text: str) -> tuple[int | None, str | None]:
    """Scan page-1 text for a known date label; return (year, source_field)."""
    m = _DOC_DATE_RE.search(text or "")
    if not m:
        return None, None
    try:
        year = int(m.group(2))
    except (ValueError, IndexError):
        return None, None
    label = _normalize_line(m.group(1)).lower()
    return year, _PAGE1_LABEL_TO_FIELD.get(label, label.replace(" ", "_"))


def extract_doc_year_from_page1(text: str) -> int | None:
    """Scan page-1 text for any known date label and return the 4-digit year."""
    return extract_doc_year_with_source_from_page1(text)[0]


# Backward-compat alias used by existing callers.
extract_outage_year_from_page1 = extract_doc_year_from_page1


def determine_doc_date(
    outage_start_date: str | None,
    job_start_date: str | None,
    approved_date: str | None,
    report_issued_date: str | None = None,
) -> tuple[str | None, str]:
    """Return (date_str, source_label) using priority: outage > job > approved > report_issued."""
    for value, label in [
        (outage_start_date,  "outage_start_date"),
        (job_start_date,     "job_start_date"),
        (approved_date,      "approved_date"),
        (report_issued_date, "report_issued_date"),
    ]:
        v = (value or "").strip()
        if v:
            return v, label
    return None, "missing"


def _is_boilerplate_line(text: str, repeated: set[str]) -> bool:
    if not text:
        return True
    if _PAGE_NUM_RE.search(text):
        return True
    if _LEGAL_RE.search(text):
        return True
    return text in repeated


def _is_toc_like_line(text: str) -> bool:
    if not text:
        return False
    if _TOC_LINE_RE.search(text):
        return True

    # Typical TOC rows like "1.2 Work Scope ______ 42".
    if re.search(r"^\d+(?:\.\d+){0,3}\s+.+(?:_{3,}|\.{3,}).*\d+\s*$", text):
        return True
    return False


def _strip_toc_block(page_text: str) -> str:
    lines = (page_text or "").splitlines()
    if not lines:
        return ""

    cleaned: list[str] = []
    in_toc = False
    non_toc_streak = 0

    for raw_line in lines:
        norm = _normalize_line(raw_line)
        if not norm:
            if not in_toc:
                cleaned.append(raw_line)
            continue

        if _TOC_MARKER_RE.match(norm):
            in_toc = True
            non_toc_streak = 0
            continue

        if in_toc:
            if _is_toc_like_line(norm):
                non_toc_streak = 0
                continue

            # Require a couple of non-TOC lines before leaving TOC mode.
            non_toc_streak += 1
            if non_toc_streak < 2:
                continue
            in_toc = False

        cleaned.append(raw_line)

    return "\n".join(cleaned).strip()


def _compute_repeated_edge_lines(pages: list[str]) -> set[str]:
    """Detect repeated header/footer-like lines using page edge line windows.

    pypdf2 does not provide positional coordinates in this path, so we approximate
    header/footer zones by looking at the first/last few non-empty lines per page.
    """
    line_pages: dict[str, set[int]] = {}
    for page_idx, page_text in enumerate(pages):
        lines = [_normalize_line(ln) for ln in (page_text or "").splitlines()]
        lines = [ln for ln in lines if ln]
        if not lines:
            continue

        edge_lines = lines[:3] + lines[-3:]
        for line in edge_lines:
            line_pages.setdefault(line, set()).add(page_idx)

    live = max(1, len(pages))
    thresh = max(5, int(live * 0.20))
    return {line for line, idxs in line_pages.items() if len(idxs) >= thresh}


def _suppress_boilerplate_pages(pages: list[str]) -> list[str]:
    repeated = _compute_repeated_edge_lines(pages)
    cleaned_pages: list[str] = []

    for page_text in pages:
        page_text = _strip_toc_block(page_text)
        kept: list[str] = []
        for raw_line in (page_text or "").splitlines():
            norm = _normalize_line(raw_line)
            if _is_boilerplate_line(norm, repeated):
                continue
            kept.append(raw_line)
        cleaned_pages.append("\n".join(kept).strip())

    return cleaned_pages


def _looks_like_numbered_heading(stripped: str) -> bool:
    if len(stripped) >= 100:
        return False
    if _is_toc_like_line(stripped):
        return False
    if not _HEADING_NUMBERED_RE.match(stripped):
        return False
    return stripped[-1] not in ".?!"


def _looks_like_upper_heading(stripped: str, next_line: str) -> bool:
    if not (3 < len(stripped) < 80):
        return False
    # Bullet-prefixed lines (•, -, *) are list items, not section headings.
    if stripped[0] in "\u2022\u2023\u25e6\u2043-*\u2013\u2014":
        return False
    if stripped.endswith(".") or not stripped.isupper():
        return False

    words = [w for w in re.split(r"\s+", stripped) if w]
    if not (2 <= len(words) <= 8):
        return False
    if _HEADING_GUARD_RE.match(stripped):
        return False
    if _is_toc_like_line(stripped):
        return False

    # Favor uppercase lines that are followed by substantive body text.
    next_norm = _normalize_line(next_line)
    if not next_norm:
        return False
    return len(next_norm) >= 40


def _inject_pdf_heading_markers(page_text: str) -> str:
    """Heuristically prepend markdown heading markers to heading-like lines.

    Mirrors DS-Guru's `_inject_pdf_heading_markers` in `ds-guru/app/main.py`
    exactly so that the text fed to the preprocessor matches DS-Guru's
    representation. This affects sub-section boundary detection: numbered
    section headings and ALL-CAPS lines get a `## ` / `### ` prefix which
    suppresses the preprocessor's SUBSEC_GEN / SUBSEC_GT regex patterns
    (anchored at ``^\\d``) — producing coarser, DS-Guru-aligned region output.

    To revert: remove the `_inject_pdf_heading_markers(page_text)` call in
    `parse_pypdf2` and change the page separator back to `"\n\n".join(pages)`
    with `sum(len(p) + 2 ...)` offsets.
    """
    lines = page_text.split('\n')
    result = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        if stripped.startswith('#'):
            result.append(line)
            continue

        is_heading = False
        level = "## "

        if _looks_like_numbered_heading(stripped):
            is_heading = True
            if stripped.split()[0].count('.') >= 2:
                level = "### "
        else:
            next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
            if _looks_like_upper_heading(stripped, next_line):
                is_heading = True

        if is_heading and not _HEADING_GUARD_RE.match(stripped):
            is_heading = True

        if is_heading:
            result.append(level + stripped)
        else:
            result.append(line)
    return '\n'.join(result)


def parse_pymupdf(doc: dict) -> ParsedDocument:
    """Open the PDF at doc['volume_path'] and extract text via PyMuPDF."""
    import fitz  # noqa: PLC0415

    document_id = doc["document_id"]
    volume_path = doc["volume_path"]
    filename = Path(volume_path).name

    raw_pages: list[str] = []
    pages: list[str] = []
    page_offsets: list[dict] = []

    pdf = fitz.open(volume_path)
    try:
        for page in pdf:
            raw_pages.append(page.get_text("text") or "")
    finally:
        pdf.close()

    cleaned_pages = _suppress_boilerplate_pages(raw_pages)
    for page_text in cleaned_pages:
        if page_text:
            page_text = _inject_pdf_heading_markers(page_text)
        start = sum(len(p) + 1 for p in pages)
        end = start + len(page_text)
        pages.append(page_text)
        page_offsets.append({"start": start, "end": end})

    full_text = "\n".join(pages)

    log.info(f"  [PARSED/pymupdf] {document_id[:40]}  pages={len(pages)}  chars={len(full_text)}")

    return ParsedDocument(
        document_id=document_id,
        filename=filename,
        volume_path=volume_path,
        full_text=full_text,
        parser_version="pymupdf_v1.0",
        pages=pages,
        raw_pages=raw_pages,
        page_offsets=page_offsets,
    )
