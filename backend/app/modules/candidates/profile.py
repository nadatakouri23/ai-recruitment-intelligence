"""Profil candidat structuré, produit par le parseur de CV.

Principes :
- On n'invente jamais une information : un champ absent du CV reste `None` / liste vide.
- `origin` distingue ce qui est LU dans le CV ("extracted") de ce qui est CALCULÉ à partir de
  ce qu'on a lu ("inferred", par exemple une durée déduite de deux dates).
- `snippet` garde l'extrait du CV qui justifie l'information (traçabilité).
- Les caractéristiques protégées (âge / date de naissance, genre, nationalité, situation
  familiale, photo, adresse) ne sont volontairement PAS extraites.
"""

from typing import Literal

from pydantic import BaseModel, Field

Origin = Literal["extracted", "inferred"]
DetectedLanguage = Literal["fr", "en", "unknown"]


class Provenance(BaseModel):
    """D'où vient une information."""

    origin: Origin = "extracted"
    section: str | None = None
    snippet: str = Field(default="", max_length=240)


class SkillItem(BaseModel):
    name: str  # nom canonique (ex. "Machine Learning"), identique en FR et en EN
    category: str
    mentions: int = Field(ge=1)  # nombre de lignes du CV qui l'évoquent
    listed_in_skills_section: bool
    provenance: Provenance


class EducationItem(BaseModel):
    degree: str | None = None
    institution: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    provenance: Provenance


class ExperienceItem(BaseModel):
    title: str | None = None
    company: str | None = None
    start: str | None = None  # "AAAA" ou "AAAA-MM", tel qu'écrit dans le CV
    end: str | None = None
    is_current: bool = False
    # Calculé à partir des dates : listé dans `inferred_fields`, jamais lu directement.
    duration_months: int | None = Field(default=None, ge=0)
    inferred_fields: list[str] = Field(default_factory=list)
    description: str = ""
    skills: list[str] = Field(default_factory=list)  # compétences citées dans cette expérience
    provenance: Provenance


class ProjectItem(BaseModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    provenance: Provenance


class LanguageItem(BaseModel):
    language: str  # nom canonique en anglais (ex. "French")
    level: str | None = None  # texte du CV : "C1", "courant", "native"…
    provenance: Provenance


class CertificationItem(BaseModel):
    name: str
    provenance: Provenance


class ParsingReport(BaseModel):
    """Qualité et limites de l'extraction : à afficher avec le profil."""

    parser_version: str
    detected_language: DetectedLanguage
    sections_found: list[str]
    warnings: list[str] = Field(default_factory=list)
    # Mesure la COMPLÉTUDE (quelles informations attendues ont été trouvées), pas l'EXACTITUDE :
    # une valeur élevée ne garantit pas que ce qui a été extrait est correct.
    extraction_completeness: float = Field(ge=0, le=1)
    inferred_fields: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    links: list[str] = Field(default_factory=list)
    summary: str | None = None
    skills: list[SkillItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    # Durée cumulée (périodes qui se chevauchent comptées une seule fois). Toujours déduite.
    total_experience_months: int | None = Field(default=None, ge=0)
    field_evidence: dict[str, Provenance] = Field(default_factory=dict)
    report: ParsingReport
