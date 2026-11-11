"""Banc d'évaluation du matching sur le jeu SYNTHÉTIQUE.

Usage, depuis backend/ :
    .venv\\Scripts\\python.exe -m evaluation.run --seed 1 --output ..\\docs\\evaluation\\matching-results-dev.md

Protocole : la graine « dev » sert à regarder, comprendre et corriger. Le chiffre final est calculé
UNE FOIS sur la graine « test », qu'on n'a pas regardée avant. Toute modification du moteur après
avoir vu les résultats « test » invalide ce jeu : il faudrait en tirer un nouveau.
"""

import argparse
import random
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

from app.core.config import Settings
from app.modules.candidates.parsing.parser import parse_cv
from app.modules.candidates.parsing.text_cleaning import clean_text
from app.modules.candidates.profile import CandidateProfile
from app.modules.documents.extraction import NoExtractableTextError, detect_kind, extract_text
from app.modules.embeddings.chunking import Chunk, chunk_cv
from app.modules.embeddings.embedder import Embedder, build_embedder, embed_texts
from app.modules.embeddings.similarity import semantic_score
from app.modules.evaluation.metrics import (
    bootstrap_ci,
    mean_defined,
    ndcg_at_k,
    paired_difference_ci,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.modules.jobs.parsing import analyze_job
from app.modules.jobs.profile import JobProfile
from app.modules.matching.engine import CandidateInput, rank
from app.modules.matching.service import job_query_text
from app.modules.matching.text import anonymized_cv_text
from app.modules.matching.weights import MatchingWeights
from evaluation.generator import (
    TODAY,
    Dataset,
    JobSpec,
    build_dataset,
    gold_grade,
    twin_gender_titles,
    twin_identity,
    twin_proxies,
)
from tests.cv_factory import SyntheticCV, render

COMPONENTS = ("skills", "experience", "education", "tfidf", "keyword", "semantic")
RELEVANT = 2  # une pertinence >= 2 compte comme « pertinent » pour Precision/Recall
PERMUTATIONS = 20  # tirages d'identifiants pour moyenner l'effet des égalités de score

VARIANTS: dict[str, dict[str, float]] = {
    "Mots-clés seuls": {"keyword": 1},
    "TF-IDF seul": {"tfidf": 1},
    "Texte (TF-IDF + mots-clés)": {"tfidf": 1, "keyword": 1},
    "Compétences seules": {"skills": 1},
    "Expérience seule": {"experience": 1},
    "Niveau d'études seul": {"education": 1},
    "Compétences + expérience": {"skills": 1, "experience": 1},
    "Poids par défaut (45/20/20/10/5)": MatchingWeights().model_dump(),
}
DEFAULT_NAME = "Poids par défaut (45/20/20/10/5)"

# Variantes ajoutées seulement quand un modèle d'embeddings est fourni (sinon la composante
# sémantique est vide et ces variantes se confondraient avec d'autres : trompeur).
_DEFAULT_WEIGHTS = {k: v for k, v in MatchingWeights().model_dump().items() if k != "semantic"}
SEMANTIC_VARIANTS: dict[str, dict[str, float]] = {
    "Sémantique seule": {"semantic": 1},
    "Compétences + sémantique": {"skills": 1, "semantic": 1},
    "Texte + sémantique": {"tfidf": 1, "keyword": 1, "semantic": 1},
    "Défaut + sémantique (20 %)": {
        **{k: v * 0.8 for k, v in _DEFAULT_WEIGHTS.items()},
        "semantic": 0.2,
    },
}
SEMANTIC_NAMES = tuple(SEMANTIC_VARIANTS)
WITH_SEMANTIC_NAME = "Défaut + sémantique (20 %)"


def variants_for(has_semantic: bool) -> dict[str, dict[str, float]]:
    return {**VARIANTS, **SEMANTIC_VARIANTS} if has_semantic else dict(VARIANTS)


@dataclass
class Parsed:
    inputs: dict[int, CandidateInput]  # par clé de candidat
    profiles: dict[int, CandidateProfile]
    failures: int
    chunks: dict[int, list[Chunk]] = field(default_factory=dict)  # passages (mêmes règles d'équité)
    chunk_vectors: dict[int, list[list[float]]] = field(default_factory=dict)

    @property
    def has_semantic(self) -> bool:
        return bool(self.chunk_vectors)


def parse_pool(cvs: dict[int, SyntheticCV], embedder: Embedder | None = None) -> Parsed:
    """Chaque CV passe par le VRAI pipeline : rendu en fichier, validation, extraction, analyse."""
    inputs, profiles, failures = {}, {}, 0
    chunks: dict[int, list[Chunk]] = {}
    vectors: dict[int, list[list[float]]] = {}
    for key, cv in cvs.items():
        content = render(cv)
        kind = detect_kind(cv.filename, content, 5 * 1024 * 1024)
        try:
            text = clean_text(extract_text(content, kind, max_pages=30).text)
        except NoExtractableTextError:
            failures += 1
            text = ""
        profile = parse_cv(text, today=TODAY)
        profiles[key] = profile
        inputs[key] = CandidateInput(key, profile, anonymized_cv_text(text))
        chunks[key] = chunk_cv(text)
        if embedder is not None:
            vectors[key] = (
                embed_texts(embedder, [c.text for c in chunks[key]]) if chunks[key] else []
            )
    return Parsed(inputs, profiles, failures, chunks, vectors)


def combine(raw: dict[str, float | None], weights: dict[str, float]) -> float:
    """Recombine les composantes déjà calculées (même règle que le moteur, pour tester d'autres poids)."""
    usable = {
        n: weights.get(n, 0) for n in COMPONENTS if raw[n] is not None and weights.get(n, 0) > 0
    }
    total = sum(usable.values())
    if not total:
        return 0.0
    return round(sum(100 * usable[n] / total * (raw[n] or 0.0) for n in usable), 2)


def engine_components(
    job: JobSpec, parsed: Parsed, profile: JobProfile, embedder: Embedder | None = None
) -> dict[int, dict[str, float | None]]:
    """Composantes brutes de chaque candidat, calculées UNE fois par le vrai moteur."""
    inputs = list(parsed.inputs.values())
    if embedder is not None and parsed.has_semantic:
        (job_vector,) = embed_texts(embedder, [job_query_text(job.title, profile)])
        inputs = [
            replace(
                candidate,
                semantic=semantic_score(job_vector, parsed.chunk_vectors[candidate.candidate_id]),
            )
            for candidate in inputs
        ]
    results = rank(
        profile, f"{job.title}\n{job.description}", inputs, MatchingWeights(), today=TODAY
    )
    return {r.candidate.id: {c.name: c.raw_score for c in r.components} for r in results}


def order(
    raws: dict[int, dict[str, float | None]], weights: dict[str, float], tie_ids: dict[int, int]
) -> list[int]:
    """Clés classées du meilleur au moins bon ; égalités départagées par identifiant (permuté)."""
    scored = {key: combine(raw, weights) for key, raw in raws.items()}
    return sorted(scored, key=lambda k: (-scored[k], tie_ids[k]))


def metrics_for(ranked: list[int], gains: dict[int, int]) -> dict[str, float | None]:
    ordered = [gains[k] for k in ranked]
    return {
        "P@5": precision_at_k(ordered, 5, RELEVANT),
        "P@10": precision_at_k(ordered, 10, RELEVANT),
        "R@10": recall_at_k(ordered, 10, RELEVANT),
        "NDCG@10": ndcg_at_k(ordered, 10),
        "MRR": reciprocal_rank(ordered, RELEVANT),
    }


def average(dicts: list[dict[str, float | None]]) -> dict[str, float | None]:
    return {name: mean_defined([d[name] for d in dicts])[0] for name in dicts[0]}


def fmt(value: float | None, digits: int = 3) -> str:
    return "n/d" if value is None else f"{value:.{digits}f}"


def fmt_ci(values: list[float | None]) -> str:
    mean, _ = mean_defined(values)
    interval = bootstrap_ci(values, seed=7)
    if mean is None:
        return "n/d"
    return f"{mean:.3f} [{interval[0]:.2f}–{interval[1]:.2f}]" if interval else f"{mean:.3f}"


# ------------------------------------------------------------------ expériences


def evaluate(
    dataset: Dataset,
    parsed: Parsed,
    profiles: list[JobProfile],
    seed: int,
    embedder: Embedder | None = None,
) -> dict:
    variants = variants_for(parsed.has_semantic)
    keys = [c.key for c in dataset.candidates]
    by_key = {c.key: c for c in dataset.candidates}
    rng = random.Random(seed + 1)
    permutations = []
    for _ in range(PERMUTATIONS):
        shuffled = keys[:]
        rng.shuffle(shuffled)
        permutations.append({key: position for position, key in enumerate(shuffled)})

    raws, gains = {}, {}
    for job, profile in zip(dataset.jobs, profiles, strict=True):
        raws[job.key] = engine_components(job, parsed, profile, embedder)
        gains[job.key] = {k: gold_grade(by_key[k], job) for k in keys}

    per_variant: dict[str, dict[str, list[float | None]]] = {}
    for name, weights in variants.items():
        per_job = {m: [] for m in ("P@5", "P@10", "R@10", "NDCG@10", "MRR")}
        for job in dataset.jobs:
            runs = [
                metrics_for(order(raws[job.key], weights, perm), gains[job.key])
                for perm in permutations
            ]
            for metric, value in average(runs).items():
                per_job[metric].append(value)
        per_variant[name] = per_job

    # Référence aléatoire : espérance sur de nombreux tirages.
    random_runs: dict[str, list[float | None]] = {
        m: [] for m in ("P@5", "P@10", "R@10", "NDCG@10", "MRR")
    }
    for job in dataset.jobs:
        draws = []
        for _ in range(300):
            shuffled = keys[:]
            rng.shuffle(shuffled)
            draws.append(metrics_for(shuffled, gains[job.key]))
        for metric, value in average(draws).items():
            random_runs[metric].append(value)
    per_variant["Aléatoire (espérance)"] = random_runs

    return {
        "raws": raws,
        "gains": gains,
        "per_variant": per_variant,
        "permutations": permutations,
        "by_key": by_key,
        "variants": variants,
    }


def weight_sensitivity(
    dataset: Dataset,
    raws: dict,
    gains: dict,
    perm: dict[int, int],
    n: int = 400,
    has_semantic: bool = False,
) -> dict:
    """Moyenne du NDCG@10 sur toutes les offres pour des poids tirés au hasard (Dirichlet uniforme)."""
    rng = random.Random(11)
    components = [c for c in COMPONENTS if c != "semantic" or has_semantic]
    scores = []
    for _ in range(n):
        draw = [rng.gammavariate(1, 1) for _ in components]
        weights = {c: v / sum(draw) for c, v in zip(components, draw, strict=True)}
        values = [
            metrics_for(order(raws[j.key], weights, perm), gains[j.key])["NDCG@10"]
            for j in dataset.jobs
        ]
        scores.append((mean_defined(values)[0] or 0.0, weights))
    scores.sort(key=lambda s: s[0])
    default = (
        mean_defined(
            [
                metrics_for(order(raws[j.key], MatchingWeights().model_dump(), perm), gains[j.key])[
                    "NDCG@10"
                ]
                for j in dataset.jobs
            ]
        )[0]
        or 0.0
    )
    below = sum(1 for s, _ in scores if s < default) / n
    return {"scores": scores, "default": default, "percentile": below}


def language_effect(
    dataset: Dataset,
    raws: dict,
    gains: dict,
    perm: dict[int, int],
    by_key: dict,
    variants: dict[str, dict[str, float]],
) -> dict:
    """Rang moyen (en %, 0 = tête) des candidats de pertinence 3, selon que CV et offre ont la même langue."""
    out = {}
    for name in ("TF-IDF seul", "Sémantique seule", "Compétences seules", DEFAULT_NAME):
        if name not in variants:
            continue
        buckets: dict[str, list[float]] = {"même langue": [], "langues différentes": []}
        for job in dataset.jobs:
            ranking = order(raws[job.key], variants[name], perm)
            for position, key in enumerate(ranking):
                if gains[job.key][key] == 3:
                    label = "même langue" if by_key[key].lang == job.lang else "langues différentes"
                    buckets[label].append(100 * position / len(ranking))
        out[name] = {k: (statistics.mean(v) if v else None, len(v)) for k, v in buckets.items()}
    return out


def diagnose(dataset: Dataset, parsed: Parsed, profiles: list[JobProfile]) -> dict:
    """Qualité de la lecture des CV et des offres, comparée aux attributs cachés."""
    tp = found_total = expected_total = 0
    no_experience = unknown_heading = 0
    for c in dataset.candidates:
        found = {s.name for s in parsed.profiles[c.key].skills}
        expected = set(c.held) - set(c.substituted)
        tp += len(found & expected)
        found_total += len(found)
        expected_total += len(expected)
        if not parsed.profiles[c.key].experience:
            no_experience += 1
            if c.cv.extra.get("experience") in ("MON PARCOURS", "WHAT I HAVE DONE"):
                unknown_heading += 1
    req_tp = req_found = req_exp = opt_tp = opt_found = opt_exp = years_ok = 0
    for job, profile in zip(dataset.jobs, profiles, strict=True):
        req_tp += len(set(profile.required_skills) & set(job.required_true))
        req_found += len(profile.required_skills)
        req_exp += len(job.required_true)
        opt_tp += len(set(profile.optional_skills) & set(job.optional_true))
        opt_found += len(profile.optional_skills)
        opt_exp += len(job.optional_true)
        years_ok += profile.min_experience_years == job.min_years
    completeness = statistics.mean(
        p.report.extraction_completeness for p in parsed.profiles.values()
    )
    invisible = sum(len(c.substituted) for c in dataset.candidates)
    held = sum(len(c.held) for c in dataset.candidates)
    return {
        "skill_precision": tp / found_total, "skill_recall": tp / expected_total,
        "no_experience": no_experience, "unknown_heading": unknown_heading, "completeness": completeness,
        "req_precision": req_tp / req_found, "req_recall": req_tp / req_exp,
        "opt_precision": opt_tp / max(opt_found, 1), "opt_recall": opt_tp / max(opt_exp, 1),
        "years_ok": years_ok, "jobs": len(dataset.jobs), "failures": parsed.failures,
        "invisible_share": invisible / held,
    }  # fmt: skip


# ------------------------------------------------------------------ équité


def fairness(dataset: Dataset, base: Parsed, profiles: list[JobProfile], seed: int) -> dict:
    rng = random.Random(seed + 2)
    by_key = {c.key: c for c in dataset.candidates}
    specs = {
        "identité (nom, contacts, titre d'en-tête, langues parlées)": {k: twin_identity(c, rng) for k, c in by_key.items()},
        "genre des intitulés de poste (CV français)": {k: twin_gender_titles(c.cv) if c.lang == "fr" else c.cv for k, c in by_key.items()},
        "proxys géographiques (villes des employeurs et de l'école)": {k: twin_proxies(c.cv) for k, c in by_key.items()},
    }  # fmt: skip
    results = {}
    for label, twin_cvs in specs.items():
        twin = parse_pool(twin_cvs)
        deltas, overlaps, with_city, without_city = [], [], [], []
        for job, profile in zip(dataset.jobs, profiles, strict=True):
            text = f"{job.title}\n{job.description}"
            a = {
                r.candidate.id: r
                for r in rank(
                    profile, text, list(base.inputs.values()), MatchingWeights(), today=TODAY
                )
            }
            b = {
                r.candidate.id: r
                for r in rank(
                    profile, text, list(twin.inputs.values()), MatchingWeights(), today=TODAY
                )
            }
            diffs = [abs(a[k].score - b[k].score) for k in a]
            deltas.append(
                (
                    max(diffs),
                    statistics.mean(diffs),
                    sum(1 for d in diffs if d > 0.005) / len(diffs),
                )
            )
            top_a = {k for k, r in a.items() if r.rank <= 10}
            top_b = {k for k, r in b.items() if r.rank <= 10}
            overlap = len(top_a & top_b) / 10
            overlaps.append(overlap)
            (with_city if job.city else without_city).append((statistics.mean(diffs), overlap))
        results[label] = {
            "max": max(d[0] for d in deltas), "mean": statistics.mean(d[1] for d in deltas),
            "changed": statistics.mean(d[2] for d in deltas), "overlap": statistics.mean(overlaps),
            "city": (statistics.mean(x[0] for x in with_city) if with_city else None, statistics.mean(x[1] for x in with_city) if with_city else None, len(with_city)),
            "nocity": (statistics.mean(x[0] for x in without_city) if without_city else None, statistics.mean(x[1] for x in without_city) if without_city else None, len(without_city)),
        }  # fmt: skip
    return results


def _top10(scores: dict[int, float]) -> set[int]:
    return set(sorted(scores, key=lambda key: (-scores[key], key))[:10])


def semantic_fairness(
    dataset: Dataset,
    base: Parsed,
    profiles: list[JobProfile],
    embedder: Embedder,
    seed: int,
) -> dict:
    """Le score sémantique change-t-il quand on modifie UN élément du CV (jumeaux) ?

    Les passages excluent l'en-tête, les langues et les intérêts : changer l'identité ne doit rien
    changer (même texte, mêmes vecteurs). Les villes et les écoles, elles, restent dans les passages.
    """
    rng = random.Random(seed + 3)
    by_key = {c.key: c for c in dataset.candidates}
    twins = {
        "identité (nom, contacts, titre d'en-tête, langues parlées)": {
            k: twin_identity(c, rng) for k, c in by_key.items()
        },
        "genre des intitulés de poste (CV français)": {
            k: twin_gender_titles(c.cv) if c.lang == "fr" else c.cv for k, c in by_key.items()
        },
        "proxys géographiques (villes des employeurs et de l'école)": {
            k: twin_proxies(c.cv) for k, c in by_key.items()
        },
    }
    out = {}
    for label, cvs in twins.items():
        twin = parse_pool(cvs, embedder)
        deltas, overlaps = [], []
        for job, profile in zip(dataset.jobs, profiles, strict=True):
            (job_vector,) = embed_texts(embedder, [job_query_text(job.title, profile)])
            a = {k: semantic_score(job_vector, v) or 0.0 for k, v in base.chunk_vectors.items()}
            b = {k: semantic_score(job_vector, v) or 0.0 for k, v in twin.chunk_vectors.items()}
            deltas += [abs(a[k] - b[k]) * 100 for k in a]
            overlaps.append(len(_top10(a) & _top10(b)) / 10)
        out[label] = {
            "max": max(deltas),
            "mean": statistics.mean(deltas),
            "changed": sum(d > 0.005 for d in deltas) / len(deltas),
            "overlap": statistics.mean(overlaps),
        }
    return out


def name_group_audit(dataset: Dataset, raws: dict, gains: dict) -> tuple[dict, float]:
    """Score moyen par famille de noms, à pertinence égale (candidats de pertinence 3).

    Retourne aussi la p-value d'un test de permutation de l'écart maximal entre groupes : on
    redistribue au hasard les familles de noms ENTRE CANDIDATS (et non entre lignes, car un même
    candidat revient dans plusieurs offres) et on regarde à quelle fréquence le hasard seul produit un
    écart au moins aussi grand.
    """
    by_key = {c.key: c for c in dataset.candidates}
    rows: list[tuple[int, float]] = []  # (clé de candidat, score)
    for job in dataset.jobs:
        for key, raw in raws[job.key].items():
            if gains[job.key][key] == 3:
                rows.append((key, combine(raw, MatchingWeights().model_dump())))

    def spread(label_of: dict[int, int]) -> float:
        groups: dict[int, list[float]] = defaultdict(list)
        for key, score in rows:
            groups[label_of[key]].append(score)
        means = [statistics.mean(v) for v in groups.values()]
        return max(means) - min(means)

    involved = sorted({key for key, _ in rows})
    real = {key: by_key[key].name_pool for key in involved}
    observed = spread(real)
    rng = random.Random(5)
    labels = list(real.values())
    at_least_as_large = 0
    trials = 3000
    for _ in range(trials):
        rng.shuffle(labels)
        at_least_as_large += spread(dict(zip(involved, labels, strict=True))) >= observed

    groups_stats: dict[int, list[float]] = defaultdict(list)
    for key, score in rows:
        groups_stats[real[key]].append(score)
    stats = {g: (statistics.mean(v), len(v)) for g, v in sorted(groups_stats.items())}
    return stats, (at_least_as_large + 1) / (trials + 1)


def stuffing_effect(
    dataset: Dataset,
    raws: dict,
    gains: dict,
    perm: dict[int, int],
    variants: dict[str, dict[str, float]],
) -> dict:
    """Combien de places du top 10 sont prises par des CV qui ont gonflé leur liste de compétences."""
    stuffers = {c.key for c in dataset.candidates if c.stuffed}
    out = {}
    for name in (
        "Mots-clés seuls",
        "Sémantique seule",
        "Compétences seules",
        "Compétences + expérience",
        DEFAULT_NAME,
        WITH_SEMANTIC_NAME,
    ):
        if name not in variants:
            continue
        slots = 0
        for job in dataset.jobs:
            top = order(raws[job.key], variants[name], perm)[:10]
            slots += sum(1 for k in top if k in stuffers and gains[job.key][k] <= 1)
        out[name] = slots
    expected = len(stuffers) * 10 / len(dataset.candidates) * len(dataset.jobs)
    return {"count": len(stuffers), "slots": out, "random_expectation": expected}


# ------------------------------------------------------------------ rapport


def build_report(
    seed: int,
    dataset: Dataset,
    parsed: Parsed,
    profiles: list[JobProfile],
    results: dict,
    started: float,
) -> str:
    per_variant = results["per_variant"]
    jobs = dataset.jobs
    diag = diagnose(dataset, parsed, profiles)
    sensitivity = weight_sensitivity(
        dataset,
        results["raws"],
        results["gains"],
        results["permutations"][0],
        has_semantic=parsed.has_semantic,
    )
    language = language_effect(
        dataset,
        results["raws"],
        results["gains"],
        results["permutations"][0],
        results["by_key"],
        results["variants"],
    )
    twins = fairness(dataset, parsed, profiles, seed)
    groups, p_value = name_group_audit(dataset, results["raws"], results["gains"])
    stuffing = stuffing_effect(
        dataset, results["raws"], results["gains"], results["permutations"][0], results["variants"]
    )

    relevant_counts = [
        sum(1 for g in results["gains"][j.key].values() if g >= RELEVANT) for j in jobs
    ]
    grade3 = [sum(1 for g in results["gains"][j.key].values() if g == 3) for j in jobs]
    lines = [
        f"# Résultats d'évaluation du matching — graine {seed}",
        "",
        "> **À lire avant les chiffres.** Ce jeu est SYNTHÉTIQUE : candidats, offres et règle de pertinence",
        "> ont été écrits par la même personne (Claude). Aucun recruteur n'a jugé ces classements. Ces",
        "> résultats mesurent la cohérence du système avec une règle explicite sur des CV propres et",
        "> homogènes ; ils ne prédisent PAS la performance sur de vrais CV, qui sera inférieure.",
        "",
        "## Jeu de données",
        "",
        f"- Graine **{seed}** ; {len(dataset.candidates)} candidats (9 familles de métiers × {len(dataset.candidates) // 9}), "
        f"{len(jobs)} offres (9 mono-famille + 2 hybrides).",
        "- CV en français et en anglais (mélangés), PDF et DOCX, rendus en vrais fichiers puis relus par le pipeline.",
        "- Offres et CV de langues indépendantes : une partie des paires est inter-langues.",
        f"- Pertinence 0 à 3 calculée sur des attributs CACHÉS (voir `evaluation/generator.py::gold_grade`). "
        f"Par offre : {min(relevant_counts)}–{max(relevant_counts)} candidats pertinents (niveau ≥ 2), "
        f"{min(grade3)}–{max(grade3)} de niveau 3.",
        f"- {diag['invisible_share']:.0%} des compétences réellement possédées sont écrites avec un outil **absent du "
        f"référentiel** (invisibles pour le système, par construction).",
        f"- Durée du calcul : {time.perf_counter() - started:.0f} s. Égalités de score départagées au hasard, moyennées sur {PERMUTATIONS} tirages.",
        "",
        "## 1. Qualité du classement",
        "",
        f"Moyenne sur les {len(jobs)} offres, **[intervalle de confiance à 95 %]** par rééchantillonnage des offres "
        "(large, car il n'y a que 11 offres). Précision/rappel : pertinent = niveau ≥ 2.",
        "",
        "| Variante | P@5 | P@10 | R@10 | NDCG@10 | MRR |",
        "|---|---|---|---|---|---|",
    ]
    for name, series in per_variant.items():
        lines.append(
            f"| {name} | "
            + " | ".join(fmt_ci(series[m]) for m in ("P@5", "P@10", "R@10", "NDCG@10", "MRR"))
            + " |"
        )

    default = per_variant[DEFAULT_NAME]["NDCG@10"]
    lines += ["", "### Écart de NDCG@10 entre les poids par défaut et chaque autre variante", "",
              "| Variante comparée | Écart moyen (défaut − variante) | IC 95 % | Conclusion |", "|---|---|---|---|"]  # fmt: skip
    for name, series in per_variant.items():
        if name == DEFAULT_NAME:
            continue
        diff = paired_difference_ci(default, series["NDCG@10"], seed=3)
        if diff is None:
            continue
        mean, (low, high) = diff
        verdict = (
            "défaut meilleur" if low > 0 else "défaut moins bon" if high < 0 else "indécidable"
        )
        lines.append(f"| {name} | {mean:+.3f} | [{low:+.2f}, {high:+.2f}] | {verdict} |")

    lines += [
        "",
        "### Détail par offre (poids par défaut)",
        "",
        "| Offre | Langue | Pertinents | NDCG@10 | P@10 |",
        "|---|---|---|---|---|",
    ]
    for i, job in enumerate(jobs):
        lines.append(
            f"| {job.title} | {job.lang} | {relevant_counts[i]} | {fmt(default[i])} | {fmt(per_variant[DEFAULT_NAME]['P@10'][i])} |"
        )

    best = sensitivity["scores"][-1]
    lines += [
        "",
        "## 2. Sensibilité aux poids",
        "",
        f"400 jeux de poids tirés au hasard (loi de Dirichlet uniforme). NDCG@10 moyen : médiane "
        f"{sensitivity['scores'][len(sensitivity['scores']) // 2][0]:.3f}, minimum {sensitivity['scores'][0][0]:.3f}, "
        f"maximum {best[0]:.3f}. Poids par défaut : **{sensitivity['default']:.3f}**, soit mieux que "
        f"{sensitivity['percentile']:.0%} des tirages.",
        "",
        "Meilleurs poids trouvés : "
        + ", ".join(f"{c} {w:.2f}" for c, w in best[1].items())
        + ". **Ne pas adopter ces poids** : ils sont optimisés sur ces mêmes offres (surapprentissage garanti) "
        "et l'écart avec le défaut est à comparer à l'incertitude ci-dessus.",
        "",
        "## 3. Effet de la langue (rang moyen des candidats de pertinence 3, en % ; 0 % = tête)",
        "",
        "| Variante | Même langue offre/CV | Langues différentes |",
        "|---|---|---|",
    ]
    for name, buckets in language.items():
        same, cross = buckets["même langue"], buckets["langues différentes"]
        lines.append(
            f"| {name} | {fmt(same[0], 1)} (n={same[1]}) | {fmt(cross[0], 1)} (n={cross[1]}) |"
        )

    lines += [
        "",
        "## 4. Qualité de la lecture (comparée aux attributs cachés)",
        "",
        f"- Compétences détectables (hors outils hors référentiel) : précision **{diag['skill_precision']:.3f}**, rappel **{diag['skill_recall']:.3f}**.",
        f"- Complétude moyenne de l'extraction des CV : {diag['completeness']:.2f}.",
        f"- CV sans aucune expérience lue : {diag['no_experience']}/{len(dataset.candidates)} "
        f"(dont {diag['unknown_heading']} à cause d'un titre de rubrique non reconnu) ; échecs de lecture de fichier : {diag['failures']}.",
        f"- Analyse des offres, compétences requises : précision {diag['req_precision']:.3f}, rappel {diag['req_recall']:.3f} ; "
        f"optionnelles : précision {diag['opt_precision']:.3f}, rappel {diag['opt_recall']:.3f} ; "
        f"années d'expérience exactes : {diag['years_ok']}/{diag['jobs']}.",
        "",
        "## 5. Équité",
        "",
        "Chaque candidat est comparé à son « jumeau » (même CV, un seul élément changé). "
        "Δ = écart de score (sur 100) ; « top-10 conservé » = part du top 10 inchangée.",
        "",
        "| Élément modifié | Δ max | Δ moyen | Candidats dont le score change | Top-10 conservé |",
        "|---|---|---|---|---|",
    ]
    for label, r in twins.items():
        lines.append(
            f"| {label} | {r['max']:.2f} | {r['mean']:.3f} | {r['changed']:.0%} | {r['overlap']:.0%} |"
        )
    proxy = twins["proxys géographiques (villes des employeurs et de l'école)"]
    lines += [
        "",
        "Sensibilité aux proxys géographiques selon que l'offre cite une ville ou non : "
        f"offres citant une ville (n={proxy['city'][2]}) : Δ moyen {fmt(proxy['city'][0])}, top-10 conservé {fmt(proxy['city'][1], 2)} ; "
        f"offres sans ville (n={proxy['nocity'][2]}) : Δ moyen {fmt(proxy['nocity'][0])}, top-10 conservé {fmt(proxy['nocity'][1], 2)}.",
        "",
        "Score moyen (poids par défaut) par famille de noms, parmi les candidats de pertinence 3 uniquement "
        "(à pertinence égale) :",
        "",
        "| Famille de noms | Score moyen | Effectif |",
        "|---|---|---|",
    ]
    for group, (mean, count) in groups.items():
        lines.append(f"| {group + 1} | {mean:.2f} | {count} |")
    spread = max(m for m, _ in groups.values()) - min(m for m, _ in groups.values())
    verdict = (
        "compatible avec le simple hasard de l'échantillonnage" if p_value > 0.05
        else "PEU PROBABLE par hasard seul : à investiguer"
    )  # fmt: skip
    lines += [
        "",
        f"Écart maximal entre familles de noms : {spread:.2f} points. **Test de permutation** (3000 tirages, "
        f"familles de noms redistribuées entre candidats) : p = {p_value:.3f}, soit {verdict}. Les familles de noms "
        "sont attribuées au hasard dans ce jeu : un écart significatif ne pourrait venir que d'un biais direct. "
        "L'absence d'écart significatif ne dit RIEN sur les corrélations réelles entre origine et parcours "
        "(écoles, villes, trous de carrière…) : un test sur ce jeu n'a pas la puissance d'en détecter de petites.",
        "",
        "## 6. Bourrage de mots-clés",
        "",
        f"{stuffing['count']} CV listent, dans leur seule section « compétences », des compétences d'une famille "
        "éloignée qu'ils ne possèdent pas (aucune trace dans leurs expériences). Places du top 10 occupées, sur "
        f"l'ensemble des {len(jobs)} offres, par de tels CV de pertinence ≤ 1 (espérance au hasard : "
        f"{stuffing['random_expectation']:.1f}) :",
        "",
        "| Variante | Places occupées par des CV gonflés |",
        "|---|---|",
        *(f"| {name} | {slots} |" for name, slots in stuffing["slots"].items()),
        "",
        "## Limites de cette évaluation",
        "",
        "- Jeu, offres et règle de pertinence écrits par la même personne ; aucune validation par des recruteurs.",
        "- 11 offres seulement : les intervalles de confiance sont larges, des écarts modestes sont indécidables.",
        "- CV propres et homogènes (une colonne, rubriques standard) : la vraie difficulté est sous-estimée.",
        "- La pertinence de référence dépend des mêmes notions (compétences, années) que le moteur : un accord élevé est en partie attendu.",
        "- Le niveau d'études n'entre pas dans la règle de pertinence mais entre dans le score du moteur.",
        "- L'audit d'équité ne teste que les éléments qu'on a pensé à faire varier.",
        "",
    ]
    return "\n".join(lines)


def _embedder(kind: str) -> Embedder | None:
    if kind == "none":
        return None
    settings = Settings(
        postgres_password="x",  # type: ignore[arg-type]
        jwt_secret_key="x",  # type: ignore[arg-type]
        embedding_provider=kind,  # type: ignore[arg-type]
    )
    return build_embedder(settings)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--per-family", type=int, default=14)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--embedder",
        choices=("none", "hashing", "sentence_transformers"),
        default="none",
        help="none : évaluation de la Phase 5 telle quelle ; sentence_transformers : modèle réel.",
    )
    args = parser.parse_args()

    embedder = _embedder(args.embedder)
    started = time.perf_counter()
    dataset = build_dataset(args.seed, args.per_family)
    parsed = parse_pool({c.key: c.cv for c in dataset.candidates}, embedder)
    profiles = [analyze_job(j.title, j.description) for j in dataset.jobs]
    results = evaluate(dataset, parsed, profiles, args.seed, embedder)
    results["embedder"] = embedder.name if embedder else None
    report = build_report(args.seed, dataset, parsed, profiles, results, started)
    if embedder is not None:
        from evaluation.search_eval import evaluate_search, search_report

        report += "\n" + search_report(evaluate_search(dataset, parsed, embedder), embedder.name)
        fair = semantic_fairness(dataset, parsed, profiles, embedder, args.seed)
        report += "\n## 8. Équité de la composante sémantique\n\n"
        report += (
            "Même méthode que la section 5 (jumeaux), appliquée au score sémantique (0 à 100) "
            "des 126 candidats pour les 11 offres.\n\n"
            "| Élément modifié | Δ max | Δ moyen | Scores qui changent | Top-10 conservé |\n"
            "|---|---|---|---|---|\n"
        )
        for label, r in fair.items():
            report += (
                f"| {label} | {r['max']:.2f} | {r['mean']:.3f} | {r['changed']:.0%} | "
                f"{r['overlap']:.0%} |\n"
            )
        report += (
            "\nLes écoles et les villes restent dans les passages vectorisés : un modèle "
            "d'embedding peut y encoder un prestige ou une origine. Ce test ne mesure que la "
            "sensibilité à des changements de ville ; il ne dit rien des corrélations réelles.\n"
        )
    if args.output:
        args.output.write_text(report, encoding="utf-8", newline="\n")
        print(f"Rapport écrit : {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
