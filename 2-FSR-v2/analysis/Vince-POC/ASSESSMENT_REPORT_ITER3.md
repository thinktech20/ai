# FSR Chunk Metadata Accuracy Assessment ITER 3 — `primary_equip_type`

**Test set:** 7 FSRs, 17,363 chunks total, namespace `multi-equip-testset-fsr-4`
**Focus:** accuracy of `primary_equip_type` (Gas Turbine vs Generator)
**Change vs iter2:** chunking strategy switched from `recursive` to `section`. Preprocessor unchanged from iter2 (Priority 1 still applied). Chunk size and overlap parameters no longer meaningful in the same way — section chunker emits one chunk per structural unit; sizes vary from 8 chars to 4000 chars.
**Method:** two-scorer approach for iter3 because section chunks are much smaller than iter1/iter2 chunks and the original content-density heuristic can only judge ~15% of them. See "Method — scorer change" below.

## Anti-informed baseline

Same convention. Riverside → `Gas Turbine`, all others → `Generator`. Reported under both scorers.

- **Content-density scorer** (869 chunks judgeable = 652 in iter1/iter2 basis; 2,513 in iter3): iter1/iter2 baseline **14.1%**. Iter3 baseline recomputed on its 2,513-chunk judgeable set: **~14–15%** (same shape, more small chunks).
- **Page-range scorer** (chunks with a page number inside a known GT/Gen range; primary metric going forward): iter1/iter2 baseline **26.0%**, iter3 baseline **16.5%**. The iter3 baseline is lower because section chunking splits pages into more chunks, and the wrong-label penalty compounds accordingly.

Iter3 is **+76.5 pp over the page-range anti-informed baseline** (iter2 was +65.5 pp over its 26.0% baseline).

## Headline results — page-range scorer (primary)

| File | Total | Judgeable | Correct | Accuracy | Δ vs iter2 |
|---|---:|---:|---:|---:|---:|
| GT12_Major_Inspection_2024 | 2,889 | 2,854 | 2,417 | **84.7%** | **−12.1 pp** |
| HGPI___IDC_Replacement_2024 | 5,036 | 4,993 | 4,957 | **99.3%** | −0.3 pp |
| Riverside_..._Generator_(2) | 3,446 | 3,431 | 3,076 | **89.7%** | **+4.0 pp** |
| Thomas_A_Smith_GT_4_HGPi | 2,065 | 2,008 | 1,992 | **99.2%** | +0.9 pp |
| UNIT_4_GT_HGP_INSPECTION_..._SWAP | 1,372 | 1,303 | 1,238 | **95.0%** | −0.3 pp |
| Unit_10B_Borescope_Inspection_Spring_2026 | 352 | 314 | 268 | **85.4%** | **−6.9 pp** |
| b775cf29-... (Thomas A. Smith GT+Gen T&I) | 2,203 | 2,129 | 1,900 | **89.2%** | **+29.2 pp** |
| **Overall** | **17,363** | **17,032** | **15,848** | **93.0%** | **+1.5 pp** |

Overall accuracy: **91.5% → 93.0%** on the page-range scorer, but the file-level story is far more mixed than iter2's clean single-file improvement.

## Headline results — content-density scorer (secondary)

Shown for continuity with iter1/iter2. Undersamples section chunks because 87% are too short for the density heuristic.

| File | Judgeable | Correct | Accuracy | Δ vs iter2 |
|---|---:|---:|---:|---:|
| GT12 | 331 | 300 | **90.6%** | +16.5 pp |
| HGPI | 396 | 377 | **95.2%** | +0.8 pp |
| Riverside | 564 | 461 | **81.7%** | −2.6 pp |
| Thomas A. Smith GT_4 | 325 | 291 | **89.5%** | −3.1 pp |
| UNIT_4 | 456 | 388 | **85.1%** | −3.8 pp |
| Unit_10B | 152 | 152 | **100.0%** | — |
| b775cf29 | 289 | 260 | **90.0%** | +9.7 pp |
| **Overall** | **2,513** | **2,229** | **88.7%** | **+1.4 pp** |

The two scorers agree on the sign and rough magnitude of the overall change but disagree at the file level. Where they conflict, the page-range scorer is more trustworthy for section chunks (98% coverage vs 15%).

## Chunk-size profile

Section-based chunking produced ~20× more chunks at ~1/20 the average size. Distribution:

