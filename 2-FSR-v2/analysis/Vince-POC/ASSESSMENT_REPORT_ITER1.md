# FSR Chunk Metadata Accuracy Assessment — `primary_equip_type`

**Test set:** 7 FSRs, 869 chunks total, namespace `multi-equip-testset-fsr-2`
**Focus:** accuracy of `primary_equip_type` (Gas Turbine vs Generator)
**Method:** heuristic ground truth derived from text extracts (section-header + keyword-density signals), boilerplate excluded from accuracy, disagreements spot-checked against text extracts and PDFs.

Auxiliary values in the schema (`shared`, `controls`, `exciter`, `steam turbine`) are treated as valid — chunks the metadata calls "Gas Turbine" or "Generator" that a stricter labeler could call one of those are **not** counted as errors here, per user direction (main concern is GT-vs-Gen).

## Headline results

| File | Total | Boiler-plate | Judgeable | Correct | Accuracy | Direction of errors |
|---|---:|---:|---:|---:|---:|---|
| GT12_Major_Inspection_2024 | 160 | 3 | 81 | 60 | **74.1%** | Boundary chunks mislabeled + generator recs mislabeled GT |
| HGPI___IDC_Replacement_2024 | 227 | 5 | 142 | 134 | **94.4%** | Small — inferrer likely over-flags a few |
| Riverside_..._Generator_(2) | 225 | 3 | 198 | 139 | **70.2%** | Generator-only report; 86 chunks mislabeled GT |
| Thomas_A_Smith_GT_4_HGPi | 64 | 5 | 54 | 50 | **92.6%** | Mostly correct |
| UNIT_4_GT_HGP_INSPECTION_..._SWAP | 69 | 4 | 63 | 56 | **88.9%** | Mostly correct |
| Unit_10B_Borescope_Inspection_Spring_2026 | 55 | 2 | 53 | 53 | **100.0%** | Clean |
| b775cf29-... (Thomas A. Smith GT+Gen T&I) | 69 | 3 | 61 | 49 | **80.3%** | All 69 labeled GT; ~10 real generator chunks miss |
| **Overall** | **869** | **25** | **652** | **541** | **83.0%** | |

Overall accuracy is **~83%** on judgeable chunks. Two documents drag the average down: Riverside (70%) and GT12 (74%). Excluding those, the remaining five files run ~90-100%.

## Key findings

### 1. Riverside — generator-only report labeled ~38% Gas Turbine
The report is titled "Riverside Generating Station Unit 1 Generator — Partial Restack & Full Rewind" and contains only 9 unique "gas turbine" mentions (all in ESN headers or an appendix TIL). Yet **86 of 225 chunks** are labeled `Gas Turbine`, alternating with `Generator` roughly every 1–15 chunks (see `chunks 0→7, 7→10, 10→12, 12→16, ...`). None of the sampled GT-labeled chunks contain gas-turbine content — they are all generator stator/rotor/NDE/appendix material. This is the largest single source of error in the test set (56 misses).

### 2. b775cf29 — generator T&I chunks all labeled Gas Turbine
Report is a combined **Gas Turbine T&I + 7FH2 Hydrogen-Cooled Generator T&I** (Thomas A. Smith site). The TOC only lists `## GAS TURBINE (297651 | SY0070884)` — there is no `## GENERATOR (...)` top-level header. All 69 chunks are labeled `Gas Turbine`. But sections 3.1.1 "Generator Stator/Field Tests with Borescope Inspection", the RTD forms, HV bushings, End Winding inspections, and TIL 2441 material (pages 25–160-ish) are generator content. At least ~10 chunks are unambiguously generator; my heuristic flagged them, and page-range inspection in the PDF confirms.

### 3. GT12 — recommendations and boundary chunks are mislabeled
The GT12 report has a clean `## GAS TURBINE (...)` / `## GENERATOR (...)` split, but:
- **Chunk 55 (page 173)** is labeled `Gas Turbine`, yet its content is "Stator End Winding Assembly … The end winding is recommended for cleaning…" — generator recommendation.
- **Chunk 54 (page 171)** is labeled `Gas Turbine` and contains generator part numbers (SNH3730355-x parts).
- The switch to `Generator` happens at chunk 56 — the metadata boundary is late by ~2–3 chunks.

