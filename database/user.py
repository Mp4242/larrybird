from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func
from database.database import Base            # ✅ importe Base directement ici
from sqlalchemy import Boolean

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    pseudo = Column(String(30), nullable=False)
    avatar_emoji = Column(String(10), default="👤")
    quit_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_checkpoint = Column(Integer, default=0)
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    is_sober = Column(Boolean, default=True)