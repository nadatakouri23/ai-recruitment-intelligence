"""Détection des compétences du référentiel dans un CV (FR et EN)."""

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from app.modules.candidates.parsing.sections import Line
from app.modules.candidates.parsing.skills_taxonomy import SKILLS, SkillDef
from app.modules.candidates.parsing.text_cleaning import fold
from app.modules.candidates.profile import Provenance, SkillItem

_BY_ALIAS: dict[str, SkillDef] = {}
for _skill in SKILLS:
    for _alias in _skill.aliases:
        _BY_ALIAS[fold(_alias)] = _skill

# Un alias ne doit pas être collé à une lettre/un chiffre (« java » dans « javascript »,
# « sql » dans « mysql ») ni suivi de + ou # (« c » dans « c++ » est traité à part).
# Les alias les plus longs passent en premier : « react native » l'emporte sur « react ».
_ALIAS_REGEX = re.compile(
    r"(?<![a-z0-9])(?:"
    + "|".join(re.escape(a) for a in sorted(_BY_ALIAS, key=len, reverse=True))
    + r")(?![a-z0-9+#])"
)

# Alias ambigus (R, C, Go, Spark, Excel…) : casse exacte, jamais collés à un autre mot.
# - mode « full »    : reconnus tels quels (section Compétences, où l'on liste des technologies).
# - mode « relaxed » : ailleurs, seuls les noms de plus de 2 lettres, avec majuscule et AU MILIEU
#                      d'une phrase (« ETL avec Spark »). « Spring » (la saison) et les lettres
#                      isolées (R, C, Go) restent réservés à la section Compétences.
# - mode « listing » : comme « relaxed » mais le mot peut ouvrir une ligne : pour les puces courtes
#                      d'une offre (« - Spark est un plus », « - Tableau »).
StrictMode = Literal["none", "relaxed", "listing", "full"]
_STRICT: dict[str, SkillDef] = {t: s for s in SKILLS for t in s.strict_aliases}
_RELAXED: dict[str, SkillDef] = {t: s for t, s in _STRICT.items() if len(t) > 2 and t != "Spring"}


def _strict_regex(tokens: dict[str, SkillDef], *, mid_sentence: bool) -> re.Pattern[str]:
    # « au milieu d'une phrase » : après un mot et une espace, ou après ' ’ ( / (« d'Excel »).
    start = r"(?:(?<=\S )|(?<=['’(/]))" if mid_sentence else ""
    body = "|".join(re.escape(t) for t in tokens)
    return re.compile(rf"{start}(?<![\w+#./&-])(?:{body})(?![\w+#&-])")


# Mots ambigus de plus de 2 lettres, acceptés si la phrase contient déjà une compétence SANS
# ambiguïté (« Java, Spring et SQL » : le framework ; « Spring 2020 » seul : la saison).
_COOCCURRING: dict[str, SkillDef] = {t: s for t, s in _STRICT.items() if len(t) > 2}
_STRICT_REGEX = _strict_regex(_STRICT, mid_sentence=False)
_COOCCURRING_REGEX = _strict_regex(_COOCCURRING, mid_sentence=False)
_RELAXED_REGEX = _strict_regex(_RELAXED, mid_sentence=True)
_LISTING_REGEX = _strict_regex(_RELAXED, mid_sentence=False)

_SNIPPET_MAX = 240


@dataclass(frozen=True)
class _Hit:
    skill: SkillDef
    line_index: int
    section: str


_BY_NAME: dict[str, SkillDef] = {fold(s.name): s for s in SKILLS}


def canonical_skill_name(query: str) -> str | None:
    """« python », « apprentissage automatique », « ML », « Go »… → nom canonique, ou None.

    Accepte les alias ET les noms canoniques exacts (y compris ceux, comme « R » ou « Go »,
    qu'on ne cherche pas librement dans un texte).
    """
    key = fold(query.strip())
    skill = _BY_ALIAS.get(key) or _BY_NAME.get(key)
    return skill.name if skill else None


def skill_category(name: str) -> str | None:
    skill = _BY_NAME.get(fold(name))
    return skill.category if skill else None


def find_skills_in_text(text: str, *, mode: StrictMode = "relaxed") -> list[str]:
    """Noms canoniques des compétences présentes dans `text` (ordre d'apparition, sans doublon)."""
    names: list[str] = []
    for skill in _scan_line(text, mode):
        if skill.name not in names:
            names.append(skill.name)
    return names


# Une adresse ou un lien (github.com/…, linkedin.com/…) n'est pas une compétence.
_LINK_OR_EMAIL = re.compile(
    r"[\w.%+-]+@[\w.-]+\.\w+|(?:https?://|www\.)\S+|\b(?:linkedin|github|gitlab)\.com/\S*",
    re.IGNORECASE,
)


def _scan_line(text: str, mode: StrictMode) -> list[SkillDef]:
    text = _LINK_OR_EMAIL.sub(lambda m: " " * len(m.group(0)), text)
    found = [(m.start(), _BY_ALIAS[m.group(0)]) for m in _ALIAS_REGEX.finditer(fold(text))]
    if mode == "full":
        found += [(m.start(), _STRICT[m.group(0)]) for m in _STRICT_REGEX.finditer(text)]
    elif mode in ("relaxed", "listing"):
        regex = _RELAXED_REGEX if mode == "relaxed" else _LISTING_REGEX
        found += [(m.start(), _RELAXED[m.group(0)]) for m in regex.finditer(text)]
        if found:  # contexte : une compétence sûre est déjà présente dans la phrase
            known = {m_start for m_start, _ in found}
            found += [
                (m.start(), _COOCCURRING[m.group(0)])
                for m in _COOCCURRING_REGEX.finditer(text)
                if m.start() not in known
            ]
    found.sort(key=lambda item: item[0])
    return [skill for _, skill in found]


def extract_skills(lines: list[Line]) -> list[SkillItem]:
    """Compétences du CV, avec la première ligne qui les justifie et leur fréquence."""
    hits: dict[str, list[_Hit]] = defaultdict(list)
    for index, line in enumerate(lines):
        if not line.text:
            continue
        mode: StrictMode = "full" if line.section == "skills" else "relaxed"
        for skill in _scan_line(line.text, mode):
            hit = _Hit(skill, index, line.section)
            if not hits[skill.name] or hits[skill.name][-1].line_index != index:
                hits[skill.name].append(hit)

    items: list[SkillItem] = []
    for name, skill_hits in hits.items():
        first = skill_hits[0]
        snippet = lines[first.line_index].text[:_SNIPPET_MAX]
        items.append(
            SkillItem(
                name=name,
                category=first.skill.category,
                mentions=len(skill_hits),
                listed_in_skills_section=any(h.section == "skills" for h in skill_hits),
                provenance=Provenance(origin="extracted", section=first.section, snippet=snippet),
            )
        )
    items.sort(key=lambda s: (not s.listed_in_skills_section, -s.mentions, s.name))
    return items
