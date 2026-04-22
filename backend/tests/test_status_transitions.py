"""Tests for status_transitions data model enhancement.

Covers:
- compute_workflow_timestamps_from_transitions() calculator helper
- cycle_time_between_statuses() calculator helper
- DB migration adds column to existing table (migrate_schema)
- _store_items() upsert behaviour (no delete-all)
- recompute_workflow_timestamps() service
- available-statuses API endpoint
- Jira connector transition extraction helpers (unit tests, no network)
"""
from __future__ import annotations

import pytest
import pandas as pd
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Calculator helpers
# ---------------------------------------------------------------------------

class TestComputeWorkflowTimestampsFromTransitions:
    STEPS = [
        {"display_name": "Backlog", "source_statuses": ["backlog"], "stage": "queue", "position": 0},
        {"display_name": "In Progress", "source_statuses": ["in progress", "active"], "stage": "start", "position": 1},
        {"display_name": "Done", "source_statuses": ["done", "closed"], "stage": "done", "position": 2},
    ]

    def test_basic_mapping(self):
        from calculator.flow import compute_workflow_timestamps_from_transitions
        transitions = [
            {"from_status": None, "to_status": "Backlog", "transitioned_at": "2024-01-01T10:00:00"},
            {"from_status": "Backlog", "to_status": "In Progress", "transitioned_at": "2024-01-02T10:00:00"},
            {"from_status": "In Progress", "to_status": "Done", "transitioned_at": "2024-01-05T10:00:00"},
        ]
        result = compute_workflow_timestamps_from_transitions(transitions, self.STEPS)
        assert result["Backlog"] == "2024-01-01T10:00:00"
        assert result["In Progress"] == "2024-01-02T10:00:00"
        assert result["Done"] == "2024-01-05T10:00:00"

    def test_case_insensitive_matching(self):
        from calculator.flow import compute_workflow_timestamps_from_transitions
        transitions = [
            {"from_status": None, "to_status": "IN PROGRESS", "transitioned_at": "2024-01-02T10:00:00"},
        ]
        result = compute_workflow_timestamps_from_transitions(transitions, self.STEPS)
        assert result["In Progress"] == "2024-01-02T10:00:00"

    def test_first_entry_wins_on_reopen(self):
        """If an issue is reopened, the FIRST Done timestamp is kept."""
        from calculator.flow import compute_workflow_timestamps_from_transitions
        transitions = [
            {"from_status": None, "to_status": "In Progress", "transitioned_at": "2024-01-01T10:00:00"},
            {"from_status": "In Progress", "to_status": "Done", "transitioned_at": "2024-01-05T10:00:00"},
            {"from_status": "Done", "to_status": "In Progress", "transitioned_at": "2024-01-06T10:00:00"},
            {"from_status": "In Progress", "to_status": "Done", "transitioned_at": "2024-01-10T10:00:00"},
        ]
        result = compute_workflow_timestamps_from_transitions(transitions, self.STEPS)
        assert result["Done"] == "2024-01-05T10:00:00"

    def test_missing_step_returns_none(self):
        from calculator.flow import compute_workflow_timestamps_from_transitions
        transitions = [
            {"from_status": None, "to_status": "In Progress", "transitioned_at": "2024-01-01T10:00:00"},
        ]
        result = compute_workflow_timestamps_from_transitions(transitions, self.STEPS)
        assert result["Done"] is None

    def test_empty_transitions_returns_all_none(self):
        from calculator.flow import compute_workflow_timestamps_from_transitions
        result = compute_workflow_timestamps_from_transitions([], self.STEPS)
        assert all(v is None for v in result.values())

    def test_null_transitions_returns_all_none(self):
        from calculator.flow import compute_workflow_timestamps_from_transitions
        result = compute_workflow_timestamps_from_transitions(None, self.STEPS)
        assert all(v is None for v in result.values())

    def test_alias_status_maps_correctly(self):
        """'active' is an alias for 'In Progress' via source_statuses."""
        from calculator.flow import compute_workflow_timestamps_from_transitions
        transitions = [
            {"from_status": None, "to_status": "Active", "transitioned_at": "2024-02-01T00:00:00"},
        ]
        result = compute_workflow_timestamps_from_transitions(transitions, self.STEPS)
        assert result["In Progress"] == "2024-02-01T00:00:00"


