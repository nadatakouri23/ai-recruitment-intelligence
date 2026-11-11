"""Orchestration du matching : charge l'offre et les candidats du recruteur, appelle le moteur."""

import time

import structlog

from app.core.config import Settings
from app.modules.candidates.profile import CandidateProfile
from app.modules.candidates.repository import CandidateRepository
from app.modules.embeddings.embedder import Embedder, embed_texts
from app.modules.embeddings.repository import ChunkRepository
from app.modules.embeddings.similarity import semantic_score
from app.modules.jobs.profile import JobProfile
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.service import JobNotFoundError
from app.modules.matching.engine import LIMITATIONS, CandidateInput, rank
from app.modules.matching.schemas import (
    CandidateRef,
    MatchRequest,
    MatchResponse,
    MatchResult,
)
from app.modules.matching.text import anonymized_cv_text
from app.modules.matching.weights import MatchingWeights

log = structlog.get_logger()

# Au-delà, on classe seulement les plus récents et on le signale (le calcul reste rapide).
MAX_POOL = 500


def job_query_text(title: str, job: JobProfile) -> str:
    """Texte court et dense de l'offre pour l'embedding (le modèle lit ~80 mots) : titre, exigences
    et premières missions, sans les avantages ni la présentation de l'entreprise."""
    parts = [title, ", ".join(job.required_skills), " ".join(job.responsibilities[:3])]
    return ". ".join(p for p in parts if p)


class MatchingService:
    def __init__(
        self,
        jobs: JobRepository,
        candidates: CandidateRepository,
        settings: Settings,
        chunks: ChunkRepository | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._jobs = jobs
        self._candidates = candidates
        self._settings = settings
        self._chunks = chunks
        self._embedder = embedder

    def _semantic_scores(
        self, owner_id: int, title: str, job: JobProfile, candidate_ids: list[int]
    ) -> dict[int, float]:
        """Similarité sémantique offre/CV des candidats indexés ({} si embeddings désactivés)."""
        if self._embedder is None or self._chunks is None:
            return {}
        (job_vector,) = embed_texts(self._embedder, [job_query_text(title, job)])
        vectors = self._chunks.vectors_by_candidate(owner_id, self._embedder.name)
        scores = {}
        for candidate_id in candidate_ids:
            score = semantic_score(job_vector, vectors.get(candidate_id, []))
            if score is not None:
                scores[candidate_id] = score
        return scores

    def match_one(self, owner_id: int, job_id: int, candidate_id: int) -> MatchResult | None:
        """Résultat d'UN candidat, calculé dans le classement complet (le score est relatif au lot :
        on ne peut pas l'obtenir en ne classant qu'un candidat). None s'il n'est pas dans le lot."""
        _, _, ranked, _, _ = self._rank_pool(owner_id, job_id, None)
        return next((r for r in ranked if r.candidate.id == candidate_id), None)

    def match(self, owner_id: int, job_id: int, request: MatchRequest) -> MatchResponse:
        started = time.perf_counter()
        job, pool, ranked, total, weights = self._rank_pool(owner_id, job_id, request.weights)

        display = {c.id: CandidateRef(id=c.id, full_name=c.full_name, email=c.email) for c in pool}
        results = []
        for result in ranked:
            if result.score < request.min_score:
                continue
            if len(results) >= request.limit:
                break
            # Le nom n'a servi à rien dans le calcul : il n'est ajouté qu'ici, pour l'affichage.
            candidate_ref = (
                CandidateRef(id=result.candidate.id)
                if request.anonymize
                else display[result.candidate.id]
            )
            results.append(result.model_copy(update={"candidate": candidate_ref}))

        log.info(
            "matching_done",
            job_id=job_id,
            owner_id=owner_id,
            pool_size=len(pool),
            returned=len(results),
            anonymized=request.anonymize,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        return MatchResponse(
            job_id=job.id,
            job_title=job.title,
            weights_used=weights,
            pool_size=len(pool),
            pool_truncated=total > len(pool),
            returned=len(results),
            results=results,
            limitations=LIMITATIONS,
        )

    def _rank_pool(self, owner_id: int, job_id: int, requested: MatchingWeights | None):
        """Classe TOUS les candidats ; retourne (offre, lot, classement, total, poids)."""
        job = self._jobs.get(owner_id, job_id)
        if job is None:
            raise JobNotFoundError

        pool, total = self._candidates.list(owner_id, limit=MAX_POOL, offset=0)
        job_profile = JobProfile.model_validate(job.profile)
        semantic = self._semantic_scores(owner_id, job.title, job_profile, [c.id for c in pool])
        inputs = [
            CandidateInput(
                candidate_id=c.id,
                profile=CandidateProfile.model_validate(c.profile),
                # Texte restreint aux sections liées au poste : sans nom, contacts, langues.
                text=anonymized_cv_text(c.document.extracted_text),
                semantic=semantic.get(c.id),
            )
            for c in pool
        ]
        weights = (requested or self._settings.matching_weights).normalized()
        ranked = rank(job_profile, f"{job.title}\n{job.description}", inputs, weights)
        return job, pool, ranked, total, weights
