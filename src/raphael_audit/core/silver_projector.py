"""Silver projection from Kafka platform events."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from raphael_audit.core.silver_store import SilverStore

logger = logging.getLogger(__name__)

_silver = SilverStore()
_GRAPH_URL = os.environ.get("RAPHAEL_GRAPH_URL", "http://127.0.0.1:8100").rstrip("/")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sync_graph_edge(from_id: str, to_id: str, edge_type: str) -> None:
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{_GRAPH_URL}/v1/graph/edges",
                json={"from_id": from_id, "to_id": to_id, "edge_type": edge_type},
            )
    except httpx.HTTPError:
        logger.debug("Graph sync skipped for %s -> %s", from_id, to_id)


def handle_platform_event(envelope: dict[str, Any]) -> None:
    """Project platform Kafka events into silver store and sync graph edges."""
    event_type = envelope.get("type", "")
    data = envelope.get("data") or {}
    workspace_id = envelope.get("workspace_id") or data.get("workspace_id") or "default"
    updated_at = envelope.get("time") or _utc_now()

    if event_type == "raphael.workspaces.commit":
        module_id = data.get("module_id", "")
        if module_id:
            _silver.upsert(
                module_id,
                workspace_id,
                "module",
                {
                    "last_commit_hash": data.get("hash"),
                    "last_branch": data.get("branch"),
                    "last_message": data.get("message"),
                    "intent_summary": data.get("intent_summary"),
                },
                updated_at,
            )

    elif event_type == "raphael.workspaces.merge":
        module_id = data.get("module_id", "")
        if module_id:
            _silver.upsert(
                module_id,
                workspace_id,
                "module",
                {
                    "last_merge": {
                        "source": data.get("source"),
                        "target": data.get("target"),
                        "hash": data.get("hash"),
                        "status": data.get("status"),
                    }
                },
                updated_at,
            )

    elif event_type == "raphael.workspaces.fork":
        source_id = data.get("source_module_id", "")
        new_id = data.get("new_module_id", "")
        if source_id and new_id:
            _silver.upsert(new_id, workspace_id, "module", {"forked_from": source_id, "name": data.get("name")}, updated_at)
            _sync_graph_edge(new_id, source_id, "forked_from")

    elif event_type == "raphael.workspaces.slice":
        source_id = data.get("source_module_id", "")
        new_id = data.get("new_module_id", "")
        if source_id and new_id:
            _silver.upsert(
                new_id,
                workspace_id,
                "module",
                {"sliced_from": source_id, "name": data.get("name"), "scope": data.get("scope")},
                updated_at,
            )
            _sync_graph_edge(new_id, source_id, "sliced_from")

    elif event_type == "raphael.reviews.created":
        review_id = data.get("id", "")
        if review_id:
            _silver.upsert(review_id, workspace_id, "review", data, updated_at)
            module_id = data.get("module_id") or data.get("repo_id")
            if module_id:
                _sync_graph_edge(review_id, module_id, "review_for")

    elif event_type == "raphael.reviews.merged":
        review_id = data.get("review_id", "")
        if review_id:
            existing = _silver.get(review_id) or {}
            existing.update({"status": "merged", **{k: v for k, v in data.items() if k != "review_id"}})
            _silver.upsert(review_id, workspace_id, "review", existing, updated_at)

    elif event_type == "raphael.artifacts.ingest":
        artifact_id = data.get("artifact_id", "")
        if artifact_id:
            _silver.upsert(artifact_id, workspace_id, "artifact", data, updated_at)
            module_id = data.get("module_id")
            if module_id:
                _sync_graph_edge(artifact_id, module_id, "artifact_of")

    elif event_type.startswith("raphael.audit."):
        event_id = data.get("event_id", envelope.get("id", ""))
        if event_id:
            _silver.upsert(
                event_id,
                workspace_id,
                "audit_event",
                {"event_type": data.get("event_type"), "payload": data.get("payload")},
                updated_at,
            )
