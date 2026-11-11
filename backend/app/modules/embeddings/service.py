"""Indexation des CV (passages + vecteurs) et recherche de candidats."""

import structlog

from app.modules.candidates.models import Candidate
from app.modules.candidates.parsing.skills import canonical_skill_name
from app.modules.candidates.repository import CandidateRepository
from app.modules.embeddings.chunking import chunk_cv
from app.modules.embeddings.embedder import Embedder, embed_texts
from app.modules.embeddings.models import CandidateChunk
from app.modules.embeddings.ranking import ranks, reciprocal_rank_fusion
from app.modules.embeddings.repository import ChunkRepository
from app.modules.embeddings.schemas import (
    IndexStatus,
    Passage,
    ReindexReport,
    SearchHit,
    SearchRequest,
    SearchResponse,
)
from app.modules.matching.schemas import CandidateRef
from app.modules.matching.tfidf import tfidf_similarities

log = structlog.get_logger()

SEMANTIC_CANDIDATE_PASSAGES = 300


class SemanticDisabledError(Exception):
    """La recherche sémantique est désactivée (EMBEDDING_PROVIDER=none) ou indisponible."""


class IndexingService:
    def __init__(
        self, chunks: ChunkRepository, candidates: CandidateRepository, embedder: Embedder | None
    ) -> None:
        self._chunks = chunks
        self._candidates = candidates
        self._embedder = embedder

    def index_candidate(self, candidate: Candidate) -> tuple[int, int]:
        """Découpe le CV et enregistre ses passages ; les vectorise si un modèle est configuré.

        Retourne (passages, passages vectorisés). Un échec de vectorisation ne perd pas les
        passages : la recherche par mots-clés reste disponible et `reindex` pourra réessayer.
        """
        chunks = chunk_cv(candidate.document.extracted_text)
        vectors: list[list[float]] | None = None
        if self._embedder is not None and chunks:
            try:
                vectors = embed_texts(self._embedder, [c.text for c in chunks])
            except Exception as exc:  # noqa: BLE001 - modèle absent, mémoire, etc.
                log.error("embedding_failed", candidate_id=candidate.id, error=type(exc).__name__)
        rows = [(c, vectors[i] if vectors else None) for i, c in enumerate(chunks)]
        self._chunks.replace_for_candidate(
            candidate.id,
            candidate.owner_id,
            rows,
            self._embedder.name if self._embedder and vectors else None,
        )
        return len(chunks), len(chunks) if vectors else 0

    def reindex(self, owner_id: int) -> ReindexReport:
        """Indexe les candidats sans passage ou sans vecteur à jour (idempotent)."""
        model = self._embedder.name if self._embedder else None
        processed = total = embedded = 0
        for candidate_id in self._chunks.candidate_ids_needing_index(owner_id, model):
            candidate = self._candidates.get(owner_id, candidate_id)
            if candidate is None:
                continue
            count, with_vectors = self.index_candidate(candidate)
            processed += 1
            total += count
            embedded += with_vectors
        log.info("reindex_done", owner_id=owner_id, candidates=processed, chunks=total)
        return ReindexReport(candidates_processed=processed, chunks=total, with_vectors=embedded)

    def status(self, owner_id: int, provider: str) -> IndexStatus:
        model = self._embedder.name if self._embedder else None
        stats = self._chunks.stats(owner_id, model)
        return IndexStatus(
            provider=provider,
            model=model,
            semantic_enabled=self._embedder is not None,
            candidates=stats["candidates"],
            chunks=stats["chunks"],
            vectors=stats["vectors"],
            candidates_needing_index=len(self._chunks.candidate_ids_needing_index(owner_id, model)),
        )


