"""Offre d'emploi structurée, produite par l'analyse du texte puis corrigeable par le recruteur."""

from typing import Literal

from pydantic import BaseModel, Field

from app.modules.candidates.profile import DetectedLanguage

JobSkillSource = Literal["analysis", "recruiter"]


class JobProfile(BaseModel):
    title: str
    required_skills: list[str] = Field(default_factory=list)
    optional_skills: list[str] = Field(default_factory=list)
    # Compétences requises de nature technique (langages, frameworks, données, cloud…).
    technical_requirements: list[str] = Field(default_factory=list)
    min_experience_years: int | None = Field(default=None, ge=0, le=40)
    # Niveau d'études minimal, en années après le bac (5 = Bac+5, 8 = doctorat).
    education_level: int | None = Field(default=None, ge=0, le=8)
    responsibilities: list[str] = Field(default_factory=list)
    preferred_qualifications: list[str] = Field(default_factory=list)
    detected_language: DetectedLanguage = "unknown"
    parser_version: str
    # Champs corrigés à la main par le recruteur : prioritaires sur l'analyse automatique.
    recruiter_overrides: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
