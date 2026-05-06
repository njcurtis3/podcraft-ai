"""JSON schema validators for inter-stage data contracts."""

import json
from typing import Any

import jsonschema

BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["topic", "key_angles", "facts_and_stats", "expert_perspectives", "controversy_or_nuance", "sources"],
    "properties": {
        "topic": {"type": "string", "minLength": 1},
        "key_angles": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "facts_and_stats": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "expert_perspectives": {"type": "array", "items": {"type": "string"}},
        "controversy_or_nuance": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
    "additionalProperties": False,
}

SCRIPT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "duration_estimate", "segments"],
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "duration_estimate": {"type": "string"},
        "segments": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["segment", "turns"],
                "properties": {
                    "segment": {"type": "string", "enum": ["intro", "main", "interview", "wrap"]},
                    "turns": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["speaker", "text"],
                            "properties": {
                                "speaker": {"type": "string", "enum": ["HOST_A", "HOST_B"]},
                                "text": {"type": "string", "minLength": 1},
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def validate_brief(data: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError if data does not match the research brief schema."""
    jsonschema.validate(instance=data, schema=BRIEF_SCHEMA)


def validate_script(data: dict[str, Any]) -> None:
    """Raise jsonschema.ValidationError if data does not match the script schema."""
    jsonschema.validate(instance=data, schema=SCRIPT_SCHEMA)
