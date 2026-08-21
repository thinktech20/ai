import re
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

# GE FSR metadata preprocessor — redesign variant.
# NOTE: Existing regex constants below are copied from preprocessor.py as requested.

NOT_APPLICABLE = [
    r'(?i)this equipment is not applicable',
    r'(?i)not applicable for this outage',
    r'(?i)no work performed on this (?:unit|equipment)',
    r'(?i)not included in (?:this )?scope',
]

# Section headers like:  GENERATOR (337X766 | SY0072576)  or  GENERATOR (GG10675 | SY1390901)
HEADER = r'(GAS TURBINE|GENERATOR|STEAM TURBINE|EXCITER)\s*\(\s*(\d{3}[A-Z]?\d{3}|GG\d{4,6})\s*\|\s*(SY\d{7})\)'

GT_LABELS = [
    r'Gas\s*Turbine\s*(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
    r'Assoc(?:iated)?\.?\s*Turbine\s*[:#]?\s*(\d{6})',
]
GEN_LABELS = [
    r'Gen(?:erator)?\s*(?:Field\s*)?(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]\d{3})',
    r'Generator\s*#\s*(\d{3}[A-Z]\d{3})',
    r'(?:Equipment\s+)?Generator\s+(?:No|Number)\.?\s*[:#]?\s*(\d{3}[A-Z]\d{3})',
    r'(GG\d{4,6})\s*\|\s*SY\d{7}',
]
GEN_EQUIPMENT_ID_SN_PAIR = (
    r'(?is)\bEquipment\s+ID\s*[:#]?\s*SY\d{7}\s*'
    r'Equipment\s+(?:SN|Serial(?:\s*(?:No|#|Number))?)\s*[:#]?\s*'
    r'(GG\d{4,6})\b'
)
ST_LABELS = [
    r'Steam\s*Turbine\s*(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
]
GENERIC_LABELS = [
    r'Equipment\s*Serial\s*#?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
    r'\bESN\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
]

GEN_FORMS = ['D3162041', 'D3162043', 'D3162044', 'D316218', 'D316303', 'D316402',
             'D316403', 'D316501', 'D316512', 'D300001', 'D306301', 'D306302',
             'D309102', 'D309301', 'D309302', 'D315102']
GT_FORMS = ['GT3225', 'GT9245', 'GT9386', 'GT9390', 'GT4050', 'GT1040', 'GT71F040', 'GT71F045']

GEN_SIGNATURES = [
    'armature winding resistance', 'armature insulation', 'hipotential testing',
    'stator voltage', 'polarization index', 'power mva', 'max h2 pressure',
    'collector end', 'dc leakage', 'stator insulation resistance',
    'endwinding', 'end winding', 'retaining ring', 'field winding',
    'el-cid', 'el cid', 'wedge tightness', 'stator core',
    'hydrogen seal', 'diode wheel', 'partial discharge', 'stator rewind',
    'core lamination', 'generator specialist',
]

GT_SIGNATURES = [
    'combustion liner', 'combustion can', 'transition piece', 'fuel nozzle',
    'crossfire tube', 'cross fire tube', 'flow sleeve',
    'inlet guide vane', 'compressor discharge', 'hot gas path',
    'stage 1 nozzle', 'stage 1 bucket', 'stage 1 shroud',
    'stage 2 nozzle', 'stage 2 bucket', 'stage 2 shroud',
    'stage 3 nozzle', 'stage 3 bucket', 'stage 3 shroud',
    'wheelspace', 'load coupling', 'load gear',
    'igv calibration', 'bleed valve', 'spark plug', 'flame detector',
    'wheel space', 'dln tuning', 'fsnl', 'water wash',
    'exhaust thermocouple', 'gas turbine executive', 'fired hours',
    'compressor blade', 'compressor vane', 'turbine wheel',
]

START_LABELS = [r'(?:Job|Outage)\s*Start\s*Date\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']
END_LABELS = [r'(?:Job|Outage)\s*(?:End|Completion)\s*Date\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']
ISSUED_LABELS = [r'(?:Approved|Report\s*Issued|Date\s*Issued)\s*(?:Date)?\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']

_DATE_STOP = r'\s{2,}|Oracle|Prepared|Approved|Equipment|Report|Contents|Generator|Gas\s*Turbine|Job\b'

# New patterns from redesign doc.
UNNUMBERED_EQUIP_HDR = r'(?im)^(GAS\s+TURBINE|GENERATOR|STEAM\s+TURBINE|EXCITER)\s*$'
UNNUMBERED_TITLED_HDR = (
    r'(?im)^(Generator|Gas\s+Turbine|Steam\s+Turbine)\s+'
    r'(?:Section|Report|Inspection)\b.*$'
)
SECTION_HDR = r'(?im)^\s*#{0,3}\s*(\d+)[ \t]+(GAS\s+TURBINE|TURBINE|GENERATOR|STEAM\s+TURBINE|EXCITER)\s*$'
# Numbered top-level sections whose title names the electrical/generator scope
# (e.g. `5 Electrical System`) belong to the Generator equipment. Section number
# is captured; the equipment label is fixed to Generator by rule.
SECTION_HDR_GEN_KEYWORD = (
    r'(?im)^\s*#{0,3}\s*(\d+)[ \t]+(Electrical\s+System|Electrical|Electrification)\s*$'
)
SUBSEC_GEN = r'(?m)^(?:#{1,3}\s+)?(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?) Generator\b'
SUBSEC_GEN_KEYWORD = (
    r'(?m)^(?:#{1,3}\s+)?(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?) '
    r'(?:Electrical|Electrification|DC\s+Leakage)\b'
)
SUBSEC_TURBINE = r'(?m)^(?:#{1,3}\s+)?(\d{1,2}(?:\.\d{1,2})+) Turbine\b'
SUBSEC_GT = r'(?m)^(?:#{1,3}\s+)?(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?) (?:Compressor|Combustion|Inlet)\b'
SUBSEC_GENERIC = r'(?m)^(?:#{1,3}\s+)?(\d{1,2}(?:\.\d{1,2})+)\s+([^\n]+)$'

DOC_SUMMARY_PATTERN = re.compile(r"\bexecutive\s+summary\b|\binspection\s+summary\b|\bsummary\b", re.IGNORECASE)
DOC_SUMMARY_NOISE_PATTERN = re.compile(
    r"^[\s_\-\.\|]*$"
    r"|^table\s+of\s+contents?$"
    r"|^contents?$",
    re.IGNORECASE,
)


class HeadingType(str, Enum):
    HEADER = "HEADER"
    SECTION_HDR = "SECTION_HDR"
    SUBSEC = "SUBSEC"
    UNNUMBERED = "UNNUMBERED"
    TOC = "TOC"


class EsnConfidence(str, Enum):
    HIGHEST = "highest"
    HIGH = "high"
    LOW = "low"
    FALLBACK = "fallback"
    NONE = "none"


class EsnSource(str, Enum):
    """Provenance of the ESN attached to a section or region."""

    # ESN explicitly present in the heading text, e.g. HEADER pattern match.
    LOCAL_HEADER = "local_header"
    # ESN inherited from the nearest parent span with matching equipment type.
    PARENT_INHERIT = "parent_inherit"
    # Exactly one active ESN exists for the equipment type, so assign deterministically.
    SINGLE_TYPE = "single_type"
    # ESN selected via IBAT candidate lookup when local/parent/single-type are insufficient.
    IBAT_TRAIN = "ibat_train"
    # ESN inferred for synthetic gap regions from neighboring region context.
    NEIGHBOR_GAP = "neighbor_gap"
    # ESN inherited from document-level primary context.
    DOC_PRIMARY = "doc_primary"
    # No ESN could be assigned.
    NONE = "none"


class RegionSource(str, Enum):
    """Origin of region boundaries and attribution metadata."""

    # Region created from a resolved section span.
    SECTION_SPAN = "section_span"
    # Synthetic region before the first attributable section span.
    FRONT_MATTER = "front_matter"
    # Synthetic region filling uncovered text between two spans.
    GAP_FALLBACK = "gap_fallback"
    # Synthetic region after the last attributable section span.
    TRAILING = "trailing"
    # Synthetic catch-all region when no attributable spans exist.
    SYNTHETIC = "synthetic"


