"""Audit API — timeline and activity feed."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(tags=["audit"])

# ponytail: in-memory timeline until calliope-core event store is fully migrated
_EVENTS: list[dict[str, Any]] = [
    {"event_id": "e1", "event_type": "module.commit", "timestamp_utc": "2026-01-01T00:00:00Z", "summary": "Initial commit"},
]


@router.get("/timeline")
def timeline(project_id: str | None = None, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
    events = _EVENTS[:limit]
    return {"events": events, "next_cursor": None, "has_more": False}


@router.get("/events/{event_id}")
def get_event(event_id: str) -> dict[str, Any]:
    ev = next((e for e in _EVENTS if e.get("event_id") == event_id), None)
    return {"event": ev or {"event_id": event_id, "status": "not_found"}}
