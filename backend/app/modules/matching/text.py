"""Préparation du texte pour le matching : anonymisation, tokenisation FR/EN.

Choix d'équité : le texte comparé à l'offre n'inclut JAMAIS l'en-tête du CV (nom, titre, contacts,
liens), les langues parlées ni les centres d'intérêt. Ces éléments n'ont pas de lien démontrable
avec les exigences d'un poste, et sont des proxys de caractéristiques protégées (origine,
nationalité, religion, âge, genre).
"""

import re

from app.modules.candidates.parsing.sections import split_sections
from app.modules.candidates.parsing.text_cleaning import clean_text, fold

# Sections du CV autorisées dans le matching.
_ALLOWED_SECTIONS = {"summary", "experience", "education", "skills", "projects", "certifications"}

STOPWORDS = frozenset(
    # français
    "le la les l un une des du de d et ou ni mais donc or car que qui quoi dont où au aux en dans "
    "sur sous par pour avec sans chez vers entre comme plus moins très tres tout tous toute toutes "
    "ce cet cette ces se sa son ses leur leurs notre nos votre vos mon ma mes ton ta tes il elle ils "
    "elles on nous vous je tu est sont etre avoir ete etait sera ont a as avons avez fait faire "
    "etc ainsi aussi bien encore deja afin lors depuis jusqu y ne pas non oui si "
    # anglais
    "the a an and or but of to in on at by for with from as is are was were be been being have has "
    "had do does did will would can could should may might this that these those it its we you they "
    "he she them their our your my his her not no yes if then than so such into over under about "
    "across between within without per via also more most very all any each other".split()
)

# Formes féminines de métiers fréquents -> forme masculine (comparaison sur texte « plié »).
# Évite que « ingénieure » et « ingénieur » comptent comme deux mots différents et que le TF-IDF
# encode le genre. Liste volontairement courte : la neutralisation est PARTIELLE.
_GENDER_NEUTRAL = {
    "ingenieure": "ingenieur", "developpeuse": "developpeur", "directrice": "directeur",
    "chargee": "charge", "assistante": "assistant", "consultante": "consultant",
    "technicienne": "technicien", "administratrice": "administrateur", "redactrice": "redacteur",
    "conceptrice": "concepteur", "formatrice": "formateur", "chercheuse": "chercheur",
    "enseignante": "enseignant", "etudiante": "etudiant", "cheffe": "chef",
    "coordinatrice": "coordinateur", "animatrice": "animateur", "commerciale": "commercial",
    "experte": "expert", "ingenieures": "ingenieur", "developpeuses": "developpeur",
    "consultantes": "consultant", "directrices": "directeur", "integratrice": "integrateur",
}  # fmt: skip

# Même table, mais vers la forme masculine CORRECTEMENT ACCENTUÉE : elle s'applique au texte envoyé
# aux modèles d'embeddings (sensibles aux accents), pas seulement aux mots du TF-IDF.
_GENDER_NEUTRAL_TEXT = {
    "ingenieure": "ingénieur", "developpeuse": "développeur", "directrice": "directeur",
    "chargee": "chargé", "assistante": "assistant", "consultante": "consultant",
    "technicienne": "technicien", "administratrice": "administrateur", "redactrice": "rédacteur",
    "conceptrice": "concepteur", "formatrice": "formateur", "chercheuse": "chercheur",
    "enseignante": "enseignant", "etudiante": "étudiant", "cheffe": "chef",
    "coordinatrice": "coordinateur", "animatrice": "animateur", "commerciale": "commercial",
    "experte": "expert", "integratrice": "intégrateur", "ingenieures": "ingénieur",
    "developpeuses": "développeur", "consultantes": "consultant", "directrices": "directeur",
}  # fmt: skip
_FEMININE_WORD = re.compile(r"\b(" + "|".join(_GENDER_NEUTRAL_TEXT) + r")\b")


def neutralize_gender_text(text: str) -> str:
    """Remplace les formes féminines connues de métiers par le masculin, en gardant la casse.

    Évite qu'un modèle d'embeddings voie « Ingénieure » et « Ingénieur » comme deux profils
    différents. Liste courte : la neutralisation est PARTIELLE (voir ADR-004 et ADR-005).
    """
    folded = fold(text)
    out: list[str] = []
    last = 0
    for match in _FEMININE_WORD.finditer(folded):
        replacement = _GENDER_NEUTRAL_TEXT[match.group(1)]
        original = text[match.start() : match.end()]
        if original.isupper():
            replacement = replacement.upper()
        elif original[:1].isupper():
            replacement = replacement[:1].upper() + replacement[1:]
        out += [text[last : match.start()], replacement]
        last = match.end()
    out.append(text[last:])
    return "".join(out)


_TOKEN = re.compile(r"[a-z0-9]+(?:[+#]+|\.[a-z0-9]+)*")


def anonymized_cv_text(extracted_text: str) -> str:
    """Texte du CV restreint aux sections liées au poste (voir l'en-tête du module)."""
    lines, _ = split_sections(clean_text(extracted_text))
    return "\n".join(line.text for line in lines if line.section in _ALLOWED_SECTIONS and line.text)


def tokens(text: str) -> list[str]:
    """Mots significatifs : sans accents, sans mots vides, sans nombres seuls, genre neutralisé."""
    result: list[str] = []
    for raw in _TOKEN.findall(fold(text)):
        word = raw.rstrip(".")
        if word.isdigit() or word in STOPWORDS:
            continue
        if len(word) < 2 and not any(ch in word for ch in "+#"):
            continue
        result.append(_GENDER_NEUTRAL.get(word, word))
    return result


def analyzer(text: str) -> list[str]:
    """Analyseur TF-IDF : mots et bigrammes de mots consécutifs."""
    words = tokens(text)
    return words + [f"{a} {b}" for a, b in zip(words, words[1:], strict=False)]
