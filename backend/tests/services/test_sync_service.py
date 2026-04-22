"""Tests for SyncService business logic."""
import pytest
import os
import tempfile
import textwrap
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


def _make_csv_with_items(n: int = 5) -> str:
    lines = ["item_key,item_type,created_at,Backlog,In Progress,Done"]
    for i in range(n):
        lines.append(f"ITEM-{i+1},Story,2024-01-{i+1:02d},2024-01-{i+1:02d},2024-01-{i+2:02d},2024-01-{i+3:02d}")
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    tf.write("\n".join(lines))
    tf.close()
    return tf.name


class TestSyncServiceCreateJob:
    def test_creates_pending_job(self, db):
        project = _create_project(db)
        svc = SyncService(db)
        job = svc.create_job(project.id)
        assert job.id is not None
        assert job.status == "pending"
        assert job.project_id == project.id


class TestSyncServiceRun:
    def test_run_success_with_csv(self, db):
        project = _create_project(db)
        csv_path = _make_csv_with_items(5)
        try:
            project.config = {"file_path": csv_path}
            db.commit()

            svc = SyncService(db)
            svc.create_job(project.id)
            svc.run(project.id)

            job = db.query(SyncJob).filter(SyncJob.project_id == project.id).order_by(SyncJob.id.desc()).first()
            assert job.status == "success"
            assert job.items_fetched == 5
            assert job.finished_at is not None
        finally:
            os.unlink(csv_path)

    def test_run_updates_last_synced_at(self, db):
        project = _create_project(db)
        csv_path = _make_csv_with_items(3)
        try:
            project.config = {"file_path": csv_path}
            db.commit()
            assert project.last_synced_at is None

            svc = SyncService(db)
            svc.create_job(project.id)
            svc.run(project.id)

            db.refresh(project)
            assert project.last_synced_at is not None
        finally:
            os.unlink(csv_path)

    def test_run_stores_cached_items(self, db):
        project = _create_project(db)
        csv_path = _make_csv_with_items(4)
        try:
            project.config = {"file_path": csv_path}
            db.commit()

            svc = SyncService(db)
            svc.create_job(project.id)
            svc.run(project.id)

            items = db.query(CachedItem).filter(CachedItem.project_id == project.id).all()
            assert len(items) == 4
        finally:
            os.unlink(csv_path)

    def test_run_replaces_cached_items_on_second_sync(self, db):
        project = _create_project(db)
        csv_path = _make_csv_with_items(3)
        try:
            project.config = {"file_path": csv_path}
            db.commit()

            svc = SyncService(db)
            svc.create_job(project.id)
            svc.run(project.id)

            svc.create_job(project.id)
            svc.run(project.id)

            items = db.query(CachedItem).filter(CachedItem.project_id == project.id).all()
            assert len(items) == 3  # not 6
        finally:
            os.unlink(csv_path)

    def test_run_with_connector_error_sets_error_status(self, db):
        project = _create_project(db)
        # file_path does not exist → connector will raise
        project.config = {"file_path": "/nonexistent/bad.csv"}
        db.commit()

        svc = SyncService(db)
        svc.create_job(project.id)

        with pytest.raises(Exception):
            svc.run(project.id)

        job = db.query(SyncJob).filter(SyncJob.project_id == project.id).order_by(SyncJob.id.desc()).first()
        assert job.status == "error"
        assert job.error_message

    def test_run_with_no_pending_job_is_noop(self, db):
        project = _create_project(db)
        svc = SyncService(db)
        # No job created — should just return without raising
        svc.run(project.id)
        jobs = db.query(SyncJob).filter(SyncJob.project_id == project.id).all()
        assert len(jobs) == 0
