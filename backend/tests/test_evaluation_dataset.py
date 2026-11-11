"""Le banc d'évaluation lui-même : générateur, règle de pertinence, jumeaux, exécution complète.

Un banc d'essai faux donnerait des chiffres faux avec une apparence de rigueur : on le teste donc
comme du code de production.
"""

import dataclasses
import random
import re

import pytest

from app.modules.candidates.parsing.skills import canonical_skill_name
from app.modules.documents.extraction import detect_kind, extract_text
from app.modules.jobs.parsing import analyze_job
from evaluation.families import ADJACENT, FAMILIES, SURFACE, are_adjacent, surface
from evaluation.generator import (
    CITIES,
    LANGUAGE_LINES,
    NAME_POOLS,
    CandidateSpec,
    JobSpec,
    build_dataset,
    gold_grade,
    twin_gender_titles,
    twin_identity,
    twin_proxies,
)
from evaluation.run import (
    DEFAULT_NAME,
    build_report,
    combine,
    evaluate,
    metrics_for,
    parse_pool,
)
from tests.cv_factory import render

SMALL = 3  # candidats par famille dans les tests (rapide)


@pytest.fixture(scope="module")
def dataset():
    return build_dataset(1, per_family=SMALL)


# ------------------------------------------------------------------ référentiel et familles


def test_every_core_and_extra_skill_exists_in_the_taxonomy() -> None:
    for family in FAMILIES.values():
        for skill in (*family.core, *family.extras):
            assert canonical_skill_name(skill) == skill, (family.name, skill)


def test_every_alternative_spelling_resolves_to_its_canonical_skill() -> None:
    for canonical, forms in SURFACE.items():
        for form in forms:
            assert canonical_skill_name(form) == canonical, (canonical, form)


def test_off_taxonomy_tools_are_really_invisible_to_the_system() -> None:
    """Sinon « outil hors référentiel » serait une fausse promesse et le rappel serait surestimé."""
    for family in FAMILIES.values():
        for tool in family.offtax:
            assert canonical_skill_name(tool) is None, (family.name, tool)


def test_mission_topics_contain_no_taxonomy_skill() -> None:
    """Sinon l'analyse d'offre lirait un thème de mission comme une exigence inatteignable."""
    from app.modules.candidates.parsing.skills import find_skills_in_text

    for family in FAMILIES.values():
        for topic in (*family.topics_en, *family.topics_fr):
            assert find_skills_in_text(topic, mode="listing") == [], (family.name, topic)


def test_adjacency_is_symmetric_and_refers_to_existing_families() -> None:
    assert are_adjacent("devops", "backend_python") and are_adjacent("backend_python", "devops")
    assert not are_adjacent("marketing", "devops")
    for pair in ADJACENT:
        assert pair <= set(FAMILIES)


def test_surface_form_selection_is_deterministic_and_covers_variants() -> None:
    assert surface("Kubernetes", 0.0) == "Kubernetes" and surface("Kubernetes", 0.99) == "K8s"
    assert surface("Python", 0.7) == "Python"  # pas de variante : toujours le nom


# ------------------------------------------------------------------ générateur


def test_dataset_is_deterministic_for_a_given_seed(dataset) -> None:
    again = build_dataset(1, per_family=SMALL)

    assert [(c.family, c.held, c.cv.name, c.cv.jobs) for c in dataset.candidates] == [
        (c.family, c.held, c.cv.name, c.cv.jobs) for c in again.candidates
    ]
    assert [j.description for j in dataset.jobs] == [j.description for j in again.jobs]


def test_different_seeds_give_different_datasets(dataset) -> None:
    other = build_dataset(2, per_family=SMALL)

    assert [c.cv.name for c in dataset.candidates] != [c.cv.name for c in other.candidates]


def test_dataset_shape(dataset) -> None:
    assert len(dataset.candidates) == 9 * SMALL
    assert len(dataset.jobs) == 11
    assert {c.family for c in dataset.candidates} == set(FAMILIES)
    assert sum(1 for j in dataset.jobs if len(j.targets) == 2) == 2  # offres hybrides
    assert {c.lang for c in build_dataset(1, per_family=14).candidates} == {"fr", "en"}


def test_synthetic_identities_are_clearly_fictional(dataset) -> None:
    for c in dataset.candidates:
        assert c.cv.email.endswith("@example.com")
        assert c.cv.link.endswith("-demo")


def test_held_skills_belong_to_the_candidates_world(dataset) -> None:
    for c in dataset.candidates:
        family = FAMILIES[c.family]
        assert c.held & set(family.core), "au moins une compétence de base"
        assert c.substituted <= c.held
        assert c.substituted <= set(family.core)


def test_substituted_skills_do_not_appear_under_their_real_name(dataset) -> None:
    for c in (c for c in dataset.candidates if c.substituted):
        text = " ".join(c.cv.skills[i][1] for i in range(len(c.cv.skills)))
        text += " ".join(b for j in c.cv.jobs for b in j.bullets)
        for skill in c.substituted:
            # La compétence réelle est cachée derrière l'outil (« Dataiku »), variantes comprises.
            assert not any(
                re.search(rf"\b{re.escape(f)}\b", text) for f in SURFACE.get(skill, (skill,))
            ), (
                c.cv.slug,
                skill,
            )


