"""Session commit service: fold micro-events into session commits."""

from __future__ import annotations

from typing import Any

from raphael_audit.core.store import EventStore


class SessionCommitService:
    """Fold micro-events on explicit close; delegates to EventStore.commit_session()."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def commit(self, session_id: str, project_id: str | None = None) -> dict[str, Any]:
        events = self._store.list_events_by_session(session_id)
        if project_id:
            events = [e for e in events if e.get("project_id") == project_id]
        if not events:
            return {
                "accepted": False,
                "error": "no_events",
                "session_id": session_id,
            }
        proj = project_id or events[0]["project_id"]
        commit_id = self._store.commit_session(session_id, proj, events)
        return {
            "accepted": True,
            "commit_id": commit_id,
            "session_id": session_id,
            "project_id": proj,
            "event_count": len(events),
        }

    def get_session(self, session_id: str) -> dict[str, Any]:
        events = self._store.list_events_by_session(session_id)
        commit = self._store.get_session_commit(session_id)
        return {
            "session_id": session_id,
            "micro_event_count": len(events),
            "events": events,
            "commit": commit,
        }
