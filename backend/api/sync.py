from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
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


@router.get("/{project_id}/status", response_model=SyncJobOut)
def get_sync_status(project_id: int, db: Session = Depends(get_db)):
    job = db.query(SyncJob).filter(SyncJob.project_id == project_id).order_by(SyncJob.id.desc()).first()
    if not job:
        raise HTTPException(status_code=404, detail="No sync jobs found")
    return job


@router.get("/{project_id}/history", response_model=List[SyncJobOut])
def get_sync_history(project_id: int, db: Session = Depends(get_db)):
    return db.query(SyncJob).filter(SyncJob.project_id == project_id).order_by(SyncJob.id.desc()).limit(10).all()

