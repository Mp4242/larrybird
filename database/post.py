from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from database.database import Base

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    author_id = Column(Integer, ForeignKey("users.id"), index=True)  # Index pour queries rapides by author
    thread_id = Column(Integer)
    text = Column(String(1000))
    reply_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted = Column(Boolean, default=False)  # Marqueur pour delete UX soft
    message_id = Column(Integer, nullable=True)  # Pour edit in group (remove reactions)