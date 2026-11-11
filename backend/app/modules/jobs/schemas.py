"""Schémas de l'API des offres."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.jobs.models import Job
from app.modules.jobs.profile import JobProfile


class JobOverrides(BaseModel):
    """Corrections du recruteur. Un champ absent (None) laisse l'analyse automatique telle quelle ;
    une liste vide ([]) vide explicitement le champ."""

    required_skills: list[str] | None = Field(default=None, max_length=60)
    optional_skills: list[str] | None = Field(default=None, max_length=60)
    min_experience_years: int | None = Field(default=None, ge=0, le=40)
    # Années après le bac : 2, 3, 5 ou 8 (doctorat).
    education_level: int | None = Field(default=None, ge=0, le=8)


class JobCreate(JobOverrides):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=20, max_length=20_000)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le titre ne peut pas être vide.")
        return value


class JobUpdate(JobOverrides):
    title: str | None = Field(default=None, min_length=1, max_length=200)


class JobSummary(BaseModel):
    id: int
    title: str
    required_skills: list[str]
    optional_skills: list[str]
    min_experience_years: int | None
    created_at: datetime

    @classmethod
    def from_job(cls, job: Job) -> "JobSummary":
        profile = JobProfile.model_validate(job.profile)
        return cls(
            id=job.id,
            title=job.title,
            required_skills=profile.required_skills,
            optional_skills=profile.optional_skills,
            min_experience_years=profile.min_experience_years,
            created_at=job.created_at,
        )


class JobRead(BaseModel):
    id: int
    title: str
    description: str
    created_at: datetime
    profile: JobProfile

    @classmethod
    def from_job(cls, job: Job) -> "JobRead":
        return cls(
            id=job.id,
            title=job.title,
            description=job.description,
            created_at=job.created_at,
            profile=JobProfile.model_validate(job.profile),
        )


class JobList(BaseModel):
    items: list[JobSummary]
    total: int
    limit: int
    offset: int
