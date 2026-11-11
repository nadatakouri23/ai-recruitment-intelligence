"""Schémas du résultat de matching : tout ce qui sert à comprendre un score."""

from typing import Literal

from pydantic import BaseModel, Field

from app.modules.matching.weights import MatchingWeights

ComponentName = Literal["skills", "experience", "education", "tfidf", "keyword", "semantic"]
ConfidenceLevel = Literal["low", "medium", "high"]


class ComponentResult(BaseModel):
    name: ComponentName
    label: str
    # Score brut de la composante, entre 0 et 1 ; None = non évaluable pour ce candidat.
    raw_score: float | None
    # Poids effectif après exclusion des composantes non évaluables (somme des poids effectifs = 1).
    effective_weight: float
    # Points apportés au score final : la somme des contributions est égale au score.
    contribution: float
    note: str = ""


class SkillsDetail(BaseModel):
    matched_required: list[str]
    missing_required: list[str]
    matched_optional: list[str]
    missing_optional: list[str]
    # Extrait du CV qui justifie chaque compétence trouvée.
    evidence: dict[str, str]


class RelevantExperience(BaseModel):
    title: str | None
    company: str | None
    duration_months: int | None
    matching_skills: list[str]


class Confidence(BaseModel):
    """Fiabilité de L'ANALYSE (qualité des données lues), pas probabilité de réussite."""

    level: ConfidenceLevel
    value: float = Field(ge=0, le=1)
    reasons: list[str]


class CandidateRef(BaseModel):
    id: int
    # Absents en mode anonyme.
    full_name: str | None = None
    email: str | None = None


class MatchResult(BaseModel):
    rank: int
    candidate: CandidateRef
    # 0 à 100. Score RELATIF à ce lot de candidats et à cette offre : ce n'est pas une probabilité.
    score: float = Field(ge=0, le=100)
    components: list[ComponentResult]
    skills: SkillsDetail
    relevant_experience: list[RelevantExperience]
    explanations: list[str]
    warnings: list[str]
    confidence: Confidence


class MatchRequest(BaseModel):
    weights: MatchingWeights | None = Field(
        default=None, description="Poids personnalisés ; par défaut ceux du serveur."
    )
    limit: int = Field(default=20, ge=1, le=100)
    min_score: float = Field(default=0, ge=0, le=100)
    # True : nom et e-mail retirés de la réponse (évaluation « à l'aveugle »).
    anonymize: bool = False


class MatchResponse(BaseModel):
    job_id: int
    job_title: str
    weights_used: MatchingWeights
    pool_size: int
    pool_truncated: bool
    returned: int
    results: list[MatchResult]
    limitations: list[str]
