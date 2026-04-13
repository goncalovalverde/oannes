"""Integration tests for /connectors API endpoints.

Connector tests use the CSV connector (no external dependencies) to exercise
real request paths. Network-bound connectors (Jira, Trello, etc.) are tested
via validation-only paths that don't require live credentials.
"""
from __future__ import annotations

import csv
import os
import tempfile

import pytest


class TestTestConnection:
    # ------------------------------------------------------------------
    # CSV connector — works offline
    # ------------------------------------------------------------------

    def test_csv_valid_file_returns_success(self, client):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=["item_key", "item_type", "created_at", "done_at"])
            writer.writeheader()
            writer.writerow({"item_key": "A-1", "item_type": "Story",
                             "created_at": "2024-01-01", "done_at": "2024-01-08"})
            tmp_path = f.name

        try:
            r = client.post("/api/connectors/test", json={
                "platform": "csv",
                "config": {"file_path": tmp_path},
            })
            assert r.status_code == 200
            body = r.json()
            assert "success" in body
            assert "message" in body
        finally:
            os.unlink(tmp_path)

    def test_csv_missing_file_returns_error_response(self, client):
        r = client.post("/api/connectors/test", json={
            "platform": "csv",
            "config": {"file_path": "/nonexistent/file.csv"},
        })
        assert r.status_code == 200  # endpoint never raises 500
        assert r.json()["success"] is False

    # ------------------------------------------------------------------
    # Config validation — missing required fields → 422
    # ------------------------------------------------------------------

    def test_jira_missing_required_fields_returns_422(self, client):
        r = client.post("/api/connectors/test", json={
            "platform": "jira",
            "config": {},          # missing url, email, api_token
        })
        assert r.status_code == 422

    def test_trello_missing_api_key_returns_422(self, client):
        r = client.post("/api/connectors/test", json={
            "platform": "trello",
            "config": {"token": "tok"},   # missing api_key
        })
        assert r.status_code == 422

    def test_azure_devops_missing_org_returns_422(self, client):
        r = client.post("/api/connectors/test", json={
            "platform": "azure_devops",
            "config": {"project": "P", "personal_access_token": "pat"},
        })
        assert r.status_code == 422

    def test_unknown_platform_still_returns_200(self, client):
        """Unknown platform: validator has no model — passes through to connector factory."""
        r = client.post("/api/connectors/test", json={
            "platform": "unknown_platform",
            "config": {},
        })
        # Connector factory raises → endpoint catches and returns success=False
        assert r.status_code == 200
        assert r.json()["success"] is False

    # ------------------------------------------------------------------
    # Response shape
    # ------------------------------------------------------------------

    def test_response_has_required_keys(self, client):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            csv.DictWriter(f, fieldnames=["item_key"]).writeheader()
            tmp_path = f.name

        try:
            r = client.post("/api/connectors/test", json={
                "platform": "csv",
                "config": {"file_path": tmp_path},
            })
            body = r.json()
            assert "success" in body
            assert "message" in body
            assert "projects_found" in body
            assert isinstance(body["projects_found"], list)
        finally:
            os.unlink(tmp_path)


class TestDiscoverStatuses:
    def test_csv_returns_status_list(self, client):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            writer = csv.DictWriter(f, fieldnames=["item_key", "status"])
            writer.writeheader()
            writer.writerow({"item_key": "A-1", "status": "Done"})
            tmp_path = f.name

        try:
            r = client.post("/api/connectors/discover-statuses", json={
                "platform": "csv",
                "config": {"file_path": tmp_path},
                "board_id": "",
            })
            assert r.status_code == 200
            assert "statuses" in r.json()
            assert isinstance(r.json()["statuses"], list)
        finally:
            os.unlink(tmp_path)

    def test_failed_discover_returns_empty_list(self, client):
        r = client.post("/api/connectors/discover-statuses", json={
            "platform": "csv",
            "config": {"file_path": "/nonexistent/file.csv"},
            "board_id": "",
        })
        assert r.status_code == 200
        assert r.json()["statuses"] == []
