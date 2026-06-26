"""Audit API — timeline and activity feed."""

from __future__ import annotations

from fastapi import APIRouter

from raphael_audit.audit_store import AuditStore

router = APIRouter(tags=["audit"])
_store = AuditStore()


@router.get("/timeline")
def timeline(project_id: str | None = None, limit: int = 50, cursor: str | None = None) -> dict:
    return _store.timeline(project_id, limit, cursor)


@router.get("/events/{event_id}")
def get_event(event_id: str) -> dict:
    ev = _store.get_event(event_id)
    return {"event": ev or {"event_id": event_id, "status": "not_found"}}


@router.get("/verify")
def verify() -> dict:
    return _store.verify()
