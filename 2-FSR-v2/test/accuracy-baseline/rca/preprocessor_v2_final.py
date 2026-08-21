import re

# GE FSR metadata preprocessor — v2 (Priority 1: content-weighted primary).
# Changes vs v1:
#   1. Adds GT_SIGNATURES to parallel GEN_SIGNATURES.
#   2. Picks primary_esn / primary_equip_type by which equipment actually
#      owns most of the document body, not by GT-first fallback.
#      Uses section-boundary byte-share as the strong signal, corroborated
#      by document-wide signature counts.
#   3. Falls back to 'shared' when neither equipment clearly dominates.
# Everything else is unchanged from v1 so results are directly comparable.

NOT_APPLICABLE = [
    r'(?i)this equipment is not applicable',
    r'(?i)not applicable for this outage',
    r'(?i)no work performed on this (?:unit|equipment)',
    r'(?i)not included in (?:this )?scope',
]

# Section headers like:  GENERATOR (337X766 | SY0072576)
HEADER = r'(GAS TURBINE|GENERATOR|STEAM TURBINE|EXCITER)\s*\(\s*(\d{3}[A-Z]?\d{3})\s*\|\s*(SY\d{7})\)'

GT_LABELS = [
    r'Gas\s*Turbine\s*(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
    r'Assoc(?:iated)?\.?\s*Turbine\s*[:#]?\s*(\d{6})',
]
GEN_LABELS = [
    r'Gen(?:erator)?\s*(?:ESN|Serial\s*(?:No|#|Number))\.?\s*[:#]\s*(\d{3}[A-Z]\d{3})',
]
GENERIC_LABELS = [
    r'Equipment\s*Serial\s*#?\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
    r'\bESN\s*[:#]\s*(\d{3}[A-Z]?\d{3})',
]

GEN_FORMS = ['D3162041','D3162043','D3162044','D316218','D316303','D316402',
             'D316403','D316501','D316512','D300001','D306301','D306302',
             'D309102','D309301','D309302','D315102']
GT_FORMS = ['GT3225','GT9245','GT9386','GT9390','GT4050','GT1040','GT71F040','GT71F045']

# Generator-only content signatures (kept from v1, plus a few additions).
GEN_SIGNATURES = [
    'armature winding resistance', 'armature insulation', 'hipotential testing',
    'stator voltage', 'polarization index', 'power mva', 'max h2 pressure',
    'collector end', 'dc leakage', 'stator insulation resistance',
    'endwinding', 'end winding', 'retaining ring', 'field winding',
    'el-cid', 'el cid', 'wedge tightness', 'stator core',
    'hydrogen seal', 'diode wheel', 'partial discharge', 'stator rewind',
    'core lamination', 'generator specialist',
]

# Gas turbine-only content signatures (new in v2). Deliberately narrow —
# words that appear on GT pages but not on generator pages.
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
END_LABELS   = [r'(?:Job|Outage)\s*(?:End|Completion)\s*Date\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']
ISSUED_LABELS= [r'(?:Approved|Report\s*Issued|Date\s*Issued)\s*(?:Date)?\s*[:#]\s*([0-9A-Za-z /,.\-]{6,24})']

_DATE_STOP = r'\s{2,}|Oracle|Prepared|Approved|Equipment|Report|Contents|Generator|Gas\s*Turbine|Job\b'


def _norm(esn):
    return esn.upper().strip()


def _clean_date(s):
    s = s.strip().rstrip('.').strip()
    s = re.split(_DATE_STOP, s)[0].strip()
    return s or None


def _count_sig(text_lower, sig_list):
    return sum(text_lower.count(s) for s in sig_list)


