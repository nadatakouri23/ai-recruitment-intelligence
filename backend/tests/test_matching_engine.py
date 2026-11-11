"""Moteur de classement sur de vrais fichiers PDF/DOCX et des offres synthétiques.

Les « bonnes réponses » (quel CV correspond à quelle offre) sont écrites à la main par la même
personne que les CV et les offres : ces tests sont des garde-fous contre les régressions, PAS une
mesure de la qualité du matching sur de vraies données (voir docs/evaluation/matching.md).
"""

import dataclasses
import itertools
import math
from datetime import date

import pytest

from app.modules.candidates.parsing.parser import parse_cv
from app.modules.candidates.parsing.text_cleaning import clean_text
from app.modules.documents.extraction import detect_kind, extract_text
from app.modules.jobs.parsing import analyze_job
from app.modules.jobs.profile import JobProfile
from app.modules.matching.engine import CandidateInput
from app.modules.matching.engine import rank as _rank
from app.modules.matching.schemas import MatchResult
from app.modules.matching.text import anonymized_cv_text
from app.modules.matching.tfidf import tfidf_similarities
from app.modules.matching.weights import MatchingWeights
from tests.cv_factory import SYNTHETIC_CVS, SyntheticCV, render
from tests.job_factory import SYNTHETIC_JOBS, SyntheticJob

TODAY = date(2026, 11, 11)
DEFAULT = MatchingWeights()
CV_BY_SLUG = {cv.slug: cv for cv in SYNTHETIC_CVS}


def rank(*args, **kwargs):
    """`rank` avec une date fixe : les postes « en cours » donnent des résultats reproductibles."""
    return _rank(*args, today=TODAY, **kwargs)


def candidate_input(cv: SyntheticCV, candidate_id: int) -> CandidateInput:
    content = render(cv)
    kind = detect_kind(cv.filename, content, 5 * 1024 * 1024)
    text = clean_text(extract_text(content, kind, max_pages=30).text)
    return CandidateInput(candidate_id, parse_cv(text, today=TODAY), anonymized_cv_text(text))


def job_inputs(job: SyntheticJob) -> tuple[JobProfile, str]:
    return analyze_job(job.title, job.description), f"{job.title}\n{job.description}"


@pytest.fixture(scope="module")
def pool() -> dict[str, CandidateInput]:
    """Les 6 CV, par slug (identifiants 1 à 6)."""
    return {cv.slug: candidate_input(cv, i) for i, cv in enumerate(SYNTHETIC_CVS, start=1)}


def slug_of(result: MatchResult, pool: dict[str, CandidateInput]) -> str:
    return next(slug for slug, c in pool.items() if c.candidate_id == result.candidate.id)


def run(job: SyntheticJob, pool: dict[str, CandidateInput], weights: MatchingWeights = DEFAULT):
    profile, text = job_inputs(job)
    return rank(profile, text, list(pool.values()), weights)


# ------------------------------------------------------------------ classement de bon sens


@pytest.mark.parametrize("job", SYNTHETIC_JOBS, ids=lambda j: j.slug)
def test_relevant_cvs_are_ranked_first(job: SyntheticJob, pool: dict[str, CandidateInput]) -> None:
    results = run(job, pool)

    top = {slug_of(r, pool) for r in results[: len(job.relevant)]}
    assert top == set(job.relevant), [
        (slug_of(r, pool), r.score) for r in results
    ]  # affiche le classement complet en cas d'échec


def test_irrelevant_candidates_score_clearly_lower(pool: dict[str, CandidateInput]) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "devops_fr")
    results = run(job, pool)

    best, second = results[0], results[1]
    assert best.score - second.score > 15


# ------------------------------------------------------------------ intégrité du score


