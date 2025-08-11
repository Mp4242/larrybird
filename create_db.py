# create_db.py
import asyncio

from database.database import engine, Base

from database import user, post, post_like # chaque module contenant un modèle


async def create() -> None:
    """Crée toutes les tables de la base (SQLite ou autre)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Base de données initialisée avec succès.")

if __name__ == "__main__":
    asyncio.run(create())