"""Point d'entrée de l'API : construit l'application FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api import health
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    Accepter `settings` en paramètre permet aux tests de fournir leur propre
    configuration sans toucher à l'environnement.
    """
    settings = settings or get_settings()
    configure_logging(settings)
    log = structlog.get_logger()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Code exécuté au démarrage (avant le yield) et à l'arrêt (après).
        log.info("app_started", app=settings.app_name, environment=settings.environment)
        yield
        log.info("app_stopped")

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    return app


# Volontairement AUCUN `app = create_app()` ici : l'import de ce module ne doit
# rien exécuter (ni lire .env, ni configurer le logging). Uvicorn appelle la
# factory lui-même :  uvicorn app.main:create_app --factory
