# FSR Chunk Metadata Accuracy Assessment ITER 2 — `primary_equip_type`

**Test set:** 7 FSRs, 869 chunks total, namespace `multi-equip-testset-fsr-3`
**Focus:** accuracy of `primary_equip_type` (Gas Turbine vs Generator)
**Change vs iter1:** preprocessor updated to Priority 1 (content-weighted `primary` selection with 1.2× byte-share margin, `GT_SIGNATURES` list, `shared` fallback). Everything else — chunking strategy, chunk size, overlap, embedding model — held constant. See `preprocessor_v2_p1.py`.
**Method:** heuristic ground truth derived from text extracts (section-header + keyword-density signals), boilerplate excluded from accuracy, disagreements spot-checked against text extracts and PDFs. Same scorer as iter1.

Auxiliary schema values (`shared`, `controls`, `exciter`, `steam turbine`) treated as valid — chunks the metadata calls "Gas Turbine" or "Generator" that a stricter labeler could call one of those are **not** counted as errors here, per user direction (main concern is GT-vs-Gen).

## Anti-informed baseline

Reference floor used across every iteration report. Each report forced to a single wrong-for-that-report label — Riverside → `Gas Turbine`, all others → `Generator` — and scored against the same heuristic ground truth (652 judgeable chunks):

| File | Judgeable | Correct | Anti-informed accuracy |
|---|---:|---:|---:|
| GT12 | 81 | 22 | 27.2% |
| HGPI | 142 | 18 | 12.7% |
| Riverside | 198 | 10 | 5.1% |
| Thomas A. Smith GT_4 | 54 | 9 | 16.7% |
| UNIT_4 | 63 | 19 | 30.2% |
| Unit_10B | 53 | 4 | 7.5% |
| b775cf29 | 61 | 10 | 16.4% |
| **Overall** | **652** | **92** | **14.1%** |

Iter2 is **+73.2 pp over baseline** (iter1 was +68.9 pp).

## Headline results

| File | Total | Boiler-plate | Judgeable | Correct | Accuracy | Δ vs iter1 |
|---|---:|---:|---:|---:|---:|---:|
| GT12_Major_Inspection_2024 | 160 | 3 | 81 | 60 | **74.1%** | — |
| HGPI___IDC_Replacement_2024 | 227 | 5 | 142 | 134 | **94.4%** | — |
| Riverside_..._Generator_(2) | 225 | 3 | 198 | 167 | **84.3%** | **+14.1 pp** |
| Thomas_A_Smith_GT_4_HGPi | 64 | 5 | 54 | 50 | **92.6%** | — |
| UNIT_4_GT_HGP_INSPECTION_..._SWAP | 69 | 4 | 63 | 56 | **88.9%** | — |
| Unit_10B_Borescope_Inspection_Spring_2026 | 55 | 2 | 53 | 53 | **100.0%** | — |
| b775cf29-... (Thomas A. Smith GT+Gen T&I) | 69 | 3 | 61 | 49 | **80.3%** | — |
| **Overall** | **869** | **25** | **652** | **569** | **87.3%** | **+4.3 pp** |

Overall accuracy: **83.0% → 87.3%** (+4.3 pp). All of the gain came from Riverside (70.2% → 84.3%). Six of seven files are byte-identical to iter1 apart from the `namespace` change (`multi-equip-testset-fsr-2` → `-3`), which is the correct footprint of a change scoped to one preprocessor decision.

## Key findings

### 1. Riverside — content-weighted primary flipped it from Gas Turbine to Generator

Iter1 labeled 86 chunks Gas Turbine and 139 Generator. Iter2 labels **33 GT and 192 Generator**. 53 chunks flipped GT → Gen; zero flipped the other way. The document-level `primary_equip_type` is now `Generator` (correct — the report is a full generator rewind/restack). The `GT_SIGNATURES` list did what it was supposed to: byte-share for Riverside comes out overwhelmingly generator, so Priority 1 selects `primary=338X447 (Generator)` instead of the alphabetically-first GT ESN.

**Residual: 33 chunks still labeled Gas Turbine (all wrong).** These are the ones the per-page fallback branch of the preprocessor is still mishandling — the fallback assigns pages by "first ESN found in `sorted(active)`" which alphabetically prefers `298250` (GT) over `338X447` (Gen). Root cause is in the fallback code path (`preprocessor_v2_p1.py` lines ~268-302). Priority 1 fixed the doc-level primary but did not thread that decision into the fallback branch.

### 2. GT12 — unchanged (74.1%)

Same 21 disagreements as iter1: 17 boundary/recommendation chunks labeled Gas Turbine that should be Generator (chunks 32-33 controls, chunks 54-55 recommendations), and 4 NDE-attachment chunks labeled Generator that should be Gas Turbine (chunks 98-112, Liquid Penetrant Exam of GT hot-gas-path parts). Priority 1 doesn't touch region boundaries or per-chunk overrides, so this file was not expected to move.

### 3. b775cf29 — unchanged (80.3%)

