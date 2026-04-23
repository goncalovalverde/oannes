from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from database import Base


class ItemTransition(Base):
    __tablename__ = "item_transitions"
    __table_args__ = (
        Index("ix_item_transition_item_id", "item_id"),
        Index("ix_item_transition_transitioned_at", "transitioned_at"),
        Index("ix_item_transition_to_status", "to_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("cached_items.id", ondelete="CASCADE"), nullable=False)
    to_status = Column(String(255), nullable=False)
    transitioned_at = Column(DateTime, nullable=False)

