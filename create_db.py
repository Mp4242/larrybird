# create_db.py
import asyncio
from database.database import engine, Base

# 🚨 Ces imports sont obligatoires pour que les tables soient créées !
from database import user, post  # ajoute tous les modules qui contiennent des modèles

async def create():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Base de données initialisée avec succès.")

if __name__ == "__main__":
    asyncio.run(create())
