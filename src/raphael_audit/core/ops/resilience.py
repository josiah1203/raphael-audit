"""Operational Excellence & Infrastructure hardening utilities."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class CapacityAlerting:
    """Predictive alerting using linear regression (simulation)."""

    def __init__(self, current_usage: float, growth_rate: float):
        self.current_usage = current_usage
        self.growth_rate = growth_rate # units per day

    def predict_90_day_projection(self) -> float:
        """90-day projection of capacity usage."""
        return self.current_usage + (self.growth_rate * 90)

    def check_alerts(self, threshold: float) -> list[str]:
        projection = self.predict_90_day_projection()
        if projection > threshold:
            return [f"ALERT: Projected usage {projection:.1f} exceeds threshold {threshold:.1f} in 90 days"]
        return []


class GracefulDegradation:
    """Contracts for graceful degradation under load or failure."""

    @staticmethod
    def get_policy(layer: str, status: str) -> dict[str, Any]:
        """
        Define 'Graceful Degradation' contracts for each layer.
        Example: local buffering when Kafka is down.
        """
        policies = {
            "ingestion": {
                "healthy": "direct_transmit",
                "kafka_down": "local_sqlite_buffer",
                "disk_full": "drop_non_critical"
            },
            "graph_sync": {
                "healthy": "30s_active",
                "high_load": "5m_inactive_only",
                "neo4j_down": "retry_backoff"
            }
        }
        return {"policy": policies.get(layer, {}).get(status, "default")}


class IntegrityChecks:
    """Cryptographic signed bundles and manifest checksums."""

    @staticmethod
    def verify_bundle(bundle: dict[str, Any], signature: str) -> bool:
        """Simulate cryptographically signed update bundles verification."""
        # In real impl, would use RSA/ECDSA
        logger.info(f"Verifying signed bundle with manifest checksum {bundle.get('checksum')}")
        return signature.startswith("sig:")
