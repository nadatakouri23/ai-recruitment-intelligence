"""Accès aux passages vectorisés. Toutes les requêtes filtrent par propriétaire."""

from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.candidates.models import Candidate
from app.modules.embeddings.chunking import Chunk
from app.modules.embeddings.models import CandidateChunk


class ChunkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def replace_for_candidate(
        self,
        candidate_id: int,
        owner_id: int,
        rows: Sequence[tuple[Chunk, list[float] | None]],
        model: str | None,
    ) -> None:
        """Remplace tous les passages d'un candidat dans une seule transaction."""
        try:
            self._session.execute(
                delete(CandidateChunk).where(
                    CandidateChunk.candidate_id == candidate_id, CandidateChunk.owner_id == owner_id
                )
            )
            self._session.add_all(
                CandidateChunk(
                    candidate_id=candidate_id,
                    owner_id=owner_id,
                    position=chunk.position,
                    section=chunk.section,
                    text=chunk.text,
                    embedding=vector,
                    embedding_model=model if vector is not None else None,
                )
                for chunk, vector in rows
            )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def _candidate_filter(self, owner_id: int, skill: str | None):
        """Candidats du propriétaire, éventuellement restreints à une compétence (JSONB @>)."""
        conditions = [Candidate.owner_id == owner_id]
        if skill:
            conditions.append(Candidate.profile.contains({"skills": [{"name": skill}]}))
        return select(Candidate.id).where(*conditions)

    def semantic_search(
        self, owner_id: int, vector: list[float], model: str, *, limit: int, skill: str | None
    ) -> list[tuple[CandidateChunk, float]]:
        """Passages les plus proches (distance cosinus croissante), parmi ceux du propriétaire."""
        distance = CandidateChunk.embedding.cosine_distance(vector)
        statement = (
            select(CandidateChunk, distance)
            .where(
                CandidateChunk.owner_id == owner_id,
                CandidateChunk.embedding_model == model,
                CandidateChunk.candidate_id.in_(self._candidate_filter(owner_id, skill)),
            )
            .order_by(distance)
            .limit(limit)
        )
        return [(chunk, float(dist)) for chunk, dist in self._session.execute(statement)]

    def texts(self, owner_id: int, *, skill: str | None) -> list[CandidateChunk]:
        """Tous les passages (texte) du propriétaire, pour la recherche par mots-clés."""
        statement = (
            select(CandidateChunk)
            .where(
                CandidateChunk.owner_id == owner_id,
                CandidateChunk.candidate_id.in_(self._candidate_filter(owner_id, skill)),
            )
            .order_by(CandidateChunk.candidate_id, CandidateChunk.position)
        )
        return list(self._session.scalars(statement))

    def vectors_by_candidate(self, owner_id: int, model: str) -> dict[int, list[list[float]]]:
        statement = select(CandidateChunk.candidate_id, CandidateChunk.embedding).where(
            CandidateChunk.owner_id == owner_id,
            CandidateChunk.embedding_model == model,
            CandidateChunk.embedding.is_not(None),
        )
        grouped: dict[int, list[list[float]]] = defaultdict(list)
        for candidate_id, vector in self._session.execute(statement):
            grouped[candidate_id].append([float(x) for x in vector])
        return dict(grouped)

    def candidate_ids_needing_index(self, owner_id: int, model: str | None) -> list[int]:
        """Candidats sans passage, ou dont un passage n'est pas vectorisé avec le modèle courant."""
        stale = func.count().filter(
            (CandidateChunk.embedding.is_(None)) | (CandidateChunk.embedding_model != model)
            if model
            else CandidateChunk.id.is_(None)
        )
        counts = (
            select(CandidateChunk.candidate_id, func.count().label("n"), stale.label("stale"))
            .where(CandidateChunk.owner_id == owner_id)
            .group_by(CandidateChunk.candidate_id)
            .subquery()
        )
        statement = (
            select(Candidate.id)
            .outerjoin(counts, counts.c.candidate_id == Candidate.id)
            .where(Candidate.owner_id == owner_id)
            .where((counts.c.n.is_(None)) | (counts.c.stale > 0))
            .order_by(Candidate.id)
        )
        return list(self._session.scalars(statement))

    def display_names(
        self, owner_id: int, ids: Sequence[int]
    ) -> dict[int, tuple[str | None, str | None]]:
        statement = select(Candidate.id, Candidate.full_name, Candidate.email).where(
            Candidate.owner_id == owner_id, Candidate.id.in_(list(ids))
        )
        return {cid: (name, email) for cid, name, email in self._session.execute(statement)}

    def stats(self, owner_id: int, model: str | None) -> dict[str, int]:
        total_candidates = self._session.scalar(
            select(func.count()).select_from(Candidate).where(Candidate.owner_id == owner_id)
        )
        chunks = self._session.scalar(
            select(func.count())
            .select_from(CandidateChunk)
            .where(CandidateChunk.owner_id == owner_id)
        )
        vectors = (
            self._session.scalar(
                select(func.count())
                .select_from(CandidateChunk)
                .where(
                    CandidateChunk.owner_id == owner_id,
                    CandidateChunk.embedding_model == model,
                    CandidateChunk.embedding.is_not(None),
                )
            )
            if model
            else 0
        )
        return {
            "candidates": total_candidates or 0,
            "chunks": chunks or 0,
            "vectors": vectors or 0,
        }
