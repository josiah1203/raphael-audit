"""Graph client factory and protocol."""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from raphael_graph.calliope_graph.neo4j_client import InMemoryGraphClient, Neo4jGraphClient
from raphael_graph.calliope_graph.sqlite_store import SqliteGraphClient


@runtime_checkable
class GraphClient(Protocol):
    def upsert_node(self, node_id: str, labels: list[str], properties: dict[str, Any]) -> None: ...
    def create_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        properties: dict[str, Any],
        from_timestamp: str | None = None,
        to_timestamp: str | None = None,
    ) -> None: ...
    def query_impact_set(self, start_node_id: str, depth: int = 5) -> set[str]: ...
    def find_temporal_edges(self, start_ts: str, end_ts: str) -> list[dict[str, Any]]: ...


def create_graph_client(
    *,
    graph_backend: str = "sqlite",
    neo4j_uri: str | None = None,
    neo4j_user: str | None = None,
    neo4j_password: str | None = None,
    graph_db_path: Any = None,
) -> GraphClient:
    uri = neo4j_uri or os.environ.get("NEO4J_URI")
    user = neo4j_user or os.environ.get("NEO4J_USER", "neo4j")
    password = neo4j_password or os.environ.get("NEO4J_PASSWORD", "password")
    if graph_backend == "neo4j" or uri:
        return Neo4jGraphClient(uri=uri or "bolt://localhost:7687", user=user, password=password)
    return SqliteGraphClient(db_path=graph_db_path)


# Backward-compatible alias used in tests
Neo4jClient = InMemoryGraphClient

__all__ = [
    "GraphClient",
    "InMemoryGraphClient",
    "Neo4jClient",
    "Neo4jGraphClient",
    "SqliteGraphClient",
    "create_graph_client",
]
