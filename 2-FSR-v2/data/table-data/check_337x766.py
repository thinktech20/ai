import csv, json

BASE = '/home/u560060992/dbx/2-FSR-v2/data/table-data'
META_FILE = BASE + '/fsr_metadata_v2.csv'
MAP_FILE  = BASE + '/fsr_document_equipment_map_v2.csv'

# 1. All docs where 337X766 appears anywhere in ESN fields
print('=== ALL 337X766 DOCS IN METADATA TABLE ===')
found_ids = []
with open(META_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        esn_fields = [
            (row.get('primary_esn') or '').upper(),
            (row.get('gt_esn') or '').upper(),
            (row.get('gen_esn') or '').upper(),
        ]
        if '337X766' in esn_fields:
            doc_id = (row.get('document_id') or '').strip()
            found_ids.append(doc_id)
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
                    # Count regions per ESN
                    from collections import Counter
                    esn_counts = Counter(
                        r.get('metadata', {}).get('primary_esn', '')
                        for r in regions
                        if r.get('metadata', {}).get('primary_esn')
                    )
                    print('regions_by_esn    :', dict(esn_counts))
                except Exception as e:
                    print('regions_parse_err :', e)

print()
print(f'Total 337X766 docs: {len(found_ids)}')

# 2. Xujin's 4 specific docs - confirm which are MISSING
TARGET_XUJIN_4 = {
    '9e279e5a-a24e-4ebd-a79e-5aa24efebd04': 'Field_Service_Report_ProjectID_A-1359354_FSP-268167_C-10332393.pdf',
    'af693a98-1e5c-499d-aa10-cccc54885c64': 'Field_Service_Report_ProjectID_A-1693690_EV-106469_C-10373177_EVP-502842.pdf',
    '796f4d53-a8ad-42e1-af4d-53a8add2e1a4': 'Field_Service_Report_ProjectID_A-1427112_FSP-268159_C-10332610.pdf',
    '806975e9-062b-4da3-9ae7-5881a5daffd1_204049598-39387-297652-final_master_report': 'Generator_Hydrogen_Leak...297652',
}

print()
print('=== XUJIN DOC STATUS ===')
all_meta_ids = set()
with open(META_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        all_meta_ids.add((row.get('document_id') or '').strip())

for doc_id, fname in TARGET_XUJIN_4.items():
    status = 'FOUND' if doc_id in all_meta_ids else 'MISSING - not ingested'
    print(f'{doc_id[:36]}  {status}  ({fname[:60]})')

# 3. Also check doc equipment map for 337X766 coverage
print()
print('=== EQUIPMENT MAP: all 337X766 entries ===')
with open(MAP_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if (row.get('esn') or '').upper() == '337X766':
            print(
                row.get('document_id'), '|',
                'is_primary=', row.get('is_primary_esn'), '|',
                'is_active=', row.get('is_active'), '|',
                'equip_type=', row.get('equip_type'), '|',
                'source_region_count=', row.get('source_region_count'),
            )
