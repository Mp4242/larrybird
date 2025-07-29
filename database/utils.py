from sqlalchemy import select, update
from sqlalchemy.exc import NoResultFound
from database import async_session
from database.user import User
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_user(telegram_id: int) -> User | None:
    async with get_session() as session:
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

async def create_user(telegram_id: int, pseudo: str, emoji: str = "👤") -> User:
    async with get_session() as session:
        user = User(telegram_id=telegram_id, pseudo=pseudo, avatar_emoji=emoji)
        session.add(user)
        await session.commit()
        return user

async def update_user(telegram_id: int, **kwargs) -> None:
    async with get_session() as session:
        stmt = update(User).where(User.telegram_id == telegram_id).values(**kwargs)
        await session.execute(stmt)
        await session.commit()
