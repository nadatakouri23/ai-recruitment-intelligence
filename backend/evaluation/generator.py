"""Générateur du jeu d'évaluation SYNTHÉTIQUE (CV et offres) et règle de pertinence de référence.

Principe : chaque candidat est d'abord décrit par des attributs CACHÉS (famille de métier, niveau,
compétences réellement possédées, années d'expérience), puis rendu en vrai fichier PDF/DOCX.
La pertinence de référence (« gold ») est calculée à partir des attributs cachés, JAMAIS à partir
de ce que lit le parseur : les erreurs de lecture comptent donc contre le système.

Limites (à garder en tête) : tout est écrit par un seul auteur (Claude), avec ses propres idées de ce
qu'est un bon profil ; les CV sont plus propres et plus homogènes que de vrais CV ; la règle de
pertinence n'a été validée par aucun recruteur.
"""

import random
import unicodedata
from dataclasses import dataclass, replace
from datetime import date

from app.modules.candidates.parsing.skills import find_skills_in_text
from evaluation.families import FAMILIES, Family, are_adjacent, surface
from tests.cv_factory import Job, SyntheticCV, Truth

TODAY = date(2026, 11, 11)

# Six « familles de prénoms et noms » d'origines culturelles variées, entièrement fictives (combinaisons
# aléatoires). Elles ne servent QU'à l'audit d'équité : aucune ne porte de signal sur la compétence.
NAME_POOLS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        ("Camille", "Julien", "Chloé", "Mathieu", "Élodie", "Thomas"),
        ("Martin", "Bernard", "Dubois", "Moreau", "Laurent", "Simon"),
    ),
    (
        ("Yassine", "Salma", "Karim", "Nadia", "Mehdi", "Imane"),
        ("Benali", "Haddad", "Karoui", "Amrani", "Belkacem", "Cherif"),
    ),
    (
        ("Kwame", "Aminata", "Moussa", "Fatou", "Ibrahim", "Awa"),
        ("Diallo", "Traoré", "Ndiaye", "Mensah", "Okafor", "Sow"),
    ),
    (
        ("James", "Emily", "Oliver", "Sophie", "Daniel", "Hannah"),
        ("Whitfield", "Carter", "Brooks", "Hughes", "Fletcher", "Morgan"),
    ),
    (
        ("Priya", "Arjun", "Ananya", "Rahul", "Meera", "Vikram"),
        ("Raman", "Iyer", "Kapoor", "Nair", "Desai", "Menon"),
    ),
    (
        ("Wei", "Mei", "Hiro", "Yuna", "Jun", "Lin"),
        ("Zhang", "Tanaka", "Kim", "Nguyen", "Chen", "Park"),
    ),
)
CITIES = (
    "Paris",
    "Lyon",
    "Toulouse",
    "Casablanca",
    "London",
    "Berlin",
    "Madrid",
    "Dakar",
    "Montréal",
    "Tunis",
)
COMPANIES = (
    "Lumen Analytics", "Atelier Numérique", "Orbite Cloud", "Northwind Labs", "Contoso Démo",
    "Brightpath", "Vertex Robotics", "Datenfluss", "Maison Lumière", "Horizon Systèmes",
    "Quantum Démo", "Pixel Forge", "Nimbus Works", "Aurora Tech", "Cobalt Studio", "Helios Group",
)  # fmt: skip
MONTHS_FR = ("Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre")  # fmt: skip
MONTHS_EN = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
LANGUAGE_LINES = (
    "Français (natif), Anglais (C1)",
    "Anglais (natif), Français (B2)",
    "Arabe (natif), Français (courant), Anglais (B2)",
    "English (native), German (B1)",
    "Français (natif), Espagnol (B2), Anglais (C1)",
    "English (fluent), Hindi (native)",
)

HEADINGS = {
    "fr": {
        "experience": ("EXPÉRIENCE PROFESSIONNELLE", "EXPÉRIENCE", "PARCOURS PROFESSIONNEL"),
        "skills": ("COMPÉTENCES", "COMPÉTENCES TECHNIQUES"),
        "education": ("FORMATION", "ÉTUDES"),
    },
    "en": {
        "experience": ("WORK EXPERIENCE", "EXPERIENCE", "PROFESSIONAL EXPERIENCE"),
        "skills": ("SKILLS", "TECHNICAL SKILLS", "KEY SKILLS"),
        "education": ("EDUCATION",),
    },
}
UNKNOWN_EXPERIENCE_HEADING = {"fr": "MON PARCOURS", "en": "WHAT I HAVE DONE"}
QUALITY_KEEP = {"strong": 0.95, "medium": 0.75, "weak": 0.45}
SENIORITY_YEARS = {"junior": (1.0, 2.5), "mid": (3.0, 5.5), "senior": (6.0, 10.0)}
_PLACEHOLDER_TRUTH = Truth(frozenset(), (), (), (), frozenset(), 0, 0)