Conversely, **chunks 98–112 (pages 308–322)** are labeled `Generator` but contain a third-party Liquid Penetrant Exam report on gas-turbine hot-gas-path parts. Verification against the pdf: these NDE reports are the GT PIPO section, not generator. So the metadata boundary is *late* in one direction and *early* in another.

### 4. Thomas_A_Smith_GT_4_HGPi and UNIT_4 — mostly correct but suspiciously identical labeling
Both reports labeled ~74–75% GT / 25–29% Generator, roughly matching content. Only 2–14 disagreements per file, most at boundaries or in mixed-content chunks.

### 5. HGPI — highest accuracy
94% agreement. Small residual disagreements (~8 chunks) trace to Mark VIe control system content (would fit `controls` in the expanded schema) or generator air-leakage test blocks where my inferrer confused a project ID (`GT 31`) with GT content. Metadata here is likely correct.

### 6. Unit_10B_Borescope_Inspection — perfect
Pure GT borescope inspection; only 4 chunks labeled Generator (chapter about turbine section). All labels consistent with content.

## Systematic error patterns

**Pattern A — sticky GT label when only GT ESN is in the header.** When the FSR title/header lists both a GT ESN and a Generator ESN but the TOC only has `## GAS TURBINE (...)` (b775cf29), or when the "primary" ESN is the GT (Riverside), the labeler defaults to `Gas Turbine` even for entire generator sub-sections. This is the dominant error mode. Suggests the labeler is looking at `primary_esn`/`gt_esn` in metadata rather than content signals.

**Pattern B — alternating labels driven by page/section number, not content.** Riverside's label toggles ~34 times across 225 chunks (`0:GT → 7:Gen → 10:GT → 12:Gen → …`). No FSR has that many real section transitions between GT and Generator content. Suggests the labeler is keying off something like a section-number regex that doesn't distinguish GT-appendix vs generator body.

**Pattern C — boundary chunks land on the wrong side.** In GT12, chunk 54–55 sit exactly at the GAS TURBINE → GENERATOR handoff but are labeled `Gas Turbine`. The chunk spans the boundary, and the labeler picks the *first* section header seen instead of the dominant one.

**Pattern D — third-party NDE reports get mislabeled.** GT12 chunks 98–112 (Liquid Penetrant Exam of GT parts, produced by a Myanmar sub-contractor) are labeled `Generator` because they sit inside a report page range that came right after generator work. NDE and outage-services boilerplate is a distinct sub-type that trips up the labeler.

## Boilerplate handling

25 chunks (2.9%) were flagged as boilerplate (TOC + exec summary + cover pages) and excluded from accuracy. The metadata assigns them whatever value the current sliding window has (mostly `Gas Turbine`), which is not obviously wrong for a title page but has no meaningful ground truth. Recommend routing these to `shared` (or dropping them from the vector index) rather than assigning them arbitrarily.

## Method — limits

- **Ground truth is heuristic**, not human-annotated. Signals used: (a) last `## GAS TURBINE (` or `## GENERATOR (` header seen in the chunk; (b) keyword density (generator-specific electrical terms vs GT compressor/combustion terms) after stripping the repeating GE Vernova footer. Where neither signal fires, the chunk is marked `Unknown` and excluded from accuracy.
- **False positives:** the keyword-density fallback fires on generic terms. My spot check found:
  - GT12 chunks 32–33 (Mark controller / IGV LVDT calibration) flagged as `Generator` — actually GT controls. This is a labeler bug (should be `Controls`), not a `Generator` miss.
  - HGPI chunks 187–201 flagged as `Gas Turbine` when they are correctly generator (stator air leakage, buffer tank inspection). The false positive is on my end; the metadata is right.
- **Judgeable universe = 652 of 869 chunks (75%).** The other 217 chunks landed in `Unknown` (no signal), `Shared` (tie), or boilerplate. Accuracy on the judgeable set is 83%. The unmeasured 25% is not necessarily worse; it's just where my heuristic can't decide.

Bottom line on the method: because my heuristic has visible false-positive noise, treat the 83% number as a *lower bound with ±3–5 pp of noise* rather than an exact figure. The direction and shape of the errors — Riverside miscoded, b775cf29 miscoded, GT12 boundary drift — are robust across both header-signal and keyword-density evidence.

