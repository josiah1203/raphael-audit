"""JSON Schema validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # pragma: no cover
    Draft202012Validator = None  # type: ignore[assignment]

try:
    from raphael_artifacts.calliope_schema.loader import load_schema
    from raphael_artifacts.calliope_schema.registry.core import SchemaRegistry
except ModuleNotFoundError:  # pragma: no cover
    load_schema = None  # type: ignore[assignment]
    SchemaRegistry = None  # type: ignore[assignment]

def get_calliope_home() -> Path:
    return Path.home() / ".calliope"

_ENVELOPE = Draft202012Validator(load_schema("event_envelope.v0.json")) if (Draft202012Validator and load_schema) else None
_SNAPSHOT = Draft202012Validator(load_schema("design_snapshot.v0.json")) if (Draft202012Validator and load_schema) else None
_ADDON_SCHEMAS = (
    {
        "fusion": Draft202012Validator(load_schema("addon_snapshot_fusion.v0.json")),
        "solidworks": Draft202012Validator(load_schema("addon_snapshot_solidworks.v0.json")),
        "altium": Draft202012Validator(load_schema("addon_snapshot_altium.v0.json")),
    }
    if (Draft202012Validator and load_schema)
    else {}
)

# Global registry instance with persistence
REGISTRY = SchemaRegistry(persistence_path=get_calliope_home() / "registry.json") if SchemaRegistry else None


def validate_event(event: dict[str, Any], use_registry: bool = True) -> list[str]:
    """Return validation error messages for an event envelope."""
    if _ENVELOPE is None:
        return []
    errors = sorted(error.message for error in _ENVELOPE.iter_errors(event))
    if errors:
        return errors
    
    if use_registry and REGISTRY and "wire_schema_id" in event:
        schema_id = event["wire_schema_id"]
        if schema_id == 0:
            return [] # Reserved for 'no specific wire schema' or 'legacy'
            
        schema_obj = REGISTRY.get_by_id(schema_id)
        if not schema_obj:
            return [f"Unknown wire_schema_id: {event['wire_schema_id']}"]
        
        # Validate payload against the registered wire schema
        try:
            wire_schema = json.loads(schema_obj.schema)
            validator = Draft202012Validator(wire_schema)
            payload_errors = sorted(error.message for error in validator.iter_errors(event["payload"]))
            if payload_errors:
                return [f"Payload doesn't match wire schema: {err}" for err in payload_errors]
        except Exception as e:
            return [f"Failed to validate against wire schema: {str(e)}"]
            
    return []


def validate_design_snapshot(snapshot: dict[str, Any]) -> list[str]:
    """Return validation error messages for a design snapshot."""
    if _SNAPSHOT is None:
        return []
    return sorted(error.message for error in _SNAPSHOT.iter_errors(snapshot))


def validate_addon_snapshot(tool: str, payload: dict[str, Any]) -> list[str]:
    """Validate desktop addon snapshot payloads by tool name."""
    validator = _ADDON_SCHEMAS.get(tool)
    if not validator:
        return [f"unknown addon tool: {tool}"]
    return sorted(error.message for error in validator.iter_errors(payload))
