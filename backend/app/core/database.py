"""Connexion à PostgreSQL : moteur, fabrique de sessions et classe mère des modèles.

Rien n'est créé à l'import : le moteur est construit par `create_db_engine`, appelé
au démarrage de l'application (voir `create_app`).
"""

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings


class Base(DeclarativeBase):
    """Classe mère de tous les modèles SQLAlchemy.

    Alembic s'appuie sur `Base.metadata` pour découvrir les tables.
    """


def build_database_url(settings: Settings) -> URL:
    """Construit l'URL de connexion à partir de la configuration.

    `URL.create` échappe correctement les caractères spéciaux du mot de passe
    (@, /, :…), contrairement à une f-string. L'objet `URL` masque aussi le mot
    de passe dans `repr()` ; pour une chaîne de log, utiliser
    `url.render_as_string(hide_password=True)`.
    """
    return URL.create(
        drivername="postgresql+psycopg",  # +psycopg : pilote psycopg 3
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


def create_db_engine(settings: Settings) -> Engine:
    """Crée le moteur SQLAlchemy (pool de connexions réutilisées).

    Le moteur ne se connecte qu'à la première utilisation.
    `pool_pre_ping` teste chaque connexion avant de la prêter : si PostgreSQL a
    redémarré entre-temps, la connexion morte est remplacée au lieu de provoquer
    une erreur sur la requête de l'utilisateur.
    """
    return create_engine(build_database_url(settings), pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Crée la fabrique de sessions (à appeler une fois par requête HTTP).

    `expire_on_commit=False` : après un `commit()`, les objets restent lisibles.
    Sinon SQLAlchemy les « expire » et relirait la base au premier accès, ce qui
    échoue si on renvoie l'objet dans une réponse d'API une fois la session fermée.
    """
    return sessionmaker(bind=engine, expire_on_commit=False)
