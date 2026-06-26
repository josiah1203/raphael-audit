"""AI Inference layer for relationship suggestions and feedback loops."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InferenceLayer:
    """Simulates AI inference for graph relationships."""

    def __init__(self):
        self._feedback_store: list[dict[str, Any]] = []

    def suggest_relationships(self, event: dict[str, Any], context: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Suggest relationships based on co-occurrence or similarity.
        Implements 'co_occurred_with' edge suggestions.
        """
        suggestions = []
        payload = event.get("payload", {})
        
        # Simple rule: if two features are modified within the same session close in time
        for prior in context:
            if prior.get("session_id") == event.get("session_id"):
                if prior.get("event_id") != event.get("event_id"):
                    suggestions.append({
                        "from_id": event["event_id"],
                        "to_id": prior["event_id"],
                        "type": "co_occurred_with",
                        "confidence": 0.85,
                        "reason": "Temporal co-occurrence in same session"
                    })
        
        return suggestions

    def record_feedback(self, suggestion_id: str, approved: bool, user_id: str = "local") -> None:
        """Feedback loop: approve/reject AI suggestions to refine model."""
        feedback = {
            "suggestion_id": suggestion_id,
            "approved": approved,
            "user_id": user_id,
            "timestamp": "2026-06-10T12:36:00Z",
        }
        self._feedback_store.append(feedback)
        logger.info(
            "Recorded feedback for AI suggestion %s: %s",
            suggestion_id,
            "Approved" if approved else "Rejected",
        )

    def suggest(self, event: dict[str, Any], context: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """Agent compatibility alias."""
        return self.suggest_relationships(event, context or [])
