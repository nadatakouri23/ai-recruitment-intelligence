"""Composantes du score. Chaque fonction retourne un score entre 0 et 1, ou None quand la
composante ne peut pas être évaluée (information absente) : elle est alors écartée du calcul au
lieu de compter comme un zéro."""

from dataclasses import dataclass, field

from app.modules.matching.text import tokens

# Part de la couverture des compétences requises dans le score « compétences » (le reste =
# compétences optionnelles). Choix de conception, pas une vérité : à valider avec des données.
REQUIRED_SHARE = 0.8


@dataclass(frozen=True)
class SkillsMatch:
    score: float | None
    matched_required: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    matched_optional: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)


def skills_match(
    required: list[str], optional: list[str], candidate_skills: set[str]
) -> SkillsMatch:
    matched_req = [s for s in required if s in candidate_skills]
    missing_req = [s for s in required if s not in candidate_skills]
    matched_opt = [s for s in optional if s in candidate_skills]
    missing_opt = [s for s in optional if s not in candidate_skills]

    required_cov = len(matched_req) / len(required) if required else None
    optional_cov = len(matched_opt) / len(optional) if optional else None
    if required_cov is not None and optional_cov is not None:
        score: float | None = REQUIRED_SHARE * required_cov + (1 - REQUIRED_SHARE) * optional_cov
    else:
        score = required_cov if required_cov is not None else optional_cov
    return SkillsMatch(score, matched_req, missing_req, matched_opt, missing_opt)


def experience_score(required_years: int | None, total_months: int | None) -> float | None:
    """Années d'expérience cumulées / années demandées, plafonné à 1.

    None si l'offre n'exige rien OU si l'expérience du candidat n'a pas pu être lue (on ne
    présume pas qu'elle est nulle : l'extraction a pu échouer).
    """
    if required_years is None or required_years == 0 or total_months is None:
        return None
    return min(1.0, (total_months / 12) / required_years)


def education_score(required_level: int | None, candidate_level: int | None) -> float | None:
    """1 si le niveau est atteint ; sinon proportion du niveau demandé. None si non évaluable."""
    if required_level is None or required_level == 0 or candidate_level is None:
        return None
    return min(1.0, candidate_level / required_level)


def keyword_score(job_text: str, cv_text: str) -> float | None:
    """Part des mots significatifs de l'offre retrouvés dans le CV (baseline la plus simple)."""
    job_words = set(tokens(job_text))
    if not job_words:
        return None
    return len(job_words & set(tokens(cv_text))) / len(job_words)
