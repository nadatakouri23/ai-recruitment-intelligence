"""Moteur de classement : combine les composantes en un score pondéré et explicable.

Fonction pure (aucun accès à la base ni au réseau) : mêmes entrées, mêmes sorties.
N'utilise que des informations liées au poste : compétences, expérience cumulée, niveau d'études
et texte des sections pertinentes. Jamais le nom, les contacts, les langues parlées, l'âge, etc.
"""

from dataclasses import dataclass
from datetime import date

from app.modules.candidates.parsing.dates import interval_of, merged_months
from app.modules.candidates.parsing.education import education_level, label
from app.modules.candidates.profile import CandidateProfile
from app.modules.jobs.profile import JobProfile
from app.modules.matching.components import (
    SkillsMatch,
    education_score,
    experience_score,
    keyword_score,
    skills_match,
)
from app.modules.matching.schemas import (
    CandidateRef,
    ComponentName,
    ComponentResult,
    Confidence,
    MatchResult,
    RelevantExperience,
    SkillsDetail,
)
from app.modules.matching.tfidf import tfidf_similarities
from app.modules.matching.weights import MatchingWeights

LIMITATIONS = [
    "Ce score aide à trier des candidats ; il ne mesure ni la compétence réelle ni l'aptitude au "
    "poste. La décision finale revient toujours au recruteur.",
    "Les compétences ne sont détectées que si elles figurent dans le référentiel et dans le CV.",
    "TF-IDF et mots-clés comparent des mots, pas des sens (pas de synonymes) ; la similarité "
    "sémantique n'est pas encore implémentée.",
    "Le score est relatif à l'offre et à ce lot de candidats : il n'a pas de valeur absolue et "
    "n'est pas comparable d'une recherche à l'autre.",
    "L'expérience est déduite des dates lues dans le CV ; un CV mal lu peut sous-estimer un "
    "profil. Seules comptent les années sur des postes qui mobilisent des compétences de l'offre.",
    "Les caractéristiques protégées (nom, âge, genre, nationalité, langues parlées, adresse, "
    "photo) ne sont pas utilisées. Des biais indirects dans le vocabulaire restent possibles.",
]

_LABELS: dict[ComponentName, str] = {
    "skills": "Compétences",
    "experience": "Expérience",
    "education": "Niveau d'études",
    "tfidf": "Similarité de texte (TF-IDF)",
    "keyword": "Mots-clés de l'offre",
    "semantic": "Similarité sémantique (embeddings)",
}
_ORDER: tuple[ComponentName, ...] = (
    "skills",
    "experience",
    "education",
    "tfidf",
    "keyword",
    "semantic",
)


@dataclass(frozen=True)
class CandidateInput:
    """Un candidat tel que le moteur le voit : un profil et un texte DÉJÀ anonymisé."""

    candidate_id: int
    profile: CandidateProfile
    text: str
    # Similarité sémantique avec l'offre (0 à 1), calculée AVANT le moteur à partir des embeddings.
    # None : embeddings désactivés ou candidat non indexé. Le moteur reste une fonction pure.
    semantic: float | None = None


def format_duration(months: int) -> str:
    years, rest = divmod(months, 12)
    parts = []
    if years:
        parts.append(f"{years} an{'s' if years > 1 else ''}")
    if rest or not years:
        parts.append(f"{rest} mois")
    return " ".join(parts)


@dataclass(frozen=True)
class ExperienceFit:
    """Expérience retenue pour le score.

    `months` : mois pris en compte (None = non évaluable). `basis` : « relevant » = seulement les
    postes qui mobilisent des compétences de l'offre ; « total » = toute l'expérience, quand l'offre
    ne contient aucune compétence qui permette de juger de la pertinence.
    """

    months: int | None
    total_months: int | None
    basis: str


def _experience_fit(job: JobProfile, profile: CandidateProfile, today: date) -> ExperienceFit:
    total = profile.total_experience_months
    if total is None:
        return ExperienceFit(None, None, "relevant")
    wanted = set(job.required_skills) | set(job.optional_skills)
    if not wanted:
        return ExperienceFit(total, total, "total")
    intervals = [
        interval
        for item in profile.experience
        if wanted & set(item.skills)
        and (interval := interval_of(item.start, item.end, item.is_current, today)) is not None
    ]
    # Périodes qui se chevauchent comptées une seule fois.
    return ExperienceFit(merged_months(intervals), total, "relevant")


def rank(
    job: JobProfile,
    job_text: str,
    candidates: list[CandidateInput],
    weights: MatchingWeights,
    today: date | None = None,
) -> list[MatchResult]:
    """Classe les candidats (meilleur d'abord, égalités départagées par identifiant croissant).

    `today` sert aux postes « en cours » ; fixé dans les tests pour des résultats reproductibles.
    """
    if not candidates:
        return []
    today = today or date.today()
    normalized = weights.normalized()
    similarities = tfidf_similarities(job_text, [c.text for c in candidates])
    scored = [
        _score(job, job_text, candidate, similarity, normalized, today)
        for candidate, similarity in zip(candidates, similarities, strict=True)
    ]
    scored.sort(key=lambda r: (-r.score, r.candidate.id))
    return [r.model_copy(update={"rank": position}) for position, r in enumerate(scored, start=1)]


