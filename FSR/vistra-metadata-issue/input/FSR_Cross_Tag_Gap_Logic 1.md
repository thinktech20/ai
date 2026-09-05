# FSR Cross-Train Generator Tagging Gap Finder
## Relationship Diagram, Query Logic, and Runbook

Purpose: given any list of serial numbers or train IDs, identify FSR PDFs where one train-linked asset is tagged in metadata but the generator row is missing, then surface generator-scope evidence from chunk text and link a potential sibling generator event.

This package is generic. It is not tied to a specific fleet population.

## Scripts In This Folder

- `fsr_cross_tag_gaps.py`
  Workspace-local launcher. Use this file when you want the script and logic note together in the `workspace/cross_tag_gaps` folder.
- `../../fsr_cross_tag_gaps.py`
  Source-of-truth implementation. The launcher delegates to this script so the behavior stays current without maintaining duplicate code.

## What The Workbook Is Doing Now

- Input can be any train list or any ESN list.
- The output workbook keeps only gap rows where the missing sibling is the Generator.
- Chunk confirmation is still based on missing-sibling mention in the PDF chunks.
- Final gap confirmation requires generator engineering evidence from the same candidate PDFs.
- Event correlation uses an 80-day report-to-event window.
- The workbook carries both:
  - the tagged-equipment event in the main event columns
  - a potential sibling generator event in `Sibling Event Type` and `Sibling Event ID`

## Entity Relationship Diagram

```text
<GP_CATALOG>.prm_std_views (IBAT - Equipment and Plant Master)
┌─────────────────────┐       ┌──────────────────────┐       ┌──────────────────────┐
│   IBAT_TRAIN_MST    │       │  IBAT_EQUIPMENT_MST  │       │   IBAT_PLANT_MST     │
│─────────────────────│       │──────────────────────│       │──────────────────────│
│ train_sys_id  (PK)  │──────<│ equip_serial_number  │>──────│ plant_sys_id   (PK)  │
│ fuel_type           │  FK   │ equipment_type        │  FK   │ plant_name           │
│                     │       │ equipment_class       │       │ owner_name_1         │
│                     │       │ train_sys_id_fk       │       │                      │
│                     │       │ plant_sys_id_fk       │       │                      │
│                     │       │ equipment_status      │       │                      │
└─────────────────────┘       └──────────────────────┘       └──────────────────────┘
                                        │
                          equip_serial_number = ESN
                                        │
              ┌─────────────────────────┴────────────────────────────┐
              │                                                       │
              ▼                                                       ▼
<AI_CATALOG>.ai_sot_field_service_report            <GP_CATALOG>.fsr_std_views (Event Vision)
┌──────────────────────────────────────┐      ┌──────────────────────────────────────┐
│  biz_metadata_field_service_report   │      │  event_equipment_dtls_event_vision   │
│──────────────────────────────────────│      │──────────────────────────────────────│
│ document_id                          │      │ ev_serial_number                     │
│ pdf_name                             │      │ ev_equipment_event_id                │
│ esn                                  │      │ ev_equipment_type                    │
│ equipment_type                       │      │ ev_site_name                         │
│ report_issued_date                   │      └──────────────┬───────────────────────┘
│ outage_start_date                    │                     │ ev_equipment_event_id
│ event_type                           │      ┌──────────────┴───────────────────────┐
│ metadata_status                      │      │  eventmgmt_event_vision_sot          │
└──────────────────────────────────────┘      │──────────────────────────────────────│
              │                               │ ev_equipment_event_id                │
              │ pdf_name                      │ ev_actual_start_date                 │
              ▼                               │ ev_plan_event_start_date            │
<AI_CATALOG>.ai_std_con_field_service_report  │ ev_event_type                       │
┌──────────────────────────────────────┐      │ ev_event_status                     │
│  vec_field_service_report            │      │ ev_event_field_scope                │
│──────────────────────────────────────│      └──────────────────────────────────────┘
│ chunk_id                             │
│ pdf_name                             │
│ esn                                  │
│ chunk_text                           │
│ page_number                          │
│ report_date                          │
└──────────────────────────────────────┘
```

## Key Data Quality Rules

