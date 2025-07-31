# database/post.py
from sqlalchemy import Column, Integer, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from database.database import Base

class Post(Base):
    __tablename__ = "posts"

    id          = Column(Integer, primary_key=True)          # = message_id Telegram
    author_id   = Column(Integer, ForeignKey("users.id"))
    thread_id   = Column(Integer, nullable=False)            # TOPICS["sos"] | ["wins"] | ...
    parent_id   = Column(Integer, nullable=True)             # None = post racine, sinon reply
    text        = Column(Text)
    reply_count = Column(Integer, default=0)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    deleted     = Column(Boolean, default=False)             # ← NEW