All 69 chunks still labeled Gas Turbine. Because Priority 1 uses `boundaries` byte-share as the primary signal and b775cf29 has zero `HEADER` matches for Generator (its generator content sits under nested `3.1.1 Generator Stator/Field Tests` headers), byte-share for Gen came out at 0 and Priority 1 correctly kept `primary=Gas Turbine`. But the report is genuinely mixed; the ~10 chunks that should be Generator remain misattributed. Priority 2 (nested `SECTION_HDR`) still needed to break this open.

### 4. HGPI, Thomas A. Smith, UNIT_4, Unit_10B — unchanged

Same accuracy as iter1 (94.4%, 92.6%, 88.9%, 100.0%). These reports have clean GT+Generator dual-section layouts where iter1's structural attribution already worked. Priority 1's byte-share confirms the existing choice; nothing flips.

## Systematic error patterns (updated)

**Pattern A (was iter1's dominant) — sticky GT label when only GT ESN is in the header.** *Substantially reduced.* Priority 1 removed the doc-level GT-first bias. Riverside no longer defaults to GT primary. The pattern only survives in the per-page fallback branch, which affects the 33 residual Riverside chunks.

**Pattern B — alternating labels driven by page/section number.** *Reduced.* Iter1 Riverside toggled ~34 times; iter2 Riverside toggles far fewer (Generator is now the doc-level default so the fallback flips less often).

**Pattern C — boundary chunks land on the wrong side.** *Unchanged.* GT12 chunks 54-55 still land on Gas Turbine even though their body is generator recommendations. Priority 1 doesn't do content-signal chunk overrides.

**Pattern D — third-party NDE reports mislabeled.** *Unchanged.* GT12 chunks 98-112 still labeled Generator. Same root cause as iter1; needs NDE-detection logic.

## Boilerplate handling

Same 25 chunks flagged as boilerplate as in iter1 (chunking unchanged → chunks unchanged for six of seven files; Riverside chunks are unchanged too, only labels moved). Same recommendation: route boilerplate to `shared` or drop from index rather than assigning arbitrary GT/Gen.

## Method — limits

- Ground truth is the same heuristic used for iter1. Same false-positive noise (~±3-5 pp).
- Judgeable universe unchanged: 652 chunks. Six of seven files scored identically to iter1 (byte-for-byte identical content, only labels changed on Riverside), so any drift in the accuracy figure reflects Riverside's label flips only.
- Iter2 delta is high-confidence: the direction and shape (only Riverside moved, only GT → Gen flips, no back-flips) is unambiguous.

## Recommendations for iteration 3+

1. **Fallback honors doc-level `primary_type`** *(new top priority)*. Inside the per-page fallback branch, when a page has no form/signature signal, prefer the doc-level `primary_type` over `sorted(active)[0]`. Would address the 33 residual Riverside GT chunks. Estimated impact: +2-4 pp overall.
2. **Nested `SECTION_HDR`** to catch b775cf29's `3.1.1 Generator Stator/Field Tests` and analogous nested headers. Estimated impact: +4-6 pp overall.
3. **Content-signal chunk override** for GT12's boundary chunks and NDE attachments. Estimated impact: +2-3 pp overall.
4. **TOC-anchored boundaries** — every FSR has `## GENERATOR (...)__________NNN` in the TOC; the page number is authoritative. Estimated impact: +1-2 pp incremental.
5. **`shared`/`controls` labels** for genuinely mixed sections (site personnel, exec summary, Mark VIe controls) — as in iter1's recommendations. Reduces the ambiguous residual across every file.

## Artifacts

- `preprocessor_v2_p1.py` — the updated preprocessor (Priority 1 applied).
- `assess_chunks.py` — the scorer, unchanged from iter1.
- `assessment_iter2.json` — per-file counts and every disagreement with a 300-char preview.
- `PREPROCESSOR_ANALYSIS_ITER2.md` — the accompanying preprocessor analysis.

## Settings

- azure-embeddings-3-large
- 4000 chunk size
- 200 overlap
- Recursive chunking
- Preprocessor: `preprocessor_v2_p1.py` (Priority 1)
- Namespace: `multi-equip-testset-fsr-3`

## Preprocessor code (v2 — Priority 1)

```python
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
    SECTION_HDR = r'(?im)^\s*#{0,3}\s*\d+\s+(GAS\s+TURBINE|TURBINE|GENERATOR|STEAM\s+TURBINE|EXCITER)\s*$'

    def _canon(name):
        n = name.strip().lower()
        if 'generator' in n:
            return 'Generator'
        if 'exciter' in n:
            return 'Exciter'
        if 'steam' in n:
            return 'Steam Turbine'
        return 'Gas Turbine'

    boundaries = []
    for m in re.finditer(HEADER, full, re.I):
        boundaries.append((m.start(), m.group(1).title(), _norm(m.group(2))))
    for m in re.finditer(SECTION_HDR, full):
        t = _canon(m.group(1))
        e = gen_esn if t in ('Generator', 'Exciter') else (gt_esn if t == 'Gas Turbine' else None)
        boundaries.append((m.start(), t, e))
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
                for e in sorted(active):
                    if e in ptext:
                        page_assign[i] = (esn_type.get(e, 'Unknown'), e)
                        break
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
```