@dataclass(frozen=True)
class CandidateSpec:
    key: int
    family: str
    lang: str
    quality: str
    seniority: str
    years: float
    held: frozenset[
        str
    ]  # compétences RÉELLEMENT possédées (y compris celles écrites en outil hors référentiel)
    substituted: frozenset[str]  # parmi `held`, celles écrites avec un outil absent du référentiel
    stuffed: bool  # CV qui liste des compétences qu'il n'a pas (bourrage de mots-clés)
    name_pool: int
    cv: SyntheticCV


@dataclass(frozen=True)
class JobSpec:
    key: int
    title: str
    description: str
    lang: str
    targets: frozenset[str]  # familles de métiers visées
    required_true: tuple[str, ...]  # exigences réelles (vérité terrain de l'analyse d'offre)
    optional_true: tuple[str, ...]
    min_years: int
    city: str | None


@dataclass(frozen=True)
class Dataset:
    seed: int
    candidates: tuple[CandidateSpec, ...]
    jobs: tuple[JobSpec, ...]


# ------------------------------------------------------------------ pertinence de référence


def gold_grade(candidate: CandidateSpec, job: JobSpec) -> int:
    """Pertinence 0 à 3, calculée sur les attributs CACHÉS (jamais sur la sortie du parseur).

    - Part des exigences de l'offre réellement possédées f, et années d'expérience suffisantes.
    - f >= 0,7 et expérience suffisante : 3 ; f >= 0,5 (ou f >= 0,7 sans l'expérience) : 2 ;
      f >= 0,3 : 1 ; sinon 0.
    - Même famille de métier : au moins 1. Famille voisine : entre 1 et 2. Famille sans rapport : au plus 1.
    Le niveau d'études n'entre pas dans la règle (le moteur, lui, en tient compte).
    """
    fraction = len(set(job.required_true) & candidate.held) / len(job.required_true)
    years_ok = candidate.years >= job.min_years
    if fraction >= 0.7:
        grade = 3 if years_ok else 2
    elif fraction >= 0.5:
        grade = 2
    elif fraction >= 0.3:
        grade = 1
    else:
        grade = 0
    if candidate.family in job.targets:
        return max(grade, 1)
    if any(are_adjacent(candidate.family, target) for target in job.targets):
        return min(max(grade, 1), 2)
    return min(grade, 1)


# ------------------------------------------------------------------ génération


def _neutral(titles: tuple[str, ...]) -> tuple[str, ...]:
    """Intitulés sans nom de compétence (« Java Developer », « Ingénieur DevOps » en contiennent un).

    Une offre dont le titre cite une compétence l'exige (à juste titre) ; pour que la vérité terrain
    des exigences reste exacte, les titres du jeu n'en citent aucune.
    """
    neutral = tuple(t for t in titles if not find_skills_in_text(t, mode="listing"))
    return neutral or ("Spécialiste",)


def _ascii(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    ).lower()


def _month_label(index: int, lang: str, numeric: bool) -> str:
    year, month = divmod(index, 12)
    if numeric:
        return f"{month + 1:02d}/{year}"
    return f"{(MONTHS_FR if lang == 'fr' else MONTHS_EN)[month]} {year}"


def _period(start: int, end: int, current: bool, lang: str, numeric: bool) -> str:
    present = "Présent" if lang == "fr" else "Present"
    separator = " – " if lang == "fr" else " - "
    return f"{_month_label(start, lang, numeric)}{separator}{present if current else _month_label(end, lang, numeric)}"


def _name(rng: random.Random, pool: int) -> tuple[str, str, str, str, str]:
    first_names, last_names = NAME_POOLS[pool]
    first, last = rng.choice(first_names), rng.choice(last_names)
    handle = f"{_ascii(first)}.{_ascii(last)}"
    phone = f"+{rng.choice((33, 44, 49, 212, 221, 1))} {rng.randint(1, 9)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)} {rng.randint(10, 99)}"
    link = rng.choice(
        (
            f"github.com/{_ascii(first)}{_ascii(last)}-demo",
            f"linkedin.com/in/{handle.replace('.', '-')}-demo",
        )
    )
    return f"{first} {last}", f"{handle}@example.com", phone, link, handle


