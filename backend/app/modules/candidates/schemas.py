"""Schémas de l'API des candidats."""

from datetime import datetime

from pydantic import BaseModel

from app.modules.candidates.models import Candidate
from app.modules.candidates.profile import CandidateProfile


class CandidateSummary(BaseModel):
    """Ligne de liste : l'essentiel, sans le profil complet."""

    id: int
    full_name: str | None
    email: str | None
    original_filename: str
    skills: list[str]
    total_experience_months: int | None
    extraction_completeness: float
    created_at: datetime

    @classmethod
    def from_candidate(cls, candidate: Candidate) -> "CandidateSummary":
        profile = CandidateProfile.model_validate(candidate.profile)
        return cls(
            id=candidate.id,
            full_name=candidate.full_name,
            email=candidate.email,
            original_filename=candidate.document.original_filename,
            skills=[skill.name for skill in profile.skills],
            total_experience_months=profile.total_experience_months,
            extraction_completeness=profile.report.extraction_completeness,
            created_at=candidate.created_at,
        )


class CandidateRead(BaseModel):
    """Détail d'un candidat avec son profil structuré complet."""

    id: int
    original_filename: str
    kind: str
    size_bytes: int
    page_count: int | None
    created_at: datetime
    profile: CandidateProfile

    @classmethod
    def from_candidate(cls, candidate: Candidate) -> "CandidateRead":
        document = candidate.document
        return cls(
            id=candidate.id,
            original_filename=document.original_filename,
            kind=document.kind,
            size_bytes=document.size_bytes,
            page_count=document.page_count,
            created_at=candidate.created_at,
            profile=CandidateProfile.model_validate(candidate.profile),
        )


class CandidateList(BaseModel):
    items: list[CandidateSummary]
    total: int
    limit: int
    offset: int


class CandidateText(BaseModel):
    """Texte extrait du CV, pour vérifier ce que le parseur a réellement lu."""

    candidate_id: int
    text: str
