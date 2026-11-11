"""Passages de CV (texte + vecteur) pour la recherche."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.embeddings.embedder import EMBEDDING_DIM


class CandidateChunk(Base):
    __tablename__ = "candidate_chunks"
    __table_args__ = (
        UniqueConstraint("candidate_id", "position", name="uq_chunks_candidate_position"),
        # Index de voisins approchés (HNSW, distance cosinus). Inutile pour quelques milliers de
        # passages (un balayage exact est instantané), mais c'est ce qui permettra de passer à
        # l'échelle sans changer les requêtes.
        Index(
            "ix_candidate_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    # Dupliqué pour filtrer par propriétaire directement dans la requête vectorielle.
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    section: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    # Absents tant que les embeddings sont désactivés : la recherche par mots-clés marche déjà.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(120))