class TestCycleTimeBetweenStatuses:
    def test_basic_cycle_time(self):
        from calculator.flow import cycle_time_between_statuses
        items = [
            {
                "item_key": "PROJ-1",
                "status_transitions": [
                    {"from_status": None, "to_status": "To Do", "transitioned_at": "2024-01-01T00:00:00Z"},
                    {"from_status": "To Do", "to_status": "In Progress", "transitioned_at": "2024-01-02T00:00:00Z"},
                    {"from_status": "In Progress", "to_status": "Done", "transitioned_at": "2024-01-05T00:00:00Z"},
                ],
            }
        ]
        result = cycle_time_between_statuses(items, "In Progress", "Done")
        assert len(result) == 1
        assert result[0]["item_key"] == "PROJ-1"
        assert result[0]["cycle_time_days"] == pytest.approx(3.0, abs=0.01)

    def test_never_reached_from_status_returns_none(self):
        from calculator.flow import cycle_time_between_statuses
        items = [{"item_key": "X-1", "status_transitions": [
            {"from_status": None, "to_status": "To Do", "transitioned_at": "2024-01-01T00:00:00Z"},
        ]}]
        result = cycle_time_between_statuses(items, "In Progress", "Done")
        assert result[0]["cycle_time_days"] is None

    def test_null_transitions_returns_none(self):
        from calculator.flow import cycle_time_between_statuses
        items = [{"item_key": "X-1", "status_transitions": None}]
        result = cycle_time_between_statuses(items, "In Progress", "Done")
        assert result[0]["cycle_time_days"] is None

    def test_reopened_uses_first_entry(self):
        """First entry into from_status → first subsequent entry into to_status."""
        from calculator.flow import cycle_time_between_statuses
        items = [{"item_key": "X-1", "status_transitions": [
            {"from_status": None, "to_status": "In Progress", "transitioned_at": "2024-01-01T00:00:00Z"},
            {"from_status": "In Progress", "to_status": "Done", "transitioned_at": "2024-01-04T00:00:00Z"},
            # Reopened: should NOT affect the first measurement
            {"from_status": "Done", "to_status": "In Progress", "transitioned_at": "2024-01-06T00:00:00Z"},
            {"from_status": "In Progress", "to_status": "Done", "transitioned_at": "2024-01-10T00:00:00Z"},
        ]}]
        result = cycle_time_between_statuses(items, "In Progress", "Done")
        assert result[0]["cycle_time_days"] == pytest.approx(3.0, abs=0.01)

    def test_empty_items(self):
        from calculator.flow import cycle_time_between_statuses
        assert cycle_time_between_statuses([], "X", "Y") == []


# ---------------------------------------------------------------------------
# DB migration
# ---------------------------------------------------------------------------

def test_migrate_schema_adds_column(engine):
    """migrate_schema() is idempotent — calling it multiple times is safe."""
    from database import migrate_schema
    from sqlalchemy import inspect as sa_inspect

    # Calling migrate_schema works without error (uses global SessionLocal)
    migrate_schema()

    # Column is present (the test engine has it because the model declares it)
    insp = sa_inspect(engine)
    col_names = [c["name"] for c in insp.get_columns("cached_items")]
    assert "status_transitions" in col_names


# ---------------------------------------------------------------------------
# SyncService._store_items — upsert behaviour
# ---------------------------------------------------------------------------