class SearchService:
    def __init__(self, chunks: ChunkRepository, embedder: Embedder | None) -> None:
        self._chunks = chunks
        self._embedder = embedder

    def search(self, owner_id: int, request: SearchRequest) -> SearchResponse:
        mode = request.mode
        if mode == "auto":
            mode = "hybrid" if self._embedder is not None else "keyword"
        if mode in ("semantic", "hybrid") and self._embedder is None:
            raise SemanticDisabledError
        skill = None
        if request.skill:
            skill = canonical_skill_name(request.skill) or request.skill.strip()

        keyword = self._keyword(owner_id, request.query, skill) if mode != "semantic" else {}
        semantic = self._semantic(owner_id, request.query, skill) if mode != "keyword" else {}
        keyword_rank = ranks({cid: s for cid, (s, _) in keyword.items()})
        semantic_rank = ranks({cid: s for cid, (s, _) in semantic.items()})

        if mode == "keyword":
            scores = {cid: s for cid, (s, _) in keyword.items()}
        elif mode == "semantic":
            scores = {cid: s for cid, (s, _) in semantic.items()}
        else:  # hybride : fusion des RANGS, car TF-IDF et cosinus n'ont pas la même échelle
            scores = reciprocal_rank_fusion(keyword_rank, semantic_rank)
        ordered = sorted(scores, key=lambda cid: (-scores[cid], cid))[: request.limit]
        names = self._chunks.display_names(owner_id, ordered)

        results = []
        for cid in ordered:
            chunk = (semantic.get(cid) or keyword.get(cid))[1]  # type: ignore[index]
            name, email = names.get(cid, (None, None))
            results.append(
                SearchHit(
                    candidate=CandidateRef(
                        id=cid,
                        full_name=None if request.anonymize else name,
                        email=None if request.anonymize else email,
                    ),
                    score=round(scores[cid], 4),
                    best_passage=Passage(section=chunk.section, text=chunk.text),
                    keyword_rank=keyword_rank.get(cid),
                    semantic_rank=semantic_rank.get(cid),
                )
            )

        unindexed = 0
        if mode != "keyword" and self._embedder is not None:
            unindexed = len(self._chunks.candidate_ids_needing_index(owner_id, self._embedder.name))
        log.info(
            "search_done",
            owner_id=owner_id,
            mode=mode,
            returned=len(results),
            query_chars=len(request.query),
        )
        return SearchResponse(
            mode_used=mode,  # type: ignore[arg-type]
            results=results,
            unindexed_candidates=unindexed,
            note=_NOTES[mode],
        )

    def _keyword(
        self, owner_id: int, query: str, skill: str | None
    ) -> dict[int, tuple[float, CandidateChunk]]:
        chunks = self._chunks.texts(owner_id, skill=skill)
        similarities = tfidf_similarities(query, [c.text for c in chunks])
        best: dict[int, tuple[float, CandidateChunk]] = {}
        for chunk, score in zip(chunks, similarities, strict=True):
            if score > 0 and score > best.get(chunk.candidate_id, (0.0, chunk))[0]:
                best[chunk.candidate_id] = (score, chunk)
        return best

    def _semantic(
        self, owner_id: int, query: str, skill: str | None
    ) -> dict[int, tuple[float, CandidateChunk]]:
        assert self._embedder is not None
        (vector,) = embed_texts(self._embedder, [query])
        rows = self._chunks.semantic_search(
            owner_id, vector, self._embedder.name, limit=SEMANTIC_CANDIDATE_PASSAGES, skill=skill
        )
        best: dict[int, tuple[float, CandidateChunk]] = {}
        for chunk, distance in rows:  # triés du plus proche au plus lointain
            similarity = max(0.0, 1.0 - distance)
            if similarity > 0 and chunk.candidate_id not in best:
                best[chunk.candidate_id] = (similarity, chunk)
        return best


_NOTES = {
    "keyword": "Recherche lexicale (TF-IDF) : trouve les mots de la requête, pas leurs synonymes.",
    "semantic": "Recherche par le sens (embeddings) : peut remonter des profils sans les mots "
    "de la requête, mais aussi des profils seulement proches. Vérifiez le passage affiché.",
    "hybrid": "Fusion des rangs lexical et sémantique (RRF). Le passage affiché est le meilleur "
    "passage sémantique, à défaut le meilleur passage lexical.",
}
