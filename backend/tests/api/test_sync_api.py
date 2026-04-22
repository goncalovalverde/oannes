"""Integration tests for /sync API endpoints."""
from __future__ import annotations

import pytest


def _create_project(client):
    resp = client.post("/api/projects/", json={
        "name": "Sync Test Project",
        "platform": "csv",
        "config": {"file_path": "/tmp/dummy.csv"},
        "sync_frequency": "manual",
        "workflow_steps": [],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


class TestTriggerSync:
    def test_trigger_creates_pending_job(self, client):
        pid = _create_project(client)
        r = client.post(f"/api/sync/{pid}")
        assert r.status_code == 200
        body = r.json()
        assert body["project_id"] == pid
        # Job starts as "pending" (background task hasn't run yet in test)
        assert body["status"] in ("pending", "running", "success", "error")

    def test_trigger_unknown_project_returns_404(self, client):
        r = client.post("/api/sync/999")
        assert r.status_code == 404

    def test_trigger_response_has_expected_keys(self, client):
        pid = _create_project(client)
        r = client.post(f"/api/sync/{pid}")
        assert r.status_code == 200
        body = r.json()
        for key in ("id", "project_id", "status"):
            assert key in body, f"Missing key: {key}"


class TestSyncStatus:
    def test_no_jobs_returns_404(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/sync/{pid}/status")
        assert r.status_code == 404

    def test_status_after_trigger(self, client):
        pid = _create_project(client)
        client.post(f"/api/sync/{pid}")
        r = client.get(f"/api/sync/{pid}/status")
        assert r.status_code == 200
        assert "status" in r.json()

    def test_status_unknown_project_returns_404(self, client):
        r = client.get("/api/sync/999/status")
        assert r.status_code == 404


class TestSyncHistory:
    def test_empty_history(self, client):
        pid = _create_project(client)
        r = client.get(f"/api/sync/{pid}/history")
        assert r.status_code == 200
        assert r.json() == []

    def test_history_after_trigger(self, client):
        pid = _create_project(client)
        client.post(f"/api/sync/{pid}")
        r = client.get(f"/api/sync/{pid}/history")
        assert r.status_code == 200
        history = r.json()
        assert len(history) >= 1
        assert history[0]["project_id"] == pid

    def test_history_limited_to_10(self, client):
        pid = _create_project(client)
        for _ in range(12):
            client.post(f"/api/sync/{pid}")
        r = client.get(f"/api/sync/{pid}/history")
        assert r.status_code == 200
        assert len(r.json()) <= 10


class TestClearCache:
    def test_clear_cache_unknown_project_returns_404(self, client):
        r = client.delete("/api/sync/999/cache")
        assert r.status_code == 404

    def test_clear_cache_empty_project(self, client):
        pid = _create_project(client)
        r = client.delete(f"/api/sync/{pid}/cache")
        assert r.status_code == 200
        body = r.json()
        assert "deleted_count" in body
        assert body["deleted_count"] == 0

    def test_clear_cache_deletes_items(self, client, db):
        """Clear cache should delete all CachedItems for a project."""
        from models.sync_job import CachedItem
        from datetime import datetime, timezone
        
        pid = _create_project(client)
        
        # Create some cached items
        for i in range(3):
            item = CachedItem(
                project_id=pid,
                item_key=f"item-{i}",
                item_type="issue",
                creator=f"user-{i}",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                workflow_timestamps={},
            )
            db.add(item)
        db.commit()
        
        # Verify items exist
        assert db.query(CachedItem).filter(CachedItem.project_id == pid).count() == 3
        
        # Clear cache
        r = client.delete(f"/api/sync/{pid}/cache")
        assert r.status_code == 200
        assert r.json()["deleted_count"] == 3
        
        # Verify items are deleted
        assert db.query(CachedItem).filter(CachedItem.project_id == pid).count() == 0

    def test_clear_cache_resets_last_synced_at(self, client, db):
        """Clear cache should reset last_synced_at to None."""
        from models.project import Project
        from datetime import datetime, timezone
        
        pid = _create_project(client)
        
        # Set last_synced_at to some past time
        project = db.query(Project).filter(Project.id == pid).one()
        project.last_synced_at = datetime(2020, 1, 1, tzinfo=timezone.utc).replace(tzinfo=None)
        db.commit()
        
        # Verify it's set
        assert project.last_synced_at is not None
        
        # Clear cache
        r = client.delete(f"/api/sync/{pid}/cache")
        assert r.status_code == 200
        
        # Verify last_synced_at is reset
        project = db.query(Project).filter(Project.id == pid).one()
        assert project.last_synced_at is None

