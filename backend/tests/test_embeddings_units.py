"""Embeddings : découpage, similarité, doublure déterministe (sans modèle, sans base)."""

import math

import pytest

from app.core.config import Settings
from app.modules.embeddings.chunking import ALLOWED_SECTIONS, MAX_WORDS, chunk_cv
from app.modules.embeddings.embedder import (
    EMBEDDING_DIM,
    HashingEmbedder,
    build_embedder,
    embed_texts,
)
from app.modules.embeddings.similarity import cosine, semantic_score
from app.modules.matching.text import neutralize_gender_text
from tests.cv_factory import SYNTHETIC_CVS

CV_TEXT = """Camille Martin
Ingénieure Data
camille.martin@example.com | +33 6 11 22 33 44 | github.com/cmartin

PROFIL
Data scientist passionnée par le traitement du langage naturel.

EXPÉRIENCE PROFESSIONNELLE
Data Scientist
Acme, Paris
Mars 2021 – Présent
- Modèles de langage avec Python et PyTorch
- Déploiement avec Docker

COMPÉTENCES
Python, SQL

LANGUES
Arabe (natif), Anglais (C1)

CENTRES D'INTÉRÊT
Pratique religieuse, militantisme
"""

# ------------------------------------------------------------------ découpage


def test_chunks_keep_only_job_related_sections() -> None:
    chunks = chunk_cv(CV_TEXT)
    joined = "\n".join(c.text for c in chunks)

    assert {c.section for c in chunks} <= ALLOWED_SECTIONS
    assert {"summary", "experience", "skills"} <= {c.section for c in chunks}
    for excluded in ("Camille", "Martin", "@", "+33", "github", "Arabe", "Anglais", "religieuse"):
        assert excluded not in joined


def test_chunk_positions_are_sequential_and_stable() -> None:
    chunks = chunk_cv(CV_TEXT)

    assert [c.position for c in chunks] == list(range(len(chunks)))
    assert chunk_cv(CV_TEXT) == chunks


def test_chunks_respect_the_word_budget_and_never_lose_content() -> None:
    lines = "\n".join(
        f"- Réalisation numéro {i} avec Python et SQL pour le client" for i in range(40)
    )
    text = f"EXPÉRIENCE PROFESSIONNELLE\n{lines}"

    chunks = chunk_cv(text, max_words=30)

    assert len(chunks) > 3
    for chunk in chunks:
        # budget + au plus une ligne de recouvrement
        assert len(chunk.text.split()) <= 30 + 12
    covered = " ".join(c.text for c in chunks)
    assert all(f"numéro {i} " in covered for i in range(40))


def test_adjacent_chunks_overlap_by_one_short_line() -> None:
    lines = "\n".join(f"- Ligne {i} avec quelques mots utiles ici" for i in range(20))
    chunks = chunk_cv(f"EXPÉRIENCE\n{lines}", max_words=25)

    for before, after in zip(chunks, chunks[1:], strict=False):
        assert before.text.splitlines()[-1] == after.text.splitlines()[0]


def test_a_very_long_single_line_is_kept_whole_without_looping() -> None:
    text = "COMPÉTENCES\n" + " ".join(["mot"] * 400)

    chunks = chunk_cv(text, max_words=MAX_WORDS)

    assert len(chunks) == 1 and len(chunks[0].text.split()) == 400


@pytest.mark.parametrize("text", ["", "   \n\n", "Camille Martin\ncamille@example.com"])
def test_text_without_job_content_gives_no_chunk(text: str) -> None:
    assert chunk_cv(text) == []


def test_chunks_of_real_cvs_never_contain_identity() -> None:
    for cv in SYNTHETIC_CVS:
        from app.modules.documents.extraction import detect_kind, extract_text
        from tests.cv_factory import render

        content = render(cv)
        text = extract_text(content, detect_kind(cv.filename, content, 5_000_000), 30).text
        joined = "\n".join(c.text for c in chunk_cv(text))
        for secret in (cv.name, cv.email, cv.phone, cv.link):
            assert secret not in joined, (cv.slug, secret)


# ------------------------------------------------------------------ similarité


def test_cosine_basic_cases() -> None:
    assert cosine([1, 0], [1, 0]) == pytest.approx(1)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0)
    assert cosine([1, 0], [-1, 0]) == pytest.approx(-1)
    assert cosine([0, 0], [1, 0]) == 0  # vecteur nul : pas de division par zéro
    assert cosine([3, 4], [6, 8]) == pytest.approx(1)  # insensible à la norme


def test_semantic_score_averages_the_best_passages() -> None:
    job = [1.0, 0.0]
    chunks = [[1.0, 0.0], [0.6, 0.8], [0.0, 1.0], [-1.0, 0.0]]

    assert semantic_score(job, chunks, top=2) == pytest.approx((1.0 + 0.6) / 2)
    assert semantic_score(job, chunks, top=1) == pytest.approx(1.0)


def test_one_lucky_passage_does_not_dominate_with_top_three() -> None:
    job = [1.0, 0.0]
    lucky = [[1.0, 0.0], [0.0, 1.0], [0.0, 1.0], [0.0, 1.0]]
    solid = [[0.8, 0.6], [0.8, 0.6], [0.8, 0.6], [0.0, 1.0]]

    assert semantic_score(job, solid) > semantic_score(job, lucky)