@pytest.mark.parametrize("job", SYNTHETIC_JOBS, ids=lambda j: j.slug)
def test_contributions_add_up_to_the_score(
    job: SyntheticJob, pool: dict[str, CandidateInput]
) -> None:
    for result in run(job, pool):
        assert 0 <= result.score <= 100
        assert sum(c.contribution for c in result.components) == pytest.approx(
            result.score, abs=0.05
        )
        # Les poids effectifs des composantes évaluées forment un tout.
        assert sum(c.effective_weight for c in result.components) == pytest.approx(1, abs=0.001)
        assert [c.name for c in result.components] == [
            "skills", "experience", "education", "tfidf", "keyword", "semantic"
        ]  # fmt: skip
        # Sans embeddings (cas par défaut), la composante sémantique est non évaluée et sans poids.
        semantic = result.components[-1]
        assert semantic.raw_score is None and semantic.effective_weight == 0


def test_ranks_are_sequential_and_scores_non_increasing(pool: dict[str, CandidateInput]) -> None:
    results = run(SYNTHETIC_JOBS[0], pool)

    assert [r.rank for r in results] == list(range(1, len(pool) + 1))
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_ranking_is_deterministic_and_independent_of_input_order(
    pool: dict[str, CandidateInput],
) -> None:
    profile, text = job_inputs(SYNTHETIC_JOBS[0])
    inputs = list(pool.values())

    reference = rank(profile, text, inputs, DEFAULT)
    assert rank(profile, text, inputs, DEFAULT) == reference
    for permutation in itertools.islice(itertools.permutations(inputs), 12):
        shuffled = rank(profile, text, list(permutation), DEFAULT)
        assert [(r.candidate.id, r.score) for r in shuffled] == [
            (r.candidate.id, r.score) for r in reference
        ]


def test_empty_pool_gives_an_empty_ranking() -> None:
    profile, text = job_inputs(SYNTHETIC_JOBS[0])

    assert rank(profile, text, [], DEFAULT) == []


def test_single_candidate_pool_works(pool: dict[str, CandidateInput]) -> None:
    profile, text = job_inputs(SYNTHETIC_JOBS[0])

    (result,) = rank(profile, text, [pool["fr_data_scientist"]], DEFAULT)

    assert result.rank == 1 and 0 < result.score <= 100


# ------------------------------------------------------------------ transparence des détails


def test_matched_and_missing_skills_are_exact(pool: dict[str, CandidateInput]) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "data_scientist_fr")
    result = next(r for r in run(job, pool) if slug_of(r, pool) == "fr_data_scientist")

    # Le CV de Sofia n'a ni « Data Science » (mot jamais écrit tel quel) ni rien d'autre à signaler.
    assert set(result.skills.matched_required) | set(result.skills.missing_required) == set(
        job.required
    )
    assert set(result.skills.matched_optional) | set(result.skills.missing_optional) == set(
        job.optional
    )
    assert {"NLP", "Python", "PyTorch", "SQL", "Docker"} <= set(result.skills.matched_required)
    assert {"LangChain", "pgvector", "AWS"} == set(result.skills.matched_optional)


def test_missing_required_skills_are_listed_for_a_weaker_candidate(
    pool: dict[str, CandidateInput],
) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "devops_fr")
    result = next(r for r in run(job, pool) if slug_of(r, pool) == "fr_marketing")

    assert result.skills.matched_required == []
    assert set(result.skills.missing_required) == set(job.required)
    assert result.score < 20


def test_skill_evidence_comes_from_the_cv_body_not_the_header(
    pool: dict[str, CandidateInput],
) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "backend_en")
    result = next(r for r in run(job, pool) if slug_of(r, pool) == "en_backend_engineer")

    assert result.skills.evidence
    for skill, snippet in result.skills.evidence.items():
        assert snippet and "@" not in snippet and "Whitfield" not in snippet, skill


def test_relevant_experience_lists_jobs_sharing_required_skills(
    pool: dict[str, CandidateInput],
) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "backend_en")
    result = next(r for r in run(job, pool) if slug_of(r, pool) == "en_backend_engineer")

    first = result.relevant_experience[0]
    assert first.title == "Senior Backend Engineer"
    assert {"Java", "Kubernetes"} <= set(first.matching_skills)


