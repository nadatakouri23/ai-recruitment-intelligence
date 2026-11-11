"""Stockage des fichiers sur disque.

Le nom du fichier sur disque est généré par nous (UUID) : jamais dérivé du nom envoyé par
l'utilisateur, ce qui rend impossible toute traversée de dossier (« ../../etc/passwd »).
"""

import uuid
from pathlib import Path

import structlog

log = structlog.get_logger()


class FileStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, content: bytes, extension: str) -> str:
        """Écrit le fichier et retourne son nom de stockage."""
        self._root.mkdir(parents=True, exist_ok=True)
        storage_name = f"{uuid.uuid4().hex}.{extension.lstrip('.')}"
        (self._root / storage_name).write_bytes(content)
        return storage_name

    def delete(self, storage_name: str) -> None:
        """Supprime le fichier. Une absence n'est pas une erreur ; tout échec est journalisé."""
        path = self._root / Path(storage_name).name  # ne garde que le nom, jamais un chemin
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            log.error(
                "file_delete_failed", storage_name=storage_name, error_type=type(exc).__name__
            )

    def exists(self, storage_name: str) -> bool:
        return (self._root / Path(storage_name).name).is_file()
