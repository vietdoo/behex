from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Friendship(Base):
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    addressee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, accepted, blocked
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    requester = relationship("User", foreign_keys=[requester_id], backref="sent_friend_requests")
    addressee = relationship("User", foreign_keys=[addressee_id], backref="received_friend_requests")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('requester_id', 'addressee_id', name='unique_friendship'),
    ) 