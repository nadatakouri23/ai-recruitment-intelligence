"""Route du matching : classer vos candidats pour une offre."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_matching_service
from app.modules.authentication.models import User
from app.modules.jobs.service import JobNotFoundError
from app.modules.matching.schemas import MatchRequest, MatchResponse
from app.modules.matching.service import MatchingService

router = APIRouter(prefix="/jobs", tags=["matching"])


@router.post("/{job_id}/matches", response_model=MatchResponse)
def match_candidates(
    job_id: int,
    request: MatchRequest | None = None,
    user: User = Depends(get_current_user),
    service: MatchingService = Depends(get_matching_service),
) -> MatchResponse:
    """Classe vos candidats pour cette offre, avec le détail de chaque score.

    Aide à la décision uniquement : le score est relatif à ce lot de candidats et ne remplace pas
    l'examen du recruteur. Le nom du candidat n'entre jamais dans le calcul ; `anonymize=true` le
    retire aussi de la réponse.
    """
    try:
        return service.match(user.id, job_id, request or MatchRequest())
    except JobNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Offre introuvable.") from None
