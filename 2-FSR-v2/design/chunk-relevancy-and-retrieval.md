# Chunk Relevancy & Equipment-Type Filtering

## Problem Statement (from Abhinaya)

**Scenario**: Field Service Reports (FSRs) contain information about multiple equipment types (generators, gas turbines, steam turbines, etc.). When retrieving chunks for analysis of a specific equipment type, we need to:

1. ✅ **Ensure all ESNs in the document are retrievable** (solved by v2 design — multiple ESNs per chunk)
2. ✅ **BUT filter to only chunks relevant to that equipment type** (current ask)

**Example**:
- Document contains: Generator ESN + Gas Turbine ESN + Steam Turbine ESN
- Query: "Show me all chunks about the Generator"
- Current result: All 20 chunks from the document (not filtered)
- **Desired result**: Only chunks tagged with equipment_type = "generator"

---

## Available Columns for Retrieval

The `fsr_chunks_v2` table provides these columns for filtering:

| Column | Type | Purpose | Example |
|--------|------|---------|---------|
| **document_id** | string | Unique document identifier | `"doc_20250721_001"` |
| **primary_esn** | string | Primary ESN assigned to this chunk | `"GEN-298250"` |
| **primary_equip_type** | string | Equipment type of primary_esn | `"generator"` or `"gas_turbine"` |
| **active_esns** | string | Pipe-delimited ESNs in this chunk | `"GEN-298250\|GT-338X447\|ST-500"` |
| **chunk_text** | string | The actual chunk content | (full text) |
| **chunk_embedding** | array[float] | Vector embedding for semantic search | (1536-dim vector) |
| **page_number** | int | Source page in PDF | `3` |
| **report_date** | date | Document date | `2025-07-15` |

---

## Column Definitions

### `primary_esn`
- **What it is**: The single ESN responsible for this chunk's region attribution
- **How it's set**: Based on best-overlap matching between chunk boundaries and preprocessor regions
- **Example flow**:
  1. P1 extracts regions from PDF text (e.g., "Generator Section: ESN 298250")
  2. P2 chunks text and matches chunk boundaries to regions
  3. Chunk gets tagged: `primary_esn = "GEN-298250"`
- **Precision**: One ESN per chunk (deterministic)

### `primary_equip_type`
- **What it is**: The equipment category (equipment type) of the `primary_esn`
- **How it's set**: Derived from the primary_esn's metadata (stored in preprocessor regions)
- **Example values**: `"generator"`, `"gas_turbine"`, `"steam_turbine"`, `"cooling_system"`
- **Precision**: One type per chunk (matches primary_esn)

### `active_esns`
- **What it is**: All ESNs mentioned anywhere in this chunk's text
- **Format**: Pipe-delimited, normalized, sorted string (e.g., `"GEN-298250|GT-338X447|ST-500"`)
- **How it's set**: Extracted from all preprocessor regions that overlap the chunk
- **Precision**: Broader scope than primary_esn (can contain multiple ESNs)

### `chunk_text`
- **What it is**: The actual chunk content (trimmed text segment from PDF)
- **Used for**: Reading the chunk, semantic search, exact text matching

---

## Retrieval Patterns for Equipment-Type Filtering

### **Pattern 1: Filter by equipment type (Primary ESN)**
Query chunks where the *primary* equipment is of a specific type:

```sql
SELECT 
    document_id, 
    chunk_id, 
    primary_esn, 
    primary_equip_type,
    chunk_text
FROM fsr_chunks_v2
WHERE 
    document_id = 'doc_20250721_001'
    AND LOWER(primary_equip_type) = LOWER('generator')
ORDER BY chunk_index;
```

**Use case**: 
- Vernova app (generator-focused) → filter to `primary_equip_type = 'generator'`
- GT7 app (gas turbine-focused) → filter to `primary_equip_type = 'gas_turbine'`

---

### **Pattern 2: Filter by specific ESN (and fetch primary_equip_type)**
Query chunks by a specific ESN to confirm its equipment type:

```sql
SELECT 
    document_id, 
    chunk_id, 
    primary_esn, 
    primary_equip_type,
    chunk_text
FROM fsr_chunks_v2
WHERE 
    document_id = 'doc_20250721_001'
    AND primary_esn = 'GEN-298250'
ORDER BY chunk_index;
```

**Use case**: 
- App has specific ESN → retrieve only chunks attributed to that ESN
- Verify equipment_type matches expected type

---

### **Pattern 3: Broad search (ESN appears anywhere in chunk)**
Query chunks where an ESN is mentioned (even if not primary):

