# FSR v2 Metadata Levels

## Summary

Metadata in FSR v2 is derived and applied at different levels:

- doc-level: One value per document_id. Stored on the document row and reused by downstream steps unless overridden.
- region-level: One value per text region span (start/end) inside preprocessor_regions. Used for ESN/equipment attribution by position.
- chunk-level: Metadata extracted from chunk content itself (semantic/content-derived, per chunk).

## 1. Definitions

- doc-level: One value per document_id. Stored on the document row and reused by downstream steps unless overridden.
- region-level: One value per text region span (start/end) inside preprocessor_regions. Used for ESN/equipment attribution by position.
- chunk-level: Metadata extracted from chunk content itself (semantic/content-derived, per chunk).

Notes:
- fsr_metadata_v2.primary_esn is doc-level because it is written once per document row (MERGE keyed by document_id).
- fsr_chunks_v2.primary_esn is stored per chunk row, but is currently attribution-derived (from doc/region), not chunk-content-extracted metadata.
- fsr_document_equipment_map_v2 is a serving/helper table at (document_id, esn) granularity; most values are region-derived, with a doc-derived flag (is_primary_esn).
- Current v2 does not have a separate business metadata object that is extracted from chunk text itself. The `metadata.chunk_context` block is technical trace context.
- Rule used in this document: every table column is assigned exactly one metadata level. Exception: JSON subfields inside `fsr_chunks_v2.metadata`, where doc/region/chunk can coexist by field path.
- `Current implementation level` describes what the code writes today. `Proposed level` is the intended steady-state classification.

Current implementation labels used in this document:
- `mixed (doc/region)`: the stored column is populated through a fallback/override flow where a doc-level default is assigned first, and a region-level value may override it later. The final stored value can therefore come from either level depending on attribution success.
- `mixed (doc/chunk)`: the JSON column currently contains subfields from more than one level. In the current implementation of `fsr_chunks_v2.metadata`, the `doc` block is doc-level and `chunk_context` is chunk-level.

Stage legend used below:
- P1-S1: document discovery / input load
- P1-S2: PDF parsing
- P1-S3: preprocessor region + equipment inference
- P1-S4: metadata enrichment + MERGE into `fsr_metadata_v2`
- P1-S5: document equipment map materialization
- P2-S5: chunk creation + region attribution + chunk metadata assembly
- P2-S6: embedding + write to `fsr_chunks_v2`

## 2. Column Mapping (excluding audit columns)

