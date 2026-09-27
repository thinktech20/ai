"""Behavioral preprocessing profile for final master reports."""
from __future__ import annotations

import re
import os
from typing import Any

from common.fsr_v2 import preprocessor_v2

_PROFILE = "final_master_report"
_PROFILE_VERSION = "v2"
_COMPONENTS_RE = re.compile(
    r"(?m)^\s*(?:#{0,3}\s*)?\d+\.\s+COMPONENTS\s*$"
)
_APPENDIX_RE = re.compile(
    r"(?m)^\s*(?:#{0,3}\s*)?(?:\d+\.\s+)?APPENDIX(?:\s+.*)?$"
)
_TOP_LEVEL_RE = re.compile(r"(?im)^\s*(?:#{0,3}\s*)?(\d+)[.)]?\s+\S.*$")
_MARKER_RE = re.compile(
    r"(?m)^\s*(GAS\s+TURBINE|STEAM\s+TURBINE|"
    r"GENERATOR(?:\s+(?:ASSEMBLED|EXCITATION|ALIGNMENT|COOLERS|VISUAL))?|"
    r"UNCATEGORIZED)(?:\s*[-:]\s*.*|\s*)$"
)
_EVIDENCE_TERMS = (
    "generator winding", "generator stator", "generator rotor", "generator field",
    "generator excitation", "generator bearing", "generator inspection",
    "generator test", "generator electrical", "generator terminal",
)


def _profile_signal(ctx: Any) -> dict[str, Any]:
    text = ctx.full_text or ""
    filename = str(getattr(ctx, "filename", "") or "")
    filename_signal = bool(re.search(r"final[_ -]?master[_ -]?report", filename, re.I))
    components = list(_COMPONENTS_RE.finditer(text))
    dotted_contents = bool(re.search(r"(?:\.\s*){4,}\.?(?:\s|$)", _primary_toc_text(ctx)))
    marker_inside = False
    if components:
        start = components[0].start()
        end = _next_top_level_start(text, components[0].end())
        marker_inside = bool(_MARKER_RE.search(text[start:end]))
    generator_hyphen = bool(re.search(r"(?m)^\s*GENERATOR\s+-\s+", text))
    score = (2 if components else 0) + (2 if marker_inside else 0)
    score += 2 if dotted_contents else 0
    score += 2 if filename_signal else 0
    score += 2 if generator_hyphen else 0
    return {
        "method": "filename_and_structure" if filename_signal else "behavioral",
        "score": score,
        "signals": [
            name for name, present in (
                ("components_heading", bool(components)),
                ("equipment_category_marker", marker_inside),
                ("dotted_contents", dotted_contents),
                ("generator_hyphen_label", generator_hyphen),
                ("known_filename", filename_signal),
            ) if present
        ],
        "confidence": "high" if score >= 4 else "low",
    }


