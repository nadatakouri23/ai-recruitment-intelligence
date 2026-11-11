"""Évaluation de la RECHERCHE de candidats : mots-clés, sémantique, hybride.

Requêtes en langage naturel, paraphrasées, en français et en anglais, écrites AVANT de voir les
résultats et jamais modifiées ensuite. Pertinence : 2 = candidat de la famille visée, 1 = famille
voisine, 0 = autre. Précision/rappel : pertinent = niveau 2.

Les classements utilisent les MÊMES fonctions que l'API (`embeddings.ranking`, TF-IDF, cosinus) ;
seule la base de données est remplacée par la mémoire.
"""

import statistics
from collections import defaultdict
from dataclasses import dataclass

from app.modules.embeddings.embedder import Embedder, embed_texts
from app.modules.embeddings.ranking import ranks, reciprocal_rank_fusion
from app.modules.embeddings.similarity import cosine
from app.modules.evaluation.metrics import (
    bootstrap_ci,
    mean_defined,
    ndcg_at_k,
    paired_difference_ci,
    precision_at_k,
    reciprocal_rank,
)
from app.modules.matching.tfidf import tfidf_similarities
from evaluation.families import are_adjacent
from evaluation.generator import Dataset
from evaluation.run import Parsed


@dataclass(frozen=True)
class Query:
    family: str
    lang: str
    kind: str  # "descriptive" : décrit le métier sans nommer d'outil ; "outils" : cite des outils
    text: str


# Écrites une fois pour toutes. Les requêtes « descriptives » évitent volontairement le jargon des CV.
QUERIES: tuple[Query, ...] = (
    Query(
        "data_scientist",
        "fr",
        "descriptive",
        "quelqu'un qui construit des modèles prédictifs à partir de données et en tire des conclusions chiffrées",
    ),
    Query(
        "data_scientist",
        "en",
        "descriptive",
        "someone who builds predictive models from data and draws quantitative conclusions",
    ),
    Query(
        "ml_engineer",
        "fr",
        "descriptive",
        "ingénieur qui met en production des réseaux de neurones et des systèmes d'intelligence artificielle",
    ),
    Query(
        "ml_engineer",
        "en",
        "descriptive",
        "engineer who deploys neural networks and artificial intelligence systems to production",
    ),
    Query(
        "data_analyst",
        "fr",
        "descriptive",
        "personne qui prépare des tableaux de bord et des rapports d'indicateurs pour la direction",
    ),
    Query(
        "data_analyst",
        "en",
        "descriptive",
        "analyst who prepares business dashboards and indicator reports for management",
    ),
    Query(
        "data_engineer",
        "fr",
        "descriptive",
        "spécialiste des flux de données volumineuses, de leur ingestion et de leur traitement",
    ),
    Query(
        "data_engineer",
        "en",
        "descriptive",
        "specialist in large data flows, their ingestion and processing",
    ),
    Query(
        "backend_java",
        "fr",
        "descriptive",
        "développeur d'applications serveur d'entreprise avec services web et base relationnelle",
    ),
    Query(
        "backend_java",
        "en",
        "descriptive",
        "enterprise server-side application developer with web services and relational database",
    ),
    Query(
        "backend_python",
        "fr",
        "descriptive",
        "développeur de services web et d'interfaces de programmation côté serveur",
    ),
    Query(
        "backend_python",
        "en",
        "descriptive",
        "developer of web services and server-side programming interfaces",
    ),
    Query(
        "frontend",
        "fr",
        "descriptive",
        "développeur d'interfaces web modernes côté navigateur avec composants réutilisables",
    ),
    Query(
        "frontend",
        "en",
        "descriptive",
        "developer of modern browser-side web interfaces with reusable components",
    ),
    Query(
        "devops",
        "fr",
        "descriptive",
        "ingénieur qui automatise le déploiement et l'infrastructure, conteneurs et orchestration",
    ),
    Query(
        "devops",
        "en",
        "descriptive",
        "engineer who automates deployment and infrastructure, containers and orchestration",
    ),
    Query(
        "marketing",
        "fr",
        "descriptive",
        "responsable de l'acquisition en ligne, de la visibilité dans les moteurs de recherche et des campagnes",
    ),
    Query(
        "marketing",
        "en",
        "descriptive",
        "lead for online acquisition, search engine visibility and campaigns",
    ),
    # Contrôle : requêtes qui citent des outils (là, les mots-clés devraient bien faire).
    Query("data_scientist", "en", "outils", "scikit-learn pandas statistics jupyter"),
    Query("ml_engineer", "en", "outils", "pytorch deep learning docker"),
    Query("data_analyst", "fr", "outils", "power bi tableau excel analyse de données"),
    Query("data_engineer", "en", "outils", "spark airflow kafka etl"),
    Query("backend_java", "fr", "outils", "java spring microservices postgresql"),
    Query("backend_python", "en", "outils", "python postgresql docker rest api"),
    Query("frontend", "fr", "outils", "react typescript javascript html css"),
    Query("devops", "en", "outils", "kubernetes terraform ansible ci/cd"),
    Query("marketing", "fr", "outils", "seo google analytics gestion de projet"),
)