## Recommendations for iteration 2

1. **Reverse the default assumption when title contains "Generator" or work-scope is "Rewind / Restack / MAGIC / Field Removal".** Riverside should be predominantly `Generator` — currently 38% of its chunks are wrong-side.
2. **Split reports at the first `## GENERATOR (…ESN…)` header**, not by page range or ESN ownership. This alone would fix the GT12 chunk 54–55 drift and most of Riverside.
3. **Detect embedded sub-reports (NDE / third-party inspections) and label them by the equipment they test**, not by their position in the enclosing FSR. GT12's Liquid Penetrant chunks 98–112 illustrate the failure mode.
4. **Add `shared`/`controls` labels for the mixed sections you already treat as valid.** Currently the labeler collapses everything to GT/Gen; ~15–30 chunks per report would legitimately be `controls` (Mark V/VI setup, LVDT calibration, functional tests) or `shared` (site personnel, exec summary, TOC).
5. **For combined GT+Generator T&I reports (b775cf29-style) without a top-level `## GENERATOR (…)` header**, detect the generator section via sub-headers (`Generator Stator/Field Tests`, `## Stator …`, `Endwinding …`) and switch primary_equip_type accordingly.
6. **Verify boundary logic.** When a chunk crosses a GT→Gen section header, the label should follow the *dominant* half of the chunk, not the first-seen header.

## Artifacts

- `assess_chunks.py` — the scorer (regex signals, boilerplate detection, per-file metrics).
- `assessment_data.json` — per-file counts and every disagreement with a 300-char preview so you can inspect individually.

## Settings
azure-embeddings-3-large
4000 chunk size
200 overlap
Recursive

# FSR Metadata Preprocessor

A per-collection, sandboxed Python **preprocessor** that runs once per document
**before** the AI metadata extraction during ingestion. For GE Field Service
Reports (FSRs) it deterministically attributes equipment to the right chunks so
that multi-ESN documents don't cross-contaminate retrieval.

## Where it runs

```
extract text + pages  →  preprocess(ctx)  →  AI metadata extraction (guided by hints)
                          {metadata, hints, regions}
   →  merge (region tag > preprocessor doc value > AI value > upload tags)
   →  chunk (each chunk inherits the region it falls in)  →  embed → store
```

## How to install it

1. Open **Collections → Metadata Schema** and select the collection.
2. Define the fields (this preprocessor populates: `document_name`, `gt_esn`,
   `gen_esn`, `primary_esn`, `primary_equip_type`, `primary_technology_code`,
   `inactive_esns`, `outage_start_date`, `outage_end_date`, `report_issued_date`;
   it leaves `event_type` and any missed dates to the AI via hints).
3. Expand **Preprocessor (advanced)**, paste the code below, tick **Enable**,
   and click **Save Schema**. Use **Test** (paste text or a file) to verify.
4. Upload FSRs with **"Extract custom metadata"** checked.

### Processing mode

The preprocessor runs in **both** ingest paths:
- **Short / Standard** (whole-doc): regions map to chunks by character offset.
- **Large / Scanned** (page-by-page): regions map to chunks by **page number**,
  so big multi-ESN reports (400+ pages) are attributed per section without
  loading the whole PDF into memory. Selecting the **Large / Scanned** preset
  also defaults the embedding model to **`azure-embeddings-3-large`**.

## Contract

`preprocess(ctx)` receives `ctx.filename`, `ctx.full_text`, `ctx.pages` (list),
`ctx.page_offsets` (`[{page,start,end}]` char ranges), and `ctx.fields` (the
schema). It returns:

```python
{
  "metadata": {field: value, ...},   # document-level, applied to every chunk
  "hints": "text",                    # injected into the AI extraction prompt
  "regions": [{"start", "end", "metadata"}]  # per-section, tags chunks by char offset
}
```

Sandbox: no `import`/`eval`/`exec`/file access/dunder attributes. The modules
`re`, `json`, `datetime` are pre-injected.

## Detection signals (general — no hardcoded ESNs)

1. **Inactive ESNs** — "this equipment is not applicable / no work performed"
   marks title-page ESNs with no content → stored in `inactive_esns` and kept
   off every chunk.
