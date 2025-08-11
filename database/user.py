from __future__ import annotations

from sqlalchemy import Column, Integer, String, Date, DateTime, BigInteger, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import date, datetime

from database.database import Base


class User(Base):
    """Таблица участников клуба."""

    __tablename__ = "users"

    id:            Mapped[int]  = mapped_column(Integer, primary_key=True, autoincrement=True)
    # BigInteger pour couvrir tous les Telegram IDs
    telegram_id:   Mapped[int]  = mapped_column(BigInteger, unique=True, nullable=False)

    # профиль
    pseudo:        Mapped[str | None] = mapped_column(String(30), nullable=True)
    avatar_emoji:  Mapped[str | None] = mapped_column(String(4),  nullable=True)
    quit_date:     Mapped[date | None] = mapped_column(Date,       nullable=True)
    created_at                      = Column(DateTime(timezone=True), server_default=func.now())

    # бизнес-флаги
    is_member:     Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checkpoint: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_sober:      Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Un SEUL chrono d’accès (sert aussi pour les 90j gratuits)
    paid_until:    Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Héritage (plus utilisé, on le garde pour compat DB)
    lifetime_access: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Flag pour compter les 100 gratuits (offre 90 jours)
    free90_claimed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def is_active_member(self) -> bool:
        now = datetime.utcnow()
        return bool(self.paid_until and self.paid_until >= now)