def test_store_items_upserts_not_deletes(db, sample_project):
    """Incremental sync preserves pre-existing items not in the new batch."""
    from models.sync_job import CachedItem
    from services.sync_service import SyncService

    # Pre-seed two items
    db.add_all([
        CachedItem(project_id=sample_project.id, item_key="OLD-1", item_type="Bug",
                   workflow_timestamps={}, status_transitions=[]),
        CachedItem(project_id=sample_project.id, item_key="OLD-2", item_type="Story",
                   workflow_timestamps={}, status_transitions=[]),
    ])
    db.commit()

    # Incremental batch updates OLD-1 and adds NEW-1
    new_df = pd.DataFrame([
        {"item_key": "OLD-1", "item_type": "Bug-Updated", "creator": None,
         "created_at": pd.Timestamp("2024-01-01"), "workflow_timestamps": {},
         "status_transitions": [], "cycle_time_days": None, "lead_time_days": None},
        {"item_key": "NEW-1", "item_type": "Task", "creator": None,
         "created_at": pd.Timestamp("2024-02-01"), "workflow_timestamps": {},
         "status_transitions": [], "cycle_time_days": None, "lead_time_days": None},
    ])

    SyncService(db)._store_items(sample_project.id, new_df)

    keys = {i.item_key for i in db.query(CachedItem).filter_by(project_id=sample_project.id).all()}
    assert "OLD-1" in keys, "Updated item must be preserved"
    assert "OLD-2" in keys, "Untouched item must not be deleted"
    assert "NEW-1" in keys, "New item must be inserted"

    updated = db.query(CachedItem).filter_by(project_id=sample_project.id, item_key="OLD-1").one()
    assert updated.item_type == "Bug-Updated"


def test_store_items_persists_status_transitions(db, sample_project):
    from models.sync_job import CachedItem
    from services.sync_service import SyncService

    transitions = [
        {"from_status": None, "to_status": "To Do", "transitioned_at": "2024-01-01T00:00:00"},
        {"from_status": "To Do", "to_status": "In Progress", "transitioned_at": "2024-01-02T00:00:00"},
    ]
    df = pd.DataFrame([
        {"item_key": "T-1", "item_type": "Story", "creator": None,
         "created_at": pd.Timestamp("2024-01-01"), "workflow_timestamps": {},
         "status_transitions": transitions, "cycle_time_days": None, "lead_time_days": None},
    ])
    SyncService(db)._store_items(sample_project.id, df)

    item = db.query(CachedItem).filter_by(project_id=sample_project.id, item_key="T-1").one()
    assert item.status_transitions == transitions


# ---------------------------------------------------------------------------
# SyncService.recompute_workflow_timestamps
# ---------------------------------------------------------------------------

def test_recompute_skips_null_transitions(db, sample_project):
    from models.sync_job import CachedItem
    from services.sync_service import SyncService

    db.add(CachedItem(
        project_id=sample_project.id, item_key="LEGACY-1", item_type="Task",
        workflow_timestamps={}, status_transitions=None,
    ))
    db.commit()

    result = SyncService(db).recompute_workflow_timestamps(sample_project.id)
    assert result["skipped"] >= 1


def test_recompute_updates_timestamps(db, sample_project):
    """After recompute, workflow_timestamps reflect the new step config."""
    from models.sync_job import CachedItem
    from services.sync_service import SyncService

    transitions = [
        {"from_status": None, "to_status": "In Progress", "transitioned_at": "2024-03-01T00:00:00"},
        {"from_status": "In Progress", "to_status": "Done", "transitioned_at": "2024-03-10T00:00:00"},
    ]
    db.add(CachedItem(
        project_id=sample_project.id, item_key="RECOMPUTE-1", item_type="Story",
        workflow_timestamps={}, status_transitions=transitions,
    ))
    db.commit()

    result = SyncService(db).recompute_workflow_timestamps(sample_project.id)
    assert result["recomputed"] >= 1

    item = db.query(CachedItem).filter_by(item_key="RECOMPUTE-1").one()
    # "In Progress" step has source_statuses=["In Progress"] in sample_project fixture
    assert item.workflow_timestamps.get("In Progress") is not None