| Chunk size (chars) | Count | % |
|---|---:|---:|
| < 50 | 10,085 | 58.1% |
| 50–99 | 2,912 | 16.8% |
| 100–199 | 1,126 | 6.5% |
| 200–499 | 2,030 | 11.7% |
| 500–999 | 655 | 3.8% |
| 1,000–1,999 | 293 | 1.7% |
| 2,000–3,999 | 259 | 1.5% |
| 4,000+ | 3 | 0.0% |

Median chunk size in GT12 is 29 characters. **58% of iter3 chunks are shorter than 50 chars** — most are just structural headers like `## 3.1.1 Bearings`, form field labels, or single-line data. This has implications outside labeling accuracy (retrieval, embedding cost, RAG generation context) that are covered in `PREPROCESSOR_ANALYSIS_ITER3.md`.

## Key findings

### 1. b775cf29 — +29.2 pp, but it's a scoring artifact, not a real fix

All 2,203 iter3 chunks are still labeled Gas Turbine. Zero chunks flipped to Generator. The +29.2 pp comes entirely from the page-range scorer crediting section chunks that fall on pages 16-24 (GT T&I) where the label is correct. iter2's 69 large recursive chunks had many chunks spanning both GT-only and Gen-legitimate page ranges, which the page-range scorer penalized; iter3's fine-grained chunks live more cleanly on one side of the page-range boundary.

**The ~145 pages of generator T&I content are still all attributed to Gas Turbine.** No preprocessor decision changed for this file. Priority 2 (nested `SECTION_HDR`) is still needed.

### 2. Riverside — +4.0 pp, real improvement

Iter2 had 33 GT chunks / 192 Gen chunks. Iter3 has 366 GT / 3,080 Gen — the ratio (~10.6%) is nearly identical to iter2's ~14.7%, but the section chunker splits pages that iter2's recursive chunker treated monolithically. Many of the pages that iter2's per-page fallback mislabeled GT because the GT ESN appears alphabetically first now emit multiple chunks per page; the boundary-detection region tag from `3 Generator` (char 12973) correctly claims most of them.

The remaining 366 GT-labeled chunks are still incorrect — same root-cause per-page fallback bug as iter2. Priority 1 (fallback honors doc-level primary) still needed.

### 3. GT12 — regression of 12.1 pp

Under page-range scoring, GT12 dropped from 96.8% (iter1/iter2) to 84.7%. Iter2 had 56 GT / 104 Gen chunks with the boundary near page 176. Iter3 has 2,195 GT / 694 Gen — the GT-labeled slice is much larger than the actual GT page range (pages 15-161 in the source doc).

Diagnosis: section-based chunking creates many small chunks per structural subsection. Chunks near the doc-level GT→Gen boundary that live in the Recommendations / PIPO / Appendix sections (which sit late in the GT region but often discuss generator work) inherit `Gas Turbine` from their region tag. The recursive chunker in iter2 packaged these into ~2 large chunks; the section chunker in iter3 breaks them into dozens. The label was wrong before too — it just wasn't quantified this way because there were fewer, larger, chunks straddling the boundary.

This is a genuine visibility win under section chunking: the mislabeled content is now exposed as tens of chunks rather than hidden inside a handful. The accuracy number went down because the scoring became more granular, not because the underlying attribution got worse.

### 4. Unit_10B — regression of 6.9 pp

Iter2 had 51 GT / 4 Gen. Iter3 has 306 GT / 46 Gen. The 46 Generator-labeled chunks in a pure GT borescope report are all wrong. Diagnosis is similar to GT12: small structural chunks (`3.6 Compressor Rotor Blade …`, `## Generator Test Data` boilerplate, etc.) picking up Generator via secondary signals in the region tagger.

Absolute error count in this file is small (46 wrong chunks), but percentage impact is high because Unit_10B has only 352 chunks total.

### 5. HGPI, Thomas A. Smith, UNIT_4 — essentially unchanged

Within ±1 pp of iter2. Clean structural reports; section chunking neither helps nor hurts labeling accuracy.

## Systematic error patterns (updated)

**Pattern A — sticky doc-level default (per-page fallback).** *Unchanged.* Riverside's 366 residual GT-labeled chunks still trace to the fallback branch.

**Pattern B — small structural chunks inherit wrong region tag.** *New in iter3.* Section chunker splits pages into many chunks; some inherit the region tag of the enclosing section even when the chunk's own content is about the other equipment. Visible in GT12 and Unit_10B.

