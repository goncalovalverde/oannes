from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, JSON, UniqueConstraint, Index
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
    __table_args__ = (
        UniqueConstraint("project_id", "item_key", name="uq_cached_item_key"),
        Index("ix_cached_item_project_created", "project_id", "created_at"),
    )
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"))
    item_key = Column(String)
    item_type = Column(String)
    creator = Column(String, nullable=True)
    created_at = Column(DateTime)
    workflow_timestamps = Column(JSON)
    cycle_time_days = Column(Float, nullable=True)
    lead_time_days = Column(Float, nullable=True)
    # Full ordered status transition history. Each entry:
    #   {"from_status": str|null, "to_status": str, "transitioned_at": ISO-8601 str}
    # First entry is synthetic (from_status=null) representing the initial status at creation.
    # NULL means the item was synced before this feature was added (needs re-sync to populate).
    status_transitions = Column(JSON, nullable=True)