class HeadingCandidate(BaseModel):
    start_char: int
    heading_text: str
    heading_type: HeadingType
    equipment_type: str | None = None
    local_esn: str | None = None
    level: int = 0
    confidence_rank: int = 0


class SectionSpan(BaseModel):
    start: int
    end: int
    level: int
    heading_text: str
    heading_type: HeadingType
    equipment_type: str | None = None
    local_esn: str | None = None
    resolved_esn: str | None = None
    esn_confidence: EsnConfidence = EsnConfidence.NONE
    esn_source: EsnSource = EsnSource.NONE
    parent_idx: int | None = None
    level_conflict: bool = False
    is_summary: bool = False


class RegionMetadata(BaseModel):
    primary_esn: str | None = None
    primary_equip_type: str | None = None
    primary_technology_code: str | None = None
    esn_confidence: EsnConfidence = EsnConfidence.NONE
    esn_source: EsnSource = EsnSource.NONE
    equip_type_source: str = "none"
    region_source: RegionSource = RegionSource.SECTION_SPAN
    section_path: list[str] = Field(default_factory=list)
    fallback_chain: list[str] = Field(default_factory=list)


class Region(BaseModel):
    start: int
    end: int
    metadata: RegionMetadata


class PreprocessOutput(BaseModel):
    metadata: dict[str, Any]
    hints: str
    regions: list[Region]


