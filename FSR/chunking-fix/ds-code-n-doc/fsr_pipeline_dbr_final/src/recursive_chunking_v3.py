"""
Recursive chunking from raw PDF.

Level discovery is data-driven:
  1. Detect TOC pages -> extract entries with their x-position (indent)
     and numbering depth.  Indentation on the TOC page determines the
     level: leftmost indent -> L1, next indent -> L2, etc.
  2. Skip TOC + front-matter pages.
  3. Filter boilerplate (positional headers/footers + frequency-based).
  4. Classify content lines in two passes:
       Pass 1 - TOC match / numbering match  (primary)
       Pass 2 - font-size based detection    (fallback)
     Font levels are bootstrapped from pass-1 headers, so they stay
     consistent with the TOC hierarchy.
  5. Track section hierarchy recursively, chunk body text semantically.
"""

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import fitz  # PyMuPDF
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pymupdf_guard import hold_pymupdf_lock

MAX_LEVELS = 5
PageSnapshot = Dict[str, Any]
DocumentSnapshot = List[PageSnapshot]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    """Collapse whitespace to single spaces, strip."""
    return re.sub(r"\s+", " ", text or "").strip()


def _norm_key(text: str) -> str:
    """Normalised lookup key: lowercase, strip trailing colon/punctuation,
    collapse whitespace.  Used for fuzzy TOC matching."""
    t = normalize(text).lower()
    t = re.sub(r"[:;,.\s]+$", "", t)           # trailing punctuation
    t = re.sub(r"\s*[–—-]\s*", " - ", t)       # normalise dashes
    return t


def _numbering_depth(text: str) -> int:
    """Numbering depth of a text line.
    0 = unnumbered, 1 = '1 ...', 2 = '1.2 ...', 3 = '1.2.3 ...', etc.
    Requires >=2 alphabetic chars after the number to avoid matching
    measurements like '0.086 in'.
    Leading number parts must be <= 99 to avoid matching addresses/values."""
    m = re.match(r"^(\d+(?:\.\d+)*)\s+[A-Za-z]{2,}", text)
    if m:
        parts = m.group(1).split(".")
        if all(int(p) <= 99 for p in parts):
            return len(parts)
    return 0


def load_pdf_snapshot(pdf_path: str) -> DocumentSnapshot:
    """Load a PDF once and capture the page structure needed by the chunker."""
    with hold_pymupdf_lock():
        doc = fitz.open(pdf_path)
        try:
            snapshot: DocumentSnapshot = []
            for page in doc:
                page_dict = page.get_text("dict")
                snapshot.append({
                    "height": page.rect.height or 1.0,
                    "blocks": page_dict.get("blocks", []),
                })
            return snapshot
        finally:
            doc.close()


def page_text_from_snapshot(page: PageSnapshot) -> str:
    """Reconstruct page text from the captured text blocks."""
    lines: List[str] = []
    for block in page.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if text:
                lines.append(text)
    return "\n".join(lines)


def document_text_from_snapshot(snapshot: DocumentSnapshot) -> str:
    """Join all page texts from a captured snapshot into one document string."""
    return "\n\n".join(
        text
        for text in (page_text_from_snapshot(page) for page in snapshot)
        if text.strip()
    )



# ─────────────────────────────────────────────────────────────────────────────
# TOC detection
# ─────────────────────────────────────────────────────────────────────────────

def _is_toc_line(text: str) -> bool:
    """Does this line look like a TOC navigation entry?"""
    text = normalize(text)
    if not text:
        return False
    if re.search(r"\.{3,}\s*\d+\s*$", text):   return True   # dot leaders
    if re.search(r"_{3,}\s*\d+\s*$", text):     return True   # underscore leaders
    # "1.2 Some Title   45"
    if re.search(r"\s+\d{1,3}\s*$", text) and re.search(r"^\d+(?:\.\d+){0,3}\s+", text):
        return True
    return False


def detect_toc_pages(snapshot: DocumentSnapshot) -> Set[int]:
    toc_pages: Set[int] = set()
    for i, page in enumerate(snapshot):
        text = page_text_from_snapshot(page)
        if not text:
            continue
        lines = [normalize(ln) for ln in text.split("\n") if normalize(ln)]
        toc_hits = sum(1 for ln in lines if _is_toc_line(ln))
        if toc_hits >= 3 or any("table of contents" in ln.lower() for ln in lines):
            toc_pages.add(i)
    return toc_pages


