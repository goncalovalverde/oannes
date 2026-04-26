"""SyncService: orchestrates fetching data from a connector and persisting to CachedItem.

Extracted from api/sync.py to satisfy SRP: the API layer only handles HTTP;
sync is always triggered manually by the user.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from calculator.flow import compute_workflow_timestamps_from_transitions, compute_cycle_and_lead
from connectors import get_connector
from models.project import Project
from models.sync_job import CachedItem, SyncJob
from models.item_transition import ItemTransition

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

    def import_from_dataframe(self, project_id: int, df: pd.DataFrame) -> int:
        """Import items from a pre-built DataFrame. Returns item count.
        
        Public API for storing items from CSV uploads or other sources.
        Used by csv-upload and test endpoints.
        """
        self._store_items(project_id, df)
        return len(df)

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
        
        # Pass last_synced_at as 'since' for incremental syncing
        try:
            connector = get_connector(project.platform, project.config, steps, since=project.last_synced_at)
        except ValueError as e:
            # Provide helpful error message for configuration issues
            raise ValueError(
                f"Project '{project.name}' has invalid {project.platform} configuration. "
                f"Please update the project configuration. Details: {str(e)}"
            ) from e
        return connector.fetch_items()

    def _store_items(self, project_id: int, df: pd.DataFrame) -> None:
        """Upsert cached items by item_key — preserves items not in this fetch window.

        For incremental syncs the connector returns only recently-updated items.
        Using upsert-by-key ensures that older items are not lost.
        
        OPTIMIZED: bulk-loads all existing keys in a single query (N+1 elimination).
        """
        if df.empty:
            return
        
        db = self._db
        
        # Bulk-load all existing items for this project in ONE query
        item_keys = [str(r) for r in df["item_key"]]
        existing_items = db.query(CachedItem).filter(
            CachedItem.project_id == project_id,
            CachedItem.item_key.in_(item_keys)
        ).all()
        existing_map = {item.item_key: item for item in existing_items}

        # Now iterate through new/updated items with O(1) lookup
        for _, row in df.iterrows():
            item_key = str(row.get("item_key", ""))
            ct = row.get("cycle_time_days")
            lt = row.get("lead_time_days")
            transitions_list = row.get("status_transitions")
            if isinstance(transitions_list, float):
                transitions_list = None  # NaN from DataFrame

            existing = existing_map.get(item_key)
            
            if existing:
                existing.item_type = str(row.get("item_type", "Unknown"))
                existing.creator = str(row.get("creator", "")) if row.get("creator") else None
                existing.created_at = row.get("created_at")
                existing.workflow_timestamps = row.get("workflow_timestamps", {})
                existing.cycle_time_days = ct if ct is not None and pd.notna(ct) else None
                existing.lead_time_days = lt if lt is not None and pd.notna(lt) else None
                
                # Store transitions in the new table
                if transitions_list:
                    self._store_transitions(existing.id, transitions_list)
            else:
                new_item = CachedItem(
                    project_id=project_id,
                    item_key=item_key,
                    item_type=str(row.get("item_type", "Unknown")),
                    creator=str(row.get("creator", "")) if row.get("creator") else None,
                    created_at=row.get("created_at"),
                    workflow_timestamps=row.get("workflow_timestamps", {}),
                    cycle_time_days=ct if ct is not None and pd.notna(ct) else None,
                    lead_time_days=lt if lt is not None and pd.notna(lt) else None,
                )
                db.add(new_item)
                db.flush()  # Get the ID
                
                # Store transitions in the new table
                if transitions_list:
                    self._store_transitions(new_item.id, transitions_list)

        db.flush()

    def _store_transitions(self, item_id: int, transitions_list: list) -> None:
        """Store transitions in the item_transitions table.
        
        Transitions are expected to be a list of dicts with 'from_status', 'to_status' and 'transitioned_at' keys.
        """
        if not transitions_list:
            return
        
        db = self._db
        
        # Clear existing transitions for this item
        db.query(ItemTransition).filter(ItemTransition.item_id == item_id).delete()
        
        # Insert new transitions
        for transition in transitions_list:
            if isinstance(transition, dict):
                from_status = transition.get("from_status")
                to_status = transition.get("to_status")
                transitioned_at = transition.get("transitioned_at")
                
                if to_status and transitioned_at:
                    # Parse datetime if it's a string
                    if isinstance(transitioned_at, str):
                        try:
                            transitioned_at = pd.to_datetime(transitioned_at)
                        except Exception as e:
                            logger.warning(f"Failed to parse transition datetime {transitioned_at}: {e}")
                            continue
                    
                    db.add(ItemTransition(
                        item_id=item_id,
                        from_status=str(from_status) if from_status else None,
                        to_status=str(to_status),
                        transitioned_at=transitioned_at
                    ))
        
        db.flush()

    def recompute_workflow_timestamps(self, project_id: int) -> dict:
        """Recompute workflow_timestamps/cycle_time/lead_time from stored status_transitions.

        Called when the workflow configuration changes so that metric values stay
        consistent with the new step mapping without requiring a full re-sync.

        Returns:
            {"recomputed": N, "skipped": N}  – skipped items have NULL transitions
        """
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

        items = db.query(CachedItem).filter(CachedItem.project_id == project_id).all()
        recomputed = 0
        skipped = 0

        for item in items:
            # Convert ItemTransition objects to the format expected by compute_workflow_timestamps_from_transitions
            if not item.transitions:
                skipped += 1
                continue
            
            transitions_list = [
                {
                    "from_status": t.from_status,
                    "to_status": t.to_status,
                    "transitioned_at": t.transitioned_at.isoformat() if hasattr(t.transitioned_at, "isoformat") else str(t.transitioned_at),
                }
                for t in item.transitions
            ]

            new_timestamps = compute_workflow_timestamps_from_transitions(
                transitions_list, steps
            )
            # Ensure all values are ISO strings (JSON-serializable)
            item.workflow_timestamps = {
                k: v.isoformat() if hasattr(v, "isoformat") else v
                for k, v in new_timestamps.items()
            }

            # Recompute cycle/lead time via the shared calculator
            row: dict = {"created_at": item.created_at}
            row.update({k: pd.Timestamp(v) if v else pd.NaT for k, v in new_timestamps.items()})
            tmp_df = pd.DataFrame([row])
            tmp_df = compute_cycle_and_lead(tmp_df, steps)
            ct = tmp_df["cycle_time_days"].iloc[0] if "cycle_time_days" in tmp_df.columns else None
            lt = tmp_df["lead_time_days"].iloc[0] if "lead_time_days" in tmp_df.columns else None
            item.cycle_time_days = float(ct) if ct is not None and pd.notna(ct) else None
            item.lead_time_days = float(lt) if lt is not None and pd.notna(lt) else None
            recomputed += 1

        db.commit()
        logger.info("Recomputed workflow timestamps for project %s: %d items, %d skipped", project_id, recomputed, skipped)
        return {"recomputed": recomputed, "skipped": skipped}

