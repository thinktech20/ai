"""Stage 5 chunk splitting helpers."""

from __future__ import annotations

from typing import Any

from common.fsr_v2.chunker import get_chunker


def chunk_region_metadata(chunk: dict) -> dict:
    """Preserve the complete P1 region metadata in the chunk JSON contract."""
    region_metadata = dict(chunk.get("region_metadata") or {})
    region_metadata.setdefault("primary_esn", chunk.get("region_primary_esn", ""))
    region_metadata.setdefault(
        "primary_equip_type",
        chunk.get("region_primary_equip_type", ""),
    )
    return region_metadata


def _complete_region_coverage(text_length: int, regions: list[dict]) -> list[dict]:
    """Return non-overlapping regions covering [0, text_length).

    P1 normally emits full coverage. This boundary guard makes malformed or
    older metadata explicit by assigning uncovered text to shared regions
    instead of allowing a later document-level ESN fallback.
    """
    valid = []
    for region in regions or []:
        start = max(0, min(text_length, int(region.get("start", 0))))
        end = max(start, min(text_length, int(region.get("end", 0))))
        if end > start:
            valid.append((start, end, dict(region.get("metadata") or {})))

    if not valid:
        return [{
            "start": 0,
            "end": text_length,
            "metadata": {
                "primary_equip_type": "shared",
                "region_source": "synthetic",
                "esn_confidence": "none",
                "fallback_chain": ["shared"],
            },
        }]

    boundaries = {0, text_length}
    for start, end, _metadata in valid:
        boundaries.update((start, end))

    completed: list[dict] = []
    ordered = sorted(boundaries)
    for start, end in zip(ordered, ordered[1:]):
        covering = [
            (region_start, region_end, metadata)
            for region_start, region_end, metadata in valid
            if region_start <= start and region_end >= end
        ]
        if covering:
            _, _, metadata = min(covering, key=lambda item: (item[1] - item[0], item[0]))
        else:
            metadata = {
                "primary_equip_type": "shared",
                "region_source": "gap_fallback" if start else "front_matter",
                "esn_confidence": "none",
                "fallback_chain": ["shared"],
            }
            if end == text_length:
                metadata["region_source"] = "trailing"
        completed.append({"start": start, "end": end, "metadata": metadata})

    merged: list[dict] = []
    for region in completed:
        if merged and merged[-1]["end"] == region["start"] and merged[-1]["metadata"] == region["metadata"]:
            merged[-1]["end"] = region["end"]
        else:
            merged.append(region)
    return merged


def split_with_offsets(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_size: int,
    strategy: str,
    volume_path: str | None = None,
    retain_single_short: bool = False,
) -> tuple[list[tuple[str, int, int]], Any]:
    """Split text and merge undersized fragments without losing source coverage.

    Returns:
        (filtered_chunks, chunker) — chunker is returned for section_metadata calls
    """
    chunker = get_chunker(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        strategy=strategy,
    )
    chunks = chunker.chunk_text(text, pdf_path=volume_path)
    original_miss = set(getattr(chunker, "_last_mapping_miss_chunk_indices", []))
    filtered: list[tuple[str, int, int, bool]] = []
    pending_short: tuple[int, int, bool] | None = None
    for original_idx, (chunk_text, start_char, end_char) in enumerate(chunks):
        mapping_miss = original_idx in original_miss
        if len(chunk_text.strip()) < min_chunk_size:
            if filtered:
                _previous_text, previous_start, previous_end, previous_miss = filtered[-1]
                merged_end = max(previous_end, end_char)
                filtered[-1] = (
                    text[previous_start:merged_end],
                    previous_start,
                    merged_end,
                    previous_miss or mapping_miss,
                )
            elif pending_short is None:
                pending_short = (start_char, end_char, mapping_miss)
            else:
                pending_start, pending_end, pending_miss = pending_short
                pending_short = (
                    pending_start,
                    max(pending_end, end_char),
                    pending_miss or mapping_miss,
                )
            continue

        if pending_short is not None:
            pending_start, pending_end, pending_miss = pending_short
            start_char = min(pending_start, start_char)
            end_char = max(pending_end, end_char)
            chunk_text = text[start_char:end_char]
            mapping_miss = mapping_miss or pending_miss
            pending_short = None
        filtered.append((chunk_text, start_char, end_char, mapping_miss))

    if pending_short is not None:
        start_char, end_char, mapping_miss = pending_short
        pending_text = text[start_char:end_char]
        if len(pending_text.strip()) >= min_chunk_size or retain_single_short:
            filtered.append((pending_text, start_char, end_char, mapping_miss))

    filtered_miss = [
        index for index, (_chunk_text, _start, _end, mapping_miss) in enumerate(filtered)
        if mapping_miss
    ]

    # Keep diagnostics aligned to the returned (filtered) chunk list.
    chunker._last_mapping_miss_chunk_indices = filtered_miss
    return [
        (chunk_text, start_char, end_char)
        for chunk_text, start_char, end_char, _mapping_miss in filtered
    ], chunker


