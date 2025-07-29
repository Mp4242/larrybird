from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from database.database import Base            # ✅ même principe

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)         # = message_id Telegram
    author_id = Column(Integer, ForeignKey("users.id"))
    thread_id = Column(Integer)                    # topic ID (sos / wins / …)
    text = Column(String(1000))
    reply_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
