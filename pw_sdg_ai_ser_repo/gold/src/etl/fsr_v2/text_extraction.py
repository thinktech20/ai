"""Stage 5 text extraction helpers.

Loads the same parsed document artifact as P1 when available so that chunk
char offsets align exactly with preprocessor_regions built during P1.

Alignment requirement: full_text in P2 must be the same string as the full_text
P1 fed to the preprocessor — same extractor, same heading-marker injection, same
page separator ("\n".join). Any difference shifts all char offsets and breaks
region attribution.
"""

from __future__ import annotations

from pathlib import Path

def load_parsed_for_chunking(volume_path: str, parsed_volume_path: str | None = None):
    """Load ParsedDocument from persisted parsed.json (parse-once contract)."""
    from silver.src.etl.fsr_v2.parsing import load_parsed_document  # noqa: PLC0415

    if not parsed_volume_path:
        raise ValueError(
            "Missing parsed_volume_path for chunking. Parse-once mode is enforced "
            "to keep P1/P2 offsets aligned."
        )

    if not Path(parsed_volume_path).exists():
        raise ValueError(
            f"parsed_volume_path does not exist on volume: {parsed_volume_path}. "
            f"Re-run P1 with FSR_PARSED_DOC_VOLUME_ROOT set to regenerate the parsed JSON."
        )

    return load_parsed_document(parsed_volume_path)


def extract_pages(volume_path: str, parsed_volume_path: str | None = None) -> tuple[list[str], list[dict]]:
    """Extract pages + char-offset page_offsets from persisted parsed output when available.

    Delegates to persisted parsed.json or parse_pymupdf (silver/src/etl/fsr_v2/parsing.py) — the same
    representation P1 uses — so that page_offsets and full_text are in the same
    coordinate space as preprocessor_regions stored in the metadata table.

    Returns:
        pages: list of per-page text strings (with heading markers injected)
        page_offsets: list of {start, end} char offsets into full_text
            where full_text = "\n".join(pages)  (single-newline separator, same as P1)
    """
    parsed = load_parsed_for_chunking(volume_path, parsed_volume_path=parsed_volume_path)
    return parsed.pages, parsed.page_offsets


def char_to_page(char_pos: int, page_offsets: list[dict]) -> int:
    """Return 0-based page index for a char offset (fallback: last page)."""
    for i, po in enumerate(page_offsets):
        if po["start"] <= char_pos < po["end"]:
            return i
    return max(0, len(page_offsets) - 1)