def test_explanations_are_concrete(pool: dict[str, CandidateInput]) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "data_scientist_fr")
    result = next(r for r in run(job, pool) if slug_of(r, pool) == "fr_data_scientist")
    text = " ".join(result.explanations)

    assert "Compétences requises :" in text and "sur 9 trouvées" in text
    assert "Expérience pertinente : 8 ans 3 mois" in text and "3 an(s) demandé(s)" in text
    assert "Niveau d'études : Bac+5 (master) détecté pour Bac+5 (master) demandé" in text
    assert "TF-IDF" in text and "synonymes" in text


# ------------------------------------------------------------------ expérience PERTINENTE


def experience_component(result: MatchResult):
    return next(c for c in result.components if c.name == "experience")


def test_unrelated_experience_does_not_earn_points(pool: dict[str, CandidateInput]) -> None:
    """Onze ans de marketing ne valent rien pour un poste DevOps (défaut corrigé en Phase 4)."""
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "devops_fr")
    result = next(r for r in run(job, pool) if slug_of(r, pool) == "fr_marketing")

    assert experience_component(result).raw_score == 0
    assert result.score < 20


def test_relevant_experience_merges_overlaps_and_ignores_unrelated_jobs(
    pool: dict[str, CandidateInput],
) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "data_scientist_fr")
    result = next(r for r in run(job, pool) if slug_of(r, pool) == "en_ml_engineer")
    text = " ".join(result.explanations)

    # Machine Learning Engineer (Mars 2021 → aujourd'hui) + Research Engineer (chevauche) = 69 mois ;
    # le poste de Data Engineer (ETL, Spark…) ne mobilise aucune compétence de l'offre.
    assert "Expérience pertinente : 5 ans 9 mois" in text
    assert "expérience totale lue : 7 ans 5 mois" in text


def test_offer_without_skills_falls_back_to_total_experience(
    pool: dict[str, CandidateInput],
) -> None:
    vague = analyze_job(
        "Poste", "5 ans d'expérience requis. " + "Nous cherchons une personne motivée. " * 6
    )
    assert not vague.required_skills and not vague.optional_skills

    (result,) = rank(vague, "Poste", [pool["fr_marketing"]], DEFAULT)

    assert experience_component(result).raw_score == 1.0
    assert "expérience totale utilisée" in experience_component(result).note
    assert any("Expérience totale" in line for line in result.explanations)


# ------------------------------------------------------------------ composantes non évaluables


def test_components_without_data_are_excluded_not_counted_as_zero(
    pool: dict[str, CandidateInput],
) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "analyst_en")  # pas de niveau d'études exigé
    result = run(job, pool)[0]
    by_name = {c.name: c for c in result.components}

    assert by_name["education"].raw_score is None
    assert by_name["education"].effective_weight == 0
    assert "n'exige pas de niveau" in by_name["education"].note
    assert sum(c.effective_weight for c in result.components) == pytest.approx(1, abs=0.001)


def test_unreadable_experience_is_not_treated_as_zero(pool: dict[str, CandidateInput]) -> None:
    profile, text = job_inputs(next(j for j in SYNTHETIC_JOBS if j.slug == "backend_en"))
    candidate = pool["en_backend_engineer"]
    blind = dataclasses.replace(
        candidate, profile=candidate.profile.model_copy(update={"total_experience_months": None})
    )

    (result,) = rank(profile, text, [blind], DEFAULT)
    experience = next(c for c in result.components if c.name == "experience")

    assert experience.raw_score is None and experience.effective_weight == 0
    assert "limite de la lecture" in experience.note
    assert any("Composantes non évaluées" in reason for reason in result.confidence.reasons)


def test_candidate_without_usable_text_gets_a_warning(pool: dict[str, CandidateInput]) -> None:
    profile, text = job_inputs(SYNTHETIC_JOBS[0])
    empty = dataclasses.replace(pool["fr_marketing"], text="")

    (result,) = rank(profile, text, [empty], DEFAULT)

    assert any("Aucun contenu exploitable" in w for w in result.warnings)
    assert next(c for c in result.components if c.name == "tfidf").raw_score is None


