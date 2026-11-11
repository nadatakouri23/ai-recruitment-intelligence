"""Routes HTTP des offres d'emploi."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import get_current_user, get_job_service
from app.modules.authentication.models import User
from app.modules.jobs.schemas import JobCreate, JobList, JobRead, JobSummary, JobUpdate
from app.modules.jobs.service import JobNotFoundError, JobService, UnknownSkillsError

router = APIRouter(prefix="/jobs", tags=["jobs"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offre introuvable.")


def _unknown_skills(exc: UnknownSkillsError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=(
            "Compétences absentes du référentiel (elles ne pourraient être trouvées chez aucun "
            f"candidat) : {', '.join(exc.unknown)}."
        ),
    )


@router.post("", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobRead:
    """Crée une offre : le texte est analysé automatiquement, puis vos corrections éventuelles
    (compétences, expérience, niveau d'études) sont appliquées par-dessus."""
    try:
        return JobRead.from_job(service.create(user.id, payload))
    except UnknownSkillsError as exc:
        raise _unknown_skills(exc) from None


@router.get("", response_model=JobList)
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobList:
    jobs, total = service.list(user.id, limit=limit, offset=offset)
    return JobList(
        items=[JobSummary.from_job(j) for j in jobs], total=total, limit=limit, offset=offset
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobRead:
    try:
        return JobRead.from_job(service.get(user.id, job_id))
    except JobNotFoundError:
        raise _NOT_FOUND from None


@router.patch("/{job_id}", response_model=JobRead)
def update_job(
    job_id: int,
    payload: JobUpdate,
    user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> JobRead:
    """Corrige l'offre structurée (le texte de l'offre, lui, ne change pas)."""
    try:
        return JobRead.from_job(service.update(user.id, job_id, payload))
    except JobNotFoundError:
        raise _NOT_FOUND from None
    except UnknownSkillsError as exc:
        raise _unknown_skills(exc) from None


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: int,
    user: User = Depends(get_current_user),
    service: JobService = Depends(get_job_service),
) -> Response:
    try:
        service.delete(user.id, job_id)
    except JobNotFoundError:
        raise _NOT_FOUND from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
