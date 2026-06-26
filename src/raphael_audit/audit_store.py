"""Simplified event store for audit timeline."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


class AuditStore:
    def __init__(self, db_path: Path | None = None) -> None:
        path = db_path or Path(os.environ.get("RAPHAEL_AUDIT_DB", "/tmp/raphael-audit.db"))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS micro_events (
                event_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                body TEXT NOT NULL
            )"""
        )
        self._seed()

    def _seed(self) -> None:
        if self._conn.execute("SELECT COUNT(*) FROM micro_events").fetchone()[0]:
            return
        ev = {
            "event_id": "e1",
            "event_type": "module.commit",
            "timestamp_utc": "2026-01-01T00:00:00Z",
            "summary": "Initial commit",
            "project_id": "default",
        }
        self.append(ev)

    def append(self, event: dict[str, Any]) -> str:
        eid = event["event_id"]
        self._conn.execute(
            "INSERT OR IGNORE INTO micro_events (event_id, project_id, event_type, timestamp_utc, body) VALUES (?, ?, ?, ?, ?)",
            (
                eid,
                event.get("project_id", "default"),
                event.get("event_type", "unknown"),
                event.get("timestamp_utc", ""),
                json.dumps(event),
            ),
        )
        self._conn.commit()
        return eid

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT body FROM micro_events WHERE event_id = ?", (event_id,)).fetchone()
        return json.loads(row["body"]) if row else None

    def timeline(self, project_id: str | None = None, limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
        q = "SELECT body, timestamp_utc FROM micro_events WHERE 1=1"
        params: list[Any] = []
        if project_id:
            q += " AND project_id = ?"
            params.append(project_id)
        if cursor:
            q += " AND timestamp_utc > ?"
            params.append(cursor)
        q += " ORDER BY timestamp_utc ASC LIMIT ?"
        params.append(limit + 1)
        rows = list(self._conn.execute(q, params))
        has_more = len(rows) > limit
        page = rows[:limit]
        events = [json.loads(r["body"]) for r in page]
        return {
            "events": events,
            "next_cursor": page[-1]["timestamp_utc"] if has_more and page else None,
            "has_more": has_more,
        }

    def verify(self) -> dict[str, str]:
        count = self._conn.execute("SELECT COUNT(*) FROM micro_events").fetchone()[0]
        return {"status": "ok", "event_count": str(count)}
