"""Integration tests for /projects API endpoints."""
import pytest


def _create_project(client, name="Test Project", platform="csv"):
    payload = {
        "name": name,
        "platform": platform,
        "config": {"file_path": "/tmp/test.csv"},
        "workflow_steps": [
            {"display_name": "Backlog",     "stage": "queue", "position": 0, "source_statuses": ["Backlog"]},
            {"display_name": "In Progress", "stage": "start", "position": 1, "source_statuses": ["In Progress"]},
            {"display_name": "Done",        "stage": "done",  "position": 2, "source_statuses": ["Done"]},
        ]
    }
    return client.post("/api/projects", json=payload)


class TestProjectsCRUD:
    def test_create_project_returns_201(self, client):
        resp = _create_project(client)
        assert resp.status_code in (200, 201), resp.text
        data = resp.json()
        assert data["name"] == "Test Project"
        assert data["platform"] == "csv"
        assert "id" in data

    def test_list_projects_empty(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_projects_after_create(self, client):
        _create_project(client, name="Project Alpha")
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Project Alpha" in names

    def test_get_project_by_id(self, client):
        create_resp = _create_project(client, name="Project Beta")
        project_id = create_resp.json()["id"]
        resp = client.get(f"/api/projects/{project_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    def test_get_nonexistent_project_returns_404(self, client):
        resp = client.get("/api/projects/999999")
        assert resp.status_code == 404

    def test_update_project_name(self, client):
        create_resp = _create_project(client, name="Old Name")
        project_id = create_resp.json()["id"]
        resp = client.put(f"/api/projects/{project_id}", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_project(self, client):
        create_resp = _create_project(client, name="To Delete")
        project_id = create_resp.json()["id"]
        del_resp = client.delete(f"/api/projects/{project_id}")
        assert del_resp.status_code in (200, 204)
        get_resp = client.get(f"/api/projects/{project_id}")
        assert get_resp.status_code == 404

    def test_config_not_exposed_as_plaintext(self, client):
        """The API should return config but the secret fields must not appear as cleartext in the DB.
        We can only verify that round-tripping works correctly (encrypt + decrypt)."""
        create_resp = _create_project(client, name="Encrypted Project")
        assert create_resp.status_code in (200, 201)
        project_id = create_resp.json()["id"]
        get_resp = client.get(f"/api/projects/{project_id}")
        config = get_resp.json().get("config", {})
        # The decrypted value should match what we put in
        assert config.get("file_path") == "/tmp/test.csv"

    def test_workflow_steps_created(self, client):
        resp = _create_project(client)
        project_id = resp.json()["id"]
        get_resp = client.get(f"/api/projects/{project_id}")
        steps = get_resp.json().get("workflow_steps", [])
        assert len(steps) == 3
        names = [s["display_name"] for s in steps]
        assert "Backlog" in names
        assert "Done" in names


# ---------------------------------------------------------------------------
# Update validation
# ---------------------------------------------------------------------------

class TestProjectUpdate:
    def test_update_platform_to_jira(self, client):
        create_resp = _create_project(client)
        pid = create_resp.json()["id"]
        r = client.put(f"/api/projects/{pid}", json={"platform": "jira"})
        assert r.status_code == 200
        assert r.json()["platform"] == "jira"

    def test_update_unknown_project_returns_404(self, client):
        r = client.put("/api/projects/999999", json={"name": "Ghost"})
        assert r.status_code == 404

    def test_update_invalid_platform_returns_422(self, client):
        create_resp = _create_project(client)
        pid = create_resp.json()["id"]
        r = client.put(f"/api/projects/{pid}", json={"platform": "totally_fake"})
        assert r.status_code == 422

    def test_update_workflow_steps_replaces_all(self, client):
        create_resp = _create_project(client)
        pid = create_resp.json()["id"]
        new_steps = [
            {"display_name": "Todo",  "stage": "queue", "position": 0, "source_statuses": ["Todo"]},
            {"display_name": "Done",  "stage": "done",  "position": 1, "source_statuses": ["Done"]},
        ]
        r = client.put(f"/api/projects/{pid}", json={"workflow_steps": new_steps})
        assert r.status_code == 200
        steps = r.json()["workflow_steps"]
        assert len(steps) == 2
        assert {s["display_name"] for s in steps} == {"Todo", "Done"}

    def test_partial_update_does_not_clear_other_fields(self, client):
        """Updating only the name must leave platform and config unchanged."""
        create_resp = _create_project(client, name="Original")
        pid = create_resp.json()["id"]
        original_platform = create_resp.json()["platform"]
        r = client.put(f"/api/projects/{pid}", json={"name": "Renamed"})
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Renamed"
        assert body["platform"] == original_platform


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestProjectDelete:
    def test_delete_unknown_project_returns_404(self, client):
        r = client.delete("/api/projects/999999")
        assert r.status_code == 404

    def test_deleted_project_not_in_list(self, client):
        pid = _create_project(client, name="ToRemove").json()["id"]
        client.delete(f"/api/projects/{pid}")
        names = [p["name"] for p in client.get("/api/projects").json()]
        assert "ToRemove" not in names

    def test_delete_removes_workflow_steps(self, client, db):
        """Cascade: deleting a project must also remove its workflow steps."""
        from models.project import WorkflowStep
        pid = _create_project(client).json()["id"]
        client.delete(f"/api/projects/{pid}")
        steps = db.query(WorkflowStep).filter(WorkflowStep.project_id == pid).all()
        assert steps == []


# ---------------------------------------------------------------------------
# Create validation
# ---------------------------------------------------------------------------

class TestProjectCreateValidation:
    def test_create_invalid_platform_returns_422(self, client):
        r = client.post("/api/projects", json={
            "name": "Bad", "platform": "oracle_db",
            "config": {},
        })
        assert r.status_code == 422

    def test_create_invalid_stage_in_workflow_returns_422(self, client):
        r = client.post("/api/projects", json={
            "name": "Bad", "platform": "csv",
            "config": {"file_path": "/f.csv"},
            "workflow_steps": [
                {"display_name": "Backlog", "stage": "invalid_stage",
                 "position": 0, "source_statuses": []}
            ],
        })
        assert r.status_code == 422

    def test_create_missing_name_returns_422(self, client):
        r = client.post("/api/projects", json={
            "platform": "csv", "config": {},
        })
        assert r.status_code == 422

    def test_create_empty_name_returns_422(self, client):
        """Empty string name should be rejected — a project must have a non-empty name."""
        r = client.post("/api/projects", json={
            "name": "", "platform": "csv", "config": {},
        })
        assert r.status_code == 422, f"Expected 422 for empty name, got {r.status_code}: {r.text}"

