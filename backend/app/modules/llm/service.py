"""Tâches LLM : extraction structurée, résumé, analyse d'offre, explication d'un classement.

Principes, appliqués à CHAQUE tâche :
- Désactivé par défaut ; le consentement explicite est vérifié par la route.
- Seul du texte ANONYMISÉ (sections liées au poste, sans nom ni contacts) et EXPURGÉ (e-mails,
  téléphones, liens) est envoyé, plafonné en taille.
- Le document est délimité et déclaré non fiable (injection de prompt).
- Toute affirmation du modèle doit citer un extrait RÉEL du document envoyé, sinon elle est écartée
  et comptée. Un texte libre qui cite une compétence absente du document est retenu, pas affiché.
- Aucune suggestion n'est appliquée automatiquement : le recruteur décide.
"""

import json

import structlog

from app.modules.candidates.models import Candidate
from app.modules.candidates.parsing.skills import canonical_skill_name, find_skills_in_text
from app.modules.candidates.repository import CandidateRepository
from app.modules.candidates.service import CandidateNotFoundError
from app.modules.jobs.profile import JobProfile
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import JobNotFoundError
from app.modules.llm import prompts
from app.modules.llm.errors import LLMDisabledError
from app.modules.llm.generate import generate
from app.modules.llm.providers import LLMProvider
from app.modules.llm.safety import contains_word, is_grounded, normalize, redact, wrap_document
from app.modules.llm.schemas import (
    CallInfo,
    CVExtractionResult,
    DroppedCounts,
    ExplanationResult,
    GroundedEducation,
    GroundedExperience,
    GroundedSkill,
    JobAnalysisResult,
    JobSuggestion,
    KeyPoint,
    RawCVExtraction,
    RawExplanation,
    RawJobAnalysis,
    RawSkill,
    RawSummary,
    SkillComparison,
    SummaryResult,
)
from app.modules.matching.service import MatchingService
from app.modules.matching.text import anonymized_cv_text

log = structlog.get_logger()


class CandidateNotRankedError(Exception):
    """Le candidat n'est pas dans le lot classé (il n'existe pas, ou le lot est tronqué)."""


