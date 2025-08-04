# create_db.py
import asyncio

from database.database import engine, Base

# 🚨 Ces imports explicites sont nécessaires !
from database import user, post, milestone_like, post_like # ajoute ici chaque module contenant un modèle


async def create() -> None:
    """Crée toutes les tables de la base (SQLite ou autre)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Base de données initialisée avec succès.")

if __name__ == "__main__":
    asyncio.run(create())