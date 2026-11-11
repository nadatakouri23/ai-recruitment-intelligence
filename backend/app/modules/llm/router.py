"""Routes LLM. Désactivées par défaut ; le consentement est exigé à CHAQUE appel."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_app_settings, get_current_user, get_llm_service
from app.core.config import Settings
from app.modules.authentication.models import User
from app.modules.candidates.service import CandidateNotFoundError
from app.modules.jobs.service import JobNotFoundError
from app.modules.llm.errors import LLMDisabledError, LLMOutputError, LLMProviderError
from app.modules.llm.providers import DEFAULT_MODELS
from app.modules.llm.schemas import (
    CVExtractionResult,
    ExplanationResult,
    ExternalProcessingConsent,
    JobAnalysisResult,
    LLMStatus,
    SummaryResult,
)
from app.modules.llm.service import CandidateNotRankedError, LLMService

router = APIRouter(tags=["llm"])

_NO_CANDIDATE = HTTPException(status.HTTP_404_NOT_FOUND, detail="Candidat introuvable.")
_NO_JOB = HTTPException(status.HTTP_404_NOT_FOUND, detail="Offre introuvable.")


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, LLMDisabledError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, (LLMProviderError, LLMOutputError)):
        return HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, CandidateNotFoundError):
        return _NO_CANDIDATE
    if isinstance(exc, JobNotFoundError):
        return _NO_JOB
    if isinstance(exc, CandidateNotRankedError):
        return HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Candidat introuvable pour cette offre."
        )
    raise exc


@router.get("/llm/status", response_model=LLMStatus)
def llm_status(
    _user: User = Depends(get_current_user), settings: Settings = Depends(get_app_settings)
) -> LLMStatus:
    """État de la fonction LLM (jamais la clé)."""
    if settings.llm_provider == "none":
        return LLMStatus(
            enabled=False,
            provider="none",
            model=None,
            note="Désactivée (LLM_PROVIDER=none). Aucun texte n'est envoyé à un service externe.",
        )
    return LLMStatus(
        enabled=True,
        provider=settings.llm_provider,
        model=settings.llm_model or DEFAULT_MODELS[settings.llm_provider],
        note="Fournisseur EXTERNE : chaque appel envoie du texte anonymisé, avec consentement.",
    )


@router.post("/candidates/{candidate_id}/llm/extraction", response_model=CVExtractionResult)
def extract_cv(
    candidate_id: int,
    _consent: ExternalProcessingConsent,
    user: User = Depends(get_current_user),
    service: LLMService = Depends(get_llm_service),
) -> CVExtractionResult:
    """Extraction structurée par LLM, comparée à l'extraction par règles. N'écrit rien en base."""
    try:
        return service.extract_cv(user.id, candidate_id)
    except (LLMDisabledError, LLMProviderError, LLMOutputError, CandidateNotFoundError) as exc:
        raise _translate(exc) from None


@router.post("/candidates/{candidate_id}/llm/summary", response_model=SummaryResult)
def summarize_cv(
    candidate_id: int,
    _consent: ExternalProcessingConsent,
    user: User = Depends(get_current_user),
    service: LLMService = Depends(get_llm_service),
) -> SummaryResult:
    try:
        return service.summarize_cv(user.id, candidate_id)
    except (LLMDisabledError, LLMProviderError, LLMOutputError, CandidateNotFoundError) as exc:
        raise _translate(exc) from None


@router.post("/jobs/{job_id}/llm/analysis", response_model=JobAnalysisResult)
def analyze_job(
    job_id: int,
    _consent: ExternalProcessingConsent,
    user: User = Depends(get_current_user),
    service: LLMService = Depends(get_llm_service),
) -> JobAnalysisResult:
    """Suggestion d'analyse d'offre. Jamais appliquée automatiquement."""
    try:
        return service.analyze_job(user.id, job_id)
    except (LLMDisabledError, LLMProviderError, LLMOutputError, JobNotFoundError) as exc:
        raise _translate(exc) from None


@router.post(
    "/jobs/{job_id}/matches/{candidate_id}/llm/explanation", response_model=ExplanationResult
)
def explain_match(
    job_id: int,
    candidate_id: int,
    _consent: ExternalProcessingConsent,
    user: User = Depends(get_current_user),
    service: LLMService = Depends(get_llm_service),
) -> ExplanationResult:
    """Explication rédigée d'un classement DÉJÀ calculé (le score, lui, n'est pas modifié)."""
    try:
        return service.explain_match(user.id, job_id, candidate_id)
    except (
        LLMDisabledError,
        LLMProviderError,
        LLMOutputError,
        JobNotFoundError,
        CandidateNotRankedError,
    ) as exc:
        raise _translate(exc) from None
