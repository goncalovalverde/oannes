"""SyncService: orchestrates fetching data from a connector and persisting to CachedItem.

Extracted from api/sync.py to satisfy SRP: the API layer only handles HTTP,
the scheduler only handles timers — both delegate execution here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from connectors import get_connector
from models.project import Project
from models.sync_job import CachedItem, SyncJob

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SyncService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_job(self, project_id: int) -> SyncJob:
        """Persist a new pending SyncJob and return it."""
        job = SyncJob(project_id=project_id, status="pending")
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def run(self, project_id: int) -> None:
        """Execute a full sync for *project_id* in the current thread.

        Finds the latest pending job, transitions it through running → success/error,
        and replaces all CachedItems for the project.
        """
        db = self._db
        job = (
            db.query(SyncJob)
            .filter(SyncJob.project_id == project_id, SyncJob.status == "pending")
            .order_by(SyncJob.id.desc())
            .first()
        )
        if not job:
            logger.warning("run_sync: no pending job for project %s", project_id)
            return

        job.status = "running"
        job.started_at = _utcnow()
        db.commit()

        try:
            df = self._fetch(project_id)
            self._store_items(project_id, df)

            project = db.query(Project).filter(Project.id == project_id).one()
            project.last_synced_at = _utcnow()

            job.status = "success"
            job.finished_at = _utcnow()
            job.items_fetched = len(df)
            db.commit()

            logger.info("Sync project %s: %d items fetched", project_id, len(df))
        except Exception as exc:
            logger.exception("Sync project %s failed", project_id)
            job.status = "error"
            job.finished_at = _utcnow()
            job.error_message = str(exc)
            db.commit()
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch(self, project_id: int) -> pd.DataFrame:
        db = self._db
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        steps = [
            {
                "display_name": s.display_name,
                "source_statuses": s.source_statuses,
                "stage": s.stage,
                "position": s.position,
            }
            for s in project.workflow_steps
        ]
        connector = get_connector(project.platform, project.config, steps)
        return connector.fetch_items()

    def _store_items(self, project_id: int, df: pd.DataFrame) -> None:
        """Replace all cached items for *project_id* atomically.

        Build the new list first; only delete the old rows once the new objects
        are ready. This prevents a window where the project has zero items if
        an error occurs during construction.
        """
        db = self._db
        new_items: list[CachedItem] = []
        for _, row in df.iterrows():
            ct = row.get("cycle_time_days")
            lt = row.get("lead_time_days")
            new_items.append(
                CachedItem(
                    project_id=project_id,
                    item_key=str(row.get("item_key", "")),
                    item_type=str(row.get("item_type", "Unknown")),
                    creator=str(row.get("creator", "")) if row.get("creator") else None,
                    created_at=row.get("created_at"),
                    workflow_timestamps=row.get("workflow_timestamps", {}),
                    cycle_time_days=ct if ct is not None and pd.notna(ct) else None,
                    lead_time_days=lt if lt is not None and pd.notna(lt) else None,
                )
            )
        # Delete old rows only after successfully building the replacement list.
        db.query(CachedItem).filter(CachedItem.project_id == project_id).delete()
        db.bulk_save_objects(new_items)
        db.flush()
