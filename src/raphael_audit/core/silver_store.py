"""Persisted silver projection state in SQLite."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from raphael_audit.core.paths import calliope_home


class SilverStore:
    """Silver layer object state keyed by object_id."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or calliope_home() / "silver.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS silver_objects (
                object_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                object_type TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_silver_project ON silver_objects(project_id)"
        )
        self._conn.commit()

    def upsert(self, object_id: str, project_id: str, object_type: str, state: dict[str, Any], updated_at: str) -> None:
        self._conn.execute(
            """
            INSERT INTO silver_objects (object_id, project_id, object_type, state_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(object_id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (object_id, project_id, object_type, json.dumps(state), updated_at),
        )
        self._conn.commit()

    def get(self, object_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT state_json FROM silver_objects WHERE object_id = ?", (object_id,)
        ).fetchone()
        if not row:
            return None
        return json.loads(row["state_json"])

    def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT object_id, object_type, state_json, updated_at FROM silver_objects WHERE project_id = ?",
            (project_id,),
        )
        return [
            {
                "object_id": r["object_id"],
                "object_type": r["object_type"],
                "state": json.loads(r["state_json"]),
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def list_all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT object_id, project_id, object_type, state_json, updated_at FROM silver_objects"
        )
        return [
            {
                "object_id": r["object_id"],
                "project_id": r["project_id"],
                "object_type": r["object_type"],
                "state": json.loads(r["state_json"]),
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def delete_by_project(self, project_id: str) -> int:
        cursor = self._conn.execute(
            "DELETE FROM silver_objects WHERE project_id = ?", (project_id,)
        )
        self._conn.commit()
        return cursor.rowcount

    def clear(self) -> None:
        self._conn.execute("DELETE FROM silver_objects")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
