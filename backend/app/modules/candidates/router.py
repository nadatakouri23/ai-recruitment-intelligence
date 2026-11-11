"""Routes HTTP des candidats : import de CV, consultation, suppression."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status

from app.api.deps import get_candidate_service, get_current_user
from app.modules.authentication.models import User
from app.modules.candidates.schemas import (
    CandidateList,
    CandidateRead,
    CandidateSummary,
    CandidateText,
)
from app.modules.candidates.service import (
    CandidateNotFoundError,
    CandidateService,
    DuplicateCVError,
)
from app.modules.documents.extraction import FileTooLargeError, InvalidUploadError

router = APIRouter(prefix="/candidates", tags=["candidates"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidat introuvable.")


@router.post("", response_model=CandidateRead, status_code=status.HTTP_201_CREATED)
def upload_cv(
    file: UploadFile = File(description="CV au format PDF ou DOCX"),
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateRead:
    """Importe un CV, en extrait le texte et crée le profil structuré du candidat.

    Cette route est synchrone (exécutée dans un thread) : l'extraction d'un PDF est coûteuse en CPU
    et ne doit pas bloquer la boucle d'événements.
    """
    # On lit au plus « limite + 1 » octets : un fichier géant n'est jamais chargé en mémoire.
    content = file.file.read(service.max_upload_bytes + 1)
    try:
        candidate = service.import_cv(user.id, file.filename, content)
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from None
    except InvalidUploadError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None
    except DuplicateCVError as exc:
        suffix = f" (candidat n° {exc.candidate_id})" if exc.candidate_id else ""
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"Ce CV a déjà été importé{suffix}."
        ) from None
    return CandidateRead.from_candidate(candidate)


@router.get("", response_model=CandidateList)
def list_candidates(
    q: str | None = Query(default=None, max_length=100, description="Recherche dans le nom"),
    skill: str | None = Query(
        default=None,
        max_length=60,
        description="Compétence (FR ou EN : « apprentissage automatique », « ML »…)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateList:
    """Liste vos candidats (les plus récents d'abord), avec filtres optionnels."""
    candidates, total = service.list(user.id, name_query=q, skill=skill, limit=limit, offset=offset)
    return CandidateList(
        items=[CandidateSummary.from_candidate(c) for c in candidates],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{candidate_id}", response_model=CandidateRead)
def get_candidate(
    candidate_id: int,
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateRead:
    try:
        return CandidateRead.from_candidate(service.get(user.id, candidate_id))
    except CandidateNotFoundError:
        raise _NOT_FOUND from None


@router.get("/{candidate_id}/text", response_model=CandidateText)
def get_candidate_text(
    candidate_id: int,
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> CandidateText:
    """Texte brut lu dans le CV : permet de vérifier ce que le parseur a réellement vu."""
    try:
        candidate = service.get(user.id, candidate_id)
    except CandidateNotFoundError:
        raise _NOT_FOUND from None
    return CandidateText(candidate_id=candidate.id, text=candidate.document.extracted_text)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_candidate(
    candidate_id: int,
    user: User = Depends(get_current_user),
    service: CandidateService = Depends(get_candidate_service),
) -> Response:
    """Supprime définitivement le candidat, son texte extrait et le fichier d'origine."""
    try:
        service.delete(user.id, candidate_id)
    except CandidateNotFoundError:
        raise _NOT_FOUND from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
