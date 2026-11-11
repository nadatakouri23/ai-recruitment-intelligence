"""Modèle SQLAlchemy d'un document importé (fichier + texte extrait)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"
    # Un même propriétaire ne peut pas importer deux fois exactement le même fichier.
    __table_args__ = (UniqueConstraint("owner_id", "sha256", name="uq_documents_owner_sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # "pdf" | "docx"
    # Nom d'affichage uniquement ; le fichier est stocké sous `storage_name` (UUID).
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_name: Mapped[str] = mapped_column(String(80), unique=True)
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    page_count: Mapped[int | None]
    # Texte nettoyé : base de la recherche et du futur RAG.
    extracted_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
