"""Foundation parser adapter for TIL profile extraction.

Calls the GE Foundation PDF extraction service (HTTP), which returns structured
JSON with per-page text, tables, and image descriptions.  Mirrors the logic in
SDG_Scoping_Feedback_Loop/code_assets/experiments/step6/run_til_profile_extraction_pilot.py
(call_foundation_service + parse_foundation_response).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import requests
import urllib3

from contracts.types.entities import DocumentReference, ExtractedProfile

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class FoundationParser:
    name = "foundation"
    version = "v0"

    def __init__(
        self,
        url: str | None = None,
        project_id: str | None = None,
        process_mode: str = "accuracy",
        mode: str = "asynchronous",
        max_text_chars: int = 40000,
        verify_ssl: bool = False,
    ) -> None:
        self.url = url or os.getenv(
            "TIL_FOUNDATION_URL",
            "https://dev-genai-foundation.apps.gevernova.net/pdf/extract/",
        )
        self.project_id = project_id or os.getenv(
            "TIL_FOUNDATION_PROJECT_ID",
            "9f3cbb78-48a9-45cc-a1f2-52c6d02b58a3",
        )
        self.process_mode = process_mode
        self.mode = mode
        self.max_text_chars = max_text_chars
        self.verify_ssl = verify_ssl

    # ── Public interface ──────────────────────────────────────────────────────

    def parse(self, document: DocumentReference, payload: bytes) -> ExtractedProfile:
        filename = Path(document.source_path).name or f"{document.document_id}.pdf"
        raw_response = self._call_service(payload, filename)
        text, tables = self._parse_response(raw_response)
        text = text[: self.max_text_chars]
        return ExtractedProfile(
            document_id=document.document_id,
            fields={
                "raw_text":           text,
                "raw_tables":         tables,
                "extraction_method":  self.name,
                "table_count":        len(tables),
                "char_count":         len(text),
            },
            elements=[
                {"element_type": "table", "element_text": json.dumps(t, default=str)}
                for t in tables
            ],
            parser_name=self.name,
            parser_version=self.version,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _call_service(self, pdf_bytes: bytes, filename: str) -> dict[str, Any]:
        resp = requests.post(
            self.url,
            headers={
                "accept":       "application/json",
                "project-id":   self.project_id,
            },
            files={"file": (filename, pdf_bytes, "application/pdf")},
            data={
                "mode":          self.mode,
                "process_mode":  self.process_mode,
                "part_number":   "",
                "model_name":    "string",
            },
            verify=self.verify_ssl,
            timeout=300,
            proxies={"http": "", "https": ""},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Foundation service returned {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()

    def _parse_response(self, raw: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        """Flatten per-page text, tables, and image descriptions from Foundation JSON."""
        text_pages: list[str] = []
        tables_found: list[dict[str, Any]] = []
        results = raw.get("results", {})

        for page_key in sorted(results.keys(), key=lambda k: int(k)):
            page_num = int(page_key)
            page_items = results[page_key]
            page_text = ""
            page_tables_raw: list[dict[str, str]] = []
            page_images: list[str] = []

            for item in page_items:
                item_type = item.get("type", "")
                if item_type == "text":
                    for content in item.get("content", []):
                        cleaned = (content or "").strip()
                        if cleaned:
                            text_pages.append(cleaned)
                            page_text += cleaned + "\n"
                elif item_type == "table":
                    for content in item.get("content", []):
                        cleaned = (content or "").strip()
                        if cleaned and cleaned != "Extracted Tables:":
                            page_tables_raw.append(
                                {
                                    "source":  (item.get("source") or "textract").strip(),
                                    "content": cleaned,
                                }
                            )
                elif item_type == "image":
                    for content in item.get("content", []):
                        cleaned = (content or "").strip()
                        if cleaned:
                            page_images.append(cleaned)

            # Label tables using the Table N: description from the page text.
            label_match = re.search(r"(Table \d+):\s*(.+)", page_text)
            if label_match and page_tables_raw:
                for entry in page_tables_raw:
                    tables_found.append(
                        {
                            "page":        page_num,
                            "label":       label_match.group(1),
                            "description": label_match.group(2).strip(),
                            "source":      entry["source"],
                            "content":     entry["content"],
                        }
                    )
            elif page_tables_raw:
                for entry in page_tables_raw:
                    text_pages.append(
                        f"[Unlabeled table from page {page_num}]\n{entry['content']}"
                    )

            for img_text in page_images:
                text_pages.append(f"[Image description from page {page_num}]\n{img_text}")

        return "\n\n".join(text_pages), tables_found

