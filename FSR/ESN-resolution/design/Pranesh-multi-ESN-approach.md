VOLUME
  │
  │  mod_time > watermark
  ▼
┌─────────────────────────────────────┐
│  PHASE 1 — DISCOVERY                │
│  Insert NEW stub rows only          │
│  meta_status  = pending             │
│  chunk_status = pending             │
└──────────────┬──────────────────────┘
               │
               │  meta_status IN ('pending','failed')
               │  AND doc_id NOT LIKE '%\_%'
               │  
               ▼
┌─────────────────────────────────────┐
│  PHASE 2 — EXTRACTION + EXPANSION   │
│                                     │
│  Error / 0 ESNs:                    │
│    └─ meta_status = 'failed'        │
│       retry_count += 1              │
│       (bare doc_id stays, retried   │
│        next scheduled run)          │
│                                     │
│  ≥1 ESN found:                      │
│    └─ UPDATE stub → doc_id_<esn0>   │
│    └─ INSERT rows for esn1..esnN    │
│       meta_status = 'completed'     │
│       chunk_status = 'pending'      │
└──────────────┬──────────────────────┘
               │
               │  meta_status = 'completed'
               │  AND chunk_status IN ('pending','failed')
               │  AND doc_id LIKE '%\_%'
               │  AND retry_count < MAX
               ▼
┌─────────────────────────────────────┐
│  PHASE 3 — CHUNKING + ESN COPY      │
│                                     │
│  Error on chunk/embed:              │
│    └─ chunk_status = 'failed'       │
│       retry_count += 1              │
│       delete partial chunks         │
│       (retried next scheduled run)  │
│                                     │
│  Success:                           │
│    └─ First ESN → chunk + embed     │
│         chunk_id = <uuid>_<esn0>    │
│    └─ Other ESNs → batch copy       │
│         chunk_id = <uuid>_<esnN>    │
│       chunk_status = 'completed'    │
└─────────────────────────────────────┘