def detect_front_matter(toc_pages: Set[int]) -> Set[int]:
    """All pages before the first TOC page are front-matter / cover pages."""
    if not toc_pages:
        return set()
    first_toc = min(toc_pages)
    return set(range(0, first_toc))


# ─────────────────────────────────────────────────────────────────────────────
# TOC entry extraction  →  {normalised_title: level}
# ─────────────────────────────────────────────────────────────────────────────

_NOISE_RE = re.compile(
    r"table of contents|confidential|proprietary|copyright"
    r"|shall not be used|not to be copied|express written"
    r"|disclosed in confidence|serial\s*#|page\s*\d"
    r"|gegege|ge vernova|ge power"
    r"|inspection.*life.*extension|life extension services"
    r"|southern california|public power|apex generating"
    r"|all rights reserved|no part of this document"
    r"|may be reproduced|ge compressor components",
    re.IGNORECASE,
)


def extract_toc_entries(
    snapshot: DocumentSnapshot, toc_pages: Set[int]
) -> Tuple[Dict[str, Tuple[int, str]], Dict[int, int]]:
    """Return ({norm_key: (level, original_title)}, num_depth_to_level).

    Two-pass approach:
      1. Collect every TOC entry with its x-position and numbering depth.
      2. Determine levels from *indentation* on the TOC page:
         leftmost indent -> L1, next indent -> L2, etc.
      3. Derive num_depth_to_level so numbered non-TOC lines can be classified.
    """
    # (norm_key, x-position, numbering_depth, original_clean)
    raw_entries: List[Tuple[str, float, int, str]] = []

    for page_num in toc_pages:
        page = snapshot[page_num]
        ph = page.get("height", 1.0) or 1.0

        for block in page.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                # skip positional headers/footers on TOC pages too
                bbox = line.get("bbox", (0, 0, 0, ph))
                y = bbox[1] / ph
                if y < 0.07 or y > 0.88:
                    continue

                x0 = bbox[0]  # left edge = indentation

                raw = normalize("".join(s.get("text", "") for s in spans))
                if len(raw) < 3:
                    continue

                # strip leader characters + trailing page number
                clean = re.sub(r"[_.]{3,}.*$", "", raw)
                clean = re.sub(r"\s+\d{1,3}\s*$", "", clean).strip()
                if len(clean) < 3:
                    continue

                if _NOISE_RE.search(clean):
                    continue
                if re.match(r"^[\d\s]+$", clean):
                    continue
                if re.match(r"^[A-Z]{4,}$", clean):     # "GEGEGE"
                    continue
                if not re.search(r"[A-Za-z]{2,}", clean):
                    continue

                depth = _numbering_depth(clean)
                key = _norm_key(clean)
                raw_entries.append((key, x0, depth, clean))

    if not raw_entries:
        return {}, {}

    # -- Second pass: indent -> level ------------------------------------------
    tolerance = 12.0   # points (~1/6 inch)
    x_bins = sorted(set(round(x / tolerance) for _, x, _, _ in raw_entries))
    bin_to_rank = {b: i for i, b in enumerate(x_bins)}

    entries: Dict[str, Tuple[int, str]] = {}
    depth_level_pairs: List[Tuple[int, int]] = []

    for key, x0, num_depth, orig in raw_entries:
        indent_bin = round(x0 / tolerance)
        level = min(bin_to_rank[indent_bin] + 1, MAX_LEVELS)
        entries[key] = (level, orig)
        if num_depth > 0:
            depth_level_pairs.append((num_depth, level))

    # Derive num_depth -> level from what we observed in the TOC
    dl: Dict[int, List[int]] = defaultdict(list)
    for nd, lvl in depth_level_pairs:
        dl[nd].append(lvl)
    num_depth_to_level = {nd: min(levels) for nd, levels in dl.items()}

    return entries, num_depth_to_level


# ─────────────────────────────────────────────────────────────────────────────
# Boilerplate detection
# ─────────────────────────────────────────────────────────────────────────────

