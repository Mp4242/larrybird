from contextlib import asynccontextmanager
from typing import Iterable, Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound

from database import async_session
from database.user import User
from database.post import Post


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


async def create_user(telegram_id: int, pseudo: str, emoji: str = "👤") -> User:
    async with get_session() as ses:
        user = User(telegram_id=telegram_id, pseudo=pseudo, avatar_emoji=emoji)
        ses.add(user)
        await ses.commit()
        return user


async def update_user(telegram_id: int, **kwargs) -> None:
    async with get_session() as ses:
        stmt = update(User).where(User.telegram_id == telegram_id).values(**kwargs)
        await ses.execute(stmt)
        await ses.commit()


# ───────────────────────────────  POST  ───────────────────────────────────
async def get_posts_by_user(user_id: int, *, only_original: bool = False):
    async with get_session() as ses:
        stmt = select(Post).where(
            Post.author_id == user_id,
            Post.deleted.is_(False)
        )
        if only_original:
            stmt = stmt.where(Post.parent_id.is_(None))
        return (await ses.execute(stmt)).scalars().all()

async def get_post_by_id(post_id: int) -> Post | None:
    async with get_session() as ses:
        return await ses.get(Post, post_id)

async def update_post(post_id: int, **kwargs):
    async with get_session() as ses:
        await ses.execute(
            update(Post).where(Post.id == post_id).values(**kwargs)
        )
        await ses.commit()
