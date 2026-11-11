"""Classements et fusion de classements (fonctions pures).

Partagées par la recherche (service) et par le banc d'évaluation : on évalue ainsi exactement
le code qui sert en production.
"""

from collections.abc import Mapping

# Constante classique de la fusion de rangs (Cormack et al., 2009).
RRF_K = 60


def ranks(scores: Mapping[int, float]) -> dict[int, int]:
    """Rang (1 = meilleur) de chaque identifiant ; égalités : identifiant croissant d'abord."""
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    return {key: position for position, key in enumerate(ordered, start=1)}


def reciprocal_rank_fusion(
    keyword: Mapping[int, int], semantic: Mapping[int, int]
) -> dict[int, float]:
    """Fusionne deux classements par leurs RANGS (pas leurs scores), score final entre 0 et 1.

    On fusionne les rangs parce que TF-IDF et cosinus n'ont pas la même échelle et ne s'additionnent
    pas. 1 = premier dans les deux classements ; un candidat absent d'un classement n'y gagne rien.
    """
    best = 2 / (RRF_K + 1)
    return {
        key: (
            (1 / (RRF_K + keyword[key]) if key in keyword else 0.0)
            + (1 / (RRF_K + semantic[key]) if key in semantic else 0.0)
        )
        / best
        for key in set(keyword) | set(semantic)
    }
