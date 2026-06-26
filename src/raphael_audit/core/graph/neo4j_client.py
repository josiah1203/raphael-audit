"""Neo4j and in-memory graph clients."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryGraphClient:
    """In-memory graph for tests and Neo4j fallback."""

    def __init__(self, uri: str = "bolt://localhost:7687") -> None:
        self.uri = uri
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: list[dict[str, Any]] = []

    def upsert_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> None:
        if node_id not in self._nodes:
            self._nodes[node_id] = {"id": node_id, "labels": labels, "properties": {}}
        self._nodes[node_id]["properties"].update(properties)
        logger.debug("Upserted node %s", node_id)

    def create_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: dict[str, Any],
        from_timestamp: str | None = None,
        to_timestamp: str | None = None,
    ) -> None:
        self._edges.append(
            {
                "from": from_id,
                "to": to_id,
                "type": edge_type,
                "properties": properties,
                "from_timestamp": from_timestamp,
                "to_timestamp": to_timestamp,
            }
        )

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

    def sync_event(self, event: dict[str, Any]) -> None:
        """Agent adapter compatibility: map event to graph."""
        payload = event.get("payload", {})
        if "feature" in event.get("event_type", ""):
            f_id = payload.get("feature_id")
            if f_id:
                self.upsert_node(
                    f_id,
                    ["Feature"],
                    {
                        "name": payload.get("feature_name") or payload.get("name"),
                        "type": payload.get("feature_type") or payload.get("type"),
                    },
                )
        self.upsert_node(
            event["event_id"],
            ["Event"],
            {"type": event.get("event_type"), "timestamp": event.get("timestamp_utc")},
        )

    def run_query(self, query: str, params: dict[str, Any] | None = None) -> list[Any]:
        logger.info("Cypher: %s %s", query, params)
        return []

    def verify_connectivity(self) -> bool:
        return True

    def close(self) -> None:
        return None


class Neo4jGraphClient(InMemoryGraphClient):
    """Neo4j driver wrapper with real Cypher when driver is available."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "password",
    ) -> None:
        super().__init__(uri=uri)
        self.user = user
        self.password = password
        self._driver = None
        try:
            from neo4j import GraphDatabase  # type: ignore[import-untyped]

            self._driver = GraphDatabase.driver(uri, auth=(user, password))
        except Exception:
            logger.warning("Neo4j driver unavailable; using in-memory graph at %s", uri)

    def _run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        if not self._driver:
            return []
        with self._driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def upsert_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> None:
        if not self._driver:
            return super().upsert_node(node_id, labels, properties)
        label_clause = ":".join(labels) if labels else "Node"
        props = {"id": node_id, **properties}
        self._run(
            f"MERGE (n:{label_clause} {{id: $id}}) SET n += $props",
            id=node_id,
            props=props,
        )
        super().upsert_node(node_id, labels, properties)

    def create_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: dict[str, Any],
        from_timestamp: str | None = None,
        to_timestamp: str | None = None,
    ) -> None:
        if not self._driver:
            return super().create_edge(
                from_id, to_id, edge_type, properties, from_timestamp, to_timestamp
            )
        self._run(
            f"""
            MATCH (a {{id: $from_id}}), (b {{id: $to_id}})
            MERGE (a)-[r:{edge_type}]->(b)
            SET r += $props
            """,
            from_id=from_id,
            to_id=to_id,
            props={
                **properties,
                "from_timestamp": from_timestamp,
                "to_timestamp": to_timestamp,
            },
        )
        super().create_edge(
            from_id, to_id, edge_type, properties, from_timestamp, to_timestamp
        )

    def get_node(self, node_id: str) -> dict[str, Any] | None:
        if self._driver:
            rows = self._run("MATCH (n {id: $id}) RETURN n AS node", id=node_id)
            if rows and rows[0].get("node"):
                node = dict(rows[0]["node"])
                return {"id": node.get("id", node_id), "properties": node}
        return super().get_node(node_id)

    def query_impact_set(self, start_node_id: str, depth: int = 5) -> set[str]:
        if not self._driver:
            return super().query_impact_set(start_node_id, depth=depth)
        rows = self._run(
            """
            MATCH (start {id: $start_id})-[*1..$depth]->(n)
            RETURN DISTINCT n.id AS id
            """,
            start_id=start_node_id,
            depth=depth,
        )
        impact = {start_node_id}
        impact.update(row["id"] for row in rows if row.get("id"))
        return impact

    def list_edges(self, from_id: str | None = None, to_id: str | None = None) -> list[dict[str, Any]]:
        if not self._driver:
            return super().list_edges(from_id=from_id, to_id=to_id)
        query = "MATCH (a)-[r]->(b)"
        params: dict[str, Any] = {}
        clauses = []
        if from_id:
            clauses.append("a.id = $from_id")
            params["from_id"] = from_id
        if to_id:
            clauses.append("b.id = $to_id")
            params["to_id"] = to_id
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " RETURN a.id AS from_id, b.id AS to_id, type(r) AS type, properties(r) AS properties"
        rows = self._run(query, **params)
        return [
            {
                "from": row["from_id"],
                "to": row["to_id"],
                "type": row["type"],
                "properties": row.get("properties") or {},
            }
            for row in rows
        ]

    def verify_connectivity(self) -> bool:
        if not self._driver:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._driver:
            self._driver.close()


Neo4jClient = InMemoryGraphClient
