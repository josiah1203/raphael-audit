"""Deterministic Event ID scheme."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_deterministic_id(
    tenant_id: str,
    tool_id: str,
    object_id: str,
    change_fingerprint: str,
    timestamp_rounded: str,
    sequence: int = 0,
) -> str:
    """
    Build Deterministic Event ID scheme:
    SHA-256 hash of (tenant_id, tool_id, object_id, change_fingerprint, timestamp_rounded)
    Sequence suffix for sub-second logical duplicates.
    """
    payload = {
        "tenant_id": tenant_id,
        "tool_id": tool_id,
        "object_id": object_id,
        "change_fingerprint": change_fingerprint,
        "timestamp_rounded": timestamp_rounded,
    }
    # Stable JSON representation
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    base_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    
    if sequence > 0:
        return f"{base_hash}-{sequence}"
    return base_hash
