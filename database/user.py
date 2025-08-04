from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func
from database.database import Base            # ✅ importe Base directement ici
from sqlalchemy import Boolean
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date
from __future__ import annotations


class User(Base):
    """Таблица участников клуба."""

    __tablename__ = "users"

    id:            Mapped[int]    = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id:   Mapped[int]    = mapped_column(Integer, unique=True, nullable=False)

    # профиль
    pseudo:        Mapped[str]    = mapped_column(String(30), nullable=True)
    avatar_emoji:  Mapped[str]    = mapped_column(String(4),  nullable=True)
    quit_date:     Mapped[date]   = mapped_column(Date,       nullable=True)
    created_at                    = Column(DateTime(timezone=True), server_default=func.now())

    # бизнес-флаги
    is_member:     Mapped[bool]   = mapped_column(Boolean, default=False, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checkpoint: Mapped[int]  = mapped_column(Integer, default=0, nullable=False)
    is_sober:      Mapped[bool]   = mapped_column(Boolean, default=True, nullable=False)
    paid_until                    = mapped_column(DateTime, nullable=True)   # optionnel
