"""Métriques de qualité d'un classement (fonctions pures, sans dépendance).

Un classement est donné par les GAINS de pertinence, dans l'ordre où le système a classé les
candidats : `gains[0]` est la pertinence du candidat classé premier. Un gain est un nombre >= 0
(0 = non pertinent ; 1, 2, 3 = pertinence croissante).

Convention : une métrique qui n'est pas définie (par exemple le rappel quand aucun candidat n'est
pertinent) vaut None, et non 0, pour ne pas fausser les moyennes ; `mean_defined` les écarte et
indique combien ont été écartés.
"""

import math
import random
from collections.abc import Sequence


def precision_at_k(gains: Sequence[float], k: int, threshold: float = 1) -> float | None:
    """Part des k premiers qui sont pertinents (gain >= threshold). None si la liste est vide."""
    _check_k(k)
    top = gains[:k]
    if not top:
        return None
    # On divise par k même si la liste est plus courte : un système qui rend moins de k résultats
    # n'est pas récompensé pour cela.
    return sum(1 for g in top if g >= threshold) / k


def recall_at_k(gains: Sequence[float], k: int, threshold: float = 1) -> float | None:
    """Part des candidats pertinents retrouvés dans les k premiers. None s'il n'y en a aucun."""
    _check_k(k)
    total = sum(1 for g in gains if g >= threshold)
    if total == 0:
        return None
    return sum(1 for g in gains[:k] if g >= threshold) / total


def dcg_at_k(gains: Sequence[float], k: int) -> float:
    """Gain cumulé actualisé : un résultat pertinent compte plus s'il est classé haut.

    Gain exponentiel (2^g - 1) : un candidat de gain 3 vaut nettement plus que trois de gain 1.
    """
    _check_k(k)
    return sum(
        (2**g - 1) / math.log2(position + 1) for position, g in enumerate(gains[:k], start=1)
    )


def ndcg_at_k(gains: Sequence[float], k: int) -> float | None:
    """DCG normalisé par le meilleur classement possible de CES MÊMES candidats (entre 0 et 1).

    `gains` doit contenir TOUS les candidats classés (pas seulement les k premiers), car la
    normalisation compare à l'ordre idéal de l'ensemble. None si aucun candidat n'est pertinent.
    """
    ideal = dcg_at_k(sorted(gains, reverse=True), k)
    if ideal == 0:
        return None
    return dcg_at_k(gains, k) / ideal


def reciprocal_rank(gains: Sequence[float], threshold: float = 1) -> float | None:
    """1 / rang du premier résultat pertinent ; 0 s'il n'y en a aucun dans la liste classée."""
    if not any(g >= threshold for g in gains):
        return None
    for position, g in enumerate(gains, start=1):
        if g >= threshold:
            return 1 / position
    return None  # inatteignable


def mean_defined(values: Sequence[float | None]) -> tuple[float | None, int]:
    """(moyenne des valeurs définies, nombre de valeurs écartées)."""
    defined = [v for v in values if v is not None]
    dropped = len(values) - len(defined)
    return (sum(defined) / len(defined) if defined else None), dropped


def bootstrap_ci(
    values: Sequence[float | None],
    *,
    confidence: float = 0.95,
    resamples: int = 2000,
    seed: int = 0,
) -> tuple[float, float] | None:
    """Intervalle de confiance de la moyenne par rééchantillonnage (percentile).

    Rééchantillonne les VALEURS (ici : une par offre). Avec peu d'offres l'intervalle est large :
    c'est voulu, il dit honnêtement ce que ces données permettent d'affirmer.
    """
    defined = [v for v in values if v is not None]
    if len(defined) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(
        sum(rng.choices(defined, k=len(defined))) / len(defined) for _ in range(resamples)
    )
    alpha = (1 - confidence) / 2
    return means[int(alpha * resamples)], means[min(resamples - 1, int((1 - alpha) * resamples))]


def paired_difference_ci(
    a: Sequence[float | None],
    b: Sequence[float | None],
    *,
    confidence: float = 0.95,
    resamples: int = 2000,
    seed: int = 0,
) -> tuple[float, tuple[float, float]] | None:
    """Différence moyenne a - b sur les offres où les deux sont définies, avec son intervalle.

    Si l'intervalle ne contient pas 0, la différence n'est pas explicable par le seul hasard du
    choix des offres (sous les hypothèses du rééchantillonnage).
    """
    if len(a) != len(b):
        raise ValueError("Les deux séries doivent avoir la même longueur.")
    diffs = [x - y for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    interval = bootstrap_ci(diffs, confidence=confidence, resamples=resamples, seed=seed)
    if interval is None:
        return None
    return sum(diffs) / len(diffs), interval


def _check_k(k: int) -> None:
    if k < 1:
        raise ValueError("k doit être >= 1.")