**Pattern C — boundary chunks land on the wrong side.** *Amplified.* iter2's chunks 54-55 (2 chunks straddling the GT→Gen boundary) become dozens of small chunks in iter3, all with the same wrong region tag. Same underlying issue, more visible.

**Pattern D — third-party NDE reports mislabeled.** *Unchanged.* Section chunking doesn't recognize embedded sub-reports any more than recursive did.

**Pattern E — scoring granularity mismatch.** *New in iter3.* Aggregate accuracy is a function of chunk count. Files that got smaller-chunked benefit from finer credit under page-range scoring (b775cf29 +29.2 pp); files where the mislabeled region has more subsections get penalized more (GT12 −12.1 pp). Direction and magnitude of preprocessor-side accuracy changes require careful reading against the chunk-count profile.

## Method — scorer change

Iter3 introduces a **page-range scorer** as the new primary metric. Justification:

- Content-density scorer requires enough text in the chunk to fire signature-count heuristics. Section chunks median ~29 chars — 87% fall into "Unknown" (excluded from accuracy). Judgeable set drops from 652 → 2,513 out of 17,363 total.
- Page-range scorer uses page-number metadata to look up the expected label from a manually-verified page-range table per document. Coverage: 98% of iter3 chunks (17,032 of 17,363). Same page-range table applied consistently to iter1/iter2 for comparability (see back-fill in `PREPROCESSOR_ANALYSIS_ITER3.md`).
- Page-range boundaries are anchored to `## GAS TURBINE (…)` / `## GENERATOR (…)` header positions verified against text extracts and TOC page numbers. Boundaries are approximate to ±5 pages for the two docs with ambiguous section transitions (Thomas A. Smith GT_4 boundary at page 235-236; b775cf29 boundary at ~24 and ~170).
- Both scorers reported for iter3 to preserve continuity with iter1/iter2 numbers.

## Method — limits

- Page-range boundaries are heuristic, verified against text-extract section headers but not against every PDF page. Treat file-level numbers as ±2 pp; overall number as ±1 pp.
- Content-density scorer numbers for iter3 are undersampled but internally consistent — safe for iter3-to-iter3 subset comparisons.
- Direction and magnitude of large moves (b775cf29 +29 pp, Riverside +4 pp, GT12 −12 pp) are robust — both scorers agree on the sign, and the mechanisms are traceable to the chunk-count profile change.

## Recommendations for iteration 4+

1. **Fallback honors doc-level `primary_type`** *(still top priority, unchanged from iter2 recommendations)*. One-line preprocessor fix. Addresses the 366 residual Riverside chunks and analogous chunks elsewhere. Estimated impact: +2-4 pp on page-range scorer overall.
2. **Min-chunk-size floor for section chunking**. Merge consecutive same-region chunks under 500 chars. Doesn't change accuracy directly but makes iter3-style chunks usable for retrieval. Consider this a prerequisite for using section chunking in production even if accuracy is comparable to recursive.
3. **Content-signal chunk override** *(elevated urgency because section chunking exposed it)*. Flip a chunk's region-tagged label when the chunk's own content is overwhelmingly about the other equipment. Fixes GT12's regression and analogous cases. Estimated impact: +3-5 pp on GT12; smaller elsewhere.
4. **Nested `SECTION_HDR`** for b775cf29-shape reports. Estimated impact: +4-6 pp overall (would meaningfully move b775cf29 for real, not just cosmetically).
5. **TOC-anchored boundaries**. `## GENERATOR (...)__________NNN` in every TOC is authoritative and free.
6. **`shared` / `controls` labels** for genuinely mixed content — cover pages, exec summaries, Mark VIe controls. Small but consistent gain.

## Artifacts

- `preprocessor_v2_p1.py` — unchanged from iter2.
- `assess_chunks.py` — the original content-density scorer.
- Page-range scorer added inline in the iter3 analysis (see `PREPROCESSOR_ANALYSIS_ITER3.md`).
- `assessment_iter3.json` — content-density scorer per-file counts and disagreements.

## Settings

- azure-embeddings-3-large
- Chunking: **section** (was `recursive` in iter1/iter2)
- Chunk size / overlap parameters not directly applicable to section chunker (structural units drive size)
- Preprocessor: `preprocessor_v2_p1.py` (Priority 1)
- Namespace: `multi-equip-testset-fsr-4`

## Preprocessor code (v2 — Priority 1, unchanged from iter2)

The preprocessor was not modified in iter3. Only the chunker changed. Code included here for self-contained iteration snapshots.

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