# ------------------------------------------------------------------ poids configurables


def test_weights_change_the_score_as_expected(pool: dict[str, CandidateInput]) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "data_scientist_fr")
    skills_only = MatchingWeights(skills=1, experience=0, tfidf=0, keyword=0, education=0)
    results = run(job, pool, skills_only)

    for result in results:
        skills = next(c for c in result.components if c.name == "skills")
        assert result.score == pytest.approx(100 * (skills.raw_score or 0), abs=0.05)
        ignored = next(c for c in result.components if c.name == "tfidf")
        assert (
            ignored.effective_weight == 0 and ignored.raw_score is not None
        )  # affiché, sans effet
        assert "Poids à 0" in ignored.note


def test_only_the_ratio_between_weights_matters(pool: dict[str, CandidateInput]) -> None:
    job = SYNTHETIC_JOBS[0]
    small = MatchingWeights(skills=0.45, experience=0.2, tfidf=0.2, keyword=0.1, education=0.05)
    large = MatchingWeights(skills=45, experience=20, tfidf=20, keyword=10, education=5)

    assert run(job, pool, small) == run(job, pool, large)


def test_different_weights_can_reorder_candidates(pool: dict[str, CandidateInput]) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "data_scientist_fr")
    by_skills = [
        slug_of(r, pool)
        for r in run(
            job, pool, MatchingWeights(skills=1, experience=0, tfidf=0, keyword=0, education=0)
        )
    ]
    by_text = [
        slug_of(r, pool)
        for r in run(
            job, pool, MatchingWeights(skills=0, experience=0, tfidf=1, keyword=0, education=0)
        )
    ]

    assert by_skills != by_text  # les poids ne sont pas décoratifs


def test_no_evaluable_component_gives_zero_with_a_warning(pool: dict[str, CandidateInput]) -> None:
    profile, text = job_inputs(next(j for j in SYNTHETIC_JOBS if j.slug == "analyst_en"))
    only_education = MatchingWeights(skills=0, experience=0, tfidf=0, keyword=0, education=1)

    results = rank(profile, text, list(pool.values()), only_education)

    assert all(r.score == 0 for r in results)
    assert all(any("Aucune composante évaluable" in w for w in r.warnings) for r in results)


# ------------------------------------------------------------------ confiance


def test_confidence_reflects_data_quality(pool: dict[str, CandidateInput]) -> None:
    job = next(j for j in SYNTHETIC_JOBS if j.slug == "data_scientist_fr")
    good = next(r for r in run(job, pool) if slug_of(r, pool) == "fr_data_scientist")
    poor_profile = parse_cv("lorem ipsum dolor sit amet", today=TODAY)
    poor = CandidateInput(99, poor_profile, "lorem ipsum dolor sit amet")
    profile, text = job_inputs(job)
    (poor_result,) = rank(profile, text, [poor], DEFAULT)

    assert good.confidence.level == "high"
    assert poor_result.confidence.level == "low"
    assert poor_result.confidence.reasons
    assert any("incomplète" in w for w in poor_result.warnings)


def test_vague_job_lowers_confidence(pool: dict[str, CandidateInput]) -> None:
    vague = analyze_job(
        "Poste", "Nous cherchons une personne motivée pour rejoindre notre équipe. " * 5
    )

    (result,) = rank(vague, "Poste", [pool["fr_data_scientist"]], DEFAULT)

    assert result.confidence.level != "high"
    assert any("Offre peu structurée" in r for r in result.confidence.reasons)


# ------------------------------------------------------------------ ÉQUITÉ : contre-exemples


def score_signature(result: MatchResult) -> tuple:
    """Tout ce que le calcul produit, hors identité d'affichage."""
    return (
        result.score,
        [(c.name, c.raw_score, c.effective_weight, c.contribution) for c in result.components],
        result.skills.matched_required,
        result.skills.missing_required,
        [(e.title, e.duration_months) for e in result.relevant_experience],
    )