| Issue | Current Handling |
|-------|------------------|
| Metadata cardinality | `biz_metadata_field_service_report` is one row per ESN per PDF. Train-level coverage is inferred by grouping rows with the same `pdf_name`. |
| Chunk ESN inheritance | Chunks can carry a single inherited ESN or anonymized `XXXXXX`, so chunk search is done by `pdf_name`, not by ESN. |
| Workbook scope | Only gaps with `missing_equipment_type = Generator` are retained in the final workbook. |
| Weak keyword hits | Final `Gap Confirmed = YES` requires at least 3 generator engineering keywords from generator-scope chunks. |
| Event ID mismatch in metadata | Event correlation does not trust the metadata event ID. It uses report-to-event date proximity instead. |
| Event matching intent | Main event columns describe the tagged asset. Sibling event columns describe the potential generator event on the missing ESN. |

## Four-Phase Logic

### Phase 1 - Resolve Train Equipment From Any Input List

The script accepts either train IDs directly or a generic ESN list. When ESNs are supplied, it first resolves the connected train(s), then pulls Generator, Gas Turbine, and Steam Turbine siblings for each train.

```sql
SELECT
    e.equip_serial_number AS esn,
    e.equipment_type,
    e.equipment_class,
    e.train_sys_id_fk AS train_sys_id,
    p.plant_name
FROM <GP_CATALOG>.prm_std_views.ibat_equipment_mst e
JOIN <GP_CATALOG>.prm_std_views.ibat_train_mst t
    ON e.train_sys_id_fk = t.train_sys_id
LEFT JOIN <GP_CATALOG>.prm_std_views.ibat_plant_mst p
    ON e.plant_sys_id_fk = p.plant_sys_id
WHERE e.equipment_type IN ('Generator', 'Gas Turbine', 'Steam Turbine')
  AND COALESCE(e.equipment_status, '') NOT IN
      ('Scrapped', 'Never Built (Cancelled)', 'Retired')
```

Python then builds a sibling map by train.

### Phase 2 - Detect Metadata Gaps And Keep Generator-Missing Cases

All train-linked ESNs are queried in one metadata batch. Rows are grouped by `pdf_name` and compared against the full train sibling set.

```sql
SELECT
    document_id,
    pdf_name,
    esn,
    equipment_type,
    outage_start_date,
    outage_end_date,
    report_issued_date,
    event_type,
    outage_type
FROM <AI_CATALOG>.ai_sot_field_service_report.biz_metadata_field_service_report
WHERE esn IN ('337X752', '297604', '290T484', '270T484', '...')
  AND metadata_status = 'completed'
ORDER BY report_issued_date DESC
```

Gap logic:

```text
For each train and each pdf_name:
  tagged_esns = metadata rows present for that PDF on the train
  missing_esns = full train ESN set - tagged_esns

Each missing ESN becomes a gap candidate.
Only candidates where missing_equipment_type = Generator are retained.
```

That means the workbook is intentionally focused on reports that may have generator scope but are not generator-tagged in metadata.

### Phase 3 - Confirm Generator Context In Chunks

Two related checks are run on the retained generator-missing PDFs.

#### Phase 3A - Preliminary Missing-Sibling Mention Check

The script scans chunk text by `pdf_name` for either the missing generator serial number or the missing generator equipment type.

```sql
SELECT
    chunk_id,
    pdf_name,
    esn,
    chunk_text,
    page_number,
    report_date
FROM <AI_CATALOG>.ai_std_con_field_service_report.vec_field_service_report
WHERE pdf_name IN ('Field_Service_Report_1.pdf', 'Field_Service_Report_2.pdf', '...')
  AND (
      LOWER(chunk_text) LIKE '%290t484%'
      OR LOWER(chunk_text) LIKE '%generator%'
  )
```

This produces `keyword_matches`, but it is not the final confirmation test.

#### Phase 3B - Generator-Scope Engineering Evidence

The script then scans only those candidate PDFs for true generator engineering language such as:

- `MAGIC Inspection`
- `Winding Resistance`
- `DC Leakage`
- `AC Impedance`
- `Belly Bands`
- `Collector Rings`
- `Seal Rings`
- `Red Eye Repair`

Only PDFs with at least 3 engineering keywords contribute to final `Gap Confirmed = YES`.

Outputs from this phase:

- `engineering_keywords_found`
- `engineering_keyword_count`
- `generator_scope_candidates.json`
- `generator_scope_chunk_ids.json`

### Phase 4 - Event Correlation With Tagged And Sibling Views

Events are pulled for all train ESNs from Event Vision.