def split_region_first_with_offsets(
    text: str,
    regions: list[dict],
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_size: int,
    volume_path: str | None = None,
) -> list[dict]:
    """Split text by region, then recursively sub-chunk each region.

    Region boundaries from preprocessor_v2 are the authoritative semantic
    boundaries. The inner splitter is intentionally fixed to recursive so a
    legacy strategy parameter cannot reintroduce heading-based chunks or
    cross-region attribution ambiguity.
    """
    output: list[dict] = []
    sorted_regions = _complete_region_coverage(len(text), regions)
    for region in sorted_regions:
        region_start = int(region.get("start", 0))
        region_end = int(region.get("end", 0))
        if region_end <= region_start:
            continue

        region_text = text[region_start:region_end]
        if not region_text.strip():
            continue

        meta = dict(region.get("metadata") or {})
        retain_single_short = bool(meta.get("section_path")) or (
            meta.get("preprocessor_profile") == "final_master_report"
            and meta.get("fallback_reason") != "outside_components_appendix"
        )
        chunks, chunker = split_with_offsets(
            region_text,
            chunk_size,
            chunk_overlap,
            min_chunk_size,
            "recursive",
            volume_path=volume_path,
            retain_single_short=retain_single_short,
        )
        if not chunks:
            continue

        section_path = list(meta.get("section_path") or [])[:5]
        base_section_meta = {
            "section_1": section_path[0] if len(section_path) > 0 else None,
            "section_2": section_path[1] if len(section_path) > 1 else None,
            "section_3": section_path[2] if len(section_path) > 2 else None,
            "section_4": section_path[3] if len(section_path) > 3 else None,
            "section_5": section_path[4] if len(section_path) > 4 else None,
        }

        for chunk_text, rel_start, rel_end in chunks:
            abs_start = region_start + rel_start
            abs_end = region_start + rel_end
            section_meta = base_section_meta
            output.append(
                {
                    "chunk_text": chunk_text,
                    "start_char": abs_start,
                    "end_char": abs_end,
                    "region_metadata": meta,
                    "section_metadata": section_meta,
                }
            )

    for index in range(len(output) - 1):
        current_section = output[index]["section_metadata"]
        next_section = output[index + 1]["section_metadata"]
        if current_section == next_section or not any(next_section.values()):
            continue
        original_text = output[index]["chunk_text"]
        cleaned = _strip_duplicate_next_heading(
            original_text,
            next_section,
        )
        if cleaned and cleaned != original_text:
            source_start = output[index]["start_char"]
            source_end = output[index]["end_char"]
            source_text = text[source_start:source_end]
            retained_start = source_text.find(cleaned)
            output[index]["chunk_text"] = cleaned
            if retained_start >= 0:
                output[index]["end_char"] = source_start + retained_start + len(cleaned)
            else:
                output[index]["end_char"] = max(
                    source_start,
                    source_end - (len(original_text) - len(cleaned)),
                )

    return output


def _heading_key(text: str) -> str:
    return "".join(character.casefold() for character in text if character.isalnum())


def _strip_duplicate_next_heading(
    previous_text: str,
    next_section_metadata: dict,
) -> str:
    lines = previous_text.rstrip().splitlines()
    if not lines:
        return previous_text

    section_headings = [
        str(value) for value in next_section_metadata.values() if value
    ]
    targets = section_headings[-1:]

    for target in targets:
        target_key = _heading_key(target)
        if not target_key:
            continue
        if _heading_key(lines[-1]) == target_key:
            return "\n".join(lines[:-1]).rstrip()

        lower_bound = max(-1, len(lines) - len(target_key) - 5)
        for start in range(len(lines) - 1, lower_bound, -1):
            vertical_lines = [line.strip() for line in lines[start:]]
            if any(len(line) > 2 for line in vertical_lines):
                break
            vertical_key = _heading_key("".join(vertical_lines))
            if vertical_key == target_key:
                return "\n".join(lines[:start]).rstrip()
            if len(vertical_key) > len(target_key):
                break

    return previous_text