def _model_to_dict(model: BaseModel) -> dict[str, Any]:
    """Serialize Pydantic model to dict across both v1 and v2 APIs.

    Pydantic v2 uses model_dump(), while v1 uses dict().
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


def _norm(esn: str | None) -> str:
    return (esn or "").upper().strip()


def _clean_date(value: str) -> str | None:
    txt = (value or "").strip().rstrip('.').strip()
    txt = re.split(_DATE_STOP, txt)[0].strip()
    return txt or None


def _section_level(num_str: str) -> int:
    return num_str.count('.')


def _canon(name: str) -> str:
    n = (name or "").strip().lower()
    if "generator" in n:
        return "Generator"
    if "exciter" in n:
        return "Exciter"
    if "steam" in n:
        return "Steam Turbine"
    return "Gas Turbine"


def _bare_turbine_from_inventory(active_by_type: dict[str, list[str]] | None) -> str | None:
    # Disambiguate bare "N Turbine" SECTION_HDR from doc-level equipment inventory
    # when no prior HEADER/turbine candidate exists to inherit from.
    if not active_by_type:
        return None
    has_gt = bool(active_by_type.get("Gas Turbine"))
    has_st = bool(active_by_type.get("Steam Turbine"))
    if has_gt and not has_st:
        return "Gas Turbine"
    if has_st and not has_gt:
        return "Steam Turbine"
    return None


# TOC cross-check gate: require at least this many parsed TOC entries before
# using TOC as an authority to accept/reject SECTION_HDR / SUBSEC_GENERIC candidates.
# Keeps behavior identical to pre-cross-check when the TOC parser itself fails.
_TOC_CROSSCHECK_MIN_ENTRIES = 5


def _section_hdr_matches_toc(
    equipment_label: str,
    toc_entries: list[tuple[str, int]],
    toc_equipment_anchors: set[str],
) -> bool:
    if len(toc_entries) < _TOC_CROSSCHECK_MIN_ENTRIES:
        return True
    if equipment_label.upper() == "TURBINE":
        return "Gas Turbine" in toc_equipment_anchors or "Steam Turbine" in toc_equipment_anchors
    return _canon(equipment_label) in toc_equipment_anchors


def _subsec_generic_matches_toc(
    section_num: str,
    title: str,
    toc_entries: list[tuple[str, int]],
) -> bool:
    if len(toc_entries) < _TOC_CROSSCHECK_MIN_ENTRIES:
        return True
    cand_tokens = set(re.findall(r'[a-z]{3,}', (title or "").lower()))
    if not cand_tokens:
        return False
    for toc_title, _page in toc_entries:
        toc_title_low = (toc_title or "").lower()
        num_match = re.match(r'^\s*(\d+(?:\.\d+)*)\s+(.*)', toc_title_low)
        if num_match:
            toc_num, toc_rest = num_match.groups()
            same_branch = (
                toc_num == section_num
                or section_num.startswith(toc_num + '.')
                or toc_num.startswith(section_num + '.')
            )
            if same_branch and (cand_tokens & set(re.findall(r'[a-z]{3,}', toc_rest))):
                return True
        else:
            if cand_tokens & set(re.findall(r'[a-z]{3,}', toc_title_low)):
                return True
    return False


def _is_valid_section_number(num_str: str) -> bool:
    parts = [p for p in num_str.split('.') if p]
    if not parts:
        return False
    return all(part.isdigit() and len(part) <= 2 for part in parts)


def _is_doc_summary(title: str) -> bool:
    return bool(DOC_SUMMARY_PATTERN.search((title or "").strip()))


def _extract_heading_section_number(heading_text: str) -> str | None:
    match = re.match(r'^\s*#{0,3}\s*(\d{1,2}(?:\.\d{1,2})*)\b', heading_text or "")
    if not match:
        return None
    return match.group(1)


def _is_bare_turbine_heading(heading_text: str) -> bool:
    return bool(re.match(r'^\s*#{0,3}\s*\d+(?:\.\d+)*\s+Turbine\b', heading_text or "", re.IGNORECASE))


def _extract_toc_entries_from_pages(pages: list[str]) -> tuple[list[tuple[str, int]], int]:
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    toc_heading = re.compile(r"table\s+of\s+contents?", re.IGNORECASE)
    total_pages = len(pages)

    candidate_pages = [
        i for i in range(min(5, total_pages))
        if toc_heading.search(pages[i] or "")
    ]
    if not candidate_pages:
        candidate_pages = list(range(min(3, total_pages)))

    for page_num in candidate_pages:
        page_text = pages[page_num] or ""
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            match = re.match(r"^(.*?)\s*[\._\-]{2,}\s*(\d{1,4})$", line)
            if match:
                title = match.group(1).strip()
                right_clean = match.group(2)
            else:
                match = re.match(r"^(.*?)(?:\s+)(\d{1,4})$", line)
                if not match:
                    continue
                title = match.group(1).strip()
                right_clean = match.group(2)

            if not right_clean and title:
                tokens = title.split()
                if tokens and re.fullmatch(r"\d+", tokens[-1]):
                    right_clean = tokens[-1]
                    title = " ".join(tokens[:-1]).strip()

            if not title or DOC_SUMMARY_NOISE_PATTERN.match(title):
                continue
            if not re.fullmatch(r"\d+", right_clean):
                continue

            key = (title, int(right_clean))
            if key not in seen:
                seen.add(key)
                entries.append(key)
    return entries, total_pages


def _extract_section_text_from_pages(pages: list[str], start_page: int, end_page: int) -> str:
    total = len(pages)
    parts: list[str] = []
    for p in range(start_page, end_page + 1):
        idx = p - 1
        if 0 <= idx < total:
            text = (pages[idx] or "").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


def _char_offset_for_page(pages: list[str], page_number: int) -> int | None:
    """Map 1-based page number to char offset in full_text='\n'.join(pages)."""
    if page_number <= 0:
        return None
    idx = page_number - 1
    if idx >= len(pages):
        return None
    return sum(len(pages[i]) + 1 for i in range(idx))


def _find_title_with_page_hint(
    full_text: str,
    title: str,
    hint_char: int | None,
    window_chars: int = 8000,
) -> int | None:
    """Find a title near TOC-indicated page first, then globally as fallback."""
    if not title:
        return None
    pattern = re.compile(re.escape(title), re.IGNORECASE)

    if hint_char is not None:
        lo = max(0, hint_char - window_chars)
        hi = min(len(full_text), hint_char + window_chars)
        snippet = full_text[lo:hi]
        local_match = pattern.search(snippet)
        if local_match:
            return lo + local_match.start()

    global_match = pattern.search(full_text)
    if global_match:
        return global_match.start()
    return None


class FSRV2Preprocessor:
    # 8/12 behavior toggles while final policy is pending reviewer confirmation.
    REQUIRE_PRIMARY_TOC_MATCH_FOR_UNNUMBERED_EQUIP = True
    ALLOW_UNNUMBERED_EQUIP_WITH_ESN_SY_NO_TOC_MATCH = True
    LAST_KNOWN_CONTEXT_MAX_CHAR_GAP = 45000
    IBAT_CANDIDATE_POOL_ORDER = ("broad_esns", "all_esns")

    @staticmethod
    def _toc_equipment_anchors(toc_entries: list[tuple[str, int]]) -> set[str]:
        anchors: set[str] = set()
        for title, _page in toc_entries:
            low = (title or "").lower()
            if "generator" in low:
                anchors.add("Generator")
            if "gas turbine" in low or low.strip() == "turbine":
                anchors.add("Gas Turbine")
            if "steam turbine" in low:
                anchors.add("Steam Turbine")
            if "exciter" in low:
                anchors.add("Exciter")
            # Electrical / Electrification top-level sections map to Generator.
            if re.search(r'\belectrical\b|\belectrification\b', low):
                anchors.add("Generator")
        return anchors

    def _suppress_redundant_unnumbered_candidates(
        self,
        candidates: list[HeadingCandidate],
    ) -> list[HeadingCandidate]:
        """Drop noisy unnumbered equipment headings that reset active numbered chains.

        This targets cases where OCR/parser emits standalone lines like "Gas Turbine"
        shortly after numbered headings of the same equipment/root, which can
        incorrectly pop section headers such as "2 Turbine" from the active path.
        """
        if not candidates:
            return candidates

        filtered: list[HeadingCandidate] = []
        last_numbered_by_equip: dict[str, HeadingCandidate] = {}

        for cand in sorted(candidates, key=lambda c: c.start_char):
            if cand.level >= 0 and cand.equipment_type:
                last_numbered_by_equip[cand.equipment_type] = cand
                filtered.append(cand)
                continue

            if cand.heading_type == HeadingType.UNNUMBERED and cand.equipment_type:
                heading_text = (cand.heading_text or "")
                # Safety belt: preserve any unnumbered equipment heading that carries
                # explicit ESN/SY markers in the same line.
                if re.search(r'\bESN\b|\bSY\d{3,}\b', heading_text, re.IGNORECASE):
                    filtered.append(cand)
                    continue

                prev = last_numbered_by_equip.get(cand.equipment_type)
                if prev is not None:
                    # If the same equipment already has an active numbered heading nearby,
                    # treat this unnumbered line as a formatting artifact.
                    if cand.start_char - prev.start_char <= 5000:
                        continue

            filtered.append(cand)

        return filtered

    @staticmethod
    def _is_low_confidence_generic_subsection_title(title: str) -> bool:
        """Heuristic guardrail to avoid promoting table/value lines as headings."""
        cleaned = re.sub(r'\s+', ' ', (title or '').strip())
        if not cleaned:
            return True

        alpha_count = sum(ch.isalpha() for ch in cleaned)
        digit_count = sum(ch.isdigit() for ch in cleaned)
        word_count = len(re.findall(r'\b\w+\b', cleaned))

        if alpha_count == 0:
            return True
        if re.fullmatch(r'[\d\W_]+', cleaned):
            return True
        if digit_count >= 4 and digit_count > alpha_count and word_count <= 6:
            return True

        # Long metric-like lines are usually body text/table rows, not section headings.
        if (
            word_count >= 10
            and re.search(r'\d+\.\d+|@\s*\d+|\b(?:ohm|psi|rpm|hz|amp|amps|volt|volts|kv|mw)\b', cleaned, re.I)
        ):
            return True

        return False

    def _discover_esn_context(self, pages: list[str], full_text: str) -> dict[str, Any]:
        title = "\n".join(pages[:6]) if pages else full_text[:8000]
        esn_type: dict[str, str] = {}

        def set_type(esn: str, equip_type: str | None):
            esn_key = _norm(esn)
            if not esn_key:
                return
            current = esn_type.get(esn_key)
            if equip_type and (current is None or current == 'Unknown'):
                esn_type[esn_key] = equip_type
            elif esn_key not in esn_type:
                esn_type[esn_key] = equip_type or 'Unknown'

        for page_text in pages:
            for match in re.finditer(HEADER, page_text, re.I):
                set_type(match.group(2), match.group(1).title())

        for pattern in GT_LABELS:
            for match in re.finditer(pattern, title, re.I):
                set_type(match.group(1), 'Gas Turbine')

        for pattern in GEN_LABELS:
            for match in re.finditer(pattern, title, re.I):
                set_type(match.group(1), 'Generator')

        for pattern in ST_LABELS:
            for match in re.finditer(pattern, title, re.I):
                set_type(match.group(1), 'Steam Turbine')

        for pattern in GENERIC_LABELS:
            for match in re.finditer(pattern, title, re.I):
                esn = _norm(match.group(1))
                set_type(esn, 'Generator' if re.search(r'[A-Z]', esn) else 'Gas Turbine')

        for match in re.finditer(HEADER, full_text, re.I):
            set_type(match.group(2), match.group(1).title())

        # Some embedded Generator reports list Equipment ID (SY) and Equipment
        # SN (GG) on separate lines rather than in the standard GG | SY format.
        for match in re.finditer(GEN_EQUIPMENT_ID_SN_PAIR, full_text):
            set_type(match.group(1), 'Generator')

        all_esns = set(esn_type.keys())

        inactive: set[str] = set()
        for page_text in pages:
            if any(re.search(pattern, page_text or "") for pattern in NOT_APPLICABLE):
                for esn in all_esns:
                    if esn in page_text:
                        inactive.add(esn)
        active = all_esns - inactive

        active_by_type: dict[str, list[str]] = {
            "Gas Turbine": sorted([e for e in active if esn_type.get(e) == "Gas Turbine"]),
            "Generator": sorted([e for e in active if esn_type.get(e) in ("Generator", "Exciter")]),
            "Steam Turbine": sorted([e for e in active if esn_type.get(e) == "Steam Turbine"]),
        }

        esn_counts: dict[str, int] = {}
        for token in re.findall(r'\b(\d{3}[A-Z]\d{3})\b', full_text, re.I):
            key = token.upper()
            esn_counts[key] = esn_counts.get(key, 0) + 1

        for token in re.findall(r'\b(\d{6})\b', full_text):
            if token in esn_type:
                esn_counts[token] = esn_counts.get(token, 0) + 1

        broad_esns = set(esn_type.keys())
        for candidate, count in esn_counts.items():
            if count >= 3 and len(candidate) >= 6:
                broad_esns.add(candidate)

        return {
            "title": title,
            "esn_type": esn_type,
            "all_esns": all_esns,
            "active": active,
            "inactive": inactive,
            "active_by_type": active_by_type,
            "broad_esns": broad_esns,
        }

    def _collect_heading_candidates(
        self,
        full_text: str,
        raw_pages: list[str],
        pages: list[str] | None = None,
        page_offsets: list[int] | None = None,
        active_by_type: dict[str, list[str]] | None = None,
    ) -> tuple[list[HeadingCandidate], list[tuple[str, int]]]:
        candidates: list[HeadingCandidate] = []
        section_root_type: dict[str, str] = {}
        generator_subsec_starts_by_root: dict[str, list[int]] = {}
        toc_entries, _total_pages = _extract_toc_entries_from_pages(raw_pages)
        toc_equipment_anchors = self._toc_equipment_anchors(toc_entries)

        for match in re.finditer(HEADER, full_text, re.I):
            equip_type = _canon(match.group(1))
            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0),
                    heading_type=HeadingType.HEADER,
                    equipment_type=equip_type,
                    local_esn=_norm(match.group(2)),
                    level=-1,
                    confidence_rank=100,
                )
            )

        # Front-matter guard: coarse offset filter to keep TOC/index lines out of
        # the body candidate pool. 2% of the doc, capped at 5000 chars, so long docs
        # (~700 pages) do not trap legitimate body sections that begin early.
        toc_cutoff = min(len(full_text) // 50, 5000)
        for match in re.finditer(UNNUMBERED_EQUIP_HDR, full_text, re.I):
            if match.start() <= toc_cutoff:
                continue
            equip_type = _canon(match.group(1))
            heading_text = match.group(0).strip()

            if self.REQUIRE_PRIMARY_TOC_MATCH_FOR_UNNUMBERED_EQUIP:
                if equip_type not in toc_equipment_anchors:
                    # Safety belt for explicitly tagged equipment lines.
                    has_esn_or_sy = bool(re.search(r'\bESN\b|\bSY\d{3,}\b', heading_text, re.IGNORECASE))
                    if not (self.ALLOW_UNNUMBERED_EQUIP_WITH_ESN_SY_NO_TOC_MATCH and has_esn_or_sy):
                        continue

            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=heading_text,
                    heading_type=HeadingType.UNNUMBERED,
                    equipment_type=equip_type,
                    level=-1,
                    confidence_rank=60,
                )
            )

        for match in re.finditer(UNNUMBERED_TITLED_HDR, full_text, re.I):
            if match.start() <= toc_cutoff:
                continue
            equip_type = _canon(match.group(1))
            heading_text = match.group(0).strip()

            if self.REQUIRE_PRIMARY_TOC_MATCH_FOR_UNNUMBERED_EQUIP:
                if equip_type not in toc_equipment_anchors:
                    has_esn_or_sy = bool(re.search(r'\bESN\b|\bSY\d{3,}\b', heading_text, re.IGNORECASE))
                    if not (self.ALLOW_UNNUMBERED_EQUIP_WITH_ESN_SY_NO_TOC_MATCH and has_esn_or_sy):
                        continue

            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=heading_text,
                    heading_type=HeadingType.UNNUMBERED,
                    equipment_type=equip_type,
                    level=-1,
                    confidence_rank=55,
                )
            )

        for match in re.finditer(SECTION_HDR, full_text):
            if match.start() <= toc_cutoff:
                continue
            num = match.group(1)
            if not _is_valid_section_number(num):
                continue
            equipment_label = match.group(2)
            if not _section_hdr_matches_toc(equipment_label, toc_entries, toc_equipment_anchors):
                continue
            equip_type = None if equipment_label.upper() == "TURBINE" else _canon(equipment_label)
            
            # For bare Turbine headings, look backwards for most recent turbine type.
            if equip_type is None and equipment_label.upper() == "TURBINE":
                for prev_candidate in reversed(candidates):
                    if prev_candidate.equipment_type in ("Gas Turbine", "Steam Turbine"):
                        equip_type = prev_candidate.equipment_type
                        break
                # Doc-level fallback when no prior HEADER/typed candidate exists.
                if equip_type is None:
                    equip_type = _bare_turbine_from_inventory(active_by_type)
            
            if equip_type:
                section_root_type[num.split('.')[0]] = equip_type
            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0).strip(),
                    heading_type=HeadingType.SECTION_HDR,
                    equipment_type=equip_type,
                    level=0,
                    confidence_rank=80,
                )
            )

        # Page-aware fallback for pypdf2-style joins where page boundaries may not
        # include a newline in full_text, causing ^-anchored SECTION_HDR matches to be missed.
        if raw_pages:
            for page_idx, page_text in enumerate(raw_pages):
                if not page_text:
                    continue

                if page_offsets and page_idx < len(page_offsets):
                    offset_entry = page_offsets[page_idx]
                    if isinstance(offset_entry, dict):
                        start_val = offset_entry.get("start")
                        page_base = start_val if isinstance(start_val, int) else None
                    elif isinstance(offset_entry, int):
                        page_base = offset_entry
                    else:
                        page_base = None
                else:
                    page_base = _char_offset_for_page(pages or raw_pages, page_idx + 1)

                if page_base is None:
                    continue

                for match in re.finditer(SECTION_HDR, page_text):
                    num = match.group(1)
                    if not _is_valid_section_number(num):
                        continue

                    abs_start = max(0, page_base + match.start())
                    if abs_start <= toc_cutoff:
                        continue

                    equipment_label = match.group(2)
                    if not _section_hdr_matches_toc(equipment_label, toc_entries, toc_equipment_anchors):
                        continue
                    equip_type = None if equipment_label.upper() == "TURBINE" else _canon(equipment_label)
                    
                    # For bare Turbine headings, look backwards for most recent turbine type.
                    if equip_type is None and equipment_label.upper() == "TURBINE":
                        for prev_candidate in reversed(candidates):
                            if prev_candidate.equipment_type in ("Gas Turbine", "Steam Turbine"):
                                equip_type = prev_candidate.equipment_type
                                break
                        # Doc-level fallback when no prior HEADER/typed candidate exists.
                        if equip_type is None:
                            equip_type = _bare_turbine_from_inventory(active_by_type)
                    
                    if equip_type:
                        section_root_type[num.split('.')[0]] = equip_type
                    candidates.append(
                        HeadingCandidate(
                            start_char=abs_start,
                            heading_text=match.group(0).strip(),
                            heading_type=HeadingType.SECTION_HDR,
                            equipment_type=equip_type,
                            level=0,
                            confidence_rank=80,
                        )
                    )

        # `N Electrical [System]` / `N Electrification` reads as a numbered top-level
        # Generator section. Emitted at the same level and rank as SECTION_HDR so
        # downstream context resolution treats them as Generator roots.
        for match in re.finditer(SECTION_HDR_GEN_KEYWORD, full_text):
            if match.start() <= toc_cutoff:
                continue
            num = match.group(1)
            if not _is_valid_section_number(num):
                continue
            section_root_type[num.split('.')[0]] = "Generator"
            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0).strip(),
                    heading_type=HeadingType.SECTION_HDR,
                    equipment_type="Generator",
                    level=0,
                    confidence_rank=80,
                )
            )

        for match in re.finditer(SUBSEC_GEN, full_text):
            if match.start() <= toc_cutoff:
                continue
            num = match.group(1)
            if not _is_valid_section_number(num):
                continue
            root = num.split('.')[0]
            generator_subsec_starts_by_root.setdefault(root, []).append(match.start())
            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0).strip(),
                    heading_type=HeadingType.SUBSEC,
                    equipment_type="Generator",
                    level=_section_level(num),
                    confidence_rank=75,
                )
            )

        for match in re.finditer(SUBSEC_GEN_KEYWORD, full_text, re.I):
            if match.start() <= toc_cutoff:
                continue
            num = match.group(1)
            if not _is_valid_section_number(num):
                continue
            root = num.split('.')[0]
            # Guardrail: treat these keyword headings as Generator only when
            # the root section is already known as Generator.
            if section_root_type.get(root) != "Generator":
                continue
            generator_subsec_starts_by_root.setdefault(root, []).append(match.start())
            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0).strip(),
                    heading_type=HeadingType.SUBSEC,
                    equipment_type="Generator",
                    level=_section_level(num),
                    confidence_rank=74,
                )
            )

        for match in re.finditer(SUBSEC_TURBINE, full_text, re.I):
            if match.start() <= toc_cutoff:
                continue
            num = match.group(1)
            if not _is_valid_section_number(num):
                continue
            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0).strip(),
                    heading_type=HeadingType.SUBSEC,
                    equipment_type=None,
                    level=_section_level(num),
                    confidence_rank=75,
                )
            )

        for match in re.finditer(SUBSEC_GT, full_text):
            if match.start() <= toc_cutoff:
                continue
            num = match.group(1)
            if not _is_valid_section_number(num):
                continue
            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0).strip(),
                    heading_type=HeadingType.SUBSEC,
                    equipment_type="Gas Turbine",
                    level=_section_level(num),
                    confidence_rank=75,
                )
            )

        seen_generic_subsecs: set[tuple[str, str]] = set()
        for match in re.finditer(SUBSEC_GENERIC, full_text):
            if match.start() <= toc_cutoff:
                continue
            # Real headings never span lines. Multi-line matches (e.g. `3.8\nPosition`)
            # are OCR/page-join artifacts and must be dropped.
            if '\n' in match.group(0).strip():
                continue
            num = match.group(1)
            if not _is_valid_section_number(num):
                continue
            if not _subsec_generic_matches_toc(num, match.group(2) or "", toc_entries):
                continue

            root = num.split('.')[0]
            prior_explicit_headers = [
                candidate for candidate in candidates
                if candidate.start_char < match.start()
                and candidate.heading_type == HeadingType.HEADER
                and candidate.equipment_type
            ]
            segment_start = (
                max(prior_explicit_headers, key=lambda candidate: candidate.start_char).start_char
                if prior_explicit_headers else -1
            )

            context_candidates = [
                candidate for candidate in candidates
                if candidate.start_char < match.start()
                and candidate.start_char >= segment_start
                and candidate.heading_type in (HeadingType.HEADER, HeadingType.SECTION_HDR)
                and candidate.equipment_type
            ]
            context_type = (
                max(context_candidates, key=lambda candidate: candidate.start_char).equipment_type
                if context_candidates else None
            )

            title = (match.group(2) or "").strip().lower()

            # Keep-alive allow-list: when the nearest typed parent context is Generator,
            # this filter would otherwise drop the candidate. Titles starting with a
            # rotor / turbine / component word survive; typing still follows context_type
            # below (Generator parent -> Generator subsec; Gas Turbine parent -> Gas Turbine).
            _gt_flipback = re.match(
                r'^(rotor|turbine|compressor|combustion|inlet|hot\s+gas|exhaust|bearing)\b', title
            )
            # Additional escape hatch: when this root has an explicit Generator top-level
            # section (e.g. `5 Generator` or `5 Electrical System`), any numbered
            # subsection under it is a legitimate Generator scope, so let it through.
            root_is_explicit_generator = section_root_type.get(root) == "Generator"
            if not context_type or (
                context_type == "Generator"
                and not _gt_flipback
                and not root_is_explicit_generator
            ):
                continue

            gen_starts = generator_subsec_starts_by_root.get(root, [])
            if not any(gen_start < match.start() for gen_start in gen_starts):
                continue

            # Skip explicit equipment-prefix headings that should be handled by typed rules.
            if re.match(r'^(generator|gas\s+turbine|steam\s+turbine|exciter|turbine|compressor|combustion|inlet)\b', title):
                continue
            if self._is_low_confidence_generic_subsection_title(title):
                continue

            dedupe_key = (num, re.sub(r'\s+', ' ', title).strip())
            if dedupe_key in seen_generic_subsecs:
                continue
            seen_generic_subsecs.add(dedupe_key)

            candidates.append(
                HeadingCandidate(
                    start_char=match.start(),
                    heading_text=match.group(0).strip(),
                    heading_type=HeadingType.SUBSEC,
                    equipment_type=context_type,
                    level=_section_level(num),
                    confidence_rank=70,
                )
            )

        hint_pages = pages if pages is not None else raw_pages
        for title, _page_number in toc_entries:
            equip_type = None
            low = title.lower()
            if "generator" in low:
                equip_type = "Generator"
            elif "gas turbine" in low or low.strip() == "turbine":
                equip_type = "Gas Turbine"
            elif "steam turbine" in low:
                equip_type = "Steam Turbine"

            if not equip_type:
                continue

            hint_char = _char_offset_for_page(hint_pages, _page_number)
            match_start = _find_title_with_page_hint(full_text, title, hint_char)
            if match_start is None:
                continue

            candidates.append(
                HeadingCandidate(
                    start_char=match_start,
                    heading_text=title,
                    heading_type=HeadingType.TOC,
                    equipment_type=equip_type,
                    level=-1 if "section" not in low else 0,
                    confidence_rank=50,
                )
            )

        deduped = self._dedupe_overlapping_candidates(candidates)
        pruned = self._suppress_redundant_unnumbered_candidates(deduped)
        return pruned, toc_entries

    def _dedupe_overlapping_candidates(self, candidates: list[HeadingCandidate]) -> list[HeadingCandidate]:
        if not candidates:
            return []

        # Prefer higher confidence when two candidates begin within a small window.
        by_pos = sorted(candidates, key=lambda c: (c.start_char, -c.confidence_rank))
        result: list[HeadingCandidate] = []

        for cand in by_pos:
            if not result:
                result.append(cand)
                continue

            last = result[-1]
            if abs(cand.start_char - last.start_char) <= 3:
                if cand.confidence_rank > last.confidence_rank:
                    result[-1] = cand
                continue

            result.append(cand)

        return sorted(result, key=lambda c: c.start_char)

    def _build_hierarchical_spans(self, candidates: list[HeadingCandidate], full_len: int) -> list[SectionSpan]:
        spans: list[SectionSpan] = []
        stack: list[int] = []

        for idx, cand in enumerate(candidates):
            level_conflict = False
            parent_idx: int | None = None

            if stack and cand.level >= 0:
                has_expected_parent = any(
                    spans[open_idx].level == cand.level - 1
                    for open_idx in stack
                )
                top_level = spans[stack[-1]].level
                if not has_expected_parent and top_level >= 0:
                    # Numbering conflict fallback:
                    # 1) prefer nearest lower-level ancestor within the same root (e.g., 2.x)
                    # 2) if root changed and expected parent is missing, re-anchor to top equipment header
                    # 3) otherwise leave parent unset for this span
                    level_conflict = True
                    cand_num = _extract_heading_section_number(cand.heading_text)
                    cand_root = cand_num.split('.')[0] if cand_num else None

                    if cand_root:
                        for open_idx in reversed(stack):
                            ancestor = spans[open_idx]
                            if ancestor.level < 0 or ancestor.level >= cand.level:
                                continue
                            anc_num = _extract_heading_section_number(ancestor.heading_text)
                            if not anc_num:
                                continue
                            if anc_num.split('.')[0] == cand_root:
                                parent_idx = open_idx
                                break

                        if parent_idx is None:
                            for open_idx in reversed(stack):
                                ancestor = spans[open_idx]
                                if ancestor.level < 0 and ancestor.equipment_type:
                                    parent_idx = open_idx
                                    break
                    else:
                        parent_idx = stack[-1]

            if not level_conflict:
                while stack and cand.level <= spans[stack[-1]].level:
                    stack.pop()
                parent_idx = stack[-1] if stack else None

                # Root-aware correction for normal stack attachment path.
                # Example: avoid attaching 3.1 under a 2.x branch when parent 3 is missing.
                if parent_idx is not None and cand.level >= 0:
                    cand_num = _extract_heading_section_number(cand.heading_text)
                    parent_num = _extract_heading_section_number(spans[parent_idx].heading_text)
                    cand_root = cand_num.split('.')[0] if cand_num else None
                    parent_root = parent_num.split('.')[0] if parent_num else None

                    if cand_root and parent_root and cand_root != parent_root:
                        level_conflict = True

                        reanchored_parent: int | None = None
                        for open_idx in reversed(stack):
                            ancestor = spans[open_idx]
                            if ancestor.level < 0 or ancestor.level >= cand.level:
                                continue
                            anc_num = _extract_heading_section_number(ancestor.heading_text)
                            if not anc_num:
                                continue
                            if anc_num.split('.')[0] == cand_root:
                                reanchored_parent = open_idx
                                break

                        if reanchored_parent is None:
                            for open_idx in reversed(stack):
                                ancestor = spans[open_idx]
                                if ancestor.level < 0 and ancestor.equipment_type:
                                    reanchored_parent = open_idx
                                    break

                        parent_idx = reanchored_parent

            spans.append(
                SectionSpan(
                    start=max(0, cand.start_char),
                    end=full_len,
                    level=cand.level,
                    heading_text=cand.heading_text,
                    heading_type=cand.heading_type,
                    equipment_type=cand.equipment_type,
                    local_esn=cand.local_esn,
                    parent_idx=parent_idx,
                    level_conflict=level_conflict,
                )
            )
            stack.append(idx)

        self._assign_span_end_offsets(spans, full_len)
        return spans

    def _assign_span_end_offsets(self, spans: list[SectionSpan], full_len: int) -> None:
        for idx, span in enumerate(spans):
            end_at = full_len
            for nxt in spans[idx + 1:]:
                if nxt.level <= span.level:
                    end_at = nxt.start
                    break
            span.end = max(span.start, min(end_at, full_len))

    def _seed_summary_from_toc(self, spans: list[SectionSpan], toc_entries: list[tuple[str, int]]) -> None:
        summary_titles = [title for title, _page in toc_entries if _is_doc_summary(title)]
        normalized = [re.sub(r'\s+', ' ', t.lower()).strip() for t in summary_titles]

        for span in spans:
            heading_norm = re.sub(r'\s+', ' ', span.heading_text.lower()).strip()
            if _is_doc_summary(span.heading_text):
                span.is_summary = True
                continue
            span.is_summary = any(h in heading_norm or heading_norm in h for h in normalized)

    def _infer_equipment_for_untyped_subsections(self, spans: list[SectionSpan]) -> None:
        # Handle untyped SUBSEC headings with segment-aware context.
        for idx, span in enumerate(spans):
            if span.heading_type != HeadingType.SUBSEC or span.equipment_type:
                continue

            num = _extract_heading_section_number(span.heading_text)
            if not num or '.' not in num:
                continue

            root = num.split('.')[0]

            # Segment boundary awareness: stop cross-report leakage by limiting
            # inference to content after the nearest explicit equipment header.
            segment_start_idx = 0
            for j in range(idx - 1, -1, -1):
                if spans[j].heading_type == HeadingType.HEADER and spans[j].equipment_type:
                    segment_start_idx = j
                    break

            inferred_type: str | None = None

            # Prefer nearest prior typed section/subsection in the same root inside segment.
            for prev in reversed(spans[segment_start_idx:idx]):
                if not prev.equipment_type:
                    continue
                prev_num = _extract_heading_section_number(prev.heading_text)
                if not prev_num:
                    continue
                if prev_num.split('.')[0] == root:
                    inferred_type = prev.equipment_type
                    break

            # Fallback: inherit explicit typed parent when available.
            if not inferred_type and span.parent_idx is not None:
                parent = spans[span.parent_idx]
                if parent.equipment_type:
                    parent_num = _extract_heading_section_number(parent.heading_text)
                    if not parent_num or parent_num.split('.')[0] == root:
                        inferred_type = parent.equipment_type

            if inferred_type:
                span.equipment_type = inferred_type

    def _resolve_span_esn_with_ibat_train(
        self,
        equip_type: str,
        active_by_type: dict[str, list[str]],
        ibat_resolver: Callable[[str, dict[str, Any]], list[str]] | None,
        context: dict[str, Any],
    ) -> str | None:
        if ibat_resolver is None:
            return None
        try:
            candidates = ibat_resolver(equip_type, context) or []
        except Exception:
            return None

        normalized = []
        for candidate in candidates:
            esn = _norm(candidate)
            if not esn or re.match(r'^SY\d{7}$', esn):
                continue
            normalized.append(esn)

        # Candidate pool preference is configurable while policy is finalized.
        # Current default: broad_esns first, then all_esns.
        pool_order = context.get("candidate_pool_order") or list(self.IBAT_CANDIDATE_POOL_ORDER)
        for pool_key in pool_order:
            pool_values = context.get(pool_key)
            if not pool_values:
                continue
            pool = {_norm(v) for v in pool_values if _norm(v)}
            filtered = [esn for esn in normalized if esn in pool]
            if len(filtered) == 1:
                return filtered[0]
            if len(filtered) > 1:
                # Keep trying later pools only when this pool produced no candidates.
                return None

        if len(normalized) == 1:
            return normalized[0]
        return None

    def _resolve_span_esn_local_first(
        self,
        spans: list[SectionSpan],
        esn_ctx: dict[str, Any],
        ibat_resolver: Callable[[str, dict[str, Any]], list[str]] | None,
    ) -> None:
        active = set(esn_ctx.get("active", set()))
        active_by_type = esn_ctx.get("active_by_type", {})
        all_esns = set(esn_ctx.get("all_esns", set()))
        broad_esns = set(esn_ctx.get("broad_esns", set()))

        # A bare numbered "Turbine" heading is ambiguous by itself. Prefer the
        # nearest explicit Steam/Gas parent; without one, use document inventory
        # only when exactly one turbine type is present.
        for span in spans:
            if span.equipment_type or not _is_bare_turbine_heading(span.heading_text):
                continue

            parent = spans[span.parent_idx] if span.parent_idx is not None else None
            if parent and parent.equipment_type in ("Gas Turbine", "Steam Turbine"):
                span.equipment_type = parent.equipment_type
                continue

            available_turbine_types = [
                equip_type
                for equip_type in ("Gas Turbine", "Steam Turbine")
                if active_by_type.get(equip_type)
            ]
            if len(available_turbine_types) == 1:
                span.equipment_type = available_turbine_types[0]

        current_turbine_esn: str | None = None
        last_resolved_by_type: dict[str, tuple[str, int]] = {}
        for idx, span in enumerate(spans):
            fallback_chain = ["local", "parent", "single_type", "ibat_train", "none"]

            if span.local_esn and (not active or span.local_esn in active):
                span.resolved_esn = span.local_esn
                span.esn_source = EsnSource.LOCAL_HEADER
                span.esn_confidence = EsnConfidence.HIGHEST
            else:
                parent = spans[span.parent_idx] if span.parent_idx is not None else None
                if (
                    parent
                    and parent.resolved_esn
                    and span.equipment_type
                    and parent.equipment_type == span.equipment_type
                ):
                    span.resolved_esn = parent.resolved_esn
                    span.esn_source = EsnSource.PARENT_INHERIT
                    span.esn_confidence = EsnConfidence.HIGH
                elif span.equipment_type:
                    same_type = list(active_by_type.get(span.equipment_type, []))
                    if len(same_type) == 1:
                        span.resolved_esn = same_type[0]
                        span.esn_source = EsnSource.SINGLE_TYPE
                        span.esn_confidence = EsnConfidence.HIGH
                    else:
                        ibat_context = {
                            "active_esns": sorted(active),
                            "all_esns": sorted(all_esns),
                            "broad_esns": sorted(broad_esns),
                            "candidate_pool_order": list(self.IBAT_CANDIDATE_POOL_ORDER),
                            "current_turbine_esn": current_turbine_esn,
                            "span_index": idx,
                            "fallback_chain": fallback_chain,
                        }
                        ibat_esn = self._resolve_span_esn_with_ibat_train(
                            span.equipment_type,
                            active_by_type,
                            ibat_resolver,
                            ibat_context,
                        )
                        if ibat_esn:
                            span.resolved_esn = ibat_esn
                            span.esn_source = EsnSource.IBAT_TRAIN
                            span.esn_confidence = EsnConfidence.LOW
                        else:
                            recovered = False
                            # Guardrailed fallback for unresolved typed spans:
                            # recover from recent same-type context when available,
                            # but leave ESN empty when context is stale to preserve
                            # a clear debugging signal.
                            if span.equipment_type and span.equipment_type in last_resolved_by_type:
                                last_esn, last_start = last_resolved_by_type[span.equipment_type]
                                if abs(span.start - last_start) <= self.LAST_KNOWN_CONTEXT_MAX_CHAR_GAP:
                                    span.resolved_esn = last_esn
                                    span.esn_source = EsnSource.PARENT_INHERIT
                                    span.esn_confidence = EsnConfidence.LOW
                                    recovered = True

                            if not recovered:
                                span.esn_source = EsnSource.NONE
                                span.esn_confidence = EsnConfidence.NONE
                else:
                    parent = spans[span.parent_idx] if span.parent_idx is not None else None
                    if parent and parent.resolved_esn:
                        span.resolved_esn = parent.resolved_esn
                        span.equipment_type = parent.equipment_type
                        span.esn_source = EsnSource.PARENT_INHERIT
                        span.esn_confidence = EsnConfidence.HIGH
                    else:
                        span.esn_source = EsnSource.NONE
                        span.esn_confidence = EsnConfidence.NONE

            if span.equipment_type and span.resolved_esn:
                last_resolved_by_type[span.equipment_type] = (span.resolved_esn, span.start)

            if span.equipment_type in ("Gas Turbine", "Steam Turbine") and span.resolved_esn:
                current_turbine_esn = span.resolved_esn

    def _section_path_for_span(self, spans: list[SectionSpan], span: SectionSpan) -> list[str]:
        path: list[str] = []
        cursor: SectionSpan | None = span
        seen: set[int] = set()
        while cursor is not None:
            path.append(cursor.heading_text)
            parent_idx = cursor.parent_idx
            if parent_idx is None or parent_idx in seen:
                break
            seen.add(parent_idx)
            cursor = spans[parent_idx]
        path.reverse()
        return path[:5]

    def _region_meta(
        self,
        spans: list[SectionSpan],
        span: SectionSpan,
        gt_tech: str | None,
        gen_tech: str | None,
    ) -> RegionMetadata:
        tech_code = None
        if span.equipment_type == "Gas Turbine":
            tech_code = gt_tech
        elif span.equipment_type == "Generator":
            tech_code = gen_tech

        return RegionMetadata(
            primary_esn=span.resolved_esn,
            primary_equip_type=span.equipment_type,
            primary_technology_code=tech_code,
            esn_confidence=span.esn_confidence,
            esn_source=span.esn_source,
            equip_type_source="heading" if span.equipment_type else "none",
            region_source=RegionSource.SECTION_SPAN,
            section_path=self._section_path_for_span(spans, span),
            fallback_chain=["local", "parent", "single_type", "ibat_train", "none"],
        )

    def _gap_region_meta(
        self,
        left: Region | None,
        right: Region | None,
        gt_tech: str | None,
        gen_tech: str | None,
        gap_len: int,
    ) -> RegionMetadata:
        # Guardrail: avoid inheriting ESN over large unknown spans.
        if gap_len > 2000:
            return RegionMetadata(
                primary_equip_type="shared",
                esn_confidence=EsnConfidence.NONE,
                esn_source=EsnSource.NONE,
                equip_type_source="none",
                region_source=RegionSource.GAP_FALLBACK,
                fallback_chain=["gap_too_large", "shared"],
            )

        left_esn = left.metadata.primary_esn if left else None
        right_esn = right.metadata.primary_esn if right else None
        left_type = left.metadata.primary_equip_type if left else None
        right_type = right.metadata.primary_equip_type if right else None

        if left_esn and right_esn and left_esn == right_esn:
            equip_type = left_type or right_type
            tech = gen_tech if equip_type == "Generator" else gt_tech
            return RegionMetadata(
                primary_esn=left_esn,
                primary_equip_type=equip_type,
                primary_technology_code=tech,
                esn_confidence=EsnConfidence.LOW,
                esn_source=EsnSource.NEIGHBOR_GAP,
                equip_type_source="neighbor_consensus",
                region_source=RegionSource.GAP_FALLBACK,
                fallback_chain=["neighbor_both", "neighbor_single", "shared"],
            )

        if left_esn and right_esn and left_esn != right_esn:
            # Deterministic tie-break: choose left when both sides disagree.
            equip_type = left_type or right_type
            tech = gen_tech if equip_type == "Generator" else gt_tech
            return RegionMetadata(
                primary_esn=left_esn,
                primary_equip_type=equip_type,
                primary_technology_code=tech,
                esn_confidence=EsnConfidence.LOW,
                esn_source=EsnSource.NEIGHBOR_GAP,
                equip_type_source="neighbor_single",
                region_source=RegionSource.GAP_FALLBACK,
                fallback_chain=["neighbor_distance_tie_left", "shared"],
            )

        if left_esn or right_esn:
            esn = left_esn or right_esn
            equip_type = left_type if left_esn else right_type
            tech = gen_tech if equip_type == "Generator" else gt_tech
            return RegionMetadata(
                primary_esn=esn,
                primary_equip_type=equip_type,
                primary_technology_code=tech,
                esn_confidence=EsnConfidence.LOW,
                esn_source=EsnSource.NEIGHBOR_GAP,
                equip_type_source="neighbor_consensus" if left_type == right_type else "neighbor_single",
                region_source=RegionSource.GAP_FALLBACK,
                fallback_chain=["neighbor_single", "shared"],
            )

        shared_type = left_type if left_type and left_type == right_type else "shared"
        return RegionMetadata(
            primary_equip_type=shared_type,
            esn_confidence=EsnConfidence.NONE,
            esn_source=EsnSource.NONE,
            equip_type_source="neighbor_consensus" if shared_type != "shared" else "none",
            region_source=RegionSource.GAP_FALLBACK,
            fallback_chain=["shared"],
        )

    def _emit_regions_full_coverage(
        self,
        spans: list[SectionSpan],
        full_len: int,
        gt_tech: str | None,
        gen_tech: str | None,
    ) -> list[Region]:
        informative_spans = [
            span for span in spans
            if span.end > span.start and (span.equipment_type or span.resolved_esn)
        ]

        if not informative_spans:
            return [
                Region(
                    start=0,
                    end=full_len,
                    metadata=RegionMetadata(
                        primary_equip_type="shared",
                        esn_confidence=EsnConfidence.NONE,
                        esn_source=EsnSource.NONE,
                        equip_type_source="none",
                        region_source=RegionSource.SYNTHETIC,
                        fallback_chain=["shared"],
                    ),
                )
            ]

        boundaries = {0, full_len}
        for span in informative_spans:
            boundaries.add(span.start)
            boundaries.add(span.end)
        ordered = sorted(boundaries)

        atomic_regions: list[Region] = []
        for left, right in zip(ordered, ordered[1:]):
            if right <= left:
                continue
            covering = [
                span for span in informative_spans
                if span.start <= left and span.end >= right
            ]
            if covering:
                chosen = sorted(
                    covering,
                    key=lambda span: (span.level, span.start, span.end),
                    reverse=True,
                )[0]
                atomic_regions.append(
                    Region(
                        start=left,
                        end=right,
                        metadata=self._region_meta(spans, chosen, gt_tech, gen_tech),
                    )
                )
            elif not atomic_regions:
                atomic_regions.append(
                    Region(
                        start=left,
                        end=right,
                        metadata=RegionMetadata(
                            primary_equip_type="shared",
                            esn_confidence=EsnConfidence.NONE,
                            esn_source=EsnSource.NONE,
                            equip_type_source="none",
                            region_source=RegionSource.FRONT_MATTER,
                            fallback_chain=["front_matter"],
                        ),
                    )
                )
            else:
                atomic_regions.append(
                    Region(
                        start=left,
                        end=right,
                            metadata=self._gap_region_meta(
                                atomic_regions[-1],
                                None,
                                gt_tech,
                                gen_tech,
                                gap_len=right - left,
                            ),
                    )
                )

        if atomic_regions:
            atomic_regions[0].metadata.region_source = (
                RegionSource.FRONT_MATTER if atomic_regions[0].start == 0 and atomic_regions[0].metadata.region_source == RegionSource.GAP_FALLBACK
                else atomic_regions[0].metadata.region_source
            )
            atomic_regions[-1].metadata.region_source = (
                RegionSource.TRAILING if atomic_regions[-1].end == full_len and atomic_regions[-1].metadata.region_source == RegionSource.GAP_FALLBACK
                else atomic_regions[-1].metadata.region_source
            )

        merged: list[Region] = []
        for region in atomic_regions:
            if region.end <= region.start:
                continue
            if not merged:
                merged.append(region)
                continue
            last = merged[-1]
            if last.end == region.start and _model_to_dict(last.metadata) == _model_to_dict(region.metadata):
                last.end = region.end
            else:
                merged.append(region)

        return merged

    def _emit_document_summary(self, full_text: str, spans: list[SectionSpan], raw_pages: list[str]) -> str | None:
        summary_parts: list[str] = []
        for span in spans:
            if not span.is_summary:
                continue
            if span.end <= span.start:
                continue
            summary_txt = full_text[span.start:span.end].strip()
            if summary_txt:
                summary_parts.append(summary_txt)

        if summary_parts:
            return "\n\n".join(summary_parts).strip()

        # Fallback to page-based TOC extraction if span matching is unavailable.
        try:
            toc_entries, total_pages = _extract_toc_entries_from_pages(raw_pages)
            sections = []
            for i, (title, start_page) in enumerate(toc_entries):
                if not _is_doc_summary(title):
                    continue
                end_page = toc_entries[i + 1][1] - 1 if i + 1 < len(toc_entries) else total_pages
                sections.append((start_page, end_page))

            for start_page, end_page in sections:
                text = _extract_section_text_from_pages(raw_pages, start_page, end_page)
                if text:
                    summary_parts.append(text)
        except Exception:
            return None

        if not summary_parts:
            return None
        return "\n\n".join(summary_parts).strip()

    def _build_document_metadata(
        self,
        filename: str,
        title_text: str,
        esn_ctx: dict[str, Any],
        spans: list[SectionSpan],
        summary_text: str | None,
        field_names: set[str],
    ) -> dict[str, Any]:
        doc: dict[str, Any] = {}

        esn_coverage: dict[str, int] = {}
        type_coverage: dict[str, int] = {}
        for span in spans:
            length = max(0, span.end - span.start)
            if span.resolved_esn:
                esn_coverage[span.resolved_esn] = esn_coverage.get(span.resolved_esn, 0) + length
            if span.equipment_type:
                type_coverage[span.equipment_type] = type_coverage.get(span.equipment_type, 0) + length

        primary_esn = max(esn_coverage, key=esn_coverage.get) if esn_coverage else None

        primary_type = None
        if type_coverage:
            sorted_types = sorted(type_coverage.items(), key=lambda kv: kv[1], reverse=True)
            if len(sorted_types) >= 2 and sorted_types[0][1] == sorted_types[1][1]:
                primary_type = "shared"
            else:
                primary_type = sorted_types[0][0]

        gt_tech = None
        gen_tech = None
        gm = re.search(r'\b(7[A-Z]{1,2}(?:\.\d{2})?)\b', title_text)
        if gm:
            gt_tech = gm.group(1)
        gn = re.search(r'\b(7?FH2|7H2(?:-[A-Z]{2})?)\b', title_text)
        if gn:
            gen_tech = gn.group(1)

        if 'document_name' in field_names:
            doc['document_name'] = filename

        active = set(esn_ctx.get('active', set()))
        inactive = set(esn_ctx.get('inactive', set()))
        esn_type = esn_ctx.get('esn_type', {})

        gt_esns = sorted([e for e in active if esn_type.get(e) == 'Gas Turbine'])
        gen_esns = sorted([e for e in active if esn_type.get(e) in ('Generator', 'Exciter')])
        st_esns = sorted([e for e in active if esn_type.get(e) == 'Steam Turbine'])

        if 'gt_esn' in field_names and gt_esns:
            doc['gt_esn'] = gt_esns[0]
        if 'gen_esn' in field_names and gen_esns:
            doc['gen_esn'] = gen_esns[0]
        if 'st_esn' in field_names and st_esns:
            doc['st_esn'] = st_esns[0]
        if 'all_esns' in field_names and esn_ctx.get('all_esns'):
            doc['all_esns'] = ", ".join(sorted(esn_ctx['all_esns']))
        if 'inactive_esns' in field_names and inactive:
            doc['inactive_esns'] = ", ".join(sorted(inactive))

        if 'primary_esn' in field_names and primary_esn:
            doc['primary_esn'] = primary_esn
        if 'primary_equip_type' in field_names and primary_type:
            doc['primary_equip_type'] = primary_type

        if 'primary_technology_code' in field_names:
            if primary_type == 'Generator' and gen_tech:
                doc['primary_technology_code'] = gen_tech
            elif primary_type == 'Gas Turbine' and gt_tech:
                doc['primary_technology_code'] = gt_tech
            elif gt_tech or gen_tech:
                doc['primary_technology_code'] = gt_tech or gen_tech

        def find_date(labels: list[str]) -> str | None:
            for pattern in labels:
                match = re.search(pattern, title_text, re.I)
                if match:
                    val = _clean_date(match.group(1))
                    if val:
                        return val
            return None

        if 'outage_start_date' in field_names:
            val = find_date(START_LABELS)
            if val:
                doc['outage_start_date'] = val
        if 'outage_end_date' in field_names:
            val = find_date(END_LABELS)
            if val:
                doc['outage_end_date'] = val
        if 'report_issued_date' in field_names:
            val = find_date(ISSUED_LABELS)
            if val:
                doc['report_issued_date'] = val

        if summary_text:
            doc['document_summary'] = summary_text

        return doc

    def _build_hints(
        self,
        esn_ctx: dict[str, Any],
        metadata: dict[str, Any],
        spans: list[SectionSpan],
    ) -> str:
        lines: list[str] = []
        active = set(esn_ctx.get('active', set()))
        inactive = set(esn_ctx.get('inactive', set()))
        esn_type = esn_ctx.get('esn_type', {})

        if active:
            lines.append(
                "Active equipment (work performed): " +
                ", ".join(f"{esn} ({esn_type.get(esn, 'Unknown')})" for esn in sorted(active))
            )
        if inactive:
            lines.append(
                "Inactive equipment (listed on title page but NOT applicable this outage): " +
                ", ".join(sorted(inactive)) +
                ". Do NOT attribute any content to these ESNs."
            )

        confidence_counts: dict[str, int] = {}
        for span in spans:
            key = span.esn_confidence.value
            confidence_counts[key] = confidence_counts.get(key, 0) + 1

        lines.append(
            "Section ESN confidence distribution: " +
            ", ".join(f"{k}={v}" for k, v in sorted(confidence_counts.items()))
        )
        conflict_count = sum(1 for span in spans if span.level_conflict)
        lines.append(f"Section hierarchy level conflicts flagged: {conflict_count}")
        lines.append(
            "Primary equipment inference: primary_equip_type=" +
            str(metadata.get('primary_equip_type')) +
            ", primary_esn=" + str(metadata.get('primary_esn')) + "."
        )
        lines.append(
            "If any of outage_start_date, outage_end_date, report_issued_date, event_type are not already provided, "
            "extract them from the title page."
        )
        return "\n".join(lines)

    def preprocess(
        self,
        ctx: Any,
        ibat_resolver: Callable[[str, dict[str, Any]], list[str]] | None = None,
    ) -> dict[str, Any]:
        pages = list(ctx.pages or [])
        raw_pages = list((getattr(ctx, 'raw_pages', None) or pages) or [])
        full_text = ctx.full_text or ""
        fields = list(ctx.fields or [])
        field_names = set(f.get('name') for f in fields)

        esn_ctx = self._discover_esn_context(pages, full_text)
        candidates, toc_entries = self._collect_heading_candidates(
            full_text,
            raw_pages,
            pages=pages,
            page_offsets=list((getattr(ctx, 'page_offsets', None) or [])),
            active_by_type=esn_ctx.get("active_by_type"),
        )
        spans = self._build_hierarchical_spans(candidates, len(full_text))
        self._seed_summary_from_toc(spans, toc_entries)
        self._infer_equipment_for_untyped_subsections(spans)
        self._resolve_span_esn_local_first(spans, esn_ctx, ibat_resolver)

        title_text = esn_ctx.get('title', '')
        gt_tech = re.search(r'\b(7[A-Z]{1,2}(?:\.\d{2})?)\b', title_text)
        gt_tech_val = gt_tech.group(1) if gt_tech else None
        gen_tech = re.search(r'\b(7?FH2|7H2(?:-[A-Z]{2})?)\b', title_text)
        gen_tech_val = gen_tech.group(1) if gen_tech else None

        regions = self._emit_regions_full_coverage(spans, len(full_text), gt_tech_val, gen_tech_val)
        summary_text = self._emit_document_summary(full_text, spans, raw_pages)

        metadata = self._build_document_metadata(
            filename=getattr(ctx, 'filename', ''),
            title_text=title_text,
            esn_ctx=esn_ctx,
            spans=spans,
            summary_text=summary_text,
            field_names=field_names,
        )
        hints = self._build_hints(esn_ctx, metadata, spans)

        out = PreprocessOutput(
            metadata=metadata,
            hints=hints,
            regions=regions,
        )

        return {
            "metadata": out.metadata,
            "hints": out.hints,
            "regions": [_model_to_dict(region) for region in out.regions],
        }


_PREPROCESSOR_V2 = FSRV2Preprocessor()


def preprocess(
    ctx: Any,
    ibat_resolver: Callable[[str, dict[str, Any]], list[str]] | None = None,
) -> dict[str, Any]:
    return _PREPROCESSOR_V2.preprocess(ctx, ibat_resolver=ibat_resolver)