MODES = ("keyword", "semantic", "hybrid")
LABELS = {"keyword": "Mots-clés (TF-IDF)", "semantic": "Sémantique", "hybrid": "Hybride (RRF)"}


def gold(query: Query, family: str) -> int:
    if family == query.family:
        return 2
    return 1 if are_adjacent(family, query.family) else 0


def rank_candidates(
    query: Query, dataset: Dataset, parsed: Parsed, embedder: Embedder
) -> dict[str, list[int]]:
    """Classement des candidats (clés) pour chaque mode, avec le code de l'API."""
    keys = [c.key for c in dataset.candidates]
    passages = [(key, chunk) for key in keys for chunk in parsed.chunks[key]]

    similarities = tfidf_similarities(query.text, [chunk.text for _, chunk in passages])
    keyword: dict[int, float] = {}
    for (key, _), score in zip(passages, similarities, strict=True):
        if score > 0 and score > keyword.get(key, 0.0):
            keyword[key] = score

    (query_vector,) = embed_texts(embedder, [query.text])
    semantic: dict[int, float] = {}
    for key in keys:
        best = max((cosine(query_vector, v) for v in parsed.chunk_vectors[key]), default=0.0)
        if best > 0:
            semantic[key] = best

    keyword_rank, semantic_rank = ranks(keyword), ranks(semantic)
    fused = reciprocal_rank_fusion(keyword_rank, semantic_rank)
    out = {}
    for mode, scores in (("keyword", keyword), ("semantic", semantic), ("hybrid", fused)):
        ordered = sorted(scores, key=lambda k: (-scores[k], k))
        # Les candidats sans aucun résultat sont ajoutés à la suite (ordre neutre) : comme dans
        # l'évaluation du matching, tous les candidats sont classés.
        out[mode] = ordered + [k for k in sorted(keys) if k not in scores]
    return out


def evaluate_search(dataset: Dataset, parsed: Parsed, embedder: Embedder) -> dict:
    by_key = {c.key: c for c in dataset.candidates}
    rows = []
    for query in QUERIES:
        rankings = rank_candidates(query, dataset, parsed, embedder)
        entry = {"query": query}
        for mode, ordered in rankings.items():
            gains = [gold(query, by_key[k].family) for k in ordered]
            entry[mode] = {
                "P@5": precision_at_k(gains, 5, 2),
                "P@10": precision_at_k(gains, 10, 2),
                "NDCG@10": ndcg_at_k(gains, 10),
                "MRR": reciprocal_rank(gains, 2),
            }
            entry[f"{mode}_cross"] = _cross_language_rank(query, ordered, by_key, gains)
        rows.append(entry)
    return {"rows": rows}


