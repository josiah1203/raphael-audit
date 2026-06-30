"""Audit API — timeline and activity feed."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from raphael_audit.core.event_builder import build_event
from raphael_audit.core.observability.hardening import (
    AUDIT_EVENTS_DUPLICATE,
    AUDIT_EVENTS_INGESTED,
    AUDIT_VERIFY_RUNS,
    metrics_body,
)
from raphael_audit.core.store import EventStore

router = APIRouter(tags=["audit"])
_store = EventStore()


def _normalize_timeline_event(event: dict[str, Any]) -> dict[str, Any]:
    """Flatten envelope fields for Activity UI consumers."""
    tool_obj = event.get("tool") or {}
    tool_id = tool_obj.get("identifier") if isinstance(tool_obj, dict) else str(tool_obj or "raphael")
    event_type = str(event.get("event_type") or event.get("type") or "event")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    status = str(payload.get("status") or event.get("status") or "ok")
    normalized = dict(event)
    normalized["type"] = event_type
    normalized["tool"] = tool_id
    normalized["status"] = status
    normalized["session_id"] = event.get("session_id")
    normalized["project_id"] = event.get("project_id")
    normalized["source"] = {
        "tool": tool_id,
        "event_type": event_type,
        **(event.get("source") if isinstance(event.get("source"), dict) else {}),
    }
    return normalized


@router.post("/events")
def ingest_event(body: dict[str, Any]) -> dict[str, Any]:
    """Accept platform events, persist, and publish to Kafka."""
    try:
        event = build_event(
            event_type=body.get("event_type", "platform.event"),
            payload=body.get("payload") or {},
            session_id=body.get("session_id", "api"),
            user_id=body.get("user_id", "system"),
            project_id=body.get("project_id") or body.get("workspace_id", "default"),
            tool_identifier=body.get("tool", "raphael"),
            tool_version=body.get("tool_version", "0.1.0"),
        )
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    rowid = _store.append_micro_event(event)
    if rowid is None:
        AUDIT_EVENTS_DUPLICATE.inc()
        return {"status": "duplicate", "event_id": event["event_id"]}
    AUDIT_EVENTS_INGESTED.labels(event_type=event["event_type"]).inc()
    try:
        from raphael_contracts.kafka import publish_event

        publish_event(
            f"raphael.audit.{event['event_type'].replace('.', '_')}",
            {"event_id": event["event_id"], "event_type": event["event_type"], "payload": event.get("payload")},
            source="raphael-audit",
            workspace_id=event.get("project_id"),
        )
    except Exception:
        pass
    return {"status": "accepted", "event_id": event["event_id"]}


@router.get("/timeline")
def timeline(project_id: str | None = None, limit: int = 50, cursor: str | None = None) -> dict:
    events, next_cursor = _store.list_events_paginated(project_id=project_id, limit=limit, cursor=cursor)
    return {
        "events": [_normalize_timeline_event(e) for e in events],
        "next_cursor": next_cursor,
        "has_more": next_cursor is not None,
    }


@router.get("/events/{event_id}")
def get_event(event_id: str) -> dict:
    ev = _store.get_event(event_id)
    return {"event": ev or {"event_id": event_id, "status": "not_found"}}


@router.get("/verify")
def verify() -> dict:
    result = _store.verify_integrity()
    valid = bool(result.get("valid") or result.get("status") in {"ok", "valid"})
    AUDIT_VERIFY_RUNS.labels(result="valid" if valid else "invalid").inc()
    return result
