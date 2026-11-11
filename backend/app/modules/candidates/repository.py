"""Accès aux données des candidats.

Toutes les requêtes filtrent par `owner_id` : un recruteur ne voit jamais les candidats d'un autre.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.candidates.models import Candidate
from app.modules.documents.models import Document


class CandidateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_hash(self, owner_id: int, sha256: str) -> Candidate | None:
        statement = (
            select(Candidate)
            .join(Document, Candidate.document_id == Document.id)
            .where(Candidate.owner_id == owner_id, Document.sha256 == sha256)
        )
        return self._session.scalar(statement)

    def get(self, owner_id: int, candidate_id: int) -> Candidate | None:
        statement = select(Candidate).where(
            Candidate.id == candidate_id, Candidate.owner_id == owner_id
        )
        return self._session.scalar(statement)

    def list(
        self,
        owner_id: int,
        *,
        name_query: str | None = None,
        skill: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Candidate], int]:
        """Retourne (page de candidats, total correspondant aux filtres)."""
        conditions = [Candidate.owner_id == owner_id]
        if name_query:
            # autoescape : les % et _ saisis par l'utilisateur sont traités comme du texte.
            conditions.append(Candidate.full_name.icontains(name_query, autoescape=True))
        if skill:
            # Opérateur JSONB « contient » : profile @> {"skills": [{"name": ...}]}
            conditions.append(Candidate.profile.contains({"skills": [{"name": skill}]}))

        total = self._session.scalar(select(func.count()).select_from(Candidate).where(*conditions))
        page = self._session.scalars(
            select(Candidate)
            .where(*conditions)
            .order_by(Candidate.created_at.desc(), Candidate.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(page), total or 0

    def add(self, candidate: Candidate) -> Candidate:
        """Enregistre le candidat et son document dans une seule transaction."""
        try:
            self._session.add(candidate)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise
        return candidate

    def delete(self, candidate: Candidate) -> None:
        """Supprime le candidat puis son document (texte extrait compris)."""
        document = candidate.document
        self._session.delete(candidate)
        self._session.delete(document)
        self._session.commit()