2. **ESN + type** — section headers `GENERATOR (337X766 | SY…)`, labeled fields
   (`Gas Turbine ESN:`, `Generator ESN:`, `Equipment Serial #:`), plus a deep
   scan for generator ESNs buried on data sheets.
3. **Equipment section boundaries (primary signal)** — top-level GE section
   headers split the document into char regions and each chunk inherits its
   region's `primary_esn` / `primary_equip_type`. Two header forms are matched:
   - parenthetical `GENERATOR (337X765 | SY…)` (multi-ESN reports), and
   - numbered TOC headers `2 Turbine` / `3 Generator` (dual-ESN reports).
   This is what attributes generator *mechanical* content (bearings, hydrogen
   seals, field/rotor, end windings, retaining rings) that carries no form
   numbers of its own — everything between the `Generator` header and the next
   equipment header is tagged Generator.
4. **GE form numbers + datasheet keywords (fallback)** — for single-equipment or
   buried-generator reports with no clear GT/Generator split, `D316xxxx`
   ⇒ Generator and `GTxxxx` ⇒ Gas Turbine drive per-page attribution.
5. **Dates + frame codes** — regex-extracts Job Start / Approved dates and
   frame codes (`7FA.03`, `7FH2`, …); anything missed is deferred to the AI.

## The code

```python
# GE FSR metadata preprocessor — multi-ESN equipment attribution.
# General across the FSR corpus (no hardcoded ESNs). Uses re/json (injected).

NOT_APPLICABLE = [
    r'(?i)this equipment is not applicable',
    r'(?i)not applicable for this outage',
    r'(?i)no work performed on this (?:unit|equipment)',
    r'(?i)not included in (?:this )?scope',
]

# Section headers like:  GENERATOR (337X766 | SY0072576)
HEADER = r'(GAS TURBINE|GENERATOR|STEAM TURBINE|EXCITER)\s*\(\s*(\d{3}[A-Z]?\d{3})\s*\|\s*(SY\d{7})\)'

# Labeled ESN fields (title page or buried data sheets)
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

# GE standard form numbers (definitive equipment classifiers)
GEN_FORMS = ['D3162041','D3162043','D3162044','D316218','D316303','D316402',
             'D316403','D316501','D316512','D300001','D306301','D306302',
             'D309102','D309301','D309302','D315102']
GT_FORMS = ['GT3225','GT9245','GT9386','GT9390','GT4050','GT1040','GT71F040','GT71F045']

GEN_SIGNATURES = ['armature winding resistance','armature insulation','hipotential testing',
                  'stator voltage','polarization index','power mva','max h2 pressure',
                  'collector end','dc leakage','stator insulation resistance']

# Date labels (colon required to avoid false hits like "Approved By")
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


def preprocess(ctx):
    pages = ctx.pages or []
    offsets = ctx.page_offsets or []
    full = ctx.full_text or ""
    field_names = set(f.get('name') for f in (ctx.fields or []))
    title = "\n".join(pages[:6]) if pages else full[:8000]

    # ---- collect ESNs + equipment types ----
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

    # deep scan whole document for buried generator ESNs (e.g. on data sheets)
    for ptext in pages:
        for pat in GEN_LABELS + [r'Equipment\s*Serial\s*#?\s*[:#]\s*(\d{3}[A-Z]\d{3})']:
            for m in re.finditer(pat, ptext, re.I):
                set_type(m.group(1), 'Generator')

    all_esns = set(esn_type.keys())

    # ---- Signal 1: inactive ESNs ("not applicable") ----
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
    primary = gt_esn or gen_esn or (sorted(active)[0] if active else None)
    primary_type = esn_type.get(primary, 'Gas Turbine') if primary else None

    # ---- technology / frame codes ----
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

    # ---- equipment sections (char offsets in full_text) ----
    # PRIMARY signal: top-level GE section headers. Two forms:
    #   * parenthetical  "GENERATOR (337X765 | SY0072576)"  (multi-ESN docs)
    #   * numbered TOC    "3 Generator" / "2 Turbine"        (dual-ESN docs)
    # Everything between one equipment header and the next inherits that
    # equipment. This attributes mechanical generator content (bearings, seals,
    # field, end windings) that has no form numbers of its own.
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

    boundaries = []
    for m in re.finditer(HEADER, full, re.I):
        boundaries.append((m.start(), m.group(1).title(), _norm(m.group(2))))
    for m in re.finditer(SECTION_HDR, full):
        t = _canon(m.group(1))
        e = gen_esn if t in ('Generator', 'Exciter') else (gt_esn if t == 'Gas Turbine' else None)
        boundaries.append((m.start(), t, e))
    boundaries = [(p, t, e) for (p, t, e) in boundaries if not (e and e in inactive)]
    boundaries.sort()

    regions = []
    distinct_types = set(t for _p, t, _e in boundaries)
    if len(distinct_types) >= 2:
        # Structural attribution (reliable for GT+Generator dual-ESN reports).
        for idx in range(len(boundaries)):
            pos, t, e = boundaries[idx]
            end_pos = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else len(full)
            rm = _region_meta(e, t)
            if rm:
                regions.append({'start': pos, 'end': end_pos, 'metadata': rm})
    else:
        # Fallback: per-page form / datasheet / direct-ESN detection for
        # single-equipment or buried-generator reports (no clear GT/Gen split).
        page_assign = {}
        for i, ptext in enumerate(pages):
            low = ptext.lower()
            is_gen = any(f in ptext for f in GEN_FORMS) or (sum(1 for s in GEN_SIGNATURES if s in low) >= 2)
            is_gt = any(f in ptext for f in GT_FORMS)
            if is_gen and gen_esn:
                page_assign[i] = ('Generator', gen_esn)
            elif is_gt and gt_esn:
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

    # ---- document-level metadata ----
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

    # ---- hints for the LLM (fills gaps: dates it missed + event_type; scoping) ----
    lines = []
    if active:
        lines.append("Active equipment (work performed): " +
                     ", ".join(e + " (" + esn_type.get(e, 'Unknown') + ")" for e in sorted(active)))
    if inactive:
        lines.append("Inactive equipment (listed on title page but NOT applicable this outage): " +
                     ", ".join(sorted(inactive)) + ". Do NOT attribute any content to these ESNs.")
    lines.append("If any of outage_start_date, outage_end_date, report_issued_date, event_type "
                 "are not already provided, extract them from the title page.")
    hints = "\n".join(lines)

    return {"metadata": doc, "hints": hints, "regions": regions}
```

