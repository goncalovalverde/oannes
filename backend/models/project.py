from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base
from utils.crypto import EncryptedJSON

_now = lambda: datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: E731

class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    platform = Column(String, nullable=False)
    config = Column(EncryptedJSON)
    sync_frequency = Column(String, default="hourly")
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)
    workflow_steps = relationship("WorkflowStep", back_populates="project", order_by="WorkflowStep.position", cascade="all, delete-orphan")
    sync_jobs = relationship("SyncJob", back_populates="project", cascade="all, delete-orphan")

class WorkflowStep(Base):
    __tablename__ = "workflow_steps"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    position = Column(Integer)
    display_name = Column(String)
    source_statuses = Column(JSON)
    stage = Column(String)
    project = relationship("Project", back_populates="workflow_steps")
