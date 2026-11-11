"""Classements et fusion de rangs (RRF), vérifiés à la main."""

import pytest

from app.modules.embeddings.ranking import RRF_K, ranks, reciprocal_rank_fusion


def test_ranks_order_by_score_then_by_identifier() -> None:
    assert ranks({10: 0.5, 20: 0.9, 30: 0.5}) == {20: 1, 10: 2, 30: 3}
    assert ranks({}) == {}


def test_first_in_both_rankings_scores_exactly_one() -> None:
    fused = reciprocal_rank_fusion({1: 1, 2: 2}, {1: 1, 3: 2})

    assert fused[1] == pytest.approx(1.0)


def test_rrf_hand_computed_values() -> None:
    fused = reciprocal_rank_fusion({1: 1, 2: 2}, {2: 1, 3: 2})
    best = 2 / (RRF_K + 1)

    assert fused[1] == pytest.approx((1 / (RRF_K + 1)) / best)  # présent d'un seul côté
    assert fused[2] == pytest.approx((1 / (RRF_K + 2) + 1 / (RRF_K + 1)) / best)
    assert fused[3] == pytest.approx((1 / (RRF_K + 2)) / best)


def test_agreement_between_methods_beats_a_single_first_place() -> None:
    # Le candidat 2 est 2e dans les deux classements ; le 1 n'est premier que d'un seul côté.
    fused = reciprocal_rank_fusion({1: 1, 2: 2}, {3: 1, 2: 2})

    assert fused[2] > fused[1] and fused[2] > fused[3]


def test_rrf_is_insensitive_to_the_scale_of_the_original_scores() -> None:
    small = ranks({1: 0.001, 2: 0.002})
    large = ranks({1: 1000.0, 2: 2000.0})

    assert small == large


def test_scores_are_between_zero_and_one() -> None:
    fused = reciprocal_rank_fusion(dict.fromkeys(range(1, 200), 1), {7: 150})

    assert all(0 < value <= 1 for value in fused.values())
