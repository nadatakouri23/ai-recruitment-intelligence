"""Modèle SQLAlchemy des utilisateurs."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Role(StrEnum):
    """Rôles applicatifs. Un nouvel inscrit est toujours RECRUITER."""

    RECRUITER = "recruiter"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Adresse normalisée (minuscules, sans espaces) : l'unicité est donc insensible à la casse.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Empreinte Argon2, jamais le mot de passe.
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(
        # Stocké en texte (pas d'ENUM natif PostgreSQL) : plus simple à faire évoluer.
        Enum(
            Role,
            native_enum=False,
            length=20,
            create_constraint=True,
            name="user_role",
            values_callable=lambda roles: [r.value for r in roles],
        ),
        default=Role.RECRUITER,
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
