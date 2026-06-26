"""SQLite-backed knowledge graph store (default on-prem backend)."""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from raphael_audit.core.paths import calliope_home

logger = logging.getLogger(__name__)


class SqliteGraphClient:
    """Persisted graph with temporal edge support."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or calliope_home() / "graph.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        # Expose for test parity with InMemoryGraphClient
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []
        self._hydrate_cache()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                labels TEXT NOT NULL,
                properties TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                properties TEXT NOT NULL,
                from_timestamp TEXT,
                to_timestamp TEXT
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_id)")
        self._conn.commit()

    def _hydrate_cache(self) -> None:
        for row in self._conn.execute("SELECT node_id, labels, properties FROM nodes"):
            self._nodes[row["node_id"]] = {
                "id": row["node_id"],
                "labels": json.loads(row["labels"]),
                "properties": json.loads(row["properties"]),
            }
        for row in self._conn.execute(
            "SELECT from_id, to_id, edge_type, properties, from_timestamp, to_timestamp FROM edges"
        ):
            self._edges.append(
                {
                    "from": row["from_id"],
                    "to": row["to_id"],
                    "type": row["edge_type"],
                    "properties": json.loads(row["properties"]),
                    "from_timestamp": row["from_timestamp"],
                    "to_timestamp": row["to_timestamp"],
                }
            )

    def upsert_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> None:
        merged = dict(self._nodes.get(node_id, {}).get("properties", {}))
        merged.update(properties)
        self._nodes[node_id] = {"id": node_id, "labels": labels, "properties": merged}
        self._conn.execute(
            """
            INSERT INTO nodes (node_id, labels, properties) VALUES (?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET labels = excluded.labels, properties = excluded.properties
            """,
            (node_id, json.dumps(labels), json.dumps(merged)),
        )
        self._conn.commit()
        logger.debug("Upserted graph node %s", node_id)

    def create_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: dict[str, Any],
        from_timestamp: str | None = None,
        to_timestamp: str | None = None,
    ) -> None:
        edge = {
            "from": from_id,
            "to": to_id,
            "type": edge_type,
            "properties": properties,
            "from_timestamp": from_timestamp,
            "to_timestamp": to_timestamp,
        }
        self._edges.append(edge)
        self._conn.execute(
            """
            INSERT INTO edges (from_id, to_id, edge_type, properties, from_timestamp, to_timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                from_id,
                to_id,
                edge_type,
                json.dumps(properties),
                from_timestamp,
                to_timestamp,
            ),
        )
        self._conn.commit()

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    def query_impact_set(self, start_node_id: str, depth: int = 5) -> set[str]:
        impact_set = {start_node_id}
        current_layer = {start_node_id}
        for _ in range(depth):
            next_layer: set[str] = set()
            for node_id in current_layer:
                for edge in self._edges:
                    if edge["from"] == node_id and edge["to"] not in impact_set:
                        next_layer.add(edge["to"])
            if not next_layer:
                break
            if len(next_layer) > 100:
                next_layer = set(list(next_layer)[:100])
            impact_set.update(next_layer)
            current_layer = next_layer
        return impact_set

    def find_temporal_edges(self, start_ts: str, end_ts: str) -> list[dict[str, Any]]:
        results = []
        for edge in self._edges:
            e_start = edge.get("from_timestamp")
            e_end = edge.get("to_timestamp")
            if not e_start or not e_end:
                continue
            if e_start <= end_ts and e_end >= start_ts:
                results.append(edge)
        return results

    def list_edges(self, from_id: str | None = None, to_id: str | None = None) -> list[dict[str, Any]]:
        edges = self._edges
        if from_id:
            edges = [e for e in edges if e["from"] == from_id]
        if to_id:
            edges = [e for e in edges if e["to"] == to_id]
        return edges

    def close(self) -> None:
        self._conn.close()
