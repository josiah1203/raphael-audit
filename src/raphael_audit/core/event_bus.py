"""Local SQLite event bus with in-process subscribers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from raphael_audit.core.store import EventStore

logger = logging.getLogger(__name__)

EventHandler = Callable[[dict[str, Any]], None]


class EventBus:
    """Append-only bronze bus with optional in-process normalization subscribers."""

    def __init__(self, store: EventStore | None = None) -> None:
        self._store = store or EventStore()
        self._subscribers: list[EventHandler] = []

    @property
    def store(self) -> EventStore:
        return self._store

    def subscribe(self, handler: EventHandler) -> None:
        self._subscribers.append(handler)

    def publish(self, event: dict[str, Any]) -> int | None:
        """Append to bronze and notify subscribers. Returns rowid or None if duplicate."""
        rowid = self._store.append(event)
        if rowid:
            for handler in self._subscribers:
                try:
                    handler(event)
                except Exception:
                    logger.exception("Event bus subscriber failed")
        return rowid

    def publish_batch(self, events: list[dict[str, Any]]) -> int:
        return sum(1 for e in events if self.publish(e))

    def close(self) -> None:
        self._store.close()