def test_stuffed_skills_are_listed_but_not_held() -> None:
    dataset = build_dataset(1, per_family=14)
    stuffers = [c for c in dataset.candidates if c.stuffed]

    assert 3 <= len(stuffers) <= 25
    for c in stuffers:
        listed = " ".join(line for _, line in c.cv.skills)
        assert listed  # le bourrage est visible dans la section compétences
        experience = " ".join(b for j in c.cv.jobs for b in j.bullets)
        assert experience  # mais l'expérience ne le soutient pas : voir ci-dessous
        foreign = [s for f in FAMILIES.values() for s in f.core if f.name != c.family]

        def mentions(text: str, skill: str) -> bool:
            # Mot entier : « R » ne doit pas être trouvé dans n'importe quel mot.
            return any(
                re.search(rf"(?<![\w+#.]){re.escape(form)}(?![\w+#])", text)
                for form in SURFACE.get(skill, (skill,))
            )

        stuffed_in_skills = [s for s in foreign if mentions(listed, s) and s not in c.held]
        assert stuffed_in_skills, c.cv.slug
        assert not any(mentions(experience, s) for s in stuffed_in_skills), c.cv.slug


def test_cv_text_never_leaks_the_hidden_labels(dataset) -> None:
    for c in dataset.candidates[:6]:
        content = render(c.cv)
        text = extract_text(content, detect_kind(c.cv.filename, content, 5_000_000), 30).text
        for label in ("data_scientist", "ml_engineer", "backend_java", "held", "gold", "stuffed"):
            assert label not in text


def test_generated_cvs_are_readable_by_the_real_pipeline(dataset) -> None:
    parsed = parse_pool({c.key: c.cv for c in dataset.candidates})

    assert parsed.failures == 0
    names = sum(parsed.profiles[c.key].full_name == c.cv.name for c in dataset.candidates)
    assert names / len(dataset.candidates) >= 0.9


def test_generated_job_requirements_are_recovered_by_the_job_analysis(dataset) -> None:
    for job in dataset.jobs:
        profile = analyze_job(job.title, job.description)
        assert set(job.required_true) <= set(profile.required_skills), job.title
        assert profile.min_experience_years == job.min_years
        assert set(job.optional_true) <= set(profile.optional_skills)


def test_analysis_finds_no_skill_outside_the_true_lists(dataset) -> None:
    """Couvre aussi le piège de la section « avantages » (une compétence citée comme formation)."""
    for job in dataset.jobs:
        profile = analyze_job(job.title, job.description)
        extra = (set(profile.required_skills) | set(profile.optional_skills)) - (
            set(job.required_true) | set(job.optional_true)
        )
        assert not extra, (job.title, extra)


# ------------------------------------------------------------------ règle de pertinence


def _candidate(dataset, family: str) -> CandidateSpec:
    return next(c for c in dataset.candidates if c.family == family)


def _job(targets: tuple[str, ...], required: tuple[str, ...], years: int = 3) -> JobSpec:
    return JobSpec(0, "Poste", "", "fr", frozenset(targets), required, (), years, None)


REQUIRED = ("Python", "SQL", "Docker", "Git")


@pytest.mark.parametrize(
    ("family", "held", "years", "targets", "expected"),
    [
        ("data_scientist", REQUIRED, 5, ("data_scientist",), 3),  # tout, assez d'expérience
        ("data_scientist", REQUIRED, 1, ("data_scientist",), 2),  # tout, pas assez d'années
        ("data_scientist", REQUIRED[:2], 5, ("data_scientist",), 2),  # 50 %
        ("data_scientist", REQUIRED[:1], 5, ("data_scientist",), 1),  # 25 % mais même famille
        ("data_scientist", (), 5, ("data_scientist",), 1),  # rien mais même famille : plancher 1
        ("ml_engineer", REQUIRED, 5, ("data_scientist",), 2),  # voisine : plafonnée à 2
        ("ml_engineer", (), 5, ("data_scientist",), 1),  # voisine : plancher 1
        ("marketing", REQUIRED, 5, ("data_scientist",), 1),  # sans rapport : plafonnée à 1
        ("marketing", (), 5, ("data_scientist",), 0),
        ("marketing", REQUIRED, 5, ("data_scientist", "marketing"), 3),  # offre hybride
    ],
)
def test_gold_rubric(
    dataset, family: str, held: tuple, years: int, targets: tuple, expected: int
) -> None:
    candidate = dataclasses.replace(_candidate(dataset, family), held=frozenset(held), years=years)

    assert gold_grade(candidate, _job(targets, REQUIRED)) == expected


