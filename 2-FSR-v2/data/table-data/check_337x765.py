import csv, json
from collections import Counter

BASE = '/home/u560060992/dbx/2-FSR-v2/data/table-data'
META_FILE = BASE + '/fsr_metadata_v2.csv'
MAP_FILE  = BASE + '/fsr_document_equipment_map_v2.csv'

# Xujin's 2 priority docs + 3 "other" docs for 337X765
TARGET_DOCS = {
    'b775cf29-8b42-4a83-af21-53075fef0802': 'Field_Service_Report_ProjectID_A-1693688_EV-106468_C-10372681_EVP-502841.pdf (337X765 primary)',
    'cc9fe3d7-87cc-4687-9fe3-d787cc3687b3': 'Field_Service_Report_ProjectID_A-1359396_FSP-268164_C-10332385.pdf (297651)',
    'af693a98-1e5c-499d-aa10-cccc54885c64': 'other doc 1',
    'd9b6c08b-d098-4939-a549-d113964e3150': 'other doc 2 (tagged 337X765 but empty)',
    'bddc3379-f29f-4665-9c33-79f29f1665be': 'other doc 3 (no useful info)',
}

print('=== METADATA TABLE ===')
found_ids = set()
with open(META_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        doc_id = (row.get('document_id') or '').strip()
        if doc_id in TARGET_DOCS:
            found_ids.add(doc_id)
            print()
            print(f'[{TARGET_DOCS[doc_id]}]')
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
                    esn_counts = Counter(
                        r.get('metadata', {}).get('primary_esn', '')
                        for r in regions
                        if r.get('metadata', {}).get('primary_esn')
                    )
                    print('regions_by_esn    :', dict(esn_counts))
                    print('region_count      :', len(regions))
                except Exception as e:
                    print('regions_parse_err :', e)

print()
print('=== MISSING (not in metadata table) ===')
for doc_id, label in TARGET_DOCS.items():
    if doc_id not in found_ids:
        print(f'  MISSING: {doc_id}  ({label})')

print()
print('=== EQUIPMENT MAP: all 337X765 entries ===')
with open(MAP_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        esn = (row.get('esn') or '').upper()
        doc_id = (row.get('document_id') or '').strip()
        if esn == '337X765' or doc_id in TARGET_DOCS:
            print(
                doc_id[:36], '|',
                'esn=', row.get('esn'), '|',
                'is_primary=', row.get('is_primary_esn'), '|',
                'is_active=', row.get('is_active'), '|',
                'equip_type=', row.get('equip_type'), '|',
                'source_region_count=', row.get('source_region_count'),
            )
