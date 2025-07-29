# database/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import DB_PATH

# 1. Créer Base tout de suite
Base = declarative_base()

# 2. Construire l’engine + session
engine = create_async_engine(DB_PATH, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# 3. Importer les modèles APRÈS (ils verront déjà Base)
from database import user, post   # noqa: E402

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