## Validated output (two real FSRs)

**Rotor Out (Major Inspection):**
`gt_esn=297651`, `gen_esn=337X765`, `primary_equip_type=Gas Turbine`,
`primary_technology_code=7FA.03`, `outage_start_date=13 Mar 2020`.

**Collector Studs (Call Out):**
`gt_esn=297651`, `outage_start_date=12/21/2018`, `report_issued_date=05/24/2019`.

## Attribution accuracy (Rotor Out, full 360 K-char report)

With the structural split (GT `7549–287895`, Generator `287895–end`), keyword
spot-checks against the whole document land where they should:

| content | Generator | Gas Turbine |
|---|---|---|
| T3/T4 bearings | 66 | 0 |
| end windings | 21 | 0 |
| retaining rings | 12 | 0 |
| hydrogen seals/coolers | 47 | 0 |
| compressor | 1 | 47 |
| combustion | 0 | 80 |
| IGV | 0 | 15 |

(The few residual "generator bearing" phrases inside the GT section are embedded
Bently-Nevada vibration-probe references in the controls chapter — genuinely
located in the turbine section.)

## Tuning notes for the wider corpus

- **Section headers are the primary signal.** The numbered-TOC convention
  (`2 Turbine`, `3 Generator`, …) is standard across GE FSRs; the structural
  split takes precedence over form-prefix heuristics (so a `GTxxxx` oil-deflector
  form that physically sits in the Generator section stays tagged Generator).
- **GE form registry** (`GEN_FORMS` / `GT_FORMS`) is the fallback for reports
  with no GT/Generator split; extend it as new form numbers appear.
- **Frame codes**: the `gt_tech` regex is intentionally broad; tighten if you
  see false positives.
- Multi-section PDFs produce one **region per equipment section**. The
  single-region title-page examples above are only because those quick tests
  used pasted title text rather than a full report.
