from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Literal, Optional
from pydantic import BaseModel
from datetime import datetime
from database import get_db
from models.project import Project, WorkflowStep

router = APIRouter()

_VALID_STAGES = Literal["queue", "start", "in_flight", "done"]
_VALID_PLATFORMS = Literal[
    "jira", "trello", "azure_devops", "gitlab", "linear", "shortcut", "csv"
]


class WorkflowStepCreate(BaseModel):
    position: int
    display_name: str
    source_statuses: List[str]
    stage: _VALID_STAGES

class WorkflowStepOut(BaseModel):
    id: int
    project_id: int
    position: int
    display_name: str
    source_statuses: List[str]
    stage: str
    model_config = {"from_attributes": True}

class ProjectCreate(BaseModel):
    name: str
    platform: _VALID_PLATFORMS
    config: dict = {}
    workflow_steps: List[WorkflowStepCreate] = []

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    platform: Optional[_VALID_PLATFORMS] = None
    config: Optional[dict] = None
    workflow_steps: Optional[List[WorkflowStepCreate]] = None

class ProjectOut(BaseModel):
    id: int
    name: str
    platform: str
    config: dict
    last_synced_at: Optional[datetime]
    created_at: datetime
    workflow_steps: List[WorkflowStepOut] = []
    model_config = {"from_attributes": True}

@router.get("/", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()

@router.post("/", response_model=ProjectOut)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        name=data.name,
        platform=data.platform,
        config=data.config
    )
    db.add(project)
    db.flush()
    for step in data.workflow_steps:
        ws = WorkflowStep(project_id=project.id, **step.model_dump())
        db.add(ws)
    db.commit()
    db.refresh(project)
    return project

@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.put("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.name is not None:
        project.name = data.name
    if data.platform is not None:
        project.platform = data.platform
    if data.config is not None:
        project.config = data.config
    if data.workflow_steps is not None:
        db.query(WorkflowStep).filter(WorkflowStep.project_id == project_id).delete()
        for step in data.workflow_steps:
            ws = WorkflowStep(project_id=project.id, **step.model_dump())
            db.add(ws)
    db.commit()
    db.refresh(project)
    return project

@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True}