```sql
SELECT 
    document_id, 
    chunk_id, 
    primary_esn, 
    primary_equip_type,
    active_esns,
    chunk_text
FROM fsr_chunks_v2
WHERE 
    document_id = 'doc_20250721_001'
    AND active_esns LIKE '%GEN-298250%'
ORDER BY chunk_index;
```

**Use case**: 
- Discover all mentions of a specific ESN (even if it's not the primary attribution)
- Useful for cross-reference analysis

---

### **Pattern 4: Hybrid (Equipment type + semantic search with embedding)**
Filter by equipment type, then rank by semantic relevance:

```sql
WITH filtered_chunks AS (
  SELECT 
      chunk_id,
      chunk_text,
      chunk_embedding,
      primary_equip_type
  FROM fsr_chunks_v2
  WHERE 
      document_id = 'doc_20250721_001'
      AND LOWER(primary_equip_type) = LOWER('generator')
)
SELECT 
    chunk_id,
    chunk_text,
    cosine_similarity(chunk_embedding, query_embedding) AS relevance_score
FROM filtered_chunks
ORDER BY relevance_score DESC
LIMIT 10;
```

**Use case**: 
- First filter to equipment type (reduces noise)
- Then rank by semantic similarity to query
- More precise results than semantic search alone

---

## Data Quality Considerations

### When `primary_esn` might be empty
- Chunk falls in unmapped region (no preprocessor region overlay)
- Document is upload-only with no P1 preprocessing
- Region attribution disabled in configuration

**Fallback**: Use `active_esns` or examine `chunk_text` manually

### When `primary_equip_type` might be empty or incorrect
- Missing metadata in preprocessor regions
- ESN not recognized during preprocessing
- Cross-equipment-type documentation (rare)

**Mitigation**: 
- Always include chunk_text in results for manual verification
- Log warnings during chunk generation if type is missing
- Consider doc-level fallback: check document metadata for equipment type hint

### `active_esns` mismatch scenarios
- Multiple ESNs in same sentence → chunk gets multiple entries
- ESN mentioned without context → still tagged (conservative approach)

**This is intentional**: Ensures no relevant mentions are lost

---

## Recommended Query Template for Abhinaya

```python
def get_chunks_by_equipment_type(document_id: str, equipment_type: str) -> list[dict]:
    """
    Retrieve chunks by equipment type from a specific document.
    
    Args:
        document_id: FSR document ID (e.g., "doc_20250721_001")
        equipment_type: Equipment type filter (e.g., "generator", "gas_turbine")
    
    Returns:
        List of chunks with text and metadata, sorted by page/chunk order
    """
    query = f"""
    SELECT 
        document_id,
        chunk_id,
        chunk_index,
        primary_esn,
        primary_equip_type,
        page_number,
        chunk_text,
        report_date
    FROM fsr_chunks_v2
    WHERE 
        document_id = '{document_id}'
        AND LOWER(primary_equip_type) = LOWER('{equipment_type}')
    ORDER BY page_number, chunk_index;
    """
    return spark.sql(query).collect()
```

---

## Next Steps for Implementation

1. **Validate with Abhinaya**:
   - Does `primary_equip_type` match the filtering criteria?
   - Are there additional equipment types beyond generator/gas_turbine/steam_turbine?
   - Should fuzzy matching be used (e.g., "gen" vs "generator")?

2. **Test coverage**:
   - Retrieve chunks from sample FSR with multiple equipment types
   - Verify `primary_esn` and `primary_equip_type` alignment
   - Check for missing/empty values and document frequency

3. **App integration**:
   - Vernova app: Filter by `primary_equip_type = 'generator'`
   - GT7 app: Filter by `primary_equip_type = 'gas_turbine'`
   - Consider UI option to also show `active_esns` for context

4. **Performance**:
   - Index on `(document_id, primary_equip_type)` if not already present
   - Test latency with large documents (1000+ chunks)


Summary:

 I checked the chunk relevancy question you asked in the morning. So in v2, each chunk gets two key tags: primary_esn (the single ESN whose section this chunk belongs to, based on which equipment region has the most overlap with the chunk boundaries) and primary_equip_type (the equipment type of that ESN for that chunk boundary, e.g., generator, gas turbine). Two retrieval scenarios this supports:

Search by equipment type — filter chunks directly by document_id + primary_equip_type, no ESN needed
Search by ESN — look up the ESN's equipment type from fsr_document_equipment_map_v2 (maps ESN → equip type per document), then filter chunks by document_id + primary_equip_type
Both give you only the chunks from that equipment's sections, not unrelated ones from the same doc. Let me know if that matches what you had in mind or if there's a specific case you want to test!