Table_name|column_name|current implementation level|proposed level|current derivation stage / step
---|---|---|---|---
fsr_metadata_v2|document_id|doc-level|doc-level|P1-S1 input load assigns document identifier
fsr_metadata_v2|pdf_name|doc-level|doc-level|P1-S4 enrichment writes parsed filename
fsr_metadata_v2|volume_path|doc-level|doc-level|P1-S1 input load discovers source path
fsr_metadata_v2|title|doc-level|doc-level|P1-S4 enrichment from preprocessor/LLM merged metadata
fsr_metadata_v2|customer|doc-level|doc-level|P1-S4 enrichment from LLM metadata
fsr_metadata_v2|primary_esn|doc-level|doc-level|P1-S3 preprocessor infers primary equipment anchor; P1-S4 writes row
fsr_metadata_v2|primary_equip_type|doc-level|doc-level|P1-S3 preprocessor infers primary equipment type; P1-S4 writes row
fsr_metadata_v2|gt_esn|doc-level|doc-level|P1-S3 preprocessor extracts GT anchor ESN
fsr_metadata_v2|gen_esn|doc-level|doc-level|P1-S3 preprocessor extracts Generator anchor ESN
fsr_metadata_v2|primary_equip_sys_id|doc-level|doc-level|P1-S4 IBAT enrichment lookup using primary_esn
fsr_metadata_v2|primary_equip_class_code|doc-level|doc-level|P1-S4 IBAT enrichment lookup using primary_esn
fsr_metadata_v2|event_type|doc-level|doc-level|P1-S4 LLM extraction with EV fallback
fsr_metadata_v2|ev_project_id|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|ev_equipment_event_id|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|ofs_event_id|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|fsp_project_id|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|xxx_project_id|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|fsr_number|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|report_issued_date|doc-level|doc-level|P1-S3 preprocessor hint / extraction, finalized in P1-S4
fsr_metadata_v2|outage_start_date|doc-level|doc-level|P1-S3 title-page extraction with P1-S4 EV fallback
fsr_metadata_v2|outage_end_date|doc-level|doc-level|P1-S3 title-page extraction with P1-S4 EV fallback
fsr_metadata_v2|outage_type|doc-level|doc-level|P1-S4 PSOT enrichment
fsr_metadata_v2|technology_type|doc-level|doc-level|P1-S4 PSOT enrichment
fsr_metadata_v2|prepared_by|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|approved_by|doc-level|doc-level|P1-S4 LLM extraction
fsr_metadata_v2|document_summary|doc-level|doc-level|P1-S4 LLM extraction/summary
fsr_metadata_v2|page_count|doc-level|doc-level|P1-S2 parsing counts pages
fsr_metadata_v2|file_size_bytes|doc-level|doc-level|P1-S1 input load from volume listing
fsr_metadata_v2|file_last_modified|doc-level|doc-level|P1-S1 input load from volume listing
fsr_metadata_v2|preprocessor_regions|region-level|region-level|P1-S3 preprocessor emits start/end regions with metadata
fsr_metadata_v2|inactive_esns|doc-level|doc-level|P1-S3 preprocessor emits inactive ESN list; P1-S4 serializes
fsr_metadata_v2|extractor_method|doc-level|doc-level|P1-S4 pipeline run metadata
fsr_metadata_v2|preprocess_method|doc-level|doc-level|P1-S4 pipeline run metadata
fsr_metadata_v2|llm_model_extraction|doc-level|doc-level|P1-S4 pipeline run metadata
fsr_metadata_v2|llm_extraction_prompt_version|doc-level|doc-level|P1-S4 pipeline run metadata
fsr_metadata_v2|pipeline_version|doc-level|doc-level|P1-S4 pipeline run metadata
fsr_metadata_v2|run_id|doc-level|doc-level|P1-S4 pipeline run metadata
fsr_chunks_v2|chunk_id|chunk-level|chunk-level|P2-S6 generated from document_id + chunk_index during write
fsr_chunks_v2|chunk_index|chunk-level|chunk-level|P2-S5 chunk creation order
fsr_chunks_v2|document_id|doc-level|doc-level|P2-S5 carried from source metadata row
fsr_chunks_v2|pdf_name|doc-level|doc-level|P2-S5 carried from source metadata row
fsr_chunks_v2|page_number|chunk-level|chunk-level|P2-S5 char-offset to page mapping
fsr_chunks_v2|chunk_text|chunk-level|chunk-level|P2-S5 chunk splitter output
fsr_chunks_v2|primary_esn|mixed (doc/region)|region-level|P2-S5 starts with doc-level default, then region attribution may override
fsr_chunks_v2|primary_equip_type|mixed (doc/region)|region-level|P2-S5 starts with doc-level default, then region attribution may override
fsr_chunks_v2|active_esns|doc-level|doc-level|P2-S5 built from document regions + inactive_esns
fsr_chunks_v2|report_date|doc-level|doc-level|P2-S5 parsed from metadata_table report_issued_date
fsr_chunks_v2|chunk_embedding|chunk-level|chunk-level|P2-S6 embedding call on chunk_text
fsr_chunks_v2|chunk_strategy|doc-level|doc-level|P2-S5 pipeline/chunker configuration recorded per chunk row
fsr_chunks_v2|embedding_model|doc-level|doc-level|P2-S6 pipeline configuration recorded per chunk row
fsr_chunks_v2|merge_strategy|doc-level|doc-level|P2-S5 pipeline configuration recorded per chunk row
fsr_chunks_v2|region_attribution_method|doc-level|doc-level|P2-S5 pipeline configuration recorded per chunk row
fsr_chunks_v2|embedding_dimension|doc-level|doc-level|P2-S6 embedding result metadata recorded per chunk row
fsr_chunks_v2|pipeline_version|doc-level|doc-level|P2-S6 pipeline run metadata
fsr_chunks_v2|run_id|doc-level|doc-level|P2-S6 pipeline run metadata
fsr_chunks_v2|metadata|mixed (doc/chunk)|mixed (doc/region/chunk)|P2-S5 assembles JSON from doc fields plus chunk_context
fsr_document_equipment_map_v2|document_id|doc-level|doc-level|P1-S5 carried from completed metadata row before region explode
fsr_document_equipment_map_v2|esn|region-level|region-level|P1-S5 exploded from preprocessor_regions metadata.primary_esn
fsr_document_equipment_map_v2|equip_type|region-level|region-level|P1-S5 exploded from preprocessor_regions metadata.primary_equip_type
fsr_document_equipment_map_v2|technology_code|region-level|region-level|P1-S5 exploded from preprocessor_regions metadata.primary_technology_code
fsr_document_equipment_map_v2|is_primary_esn|region-level|remove|P1-S5 compares exploded esn with document primary_esn
fsr_document_equipment_map_v2|is_active|region-level|remove|P1-S5 compares exploded esn with inactive_esns list
fsr_document_equipment_map_v2|source_region_count|region-level|region-level|P1-S5 counts contributing exploded regions per document_id + esn

