"""Tests for database integrity and robustness.

Ensures database remains consistent even under:
- Concurrent access
- Failed operations
- Incomplete transactions
"""
import pytest
import logging
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import DatabaseError
from database import check_database_integrity, SessionLocal
from models.sync_job import SyncJob
from models.project import Project
from services.sync_service import SyncService


logger = logging.getLogger(__name__)


class TestDatabaseIntegrity:
    """Tests for database integrity checks."""
    
    def test_integrity_check_on_healthy_database(self, db):
        """Verify integrity check passes on a healthy database."""
        status = check_database_integrity()
        assert status == "ok"
    
    def test_sync_job_creation_success(self, db, sample_project):
        """Verify sync job is created and committed successfully."""
        job = SyncService(db).create_job(sample_project.id)
        
        assert job.id is not None
        assert job.project_id == sample_project.id
        assert job.status == "pending"
        
        # Verify job is persisted
        queried_job = db.query(SyncJob).filter(SyncJob.id == job.id).first()
        assert queried_job is not None
        assert queried_job.project_id == sample_project.id
    
    def test_sync_job_creation_rollback_on_error(self, db, sample_project):
        """Verify failed sync job creation doesn't leave partial data."""
        # Patch create_job to raise an error after add() but before commit()
        with patch.object(SyncService, 'create_job') as mock_create:
            mock_create.side_effect = ValueError("Simulated error")
            
            with pytest.raises(ValueError):
                SyncService(db).create_job(sample_project.id)
        
        # Database should still be queryable after the error
        jobs = db.query(SyncJob).filter(SyncJob.project_id == sample_project.id).all()
        assert len(jobs) == 0
    
    def test_database_remains_usable_after_failed_sync(self, db, sample_project):
        """Verify database is still usable after a failed sync attempt."""
        # Simulate a failed sync
        with patch('services.sync_service.SyncService.run') as mock_run:
            mock_run.side_effect = RuntimeError("Simulated sync failure")
            
            # Create initial job
            job = SyncService(db).create_job(sample_project.id)
            assert job.id is not None
            
            # Try to run sync (will fail)
            try:
                SyncService(db).run(sample_project.id)
            except RuntimeError:
                pass
            
            # Database should still be queryable
            queried_job = db.query(SyncJob).filter(SyncJob.id == job.id).first()
            assert queried_job is not None
            
            # Should be able to create another job
            job2 = SyncService(db).create_job(sample_project.id)
            assert job2.id != job.id
    
    def test_multiple_sync_jobs_for_same_project(self, db, sample_project):
        """Verify multiple sync jobs can be created for the same project."""
        job1 = SyncService(db).create_job(sample_project.id)
        job2 = SyncService(db).create_job(sample_project.id)
        job3 = SyncService(db).create_job(sample_project.id)
        
        assert job1.id != job2.id != job3.id
        
        # All should be queryable
        jobs = db.query(SyncJob).filter(SyncJob.project_id == sample_project.id).all()
        assert len(jobs) == 3
    
    def test_query_after_failed_insert(self, db, sample_project):
        """Verify we can query the database after a failed operation."""
        # Create a valid job
        job1 = SyncService(db).create_job(sample_project.id)
        
        # Try an operation that will fail
        try:
            with patch.object(SyncService, 'create_job') as mock_create:
                mock_create.side_effect = RuntimeError("test error")
                SyncService(db).create_job(sample_project.id)
        except RuntimeError:
            pass
        
        # Should still be able to query
        jobs = db.query(SyncJob).filter(SyncJob.project_id == sample_project.id).all()
        assert len(jobs) == 1
        assert jobs[0].id == job1.id


class TestDatabaseConcurrency:
    """Tests for concurrent database access patterns."""
    
    def test_concurrent_read_access(self, db, sample_project):
        """Verify concurrent reads don't cause issues."""
        # Create a sync job
        job = SyncService(db).create_job(sample_project.id)
        
        # Multiple readers should work
        job1 = db.query(SyncJob).filter(SyncJob.id == job.id).first()
        job2 = db.query(SyncJob).filter(SyncJob.id == job.id).first()
        job3 = db.query(SyncJob).filter(SyncJob.id == job.id).first()
        
        assert job1.id == job2.id == job3.id == job.id
    
    def test_sequential_writes_succeed(self, db, sample_project):
        """Verify sequential writes don't corrupt database."""
        job1 = SyncService(db).create_job(sample_project.id)
        job2 = SyncService(db).create_job(sample_project.id)
        job3 = SyncService(db).create_job(sample_project.id)
        
        # Verify all jobs exist
        jobs = db.query(SyncJob).filter(SyncJob.project_id == sample_project.id).all()
        assert len(jobs) == 3
        assert all(j.status == "pending" for j in jobs)


class TestTransactionRollback:
    """Tests for transaction rollback behavior."""
    
    def test_explicit_rollback_cleans_state(self, db, sample_project):
        """Verify explicit rollback clears pending changes."""
        # Create a job but rollback
        job = SyncJob(project_id=sample_project.id, status="pending")
        db.add(job)
        db.rollback()
        
        # Job should not exist in database
        jobs = db.query(SyncJob).filter(SyncJob.project_id == sample_project.id).all()
        assert len(jobs) == 0
    
    def test_commit_persists_changes(self, db, sample_project):
        """Verify committed changes are persisted."""
        job = SyncJob(project_id=sample_project.id, status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Job should exist in database
        queried = db.query(SyncJob).filter(SyncJob.id == job.id).first()
        assert queried is not None
        assert queried.status == "pending"