def test_gold_depends_only_on_hidden_attributes_not_on_the_cv_text(dataset) -> None:
    candidate = _candidate(dataset, "devops")
    job = _job(("devops",), tuple(sorted(candidate.held))[:3])
    scrambled = dataclasses.replace(
        candidate, cv=dataclasses.replace(candidate.cv, summary="texte sans rapport", skills=())
    )

    assert gold_grade(candidate, job) == gold_grade(scrambled, job)


# ------------------------------------------------------------------ jumeaux


def test_identity_twin_changes_only_identity(dataset) -> None:
    c = dataset.candidates[0]
    twin = twin_identity(c, random.Random(0))

    assert (twin.name, twin.email, twin.phone, twin.link) != (
        c.cv.name,
        c.cv.email,
        c.cv.phone,
        c.cv.link,
    )
    assert twin.languages != c.cv.languages and twin.languages in LANGUAGE_LINES
    assert twin.headline == "Profil confidentiel"
    assert (twin.jobs, twin.skills, twin.education, twin.summary) == (
        c.cv.jobs,
        c.cv.skills,
        c.cv.education,
        c.cv.summary,
    )


def test_identity_twin_uses_a_different_name_pool(dataset) -> None:
    for c in dataset.candidates[:10]:
        twin = twin_identity(c, random.Random(c.key))
        first_names = {first for pool in NAME_POOLS for first in pool[0]}
        assert twin.name.split()[0] in first_names
        assert twin.name.split()[0] not in NAME_POOLS[c.name_pool][0]


def test_gender_twin_changes_only_job_titles(dataset) -> None:
    french = next(c.cv for c in dataset.candidates if c.lang == "fr" and c.family == "devops")
    twin = twin_gender_titles(french)

    assert [j.title for j in twin.jobs] != [j.title for j in french.jobs] or all(
        "Ingénieur" not in j.title and "Administrateur" not in j.title for j in french.jobs
    )
    assert [(j.company, j.location, j.period, j.bullets) for j in twin.jobs] == [
        (j.company, j.location, j.period, j.bullets) for j in french.jobs
    ]
    assert twin.skills == french.skills


def test_proxy_twin_changes_only_places(dataset) -> None:
    c = dataset.candidates[0].cv
    twin = twin_proxies(c)

    assert [j.location for j in twin.jobs] != [j.location for j in c.jobs]
    assert all(j.location in CITIES for j in twin.jobs)
    assert [(j.title, j.company, j.period, j.bullets) for j in twin.jobs] == [
        (j.title, j.company, j.period, j.bullets) for j in c.jobs
    ]
    assert twin.skills == c.skills and twin.name == c.name


# ------------------------------------------------------------------ exécution complète (petit jeu)


def test_full_evaluation_runs_and_beats_chance() -> None:
    import time

    dataset = build_dataset(1, per_family=SMALL)
    parsed = parse_pool({c.key: c.cv for c in dataset.candidates})
    profiles = [analyze_job(j.title, j.description) for j in dataset.jobs]

    results = evaluate(dataset, parsed, profiles, seed=1)
    ndcg = results["per_variant"][DEFAULT_NAME]["NDCG@10"]
    chance = results["per_variant"]["Aléatoire (espérance)"]["NDCG@10"]

    assert len(ndcg) == len(dataset.jobs)
    assert sum(v for v in ndcg if v is not None) / len(ndcg) > sum(
        v for v in chance if v is not None
    ) / len(chance)

    report = build_report(1, dataset, parsed, profiles, results, time.perf_counter())
    for heading in (
        "## 1. Qualité du classement",
        "## 2. Sensibilité aux poids",
        "## 5. Équité",
        "## 6. Bourrage",
        "Limites de cette évaluation",
    ):
        assert heading in report
    assert "SYNTHÉTIQUE" in report and "ne prédisent PAS" in report


def test_recombination_matches_the_real_engine_scores() -> None:
    """L'évaluation recombine les composantes pour tester d'autres poids : elle doit retomber sur
    le score réel du moteur avec les poids par défaut."""
    from app.modules.matching.engine import rank
    from app.modules.matching.weights import MatchingWeights
    from evaluation.generator import TODAY

    dataset = build_dataset(1, per_family=SMALL)
    parsed = parse_pool({c.key: c.cv for c in dataset.candidates})
    job = dataset.jobs[0]
    profile = analyze_job(job.title, job.description)

    results = rank(
        profile,
        f"{job.title}\n{job.description}",
        list(parsed.inputs.values()),
        MatchingWeights(),
        today=TODAY,
    )

    for r in results:
        raw = {c.name: c.raw_score for c in r.components}
        assert combine(raw, MatchingWeights().model_dump()) == pytest.approx(r.score, abs=0.011)


def test_metrics_for_uses_the_gold_gain_of_each_ranked_candidate() -> None:
    gains = {1: 3, 2: 0, 3: 2, 4: 0}

    perfect = metrics_for([1, 3, 2, 4], gains)
    reversed_ = metrics_for([2, 4, 3, 1], gains)

    assert perfect["NDCG@10"] == pytest.approx(1.0)
    assert reversed_["NDCG@10"] < perfect["NDCG@10"]
    assert perfect["P@5"] == pytest.approx(2 / 5)
