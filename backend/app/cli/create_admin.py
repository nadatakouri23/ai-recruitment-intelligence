"""Crée le premier administrateur (impossible via l'API publique, par conception).

Usage, depuis backend/ :
    python -m app.cli.create_admin --email admin@example.com --name "Admin"
Le mot de passe est demandé de façon masquée (jamais passé en argument de ligne de commande,
où il resterait dans l'historique du shell).
"""

import argparse
import getpass
import sys

from pydantic import TypeAdapter, ValidationError

from app.core.config import get_settings
from app.core.database import create_db_engine, create_session_factory
from app.modules.authentication.models import Role
from app.modules.authentication.repository import UserRepository
from app.modules.authentication.schemas import UserCreate
from app.modules.authentication.service import AuthService, EmailAlreadyRegisteredError


def main() -> int:
    parser = argparse.ArgumentParser(description="Créer un administrateur.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
    if password != getpass.getpass("Confirmer le mot de passe : "):
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1

    try:
        # Réutilise les mêmes règles de validation que l'API.
        data = TypeAdapter(UserCreate).validate_python(
            {"email": args.email, "password": password, "full_name": args.name}
        )
    except ValidationError as exc:
        print(f"Données invalides :\n{exc}", file=sys.stderr)
        return 1

    settings = get_settings()
    engine = create_db_engine(settings)
    try:
        with create_session_factory(engine)() as session:
            service = AuthService(UserRepository(session), settings)
            user = service.register(data.email, data.password, data.full_name, role=Role.ADMIN)
            print(f"Administrateur créé (id={user.id}).")
    except EmailAlreadyRegisteredError:
        print("Cette adresse e-mail existe déjà.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
