"""Silver projector tests."""

from pathlib import Path

from raphael_audit.core.silver_projector import handle_platform_event
from raphael_audit.core.silver_store import SilverStore


def test_project_workspace_commit(tmp_path: Path, monkeypatch) -> None:
    import raphael_audit.core.silver_projector as proj

    store = SilverStore(tmp_path / "silver.db")
    monkeypatch.setattr(proj, "_silver", store)
    handle_platform_event(
        {
            "type": "raphael.workspaces.commit",
            "time": "2026-01-01T00:00:00+00:00",
            "workspace_id": "default",
            "data": {
                "module_id": "m1",
                "hash": "abc",
                "branch": "main",
                "message": "fix",
            },
        }
    )
    state = store.get("m1")
    assert state is not None
    assert state["last_commit_hash"] == "abc"


def test_project_review_created(tmp_path: Path, monkeypatch) -> None:
    import raphael_audit.core.silver_projector as proj

    store = SilverStore(tmp_path / "silver.db")
    monkeypatch.setattr(proj, "_silver", store)
    handle_platform_event(
        {
            "type": "raphael.reviews.created",
            "workspace_id": "default",
            "data": {
                "id": "pr-1",
                "module_id": "m1",
                "title": "Test",
                "status": "open",
            },
        }
    )
    state = store.get("pr-1")
    assert state is not None
    assert state["title"] == "Test"
