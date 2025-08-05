from contextlib import asynccontextmanager
from typing import Iterable, Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound

from database import async_session
from database.user import User
from database.post import Post
from sqlalchemy import select, func 
import re 

# ───────────────────────────────  SESSION  ────────────────────────────────
@asynccontextmanager
async def get_session():
    """
    Helper async-context manager pour obtenir une session et la fermer proprement.
    Usage :
        async with get_session() as ses:
            ...
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


# ───────────────────────────────  USER  ───────────────────────────────────
async def get_user(telegram_id: int) -> User | None:
    async with get_session() as ses:
        stmt = select(User).where(User.telegram_id == telegram_id)
        res = await ses.execute(stmt)
        return res.scalar_one_or_none()

async def free_slots_left() -> int:
    async with async_session() as ses:
        used = await ses.scalar(
            select(func.count()).select_from(User).where(User.lifetime_access == True)
        )
    return max(0, 100 - (used or 0))
    
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
        pseudos = (
            await ses.scalars(
                select(User.pseudo).where(User.pseudo.like("_anon%"))
            )
        ).all()

        max_n = 0
        for p in pseudos:
            m = _ANON_RE.match(p or "")
            if m:
                n = int(m.group(1) or 1)   # _anon => 1
                max_n = max(max_n, n)

        next_pseudo = "_anon" if max_n == 0 else f"_anon{max_n + 1}"

        ses.add(User(telegram_id=tg_id, pseudo=next_pseudo, avatar_emoji="👤"))
        await ses.commit()

async def update_user(telegram_id: int, **kwargs) -> None:
    async with get_session() as ses:
        stmt = update(User).where(User.telegram_id == telegram_id).values(**kwargs)
        await ses.execute(stmt)
        await ses.commit()


# ───────────────────────────────  POST  ───────────────────────────────────
async def get_posts_by_user(user_id: int) -> list[Post]:
    async with get_session() as s:
        result = await s.execute(
            select(Post)
            .where(
                Post.author_id == user_id, 
                Post.parent_id.is_(None),  # 👈 racines only
                Post.reply_count.is_not(None),    # ← uniquement les threads racine
                Post.deleted.is_(False)           # ← pas déjà supprimés
            )
            .order_by(Post.created_at.desc())
        )
        return result.scalars().all()

async def get_post_by_id(post_id: int) -> Post | None:
    async with get_session() as ses:
        return await ses.get(Post, post_id)

async def update_post(post_id: int, **fields):
    async with async_session() as ses:
        await ses.execute(
            update(Post).where(Post.id == post_id).values(**fields)
        )
        await ses.commit()
