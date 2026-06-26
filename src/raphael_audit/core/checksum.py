"""Canonical event checksum computation."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_checksum(event_without_checksum: dict[str, Any]) -> str:
    """Return ``sha256:<hex>`` checksum for an event dict without checksum field."""
    payload = {k: v for k, v in event_without_checksum.items() if k != "checksum"}
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
