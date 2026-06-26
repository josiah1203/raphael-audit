"""Audit API parity tests."""

from fastapi.testclient import TestClient

from raphael_audit.app import app
from raphael_audit.core.event_builder import build_event
from raphael_audit.core.store import EventStore

client = TestClient(app)


def test_timeline_and_verify() -> None:
    store = EventStore()
    event = build_event(
        session_id="sess-1",
        user_id="usr-1",
        tool_version="test",
        event_type="module.commit",
        payload={"document_id": "doc-1"},
        project_id="default",
    )
    store.append(event)

    timeline = client.get("/v1/audit/timeline")
    assert timeline.status_code == 200
    assert "events" in timeline.json()

    verify = client.get("/v1/audit/verify")
    assert verify.status_code == 200
    body = verify.json()
    assert "valid" in body or body.get("status") in {"ok", "valid"}
