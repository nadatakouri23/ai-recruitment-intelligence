"""Métriques de classement, vérifiées contre des valeurs calculées à la main."""

import math

import pytest

from app.modules.evaluation.metrics import (
    bootstrap_ci,
    dcg_at_k,
    mean_defined,
    ndcg_at_k,
    paired_difference_ci,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

# ------------------------------------------------------------------ Precision@K / Recall@K


def test_precision_at_k() -> None:
    gains = [3, 0, 2, 0, 1, 0]

    assert precision_at_k(gains, 1) == 1.0
    assert precision_at_k(gains, 2) == 0.5
    assert precision_at_k(gains, 3) == pytest.approx(2 / 3)
    assert precision_at_k(gains, 5, threshold=2) == pytest.approx(2 / 5)  # seuil de pertinence
    assert precision_at_k(gains, 5, threshold=3) == pytest.approx(1 / 5)


def test_precision_divides_by_k_even_when_fewer_results() -> None:
    assert precision_at_k([1, 1], 4) == 0.5  # 2 pertinents sur 4 demandés
    assert precision_at_k([], 3) is None


def test_recall_at_k() -> None:
    gains = [3, 0, 2, 0, 1, 0]  # 3 pertinents au total

    assert recall_at_k(gains, 1) == pytest.approx(1 / 3)
    assert recall_at_k(gains, 3) == pytest.approx(2 / 3)
    assert recall_at_k(gains, 5) == 1.0
    assert recall_at_k(gains, 3, threshold=2) == 1.0  # 2 pertinents (gain >= 2), 2 retrouvés


def test_recall_is_undefined_without_any_relevant_candidate() -> None:
    assert recall_at_k([0, 0, 0], 2) is None


def test_k_must_be_positive() -> None:
    for function in (precision_at_k, recall_at_k, dcg_at_k, ndcg_at_k):
        with pytest.raises(ValueError, match="k doit être"):
            function([1, 0], 0)


# ------------------------------------------------------------------ NDCG@K


def test_dcg_is_computed_by_hand() -> None:
    # gains 3, 2, 0, 1 ; k = 3 : (2^3-1)/log2(2) + (2^2-1)/log2(3) + 0
    expected = 7 / 1 + 3 / math.log2(3)
    assert dcg_at_k([3, 2, 0, 1], 3) == pytest.approx(expected)


def test_ndcg_is_one_for_the_perfect_ranking_and_lower_otherwise() -> None:
    perfect = [3, 2, 1, 0, 0]
    swapped = [2, 3, 1, 0, 0]
    worst = [0, 0, 1, 2, 3]

    assert ndcg_at_k(perfect, 5) == pytest.approx(1.0)
    assert 0 < ndcg_at_k(swapped, 5) < 1
    assert ndcg_at_k(worst, 5) < ndcg_at_k(swapped, 5)


def test_ndcg_hand_computed_value() -> None:
    gains = [2, 3, 0]  # ordre idéal : 3, 2, 0
    dcg = 3 / 1 + 7 / math.log2(3)
    ideal = 7 / 1 + 3 / math.log2(3)

    assert ndcg_at_k(gains, 3) == pytest.approx(dcg / ideal)


def test_ndcg_normalizes_against_the_whole_pool_not_just_the_top_k() -> None:
    # Le meilleur candidat (gain 3) est classé 4e : hors du top-3, il n'est pas retrouvé.
    assert ndcg_at_k([0, 0, 0, 3], 3) == 0.0
    assert ndcg_at_k([0, 0, 0, 3], 4) == pytest.approx(1 / math.log2(5))


def test_ndcg_is_undefined_when_nobody_is_relevant() -> None:
    assert ndcg_at_k([0, 0, 0], 3) is None


def test_ndcg_is_invariant_to_scaling_of_the_pool_with_irrelevant_candidates() -> None:
    assert ndcg_at_k([3, 1, 0], 3) == pytest.approx(ndcg_at_k([3, 1, 0, 0, 0, 0, 0], 3))


# ------------------------------------------------------------------ rang réciproque, moyennes


def test_reciprocal_rank() -> None:
    assert reciprocal_rank([0, 0, 2, 1]) == pytest.approx(1 / 3)
    assert reciprocal_rank([1, 0]) == 1.0
    assert reciprocal_rank([0, 0]) is None
    assert reciprocal_rank([0, 1, 2], threshold=2) == pytest.approx(1 / 3)


def test_mean_defined_ignores_undefined_values_and_counts_them() -> None:
    assert mean_defined([1.0, None, 0.0, None, 0.5]) == (0.5, 2)
    assert mean_defined([None, None]) == (None, 2)
    assert mean_defined([]) == (None, 0)


# ------------------------------------------------------------------ intervalles de confiance


def test_bootstrap_ci_contains_the_mean_and_is_reproducible() -> None:
    values = [0.2, 0.4, 0.6, 0.8, 0.5, 0.7, 0.3, 0.9]
    mean = sum(values) / len(values)

    low, high = bootstrap_ci(values, seed=1) or (0, 0)

    assert low <= mean <= high
    assert bootstrap_ci(values, seed=1) == bootstrap_ci(values, seed=1)
    assert low >= 0.2 and high <= 0.9


def test_bootstrap_ci_of_constant_values_is_degenerate() -> None:
    assert bootstrap_ci([0.5] * 6) == (0.5, 0.5)


def test_bootstrap_ci_needs_at_least_two_values() -> None:
    assert bootstrap_ci([0.5]) is None
    assert bootstrap_ci([None, None, 0.5]) is None


def test_fewer_observations_give_a_wider_interval() -> None:
    wide = bootstrap_ci([0.1, 0.9, 0.2, 0.8], seed=3) or (0, 0)
    narrow = bootstrap_ci([0.1, 0.9, 0.2, 0.8] * 10, seed=3) or (0, 0)

    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_paired_difference_detects_a_consistent_gap() -> None:
    better = [0.8, 0.9, 0.7, 0.85, 0.75, 0.8]
    worse = [0.4, 0.5, 0.3, 0.45, 0.35, 0.4]

    result = paired_difference_ci(better, worse)

    assert result is not None
    difference, (low, high) = result
    assert difference == pytest.approx(0.4)
    assert low > 0  # l'écart n'est pas dû au hasard du choix des offres


def test_paired_difference_is_inconclusive_when_gaps_change_sign() -> None:
    a = [0.9, 0.1, 0.8, 0.2, 0.7, 0.3]
    b = [0.1, 0.9, 0.2, 0.8, 0.3, 0.7]

    result = paired_difference_ci(a, b)

    assert result is not None and result[1][0] < 0 < result[1][1]


def test_paired_difference_skips_undefined_pairs_and_checks_lengths() -> None:
    result = paired_difference_ci([1.0, None, 0.5], [0.5, 0.2, 0.25])
    assert result is not None and result[0] == pytest.approx(0.375)
    with pytest.raises(ValueError, match="même longueur"):
        paired_difference_ci([1.0], [1.0, 2.0])
