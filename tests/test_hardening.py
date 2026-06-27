"""Prometheus hardening and metrics exporter tests."""

from fastapi.testclient import TestClient

from raphael_audit.app import app
from raphael_audit.core.observability.hardening import (
    AUDIT_EVENTS_INGESTED,
    AUDIT_VERIFY_RUNS,
    MultiTenancyGuard,
    ObservabilityEngine,
)


def test_metrics_endpoint_exports_audit_counters() -> None:
    client = TestClient(app)
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "raphael_audit_events_ingested_total" in res.text
    assert "raphael_audit_verify_runs_total" in res.text


def test_ingest_increments_prometheus_counter() -> None:
    client = TestClient(app)
    before = AUDIT_EVENTS_INGESTED.labels(event_type="module.commit")._value.get()
    ingest = client.post(
        "/v1/audit/events",
        json={
            "event_type": "module.commit",
            "payload": {"document_id": "prom-doc"},
            "session_id": "sess-prom",
            "user_id": "usr-prom",
            "project_id": "default",
        },
    )
    assert ingest.status_code == 200
    after = AUDIT_EVENTS_INGESTED.labels(event_type="module.commit")._value.get()
    assert after >= before + 1


def test_verify_increments_counter() -> None:
    client = TestClient(app)
    before = AUDIT_VERIFY_RUNS.labels(result="valid")._value.get()
    verify = client.get("/v1/audit/verify")
    assert verify.status_code == 200
    after = AUDIT_VERIFY_RUNS.labels(result="valid")._value.get()
    assert after >= before + 1


def test_observability_engine_trace_counter() -> None:
    engine = ObservabilityEngine()
    engine.start_trace("ingest")
    client = TestClient(app)
    res = client.get("/metrics")
    assert "raphael_audit_traces_started_total" in res.text


def test_quota_denial_counter() -> None:
    guard = MultiTenancyGuard()
    guard.quotas["tenant-x"] = {"rate_limit": 1, "memory_mb": 512}
    assert guard.enforce_quota("tenant-x", "ingest") is True
    assert guard.enforce_quota("tenant-x", "ingest") is False
    client = TestClient(app)
    res = client.get("/metrics")
    assert "raphael_audit_quota_denied_total" in res.text
