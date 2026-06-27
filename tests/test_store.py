"""Audit API parity tests."""

import os

import pytest
from fastapi.testclient import TestClient

from raphael_audit.app import app
from raphael_audit.core.event_builder import build_event

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def _postgres_migrations() -> None:
    if os.environ.get("RAPHAEL_DATABASE_URL"):
        from raphael_contracts.db import run_migrations

        run_migrations()


def test_timeline_and_verify() -> None:
    event = build_event(
        session_id="sess-1",
        user_id="usr-1",
        tool_version="test",
        event_type="module.commit",
        payload={"document_id": "doc-1"},
        project_id="default",
    )
    ingest = client.post(
        "/v1/audit/events",
        json={
            "event_type": event["event_type"],
            "payload": event["payload"],
            "session_id": event["session_id"],
            "user_id": event["user_id"],
            "project_id": event["project_id"],
        },
    )
    assert ingest.status_code == 200

    timeline = client.get("/v1/audit/timeline")
    assert timeline.status_code == 200
    assert "events" in timeline.json()

    verify = client.get("/v1/audit/verify")
    assert verify.status_code == 200
    body = verify.json()
    assert "valid" in body or body.get("status") in {"ok", "valid"}
