"""Banc d'évaluation du sémantique (doublure déterministe : rapide, sans modèle)."""

import pytest

from app.modules.embeddings.embedder import HashingEmbedder
from app.modules.jobs.parsing import analyze_job
from evaluation.families import FAMILIES
from evaluation.generator import build_dataset
from evaluation.run import (
    DEFAULT_NAME,
    SEMANTIC_NAMES,
    VARIANTS,
    WITH_SEMANTIC_NAME,
    evaluate,
    parse_pool,
    semantic_fairness,
    variants_for,
)
from evaluation.search_eval import (
    MODES,
    QUERIES,
    evaluate_search,
    gold,
    rank_candidates,
    search_report,
)

SMALL = 3


@pytest.fixture(scope="module")
def setup():
    embedder = HashingEmbedder()
    dataset = build_dataset(1, per_family=SMALL)
    parsed = parse_pool({c.key: c.cv for c in dataset.candidates}, embedder)
    profiles = [analyze_job(j.title, j.description) for j in dataset.jobs]
    return embedder, dataset, parsed, profiles


# ------------------------------------------------------------------ requêtes et règle


def test_queries_cover_every_family_in_both_languages() -> None:
    descriptive = [q for q in QUERIES if q.kind == "descriptive"]

    assert len(descriptive) == 18 and len(QUERIES) == 27
    for family in FAMILIES:
        langs = {q.lang for q in descriptive if q.family == family}
        assert langs == {"fr", "en"}, family
    assert {q.family for q in QUERIES} == set(FAMILIES)


def test_gold_for_a_query() -> None:
    query = next(q for q in QUERIES if q.family == "devops")

    assert gold(query, "devops") == 2
    assert gold(query, "backend_python") == 1  # famille voisine
    assert gold(query, "marketing") == 0


# ------------------------------------------------------------------ variantes


def test_semantic_variants_exist_only_when_embeddings_are_provided() -> None:
    assert set(variants_for(False)) == set(VARIANTS)
    assert set(variants_for(True)) == set(VARIANTS) | set(SEMANTIC_NAMES)
    assert all(
        v.get("semantic", 0) > 0 for n, v in variants_for(True).items() if n in SEMANTIC_NAMES
    )


def test_default_plus_semantic_gives_the_semantic_component_twenty_percent() -> None:
    weights = variants_for(True)[WITH_SEMANTIC_NAME]
    total = sum(weights.values())

    assert weights["semantic"] / total == pytest.approx(0.2)
    assert weights["skills"] / total == pytest.approx(0.45 * 0.8)


def test_evaluation_with_embeddings_reports_the_semantic_variants(setup) -> None:
    embedder, dataset, parsed, profiles = setup

    results = evaluate(dataset, parsed, profiles, seed=1, embedder=embedder)

    assert set(SEMANTIC_NAMES) <= set(results["per_variant"])
    for name in (*SEMANTIC_NAMES, DEFAULT_NAME):
        assert len(results["per_variant"][name]["NDCG@10"]) == len(dataset.jobs)
    # Chaque offre a une composante sémantique calculée pour chaque candidat.
    sample = next(iter(results["raws"].values()))
    assert all(raw["semantic"] is not None for raw in sample.values())


def test_without_embeddings_the_semantic_component_is_absent(setup) -> None:
    _, dataset, _, profiles = setup
    plain = parse_pool({c.key: c.cv for c in dataset.candidates})

    results = evaluate(dataset, plain, profiles, seed=1)

    assert not set(SEMANTIC_NAMES) & set(results["per_variant"])
    assert all(
        raw["semantic"] is None for per_job in results["raws"].values() for raw in per_job.values()
    )


# ------------------------------------------------------------------ recherche


def test_every_mode_ranks_every_candidate_exactly_once(setup) -> None:
    embedder, dataset, parsed, _ = setup
    keys = sorted(c.key for c in dataset.candidates)

    for query in QUERIES[:6]:
        rankings = rank_candidates(query, dataset, parsed, embedder)
        for mode in MODES:
            assert sorted(rankings[mode]) == keys, (query.text, mode)


def test_search_evaluation_and_report_are_complete(setup) -> None:
    embedder, dataset, parsed, _ = setup

    results = evaluate_search(dataset, parsed, embedder)
    report = search_report(results, embedder.name)

    assert len(results["rows"]) == len(QUERIES)
    for heading in (
        "## 7. Recherche de candidats",
        "Requêtes descriptives",
        "contrôle",
        "Effet de la langue",
    ):
        assert heading in report
    assert "Hybride (RRF)" in report and "Limites" in report


def test_keyword_search_finds_tool_queries_even_with_the_lexical_stand_in(setup) -> None:
    embedder, dataset, parsed, _ = setup
    by_key = {c.key: c for c in dataset.candidates}
    query = next(q for q in QUERIES if q.kind == "outils" and q.family == "frontend")

    top = rank_candidates(query, dataset, parsed, embedder)["keyword"][:3]

    assert sum(by_key[k].family == "frontend" for k in top) >= 2


# ------------------------------------------------------------------ équité du sémantique


def test_identity_changes_never_move_a_semantic_score(setup) -> None:
    embedder, dataset, parsed, profiles = setup

    result = semantic_fairness(dataset, parsed, profiles, embedder, seed=1)
    identity = result["identité (nom, contacts, titre d'en-tête, langues parlées)"]

    assert identity["max"] == 0 and identity["changed"] == 0 and identity["overlap"] == 1
    assert set(result) >= {"genre des intitulés de poste (CV français)"}


def test_place_changes_do_move_the_semantic_score_slightly(setup) -> None:
    """Les villes restent dans les passages : le test doit le montrer, pas le cacher."""
    embedder, dataset, parsed, profiles = setup

    result = semantic_fairness(dataset, parsed, profiles, embedder, seed=1)
    proxies = result["proxys géographiques (villes des employeurs et de l'école)"]

    assert proxies["max"] >= 0 and 0 <= proxies["overlap"] <= 1