def preprocess(ctx):
    pages = ctx.pages or []
    offsets = ctx.page_offsets or []
    full = ctx.full_text or ""
    field_names = set(f.get('name') for f in (ctx.fields or []))
    title = "\n".join(pages[:6]) if pages else full[:8000]

    # ---- collect ESNs + equipment types (unchanged) ----
    esn_type = {}
    header_hits = []

    def set_type(esn, t):
        esn = _norm(esn)
        if not esn:
            return
        cur = esn_type.get(esn)
        if t and (cur is None or cur == 'Unknown'):
            esn_type[esn] = t
        elif esn not in esn_type:
            esn_type[esn] = t or 'Unknown'

    for i, ptext in enumerate(pages):
        for m in re.finditer(HEADER, ptext, re.I):
            t = m.group(1).title()
            esn = _norm(m.group(2))
            header_hits.append((i, t, esn))
            set_type(esn, t)

    for pat in GT_LABELS:
        for m in re.finditer(pat, title, re.I):
            set_type(m.group(1), 'Gas Turbine')
    for pat in GEN_LABELS:
        for m in re.finditer(pat, title, re.I):
            set_type(m.group(1), 'Generator')
    for pat in GENERIC_LABELS:
        for m in re.finditer(pat, title, re.I):
            esn = _norm(m.group(1))
            set_type(esn, 'Generator' if re.search(r'[A-Z]', esn) else 'Gas Turbine')

    for ptext in pages:
        for pat in GEN_LABELS + [r'Equipment\s*Serial\s*#?\s*[:#]\s*(\d{3}[A-Z]\d{3})']:
            for m in re.finditer(pat, ptext, re.I):
                set_type(m.group(1), 'Generator')

    all_esns = set(esn_type.keys())

    # ---- Inactive ESNs (unchanged) ----
    inactive = set()
    for ptext in pages:
        if any(re.search(p, ptext) for p in NOT_APPLICABLE):
            for esn in all_esns:
                if esn in ptext:
                    inactive.add(esn)
    active = all_esns - inactive

    def first_active(t):
        for e in sorted(active):
            if esn_type.get(e) == t:
                return e
        return None

    gt_esn = first_active('Gas Turbine')
    gen_esn = first_active('Generator')

    # ---- Frame codes (unchanged) ----
    gt_tech = None
    gen_tech = None
    gm = re.search(r'\b(7[A-Z]{1,2}(?:\.\d{2})?)\b', title)
    if gm:
        gt_tech = gm.group(1)
    gn = re.search(r'\b(7?FH2|7H2(?:-[A-Z]{2})?)\b', full)
    if gn:
        gen_tech = gn.group(1)

    def tech_for(t):
        if t == 'Generator':
            return gen_tech
        if t == 'Gas Turbine':
            return gt_tech
        return None

    # ---- Build boundaries first (needed for byte-share primary selection) ----
    SECTION_HDR = r'(?im)^\s*#{0,3}\s*\d+[ \t]+(GAS\s+TURBINE|TURBINE|GENERATOR|STEAM\s+TURBINE|EXCITER)\s*$'

    def _canon(name):
        n = name.strip().lower()
        if 'generator' in n:
            return 'Generator'
        if 'exciter' in n:
            return 'Exciter'
        if 'steam' in n:
            return 'Steam Turbine'
        return 'Gas Turbine'

    # FIX 2 (part A): Register ESNs found in HEADER matches on full_text.
    # Some documents only mention the Generator ESN mid-document (not on title page).
    for m in re.finditer(HEADER, full, re.I):
        set_type(_norm(m.group(2)), m.group(1).title())
    # Re-derive gen_esn/gt_esn with newly discovered ESNs
    active = (all_esns | set(esn_type.keys())) - inactive
    gt_esn = None
    gen_esn = None
    for e in sorted(active):
        if esn_type.get(e) == 'Gas Turbine' and not gt_esn:
            gt_esn = e
        elif esn_type.get(e) == 'Generator' and not gen_esn:
            gen_esn = e

    # Also scan for Generator ESN patterns in body text (buried on data sheets)
    if not gen_esn:
        for m in re.finditer(r'Generator\s+(?:Serial\s+No|SN|ESN)\.?\s*[:#]?\s*(\d{3}[A-Z]\d{3})', full, re.I):
            esn = _norm(m.group(1))
            set_type(esn, 'Generator')
            if not gen_esn:
                gen_esn = esn
                active.add(esn)

    boundaries = []
    for m in re.finditer(HEADER, full, re.I):
        boundaries.append((m.start(), m.group(1).title(), _norm(m.group(2))))
    for m in re.finditer(SECTION_HDR, full):
        t = _canon(m.group(1))
        e = gen_esn if t in ('Generator', 'Exciter') else (gt_esn if t == 'Gas Turbine' else None)
        boundaries.append((m.start(), t, e))

    # FIX 2: Detect subsection-level Generator headers for documents where
    # Generator content is nested under a "Turbine" top-level section.
    # Pattern: "3.1.1 Generator Stator/Field Tests..." — numbered subsection
    # starting with "Generator" indicates a Generator region.
    # Only match real section numbers (1-2 digits per level, max 3 levels).
    # Excludes form numbers like "014.2.2" or "400.3.9".
    SUBSEC_GEN = r'(?m)^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?) Generator\b'
    SUBSEC_GT = r'(?m)^(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?) (?:Turbine|Compressor|Combustion|Inlet)\b'
    gen_subsecs = [(m.start(), m.group(1)) for m in re.finditer(SUBSEC_GEN, full)]
    gt_subsecs = [(m.start(), m.group(1)) for m in re.finditer(SUBSEC_GT, full)]
    if gen_subsecs and gen_esn:
        for gs_pos, gs_num in gen_subsecs:
            # Find end: next GT subsection after this Generator subsection
            end_pos = len(full)
            for gt_pos, gt_num in gt_subsecs:
                if gt_pos > gs_pos:
                    end_pos = gt_pos
                    break
            boundaries.append((gs_pos, 'Generator', gen_esn))
            if end_pos < len(full):
                boundaries.append((end_pos, 'Gas Turbine', gt_esn))

    boundaries = [(p, t, e) for (p, t, e) in boundaries if not (e and e in inactive)]
    boundaries.sort()

    # ---- PRIORITY 1: content-weighted primary selection ----
    # (a) byte-share from boundaries; (b) signature counts on the full document.
    gt_bytes = 0
    gen_bytes = 0
    for idx, (pos, t, _e) in enumerate(boundaries):
        end_pos = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(full)
        length = max(0, end_pos - pos)
        if t == 'Gas Turbine':
            gt_bytes += length
        elif t in ('Generator', 'Exciter'):
            gen_bytes += length

    body_lower = full.lower()
    gt_sig_hits = _count_sig(body_lower, GT_SIGNATURES)
    gen_sig_hits = _count_sig(body_lower, GEN_SIGNATURES)

    # Decision: pick the equipment that clearly dominates (either by byte-share
    # or by signature evidence). If neither dominates → 'shared'. When only one
    # equipment exists at all, use that unambiguously.
    def _choose_primary():
        if gt_esn and not gen_esn:
            return gt_esn, 'Gas Turbine'
        if gen_esn and not gt_esn:
            return gen_esn, 'Generator'
        if not gt_esn and not gen_esn:
            return (sorted(active)[0] if active else None), None

        # Both ESNs present — decide by content.
        # Byte-share is the strong signal when boundaries were detected.
        if gt_bytes + gen_bytes > 0:
            if gen_bytes >= gt_bytes * 1.2:
                return gen_esn, 'Generator'
            if gt_bytes >= gen_bytes * 1.2:
                return gt_esn, 'Gas Turbine'

        # Signature corroboration for cases with weak / no boundaries.
        if gen_sig_hits >= gt_sig_hits * 2 and gen_sig_hits >= 5:
            return gen_esn, 'Generator'
        if gt_sig_hits >= gen_sig_hits * 2 and gt_sig_hits >= 5:
            return gt_esn, 'Gas Turbine'

        # Genuinely mixed — mark shared, keep gt_esn as the anchor ID.
        return (gt_esn or gen_esn), 'shared'

    primary, primary_type = _choose_primary()

    # ---- Region tagging (unchanged from v1, uses updated primary) ----
    def _region_meta(esn, t):
        rm = {}
        if 'primary_esn' in field_names and esn:
            rm['primary_esn'] = esn
        if 'primary_equip_type' in field_names and t:
            rm['primary_equip_type'] = t
        tc = tech_for(t)
        if 'primary_technology_code' in field_names and tc:
            rm['primary_technology_code'] = tc
        return rm

    regions = []
    distinct_types = set(t for _p, t, _e in boundaries)
    if len(distinct_types) >= 2:
        for idx in range(len(boundaries)):
            pos, t, e = boundaries[idx]
            end_pos = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(full)
            rm = _region_meta(e, t)
            if rm:
                regions.append({'start': pos, 'end': end_pos, 'metadata': rm})
    else:
        page_assign = {}
        for i, ptext in enumerate(pages):
            low = ptext.lower()
            is_gen = any(f in ptext for f in GEN_FORMS) or (sum(1 for s in GEN_SIGNATURES if s in low) >= 2)
            is_gt = any(f in ptext for f in GT_FORMS) or (sum(1 for s in GT_SIGNATURES if s in low) >= 2)
            if is_gen and not is_gt and gen_esn:
                page_assign[i] = ('Generator', gen_esn)
            elif is_gt and not is_gen and gt_esn:
                page_assign[i] = ('Gas Turbine', gt_esn)
            elif is_gen and is_gt:
                # both signals — prefer the primary_type of the doc
                if primary_type == 'Generator' and gen_esn:
                    page_assign[i] = ('Generator', gen_esn)
                elif primary_type == 'Gas Turbine' and gt_esn:
                    page_assign[i] = ('Gas Turbine', gt_esn)
            else:
                # FIX 1: Use doc-level primary instead of first-sorted ESN
                found_esn = None
                for e in sorted(active):
                    if e in ptext:
                        found_esn = e
                        break
                if found_esn:
                    if primary_type and primary_type != 'shared':
                        anchor = gen_esn if primary_type == 'Generator' else gt_esn
                        page_assign[i] = (primary_type, anchor or found_esn)
                    else:
                        page_assign[i] = (esn_type.get(found_esn, 'Unknown'), found_esn)
        cur = None
        for i in range(len(pages)):
            a = page_assign.get(i)
            rm = _region_meta(a[1], a[0]) if a else {}
            if not rm or i >= len(offsets):
                if cur:
                    regions.append(cur)
                    cur = None
                continue
            o = offsets[i]
            if cur and cur['metadata'] == rm and cur['end'] == o['start']:
                cur['end'] = o['end']
            else:
                if cur:
                    regions.append(cur)
                cur = {'start': o['start'], 'end': o['end'], 'metadata': rm}
        if cur:
            regions.append(cur)

    # ---- Document-level metadata ----
    doc = {}
    if 'document_name' in field_names:
        doc['document_name'] = ctx.filename
    if 'gt_esn' in field_names and gt_esn:
        doc['gt_esn'] = gt_esn
    if 'gen_esn' in field_names and gen_esn:
        doc['gen_esn'] = gen_esn
    if 'inactive_esns' in field_names and inactive:
        doc['inactive_esns'] = ", ".join(sorted(inactive))
    if 'primary_esn' in field_names and primary:
        doc['primary_esn'] = primary
    if 'primary_equip_type' in field_names and primary_type:
        doc['primary_equip_type'] = primary_type
    if 'primary_technology_code' in field_names and (gt_tech or gen_tech):
        doc['primary_technology_code'] = gt_tech or gen_tech

    def find_date(labels):
        for pat in labels:
            m = re.search(pat, title, re.I)
            if m:
                v = _clean_date(m.group(1))
                if v:
                    return v
        return None

    if 'outage_start_date' in field_names:
        v = find_date(START_LABELS)
        if v:
            doc['outage_start_date'] = v
    if 'outage_end_date' in field_names:
        v = find_date(END_LABELS)
        if v:
            doc['outage_end_date'] = v
    if 'report_issued_date' in field_names:
        v = find_date(ISSUED_LABELS)
        if v:
            doc['report_issued_date'] = v

    # ---- Hints ----
    lines = []
    if active:
        lines.append("Active equipment (work performed): " +
                     ", ".join(e + " (" + esn_type.get(e, 'Unknown') + ")" for e in sorted(active)))
    if inactive:
        lines.append("Inactive equipment (listed on title page but NOT applicable this outage): " +
                     ", ".join(sorted(inactive)) + ". Do NOT attribute any content to these ESNs.")
    lines.append(
        "Primary equipment inference: primary_equip_type=" + str(primary_type)
        + f" (gt_bytes={gt_bytes}, gen_bytes={gen_bytes}, "
        + f"gt_sig_hits={gt_sig_hits}, gen_sig_hits={gen_sig_hits})."
    )
    lines.append("If any of outage_start_date, outage_end_date, report_issued_date, event_type "
                 "are not already provided, extract them from the title page.")
    hints = "\n".join(lines)

    return {"metadata": doc, "hints": hints, "regions": regions}


