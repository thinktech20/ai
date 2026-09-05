# Vistra Generator FSR Tagging — Action Plan

**Date:** 2026-05-31
**Trigger:** Jon — *"I did some tweaks over the weekend to the keyword logic looking for generator scope in prime-mover-tagged equipment… I need to give an update to the Vistra account team by end of week — need these FSRs tagged in the metadata table."*
**Inputs from Jon:** `Vistra Generator Missing Reports 5.31.26.xlsx`, `fsr_cross_tag_gaps.py`, `FSR_Cross_Tag_Gap_Logic 1.md`
**Deliverable back to Jon:** **`Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx`** — Jon's same workbook with one new `Action` column on the `FSR Tagging Gaps` sheet.
**Decision needed by:** Friday EOD (account-team update)

---

## 1. What we will do (this week)

For each of the 47 PDFs in Jon's `FSR Tagging Gaps` sheet where `Gap Confirmed = YES`, today the **prod** state is:

- `vaip.ai_sot_field_service_report.biz_metadata_field_service_report` — has 1 row per PDF, all tagged to the prime-mover GT/ST ESN. The Generator ESN row is **missing** for every one of the 47.
- `vaip.ai_std_con_field_service_report.vec_field_service_report` — has chunks for every one of the 47 PDFs, all tagged (top-level `esn` and inside the `metadata` JSON) to the same prime-mover ESN. No chunk row carries the Generator ESN.

A search keyed on the Generator ESN therefore returns nothing for these PDFs, even though the FSR demonstrably describes Generator work.

The enriched workbook **`Vistra Generator Missing Reports 5.31.26 - ENRICHED.xlsx`** adds one new column — **`Action (Vistra delivery plan)`** — to the right of the `FSR Tagging Gaps` sheet. All 47 confirmed rows carry the **same** value:

> **INSERT 1 row into `biz_metadata_field_service_report` (esn = `Missing ESN`) + for each existing chunk of this PDF in `vec_field_service_report`, INSERT a duplicate row with esn = `Missing ESN` (text + embedding unchanged; metadata JSON `esn` / `equipment_sys_id` / `equipment_type` / `equipment_class_code` rewritten to the Generator).**

The remaining 205 rows (`Gap Confirmed = NO`) carry `(deferred - weak match, SME review next week)` — see §2 Item 2.

### 1a. How the new `biz_metadata_field_service_report` row is filled

The new row is for the same physical PDF as the existing prime-mover row, so everything that describes the file (path, title, customer, dates, page count) is **inherited** from the existing row. Only the equipment-identity fields change.

