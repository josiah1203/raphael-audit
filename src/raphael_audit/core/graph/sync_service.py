"""Graph Sync Service for micro-batching events into the knowledge graph."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from raphael_graph.calliope_graph.neo4j_client import InMemoryGraphClient

logger = logging.getLogger(__name__)


class GraphSyncService:
    """Syncs events to graph backend with optional background batching."""

    def __init__(
        self,
        graph: InMemoryGraphClient | Any,
        active_interval: int = 30,
        inactive_interval: int = 300,
        sync_immediate: bool = False,
    ) -> None:
        self.graph = graph
        self.active_interval = active_interval
        self.inactive_interval = inactive_interval
        self.sync_immediate = sync_immediate
        self._queue: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_activity = time.time()

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def enqueue(self, event: dict[str, Any]) -> None:
        if self.sync_immediate:
            self.sync_batch([event])
            return
        with self._lock:
            self._queue.append(event)
            self._last_activity = time.time()

    def sync_batch(self, events: list[dict[str, Any]]) -> None:
        """Public batch sync (agent adapter compatibility)."""
        self._sync_batch(events)

    def sync_event(self, event: dict[str, Any]) -> None:
        if hasattr(self.graph, "sync_event"):
            self.graph.sync_event(event)
        else:
            self._sync_batch([event])

    def _run(self) -> None:
        while not self._stop_event.is_set():
            batch: list[dict[str, Any]] = []
            with self._lock:
                if self._queue:
                    batch = list(self._queue)
                    self._queue.clear()
            if batch:
                self._sync_batch(batch)
            time.sleep(0.05 if batch else 0.1)

    def _sync_batch(self, batch: list[dict[str, Any]]) -> None:
        logger.info("Syncing micro-batch of %d events to graph", len(batch))
        for event in batch:
            payload = event.get("payload", {})
            event_type = event.get("event_type")

            if event_type == "geometry.feature_created":
                node_id = payload.get("feature_id")
                if node_id:
                    self.graph.upsert_node(
                        node_id,
                        ["Feature"],
                        {
                            "name": payload.get("feature_name"),
                            "type": payload.get("feature_type"),
                            "project_id": event.get("project_id"),
                            "created_at": event.get("timestamp_utc"),
                        },
                    )
                    doc_id = payload.get("document_id")
                    if doc_id:
                        self.graph.upsert_node(doc_id, ["Document"], {"id": doc_id})
                        self.graph.create_edge(
                            node_id,
                            doc_id,
                            "PART_OF",
                            {},
                            from_timestamp=event.get("timestamp_utc"),
                            to_timestamp="9999-12-31Z",
                        )

            causation_id = event.get("causation_id")
            if causation_id:
                current_id = event["event_id"]
                self.graph.upsert_node(current_id, ["Event"], {"type": event_type})
                self.graph.create_edge(
                    current_id,
                    causation_id,
                    "caused_by",
                    {"source": "explicit_tagging"},
                    from_timestamp=event.get("timestamp_utc"),
                    to_timestamp=event.get("timestamp_utc"),
                )

            if event_type == "geometry.assembly_mate_added":
                node_id = payload.get("joint_id")
                if node_id:
                    impact_set = self.graph.query_impact_set(node_id)
                    self.graph.upsert_node(node_id, ["Joint"], {"impact_cache": list(impact_set)})

            if event_type == "geometry.material_assigned":
                mat_id = payload.get("material_id")
                if mat_id:
                    risk_data = {"lead_time_weeks": 12, "status": "EOL_WARNING"}
                    self.graph.upsert_node(mat_id, ["Material"], {"supplier_risk": risk_data})