_PAGE_NUM_RE = re.compile(r"\bpage\s*\d+\s*(of|/)\s*\d+\b", re.IGNORECASE)
_LEGAL_RE = re.compile(
    r"proprietary and confidential|all rights reserved"
    r"|no part of this document may be|shall not be used or disclosed"
    r"|reproduced.*transmitted.*stored|expressed? written consent"
    r"|general electric international|general electric company"
    r"|\u00a9\s*general electric",
    re.IGNORECASE,
)


def compute_repeated_lines(
    snapshot: DocumentSnapshot, skip_pages: Set[int]
) -> Set[str]:
    """Lines that appear on many pages in the header/footer zones → boilerplate.

    Only considers text blocks whose top edge is in the outer 10% / 10% of page
    height (y_block_top < 0.10 or y_block_bottom > 0.90).  Body-area text
    (blocks within 0.10–0.90) is NEVER treated as boilerplate even if it repeats
    — template-style FSR forms repeat column labels and test-section headers
    throughout the document body, and those are meaningful content, not running
    headers/footers.

    Uses get_text("blocks") (fast mode) rather than get_text("dict") to avoid
    doubling the per-page extraction cost.
    """
    line_pages: Dict[str, Set[int]] = defaultdict(set)
    for i, page in enumerate(snapshot):
        if i in skip_pages:
            continue
        ph = page.get("height", 1.0) or 1.0
        for block in page.get("blocks", []):
            if block.get("type") != 0:
                continue
            bbox = block.get("bbox", (0, 0, 0, ph))
            y_top = bbox[1] / ph
            y_bot = bbox[3] / ph
            # Only outer header/footer zones qualify as boilerplate candidates
            if not (y_top < 0.10 or y_bot > 0.90):
                continue
            for line in block.get("lines", []):
                t = normalize("".join(span.get("text", "") for span in line.get("spans", [])))
                if t:
                    line_pages[t].add(i)

    live = max(1, len(snapshot) - len(skip_pages))
    # Threshold: line must appear on >=20% of pages (min 5) to be boilerplate.
    thresh = max(5, int(live * 0.20))
    return {t for t, pages in line_pages.items() if len(pages) >= thresh}


def is_boilerplate(text: str, repeated: Set[str]) -> bool:
    if not text:
        return True
    if _PAGE_NUM_RE.search(text):
        return True
    if _LEGAL_RE.search(text):
        return True
    return text in repeated


# ─────────────────────────────────────────────────────────────────────────────
# Line extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_lines(
    snapshot: DocumentSnapshot,
    skip_pages: Set[int],
    repeated: Set[str],
) -> List[Dict[str, Any]]:
    """Return [{text, page, font_size, is_bold}, ...] for every non-boilerplate,
    non-positional-header/footer line on content pages."""
    lines: List[Dict[str, Any]] = []

    for page_num, page in enumerate(snapshot):
        if page_num in skip_pages:
            continue
        ph = page.get("height", 1.0) or 1.0

        for block in page.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                text = normalize("".join(s.get("text", "") for s in spans))
                if not text:
                    continue

                # positional filter: running header / footer zone
                # Only apply when y is within [0, 1]; rotated/transformed
                # content can have y outside this range and should be kept.
                y = line.get("bbox", (0, 0, 0, ph))[1] / ph
                if 0 <= y <= 1 and (y < 0.04 or y > 0.92):
                    continue

                if is_boilerplate(text, repeated):
                    continue

                # dominant font size (weighted by character count)
                total_chars = 0
                weighted_size = 0.0
                bold_chars = 0
                for s in spans:
                    n = len(s.get("text", ""))
                    weighted_size += s.get("size", 0) * n
                    total_chars += n
                    # flags bit 4 (16) indicates bold
                    if s.get("flags", 0) & 16:
                        bold_chars += n
                font_size = round(weighted_size / total_chars, 1) if total_chars else 0
                is_bold = bold_chars > total_chars * 0.5  # majority bold

                lines.append({"text": text, "page": page_num, "font_size": font_size, "is_bold": is_bold})

    return lines


