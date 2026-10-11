# Databricks notebook source
import json
import re

dbutils.widgets.text("METADATA_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_metadata_v2")
dbutils.widgets.text("CHUNK_TABLE_V2", "vaid.ai_std_con_field_service_report.fsr_chunks_v2")
dbutils.widgets.text("REPAIR_SCOPE_TABLE", "vaid.ai_sot_field_service_report.fsr_v2_repair_scope")
dbutils.widgets.text("REPAIR_RUN_ID", "oct-fsr-75daefa-20261006")
dbutils.widgets.text("UUID_DOCUMENT_ID", "796f4d53-a8ad-42e1-af4d-53a8add2e1a4")

metadata_table = dbutils.widgets.get("METADATA_TABLE_V2").strip()
chunk_table = dbutils.widgets.get("CHUNK_TABLE_V2").strip()
scope_table = dbutils.widgets.get("REPAIR_SCOPE_TABLE").strip()
repair_run_id = dbutils.widgets.get("REPAIR_RUN_ID").strip()
uuid_document_id = dbutils.widgets.get("UUID_DOCUMENT_ID").strip().lower()
for table_name in (metadata_table, chunk_table, scope_table):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError("Expected a fully qualified table name")
if not re.fullmatch(r"[A-Za-z0-9_-]+", repair_run_id):
    raise ValueError("Invalid repair run ID")
if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", uuid_document_id):
    raise ValueError("Expected a UUID document ID")

summary_id = "00f23784-d121-4595-b61d-49d223253a05"
alignment_id = "93c2180b-f866-4521-b090-b88442c6dcf1"
selected_ids = (summary_id, alignment_id, uuid_document_id)
quoted_ids = ",".join("'" + document_id + "'" for document_id in selected_ids)

metadata_rows = [row.asDict(recursive=True) for row in spark.sql(f"""
    SELECT s.document_id AS requested_id, m.document_id, m.metadata_status,
           m.chunk_status, m.updated_at, m.chunked_at, m.gt_esn, m.gen_esn, m.st_esn
    FROM {scope_table} s LEFT JOIN {metadata_table} m ON s.document_id = m.document_id
    WHERE s.run_id = '{repair_run_id}' ORDER BY s.document_id
""").collect()]
chunk_rows = [row.asDict(recursive=True) for row in spark.sql(f"""
    SELECT document_id, chunk_index, page_number, chunk_text, metadata,
           region_primary_equip_type, region_primary_esn, active_esns, created_at
    FROM {chunk_table} WHERE document_id IN ({quoted_ids})
    ORDER BY document_id, chunk_index
""").collect()]
by_document = {document_id: [] for document_id in selected_ids}
for chunk in chunk_rows:
    by_document[chunk["document_id"]].append(chunk)

def evidence(chunk, include_text=True):
    payload = json.loads(chunk["metadata"] or "{}")
    region = payload.get("region") or {}
    section = payload.get("section") or {}
    result = {
        "chunk_index": chunk["chunk_index"],
        "page_number": chunk["page_number"],
        "created_at": chunk["created_at"],
        "equipment_type": chunk["region_primary_equip_type"],
        "region_esn": chunk["region_primary_esn"],
        "section_path": region.get("section_path"),
        "section_fields": section,
        "chunk_context": payload.get("chunk_context"),
    }
    if include_text:
        result["text"] = chunk["chunk_text"][:12000]
        result["text_truncated"] = len(chunk["chunk_text"]) > 12000
    return result

def matching_chunks(document_id, pattern):
    return [evidence(chunk) for chunk in by_document[document_id]
            if re.search(pattern, chunk["chunk_text"], re.IGNORECASE)]

def heading_only(chunk):
    lines = [line.strip() for line in chunk["chunk_text"].splitlines() if line.strip()]
    substantive = [line for line in lines if not re.fullmatch(r"[A-Za-z]|[.#]+|SECTION|CATEGORY|FORM", line, re.IGNORECASE)]
    return not substantive or (
        len(substantive) == 1
        and bool(re.fullmatch(r"(?:#{1,3}\s*)?\d+(?:\.\d+)*[.)]?\s+[^\n]+", substantive[0]))
    )

summary_chunks = by_document[summary_id]
paragraph_pairs = []
for first, second in zip(summary_chunks, summary_chunks[1:]):
    if "provided a new" in first["chunk_text"].lower() and "alignment criteria" in second["chunk_text"].lower():
        first_text, second_text = first["chunk_text"], second["chunk_text"]
        shared_characters = max((
            size for size in range(1, min(len(first_text), len(second_text), 1000) + 1)
            if first_text[-size:] == second_text[:size] and first_text[-size:].strip()
        ), default=0)
        paragraph_pairs.append({
            "first": evidence(first), "second": evidence(second),
            "exact_shared_suffix_prefix_characters": shared_characters,
        })

uuid_chunks = by_document[uuid_document_id]
vertical_rows = []
for chunk in uuid_chunks:
    if chunk["chunk_index"] in (74, 79):
        next_chunk = next((candidate for candidate in uuid_chunks
                           if candidate["chunk_index"] == chunk["chunk_index"] + 1), None)
        record = evidence(chunk, include_text=False)
        record["tail"] = chunk["chunk_text"][-1200:]
        record["next_chunk_head"] = next_chunk["chunk_text"][:600] if next_chunk else None
        vertical_rows.append(record)

result = {
    "checked_at": spark.sql("SELECT current_timestamp() AS stamp").first().stamp,
    "metadata_table": metadata_table,
    "chunk_table": chunk_table,
    "uuid_document_id_provisional": uuid_document_id,
    "metadata": metadata_rows,
    "counts": {document_id: len(chunks) for document_id, chunks in by_document.items()},
    "hood_sprays": matching_chunks(summary_id, r"hood sprays|3\.\s*Components"),
    "executive_summary_split": paragraph_pairs,
    "work_scope": matching_chunks(summary_id, r"Work Scope|Generator\s+Mechanical"),
    "shifted_section_bodies": matching_chunks(alignment_id, r"2\.3 FLOATING|2\.4 INSPECT|2\.5 THRUST|T1 and T2 oil deflector|thrust bearing was disassembled"),
    "heading_only_chunks": {
        document_id: [evidence(chunk) for chunk in by_document[document_id] if heading_only(chunk)]
        for document_id in (summary_id, uuid_document_id)
    },
    "vertical_heading_examples": vertical_rows,
    "subreport_path": matching_chunks(uuid_document_id, r"4\.7\s+1A\s+BFP"),
}
dbutils.notebook.exit(json.dumps(result, default=str))