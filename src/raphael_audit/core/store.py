"""Append-only event store with deduplication (SQLite dev, Postgres when configured)."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from raphael_audit.core.bloom import BloomFilter
from raphael_audit.core.compliance.integrity import verify_integrity_chain
from raphael_audit.core.compliance.manager import ComplianceManager
from raphael_audit.core.paths import default_db_path
from raphael_audit.core.security.encryption import DataKeyManager

logger = logging.getLogger(__name__)


class EventStore:
    """Append-only local event store with event_id and checksum dedup."""

    DEDUP_WINDOW_HOURS = 24

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        encrypted_at_rest: bool = False,
        data_key_path: Path | None = None,
    ) -> None:
        from raphael_contracts import db as rdb

        self._postgres = rdb.is_postgres()
        self._bloom = BloomFilter()
        self._encryption = DataKeyManager(enabled=encrypted_at_rest, key_path=data_key_path)
        self._compliance = ComplianceManager()
        if self._postgres:
            rdb.ensure_migrations()
            self.db_path = Path("postgres")
        else:
            self.db_path = db_path or default_db_path()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        self._hydrate_bloom()
        self._hydrate_integrity_state()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS micro_events (
                event_id TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                project_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                received_timestamp_utc TEXT NOT NULL,
                body TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_commits (
                commit_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                event_count INTEGER NOT NULL,
                body TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integrity_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_hash TEXT,
                event_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_micro_project ON micro_events(project_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON session_commits(session_id)")
        row = self._conn.execute("SELECT 1 FROM integrity_meta WHERE id = 1").fetchone()
        if not row:
            self._conn.execute("INSERT INTO integrity_meta (id, last_hash, event_count) VALUES (1, NULL, 0)")
        self._conn.commit()

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any | None:
        if self._postgres:
            from raphael_contracts.db import pg_fetchone

            return pg_fetchone(sql, params)
        return self._conn.execute(sql, params).fetchone()

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        if self._postgres:
            from raphael_contracts.db import pg_fetchall

            return pg_fetchall(sql, params)
        return self._conn.execute(sql, params).fetchall()

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        if self._postgres:
            from raphael_contracts.db import pg_execute

            return pg_execute(sql, params)
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur

    def _body_field(self, row: Any) -> str:
        return row["body"] if isinstance(row, dict) else row["body"]

    def _hydrate_bloom(self) -> None:
        cutoff = self._cutoff_iso()
        rows = self._fetchall(
            "SELECT checksum FROM micro_events WHERE received_timestamp_utc >= ?",
            (cutoff,),
        )
        for row in rows:
            checksum = row["checksum"] if isinstance(row, dict) else row[0]
            self._bloom.add(checksum)

    def _hydrate_integrity_state(self) -> None:
        row = self._fetchone("SELECT last_hash FROM integrity_meta WHERE id = 1")
        if row:
            last_hash = row["last_hash"] if isinstance(row, dict) else row[0]
            self._compliance.set_last_event_hash(last_hash)

    def _persist_integrity_state(self, last_hash: str) -> None:
        self._execute(
            """
            UPDATE integrity_meta
            SET last_hash = ?, event_count = event_count + 1
            WHERE id = 1
            """,
            (last_hash,),
        )

    def _cutoff_iso(self) -> str:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.DEDUP_WINDOW_HOURS)
        return cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _encode_body(self, event: dict[str, Any]) -> str:
        raw = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        return self._encryption.encrypt(raw)

    def _decode_body(self, stored: str) -> dict[str, Any]:
        raw = self._encryption.decrypt(stored)
        return json.loads(raw)

    def append_micro_event(self, event: dict[str, Any]) -> int | None:
        """Insert micro-event; return row id if accepted, None if duplicate."""
        event_id = event["event_id"]
        checksum = event["checksum"]

        if checksum in self._bloom:
            existing = self._fetchone(
                "SELECT 1 FROM micro_events WHERE checksum = ? LIMIT 1",
                (checksum,),
            )
            if existing:
                return None

        integrity_link = self._compliance.compute_integrity_link(event)
        event["integrity_chain"] = integrity_link

        from raphael_audit.core.compliance.integrity import compute_event_hash

        try:
            if self._postgres:
                from raphael_contracts.db import adapt_sql, connection

                with connection() as conn:
                    row = conn.execute(
                        adapt_sql(
                            """
                            INSERT INTO micro_events (
                                event_id, checksum, project_id, event_type,
                                timestamp_utc, received_timestamp_utc, body
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                            RETURNING id
                            """
                        ),
                        (
                            event_id,
                            checksum,
                            event["project_id"],
                            event["event_type"],
                            event["timestamp_utc"],
                            event["received_timestamp_utc"],
                            self._encode_body(event),
                        ),
                    ).fetchone()
                    conn.execute(
                        adapt_sql(
                            """
                            UPDATE integrity_meta
                            SET last_hash = ?, event_count = event_count + 1
                            WHERE id = 1
                            """
                        ),
                        (compute_event_hash(event),),
                    )
                    conn.commit()
                    rowid = row["id"] if row else None
            else:
                cursor = self._conn.execute(
                    """
                    INSERT INTO micro_events (
                        event_id, checksum, project_id, event_type,
                        timestamp_utc, received_timestamp_utc, body
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        checksum,
                        event["project_id"],
                        event["event_type"],
                        event["timestamp_utc"],
                        event["received_timestamp_utc"],
                        self._encode_body(event),
                    ),
                )
                self._persist_integrity_state(compute_event_hash(event))
                self._conn.commit()
                rowid = cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        except Exception as exc:
            if self._postgres:
                try:
                    import psycopg.errors

                    if isinstance(exc, psycopg.errors.UniqueViolation):
                        return None
                except ImportError:
                    pass
                if "unique" in str(exc).lower():
                    return None
            raise

        self._bloom.add(checksum)
        return rowid

    def append(self, event: dict[str, Any]) -> int | None:
        return self.append_micro_event(event)

    def commit_session(self, session_id: str, project_id: str, events: list[dict[str, Any]]) -> str:
        from raphael_audit.core.uuid7 import uuid7_str

        commit_id = uuid7_str()
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        commit_body = {
            "commit_id": commit_id,
            "session_id": session_id,
            "project_id": project_id,
            "timestamp_utc": timestamp,
            "events": events,
            "fidelity_signal": events[-1]["fidelity"] if events else None,
        }
        logger.info(
            "Transactionally committing %s events to Kafka via commit %s",
            len(events),
            commit_id,
        )
        self._execute(
            """
            INSERT INTO session_commits (commit_id, session_id, project_id, timestamp_utc, event_count, body)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                commit_id,
                session_id,
                project_id,
                timestamp,
                len(events),
                json.dumps(commit_body, separators=(",", ":"), ensure_ascii=False),
            ),
        )
        return commit_id

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        row = self._fetchone("SELECT body FROM micro_events WHERE event_id = ?", (event_id,))
        if not row:
            return None
        return self._decode_body(self._body_field(row))

    def list_events(self, project_id: str | None = None) -> list[dict[str, Any]]:
        if project_id:
            rows = self._fetchall(
                "SELECT body FROM micro_events WHERE project_id = ? ORDER BY timestamp_utc",
                (project_id,),
            )
        else:
            rows = self._fetchall("SELECT body FROM micro_events ORDER BY timestamp_utc")
        return [self._decode_body(self._body_field(row)) for row in rows]

    def list_events_by_session(self, session_id: str) -> list[dict[str, Any]]:
        return [event for event in self.list_events() if event.get("session_id") == session_id]

    def get_latest_rowid(self) -> int:
        if self._postgres:
            row = self._fetchone("SELECT MAX(id) FROM micro_events")
        else:
            row = self._fetchone("SELECT MAX(rowid) FROM micro_events")
        if not row:
            return 0
        val = row[0] if not isinstance(row, dict) else next(iter(row.values()))
        return int(val) if val is not None else 0

    def get_events_range(self, start: int, end: int) -> list[dict[str, Any]]:
        if self._postgres:
            rows = self._fetchall(
                "SELECT body FROM micro_events WHERE id >= ? AND id <= ? ORDER BY id",
                (start, end),
            )
        else:
            rows = self._fetchall(
                "SELECT body FROM micro_events WHERE rowid >= ? AND rowid <= ? ORDER BY rowid",
                (start, end),
            )
        return [self._decode_body(self._body_field(row)) for row in rows]

    def get_session_commit(self, session_id: str) -> dict[str, Any] | None:
        row = self._fetchone(
            "SELECT body FROM session_commits WHERE session_id = ? ORDER BY timestamp_utc DESC LIMIT 1",
            (session_id,),
        )
        if not row:
            return None
        return json.loads(self._body_field(row))

    def list_session_commits(self, session_id: str) -> list[dict[str, Any]]:
        rows = self._fetchall(
            "SELECT body FROM session_commits WHERE session_id = ? ORDER BY timestamp_utc",
            (session_id,),
        )
        return [json.loads(self._body_field(row)) for row in rows]

    def list_events_paginated(
        self,
        *,
        project_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        since: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        limit = max(1, min(limit, 500))
        query = "SELECT event_id, body, timestamp_utc FROM micro_events WHERE 1=1"
        params: list[Any] = []
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if since:
            query += " AND timestamp_utc >= ?"
            params.append(since)
        if cursor:
            query += " AND timestamp_utc > ?"
            params.append(cursor)
        query += " ORDER BY timestamp_utc ASC LIMIT ?"
        params.append(limit + 1)
        rows = self._fetchall(query, tuple(params))
        has_extra = len(rows) > limit
        page_rows = rows[:limit]
        events = [self._decode_body(self._body_field(r)) for r in page_rows]
        if has_extra and page_rows:
            last = page_rows[-1]
            next_cursor = last["timestamp_utc"] if isinstance(last, dict) else last[2]
        else:
            next_cursor = None
        return events, next_cursor

    def timeline_for_document(self, document_id: str) -> list[dict[str, Any]]:
        return [
            event
            for event in self.list_events()
            if event.get("payload", {}).get("document_id") == document_id
        ]

    def verify_integrity(self, project_id: str | None = None) -> dict[str, Any]:
        return verify_integrity_chain(self.list_events(project_id=project_id))

    def export_jsonl(self, project_id: str | None = None) -> Iterator[str]:
        for event in self.list_events(project_id=project_id):
            yield json.dumps(event, separators=(",", ":"), ensure_ascii=False)

    def close(self) -> None:
        if not self._postgres:
            self._conn.close()
