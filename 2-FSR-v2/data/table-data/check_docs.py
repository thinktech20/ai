import csv, json

TARGET_DOCS = [
    '9e279e5a-a24e-4ebd-a79e-5aa24efebd04',
    'af693a98-1e5c-499d-aa10-cccc54885c64',
    '796f4d53-a8ad-42e1-af4d-53a8add2e1a4',
    '806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report',
    'bddc3379-f29f-4665-9c33-79f29f1665be',
    'b775cf29-8b42-4a83-af21-53075fef0802',
]

BASE = '/home/u560060992/dbx/2-FSR-v2/data/table-data'
META_FILE = BASE + '/fsr_metadata_v2.csv'
MAP_FILE  = BASE + '/fsr_document_equipment_map_v2.csv'

print('=== METADATA TABLE ===')
with open(META_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        doc_id = (row.get('document_id') or '').strip()
        if any(t.lower() in doc_id.lower() for t in TARGET_DOCS):
            print()
            print('document_id       :', doc_id)
            print('pdf_name          :', row.get('pdf_name'))
            print('primary_esn       :', row.get('primary_esn'))
            print('gt_esn            :', row.get('gt_esn'))
            print('gen_esn           :', row.get('gen_esn'))
            print('report_issued_date:', row.get('report_issued_date'))
            print('metadata_status   :', row.get('metadata_status'))
            print('chunk_status      :', row.get('chunk_status'))
            regions_raw = row.get('preprocessor_regions') or ''
            if regions_raw:
                try:
                    regions = json.loads(regions_raw)
                    esns = sorted({
                        r.get('metadata', {}).get('primary_esn', '')
                        for r in regions
                        if r.get('metadata', {}).get('primary_esn')
                    })
                    print('region_esns       :', esns)
                    print('region_count      :', len(regions))
                except Exception as e:
                    print('regions_parse_err :', e)

print()
print('=== DOCUMENT EQUIPMENT MAP ===')
with open(MAP_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        doc_id = (row.get('document_id') or '').strip()
        if any(t.lower() in doc_id.lower() for t in TARGET_DOCS):
            print(
                doc_id,
                '| esn=', row.get('esn'),
                '| equip_type=', row.get('equip_type'),
                '| is_primary=', row.get('is_primary_esn'),
                '| is_active=', row.get('is_active'),
                '| source_region_count=', row.get('source_region_count'),
            )
