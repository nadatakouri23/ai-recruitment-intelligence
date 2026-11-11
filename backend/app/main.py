"""Point d'entrée de l'API : construit l'application FastAPI."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api import health
from app.core.config import Settings, get_settings
from app.core.database import create_db_engine, create_session_factory
from app.core.logging import configure_logging
from app.modules.authentication.router import auth_router, users_router
from app.modules.candidates.router import router as candidates_router
from app.modules.embeddings.router import router as search_router
from app.modules.jobs.router import router as jobs_router
from app.modules.llm.router import router as llm_router
from app.modules.matching.router import router as matching_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    Accepter `settings` en paramètre permet aux tests de fournir leur propre
    configuration sans toucher à l'environnement.
    """
    settings = settings or get_settings()
    configure_logging(settings)
    log = structlog.get_logger()

    # Le moteur ne se connecte pas à la création : créer l'application n'exige pas
    # que la base soit disponible (les tests sans base continuent de fonctionner).
    engine = create_db_engine(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Code exécuté au démarrage (avant le yield) et à l'arrêt (après).
        log.info("app_started", app=settings.app_name, environment=settings.environment)
        yield
        engine.dispose()  # ferme proprement les connexions du pool
        log.info("app_stopped")

    app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)

    app.include_router(health.router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(candidates_router)
    app.include_router(jobs_router)
    app.include_router(matching_router)
    app.include_router(search_router)
    app.include_router(llm_router)
    return app


# Volontairement AUCUN `app = create_app()` ici : l'import de ce module ne doit
# rien exécuter (ni lire .env, ni configurer le logging). Uvicorn appelle la
# factory lui-même :  uvicorn app.main:create_app --factory
