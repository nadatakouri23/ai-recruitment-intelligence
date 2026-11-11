"""Schémas Pydantic : ce qui entre et sort de l'API (jamais le hash du mot de passe)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.authentication.models import Role


class UserCreate(BaseModel):
    """Corps de la requête d'inscription. Le rôle n'est volontairement pas modifiable ici."""

    email: EmailStr
    # 12 caractères minimum (recommandation NIST : la longueur prime sur la complexité).
    # 128 maximum : évite qu'un mot de passe géant serve à saturer le CPU (hachage coûteux).
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Le nom ne peut pas être vide.")
        return value


class UserRead(BaseModel):
    """Représentation publique d'un utilisateur."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