def _score(
    job: JobProfile,
    job_text: str,
    candidate: CandidateInput,
    tfidf_value: float,
    weights: MatchingWeights,
    today: date,
) -> MatchResult:
    profile = candidate.profile
    has_text = bool(candidate.text.strip())
    fit = _experience_fit(job, profile, today)

    skills = skills_match(
        job.required_skills, job.optional_skills, {s.name for s in profile.skills}
    )
    degree_levels = [
        level
        for e in profile.education
        if e.degree and (level := education_level(e.degree)) is not None
    ]
    candidate_level = max(degree_levels) if degree_levels else None

    raw: dict[ComponentName, float | None] = {
        "skills": skills.score,
        "experience": experience_score(job.min_experience_years, fit.months),
        "education": education_score(job.education_level, candidate_level),
        "tfidf": tfidf_value if has_text else None,
        "keyword": keyword_score(job_text, candidate.text) if has_text else None,
        "semantic": candidate.semantic,
    }

    weight_of = weights.model_dump()
    usable = {n: weight_of[n] for n in _ORDER if raw[n] is not None and weight_of[n] > 0}
    denominator = sum(usable.values())
    effective = {
        n: (usable[n] / denominator if n in usable and denominator else 0.0) for n in _ORDER
    }
    contributions = {n: 100 * effective[n] * (raw[n] or 0.0) for n in _ORDER}
    score = round(sum(contributions.values()), 2)

    notes = _notes(job, raw, weight_of, fit)
    components = [
        ComponentResult(
            name=n,
            label=_LABELS[n],
            raw_score=None if raw[n] is None else round(raw[n] or 0.0, 4),
            effective_weight=round(effective[n], 4),
            contribution=round(contributions[n], 2),
            note=notes[n],
        )
        for n in _ORDER
    ]

    warnings: list[str] = []
    if not usable:
        warnings.append(
            "Aucune composante évaluable : le score est 0 par défaut, sans signification."
        )
    if not has_text:
        warnings.append("Aucun contenu exploitable dans les sections pertinentes du CV.")
    if profile.report.extraction_completeness < 0.7:
        warnings.append(
            f"Lecture du CV incomplète ({round(profile.report.extraction_completeness * 100)} % "
            "des éléments attendus) : le score peut sous-estimer ce profil."
        )

    return MatchResult(
        rank=0,  # attribué après le tri
        candidate=CandidateRef(id=candidate.candidate_id),
        score=score,
        components=components,
        skills=SkillsDetail(
            matched_required=skills.matched_required,
            missing_required=skills.missing_required,
            matched_optional=skills.matched_optional,
            missing_optional=skills.missing_optional,
            evidence=_evidence(profile, skills.matched_required + skills.matched_optional),
        ),
        relevant_experience=_relevant_experience(job, profile),
        explanations=_explanations(job, skills, raw, candidate_level, fit),
        warnings=warnings,
        confidence=_confidence(job, profile, raw, weight_of),
    )


def _evidence(profile: CandidateProfile, names: list[str]) -> dict[str, str]:
    """Extrait du CV justifiant chaque compétence trouvée (jamais celui de l'en-tête, qui peut
    contenir le nom)."""
    by_name = {s.name: s for s in profile.skills}
    return {
        n: by_name[n].provenance.snippet
        for n in names
        if n in by_name and by_name[n].provenance.section != "header"
    }


def _relevant_experience(job: JobProfile, profile: CandidateProfile) -> list[RelevantExperience]:
    wanted = set(job.required_skills) | set(job.optional_skills)
    required = set(job.required_skills)
    rows = []
    for item in profile.experience:
        common = [s for s in item.skills if s in wanted]
        if common:
            rows.append((item, common, sum(1 for s in common if s in required)))
    rows.sort(key=lambda r: (-r[2], -len(r[1]), -(r[0].duration_months or 0)))
    return [
        RelevantExperience(
            title=item.title,
            company=item.company,
            duration_months=item.duration_months,
            matching_skills=common,
        )
        for item, common, _ in rows[:5]
    ]


