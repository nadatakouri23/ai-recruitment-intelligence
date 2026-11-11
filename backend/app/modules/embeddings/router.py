"""Routes : recherche de candidats, état et reconstruction de l'index."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_app_settings,
    get_current_user,
    get_indexing_service,
    get_search_service,
)
from app.core.config import Settings
from app.modules.authentication.models import User
from app.modules.embeddings.schemas import IndexStatus, ReindexReport, SearchRequest, SearchResponse
from app.modules.embeddings.service import IndexingService, SearchService, SemanticDisabledError

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/candidates", response_model=SearchResponse)
def search_candidates(
    request: SearchRequest,
    user: User = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """Cherche dans vos candidats : par mots-clés, par le sens, ou les deux (hybride).

    Le passage du CV qui justifie chaque résultat est affiché : vérifiez-le avant de conclure.
    """
    try:
        return service.search(user.id, request)
    except SemanticDisabledError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "La recherche sémantique est désactivée (EMBEDDING_PROVIDER=none). "
                "Utilisez le mode « keyword », ou activez les embeddings."
            ),
        ) from None


@router.get("/status", response_model=IndexStatus)
def index_status(
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
    settings: Settings = Depends(get_app_settings),
) -> IndexStatus:
    return service.status(user.id, settings.embedding_provider)


@router.post("/reindex", response_model=ReindexReport)
def reindex(
    user: User = Depends(get_current_user),
    service: IndexingService = Depends(get_indexing_service),
) -> ReindexReport:
    """Indexe vos candidats sans passages ou sans vecteur à jour (sans effet s'il n'y en a pas)."""
    return service.reindex(user.id)