def test_semantic_score_is_clipped_at_zero_and_undefined_without_passages() -> None:
    assert semantic_score([1.0, 0.0], [[-1.0, 0.0]]) == 0.0
    assert semantic_score([1.0, 0.0], []) is None


# ------------------------------------------------------------------ doublure déterministe


def test_hashing_embedder_shape_and_normalization() -> None:
    vectors = HashingEmbedder().embed(["Python et Docker", "SEO et marketing"])

    assert len(vectors) == 2 and all(len(v) == EMBEDDING_DIM == 384 for v in vectors)
    for vector in vectors:
        assert math.sqrt(sum(x * x for x in vector)) == pytest.approx(1)


def test_hashing_embedder_is_deterministic_across_instances() -> None:
    assert HashingEmbedder().embed(["Python"]) == HashingEmbedder().embed(["Python"])


def test_hashing_embedder_is_lexical_not_semantic() -> None:
    embedder = HashingEmbedder()
    base, shared, unrelated, translation = embedder.embed(
        [
            "développement python docker kubernetes",
            "python docker kubernetes déploiement",
            "stratégie marketing réseaux sociaux",
            "software development python docker kubernetes",
        ]
    )

    assert cosine(base, shared) > cosine(base, unrelated)
    # Honnêteté : un SAC DE MOTS ne relie pas le français à l'anglais au-delà des mots communs.
    assert cosine(base, translation) < 0.8


def test_hashing_embedder_neutralizes_feminine_job_titles_like_the_matching() -> None:
    a, b = HashingEmbedder().embed(["Ingénieure développeuse", "Ingénieur développeur"])

    assert cosine(a, b) == pytest.approx(1)


def test_empty_text_gives_the_zero_vector() -> None:
    (vector,) = HashingEmbedder().embed([""])

    assert vector == [0.0] * EMBEDDING_DIM


# ------------------------------------------------------------------ neutralisation du genre


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("Ingénieure Machine Learning", "Ingénieur Machine Learning"),
        ("INGÉNIEURE DATA", "INGÉNIEUR DATA"),
        ("Développeuse et chargée de projet", "Développeur et chargé de projet"),
        ("consultante senior", "consultant senior"),
        ("Intégratrice Web", "Intégrateur Web"),
        ("Ingénieur Data", "Ingénieur Data"),  # déjà masculin : inchangé
        ("Responsable marketing", "Responsable marketing"),  # épicène : inchangé
        (
            "La directrice générale",
            "La directeur générale",
        ),  # limite assumée : on ne corrige pas l'article
    ],
)
def test_neutralize_gender_text(given: str, expected: str) -> None:
    assert neutralize_gender_text(given) == expected


def test_neutralization_does_not_touch_other_words_containing_a_feminine_form() -> None:
    # Pluriels hors liste et mots qui ne contiennent la forme qu'à l'intérieur : inchangés.
    assert neutralize_gender_text("expertes-comptables, assistants, cheffes") == (
        "expertes-comptables, assistants, cheffes"
    )
    assert neutralize_gender_text("inexperte") == "inexperte"  # « experte » n'est pas un mot entier


def test_embed_texts_neutralizes_before_calling_a_model_that_is_sensitive_to_gender() -> None:
    class Literal:
        """Faux modèle qui ne voit que les caractères exacts (sensible aux accents)."""

        name = "literal"
        dimension = EMBEDDING_DIM

        def embed(self, texts):
            return [[float(ord(c)) for c in (t + " " * 40)[:40]] for t in texts]

    fake = Literal()
    raw_f, raw_m = fake.embed(["Ingénieure Data", "Ingénieur Data"])
    via_f, via_m = embed_texts(fake, ["Ingénieure Data", "Ingénieur Data"])

    assert raw_f != raw_m  # sans neutralisation, le modèle distingue les deux
    assert via_f == via_m  # avec le point d'entrée commun, non


def test_the_embedder_is_called_only_through_embed_texts() -> None:
    """Règle structurelle : un appel direct à `.embed(` contournerait la neutralisation du genre."""
    import pathlib
    import re

    backend = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for folder in ("app", "evaluation"):
        for path in (backend / folder).rglob("*.py"):
            if path.name == "embedder.py":
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.search(r"\.embed\(", line) and "def embed" not in line:
                    offenders.append(f"{path.relative_to(backend)}:{number}")

    assert offenders == []


# ------------------------------------------------------------------ fabrique


def _settings(provider: str) -> Settings:
    return Settings(
        postgres_password="x",
        jwt_secret_key="y",
        embedding_provider=provider,  # type: ignore[arg-type]
    )


def test_provider_none_disables_the_feature() -> None:
    assert build_embedder(_settings("none")) is None


def test_hashing_provider_is_built_once_and_reused() -> None:
    first = build_embedder(_settings("hashing"))
    second = build_embedder(_settings("hashing"))

    assert isinstance(first, HashingEmbedder) and first is second


def test_default_provider_is_disabled() -> None:
    assert Settings(postgres_password="x", jwt_secret_key="y").embedding_provider == "none"
