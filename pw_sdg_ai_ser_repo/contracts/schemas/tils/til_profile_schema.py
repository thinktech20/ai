"""TIL Profile Schema Normalization

Defines the standard TIL profile JSON schema and provides normalization/validation helpers.
Adapted from DS team's normalize_profile_schema pattern.
"""
from __future__ import annotations

import json
from typing import Any


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return None


def normalize_til_profile(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    """Normalize a TIL profile to ensure all expected fields exist with proper defaults.

    This ensures downstream processes don't fail on missing fields. Sets defaults for
    all optional fields, lists, and structured sub-objects.

    Args:
        profile: Raw profile dict from LLM extraction, or None if extraction failed

    Returns:
        Normalized profile with all fields present, or None if input was None
    """
    if profile is None:
        return None

    # Scalar fields with null defaults
    profile.setdefault("til_number", None)
    profile.setdefault("revision", None)
    profile.setdefault("title", None)
    profile.setdefault("publish_date", None)
    profile.setdefault("reason_for_revision", None)
    profile.setdefault("purpose", None)

    # Compliance and categorization
    profile.setdefault("compliance_category_code", None)  # M | C | A | S
    profile.setdefault("compliance_category_text", None)
    profile.setdefault("recurring_indicator_if_found", None)
    profile.setdefault("coarse_outage_type", None)

    profile.setdefault("information_only_flag", None)

    # Operational scope and recommendations
    profile.setdefault("scope_of_work", [])
    profile.setdefault("service_recommendation_line_items", [])
    profile.setdefault("service_line_item_annotations", [])
    profile.setdefault("completion_criteria_text", None)
    profile.setdefault("maintenance_trigger_text", None)
    profile.setdefault("recommended_interval_or_trigger", [])
    profile.setdefault("background_summary", None)
    profile.setdefault("manpower_and_tooling_requirements", None)

    # Usage counters (critical for scheduling)
    profile.setdefault("usage_counters_to_check_or_consider", [])
    profile.setdefault("usage_counter_requirements_text", None)

    # Configuration applicability (6 text fields for multipage rules)
    profile.setdefault("frame_or_model_applicability_text", None)
    profile.setdefault("combustion_or_fuel_configuration_text", None)
    profile.setdefault("hardware_or_part_configuration_text", None)
    profile.setdefault("serial_or_unit_applicability_text", None)
    profile.setdefault("exclusions_or_non_applicable_conditions_text", None)
    profile.setdefault("required_prior_modifications_text", None)
    profile.setdefault("prerequisite_outage_or_inspection_context_text", None)

    # Configuration analysis
    profile.setdefault("configuration_dependent", False)
    profile.setdefault("configuration_variables", [])
    profile.setdefault("configuration_summary", None)

    # Risk and severity
    profile.setdefault("severity_signals", [])
    profile.setdefault("failure_consequences", [])
    profile.setdefault("risk_summary", None)
    profile.setdefault("safety_or_damage_language_found", False)

    # SBOM and parts (critical for supply chain)
    profile.setdefault("sbom_dependency_flag", False)
    profile.setdefault("sbom_trigger_reason", None)

    # Normalize parts_referenced
    normalized_parts: list[dict[str, Any]] = []
    for item in profile.get("parts_referenced", []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        normalized_item.setdefault("part_number", None)
        normalized_item.setdefault("context", "")
        normalized_item.setdefault("required_inspection_types", [])
        normalized_item.setdefault("source_location", "")
        normalized_parts.append(normalized_item)
    profile["parts_referenced"] = normalized_parts

    # Normalize mli_numbers
    normalized_mli: list[dict[str, Any]] = []
    for item in profile.get("mli_numbers", []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        normalized_item.setdefault("mli_number", "")
        normalized_item.setdefault("context", "")
        normalized_mli.append(normalized_item)
    profile["mli_numbers"] = normalized_mli

    # Normalize reference_documents
    normalized_refs: list[dict[str, Any]] = []
    for item in profile.get("reference_documents", []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        normalized_item.setdefault("document_number", "")
        normalized_item.setdefault("document_type", "Other")  # TIL | GEK | GEH | Manual | Other
        normalized_item.setdefault("context", "")
        normalized_refs.append(normalized_item)
    profile["reference_documents"] = normalized_refs

    # Normalize tables_found_summary
    normalized_tables: list[dict[str, Any]] = []
    for item in profile.get("tables_found_summary", []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        normalized_item.setdefault("table_label", "")
        normalized_item.setdefault("table_description", "")
        normalized_item.setdefault("useful_for_downstream", False)
        normalized_item.setdefault("reason", "")
        normalized_tables.append(normalized_item)
    profile["tables_found_summary"] = normalized_tables

    # Normalize source_snippets (for explainability)
    normalized_snippets: list[dict[str, Any]] = []
    for item in profile.get("source_snippets", []):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        normalized_item.setdefault("field", "")
        normalized_item.setdefault("snippet", "")
        normalized_snippets.append(normalized_item)
    profile["source_snippets"] = normalized_snippets

    normalized_annotations: list[dict[str, Any]] = []
    for idx, item in enumerate(profile.get("service_line_item_annotations", []), start=1):
        if not isinstance(item, dict):
            continue
        normalized_item = dict(item)
        normalized_item.setdefault("line_item_id", f"item_{idx}")
        normalized_item.setdefault("line_item_text", "")
        normalized_item.setdefault("execution_classification", None)
        normalized_item.setdefault("activity_grouping", None)
        normalized_item.setdefault("system_or_component", None)
        normalized_item.setdefault("classification_rationale", None)
        normalized_annotations.append(normalized_item)
    profile["service_line_item_annotations"] = normalized_annotations

    # Quality signals
    profile.setdefault("missing_information_flags", [])
    profile.setdefault("extraction_confidence", 0.0)
    profile["information_only_flag"] = _coerce_bool(profile.get("information_only_flag"))

    return profile


def get_til_profile_json_schema() -> dict[str, Any]:
    """Return the JSON schema for TIL profiles.

    Used for validation and documentation.
    """
    return {
        "type": "object",
        "properties": {
            "til_number": {"type": ["string", "null"]},
            "revision": {"type": ["string", "null"]},
            "title": {"type": ["string", "null"]},
            "publish_date": {"type": ["string", "null"], "pattern": "^\\d{4}-\\d{2}-\\d{2}$|^null$"},
            "compliance_category_code": {"type": ["string", "null"], "enum": ["M", "C", "A", "S", None]},
            "information_only_flag": {"type": ["boolean", "null"]},
            "scope_of_work": {"type": "array", "items": {"type": "string"}},
            "service_recommendation_line_items": {"type": "array", "items": {"type": "string"}},
            "service_line_item_annotations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line_item_id": {"type": "string"},
                        "line_item_text": {"type": "string"},
                        "execution_classification": {"type": ["string", "null"]},
                        "activity_grouping": {"type": ["string", "null"]},
                        "system_or_component": {"type": ["string", "null"]},
                        "classification_rationale": {"type": ["string", "null"]},
                    },
                },
            },
            "background_summary": {"type": ["string", "null"]},
            "manpower_and_tooling_requirements": {"type": ["string", "null"]},
            "usage_counters_to_check_or_consider": {"type": "array", "items": {"type": "string"}},
            "parts_referenced": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "part_number": {"type": ["string", "null"]},
                        "context": {"type": "string"},
                        "required_inspection_types": {"type": "array", "items": {"type": "string"}},
                        "source_location": {"type": "string"},
                    },
                },
            },
            "mli_numbers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "mli_number": {"type": "string"},
                        "context": {"type": "string"},
                    },
                },
            },
            "extraction_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": [
            "til_number",
            "scope_of_work",
            "service_recommendation_line_items",
            "extraction_confidence",
        ],
    }


def validate_mandatory_fields(profile: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate that a normalized profile has required mandatory fields.

    Args:
        profile: Normalized TIL profile

    Returns:
        (is_valid: bool, missing_fields: list[str])
    """
    mandatory_fields = [
        "til_number",
        "title",
        "compliance_category_code",
        "scope_of_work",
        "service_recommendation_line_items",
    ]

    missing = []
    for field in mandatory_fields:
        value = profile.get(field)
        if value is None or (isinstance(value, (list, str)) and not value):
            missing.append(field)

    return len(missing) == 0, missing
