"""Similarité entre vecteurs (fonctions pures)."""

import math
from collections.abc import Sequence


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Similarité cosinus entre -1 et 1 (1 = même direction)."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def semantic_score(
    job_vector: Sequence[float], chunk_vectors: Sequence[Sequence[float]], top: int = 3
) -> float | None:
    """Score sémantique d'un candidat pour une offre, entre 0 et 1.

    Moyenne des `top` meilleures similarités entre l'offre et les passages du CV : un seul passage
    chanceux ne suffit pas, et un long CV n'est pas pénalisé par ses passages hors sujet. Les
    similarités négatives sont ramenées à 0. None si le candidat n'a aucun passage vectorisé.
    """
    if not chunk_vectors:
        return None
    best = sorted((cosine(job_vector, v) for v in chunk_vectors), reverse=True)[:top]
    return max(0.0, sum(best) / len(best))