def _primary_toc_text(ctx: Any) -> str:
    pages = list(getattr(ctx, "pages", []) or [])
    if pages:
        page_count = max(1, (len(pages) + 9) // 10)
        return "\n".join(pages[:page_count])
    return (ctx.full_text or "")[:10000]


def _body_section_match(pattern: re.Pattern[str], ctx: Any) -> re.Match[str] | None:
    text = ctx.full_text or ""
    matches = list(pattern.finditer(text))
    if not matches:
        return None
    pages = list(getattr(ctx, "pages", []) or [])
    offsets = list(getattr(ctx, "page_offsets", []) or [])
    if pages and len(pages) == len(offsets):
        for match in matches:
            page_index = next(
                (
                    index for index, offset in enumerate(offsets)
                    if int(offset["start"]) <= match.start() < int(offset["end"])
                ),
                None,
            )
            if page_index is None:
                continue
            page_text = pages[page_index] or ""
            is_toc_page = bool(
                re.search(
                    r"(?im)^\s*(?:table\s+of\s+)?contents"
                    r"(?:\s*\([^\n)]*\))?\s*[:.]?\s*$",
                    page_text,
                )
                or re.search(r"(?:\.\s*){4,}\.?(?:\s|$)", page_text)
            )
            if not is_toc_page:
                return match

    primary_toc = _primary_toc_text(ctx)
    has_primary_toc = bool(
        re.search(r"(?im)^\s*(?:table\s+of\s+)?contents\s*$", primary_toc)
        or re.search(r"(?:\.\s*){4,}\.?(?:\s|$)", primary_toc)
    )
    if has_primary_toc and len(matches) > 1:
        return matches[1]
    return matches[0]


def is_final_master_report(ctx: Any) -> bool:
    """Route known names or strong final-master structural evidence."""
    signal = _profile_signal(ctx)
    return "known_filename" in signal["signals"] or (
        "components_heading" in signal["signals"]
        and (
            "equipment_category_marker" in signal["signals"]
            or "dotted_contents" in signal["signals"]
            or "generator_hyphen_label" in signal["signals"]
        )
    )


def _next_top_level_start(text: str, start: int) -> int:
    for match in _TOP_LEVEL_RE.finditer(text, start):
        if match.start() > start:
            return match.start()
    return len(text)


def _offset_for(position: int, offsets: list[dict[str, int]]) -> int:
    for offset in offsets:
        if offset["start"] <= position < offset["end"]:
            return offsets.index(offset)
    return max(0, len(offsets) - 1)


def _fallback_label(
    text: str,
    toc_text: str,
    threshold: int,
    document_text: str | None = None,
) -> tuple[str, str, int]:
    toc_generator = bool(re.search(r"(?m)^\s*GENERATOR(?:\s+-\s+.*)?\s*$", toc_text))
    evidence_count = sum(text.lower().count(term) for term in _EVIDENCE_TERMS)
    if toc_generator or evidence_count > threshold:
        reason = "generator_toc" if toc_generator else "generator_evidence_threshold"
        return "shared", reason, evidence_count
    turbine_text = document_text if document_text is not None else text
    has_gt = bool(re.search(r"\bGAS\s+TURBINE\b", turbine_text, re.I))
    has_st = bool(re.search(r"\bSTEAM\s+TURBINE\b", turbine_text, re.I))
    if has_gt and not has_st:
        return "Gas Turbine", "turbine_fallback", evidence_count
    if has_st and not has_gt:
        return "Steam Turbine", "turbine_fallback", evidence_count
    return "shared", "unresolved_turbine", evidence_count


def _region(start: int, end: int, equip_type: str, reason: str, evidence_count: int = 0) -> dict[str, Any]:
    return {
        "start": start,
        "end": end,
        "metadata": {
            "primary_equip_type": equip_type,
            "equip_type_source": "final_master_report_profile",
            "region_source": "section_span" if reason == "explicit_label" else "page_fallback",
            "fallback_chain": [reason],
            "preprocessor_profile": _PROFILE,
            "preprocessor_profile_version": _PROFILE_VERSION,
            "fallback_reason": reason,
            "generator_evidence_count": evidence_count,
        },
    }


def _overlay_section_metadata(
    profile_regions: list[dict[str, Any]],
    shared_regions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    section_regions = [
        region for region in shared_regions
        if region.get("metadata", {}).get("section_path")
    ]
    if not section_regions:
        return profile_regions

    boundaries = {
        boundary
        for region in profile_regions + section_regions
        for boundary in (int(region["start"]), int(region["end"]))
    }
    overlay: list[dict[str, Any]] = []
    ordered = sorted(boundaries)
    for start, end in zip(ordered, ordered[1:]):
        profile_region = next(
            (
                region for region in profile_regions
                if int(region["start"]) <= start and int(region["end"]) >= end
            ),
            None,
        )
        if profile_region is None:
            continue

        metadata = dict(profile_region.get("metadata") or {})
        section_region = next(
            (
                region for region in section_regions
                if int(region["start"]) <= start and int(region["end"]) >= end
            ),
            None,
        )
        if section_region is not None:
            section_metadata = section_region.get("metadata") or {}
            for key in ("section_path", "heading_confidence", "heading_reason_codes"):
                if key in section_metadata:
                    metadata[key] = section_metadata[key]
        overlay.append({"start": start, "end": end, "metadata": metadata})
    return overlay


def _resolve_fallback_generator_esn(
    metadata: dict[str, Any],
    ibat_resolver: Any,
) -> tuple[str | None, str]:
    existing = str(metadata.get("gen_esn") or "").strip().upper()
    if existing and not existing.startswith("SY"):
        return existing, "existing_document_metadata"

    turbine_esn = str(
        metadata.get("gt_esn") or metadata.get("st_esn") or ""
    ).strip().upper()
    if not turbine_esn:
        return None, "no_turbine_anchor"
    if ibat_resolver is None:
        return None, "ibat_unavailable"

    try:
        candidates = ibat_resolver(
            "Generator",
            {"current_turbine_esn": turbine_esn},
        ) or []
    except Exception:
        return None, "ibat_lookup_failed"

    normalized = sorted({
        value
        for candidate in candidates
        if candidate
        for value in [str(candidate).strip().upper()]
        if value and not value.startswith("SY")
    })
    if len(normalized) == 1:
        return normalized[0], "ibat_train"
    if len(normalized) > 1:
        return None, "ibat_ambiguous"
    return None, "ibat_no_candidate"


def preprocess(
    ctx: Any,
    *,
    ibat_resolver: Any = None,
    page_fallback_enabled: bool | None = None,
    generator_threshold: int | None = None,
) -> dict[str, Any]:
    if page_fallback_enabled is None:
        page_fallback_enabled = os.getenv(
            "FSR_V2_FINAL_MASTER_PAGE_FALLBACK_ENABLED", "true"
        ).strip().lower() in {"1", "true", "yes"}
    if generator_threshold is None:
        raw_threshold = os.getenv("FSR_V2_FINAL_MASTER_GENERATOR_THRESHOLD", "7")
        try:
            generator_threshold = int(raw_threshold)
        except ValueError:
            generator_threshold = 7
    text = ctx.full_text or ""
    shared_output = preprocessor_v2.preprocess(ctx, ibat_resolver=ibat_resolver)
    signal = _profile_signal(ctx)
    regions: list[dict[str, Any]] = []
    generator_presence_detected = False
    components_match = _body_section_match(_COMPONENTS_RE, ctx)
    appendix_match = _body_section_match(_APPENDIX_RE, ctx)
    special_starts = [m.start() for m in (components_match, appendix_match) if m]
    special_starts.sort()
    for index, start in enumerate(special_starts):
        end = special_starts[index + 1] if index + 1 < len(special_starts) else len(text)
        section_text = text[start:end]
        is_components = bool(_COMPONENTS_RE.match(text, start))
        markers = list(_MARKER_RE.finditer(section_text)) if is_components else []
        if markers:
            for marker_index, marker in enumerate(markers):
                marker_end = start + (markers[marker_index + 1].start() if marker_index + 1 < len(markers) else len(section_text))
                label = marker.group(1).upper().replace("  ", " ")
                equip = "shared" if label == "UNCATEGORIZED" else (
                    "Steam Turbine" if label.startswith("STEAM") else
                    "Generator" if label.startswith("GENERATOR") else "Gas Turbine"
                )
                generator_presence_detected = generator_presence_detected or equip == "Generator"
                regions.append(_region(start + marker.start(), marker_end, equip, "explicit_label"))
            first_marker = start + markers[0].start()
            if first_marker > start:
                regions.append(_region(start, first_marker, "shared", "unlabeled_components"))
        elif page_fallback_enabled:
            for page_start, page_end in preprocessor_v2.page_ranges_for_span(ctx.page_offsets, start, end):
                page_text = text[page_start:page_end]
                equip, reason, count = _fallback_label(
                    page_text,
                    text[:start],
                    generator_threshold,
                    document_text=text,
                )
                regions.append(_region(page_start, page_end, equip, reason, count))
                generator_presence_detected = generator_presence_detected or reason in {
                    "generator_toc",
                    "generator_evidence_threshold",
                }
        else:
            regions.append(_region(start, end, "shared", "page_fallback_disabled"))

    regions = preprocessor_v2.complete_region_coverage(
        regions,
        len(text),
        lambda start, end: _region(start, end, "shared", "outside_components_appendix"),
    )
    regions = _overlay_section_metadata(regions, list(shared_output.get("regions") or []))
    metadata = dict(shared_output.get("metadata") or {})
    metadata.update({
        "preprocessor_profile": _PROFILE,
        "preprocessor_profile_version": _PROFILE_VERSION,
        "profile_detection": signal,
        "page_fallback_enabled": page_fallback_enabled,
        "generator_threshold": generator_threshold,
    })
    if generator_presence_detected:
        generator_esn, resolution = _resolve_fallback_generator_esn(
            metadata,
            ibat_resolver,
        )
        metadata["generator_esn_resolution"] = resolution
        if generator_esn:
            metadata["gen_esn"] = generator_esn
        for region in regions:
            region_metadata = region["metadata"]
            is_explicit_generator = (
                region_metadata.get("fallback_reason") == "explicit_label"
                and region_metadata.get("primary_equip_type") == "Generator"
            )
            if is_explicit_generator or region_metadata.get("fallback_reason") in {
                "generator_toc",
                "generator_evidence_threshold",
            }:
                region_metadata["generator_esn_resolution"] = resolution
                if is_explicit_generator and generator_esn:
                    region_metadata["primary_esn"] = generator_esn
    hints = (
        "preprocessor_profile=final_master_report; "
        "preprocessor_profile_version=" + _PROFILE_VERSION + "; "
        "preprocessor_strategy=components_labels_and_appendix_fallback; "
        "signals=" + ",".join(signal["signals"])
    )
    return {
        "metadata": metadata,
        "hints": shared_output.get("hints", "") + "\n" + hints,
        "regions": preprocessor_v2.merge_adjacent_regions(
            regions,
            preserve_sources={"page_fallback"},
        ),
    }