@pytest.mark.parametrize("job", SYNTHETIC_JOBS, ids=lambda j: j.slug)
def test_changing_name_and_contacts_does_not_change_the_score(job: SyntheticJob) -> None:
    original = CV_BY_SLUG["fr_data_scientist"]
    twin = dataclasses.replace(
        original,
        name="Jean-Baptiste Kowalski",
        email="jb.kowalski@example.org",
        phone="+48 22 123 45 67",
        link="github.com/jbk-demo",
        headline="Titre tout à fait différent",
    )
    profile, text = job_inputs(job)

    (a,) = rank(profile, text, [candidate_input(original, 1)], DEFAULT)
    (b,) = rank(profile, text, [candidate_input(twin, 1)], DEFAULT)

    assert score_signature(a) == score_signature(b)


def test_spoken_languages_do_not_change_the_score() -> None:
    original = CV_BY_SLUG["fr_data_scientist"]
    other_languages = dataclasses.replace(
        original, languages="Arabe (natif), Mandarin (C1), Hindi (B2)"
    )
    profile, text = job_inputs(SYNTHETIC_JOBS[0])

    (a,) = rank(profile, text, [candidate_input(original, 1)], DEFAULT)
    (b,) = rank(profile, text, [candidate_input(other_languages, 1)], DEFAULT)

    assert score_signature(a) == score_signature(b)


def test_feminine_and_masculine_job_titles_score_the_same() -> None:
    original = CV_BY_SLUG["fr_data_scientist"]  # « Ingénieure Machine Learning »
    jobs = tuple(
        dataclasses.replace(j, title=j.title.replace("Ingénieure", "Ingénieur"))
        for j in original.jobs
    )
    masculine = dataclasses.replace(original, jobs=jobs)
    profile, text = job_inputs(SYNTHETIC_JOBS[0])

    (a,) = rank(profile, text, [candidate_input(original, 1)], DEFAULT)
    (b,) = rank(profile, text, [candidate_input(masculine, 1)], DEFAULT)

    assert any("Ingénieure" in j.title for j in original.jobs)
    tfidf_a = next(c for c in a.components if c.name == "tfidf").raw_score
    tfidf_b = next(c for c in b.components if c.name == "tfidf").raw_score
    assert tfidf_a == tfidf_b and a.score == b.score


def test_anonymized_text_given_to_the_engine_never_contains_identity(
    pool: dict[str, CandidateInput],
) -> None:
    for cv in SYNTHETIC_CVS:
        text = pool[cv.slug].text
        for secret in (cv.name, cv.email, cv.phone, cv.link, cv.name.split()[0]):
            assert secret not in text, (cv.slug, secret)


# ------------------------------------------------------------------ TF-IDF


def test_tfidf_identical_texts_are_maximally_similar_and_disjoint_texts_score_zero() -> None:
    same, different = tfidf_similarities(
        "python docker sql", ["python docker sql", "marketing seo"]
    )

    assert same == pytest.approx(1.0)
    assert different == 0.0


def test_tfidf_empty_vocabulary_does_not_crash() -> None:
    assert tfidf_similarities("le la les", ["de du des"]) == [0.0]
    assert tfidf_similarities("python", []) == []


def test_tfidf_matches_scikit_learn() -> None:
    """Équivalence avec TfidfVectorizer (même formule). Ignoré si scikit-learn est absent."""
    sklearn_text = pytest.importorskip("sklearn.feature_extraction.text")
    from app.modules.matching.text import analyzer

    job = "Data scientist python pytorch sql docker déploiement modèles langage naturel"
    cvs = [
        "Python SQL et Docker pour déployer des modèles de langage",
        "Marketing digital SEO Google Analytics gestion de projet",
        "Python pandas numpy analyse de données SQL",
    ]
    matrix = sklearn_text.TfidfVectorizer(analyzer=analyzer, sublinear_tf=True).fit_transform(
        [job, *cvs]
    )
    expected = (matrix[1:] @ matrix[0].T).toarray().ravel()

    for ours, theirs in zip(tfidf_similarities(job, cvs), expected, strict=True):
        assert math.isclose(ours, float(theirs), abs_tol=1e-9)
