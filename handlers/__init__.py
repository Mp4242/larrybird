from database.database import Base, async_session, init_db

from .onboarding import onboarding_router
from .main       import main_router
from .counter    import counter_router
from .replies    import replies_router
from .post       import posts_router          # ← nom exact
from .settings   import settings_router

# alias optionnel pour rétro-compatibilité
post_router = posts_router

__all__ = [
    "Base", "async_session", "init_db",
    "onboarding_router", "main_router", "counter_router",
    "replies_router", "posts_router",   # ← même nom que l’objet importé
    "settings_router",
]
