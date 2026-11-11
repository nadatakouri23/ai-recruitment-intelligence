"""Configuration du logging structuré (structlog).

Chaque appel `log.info("evenement", cle=valeur)` produit un dictionnaire qui
traverse une chaîne de processeurs, puis est rendu en JSON (hors développement)
ou en console colorée (développement).

Règle du projet : ne jamais logger de secret, de token ni de contenu de CV.
On logge des identifiants et des métadonnées (taille, durée), jamais le texte.
"""

import logging

import structlog

from app.core.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structlog pour toute l'application.

    À appeler une seule fois, au démarrage.
    """
    # "INFO" -> 20 : le filtrage compare des niveaux numériques.
    level = logging.getLevelNamesMapping()[settings.log_level]

    shared_processors: list[structlog.typing.Processor] = [
        # Ajoute les variables de contexte (ex. request_id, ajouté plus tard).
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        # Transforme une exception en texte ; doit précéder le renderer, sinon
        # le renderer recevrait un objet exception qu'il ne sait pas afficher.
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor
    if settings.environment == "development":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        # Les messages sous le niveau configuré sont jetés très tôt (peu coûteux).
        wrapper_class=structlog.make_filtering_bound_logger(level),
        # Sortie standard : c'est ce que Docker collecte.
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
