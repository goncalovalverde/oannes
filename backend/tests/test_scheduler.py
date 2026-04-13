"""Unit tests for scheduler.py — the APScheduler hourly sync job.

These tests use mocks so they run instantly without touching the DB or
network connectors.  The key invariants under test are:

1. Every hourly project gets create_job + run called.
2. A failure on one project must NOT abort remaining projects.
3. A DB-level failure loading projects must be logged and not crash the process.
4. start_scheduler / stop_scheduler lifecycle does not raise.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(id_: int, name: str, freq: str = "hourly") -> MagicMock:
    p = MagicMock()
    p.id = id_
    p.name = name
    p.sync_frequency = freq
    return p


def _patch_scheduler_deps(projects: list, svc_mock: MagicMock = None):
    """Return context-manager patches for scheduler's lazy imports.

    scheduler.py does ``from database import SessionLocal`` and
    ``from services.sync_service import SyncService`` *inside* the function,
    so we must patch the source modules, not the scheduler namespace.
    """
    if svc_mock is None:
        svc_mock = MagicMock()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = projects

    session_cls_patch = patch("database.SessionLocal", return_value=mock_db)
    svc_patch = patch("services.sync_service.SyncService", return_value=svc_mock)
    return session_cls_patch, svc_patch, mock_db, svc_mock


# ---------------------------------------------------------------------------
# sync_all_projects — happy path
# ---------------------------------------------------------------------------

class TestSyncAllProjectsHappyPath:
    def test_single_project_gets_create_job_and_run(self):
        from scheduler import sync_all_projects

        projects = [_make_project(1, "Alpha")]
        svc = MagicMock()
        s1, s2, _, _ = _patch_scheduler_deps(projects, svc)

        with s1, s2:
            sync_all_projects()

        svc.create_job.assert_called_once_with(1)
        svc.run.assert_called_once_with(1)

    def test_multiple_projects_each_get_synced(self):
        from scheduler import sync_all_projects

        projects = [_make_project(1, "Alpha"), _make_project(2, "Beta"), _make_project(3, "Gamma")]
        svc = MagicMock()
        s1, s2, _, _ = _patch_scheduler_deps(projects, svc)

        with s1, s2:
            sync_all_projects()

        assert svc.create_job.call_count == 3
        assert svc.run.call_count == 3
        svc.create_job.assert_any_call(1)
        svc.create_job.assert_any_call(2)
        svc.create_job.assert_any_call(3)

    def test_no_projects_runs_without_error(self):
        from scheduler import sync_all_projects

        s1, s2, _, svc = _patch_scheduler_deps([])

        with s1, s2:
            sync_all_projects()   # must not raise

        svc.create_job.assert_not_called()
        svc.run.assert_not_called()

    def test_db_session_is_always_closed(self):
        from scheduler import sync_all_projects

        s1, s2, mock_db, _ = _patch_scheduler_deps([_make_project(1, "Alpha")])

        with s1, s2:
            sync_all_projects()

        mock_db.close.assert_called_once()

    def test_db_session_closed_even_when_sync_raises(self):
        from scheduler import sync_all_projects

        svc = MagicMock()
        svc.run.side_effect = RuntimeError("connector exploded")
        s1, s2, mock_db, _ = _patch_scheduler_deps([_make_project(1, "Alpha")], svc)

        with s1, s2:
            sync_all_projects()   # must not propagate

        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# sync_all_projects — per-project error isolation (C-4 requirement)
# ---------------------------------------------------------------------------

class TestSyncAllProjectsErrorIsolation:
    def test_first_project_failure_does_not_skip_second(self):
        """Core C-4 invariant: one bad project must not abort the batch."""
        from scheduler import sync_all_projects

        projects = [_make_project(1, "Bad"), _make_project(2, "Good")]
        svc = MagicMock()
        svc.run.side_effect = [RuntimeError("invalid credentials"), None]
        s1, s2, _, _ = _patch_scheduler_deps(projects, svc)

        with s1, s2:
            sync_all_projects()   # must not raise

        assert svc.run.call_count == 2, "Second project was skipped after first failed"

    def test_all_projects_attempted_even_when_all_fail(self):
        from scheduler import sync_all_projects

        n = 4
        projects = [_make_project(i, f"Proj{i}") for i in range(1, n + 1)]
        svc = MagicMock()
        svc.run.side_effect = RuntimeError("always fails")
        s1, s2, _, _ = _patch_scheduler_deps(projects, svc)

        with s1, s2:
            sync_all_projects()

        assert svc.create_job.call_count == n
        assert svc.run.call_count == n

    def test_per_project_failure_is_logged(self, caplog):
        from scheduler import sync_all_projects

        svc = MagicMock()
        svc.run.side_effect = RuntimeError("creds expired")
        s1, s2, _, _ = _patch_scheduler_deps([_make_project(7, "Faulty")], svc)

        with caplog.at_level(logging.ERROR, logger="scheduler"):
            with s1, s2:
                sync_all_projects()

        assert any("7" in r.message or "Faulty" in r.message for r in caplog.records), (
            "Expected a log message referencing the failed project"
        )

    def test_create_job_failure_does_not_skip_remaining_projects(self):
        """create_job blowing up should not kill the whole batch."""
        from scheduler import sync_all_projects

        projects = [_make_project(1, "P1"), _make_project(2, "P2")]
        svc = MagicMock()
        svc.create_job.side_effect = [RuntimeError("db full"), None]
        s1, s2, _, _ = _patch_scheduler_deps(projects, svc)

        with s1, s2:
            sync_all_projects()

        # P2's create_job must still have been attempted
        assert svc.create_job.call_count == 2


# ---------------------------------------------------------------------------
# sync_all_projects — DB-level failure loading projects
# ---------------------------------------------------------------------------

class TestSyncAllProjectsDbFailure:
    def test_db_query_failure_is_logged_and_does_not_raise(self, caplog):
        from scheduler import sync_all_projects

        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB connection lost")

        with caplog.at_level(logging.ERROR, logger="scheduler"):
            with patch("database.SessionLocal", return_value=mock_db), \
                 patch("services.sync_service.SyncService"):
                sync_all_projects()   # must not propagate

        assert any("unexpected" in r.message.lower() or "DB" in r.message
                   for r in caplog.records)
        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

class TestSchedulerLifecycle:
    def test_start_and_stop_do_not_raise(self):
        """start_scheduler + stop_scheduler must complete without exceptions."""
        from scheduler import start_scheduler, stop_scheduler
        start_scheduler()
        stop_scheduler()   # must not raise

    def test_stop_without_start_does_not_raise(self):
        """stop_scheduler called before start_scheduler must be a no-op."""
        import scheduler
        scheduler._scheduler = None
        from scheduler import stop_scheduler
        stop_scheduler()   # must not raise