def _notes(
    job: JobProfile,
    raw: dict[ComponentName, float | None],
    weight_of: dict[str, float],
    fit: ExperienceFit,
) -> dict[ComponentName, str]:
    notes: dict[ComponentName, str] = dict.fromkeys(_ORDER, "")
    if raw["skills"] is None:
        notes["skills"] = "Non évalué : l'offre ne contient aucune compétence du référentiel."
    if raw["experience"] is None:
        if not job.min_experience_years:
            notes["experience"] = "Non évalué : l'offre n'exige pas d'expérience chiffrée."
        else:
            notes["experience"] = (
                "Non évalué : aucune période datée lue dans le CV (sans doute une limite de la "
                "lecture, pas une absence d'expérience)."
            )
    elif fit.basis == "relevant":
        notes["experience"] = (
            "Seules comptent les années passées sur des postes qui mobilisent des compétences de "
            "l'offre (détectées dans le CV)."
        )
    else:
        notes["experience"] = (
            "L'offre ne contient aucune compétence du référentiel : expérience totale utilisée."
        )
    if raw["education"] is None:
        if not job.education_level:
            notes["education"] = "Non évalué : l'offre n'exige pas de niveau d'études."
        else:
            notes["education"] = "Non évalué : aucun diplôme reconnu dans le CV."
    if raw["tfidf"] is None or raw["keyword"] is None:
        notes["tfidf"] = notes["keyword"] = "Non évalué : CV sans contenu exploitable."
    if raw["semantic"] is None:
        notes["semantic"] = "Non évalué : embeddings désactivés ou candidat non indexé."
    for name in _ORDER:
        if weight_of[name] == 0:
            notes[name] = "Poids à 0 : affiché à titre indicatif, sans effet sur le score."
    return notes


def _explanations(
    job: JobProfile,
    skills: SkillsMatch,
    raw: dict[ComponentName, float | None],
    candidate_level: int | None,
    fit: ExperienceFit,
) -> list[str]:
    lines: list[str] = []
    if job.required_skills:
        found = len(skills.matched_required)
        text = f"Compétences requises : {found} sur {len(job.required_skills)} trouvées"
        text += f" ({', '.join(skills.matched_required)})" if skills.matched_required else ""
        text += (
            f" ; manquantes : {', '.join(skills.missing_required)}."
            if skills.missing_required
            else "."
        )
        lines.append(text)
    if job.optional_skills:
        lines.append(
            f"Compétences optionnelles : {len(skills.matched_optional)} sur "
            f"{len(job.optional_skills)} trouvées"
            + (f" ({', '.join(skills.matched_optional)})." if skills.matched_optional else ".")
        )
    if raw["experience"] is not None and fit.months is not None and fit.total_months is not None:
        if fit.basis == "relevant":
            lines.append(
                f"Expérience pertinente : {format_duration(fit.months)} sur des postes qui "
                f"mobilisent des compétences de l'offre (expérience totale lue : "
                f"{format_duration(fit.total_months)}) pour {job.min_experience_years} an(s) "
                "demandé(s)."
            )
        else:
            lines.append(
                f"Expérience totale : {format_duration(fit.total_months)} pour "
                f"{job.min_experience_years} an(s) demandé(s)."
            )
    if raw["education"] is not None and candidate_level is not None and job.education_level:
        lines.append(
            f"Niveau d'études : {label(candidate_level)} détecté pour "
            f"{label(job.education_level)} demandé."
        )
    if raw["tfidf"] is not None:
        lines.append(
            f"Similarité de texte (TF-IDF) : {raw['tfidf']:.2f} sur 1 — mesure lexicale, "
            "elle ne reconnaît pas les synonymes."
        )
    if raw["keyword"] is not None:
        lines.append(
            f"Mots-clés de l'offre retrouvés dans le CV : {round((raw['keyword'] or 0) * 100)} %."
        )
    if raw["semantic"] is not None:
        lines.append(
            f"Similarité sémantique : {raw['semantic']:.2f} sur 1 — compare le sens (français et "
            "anglais confondus), pas les mots ; elle peut rapprocher des profils seulement voisins."
        )
    return lines


def _confidence(
    job: JobProfile,
    profile: CandidateProfile,
    raw: dict[ComponentName, float | None],
    weight_of: dict[str, float],
) -> Confidence:
    weighted = [n for n in _ORDER if weight_of[n] > 0]
    evaluated = [n for n in weighted if raw[n] is not None]
    evaluated_ratio = len(evaluated) / len(weighted) if weighted else 0.0
    job_richness = (
        bool(job.required_skills)
        + (job.min_experience_years is not None)
        + (job.education_level is not None)
    ) / 3
    completeness = profile.report.extraction_completeness
    # La qualité de lecture du CV pèse le plus : si le CV est mal lu, tout le reste est fragile.
    value = round(0.5 * completeness + 0.25 * evaluated_ratio + 0.25 * job_richness, 2)

    reasons = []
    if completeness < 0.7:
        reasons.append("Lecture du CV incomplète.")
    if evaluated_ratio < 1:
        missing = [_LABELS[n] for n in weighted if raw[n] is None]
        reasons.append(f"Composantes non évaluées : {', '.join(missing)}.")
    if job_richness < 2 / 3:
        reasons.append(
            "Offre peu structurée (compétences, expérience ou niveau d'études manquants)."
        )
    level = "high" if value >= 0.75 else "medium" if value >= 0.5 else "low"
    return Confidence(level=level, value=value, reasons=reasons)
