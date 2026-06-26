"""Audit API — timeline and activity feed."""

from __future__ import annotations

from fastapi import APIRouter

from raphael_audit.core.store import EventStore

router = APIRouter(tags=["audit"])
_store = EventStore()


@router.get("/timeline")
def timeline(project_id: str | None = None, limit: int = 50, cursor: str | None = None) -> dict:
    events, next_cursor = _store.list_events_paginated(project_id=project_id, limit=limit, cursor=cursor)
    return {"events": events, "next_cursor": next_cursor, "has_more": next_cursor is not None}


@router.get("/events/{event_id}")
def get_event(event_id: str) -> dict:
    ev = _store.get_event(event_id)
    return {"event": ev or {"event_id": event_id, "status": "not_found"}}


@router.get("/verify")
def verify() -> dict:
    return _store.verify_integrity()
