"""Règles métier des offres : création avec analyse, correction par le recruteur, suppression."""

import structlog

from app.modules.candidates.parsing.skills import canonical_skill_name, skill_category
from app.modules.jobs.models import Job
from app.modules.jobs.parsing import analyze_job
from app.modules.jobs.profile import JobProfile
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.schemas import JobCreate, JobOverrides, JobUpdate

log = structlog.get_logger()

_TECHNICAL = {"programming", "web", "data_ml", "database", "cloud_devops"}


class JobNotFoundError(Exception):
    pass


class UnknownSkillsError(Exception):
    """Compétences corrigées par le recruteur mais absentes du référentiel."""

    def __init__(self, unknown: list[str]) -> None:
        super().__init__(", ".join(unknown))
        self.unknown = unknown


def _resolve(skills: list[str]) -> list[str]:
    """Noms canoniques sans doublon. Une compétence hors référentiel est refusée : aucun candidat
    ne pourrait jamais la « posséder », ce qui fausserait tout classement."""
    resolved: list[str] = []
    unknown: list[str] = []
    for skill in skills:
        name = canonical_skill_name(skill)
        if name is None:
            unknown.append(skill)
        elif name not in resolved:
            resolved.append(name)
    if unknown:
        raise UnknownSkillsError(unknown)
    return resolved


def apply_overrides(profile: JobProfile, overrides: JobOverrides) -> JobProfile:
    """Applique les corrections du recruteur et les consigne dans `recruiter_overrides`."""
    changed = set(profile.recruiter_overrides)
    if overrides.required_skills is not None:
        profile.required_skills = _resolve(overrides.required_skills)
        changed.add("required_skills")
    if overrides.optional_skills is not None:
        profile.optional_skills = _resolve(overrides.optional_skills)
        changed.add("optional_skills")
    if overrides.min_experience_years is not None:
        profile.min_experience_years = overrides.min_experience_years
        changed.add("min_experience_years")
    if overrides.education_level is not None:
        profile.education_level = overrides.education_level
        changed.add("education_level")

    # Une compétence ne peut pas être à la fois requise et optionnelle : « requis » l'emporte.
    profile.optional_skills = [
        s for s in profile.optional_skills if s not in profile.required_skills
    ]
    profile.technical_requirements = [
        s for s in profile.required_skills if skill_category(s) in _TECHNICAL
    ]
    profile.recruiter_overrides = sorted(changed)
    if profile.required_skills or profile.optional_skills:
        # L'avertissement « aucune compétence détectée » n'a plus lieu d'être.
        profile.warnings = [w for w in profile.warnings if "Aucune compétence" not in w]
    return profile


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def create(self, owner_id: int, data: JobCreate) -> Job:
        profile = apply_overrides(analyze_job(data.title, data.description), data)
        job = Job(
            owner_id=owner_id,
            title=profile.title,
            description=data.description,
            profile=profile.model_dump(mode="json"),
        )
        self._repository.add(job)
        log.info("job_created", job_id=job.id, owner_id=owner_id, warnings=len(profile.warnings))
        return job

    def get(self, owner_id: int, job_id: int) -> Job:
        job = self._repository.get(owner_id, job_id)
        if job is None:
            raise JobNotFoundError  # même réponse pour « inexistante » et « à un autre »
        return job

    def list(self, owner_id: int, *, limit: int, offset: int) -> tuple[list[Job], int]:
        return self._repository.list(owner_id, limit=limit, offset=offset)

    def update(self, owner_id: int, job_id: int, data: JobUpdate) -> Job:
        job = self.get(owner_id, job_id)
        profile = apply_overrides(JobProfile.model_validate(job.profile), data)
        if data.title is not None:
            job.title = profile.title = data.title.strip()
        job.profile = profile.model_dump(
            mode="json"
        )  # nouvelle valeur : SQLAlchemy détecte le changement
        self._repository.save(job)
        log.info("job_updated", job_id=job_id, owner_id=owner_id)
        return job

    def delete(self, owner_id: int, job_id: int) -> None:
        self._repository.delete(self.get(owner_id, job_id))
        log.info("job_deleted", job_id=job_id, owner_id=owner_id)
