"""TIL Profile LLM Extraction

Handles LLM-based structured field extraction for TIL profiles.
Uses the comprehensive prompt template from DS team's experimentation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Default to the latest DS-aligned extraction prompt.
_PROMPT_FILE = Path(__file__).parent / "prompts" / "til_profile_extraction_v3.txt"
SYSTEM_PROMPT = _PROMPT_FILE.read_text(encoding="utf-8")

def build_user_prompt(pdf_text: str, labeled_tables: list[dict[str, Any]]) -> str:
    """Build the user prompt for LLM extraction.
    
    Args:
        pdf_text: Full extracted document text
        labeled_tables: List of table objects with labels and content
        
    Returns:
        Formatted user prompt for LLM
    """
    return "\n".join(
      [
        "## Extracted TIL Structured Inputs",
        "```json",
        json.dumps(
          {
            "labeled_tables": labeled_tables,
          },
          indent=2,
          default=str,
        ),
        "```",
        "",
        "## Extracted TIL Document Text",
        pdf_text,
        "",
        "Return the structured JSON profile only.",
      ]
    )


def extract_json_from_llm_response(raw_response: str) -> dict[str, Any] | None:
    """Extract JSON object from LLM response (handles markdown fences, etc).
    
    Args:
        raw_response: Raw text response from LLM
        
    Returns:
        Parsed JSON object, or None if parsing failed
    """
    if not raw_response:
        return None
    
    text = raw_response.strip()
    
    # Remove markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (```json or just ```)
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        # Remove closing fence
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()
    
    # Try to find JSON object in the response
    # Look for { ... } pattern
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
    
    # Try parsing the whole text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def clean_text(value: Any) -> str:
    """Clean and normalize text values.
    
    Removes extra whitespace, handles None values, etc.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    
    # Remove extra whitespace
    value = re.sub(r"\s+", " ", value)
    return value.strip()