# FIX 3: Content-signal chunk override.
# Call this AFTER chunks have been assigned region-based metadata.
# Flips a chunk's equipment label when its own text overwhelmingly
# contradicts the region tag (e.g. 5+ Generator signatures, 0 GT).
# This catches boundary chunks that landed on the wrong side.
#
# Usage (in the application layer, after region assignment):
#   for chunk in chunks:
#       override_chunk_label(chunk["content"], chunk["metadata"])

def override_chunk_label(content, metadata, min_hits=5):
    """Override primary_equip_type on a chunk when content strongly contradicts label.

    Args:
        content: the chunk text
        metadata: the chunk's metadata dict (modified in place)
        min_hits: minimum signature hits to trigger override (default 5)

    Returns:
        True if label was flipped, False otherwise.
    """
    assigned = metadata.get('primary_equip_type')
    if not assigned or assigned not in ('Gas Turbine', 'Generator'):
        return False

    content_lower = content.lower()
    gen_hits = sum(1 for s in GEN_SIGNATURES if s in content_lower)
    gt_hits = sum(1 for s in GT_SIGNATURES if s in content_lower)

    if assigned == 'Gas Turbine' and gen_hits >= min_hits and gt_hits == 0:
        metadata['primary_equip_type'] = 'Generator'
        return True
    elif assigned == 'Generator' and gt_hits >= min_hits and gen_hits == 0:
        metadata['primary_equip_type'] = 'Gas Turbine'
        return True

    return False
