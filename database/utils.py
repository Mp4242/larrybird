from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Iterable, Sequence
import re

from sqlalchemy import select, update, func

from database.database import async_session
from database.user import User
from database.post import Post

FREE90_LIMIT = 100  # nombre de places gratuites 90j


# ───────────────────────────────  SESSION  ────────────────────────────────
@asynccontextmanager
async def get_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# ───────────────────────────────  USERS  ──────────────────────────────────
async def get_user(telegram_id: int) -> User | None:
    async with get_session() as ses:
        res = await ses.execute(select(User).where(User.telegram_id == telegram_id))
        return res.scalar_one_or_none()


async def update_user(telegram_id: int, **kwargs) -> None:
    async with get_session() as ses:
        await ses.execute(update(User).where(User.telegram_id == telegram_id).values(**kwargs))
        await ses.commit()


# Anciens helpers (garde-les si d'autres modules les utilisent)
async def create_user(telegram_id: int, pseudo: str, emoji: str = "👤") -> User:
    async with get_session() as ses:
        user = User(telegram_id=telegram_id, pseudo=pseudo, avatar_emoji=emoji)
        ses.add(user)
        await ses.commit()
        return user


_ANON_RE = re.compile(r"^_anon(\d*)$")   # capte suffixe numérique (optionnel)

async def create_user_stub(tg_id: int) -> None:
    """
    Ajoute _anon, _anon2, _anon3… sans collision.
    """
    async with async_session() as ses:
        pseudos = (await ses.scalars(select(User.pseudo).where(User.pseudo.like("_anon%")))).all()

        max_n = 0
        for p in pseudos:
            m = _ANON_RE.match(p or "")
            if m:
                n = int(m.group(1) or 1)   # _anon => 1
                max_n = max(max_n, n)

        next_pseudo = "_anon" if max_n == 0 else f"_anon{max_n + 1}"
        ses.add(User(telegram_id=tg_id, pseudo=next_pseudo, avatar_emoji="👤"))
        await ses.commit()


# ─────────────────────  Offre 90 jours gratuits  ─────────────────────────
async def free90_slots_left() -> int:
    async with async_session() as ses:
        used = await ses.scalar(
            select(func.count()).select_from(User).where(User.free90_claimed == True)
        )
        used = used or 0
        left = FREE90_LIMIT - used
        return left if left > 0 else 0


async def claim_free90(telegram_id: int) -> bool:
    """
    Attribue 90 jours gratuits en empilant dans paid_until.
    Retourne True si succès (idempotent si déjà pris), False si plus de places.
    """
    async with async_session() as ses:
        # recheck slots dans la même transaction
        used = await ses.scalar(
            select(func.count()).select_from(User).where(User.free90_claimed == True)
        )
        used = used or 0
        if used >= FREE90_LIMIT:
            return False

        user = await ses.scalar(select(User).where(User.telegram_id == telegram_id))
        if not user:
            # stub minimal
            user = User(telegram_id=telegram_id, pseudo=f"_anon{telegram_id}", avatar_emoji="👤")
            ses.add(user)
            await ses.flush()

        if user.free90_claimed:
            # déjà pris → success idempotent
            return True

        now = datetime.utcnow()
        # si l’utilisateur a déjà un paid_until dans le futur, on empile, sinon on part de now
        base = user.paid_until if (user.paid_until and user.paid_until > now) else now
        user.paid_until = base + timedelta(days=90)
        user.is_member = True
        user.free90_claimed = True

        await ses.commit()
        return True


# ───────────────────────────────  POSTS  ──────────────────────────────────
async def get_posts_by_user(user_id: int) -> list[Post]:
    async with get_session() as s:
        result = await s.execute(
            select(Post)
            .where(
                Post.author_id == user_id,
                Post.parent_id.is_(None),        # racines only
                Post.reply_count.is_not(None),   # threads racine
                Post.deleted.is_(False)
            )
            .order_by(Post.created_at.desc())
        )
        return result.scalars().all()


async def get_post_by_id(post_id: int) -> Post | None:
    async with get_session() as ses:
        return await ses.get(Post, post_id)


async def update_post(post_id: int, **fields):
    async with async_session() as ses:
        await ses.execute(update(Post).where(Post.id == post_id).values(**fields))
        await ses.commit()