```sql
SELECT
    eq.ev_serial_number AS esn,
    eq.ev_equipment_event_id,
    eq.ev_site_name,
    eq.ev_equipment_type,
    ev.ev_event_type,
    ev.ev_event_status,
    ev.ev_event_field_scope,
    COALESCE(ev.ev_actual_start_date, ev.ev_plan_event_start_date) AS event_date,
    ev.ev_actual_end_date
FROM <GP_CATALOG>.fsr_std_views.eventmgmt_event_vision_sot ev
JOIN <GP_CATALOG>.fsr_std_views.event_equipment_dtls_event_vision_sot eq
    ON ev.ev_equipment_event_id = eq.ev_equipment_event_id
WHERE eq.ev_serial_number IN ('337X752', '297604', '290T484', '270T484', '...')
  AND ev.ev_event_status IN ('Completed', 'In Progress')
ORDER BY event_date DESC
```

Matching rules:

- `Matched Event Date`, `Event Type`, and `Field Scope` are selected from the tagged ESN side.
- `Sibling Event Type` and `Sibling Event ID` are selected from the missing generator ESN side.
- The report date must be between 0 and 80 days after the event date.

This gives the workbook a direct way to associate a prime-mover-tagged report with a plausible sibling generator event.

## Output Files

The script writes revisioned outputs so repeated runs do not overwrite earlier files.

- `cross_tag_gaps.xlsx`
- `cross_tag_gaps.json`
- `generator_scope_candidates.json`
- `generator_scope_chunk_ids.json`

If a file already exists, a new revision such as `_rev01`, `_rev02`, and so on is written automatically.

## Workbook Structure

### `FSR Tagging Gaps`

One row per generator-missing PDF gap.

Important columns:

| Column | Meaning |
|--------|---------|
| `Tagged ESN` | Asset that already has the FSR metadata row |
| `Tagged Equipment Type` | Usually the connected Gas Turbine or Steam Turbine |
| `Missing ESN` | Generator ESN missing from the metadata table for that PDF |
| `Missing Equipment Type` | Always `Generator` in the retained workbook rows |
| `Matched Event Date` | Tagged-side event date within the 80-day window |
| `Event Type` | Tagged-side event type |
| `Sibling Event Type` | Potential generator-side event type |
| `Sibling Event ID` | Potential generator-side `ev_equipment_event_id` |
| `Gap Confirmed` | `YES` only when generator engineering evidence reaches threshold |
| `Keyword Matches` | Count of generator engineering keywords found in candidate chunks |
| `Keywords Found` | Deduplicated generator engineering terms |

### `Generator Scope Candidates`

Chunk-level shortlist for deeper semantic follow-up.

Important fields include:

- `Chunk ID`
- `Scope Category`
- `Technical Keywords`
- `Findings / Results`
- `Semantic Seed Query`

### `Summary`

Top-level run counts including trains analyzed, seed ESNs, PDFs scanned, confirmed gaps, and generator-scope candidate counts.

## How To Run It

Run the same-folder launcher from the repo root:

```bash
python workspace/cross_tag_gaps/fsr_cross_tag_gaps.py \
  --esn "337X752,337X753,290T484"
```

Use a text file containing any ESN list:

```text
337X752
337X753
290T484
290T435
```

```bash
python workspace/cross_tag_gaps/fsr_cross_tag_gaps.py \
  --esn-file workspace/cross_tag_gaps/my_serial_numbers.txt \
  --output-dir workspace/cross_tag_gaps/run_20260531
```

Run by train ID instead:

```bash
python workspace/cross_tag_gaps/fsr_cross_tag_gaps.py \
  --train-ids "UNI036482 UNI036596" \
  --output-dir workspace/cross_tag_gaps/run_train_ids
```

Skip chunk work if you only want the metadata gap candidates:

```bash
python workspace/cross_tag_gaps/fsr_cross_tag_gaps.py \
  --esn-file workspace/cross_tag_gaps/my_serial_numbers.txt \
  --skip-chunks
```

## Environment Notes

- Reads `.env` and `.env prod` from the repo root.
- Uses `DATABRICKS_HOST`, `DATABRICKS_WAREHOUSE`, and `DATABRICKS_TOKEN`.
- Defaults to `vaip` for AI tables and `vgpp` for operational tables in prod.
- If `vgpp` is not accessible, the script automatically falls back to `vgpd`.

## Recommended Share Package

For a handoff or shareable folder, keep these items together:

- `FSR_Cross_Tag_Gap_Logic.md`
- `fsr_cross_tag_gaps.py`
- the generated `cross_tag_gaps.xlsx`
- the generated `cross_tag_gaps.json`
- optionally `generator_scope_candidates.json` and `generator_scope_chunk_ids.json`