| column | source | example: Casco Bay PDF<br>`A-1425468_FSP-256875_C-10326237.pdf` | example: Lamar PDF<br>`A-1425464_FSP-256871_C-10326234.pdf` |
|---|---|---|---|
| `pdf_name` | same as existing row | `…A-1425468_FSP-256875_C-10326237.pdf` | `…A-1425464_FSP-256871_C-10326234.pdf` |
| `document_id` | **new** UUID per inserted row | new UUID | new UUID |
| `esn` | **`Missing ESN`** from Jon's workbook | `290T435` | `337X710` |
| `esn_source` | **new tag** for traceability / rollback | `cross_tag_gap_v1` | `cross_tag_gap_v1` |
| `equipment_type` | constant | `Generator` | `Generator` |
| `equipment_sys_id` | IBAT lookup for the Generator ESN (already resolved upstream in Jon's workbook) | sys_id for `290T435` | sys_id for `337X710` |
| `equipment_class_code` | IBAT lookup for the Generator ESN | (Generator class) | (Generator class) |
| `event_type` | from `Sibling Event Type` if present, else inherit | (sibling event) | (sibling event) |
| `ev_project_id`, `ev_equipment_event_id` | from `Sibling Event ID` | from `Sibling Event ID` | from `Sibling Event ID` |
| `volume_path` *(NOT NULL)* | inherit | `/Volumes/…/A-1425468_…pdf` | `/Volumes/…/A-1425464_…pdf` |
| `title`, `customer`, `prepared_by`, `approved_by`, `document_summary`, `report_issued_date`, `outage_start_date`, `outage_end_date`, `outage_type`, `technology_type`, `fsr_number`, `page_count`, `file_size_bytes`, `file_last_modified` | inherit (same physical PDF) | same as the `270T435` row | same as the `297258` row |
| `metadata_status`, `chunk_status` *(NOT NULL)* | constants | `completed`, `completed` | `completed`, `completed` |
| `ingested_at`, `scraped_at` | now() | now | now |
| `chunked_at` | inherit (chunks already exist) | inherit | inherit |

After the run, a query that today returns 1 row returns 2:

```sql
SELECT pdf_name, esn, esn_source, equipment_type
FROM vaip.ai_sot_field_service_report.biz_metadata_field_service_report
WHERE pdf_name = 'Field_Service_Report_ProjectID_A-1425468_FSP-256875_C-10326237.pdf';

-- before:
-- 270T435 | llm              | Steam Turbine
-- after:
-- 270T435 | llm              | Steam Turbine
-- 290T435 | cross_tag_gap_v1 | Generator
```

### 1b. What "duplicate chunks in `vec_field_service_report`" means

Each row in `vec_field_service_report` is one **(document, chunk)** pair: `pdf_name`, `document_id`, `chunk_index`, `text`, top-level `esn`, `metadata` JSON (`esn`, `equipment_sys_id`, `equipment_type`, `equipment_class_code`, …), `embedding`.

For each existing chunk row of the PDF, we insert a second row that is **identical except for the equipment identity**:

| field | original chunk row (kept unchanged) | new copy row (inserted) |
|---|---|---|
| `pdf_name`, `chunk_index`, `text`, `embedding` | unchanged | **identical** (no re-chunking, no re-embedding) |
| `document_id` | e.g. `7f3a…b2` | `7f3a…b2_<MissingESN>` (suffix the new ESN — guarantees uniqueness) |
| top-level `esn` | `Tagged ESN` (e.g. `270T435`) | **`Missing ESN`** (e.g. `290T435`) |
| `metadata` JSON `esn` | `"270T435"` | **`"290T435"`** |
| `metadata` JSON `equipment_sys_id` | (Steam Turbine sys_id) | **(Generator sys_id for `290T435`)** |
| `metadata` JSON `equipment_type` | `"Steam Turbine"` | **`"Generator"`** |
| `metadata` JSON `equipment_class_code` | (ST class) | **(Generator class)** |

So if the Casco Bay PDF has 145 chunk rows today (all `esn = 270T435`), after the run it has 290 rows (145 with `270T435` + 145 with `290T435`). Same text, same embeddings, second identity. Verification:

```sql
SELECT esn, COUNT(*) AS chunk_rows
FROM vaip.ai_std_con_field_service_report.vec_field_service_report
WHERE pdf_name = 'Field_Service_Report_ProjectID_A-1425468_FSP-256875_C-10326237.pdf'
GROUP BY esn;
-- expected: 270T435 | N    AND    290T435 | N
```

After the daily vector-index sync, a search keyed on `290T435` returns this PDF — which is the user-visible win.

### 1c. Why both tables need the change

| table | what it answers | without it |
|---|---|---|
| `biz_metadata_field_service_report` | "Is this Generator ESN tagged on any FSR?" | Jon's keyword-gap finder still flags it as missing; OSA metadata views don't list the FSR under that Generator |
| `vec_field_service_report` | "When somebody searches by Generator ESN, what passages come back?" | Search returns nothing for the Generator ESN — the passages exist but are tagged only to the GT/ST sibling |

Adding only the `biz_metadata_field_service_report` row fixes the catalog view. Adding only the chunk copies fixes search. Both are needed for "the user can find this content under the Generator ESN".

### 1d. About the dev environment (why an earlier draft said "15 PDFs need loading first")

In **prod (`vaip`)**, all 47 PDFs already exist in both tables — the action is uniform.

In **dev (`vaid`)** the picture is different: 32 of the 47 are chunked in `vec_field_service_report`, the other 15 are not, and 11 of those 15 are also missing from `biz_metadata_field_service_report` entirely. That gap is purely a dev/prod environment-sync issue (dev is behind on FSR ingestion for 15 of the 310 PDFs Jon scanned), not a Vistra problem. Closing it is an internal dev task — see §2 Item 5 — and does not change anything Vistra sees.

### Sequence this week

1. **Run all 47 in dev first** (reversible; audit log per inserted row). Where dev is missing a PDF (the 15 dev-only gaps from §1d), the standard loader runs first to bring dev to parity, then the 47-row action runs uniformly.
2. **Refresh the dev vector index** so the 47 are findable by Generator ESN.
3. **Verify** — for each of the 47, confirm (a) a `biz_metadata_field_service_report` row exists with `esn = Missing ESN` and `esn_source = cross_tag_gap_v1`; (b) `vec_field_service_report` has chunks for `(pdf_name, Missing ESN)`; (c) a Generator-ESN search returns the PDF.
4. **Vistra SME spot-checks** dev results against the enriched workbook.
5. **Promote to prod (`vaip`)** with the same action, after SME ack. Hand Jon the enriched workbook with `Dev Status = Done` and `Prod Status = Done` filled in.

---

## 2. Next steps (after this week)

In priority order. Item 1 is the actual structural fix.

| # | Action | Why | Owner | When |
|---|---|---|---|---|
| 1 | **Fix the upstream equipment-link list** so that, going forward, every Vistra train's Generator ESN is listed alongside the GT/ST ESN. Once fixed, the standard pipeline closes this gap by itself — no Vistra-specific helper needed. | This is the root cause. Today the upstream source-of-truth view only carries the prime-mover ESN for these 47 PDFs, which is why the standard repair workflow doesn't cover them today and why a fresh ingestion would drop the Generator row again. | Data & Analytics team (view owner) + Dev Team | next week |
| 2 | **Triage the 205 weak-match rows** (`Gap Confirmed = NO`) — export for Vistra SME review; keep out of `biz_metadata_field_service_report` until SME spot-confirms or the threshold is loosened. | Recovers more Generator coverage without polluting metadata with low-confidence rows. | Dev Team + Vistra SME | next week |
| 3 | **Loosen the confirmation rule** to "literal Generator ESN appears in the text **OR** ≥3 keywords match" (today: only `≥3 keywords`). | Recovers ~20–40 of the 205 weak rows that literally name the Generator ESN but fire fewer keywords (e.g. Moss Landing — see Appendix B). | Jon + Dev Team | next week |
| 4 | **Extend Jon's keyword list** with SME-validated phrases not in v1: `MAGIC`, `Robotic`, `end winding`, `stator core`, `loose core`. Exclude shared `Minor Inspection`. | Already SME-validated as Generator-scope. | Jon | next week |
| 5 | **Sync dev to prod** for the 15 PDFs missing chunks in `vaid.ai_std_con_field_service_report.vec_field_service_report` (and the 11 also missing from `vaid.ai_sot_field_service_report.biz_metadata_field_service_report`) — internal dev hygiene only, no Vistra-visible impact. | So dev mirrors prod for future debugging / SME spot-checks. | Dev Team | this week or next |
| 6 | **Promote this week's 47 from dev to prod (`vaip`)** with the same Action, after SME ack. | Closes the loop for the Vistra account team. | D&A + Dev Team | next week |
| 7 | **Rebuild the underlying metadata-generation logic** so future FSRs consult chunk evidence and the equipment hierarchy, not just the upstream view. | Structural fix — every new FSR will reintroduce this gap until that logic is rebuilt. Today's keyword pass is remediation, not a fix. | D&A | Q3 |

---

## 3. Open questions for the Vistra account team

1. **Who owns the post-load verification on Vistra's side?** We need a Vistra SME by Wednesday to spot-check the 47 PDFs against the enriched workbook (Plant, PDF, Missing ESN, Keyword Matches) — query `biz_metadata_field_service_report` and a Generator-ESN search against the dev vector index.
2. **Ship the 47 now, or wait for the looser-rule re-run** (§2 Items 3 + 4) next week? Recommendation: ship the 47 now, deliver the re-run as an additive batch.
3. **Visibility on the 205 weak rows** — now (with the enriched workbook, where they're marked `deferred`), or only after next-week SME triage?

---

## 4. Headline numbers for the account-team brief

| metric | value |
|---|---:|
| Vistra trains analyzed | 51 |
| PDFs scanned | 310 |
| Metadata gaps found (GT/ST-tagged FSRs missing the Generator row in `biz_metadata_field_service_report`) | 252 |
| **Confirmed for delivery this week — uniform Action across all rows** | **47** |
| Deferred to next-week SME triage (§2 Item 2) | 205 |

Per-row plan → enriched workbook. Full evidence list → [Appendix H](#appendix-h--the-47-confirmed-rows-full-list-embedded-for-self-contained-review).

---

# Appendices

## Appendix A — Why this matters (90-second framing for the account team)

Vistra owns 51 trains. Every train has at least one Gas Turbine or Steam Turbine *and* a Generator. When GE Vernova writes a Field Service Report covering an outage on one of those trains, the FSR text routinely describes work on both the prime mover and the Generator — but the current metadata (`biz_metadata_field_service_report`) often only tags the prime-mover ESN, leaving the Generator ESN with no metadata row for that PDF. Result: any Generator-keyed search for that Vistra unit returns nothing, even though the work is genuinely documented.

Jon's cross-tag gap finder scans every Vistra train, finds PDFs with this exact pattern, and confirms by looking for generator-scope engineering language in the chunk text. The 47 confirmed rows are PDFs that demonstrably describe Generator work and need Generator metadata rows added.

## Appendix B — Jon's keyword logic (summary of `FSR_Cross_Tag_Gap_Logic 1.md`)

Four phases:

1. **IBAT expansion** — input ESN/train list → all Generator/GT/ST siblings per train (51 seed → 102 ESNs).
2. **Metadata-gap detection** — for each PDF on a train, compare tagged ESNs to full sibling set; flag PDFs missing the Generator row.
3. **Chunk-text confirmation** — scan candidate PDFs for generator-engineering keywords; require **≥3 distinct keywords** for `Gap Confirmed = YES`.
4. **Event correlation** — 0–80 day report-to-event window; carry tagged-side event AND sibling Generator event.

### Generator-engineering keyword set (Jon's v1)

`Seal Rings`, `Blue Check`, `Hydrogen Seal Assembly`, `End Shield`, `Wedges`, `Greasing`, `Retaining Rings`, `Oil Deflectors / Oil Deflector Alignment`, `Fan Blades`, `Collector Rings`, `Generator Pressure Test`, `MAGIC Inspection`, `Winding Resistance`, `DC Leakage`, `AC Impedance`, `Belly Bands`, `Red Eye Repair`

The list is Generator-scope only; ambiguous shared terms like `Minor Inspection` are excluded by design (Minor Inspection is also a Steam Turbine activity).

### Threshold trade-off visible in the workbook

A clean illustration of where `≥3` over-rejects:

| Plant | PDF | Chunk text contains literal Generator ESN? | Keywords fired | Verdict |
|---|---|---|---|---|
| Moss Landing | `…EV-180503_EVP-552737.pdf` | yes — `Generator Field Serial Number: 290T484` | 0 | ❌ NO |
| Moss Landing | `…FSP-294850_C-10350768.pdf` | implicit | 2 (Blue Check, Seal Rings) | ❌ NO |
| Hanging Rock | `…EV-123983_C-10366888…pdf` | implicit | 10 | ✅ YES |
| Lamar Power Partners | `…EV-190593_EVP-559293.pdf` | yes — narrative names 290T435 H₂ leak | 5+ across chunks | ✅ YES |

The Moss Landing rows are why §2 Item 1 (loosen to `esn_string_hit OR ≥3 keywords`) is the highest-value follow-up.

<!-- Engineering appendices (C — insert-row mapping, D — INSERT template, E — three-layer tagging deep-dive, G — schema verification, I — bucket probe, J — pipeline-native runbook) removed 2026-06-01 at user request: "no engineering details". The full engineering plan and SQL is preserved in the dev team's internal runbook + the data_probes/p17_real_tables.py + data_probes/p20_enrich_workbook.py scripts. -->

## Appendix F — References

- `Vistra Generator Missing Reports 5.31.26.xlsx` — Jon's workbook, 3 sheets: `FSR Tagging Gaps` (252), `Generator Scope Candidates` (516), `Summary` (12).
- `fsr_cross_tag_gaps.py` — workspace launcher; source-of-truth at `<repo_root>/fsr_cross_tag_gaps.py`.
- `FSR_Cross_Tag_Gap_Logic 1.md` — Jon's runbook (the May-31 revision; supersedes the older `FSR_Cross_Tag_Gap_Logic.md`).
- `FSR_Multi_ESN_Exemplar_OceanState.md` — single-PDF deep-dive on the 3-layer tagging problem (§6, §8, §10a, §10b, §10c, §11).
- `FSR_IBAT_Investigation_2026-05-26.md` — fleet-level parent investigation.

## Appendix H — The 47 confirmed rows (full list, embedded for self-contained review)

Extracted 2026-05-31 from `Vistra Generator Missing Reports 5.31.26.xlsx` → sheet `FSR Tagging Gaps` → `Gap Confirmed = YES`. Sorted by Plant, then Report Date. Column legend: **Tagged ESN (type)** = the ESN the FSR is currently tagged to (`GT` = Gas Turbine, `ST` = Steam Turbine); **Missing ESN (Gen)** = the Generator ESN to be added; **PDF (stem)** = filename with `Field_Service_Report_ProjectID_` prefix and `.pdf` suffix removed, truncated to 55 chars; **KW** = `Keyword Matches` count (Jon's logic, threshold ≥3); **Keywords (top)** = first ~60 chars of `Keywords Found`. Full keyword lists and chunk excerpts remain in the staged `staging.vistra_gap_2026_05_31` table for the post-load SME query.

| # | Plant | Tagged ESN (type) | Missing ESN (Gen) | PDF (stem) | Report Date | KW | Keywords (top) |
|--:|---|---|---|---|---|--:|---|
| 1 | Casco Bay Power Station | 270T432 (ST) | 290T432 | `g_GE_Energy_Services_D11_Major_Inspection_Technical_...` | 2007-07-12 | 4 | Stator Winding, Wedges, Blue Check, End Shield |
| 2 | Casco Bay Power Station | 270T432 (ST) | 290T432 | `STEAM_TURBINE_INSPECTION_REPORT_D11_L-0_bucket_repla...` | 2011-06-03 | 8 | Hydrogen Seal Assembly, MAGIC Inspection, Oil Deflector A... |
| 3 | Casco Bay Power Station | 297198 (GT) | 337X063 | `GAS_TURBINE_INSPECTION_REPORT_UNIT_2_COMPRESSOR_UPGR...` | 2011-11-29 | 6 | End Shield, Hydrogen Seal Assembly, Oil Deflector Alignme... |
| 4 | Casco Bay Power Station | 297197 (GT) | 337X053 | `GAS_TURBINE_INSPECTION_REPORT_UNIT_1_COMPRESSOR_UPGR...` | 2011-11-29 | 5 | End Shield, Hydrogen Seal Assembly, Oil Deflector Alignme... |
| 5 | Casco Bay Power Station | 297198 (GT) | 337X063 | `A-1828118_EV-156901_EVP-536585` | 2025-10-14 | 7 | Core, Retaining Rings, Step Iron, Sub-slots, Main Lead, G... |
| 6 | Casco Bay Power Station | 270T432 (ST) | 290T432 | `EV-188520_EVP-557831` | 2026-01-09 | 3 | Seal Rings, Wedges, Collector Rings |
| 7 | FAIRLESS ENERGY CENTER | 298177 (GT) | 338X738 | `GAS_TURBINE_INSPECTION_REPORT_GAS_TURBINE_MAJOR_INSP...` | 2011-05-06 | 6 | End Shield, Hydrogen Seal Assembly, Oil Deflector Alignme... |
| 8 | FAIRLESS ENERGY CENTER | 298235 (GT) | 338X742 | `GAS_TURBINE_INSPECTION_REPORT_Unit_2B_Hot_Gas_Path_I...` | 2012-05-17 | 5 | End Shield, Hydrogen Seal Assembly, Oil Deflector Alignme... |
| 9 | FORNEY POWER PLANT | 298016 (GT) | 337X259 | `A-1655918_FSP-305393_C-10358660` | 2021-04-28 | 3 | Oil Deflector Alignment, Oil Deflectors, Wedge Tightness ... |
| 10 | FORNEY POWER PLANT | 298018 (GT) | 337X261 | `A-1734332_EV-136170_C-10370464` | 2022-06-30 | 5 | Collector Rings, Fan Blades, Hydrogen Seal Assembly, Oil ... |
| 11 | Fayette Energy Facility | 298158 (GT) | 338X732 | `GAS_TURBINE_INSPECTION_REPORT_Duke_Fayette_HGP_with_...` | 2011-05-11 | 12 | Belly Bands, Belly band inspection, End Shield, Fan Blade... |
| 12 | Fayette Energy Facility | 298159 (GT) | 338X731 | `A-1633218_EV-106619_EVP-502992` | 2025-05-09 | 28 | AC Impedance, Collector Rings, Core, DC Leakage, End-wind... |
| 13 | Fayette Energy Facility | 298158 (GT) | 338X732 | `A-1633216_EV-106618_EVP-502991` | 2025-05-09 | 29 | AC Impedance, Belly Bands, Collector Rings, Core, DC Leak... |
| 14 | Fayette Energy Facility | 298158 (GT) | 338X732 | `A-1377308_FSP-260331_C-10329389` | n/a | 30 | 10-minute 5000 VDC Megger PI, 10-minute Megger, Collector... |
| 15 | Hanging Rock Energy Facility | 298127 (GT) | 338X727 | `GAS_TURBINE_INSPECTION_REPORT_Major_Inspection_for_E...` | 2012-01-17 | 8 | End Shield, Hydrogen Seal Assembly, Oil Deflector Alignme... |
| 16 | Hanging Rock Energy Facility | 298112 (GT) | 338X725 | `A-1633202_EV-116831_C-10366904_EVP-515928` | 2024-06-13 | 10 | Collector Rings, Fan Blades, Hydrogen Seal Assembly, Oil ... |
| 17 | Hanging Rock Energy Facility | 298113 (GT) | 338X726 | `A-1633204_EV-124343_C-10366903_EVP-515929` | 2024-06-13 | 9 | Collector Rings, Fan Blades, Hydrogen Seal Assembly, Oil ... |
| 18 | Hanging Rock Energy Facility | 298128 (GT) | 338X728 | `A-1633210_EV-123983_C-10366888_EVP-515935` | 2024-12-20 | 10 | Oil Deflector Alignment, Oil Deflectors, Seal Rings, Fan ... |
| 19 | Hanging Rock Energy Facility | 298127 (GT) | 338X727 | `A-1633208_EV-118802_C-10366901_EVP-515932` | 2024-12-20 | 7 | Collector Rings, End Shield, Fan Blades, Hydrogen Seal As... |
| 20 | INDEPENDENCE POWER STATION | 270T259 (ST) | 290T259 | `g_GE_Energy_Services_Generator_Field_Changeout_for_S...` | 2006-05-31 | 8 | Blue Check, Oil Deflector Alignment, Oil Deflectors, Seal... |
| 21 | INDEPENDENCE POWER STATION | 296300 (GT) | 337X009 | `A-1586168_FSP-286344_C-10344989` | 2024-05-31 | 28 | AC Impedance, Belly Bands, Belly band inspection, Core, D... |
| 22 | KENDALL POWER STATION | 297544 (GT) | 337X758 | `A-1488512_FSP-270381_C-10333878` | 2021-06-15 | 32 | AC Impedance, Core, DC Hipot, DC Leakage, End Shield, End... |
| 23 | KENDALL POWER STATION | 297545 (GT) | 337X759 | `A-1737456_EV-136778_C-10370713` | 2022-07-28 | 4 | Oil Deflector Alignment, Oil Deflectors, Seal Rings, Grea... |
| 24 | LAMAR POWER PARTNERS | 297257 (GT) | 337X711 | `GAS_TURBINE_INSPECTION_REPORT_GT_22_MAJOR_INSPECTION...` | 2012-01-04 | 9 | End Shield, Fan Blades, Generator Pressure Test, Hydrogen... |
| 25 | LAMAR POWER PARTNERS | 297258 (GT) | 337X710 | `GAS_TURBINE_INSPECTION_REPORT_Major_Inspection_for_L...` | 2012-01-26 | 7 | End Shield, Hydrogen Seal Assembly, Oil Deflector Alignme... |
| 26 | LAMAR POWER PARTNERS | 297256 (GT) | 337X708 | `A-1682960_EV-114155_C-10364457` | 2022-04-25 | 9 | End-winding, Fan Blades, Gooseneck, MAGIC Inspection, Pol... |
| 27 | LAMAR POWER PARTNERS | 297255 (GT) | 337X709 | `A-1828574_EV-156982_C-10378887_EVP-536642` | 2024-04-13 | 7 | Focused Generator Inspection, Greasing, Keybars, Step Iro... |
| 28 | LAMAR POWER PARTNERS | 297258 (GT) | 337X710 | `A-1718410_EV-131641_C-10378975_EVP-521582` | 2024-06-25 | 19 | AC Impedance, DC Leakage, Focused Generator Inspection, G... |
| 29 | LAMAR POWER PARTNERS | 297257 (GT) | 337X711 | `A-1426924_EV-107829_C-10333940_EVP-504930` | 2024-06-26 | 18 | AC Impedance, DC Leakage, Fan Blades, Focused Generator I... |
| 30 | LAMAR POWER PARTNERS | 270T435 (ST) | 290T435 | `A-1881852_EV-168186_EVP-545083` | 2025-04-08 | 4 | Oil Deflector Alignment, Oil Deflectors, Wedge Tightness ... |
| 31 | LAMAR POWER PARTNERS | 270T435 (ST) | 290T435 | `A-1989440_EV-190593_EVP-559293` | 2026-03-30 | 8 | Collector Rings, Fan Blades, Hydrogen Seal Assembly, Oil ... |
| 32 | LAMAR POWER PARTNERS | 297258 (GT) | 337X710 | `A-1838482_EV-158764_EVP-538036` | 2026-04-06 | 4 | Collector Rings, Fan Blades, Oil Deflector Alignment, Oil... |
| 33 | LAMAR POWER PARTNERS | 297256 (GT) | 337X708 | `A-1628248_FSP-298346_C-10353097` | n/a | 7 | Core, Wedges, End-winding, Loose End-winding Blocking, Ma... |
| 34 | LAMAR POWER PARTNERS | 270T435 (ST) | 290T435 | `A-1425468_FSP-256875_C-10326237` | n/a | 29 | AC Impedance, Collector Rings, Core, DC Leakage, DLRO, En... |
| 35 | LAMAR POWER PARTNERS | 297258 (GT) | 337X710 | `A-1425464_FSP-256871_C-10326234` | n/a | 30 | AC Impedance, Belly Bands, Core, DC Hipot, DC Leakage, DL... |
| 36 | LAMAR POWER PARTNERS | 297257 (GT) | 337X711 | `A-1425758_FSP-256873_C-10326236` | n/a | 27 | AC Impedance, Collector Rings, DC Leakage, DLRO, Greasing... |
| 37 | Moss Landing | 297603 (GT) | 337X751 | `A-1375356_FSP-293536_C-10349934` | 2021-05-25 | 3 | Oil Deflector Alignment, Oil Deflectors, Seal Rings |
| 38 | Moss Landing | 297605 (GT) | 337X753 | `A-1377354_EV-121543_C-10350372` | 2022-05-22 | 48 | 10-minute 5000 VDC Megger PI, AC Impedance, Collector Rin... |
| 39 | Moss Landing | 297604 (GT) | 337X752 | `A-1376570_EV-113525_C-10350370` | 2022-05-25 | 56 | 10-minute 5000 VDC Megger PI, AC Impedance, Amortisseur, ... |
| 40 | Moss Landing | 297602 (GT) | 337X750 | `GAS_TURBINE_INSPECTION_REPORT_Forced_Major_Inspectio...` | n/a | 5 | Oil Deflector Alignment, Oil Deflectors, Seal Rings, Wedg... |
| 41 | ODESSA ECTOR POWER PLANT | 297493 (GT) | 337X155 | `A-1656076_FSP-305414_C-10358674` | 2021-04-28 | 3 | Oil Deflector Alignment, Oil Deflectors, Collector Rings |
| 42 | ODESSA ECTOR POWER PLANT | 297493 (GT) | 337X155 | `A-1686570_FSP-313453_C-10365083` | 2021-11-29 | 3 | Oil Deflector Alignment, Oil Deflectors, Collector Rings |
| 43 | ODESSA ECTOR POWER PLANT | 297490 (GT) | 337X152 | `GAS_TURBINE_INSPECTION_REPORT_GT1_Major_Inspection_a...` | n/a | 8 | End Shield, Generator Pressure Test, Hydrogen Seal Assemb... |
| 44 | ODESSA ECTOR POWER PLANT | 297493 (GT) | 337X155 | `A-1505048_FSP-253386_C-10323897` | n/a | 24 | AC Impedance, Collector Rings, DC Leakage, End-winding, F... |
| 45 | Washington Energy Facility | 297623 (GT) | 337X768 | `GAS_TURBINE_INSPECTION_REPORT_HGPI_and_package_4_enh...` | 2011-11-14 | 8 | Blue Check, Generator Pressure Test, Oil Deflector Alignm... |
| 46 | Washington Energy Facility | 297624 (GT) | 337X767 | `A-1377050_FSP-261004_C-10330490` | n/a | 33 | DC Leakage, End-winding, Focused Generator Inspection, Gr... |
| 47 | Washington Energy Facility | 297623 (GT) | 337X768 | `A-1376780_FSP-261003_C-10330252` | n/a | 32 | 10-minute 5000 VDC Megger PI, 10-minute Megger, Collector... |

**Plant distribution (47 rows across 10 Vistra plants):** LAMAR POWER PARTNERS 13 · Casco Bay 6 · Hanging Rock 5 · Moss Landing 4 · Fayette 4 · ODESSA 4 · Washington 3 · FAIRLESS 2 · FORNEY 2 · INDEPENDENCE 2 · KENDALL 2.

**Tagged-side split:** 39 rows tagged to a Gas Turbine, 8 rows tagged to a Steam Turbine (all 8 from Casco Bay / INDEPENDENCE / LAMAR — the trains where the Generator is paired with the ST on the shared shaft).

**Keyword strength split:** 9 rows at the threshold floor (KW=3 or 4) · 22 rows mid-band (KW=5–10) · 16 rows very strong (KW>10, max 56 at Moss Landing).