# ─────────────────────────────────────────────────────────────────────────────
# Classify: header vs body (contextual recursive approach)
# ─────────────────────────────────────────────────────────────────────────────

def _is_likely_header(ln: Dict[str, Any], body_font: float) -> bool:
    """Is this line likely a header based on font properties?
    Only called at section boundaries (first line of a section)."""
    fs = ln.get("font_size", 0)
    is_bold = ln.get("is_bold", False)
    text = ln["text"]
    num_depth = _numbering_depth(text)
    
    # Must have alphabetic content
    if not re.search(r"[A-Za-z]{2,}", text):
        return False
    
    # Must have reasonable length
    # Too short -> likely a label or table cell, not a section header
    # Single words or very short phrases are rarely section headers
    if len(text) < 8:
        return False
    
    # Too long -> likely body paragraph
    if len(text) > 120:
        return False
    
    # Very small fonts never headers
    if fs <= body_font:
        return False
    
    # Strong indicators of header:
    # 1. Very large font (>=body+5, e.g. 9pt body -> 14pt+ headers)
    if fs >= body_font + 5:
        return True
    
    # 2. Numbered AND larger font (>=body+2)
    if num_depth > 0 and fs >= body_font + 2:
        return True
    
    # 3. Bold AND significantly larger (>=body+3)
    if is_bold and fs >= body_font + 3:
        return True
    
    # Otherwise not a header (conservative)
    return False


def _header_signature(ln: Dict[str, Any]) -> Tuple[float, bool, int]:
    """Return (font_size, is_bold, numbering_depth) for sibling matching."""
    return (
        round(ln.get("font_size", 0), 1),
        ln.get("is_bold", False),
        _numbering_depth(ln["text"])
    )


def _are_siblings(
    sig1: Tuple[float, bool, int],
    sig2: Tuple[float, bool, int],
) -> bool:
    """Do these two signatures indicate sibling headers?"""
    fs1, bold1, depth1 = sig1
    fs2, bold2, depth2 = sig2
    
    # Font size within 0.5pt
    if abs(fs1 - fs2) > 0.5:
        return False
    
    # Bold must match
    if bold1 != bold2:
        return False
    
    # If both numbered, depths must match
    if depth1 > 0 and depth2 > 0:
        return depth1 == depth2
    
    return True


def _assign_level_from_metadata(
    ln: Dict[str, Any],
    toc_entries: Dict[str, Tuple[int, str]],
    num_depth_to_level: Dict[int, int],
) -> Optional[int]:
    """Try to assign level from TOC or numbering metadata."""
    text = ln["text"]
    key = _norm_key(text)
    
    # 1. Exact TOC match
    if key in toc_entries:
        return toc_entries[key][0]
    
    # 2. Substring TOC match
    for toc_key, (toc_lvl, _) in toc_entries.items():
        if len(toc_key) >= 15 and key.startswith(toc_key):
            remaining = key[len(toc_key):]
            if remaining and remaining[0] != ' ':
                continue
            if len(remaining) <= 40:
                return toc_lvl
    
    # 3. Numbering depth
    num_depth = _numbering_depth(text)
    if num_depth > 0 and num_depth in num_depth_to_level:
        return num_depth_to_level[num_depth]
    
    return None


