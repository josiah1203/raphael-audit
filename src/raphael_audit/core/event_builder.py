"""Build validated event envelopes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from raphael_audit.schema.validator import validate_event

from raphael_audit.core.checksum import compute_checksum
from raphael_audit.core.fidelity import score_fidelity
from raphael_audit.core.id_scheme import compute_deterministic_id
from raphael_audit.core.uuid7 import uuid7_str

SCHEMA_VERSION = "0.1.0"
ADAPTER_VERSION = "0.1.0"


def migrate_v0_to_v1(event: dict[str, Any]) -> dict[str, Any]:
    if "wire_schema_id" not in event:
        event["wire_schema_id"] = 0
    return event


MIGRATION_CHAIN: list[Any] = [migrate_v0_to_v1]


def migrate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Apply registered schema migrations in order (lazy on read)."""
    migrated = dict(event)
    for step in MIGRATION_CHAIN:
        migrated = step(migrated)
    return migrated


MIGRATION_CHAIN: list[tuple[str, str, Any]] = [
    ("0.0.0", "0.1.0", migrate_v0_to_v1),
]


def migrate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Apply registered schema migrations in order."""
    migrated = dict(event)
    for _from, _to, fn in MIGRATION_CHAIN:
        migrated = fn(migrated)
    return migrated


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    session_id: str,
    user_id: str,
    project_id: str,
    tool_identifier: str = "fusion360",
    tool_version: str = "unknown",
    adapter_version: str = ADAPTER_VERSION,
    tenant_id: str = "local",
    causation_id: str | None = None,
    correlation_id: str | None = None,
    timestamp_utc: str | None = None,
    corrects_event_id: str | None = None,
    use_deterministic_id: bool = False,
    object_id: str | None = None,
    application: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    """Construct a complete event envelope with checksum and fidelity."""
    fidelity = score_fidelity(event_type, payload, tool_identifier=tool_identifier)
    timestamp = timestamp_utc or _utc_now()

    if use_deterministic_id and object_id:
        ts_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        ts_rounded = ts_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        temp_event = {"payload": payload}
        fingerprint = compute_checksum(temp_event).split(":")[1][:16]
        event_id = compute_deterministic_id(
            tenant_id=tenant_id,
            tool_id=tool_identifier,
            object_id=object_id,
            change_fingerprint=fingerprint,
            timestamp_rounded=ts_rounded,
        )
    else:
        event_id = uuid7_str()

    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id,
        "timestamp_utc": timestamp,
        "received_timestamp_utc": _utc_now(),
        "session_id": session_id,
        "user_id": user_id,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "tool": {
            "identifier": tool_identifier,
            "version": tool_version,
            "adapter_version": adapter_version,
        },
        "event_type": event_type,
        "fidelity": fidelity,
        "payload": payload,
    }
    if application:
        event["application"] = application
    if branch:
        event["branch"] = branch
    if causation_id:
        event["causation_id"] = causation_id
    if correlation_id:
        event["correlation_id"] = correlation_id
    if corrects_event_id:
        event["corrects_event_id"] = corrects_event_id

    event["checksum"] = compute_checksum(event)
    event = migrate_event(event)
    errors = validate_event(event)
    if errors:
        raise ValueError(f"Invalid event envelope: {errors}")
    return event


def build_geometry_event(
    *,
    event_type: str,
    payload: dict[str, Any],
    session_id: str,
    user_id: str,
    project_id: str,
    tool_version: str = "unknown",
    tool_identifier: str = "fusion360",
    causation_id: str | None = None,
    correlation_id: str | None = None,
    timestamp_utc: str | None = None,
    corrects_event_id: str | None = None,
    use_deterministic_id: bool = False,
    object_id: str | None = None,
    application: str | None = None,
    branch: str | None = None,
) -> dict[str, Any]:
    return build_event(
        event_type=event_type,
        payload=payload,
        session_id=session_id,
        user_id=user_id,
        project_id=project_id,
        tool_identifier=tool_identifier,
        tool_version=tool_version,
        causation_id=causation_id,
        correlation_id=correlation_id,
        timestamp_utc=timestamp_utc,
        corrects_event_id=corrects_event_id,
        use_deterministic_id=use_deterministic_id,
        object_id=object_id,
        application=application,
        branch=branch,
    )
