"""Databricks native ai_parse_document parser adapter for TIL profile extraction.

Uses the built-in Databricks ai_parse_document() function for PDF parsing.
Returns structured JSON with pages, elements, text, tables, and metadata.
"""
from __future__ import annotations

import json
import time
from typing import Any

from contracts.types.entities import DocumentReference, ExtractedProfile


class DatabricksAIParser:
    name = "databricks_ai"
    version = "v1"

    def __init__(self, max_text_chars: int = 40000) -> None:
        self.max_text_chars = max_text_chars

    # ── Public interface ──────────────────────────────────────────────────────

    def parse(self, document: DocumentReference, payload: bytes) -> ExtractedProfile:
        """Parse PDF using Databricks ai_parse_document (Spark-based, requires DBR)."""
        start_time = time.time()
        try:
            # Import here to avoid hard dependency outside Databricks
            from pyspark.sql import SparkSession
            from pyspark.sql.functions import expr
            
            spark = SparkSession.getActiveSession()
            if spark is None:
                raise RuntimeError("No active SparkSession. databricks_ai parser requires Databricks environment.")
            
            # Create temp table from binary
            docs_df = spark.createDataFrame(
                [(payload,)],
                ["content"]
            )
            
            # Call ai_parse_document with version 2.0
            parsed_df = docs_df.withColumn(
                "parsed_content",
                expr("ai_parse_document(content, map('version', '2.0'))")
            )
            
            # Convert VARIANT to JSON
            parsed_json = parsed_df.select(
                expr("to_json(parsed_content) as parsed_json")
            ).first()["parsed_json"]
            
            parsed_obj = json.loads(parsed_json) if parsed_json else {}
            
            latency_s = time.time() - start_time
            
            # Extract text and tables
            text, tables = self._extract_content(parsed_obj)
            raw_elements = self._extract_raw_elements(parsed_obj)
            text = text[: self.max_text_chars]
            
            return ExtractedProfile(
                document_id=document.document_id,
                fields={
                    "raw_text":           text,
                    "raw_tables":         tables,
                    "raw_elements":       raw_elements,
                    "raw_element_count":  len(raw_elements),
                    "extraction_method":  self.name,
                    "table_count":        len(tables),
                    "char_count":         len(text),
                    "latency_s":          latency_s,
                },
                elements=[
                    {"element_type": "table", "element_text": json.dumps(t, default=str)}
                    for t in tables
                ],
                parser_name=self.name,
                parser_version=self.version,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Databricks ai_parse_document failed: {exc}. "
                "Ensure you are running in Databricks and have appropriate permissions."
            ) from exc

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _extract_content(self, parsed_obj: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        """Extract text and tables from parsed ai_parse_document output.
        
        Schema:
        {
            "metadata": {...},
            "document": {
                "pages": [...],
                "elements": [
                    {"content": "...", "type": "text|table|...", "bbox": [...]},
                    ...
                ]
            }
        }
        """
        text_parts = []
        tables = []
        
        elements = parsed_obj.get("document", {}).get("elements", [])
        
        for el in elements:
            el_type = el.get("type", "").lower()
            content = (el.get("content") or "").strip()
            
            if not content:
                continue
            
            if el_type == "table":
                # Tables from ai_parse_document come as HTML markup.
                # Store the raw content along with metadata.
                table_obj = {
                    "type": "table",
                    "content": content,
                    "confidence": el.get("confidence"),
                    "bbox": el.get("bbox"),
                }
                tables.append(table_obj)
            else:
                # text, heading, footer, etc.
                text_parts.append(content)
        
        full_text = "\n".join(text_parts)
        return full_text, tables

    def _extract_raw_elements(self, parsed_obj: dict[str, Any], max_elements: int = 400) -> list[dict[str, Any]]:
        """Capture parser element-level richness without enforcing a brittle structure.

        Keeps the native element type/content/bbox/confidence payload so downstream
        code can decide what to use. This is intentionally lightweight
        canonicalization (shape only), not semantic rewriting.
        """
        elements = parsed_obj.get("document", {}).get("elements", [])
        out: list[dict[str, Any]] = []

        for el in elements:
            if len(out) >= max_elements:
                break
            if not isinstance(el, dict):
                continue

            content = (el.get("content") or "")
            content = content.strip() if isinstance(content, str) else ""
            if not content:
                continue

            out.append(
                {
                    "type": (el.get("type") or "").lower(),
                    "content": content,
                    "confidence": el.get("confidence"),
                    "bbox": el.get("bbox"),
                }
            )

        return out
