"""Dépendances FastAPI partagées : session de base, utilisateur courant, contrôle de rôle."""

from collections.abc import Iterator

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import InvalidTokenError
from app.modules.authentication.models import Role, User
from app.modules.authentication.repository import UserRepository
from app.modules.authentication.service import AuthService
from app.modules.candidates.repository import CandidateRepository
from app.modules.candidates.service import CandidateService
from app.modules.documents.storage import FileStorage
from app.modules.embeddings.embedder import Embedder, EmbeddingUnavailableError, build_embedder
from app.modules.embeddings.repository import ChunkRepository
from app.modules.embeddings.service import IndexingService, SearchService
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import JobService
from app.modules.llm.errors import LLMDisabledError
from app.modules.llm.providers import LLMProvider, build_provider
from app.modules.llm.service import LLMService
from app.modules.matching.service import MatchingService

log = structlog.get_logger()

# tokenUrl : adresse que Swagger appelle pour obtenir un jeton (bouton « Authorize »).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_db(request: Request) -> Iterator[Session]:
    """Une session par requête HTTP, fermée à la fin même en cas d'erreur."""
    with request.app.state.session_factory() as session:
        yield session


def get_candidate_service(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> CandidateService:
    return CandidateService(
        CandidateRepository(session),
        FileStorage(settings.upload_dir),
        settings,
        indexer=_indexing_service(session, settings),
    )


def get_job_service(session: Session = Depends(get_db)) -> JobService:
    return JobService(JobRepository(session))


def get_matching_service(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> MatchingService:
    return MatchingService(
        JobRepository(session),
        CandidateRepository(session),
        settings,
        chunks=ChunkRepository(session),
        embedder=_embedder_or_none(settings),
    )


def get_llm_service(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> LLMService:
    """Service LLM. Une clé absente n'empêche pas l'API de démarrer : l'appel répond 503 en
    nommant la variable manquante (jamais sa valeur)."""
    provider: LLMProvider | None = None
    reason: str | None = None
    try:
        provider = build_provider(settings)
    except LLMDisabledError as exc:
        reason = str(exc)
    return LLMService(
        provider,
        settings.llm_max_input_chars,
        CandidateRepository(session),
        JobRepository(session),
        get_matching_service(session, settings),
        disabled_reason=reason,
    )


def _embedder_or_none(settings: Settings) -> Embedder | None:
    """Les embeddings sont facultatifs : un modèle indisponible ne doit casser ni l'import d'un
    CV ni le matching. L'erreur est journalisée et visible dans /search/status."""
    try:
        return build_embedder(settings)
    except EmbeddingUnavailableError as exc:
        log.error("embedder_unavailable", provider=settings.embedding_provider, error=str(exc))
        return None


def _indexing_service(session: Session, settings: Settings) -> IndexingService:
    return IndexingService(
        ChunkRepository(session), CandidateRepository(session), _embedder_or_none(settings)
    )


def get_indexing_service(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> IndexingService:
    return _indexing_service(session, settings)


def get_search_service(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> SearchService:
    return SearchService(ChunkRepository(session), _embedder_or_none(settings))


def get_auth_service(
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> AuthService:
    return AuthService(UserRepository(session), settings)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    service: AuthService = Depends(get_auth_service),
) -> User:
    """Utilisateur authentifié, ou 401."""
    try:
        return service.get_user_from_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise ou jeton invalide.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Utilisateur authentifié ET administrateur, ou 403."""
    if user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Accès réservé aux administrateurs."
        )
    return user
