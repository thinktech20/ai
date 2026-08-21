import csv
from collections import Counter

CHUNK_FILE = '/home/u560060992/dbx/2-FSR-v2/data/table-data/fsr_chunks_v2.csv'

# Unique document_ids and their pdf_names in chunks table
doc_pdfs = {}
esn_counter = Counter()
total = 0

with open(CHUNK_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
        total += 1
        doc_id = (row.get('document_id') or '').strip()
        pdf_name = (row.get('pdf_name') or '').strip()
        region_esn = (row.get('region_primary_esn') or '').strip()
        if doc_id not in doc_pdfs:
            doc_pdfs[doc_id] = pdf_name
        esn_counter[region_esn or '(empty)'] += 1

print(f'Total chunk rows: {total}')
print(f'Unique document_ids: {len(doc_pdfs)}')
print()
print('region_primary_esn distribution:')
for esn, cnt in esn_counter.most_common(20):
    print(f'  {esn}: {cnt}')
print()
print('Sample document_ids (first 10):')
for doc_id, pdf in list(doc_pdfs.items())[:10]:
    print(f'  {doc_id!r:50s} -> {pdf}')