def classify_lines(
    lines: List[Dict[str, Any]],
    toc_entries: Dict[str, Tuple[int, str]],
    num_depth_to_level: Dict[int, int],
) -> List[Dict[str, Any]]:
    """Classify lines using contextual recursive approach.
    
    Algorithm:
      1. Compute body font (mode)
      2. Start at first line: is it a header? (evaluate contextually)
      3. If yes: scan forward for siblings (same signature), mark as L1
      4. Within each L1 section: is first line a header?
         - If yes: recurse to find L2 siblings
         - If no: everything is body until next L1 sibling
      5. Use TOC/numbering metadata to refine levels
      6. Everything else = body
    """
    
    # -- Step 1: Compute body font ---------------------------------------------
    font_sizes = [ln.get("font_size", 0) for ln in lines if ln.get("font_size", 0) > 0]
    if not font_sizes:
        for ln in lines:
            ln["is_header"] = False
            ln["level"] = None
        return lines
    
    rounded = [round(fs) for fs in font_sizes]
    body_font = max(set(rounded), key=rounded.count)
    
    # -- Step 2: Contextual recursive scan -------------------------------------
    def scan_section(start_idx: int, end_idx: int, parent_level: int) -> None:
        """Recursively scan a section [start_idx, end_idx).
        
        Check if first line is a header. If yes, find siblings and recurse.
        If no, everything is body."""
        
        if start_idx >= end_idx:
            return
        
        # Skip already-classified lines at the start
        while start_idx < end_idx and "level" in lines[start_idx]:
            start_idx += 1
        
        if start_idx >= end_idx:
            return
        
        # Evaluate first unclassified line: is it a header?
        first_line = lines[start_idx]
        meta_level = _assign_level_from_metadata(first_line, toc_entries, num_depth_to_level)
        is_header_by_meta = meta_level is not None
        if not is_header_by_meta and not _is_likely_header(first_line, body_font):
            # NOT a header -> everything in this section is body
            for i in range(start_idx, end_idx):
                if "level" not in lines[i]:
                    lines[i]["is_header"] = False
                    lines[i]["level"] = None
            return
        
        # YES, it's a header -> establish signature and find siblings
        sig = _header_signature(first_line)
        current_level = meta_level if meta_level is not None else min(parent_level + 1, MAX_LEVELS)
        
        siblings = [start_idx]
        section_start = start_idx + 1
        
        i = start_idx + 1
        while i < end_idx:
            # Skip already-classified
            if "level" in lines[i]:
                i += 1
                continue
            
            # Check if this is a sibling (contextually: is it a likely header
            # with same signature?)
            sibling_meta_level = _assign_level_from_metadata(lines[i], toc_entries, num_depth_to_level)
            is_header_candidate = (
                _is_likely_header(lines[i], body_font)
                or sibling_meta_level == current_level
            )
            if is_header_candidate and _are_siblings(sig, _header_signature(lines[i])):
                # Process subsection before this sibling
                if section_start < i:
                    scan_section(section_start, i, current_level)
                
                siblings.append(i)
                section_start = i + 1
            
            i += 1
        
        # Process final subsection after last sibling
        if section_start < end_idx:
            scan_section(section_start, end_idx, current_level)
        
        # Mark all siblings at current_level
        for idx in siblings:
            lines[idx]["is_header"] = True
            lines[idx]["level"] = current_level
    
    # Start from the beginning
    scan_section(0, len(lines), 0)
    
    # -- Step 3: Refine levels using TOC/numbering metadata --------------------
    for ln in lines:
        if ln.get("is_header"):
            # Try to get better level from TOC/numbering
            meta_level = _assign_level_from_metadata(ln, toc_entries, num_depth_to_level)
            if meta_level is not None:
                ln["level"] = meta_level
    
    # Mark any remaining unclassified lines as body
    for ln in lines:
        if "is_header" not in ln:
            ln["is_header"] = False
            ln["level"] = None

    # -- Step 4: Demote headers on all-header pages --------------------------
    # If a page has ONLY header lines (zero body), demote lines that are NOT
    # in the TOC and have no section numbering to body.  This prevents pages
    # of short descriptive lines from being entirely swallowed as headers.
    page_lines: Dict[int, List[int]] = defaultdict(list)
    for i, ln in enumerate(lines):
        page_lines[ln["page"]].append(i)

    for pg, idxs in page_lines.items():
        n_body = sum(1 for i in idxs if not lines[i]["is_header"])
        # Skip pages where body already makes up >= 20% of lines
        if n_body / max(len(idxs), 1) >= 0.20:
            continue
        # All or nearly-all lines on this page are headers — demote non-TOC ones
        for i in idxs:
            ln = lines[i]
            # Quick checks: keep as header if in TOC or has section numbering
            key = _norm_key(ln["text"])
            if key in toc_entries or _numbering_depth(ln["text"]) > 0:
                continue
            ln["is_header"] = False
            ln["level"] = None

    return lines


# ─────────────────────────────────────────────────────────────────────────────
# Hierarchy tracking
# ─────────────────────────────────────────────────────────────────────────────

