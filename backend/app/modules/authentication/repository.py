"""Accès aux données des utilisateurs : uniquement des requêtes, aucune règle métier."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.authentication.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def list_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        statement = select(User).order_by(User.id).limit(limit).offset(offset)
        return list(self._session.scalars(statement))

    def add(self, user: User) -> User:
        """Ajoute et valide. Peut lever IntegrityError si l'email existe déjà."""
        self._session.add(user)
        self._session.commit()
        return user
