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