def build_candidate(rng: random.Random, key: int, family: Family, lang: str) -> CandidateSpec:
    quality = rng.choices(("strong", "medium", "weak"), weights=(5, 3, 2))[0]
    seniority = rng.choice(("junior", "mid", "senior"))
    years = round(rng.uniform(*SENIORITY_YEARS[seniority]), 1)

    # Compétences réellement possédées.
    keep = QUALITY_KEEP[quality]
    core = [s for s in family.core if rng.random() < keep] or [rng.choice(family.core)]
    extras = rng.sample(family.extras, k=rng.randint(2, min(5, len(family.extras))))
    foreign = [
        s
        for other in FAMILIES.values()
        if other.name != family.name
        for s in other.core
        if s not in family.core and s not in family.extras
    ]
    noise = rng.sample(foreign, k=rng.randint(0, 2))
    held = set(core) | set(extras) | set(noise)

    # Une partie des compétences de base est écrite avec un outil absent du référentiel ; la part
    # varie beaucoup d'un candidat à l'autre (certains n'en ont aucune, d'autres 40 %).
    substitution_rate = rng.choice((0.0, 0.0, 0.15, 0.4))
    substituted = {
        s: family.offtax[i % len(family.offtax)]
        for i, s in enumerate(core)
        if rng.random() < substitution_rate
    }
    visible = [(substituted.get(s) or surface(s, rng.random())) for s in sorted(held)]

    # Cas adverse : ~8 % des candidats « gonflent » leur CV en listant, dans la seule section
    # compétences, des compétences d'une famille éloignée qu'ils ne possèdent PAS (bourrage de
    # mots-clés). Elles n'entrent pas dans `held` : la pertinence de référence les ignore.
    stuffed_text: list[str] = []
    if rng.random() < 0.08:
        distant = [
            f
            for f in FAMILIES.values()
            if f.name != family.name and not are_adjacent(f.name, family.name)
        ]
        stuffed = rng.sample(rng.choice(distant).core, k=4)
        stuffed_text = [surface(s, rng.random()) for s in stuffed if s not in held]

    pool = rng.randrange(len(NAME_POOLS))
    name, email, phone, link, _ = _name(rng, pool)
    titles = _neutral(family.titles_fr if lang == "fr" else family.titles_en)
    topics = family.topics_fr if lang == "fr" else family.topics_en
    numeric_dates = rng.random() < 0.3

    # Expériences, de la plus récente à la plus ancienne.
    total_months = round(years * 12)
    count = 1 if seniority == "junior" else rng.choice((2, 3)) if seniority == "senior" else 2
    cuts = sorted(
        rng.sample(
            range(6, max(total_months - 5, 8)), k=min(count - 1, max(0, total_months - 12) // 6)
        )
    )
    bounds = [0, *cuts, total_months]
    durations = [max(6, b - a) for a, b in zip(bounds, bounds[1:], strict=False)]
    current = rng.random() < 0.6
    end_idx = TODAY.year * 12 + TODAY.month - 1 - (0 if current else rng.randint(1, 8))
    assignment = [[] for _ in durations]
    for skill_text in visible:
        for slot in rng.sample(range(len(durations)), k=rng.randint(1, min(2, len(durations)))):
            assignment[slot].append(skill_text)

    jobs: list[Job] = []
    cursor = end_idx
    first_start = cursor
    for position, (duration, skills) in enumerate(
        zip(reversed(durations), assignment, strict=True)
    ):
        start = cursor - duration + 1
        first_start = start
        bullets = _bullets(rng, lang, topics, skills)
        jobs.append(
            Job(
                title=rng.choice(titles),
                company=rng.choice(COMPANIES),
                location=rng.choice(CITIES),
                period=_period(start, cursor, current and position == 0, lang, numeric_dates),
                bullets=bullets,
            )
        )
        cursor = start - rng.randint(0, 2) - 1

    degrees_fr = (
        "Master {f}", "Master {f}", "Licence {f}", "Diplôme d'Ingénieur en {f}", "Diplôme d'Ingénieur en {f}", "BTS {f}",
    )  # fmt: skip
    degrees_en = ("MSc {f}", "MSc {f}", "BSc {f}", "BSc {f}", "BA {f}")
    fields = family.fields_fr if lang == "fr" else family.fields_en
    degree = rng.choice(degrees_fr if lang == "fr" else degrees_en).format(f=rng.choice(fields))
    institution = (
        rng.choice(("Université Démo de", "École Nationale Démo", "Institut Démo de"))
        + f" {rng.choice(CITIES)}"
    )
    graduation = first_start // 12 - rng.randint(0, 1)

    headings = {k: rng.choice(v) for k, v in HEADINGS[lang].items()}
    if rng.random() < 0.08:
        headings["experience"] = UNKNOWN_EXPERIENCE_HEADING[lang]  # rubrique non reconnue

    listed = (
        visible + stuffed_text
    )  # les compétences gonflées n'apparaissent que dans cette section
    half = len(listed) // 2
    rng.shuffle(listed)
    skill_lines = (
        (
            ("Technologies", ", ".join(listed[:half] or listed)),
            ("Outils" if lang == "fr" else "Tools", ", ".join(listed[half:])),
        )
        if half
        else (("Technologies", ", ".join(listed)),)
    )
    skill_lines = tuple(line for line in skill_lines if line[1])
    latest = jobs[0].title
    summary = (
        f"{latest} avec {int(years)} ans d'expérience."
        if lang == "fr"
        else f"{latest} with {int(years)} years of experience."
    )

    cv = SyntheticCV(
        slug=f"cand_{key:04d}",
        lang=lang,  # type: ignore[arg-type]
        fmt=rng.choice(("pdf", "pdf", "docx")),
        name=name,
        headline=latest,
        email=email,
        phone=phone,
        link=link,
        summary=summary,
        jobs=tuple(jobs),
        education=(f"{degree} — {institution}, {graduation - 3} - {graduation}",),
        skills=skill_lines,
        languages=rng.choice(LANGUAGE_LINES),
        certifications=(),
        truth=_PLACEHOLDER_TRUTH,
        layout=rng.choice(("stacked", "dated")),  # type: ignore[arg-type]
        skills_in_table=False,
        extra=headings,
    )
    return CandidateSpec(
        key,
        family.name,
        lang,
        quality,
        seniority,
        years,
        frozenset(held),
        frozenset(substituted),
        bool(stuffed_text),
        pool,
        cv,
    )


def _bullets(
    rng: random.Random, lang: str, topics: tuple[str, ...], skills: list[str]
) -> tuple[str, ...]:
    if not skills:
        topic = rng.choice(topics)
        return (
            f"Collaboration avec l'équipe sur {topic}"
            if lang == "fr"
            else f"Collaborated with the team on {topic}",
        )
    bullets = []
    pending = list(skills)
    rng.shuffle(pending)
    while pending:
        size = rng.randint(1, 3)
        group, pending = pending[:size], pending[size:]
        topic = rng.choice(topics)
        joined = _join(group, lang)
        template = rng.choice(
            (
                "Développement de {t} avec {s}",
                "Amélioration de {t} avec {s}",
                "Réalisation de {t} avec {s}",
            )
            if lang == "fr"
            else ("Developed {t} using {s}", "Improved {t} with {s}", "Delivered {t} with {s}")
        )
        bullets.append(template.format(t=topic, s=joined))
    return tuple(bullets)


def _join(items: list[str], lang: str) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + (" et " if lang == "fr" else " and ") + items[-1]


def build_job(
    rng: random.Random,
    key: int,
    targets: tuple[str, ...],
    lang: str,
    *,
    title: str | None = None,
    with_city: bool,
) -> JobSpec:
    families = [FAMILIES[t] for t in targets]
    if len(families) == 1:
        required = rng.sample(families[0].core, k=min(5, len(families[0].core)))
    else:
        required = []
        for fam in families:
            required += [s for s in rng.sample(fam.core, k=3) if s not in required]
    extras = [s for fam in families for s in fam.extras if s not in required]
    optional = rng.sample(extras, k=min(2, len(extras)))
    min_years = rng.choice((2, 3, 3, 5))
    title = title or rng.choice(
        _neutral(families[0].titles_fr if lang == "fr" else families[0].titles_en)
    )
    company = rng.choice(COMPANIES)
    city = rng.choice(CITIES) if with_city else None
    topic = rng.choice(families[0].topics_fr if lang == "fr" else families[0].topics_en)
    distractor = rng.choice(
        [s for fam in FAMILIES.values() for s in fam.core if s not in required + optional]
    )

    skill_lines = []
    for i in range(0, len(required), 3):
        group = [surface(s, rng.random()) for s in required[i : i + 3]]
        skill_lines.append(
            f"Maîtrise de {_join(group, 'fr')}"
            if lang == "fr"
            else f"Strong knowledge of {_join(group, 'en')}"
        )
    if lang == "fr":
        degree = rng.choice(
            ("Bac+5 (Master ou diplôme d'ingénieur)", "Licence ou équivalent (Bac+3)")
        )
        text = [
            f"{company} recherche un {title}." + (f" Poste basé à {city}." if city else ""),
            "",
            "Missions",
            f"- Concevoir et faire évoluer {topic}",
            "- Travailler avec les équipes métier",
            "",
            "Profil recherché",
            f"- {min_years} ans d'expérience minimum",
            f"- {degree}",
            *(f"- {line}" for line in skill_lines),
            "",
            "Atouts",
            *(f"- {surface(s, 0)} est un plus" for s in optional),
            "",
            "Nous offrons",
            f"- Formation continue ({distractor}) et télétravail partiel",
        ]
    else:
        degree = rng.choice(("Master's degree or equivalent", "Bachelor's degree or equivalent"))
        text = [
            f"{company} is looking for a {title}."
            + (f" The position is based in {city}." if city else ""),
            "",
            "Responsibilities",
            f"- Design and improve {topic}",
            "- Work with business teams",
            "",
            "Requirements",
            f"- {min_years}+ years of experience",
            f"- {degree}",
            *(f"- {line}" for line in skill_lines),
            "",
            "Nice to have",
            *(f"- {surface(s, 0)} is a plus" for s in optional),
            "",
            "Benefits",
            f"- Learning budget ({distractor}) and remote work",
        ]
    return JobSpec(
        key,
        title,
        "\n".join(text),
        lang,
        frozenset(targets),
        tuple(required),
        tuple(optional),
        min_years,
        city,
    )


def build_dataset(seed: int, per_family: int = 14) -> Dataset:
    """Jeu déterministe : même graine, même jeu."""
    rng = random.Random(seed)
    candidates = []
    for family in FAMILIES.values():
        for _ in range(per_family):
            candidates.append(
                build_candidate(rng, len(candidates), family, rng.choice(("fr", "en")))
            )

    jobs = []
    for family in FAMILIES:
        jobs.append(
            build_job(
                rng, len(jobs), (family,), rng.choice(("fr", "en")), with_city=rng.random() < 0.5
            )
        )
    # Offres hybrides : deux familles visées, ce qui rend le classement moins tranché.
    jobs.append(
        build_job(
            rng,
            len(jobs),
            ("frontend", "backend_python"),
            "en",
            title="Full-Stack Developer",
            with_city=True,
        )
    )
    jobs.append(
        build_job(
            rng,
            len(jobs),
            ("data_engineer", "data_analyst"),
            "fr",
            title="Ingénieur Analytics",
            with_city=False,
        )
    )
    return Dataset(seed, tuple(candidates), tuple(jobs))


# ------------------------------------------------------------------ jumeaux pour l'audit d'équité


def twin_identity(spec: CandidateSpec, rng: random.Random) -> SyntheticCV:
    """Même CV, autre identité : nom d'une autre « famille de noms », contacts, titre d'en-tête, langues."""
    pool = (spec.name_pool + 1 + rng.randrange(len(NAME_POOLS) - 1)) % len(NAME_POOLS)
    name, email, phone, link, _ = _name(rng, pool)
    languages = rng.choice([line for line in LANGUAGE_LINES if line != spec.cv.languages])
    return replace(
        spec.cv,
        name=name,
        email=email,
        phone=phone,
        link=link,
        headline="Profil confidentiel",
        languages=languages,
    )


_FEMININE = {
    "Ingénieur": "Ingénieure", "Développeur": "Développeuse", "Chargé": "Chargée", "Consultant": "Consultante",
    "Administrateur": "Administratrice", "Intégrateur": "Intégratrice",
}  # fmt: skip


def twin_gender_titles(cv: SyntheticCV) -> SyntheticCV:
    """Mêmes postes, intitulés mis au féminin (candidatures françaises uniquement)."""

    def feminize(title: str) -> str:
        for masculine, feminine in _FEMININE.items():
            title = title.replace(masculine, feminine)
        return title

    return replace(cv, jobs=tuple(replace(j, title=feminize(j.title)) for j in cv.jobs))


def twin_proxies(cv: SyntheticCV) -> SyntheticCV:
    """Mêmes compétences et parcours, mais autres villes (employeurs, école) : proxys géographiques."""
    shift = {city: CITIES[(i + 3) % len(CITIES)] for i, city in enumerate(CITIES)}

    def remap(text: str) -> str:
        # Remplacement simultané pour ne pas enchaîner deux substitutions.
        for city in sorted(shift, key=len, reverse=True):
            text = text.replace(city, f"\0{CITIES.index(city)}\0")
        for index, city in enumerate(CITIES):
            text = text.replace(f"\0{index}\0", shift[city])
        return text

    return replace(
        cv,
        jobs=tuple(replace(j, location=remap(j.location)) for j in cv.jobs),
        education=tuple(remap(e) for e in cv.education),
    )