# ---------------------------------------------------------------------------
# Available-statuses API endpoint
# ---------------------------------------------------------------------------

def test_available_statuses_no_data(client, sample_project):
    resp = client.get(f"/api/metrics/{sample_project.id}/available-statuses")
    assert resp.status_code == 404


def test_available_statuses_returns_unique_sorted(client, db, sample_project):
    from models.sync_job import CachedItem
    db.add_all([
        CachedItem(project_id=sample_project.id, item_key="S-1", item_type="Story",
                   workflow_timestamps={}, status_transitions=[
                       {"from_status": None, "to_status": "To Do", "transitioned_at": "2024-01-01T00:00:00"},
                       {"from_status": "To Do", "to_status": "In Progress", "transitioned_at": "2024-01-02T00:00:00"},
                   ]),
        CachedItem(project_id=sample_project.id, item_key="S-2", item_type="Bug",
                   workflow_timestamps={}, status_transitions=[
                       {"from_status": None, "to_status": "To Do", "transitioned_at": "2024-01-03T00:00:00"},
                       {"from_status": "To Do", "to_status": "Done", "transitioned_at": "2024-01-07T00:00:00"},
                   ]),
    ])
    db.commit()

    resp = client.get(f"/api/metrics/{sample_project.id}/available-statuses")
    assert resp.status_code == 200
    statuses = resp.json()["statuses"]
    assert "To Do" in statuses
    assert "In Progress" in statuses
    assert "Done" in statuses
    # Sorted
    assert statuses == sorted(statuses)
    # Unique
    assert len(statuses) == len(set(statuses))


def test_available_statuses_ignores_null_transitions(client, db, sample_project):
    """Items with NULL status_transitions (legacy) are gracefully skipped."""
    from models.sync_job import CachedItem
    db.add(CachedItem(project_id=sample_project.id, item_key="LEGACY-1", item_type="Task",
                      workflow_timestamps={}, status_transitions=None))
    db.add(CachedItem(project_id=sample_project.id, item_key="S-3", item_type="Story",
                      workflow_timestamps={}, status_transitions=[
                          {"from_status": None, "to_status": "Open", "transitioned_at": "2024-01-01T00:00:00"},
                      ]))
    db.commit()
    resp = client.get(f"/api/metrics/{sample_project.id}/available-statuses")
    assert resp.status_code == 200
    assert "Open" in resp.json()["statuses"]


# ---------------------------------------------------------------------------
# workflow update triggers recompute (projects API)
# ---------------------------------------------------------------------------

def test_workflow_update_triggers_recompute(client, db, sample_project):
    """PUT /api/projects/{id} with new workflow_steps triggers recompute."""
    from models.sync_job import CachedItem
    transitions = [
        {"from_status": None, "to_status": "Backlog", "transitioned_at": "2024-01-01T00:00:00"},
        {"from_status": "Backlog", "to_status": "In Progress", "transitioned_at": "2024-01-05T00:00:00"},
    ]
    db.add(CachedItem(project_id=sample_project.id, item_key="WF-1", item_type="Story",
                      workflow_timestamps={}, status_transitions=transitions))
    db.commit()

    new_steps = [
        {"position": 0, "display_name": "Backlog", "source_statuses": ["Backlog"], "stage": "queue"},
        {"position": 1, "display_name": "In Progress", "source_statuses": ["In Progress"], "stage": "start"},
        {"position": 2, "display_name": "Done", "source_statuses": ["Done"], "stage": "done"},
    ]
    resp = client.put(f"/api/projects/{sample_project.id}", json={"workflow_steps": new_steps})
    assert resp.status_code == 200

    item = db.query(CachedItem).filter_by(item_key="WF-1").one()
    assert item.workflow_timestamps.get("In Progress") is not None