def build_hierarchy(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Walk classified lines, track the current section at each level,
    and attach section_1..section_5 metadata to body lines."""
    hierarchy: List[Dict[str, Any]] = []
    current: Dict[int, Optional[str]] = {i: None for i in range(1, MAX_LEVELS + 1)}

    def _strip_section_number(text: str) -> str:
        """Remove leading section numbers like '1.2.3 ' from text."""
        return re.sub(r"^(?:\d+\.)*\d+\s+", "", text)

    for ln in lines:
        if ln["is_header"]:
            level = ln["level"]
            # Strip leading numbering from header text when storing in hierarchy
            current[level] = _strip_section_number(ln["text"])
            for deeper in range(level + 1, MAX_LEVELS + 1):
                current[deeper] = None
            hierarchy.append({
                "type": "header",
                "level": level,
                "text": ln["text"],
                "page": ln["page"] + 1,
            })
        else:
            hierarchy.append({
                "type": "body",
                "text": ln["text"],
                "page": ln["page"] + 1,
                **{f"section_{i}": current[i] for i in range(1, MAX_LEVELS + 1)},
            })

    return hierarchy


# ─────────────────────────────────────────────────────────────────────────────
# Semantic chunking  (langchain RecursiveCharacterTextSplitter)
# ─────────────────────────────────────────────────────────────────────────────

def semantic_chunk(
    text: str,
    chunk_size: int = 3500,
    chunk_overlap: int = 200,
) -> List[str]:
    """Split *text* into chunks using langchain's RecursiveCharacterTextSplitter."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    return splitter.split_text(text)


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def hierarchical_semantic_chunking_from_snapshot(
    snapshot: DocumentSnapshot,
    pdf_path: str,
    chunk_size: int = 3500,
    chunk_overlap: int = 200,
    verbose: bool = True,
    split_subsections: bool = True,
) -> List[Dict[str, Any]]:

    # ── 1. Structural detection ───────────────────────────────────────────────
    toc_pages    = detect_toc_pages(snapshot)
    front_matter = detect_front_matter(toc_pages)
    skip_pages   = toc_pages | front_matter
    toc_entries, num_depth_to_level = extract_toc_entries(snapshot, toc_pages)
    repeated     = compute_repeated_lines(snapshot, skip_pages)

    if verbose:
        print(f"  TOC pages (0-indexed): {sorted(toc_pages)}")
        print(f"  Front-matter pages:    {sorted(front_matter)}")
        print(f"  Skip pages:            {sorted(skip_pages)}")
        print(f"  Repeated lines:        {len(repeated)}")
        print(f"  Num-depth-to-level:    {num_depth_to_level}")
        print(f"  TOC entries ({len(toc_entries)}):")
        for title, (lvl, orig) in sorted(toc_entries.items(), key=lambda x: (x[1][0], x[0])):
            print(f"    L{lvl}  {orig}")

    # ── 2. Extract, classify, build hierarchy ─────────────────────────────────
    lines     = extract_lines(snapshot, skip_pages, repeated)
    lines     = classify_lines(lines, toc_entries, num_depth_to_level)
    hierarchy = build_hierarchy(lines)

    headers = [ln for ln in lines if ln["is_header"]]
    if verbose:
        print(f"\n  Content lines:         {len(lines)}")
        print(f"  Headers detected:      {len(headers)}")

    # ── 3. Group body text by section path ────────────────────────────────────
    sections: Dict[Tuple, List[Tuple[str, int]]] = defaultdict(list)
    for item in hierarchy:
        if item["type"] != "body":
            continue
        
        # If split_subsections is False, only use top-level (L1) section
        # Otherwise use full hierarchy
        if split_subsections:
            key = tuple(item.get(f"section_{i}") for i in range(1, MAX_LEVELS + 1))
        else:
            # Only use the first (L1) section, ignore subsections
            key = (item.get("section_1"), None, None, None, None)
        
        sections[key].append((item["text"], item["page"]))

    # ── 3b. Inject pre-TOC (front matter) and TOC as sections ─────────────
    def _page_text_items(page_set: Set[int]) -> List[Tuple[str, int]]:
        """Extract (text, 1-based-page) pairs from a set of 0-based pages."""
        items: List[Tuple[str, int]] = []
        for pg in sorted(page_set):
            text = normalize(page_text_from_snapshot(snapshot[pg]))
            if text and len(text) >= 20:
                items.append((text, pg + 1))  # convert to 1-based
        return items

    if front_matter:
        fm_items = _page_text_items(front_matter)
        if fm_items:
            fm_key = ("Front Matter",) + (None,) * (MAX_LEVELS - 1)
            sections[fm_key] = fm_items

    if toc_pages:
        toc_items = _page_text_items(toc_pages)
        if toc_items:
            toc_key = ("Table of Contents",) + (None,) * (MAX_LEVELS - 1)
            sections[toc_key] = toc_items

    # ── 4. Semantic chunking ──────────────────────────────────────────────────
    chunks: List[Dict[str, Any]] = []
    for key, body_items in sections.items():
        texts = [t for t, _ in body_items]
        pages = [p for _, p in body_items]
        raw = normalize(" ".join(texts))
        if not raw:
            continue

        _line_spans: List[Tuple[int, int, int]] = []
        _pos = 0
        for _t, _pg in body_items:
            _normed = normalize(_t)
            _line_spans.append((_pos, _pos + len(_normed), _pg))
            _pos += len(_normed) + 1

        chunk_texts = semantic_chunk(raw, chunk_size, chunk_overlap)
        n_chunks = len(chunk_texts)

        _search_from = 0
        for ci, text in enumerate(chunk_texts):
            _idx = raw.find(text, _search_from)
            if _idx == -1:
                _idx = raw.find(text.strip(), _search_from)
            if _idx != -1:
                _c_start = _idx
                _c_end = _idx + len(text)
                _chunk_pages = [pg for (s, e, pg) in _line_spans
                                if s < _c_end and e > _c_start]
                _search_from = _idx + 1
            else:
                _chunk_pages = []

            if _chunk_pages:
                cp_start = min(_chunk_pages)
                cp_end = max(_chunk_pages)
            else:
                cp_start = min(pages)
                cp_end = max(pages)

            chunks.append({
                "text": text,
                "metadata": {
                    "document_title": pdf_path,
                    **{f"section_{i}": key[i - 1] for i in range(1, MAX_LEVELS + 1)},
                    "chunk_index": ci,
                    "chunk_count": n_chunks,
                    "start_page": cp_start,
                    "end_page": cp_end,
                    "document_extension": ".pdf",
                },
            })

    chunks = [ch for ch in chunks if len(ch["text"]) >= 20]
    return chunks


def hierarchical_semantic_chunking_from_pdf(
    pdf_path: str,
    chunk_size: int = 3500,
    chunk_overlap: int = 200,
    verbose: bool = True,
    split_subsections: bool = True,
) -> List[Dict[str, Any]]:
    snapshot = load_pdf_snapshot(pdf_path)
    return hierarchical_semantic_chunking_from_snapshot(
        snapshot,
        pdf_path,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        verbose=verbose,
        split_subsections=split_subsections,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pdf_path = (
        r"C:\Users\560060297\Downloads\Recursive_Chunking\Recursive_Chunking"
        r"\FSR_Databricks\00004423-9ebe-46e9-ac88-b0d096699d3d.pdf"
    )
    out_path = (
        r"C:\Users\560060297\Downloads\Recursive_Chunking\Recursive_Chunking"
        r"\00004423-9ebe-46e9-ac88-b0d096699d3d_recursive_chunks_from_pdf.json"
    )

    print(f"Processing: {pdf_path}\n")
    result = hierarchical_semantic_chunking_from_pdf(pdf_path)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\nDone — {len(result)} chunks → {out_path}")

    # ── Quick summary ─────────────────────────────────────────────────────────
    seen = []
    for ch in result:
        m = ch["metadata"]
        path = tuple(m[f"section_{i}"] for i in range(1, MAX_LEVELS + 1))
        if path not in seen:
            seen.append(path)

    print("\nUnique section paths:")
    for path in seen:
        parts = [p for p in path if p]
        indent = "  " * (len(parts) - 1) if parts else ""
        label = parts[-1] if parts else "(no section)"
        print(f"  {indent}{label}")
