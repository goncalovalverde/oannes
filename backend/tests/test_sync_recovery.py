"""Tests for sync job recovery (stuck job detection and reset on startup)."""
import pytest
from datetime import datetime, timezone
from models.sync_job import SyncJob
from models.project import Project
from database import recover_stuck_sync_jobs


def test_recover_stuck_sync_jobs_resets_running_jobs(db):
    """Stuck jobs in 'running' state should be reset to 'error' on startup."""
    # Create a project
    project = Project(
        name="Test Project",
        platform="csv",
        config={}
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Create a stuck job (still in 'running' state)
    stuck_job = SyncJob(
        project_id=project.id,
        status="running",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(stuck_job)
    db.commit()
    db.refresh(stuck_job)
    
    original_id = stuck_job.id
    
    # Before recovery, job is still running
    assert db.query(SyncJob).filter(SyncJob.id == original_id).one().status == "running"
    
    # Run recovery (pass the test's db session)
    recover_stuck_sync_jobs(db=db)
    
    # After recovery, job should be marked as error
    recovered_job = db.query(SyncJob).filter(SyncJob.id == original_id).one()
    assert recovered_job.status == "error"
    assert recovered_job.finished_at is not None
    assert "interrupted" in recovered_job.error_message.lower()


def test_recover_stuck_sync_jobs_ignores_completed_jobs(db):
    """Completed jobs (success/error) should not be modified."""
    project = Project(
        name="Test Project",
        platform="csv",
        config={}
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Create a successful job
    success_job = SyncJob(
        project_id=project.id,
        status="success",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
        items_fetched=5
    )
    db.add(success_job)
    db.commit()
    
    # Create an error job
    error_job = SyncJob(
        project_id=project.id,
        status="error",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
        error_message="Original error"
    )
    db.add(error_job)
    db.commit()
    db.refresh(success_job)
    db.refresh(error_job)
    
    success_id = success_job.id
    error_id = error_job.id
    
    # Run recovery (pass the test's db session)
    recover_stuck_sync_jobs(db=db)
    
    # Completed jobs should be unchanged
    recovered_success = db.query(SyncJob).filter(SyncJob.id == success_id).one()
    recovered_error = db.query(SyncJob).filter(SyncJob.id == error_id).one()
    
    assert recovered_success.status == "success"
    assert recovered_success.items_fetched == 5
    assert recovered_error.status == "error"
    assert recovered_error.error_message == "Original error"


def test_recover_stuck_sync_jobs_multiple_projects(db):
    """All stuck jobs across all projects should be recovered."""
    # Create two projects
    project1 = Project(
        name="Project 1",
        platform="csv",
        config={}
    )
    project2 = Project(
        name="Project 2",
        platform="csv",
        config={}
    )
    db.add(project1)
    db.add(project2)
    db.commit()
    db.refresh(project1)
    db.refresh(project2)
    
    # Create stuck jobs for both projects
    job1 = SyncJob(project_id=project1.id, status="running", started_at=datetime.now(timezone.utc).replace(tzinfo=None))
    job2 = SyncJob(project_id=project2.id, status="running", started_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(job1)
    db.add(job2)
    db.commit()
    db.refresh(job1)
    db.refresh(job2)
    
    # Run recovery (pass the test's db session)
    recover_stuck_sync_jobs(db=db)
    
    # Both jobs should be marked as error
    recovered1 = db.query(SyncJob).filter(SyncJob.id == job1.id).one()
    recovered2 = db.query(SyncJob).filter(SyncJob.id == job2.id).one()
    
    assert recovered1.status == "error"
    assert recovered2.status == "error"
    assert recovered1.finished_at is not None
    assert recovered2.finished_at is not None


def test_recover_stuck_sync_jobs_empty_database(db):
    """Recovery should handle empty database gracefully."""
    # Ensure no stuck jobs exist
    assert db.query(SyncJob).filter(SyncJob.status == "running").count() == 0
    
    # Run recovery (pass the test's db session)
    recover_stuck_sync_jobs(db=db)
    
    # Database should still be empty
    assert db.query(SyncJob).count() == 0
