from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timezone
import logging
from database import get_db, SessionLocal
from models.sync_job import SyncJob
from models.project import Project
from services.sync_service import SyncService

router = APIRouter()
logger = logging.getLogger(__name__)


class SyncJobOut(BaseModel):
    id: int
    project_id: int
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    items_fetched: Optional[int]
    model_config = {"from_attributes": True}


class RateLimitConfig(BaseModel):
    """Rate limiting configuration for a project."""
    enabled: bool = True
    retry_delay_seconds: Optional[float] = None  # None = use API-provided delay
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "retry_delay_seconds": None
            }
        }


def _run_sync_background(project_id: int) -> None:
    """Entry point for BackgroundTasks and APScheduler — opens its own DB session."""
    db = SessionLocal()
    try:
        SyncService(db).run(project_id)
    finally:
        db.close()


@router.post("/{project_id}", response_model=SyncJobOut)
def trigger_sync(project_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        job = SyncService(db).create_job(project_id)
        background_tasks.add_task(_run_sync_background, project_id)
        return job
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to create sync job for project {project_id}")
        raise HTTPException(status_code=500, detail="Failed to create sync job")

@router.get("/{project_id}/status", response_model=Optional[SyncJobOut])
def get_sync_status(project_id: int, db: Session = Depends(get_db)):
    if not db.query(Project).filter(Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    job = db.query(SyncJob).filter(SyncJob.project_id == project_id).order_by(SyncJob.id.desc()).first()
    return job  # None (never synced) is a valid 200 response


@router.get("/{project_id}/history", response_model=List[SyncJobOut])
def get_sync_history(project_id: int, db: Session = Depends(get_db)):
    return db.query(SyncJob).filter(SyncJob.project_id == project_id).order_by(SyncJob.id.desc()).limit(10).all()


@router.delete("/{project_id}/cache", response_model=dict)
def clear_cache_and_reset_sync(project_id: int, db: Session = Depends(get_db)):
    """Delete all cached items for a project and reset last_synced_at to force fresh sync.
    
    This allows users to perform a full re-sync of the project from scratch.
    """
    from models.sync_job import CachedItem
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        # Delete all cached items for this project
        deleted_count = db.query(CachedItem).filter(CachedItem.project_id == project_id).delete()
        
        # Reset last_synced_at so next sync treats it as a fresh sync
        project.last_synced_at = None
        
        db.commit()
        
        logger.info(f"Cleared cache for project {project_id}: deleted {deleted_count} cached items")
        return {"message": f"Deleted {deleted_count} cached items", "deleted_count": deleted_count}
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to clear cache for project {project_id}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/{project_id}/csv-upload", response_model=SyncJobOut)
async def upload_and_sync_csv(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Process a CSV/Excel upload in memory and store items — no file written to disk.

    Runs synchronously (CSV processing is fast) and returns the completed SyncJob.
    """
    from connectors.csv_connector import CSVConnector

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.platform != "csv":
        raise HTTPException(status_code=400, detail="Project is not a CSV project")

    content = await file.read()
    filename = file.filename or "upload.csv"

    steps = [
        {
            "display_name": s.display_name,
            "source_statuses": s.source_statuses,
            "stage": s.stage,
            "position": s.position,
        }
        for s in project.workflow_steps
    ]

    job = SyncService(db).create_job(project_id)
    job.status = "running"
    job.started_at = _utcnow()
    db.commit()

    try:
        connector = CSVConnector(project_config={}, workflow_steps=steps)
        df = connector.fetch_from_bytes(content, filename)
        SyncService(db).import_from_dataframe(project_id, df)

        project.last_synced_at = _utcnow()
        job.status = "success"
        job.finished_at = _utcnow()
        job.items_fetched = len(df)
        db.commit()
        db.refresh(job)

        logger.info("CSV upload sync project %s: %d items", project_id, len(df))
        return job
    except Exception as exc:
        logger.exception("CSV upload sync failed for project %s", project_id)
        job.status = "error"
        job.finished_at = _utcnow()
        job.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{project_id}/rate-limit-config", response_model=RateLimitConfig)
def get_rate_limit_config(project_id: int, db: Session = Depends(get_db)):
    """Get rate limiting configuration for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return RateLimitConfig(
        enabled=project.rate_limit_enabled,
        retry_delay_seconds=project.rate_limit_retry_delay
    )


@router.put("/{project_id}/rate-limit-config", response_model=RateLimitConfig)
def update_rate_limit_config(
    project_id: int,
    config: RateLimitConfig,
    db: Session = Depends(get_db)
):
    """Update rate limiting configuration for a project.
    
    Use this to:
    - Enable/disable rate limiting
    - Override API-provided retry delays with a fixed delay (in seconds)
    
    Example:
    - {"enabled": true, "retry_delay_seconds": null} — use API-provided delays
    - {"enabled": true, "retry_delay_seconds": 300} — always wait 5 minutes
    - {"enabled": false, "retry_delay_seconds": null} — ignore rate limits (not recommended)
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        project.rate_limit_enabled = config.enabled
        project.rate_limit_retry_delay = config.retry_delay_seconds
        db.commit()
        db.refresh(project)
        
        logger.info(f"Updated rate limit config for project {project_id}: enabled={config.enabled}, delay={config.retry_delay_seconds}s")
        
        return RateLimitConfig(
            enabled=project.rate_limit_enabled,
            retry_delay_seconds=project.rate_limit_retry_delay
        )
    except Exception as e:
        db.rollback()
        logger.exception(f"Failed to update rate limit config for project {project_id}")
        raise HTTPException(status_code=500, detail="Failed to update rate limit configuration")


class PerformanceMetrics(BaseModel):
    """Performance metrics for recent sync jobs."""
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    avg_items_fetched: Optional[float]
    avg_sync_duration_seconds: Optional[float]
    last_sync_status: Optional[str]
    last_sync_at: Optional[datetime]
    last_sync_duration_seconds: Optional[float]
    

@router.get("/{project_id}/performance-metrics", response_model=PerformanceMetrics)
def get_performance_metrics(project_id: int, db: Session = Depends(get_db)):
    """Get performance metrics for a project's sync history."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get last 10 sync jobs
    sync_jobs = db.query(SyncJob).filter(SyncJob.project_id == project_id).order_by(
        SyncJob.id.desc()
    ).limit(10).all()
    
    if not sync_jobs:
        return PerformanceMetrics(
            total_syncs=0,
            successful_syncs=0,
            failed_syncs=0,
            avg_items_fetched=None,
            avg_sync_duration_seconds=None,
            last_sync_status=None,
            last_sync_at=None,
            last_sync_duration_seconds=None,
        )
    
    # Calculate metrics
    successful = [job for job in sync_jobs if job.status == "completed"]
    failed = [job for job in sync_jobs if job.status == "failed"]
    
    # Average items fetched
    items_fetched = [job.items_fetched for job in successful if job.items_fetched]
    avg_items = sum(items_fetched) / len(items_fetched) if items_fetched else None
    
    # Average sync duration
    durations = []
    for job in successful:
        if job.started_at and job.finished_at:
            duration = (job.finished_at - job.started_at).total_seconds()
            durations.append(duration)
    avg_duration = sum(durations) / len(durations) if durations else None
    
    # Last sync metrics
    last_job = sync_jobs[0]
    last_duration = None
    if last_job.started_at and last_job.finished_at:
        last_duration = (last_job.finished_at - last_job.started_at).total_seconds()
    
    return PerformanceMetrics(
        total_syncs=len(sync_jobs),
        successful_syncs=len(successful),
        failed_syncs=len(failed),
        avg_items_fetched=avg_items,
        avg_sync_duration_seconds=avg_duration,
        last_sync_status=last_job.status,
        last_sync_at=last_job.finished_at or last_job.started_at,
        last_sync_duration_seconds=last_duration,
    )