## 3. JSON Column Internal Field Levels

Note:
- `nb_sdg_fsr_v2_ddl.py` defines these columns as STRING and imports contracts from `common/fsr_v2/config.py`.
- Internal JSON keys below are from the runtime JSON contracts and writer logic.

Table_name|json_column|json_field_path|current implementation level|proposed level|current derivation stage / step
---|---|---|---|---|---
fsr_metadata_v2|preprocessor_regions|[]|region-level|region-level|P1-S3 preprocessor emits region array
fsr_metadata_v2|preprocessor_regions|[].start|region-level|region-level|P1-S3 preprocessor computes char-offset region start
fsr_metadata_v2|preprocessor_regions|[].end|region-level|region-level|P1-S3 preprocessor computes char-offset region end
fsr_metadata_v2|preprocessor_regions|[].metadata.primary_esn|region-level|region-level|P1-S3 preprocessor assigns ESN per region
fsr_metadata_v2|preprocessor_regions|[].metadata.primary_equip_type|region-level|region-level|P1-S3 preprocessor assigns equipment type per region
fsr_metadata_v2|preprocessor_regions|[].metadata.primary_technology_code|region-level|region-level|P1-S3 preprocessor assigns technology code when available
fsr_chunks_v2|metadata|metadata_contract_version|chunk-level|chunk-level|P2-S5 chunk metadata assembly writes contract marker
fsr_chunks_v2|metadata|doc|doc-level|doc-level|P2-S5 chunk metadata assembly copies doc context block
fsr_chunks_v2|metadata|doc.title|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.customer|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.event_type|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.ev_project_id|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.ev_equipment_event_id|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.ofs_event_id|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.fsp_project_id|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.xxx_project_id|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.fsr_number|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.report_issued_date|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.outage_start_date|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.outage_end_date|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.outage_type|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.technology_type|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|doc.inactive_esns|doc-level|doc-level|P2-S5 copied from metadata_table row
fsr_chunks_v2|metadata|region|not present|region-level|Not written in current implementation
fsr_chunks_v2|metadata|region.primary_esn|not present|region-level|Not written in current implementation
fsr_chunks_v2|metadata|region.primary_equip_type|not present|region-level|Not written in current implementation
fsr_chunks_v2|metadata|region.primary_technology_code|not present|region-level|Not written in current implementation
fsr_chunks_v2|metadata|chunk_context|chunk-level|chunk-level|P2-S5 chunk metadata assembly writes technical chunk context
fsr_chunks_v2|metadata|chunk_context.chunk_start_char|chunk-level|chunk-level|P2-S5 chunk metadata assembly records chunk start char