def _cross_language_rank(
    query: Query, ordered: list[int], by_key: dict, gains: list[int]
) -> dict[str, list[float]]:
    """Rang relatif (0 = tête, 100 = fin) des bons candidats, selon que leur CV est dans la langue de la requête."""
    out: dict[str, list[float]] = defaultdict(list)
    for position, (key, gain) in enumerate(zip(ordered, gains, strict=True)):
        if gain == 2:
            label = "même langue" if by_key[key].lang == query.lang else "langues différentes"
            out[label].append(100 * position / len(ordered))
    return dict(out)


def _ci(values: list[float | None]) -> str:
    mean, _ = mean_defined(values)
    interval = bootstrap_ci(values, seed=9)
    if mean is None:
        return "n/d"
    return f"{mean:.3f} [{interval[0]:.2f}–{interval[1]:.2f}]" if interval else f"{mean:.3f}"


def search_report(results: dict, model: str) -> str:
    rows = results["rows"]
    lines = [
        "## 7. Recherche de candidats : mots-clés, sémantique, hybride",
        "",
        f"Modèle d'embeddings : `{model}`. Requêtes écrites une fois pour toutes avant les résultats "
        "(`evaluation/search_eval.py`). Pertinence : 2 = candidat de la famille visée, 1 = voisine, 0 = autre ; "
        "précision : pertinent = niveau 2. Intervalles de confiance à 95 % par rééchantillonnage des requêtes.",
        "",
    ]
    for kind, title in (
        ("descriptive", "Requêtes descriptives (sans nom d'outil), 18 requêtes"),
        ("outils", "Requêtes avec noms d'outils (contrôle), 9 requêtes"),
    ):
        subset = [r for r in rows if r["query"].kind == kind]
        lines += [
            f"### {title}",
            "",
            "| Mode | P@5 | P@10 | NDCG@10 | MRR |",
            "|---|---|---|---|---|",
        ]
        for mode in MODES:
            lines.append(
                f"| {LABELS[mode]} | "
                + " | ".join(
                    _ci([r[mode][m] for r in subset]) for m in ("P@5", "P@10", "NDCG@10", "MRR")
                )
                + " |"
            )
        lines.append("")
        for other in ("keyword", "hybrid"):
            diff = paired_difference_ci(
                [r["semantic"]["NDCG@10"] for r in subset],
                [r[other]["NDCG@10"] for r in subset],
                seed=4,
            )
            if diff:
                mean, (low, high) = diff
                verdict = (
                    "sémantique meilleur"
                    if low > 0
                    else "sémantique moins bon"
                    if high < 0
                    else "indécidable"
                )
                lines.append(
                    f"- NDCG@10, sémantique − {LABELS[other]} : {mean:+.3f} [{low:+.2f}, {high:+.2f}] → {verdict}."
                )
        lines.append("")

    lines += [
        "### Effet de la langue (requêtes descriptives) : rang relatif moyen des bons candidats, en % (0 % = tête)",
        "",
        "| Mode | CV dans la langue de la requête | CV dans l'autre langue |",
        "|---|---|---|",
    ]
    descriptive = [r for r in rows if r["query"].kind == "descriptive"]
    for mode in MODES:
        buckets: dict[str, list[float]] = defaultdict(list)
        for r in descriptive:
            for label, values in r[f"{mode}_cross"].items():
                buckets[label].extend(values)
        same, other = buckets.get("même langue", []), buckets.get("langues différentes", [])
        lines.append(
            f"| {LABELS[mode]} | {statistics.mean(same):.1f} (n={len(same)}) | {statistics.mean(other):.1f} (n={len(other)}) |"
        )
    lines += [
        "",
        "Limites : requêtes écrites par la même personne que les CV ; pertinence = appartenance à une famille de "
        "métier ; CV générés avec des modèles de phrases (peu de variété lexicale) ; 27 requêtes seulement.",
        "",
    ]
    return "\n".join(lines)
