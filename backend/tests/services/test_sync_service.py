"""Tests for SyncService business logic."""
import pytest
from datetime import datetime
from unittest.mock import patch
import pandas as pd

from services.sync_service import SyncService
from models.project import Project, WorkflowStep
from models.sync_job import SyncJob, CachedItem


def _create_project(db) -> Project:
    project = Project(
        name="Test",
        platform="csv",
        config={"file_path": "/tmp/nonexistent.csv"},
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    for i, (name, stage) in enumerate([("Backlog", "queue"), ("In Progress", "start"), ("Done", "done")]):
        step = WorkflowStep(
            project_id=project.id,
            display_name=name,
            stage=stage,
            position=i,
            source_statuses=[name],
        )
        db.add(step)
    db.commit()
    return project


def _make_items_df(n: int = 5) -> pd.DataFrame:
    """Build a minimal items DataFrame that _store_items can consume."""
    rows = []
    for i in range(n):
        rows.append({
            "item_key": f"ITEM-{i+1}",
            "item_type": "Story",
            "creator": None,
            "created_at": pd.Timestamp(f"2024-01-{i+1:02d}"),
            "workflow_timestamps": {"Backlog": f"2024-01-{i+1:02d}T00:00:00",
                                    "Done": f"2024-01-{i+3:02d}T00:00:00"},
            "status_transitions": [],
            "cycle_time_days": 2.0,
            "lead_time_days": 3.0,
        })
    return pd.DataFrame(rows)


class TestSyncServiceCreateJob:
    def test_creates_pending_job(self, db):
        project = _create_project(db)
        svc = SyncService(db)
        job = svc.create_job(project.id)
        assert job.id is not None
        assert job.status == "pending"
        assert job.project_id == project.id


class TestSyncServiceRun:
    def test_run_success_sets_job_status(self, db):
        """run() marks the pending job as success and records item count."""
        project = _create_project(db)
        df = _make_items_df(5)

        svc = SyncService(db)
        svc.create_job(project.id)
        with patch.object(svc, "_fetch", return_value=df):
            svc.run(project.id)

        job = db.query(SyncJob).filter(SyncJob.project_id == project.id).order_by(SyncJob.id.desc()).first()
        assert job.status == "success"
        assert job.items_fetched == 5
        assert job.finished_at is not None

    def test_run_updates_last_synced_at(self, db):
        project = _create_project(db)
        assert project.last_synced_at is None

        svc = SyncService(db)
        svc.create_job(project.id)
        with patch.object(svc, "_fetch", return_value=_make_items_df(3)):
            svc.run(project.id)

        db.refresh(project)
        assert project.last_synced_at is not None

    def test_run_stores_cached_items(self, db):
        project = _create_project(db)
        svc = SyncService(db)
        svc.create_job(project.id)
        with patch.object(svc, "_fetch", return_value=_make_items_df(4)):
            svc.run(project.id)

        items = db.query(CachedItem).filter(CachedItem.project_id == project.id).all()
        assert len(items) == 4

    def test_run_replaces_cached_items_on_second_sync(self, db):
        """Second sync with the same keys should not duplicate items."""
        project = _create_project(db)
        svc = SyncService(db)

        svc.create_job(project.id)
        with patch.object(svc, "_fetch", return_value=_make_items_df(3)):
            svc.run(project.id)

        svc.create_job(project.id)
        with patch.object(svc, "_fetch", return_value=_make_items_df(3)):
            svc.run(project.id)

        items = db.query(CachedItem).filter(CachedItem.project_id == project.id).all()
        assert len(items) == 3  # not 6

    def test_run_with_connector_error_sets_error_status(self, db):
        project = _create_project(db)
        svc = SyncService(db)
        svc.create_job(project.id)

        with patch.object(svc, "_fetch", side_effect=RuntimeError("connector failed")):
            with pytest.raises(RuntimeError):
                svc.run(project.id)

        job = db.query(SyncJob).filter(SyncJob.project_id == project.id).order_by(SyncJob.id.desc()).first()
        assert job.status == "error"
        assert job.error_message == "connector failed"

    def test_run_with_no_pending_job_is_noop(self, db):
        project = _create_project(db)
        svc = SyncService(db)
        # No job created — should just return without raising
        svc.run(project.id)
        jobs = db.query(SyncJob).filter(SyncJob.project_id == project.id).all()
        assert len(jobs) == 0


class TestSyncServiceImportFromDataframe:
    def test_import_stores_items_and_returns_count(self, db):
        project = _create_project(db)
        df = _make_items_df(6)
        svc = SyncService(db)
        count = svc.import_from_dataframe(project.id, df)

        assert count == 6
        items = db.query(CachedItem).filter(CachedItem.project_id == project.id).all()
        assert len(items) == 6

    def test_import_idempotent_on_second_call(self, db):
        """Importing the same keys twice must not duplicate items."""
        project = _create_project(db)
        df = _make_items_df(3)
        svc = SyncService(db)
        svc.import_from_dataframe(project.id, df)
        svc.import_from_dataframe(project.id, df)

        items = db.query(CachedItem).filter(CachedItem.project_id == project.id).all()
        assert len(items) == 3

    def test_import_empty_dataframe_is_noop(self, db):
        project = _create_project(db)
        svc = SyncService(db)
        count = svc.import_from_dataframe(project.id, pd.DataFrame())
        assert count == 0
        items = db.query(CachedItem).filter(CachedItem.project_id == project.id).all()
        assert len(items) == 0
