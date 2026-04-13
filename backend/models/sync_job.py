from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from database import Base

class SyncJob(Base):
    __tablename__ = "sync_jobs"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    status = Column(String, default="pending")
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    items_fetched = Column(Integer, nullable=True)
    project = relationship("Project", back_populates="sync_jobs")

class CachedItem(Base):
    __tablename__ = "cached_items"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    item_key = Column(String)
    item_type = Column(String)
    creator = Column(String, nullable=True)
    created_at = Column(DateTime)
    workflow_timestamps = Column(JSON)
    cycle_time_days = Column(Float, nullable=True)
    lead_time_days = Column(Float, nullable=True)