class LLMService:
    def __init__(
        self,
        provider: LLMProvider | None,
        max_input_chars: int,
        candidates: CandidateRepository,
        jobs: JobRepository,
        matching: MatchingService,
        disabled_reason: str | None = None,
    ) -> None:
        self._provider = provider
        self._disabled_reason = disabled_reason
        self._max_chars = max_input_chars
        self._candidates = candidates
        self._jobs = jobs
        self._matching = matching

    # ------------------------------------------------------------------ outils communs

    def _require(self) -> LLMProvider:
        if self._provider is None:
            raise LLMDisabledError(
                self._disabled_reason
                or "La fonction LLM est désactivée (LLM_PROVIDER=none dans .env)."
            )
        return self._provider

    def _prepare(self, text: str) -> tuple[str, bool]:
        """Expurge puis plafonne le texte (coupé à une fin de ligne)."""
        text = redact(text)
        if len(text) <= self._max_chars:
            return text, False
        return text[: self._max_chars].rsplit("\n", 1)[0], True

    def _info(self, provider: LLMProvider, sent: str, truncated: bool) -> CallInfo:
        return CallInfo(
            provider=provider.name, model=provider.model, input_chars=len(sent), truncated=truncated
        )

    def _candidate(self, owner_id: int, candidate_id: int) -> Candidate:
        candidate = self._candidates.get(owner_id, candidate_id)
        if candidate is None:
            raise CandidateNotFoundError
        return candidate

    @staticmethod
    def _log(
        task: str, provider: LLMProvider, owner_id: int, sent: str, dropped: DroppedCounts
    ) -> None:
        # Des identifiants et des compteurs : jamais le texte envoyé ni la réponse.
        log.info(
            "llm_task",
            task=task,
            provider=provider.name,
            model=provider.model,
            owner_id=owner_id,
            input_chars=len(sent),
            dropped=dropped.model_dump(),
        )

    # ------------------------------------------------------------------ extraction du CV

    def extract_cv(self, owner_id: int, candidate_id: int) -> CVExtractionResult:
        provider = self._require()
        candidate = self._candidate(owner_id, candidate_id)
        text, truncated = self._prepare(anonymized_cv_text(candidate.document.extracted_text))
        raw = generate(
            provider,
            prompts.SYSTEM,
            f"{prompts.CV_EXTRACTION}\n\n{wrap_document(text)}",
            RawCVExtraction,
        )

        dropped = DroppedCounts()
        skills: list[GroundedSkill] = []
        seen: set[str] = set()
        for item in raw.skills:
            canonical = canonical_skill_name(item.name)
            supported = is_grounded(item.quote, text) and (
                contains_word(item.quote, item.name)
                or (
                    canonical is not None
                    and canonical in find_skills_in_text(item.quote, mode="full")
                )
            )
            if not supported:
                dropped.skills += 1
                continue
            key = normalize(canonical or item.name)
            if key in seen:  # doublon d'une compétence déjà retenue : ignoré, pas « inventé »
                continue
            seen.add(key)
            skills.append(GroundedSkill(name=item.name, canonical=canonical, quote=item.quote))

        experience: list[GroundedExperience] = []
        for item in raw.experience:
            title, company = _inside(item.title, item.quote), _inside(item.company, item.quote)
            if not is_grounded(item.quote, text) or not (title or company):
                dropped.experience += 1
                continue
            experience.append(
                GroundedExperience(
                    title=title, company=company, period=item.period, quote=item.quote
                )
            )

        education: list[GroundedEducation] = []
        for item in raw.education:
            degree, institution = (
                _inside(item.degree, item.quote),
                _inside(item.institution, item.quote),
            )
            if not is_grounded(item.quote, text) or not (degree or institution):
                dropped.education += 1
                continue
            education.append(
                GroundedEducation(degree=degree, institution=institution, quote=item.quote)
            )

        rules = {s["name"] for s in candidate.profile.get("skills", [])}
        llm = {s.canonical for s in skills if s.canonical}
        self._log("cv_extraction", provider, owner_id, text, dropped)
        return CVExtractionResult(
            call=self._info(provider, text, truncated),
            skills=skills,
            experience=experience,
            education=education,
            dropped=dropped,
            comparison=SkillComparison(
                both=sorted(rules & llm),
                only_llm=sorted(llm - rules),
                only_rules=sorted(rules - llm),
            ),
        )

    # ------------------------------------------------------------------ résumé

    def summarize_cv(self, owner_id: int, candidate_id: int) -> SummaryResult:
        provider = self._require()
        candidate = self._candidate(owner_id, candidate_id)
        text, truncated = self._prepare(anonymized_cv_text(candidate.document.extracted_text))
        raw = generate(
            provider, prompts.SYSTEM, f"{prompts.CV_SUMMARY}\n\n{wrap_document(text)}", RawSummary
        )

        dropped = DroppedCounts()
        points = []
        for point in raw.key_points:
            if is_grounded(point.quote, text):
                points.append(KeyPoint(text=point.text, quote=point.quote))
            else:
                dropped.key_points += 1

        # Le résumé est du texte libre, non vérifiable phrase par phrase : on contrôle qu'il
        # ne cite aucune compétence du référentiel qui ne soit pas dans le document.
        known = set(find_skills_in_text(text, mode="full"))
        invented = sorted(set(find_skills_in_text(raw.summary, mode="relaxed")) - known)
        summary: str | None = raw.summary.strip() or None
        withheld = None
        if invented:
            summary, withheld = (
                None,
                (
                    "Résumé retenu : il cite des compétences absentes du CV ("
                    + ", ".join(invented)
                    + ")."
                ),
            )
        self._log("cv_summary", provider, owner_id, text, dropped)
        return SummaryResult(
            call=self._info(provider, text, truncated),
            summary=summary,
            withheld_reason=withheld,
            key_points=points,
            dropped=dropped,
        )

    # ------------------------------------------------------------------ offre

    def analyze_job(self, owner_id: int, job_id: int) -> JobAnalysisResult:
        provider = self._require()
        job = self._jobs.get(owner_id, job_id)
        if job is None:
            raise JobNotFoundError
        text, truncated = self._prepare(f"{job.title}\n{job.description}")
        raw = generate(
            provider,
            prompts.SYSTEM,
            f"{prompts.JOB_ANALYSIS}\n\n{wrap_document(text)}",
            RawJobAnalysis,
        )

        dropped = DroppedCounts()
        required, unknown = _job_skills(raw.required_skills, text, dropped)
        optional_names, unknown_optional = _job_skills(raw.optional_skills, text, dropped)
        optional = [s for s in optional_names if s not in required]  # « exigé » l'emporte
        unknown += unknown_optional

        years = raw.min_experience_years
        if years is not None and not (
            is_grounded(raw.experience_quote, text) and str(years) in raw.experience_quote
        ):
            years = None  # un nombre d'années sans citation vérifiable n'est pas retenu

        responsibilities = []
        for point in raw.responsibilities:
            if is_grounded(point.quote, text):
                responsibilities.append(KeyPoint(text=point.text, quote=point.quote))
            else:
                dropped.responsibilities += 1

        current = JobProfile.model_validate(job.profile)
        rules = set(current.required_skills) | set(current.optional_skills)
        llm = set(required) | set(optional)
        self._log("job_analysis", provider, owner_id, text, dropped)
        return JobAnalysisResult(
            call=self._info(provider, text, truncated),
            suggestion=JobSuggestion(
                required_skills=required,
                optional_skills=optional,
                unknown_skills=unknown,
                min_experience_years=years,
                responsibilities=responsibilities,
            ),
            differences=SkillComparison(
                both=sorted(rules & llm),
                only_llm=sorted(llm - rules),
                only_rules=sorted(rules - llm),
            ),
            dropped=dropped,
        )

    # ------------------------------------------------------------------ explication d'un classement

    def explain_match(self, owner_id: int, job_id: int, candidate_id: int) -> ExplanationResult:
        provider = self._require()
        result = self._matching.match_one(owner_id, job_id, candidate_id)
        if result is None:
            raise CandidateNotRankedError
        facts = {
            "score_sur_100_relatif_au_lot": result.score,
            "composantes": [
                {"nom": c.label, "score_0_a_1": c.raw_score, "poids_effectif": c.effective_weight}
                for c in result.components
            ],
            "competences_requises_trouvees": result.skills.matched_required,
            "competences_requises_manquantes": result.skills.missing_required,
            "competences_optionnelles_trouvees": result.skills.matched_optional,
            "competences_optionnelles_manquantes": result.skills.missing_optional,
            "experiences_pertinentes": [
                {
                    "intitule": e.title,
                    "duree_mois": e.duration_months,
                    "competences": e.matching_skills,
                }
                for e in result.relevant_experience
            ],
            "avertissements": result.warnings,
            "fiabilite_de_l_analyse": result.confidence.level,
        }
        text = json.dumps(facts, ensure_ascii=False)
        raw = generate(
            provider,
            prompts.SYSTEM,
            f"{prompts.EXPLANATION}\n\n{wrap_document(text)}",
            RawExplanation,
        )

        allowed = set(result.skills.matched_required) | set(result.skills.missing_required)
        allowed |= set(result.skills.matched_optional) | set(result.skills.missing_optional)
        for experience in result.relevant_experience:
            allowed |= set(experience.matching_skills)
        invented = sorted(set(find_skills_in_text(raw.explanation, mode="relaxed")) - allowed)
        explanation: str | None = raw.explanation.strip() or None
        withheld = None
        if invented:
            explanation, withheld = (
                None,
                (
                    "Explication retenue : elle cite des compétences absentes des faits calculés ("
                    + ", ".join(invented)
                    + "). Utilisez les explications déterministes du classement."
                ),
            )
        self._log("match_explanation", provider, owner_id, text, DroppedCounts())
        return ExplanationResult(
            call=self._info(provider, text, False),
            explanation=explanation,
            withheld_reason=withheld,
            caveats=[c for c in raw.caveats if c.strip()],
        )


def _inside(value: str | None, quote: str) -> str | None:
    """Garde le champ seulement s'il figure dans la citation (sinon il a pu être inventé)."""
    return value if value and normalize(value) in normalize(quote) else None


def _job_skills(
    items: list[RawSkill], text: str, dropped: DroppedCounts
) -> tuple[list[str], list[GroundedSkill]]:
    names: list[str] = []
    unknown: list[GroundedSkill] = []
    for item in items:
        canonical = canonical_skill_name(item.name)
        supported = is_grounded(item.quote, text) and (
            contains_word(item.quote, item.name)
            or (canonical is not None and canonical in find_skills_in_text(item.quote, mode="full"))
        )
        if not supported:
            dropped.skills += 1
        elif canonical is None:
            unknown.append(GroundedSkill(name=item.name, canonical=None, quote=item.quote))
        elif canonical not in names:
            names.append(canonical)
    return names, unknown
