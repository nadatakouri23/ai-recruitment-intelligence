"""CV SYNTHÉTIQUES pour les tests et les exemples (noms, sociétés et coordonnées fictifs).

Chaque CV est décrit en données, puis rendu en PDF (reportlab) ou DOCX (python-docx). Il porte sa
« vérité terrain » : ce que le parseur devrait trouver. Cette vérité est écrite à la main par
construction ; elle sert de test de régression, PAS de mesure de performance sur de vrais CV.
"""

import io
from dataclasses import dataclass, field
from typing import Literal

from docx import Document as new_docx
from docx.shared import Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

Lang = Literal["fr", "en"]
Layout = Literal["stacked", "dated"]  # stacked : titre / entreprise / période sur 3 lignes

HEADINGS: dict[Lang, dict[str, str]] = {
    "fr": {
        "summary": "PROFIL",
        "experience": "EXPÉRIENCE PROFESSIONNELLE",
        "education": "FORMATION",
        "skills": "COMPÉTENCES",
        "projects": "PROJETS",
        "languages": "LANGUES",
        "certifications": "CERTIFICATIONS",
    },
    "en": {
        "summary": "SUMMARY",
        "experience": "WORK EXPERIENCE",
        "education": "EDUCATION",
        "skills": "SKILLS",
        "projects": "PROJECTS",
        "languages": "LANGUAGES",
        "certifications": "CERTIFICATIONS",
    },
}


@dataclass(frozen=True)
class Job:
    title: str
    company: str
    location: str
    period: str
    bullets: tuple[str, ...]


@dataclass(frozen=True)
class Truth:
    """Ce que le parseur doit trouver."""

    skills: frozenset[str]
    titles: tuple[str, ...]
    companies: tuple[str, ...]
    degrees: tuple[str, ...]
    languages: frozenset[str]
    n_certifications: int
    n_projects: int
    total_months_at_2026_11: int | None = None


@dataclass(frozen=True)
class SyntheticCV:
    slug: str
    lang: Lang
    fmt: Literal["pdf", "docx"]
    name: str
    headline: str
    email: str
    phone: str
    link: str
    summary: str
    jobs: tuple[Job, ...]
    education: tuple[str, ...]
    skills: tuple[tuple[str, str], ...]
    languages: str
    certifications: tuple[str, ...]
    truth: Truth
    projects: tuple[tuple[str, tuple[str, ...]], ...] = ()
    layout: Layout = "stacked"
    skills_in_table: bool = False
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def filename(self) -> str:
        return f"{self.slug}.{self.fmt}"


# --------------------------------------------------------------------------- les 6 CV

SYNTHETIC_CVS: tuple[SyntheticCV, ...] = (
    SyntheticCV(
        slug="fr_data_scientist",
        lang="fr",
        fmt="pdf",
        name="Sofia Benali",
        headline="Ingénieure Data Scientist",
        email="sofia.benali@example.com",
        phone="+33 6 11 22 33 44",
        link="github.com/sofia-benali-demo",
        summary="Data scientist spécialisée en traitement du langage naturel, avec 6 ans "
        "d'expérience en production de modèles et en gestion de projet.",
        jobs=(
            Job(
                "Data Scientist",
                "Lumen Analytics",
                "Lyon",
                "Mars 2021 – Présent",
                (
                    "Conception d'un moteur de recherche sémantique avec PyTorch et PostgreSQL",
                    "Déploiement via Docker et CI/CD sur AWS",
                ),
            ),
            Job(
                "Ingénieure Machine Learning",
                "Atelier Numérique",
                "Paris",
                "Septembre 2018 – Février 2021",
                (
                    "Modèles de classification avec scikit-learn et Python",
                    "Travail en méthodes agiles avec Jira",
                ),
            ),
        ),
        education=(
            "Master Intelligence Artificielle — Université de Lyon, 2016 - 2018",
            "Licence Informatique — Université de Bordeaux, 2013 - 2016",
        ),
        skills=(("Langages", "Python, SQL, R"), ("Outils", "Docker, Git, Tableau")),
        projects=(
            (
                "Assistant RAG pour documents juridiques",
                ("Recherche vectorielle avec pgvector et LangChain",),
            ),
        ),
        languages="Français (natif), Anglais (C1)",
        certifications=("AWS Certified Cloud Practitioner",),
        truth=Truth(
            skills=frozenset(
                {
                    "NLP",
                    "Project Management",
                    "PyTorch",
                    "PostgreSQL",
                    "Docker",
                    "CI/CD",
                    "AWS",
                    "scikit-learn",
                    "Python",
                    "Agile",
                    "Jira",
                    "SQL",
                    "R",
                    "Git",
                    "Tableau",
                    "RAG",
                    "pgvector",
                    "LangChain",
                    "Machine Learning",
                }
            ),
            titles=("Data Scientist", "Ingénieure Machine Learning"),
            companies=("Lumen Analytics", "Atelier Numérique"),
            degrees=("Master Intelligence Artificielle", "Licence Informatique"),
            languages=frozenset({"French", "English"}),
            n_certifications=1,
            n_projects=1,
        ),
    ),
    SyntheticCV(
        slug="en_backend_engineer",
        lang="en",
        fmt="pdf",
        layout="dated",
        name="Daniel Whitfield",
        headline="Senior Backend Engineer",
        email="daniel.whitfield@example.org",
        phone="+44 20 7946 0321",
        link="linkedin.com/in/dwhitfield-demo",
        summary="Backend engineer with 9 years of experience building REST APIs and "
        "event-driven microservices.",
        jobs=(
            Job(
                "Senior Backend Engineer",
                "Northwind Labs",
                "London",
                "Jan 2020 - Present",
                (
                    "Built microservices in Java and Spring Boot",
                    "Automated deployments with Kubernetes, Terraform and GitHub Actions",
                ),
            ),
            Job(
                "Software Developer",
                "Contoso Ltd",
                "Manchester",
                "06/2015 - 12/2019",
                (
                    "Maintained a Node.js and React platform on Azure",
                    "Introduced PostgreSQL and Redis for caching",
                ),
            ),
        ),
        education=("BSc Computer Science — University of Manchester, 2011 - 2015",),
        skills=(
            ("Backend", "Java, Spring, SQL, PostgreSQL, Redis"),
            ("DevOps", "Docker, Kubernetes, Linux, Git"),
        ),
        languages="English (native), French (B2)",
        certifications=("Certified Kubernetes Administrator",),
        truth=Truth(
            skills=frozenset(
                {
                    "REST API",
                    "Microservices",
                    "Java",
                    "Spring",
                    "Kubernetes",
                    "Terraform",
                    "GitHub Actions",
                    "Node.js",
                    "React",
                    "Azure",
                    "PostgreSQL",
                    "Redis",
                    "SQL",
                    "Docker",
                    "Linux",
                    "Git",
                    # Le CV affiche une rubrique « DevOps: Docker, … » : le candidat revendique
                    # bien « DevOps ». Cas ambigu assumé (libellé de rubrique ou compétence ?).
                    "DevOps",
                }
            ),
            titles=("Senior Backend Engineer", "Software Developer"),
            companies=("Northwind Labs", "Contoso Ltd"),
            degrees=("BSc Computer Science",),
            languages=frozenset({"English", "French"}),
            n_certifications=1,
            n_projects=0,
        ),
    ),
    SyntheticCV(
        slug="fr_devops",
        lang="fr",
        fmt="docx",
        name="Mehdi Karoui",
        headline="Ingénieur DevOps",
        email="mehdi.karoui@example.net",
        phone="+33 7 55 66 77 88",
        link="github.com/mkaroui-demo",
        summary="Ingénieur DevOps avec 7 ans d'expérience en intégration continue et "
        "automatisation d'infrastructures cloud.",
        jobs=(
            Job(
                "Ingénieur DevOps",
                "Orbite Cloud",
                "Toulouse",
                "Janvier 2019 – Aujourd'hui",
                (
                    "Migration vers Kubernetes et Terraform sur Azure",
                    "Supervision avec Prometheus et Grafana",
                    "Pipelines Jenkins et GitLab CI",
                ),
            ),
            Job(
                "Administrateur Systèmes",
                "Ministère Démo",
                "Rabat",
                "2015 – 2018",
                ("Administration de serveurs Linux et scripts Bash", "Mise en place d'Ansible"),
            ),
        ),
        education=(
            "Diplôme d'Ingénieur en Informatique — École Nationale Supérieure Démo, 2012 - 2015",
        ),
        skills=(
            ("Cloud", "Azure, Terraform, Ansible"),
            ("Outils", "Docker, Kubernetes, Jenkins, Git, Linux"),
        ),
        projects=(
            (
                "Plateforme d'observabilité interne",
                ("Dashboards Grafana alimentés par Prometheus",),
            ),
        ),
        languages="Français (natif), Anglais (B2), Arabe (natif)",
        certifications=(
            "Microsoft Certified: Azure Administrator Associate",
            "Certified Kubernetes Administrator",
        ),
        truth=Truth(
            skills=frozenset(
                {
                    "CI/CD",
                    "DevOps",
                    "Kubernetes",
                    "Terraform",
                    "Azure",
                    "Prometheus",
                    "Grafana",
                    "Jenkins",
                    "GitLab CI",
                    "Linux",
                    "Bash",
                    "Ansible",
                    "Docker",
                    "Git",
                }
            ),
            titles=("Ingénieur DevOps", "Administrateur Systèmes"),
            companies=("Orbite Cloud", "Ministère Démo"),
            degrees=("Diplôme d'Ingénieur en Informatique",),
            languages=frozenset({"French", "English", "Arabic"}),
            n_certifications=2,
            n_projects=1,
        ),
    ),
    SyntheticCV(
        slug="en_data_analyst",
        lang="en",
        fmt="docx",
        skills_in_table=True,
        name="Priya Raman",
        headline="Data Analyst",
        email="priya.raman@example.com",
        phone="+1 415 555 0142",
        link="linkedin.com/in/priyaraman-demo",
        summary="Data analyst with 4 years of experience turning raw data into dashboards "
        "and insights for product teams.",
        jobs=(
            Job(
                "Data Analyst",
                "Brightpath Inc.",
                "Austin",
                "Feb 2022 - Present",
                (
                    "Built Power BI dashboards on top of Snowflake and SQL",
                    "Automated reporting with Python, Pandas and Airflow",
                ),
            ),
            Job(
                "Junior Analyst",
                "Fieldstone Group",
                "Dallas",
                "2020 - 2022",
                ("Analyzed A/B tests in Excel and R", "Maintained MySQL reports"),
            ),
        ),
        education=("BA Economics — University of Texas Demo, 2016 - 2020",),
        skills=(
            ("Analytics", "Power BI, Tableau, Excel, SQL"),
            ("Programming", "Python, R"),
            ("Data", "Snowflake, MySQL"),
        ),
        languages="English (native), Hindi (fluent)",
        certifications=(),
        truth=Truth(
            skills=frozenset(
                {
                    "Power BI",
                    "Snowflake",
                    "SQL",
                    "Python",
                    "Pandas",
                    "Airflow",
                    "MySQL",
                    "Tableau",
                    "Excel",
                    "R",
                }
            ),
            titles=("Data Analyst", "Junior Analyst"),
            companies=("Brightpath Inc.", "Fieldstone Group"),
            degrees=("BA Economics",),
            languages=frozenset({"English", "Hindi"}),
            n_certifications=0,
            n_projects=0,
        ),
    ),
    SyntheticCV(
        slug="fr_marketing",
        lang="fr",
        fmt="pdf",
        name="Léa Fontaine",
        headline="Responsable Marketing Digital",
        email="lea.fontaine@example.fr",
        phone="+33 6 98 76 54 32",
        link="linkedin.com/in/lea-fontaine-demo",
        summary="Responsable marketing digital, 8 ans d'expérience en acquisition, "
        "référencement naturel et gestion de projet.",
        jobs=(
            Job(
                "Responsable Marketing Digital",
                "Maison Lumière",
                "Bordeaux",
                "Avril 2020 – Présent",
                (
                    "Pilotage de campagnes et suivi avec Google Analytics",
                    "Optimisation du SEO et reporting sous Excel",
                ),
            ),
            Job(
                "Chargée de Communication",
                "Agence Horizon",
                "Nantes",
                "Septembre 2015 – Mars 2020",
                ("Gestion de projet éditorial et de réseaux sociaux",),
            ),
        ),
        education=("Master Marketing Digital — Université Démo de Bordeaux, 2013 - 2015",),
        skills=(("Marketing", "SEO, Google Analytics, Excel"),),
        languages="Français (natif), Anglais (courant)",
        certifications=("Google Analytics Certification",),
        truth=Truth(
            skills=frozenset({"SEO", "Project Management", "Google Analytics", "Excel"}),
            titles=("Responsable Marketing Digital", "Chargée de Communication"),
            companies=("Maison Lumière", "Agence Horizon"),
            degrees=("Master Marketing Digital",),
            languages=frozenset({"French", "English"}),
            n_certifications=1,
            n_projects=0,
        ),
    ),
    SyntheticCV(
        slug="en_ml_engineer",
        lang="en",
        fmt="pdf",
        name="Olivia Brandt",
        headline="Machine Learning Engineer",
        email="olivia.brandt@example.org",
        phone="+49 30 1234 5678",
        link="github.com/obrandt-demo",
        summary="ML engineer focused on retrieval-augmented generation and LLM applications, "
        "with 5 years of experience shipping models to production.",
        jobs=(
            Job(
                "Machine Learning Engineer",
                "Vertex Robotics",
                "Berlin",
                "Mar 2021 - Present",
                (
                    "Built RAG pipelines with LangChain and pgvector",
                    "Fine-tuned transformers with PyTorch and Hugging Face",
                ),
            ),
            # Chevauche l'emploi précédent : le cumul ne doit pas compter deux fois ces mois.
            Job(
                "Research Engineer",
                "Open Lab Demo",
                "Berlin",
                "Sep 2022 - Aug 2023",
                ("Experiments on NLP benchmarks with spaCy and NLTK",),
            ),
            Job(
                "Data Engineer",
                "Datenfluss GmbH",
                "Munich",
                "Jul 2019 - Feb 2021",
                ("Built ETL jobs with Spark and Airflow on GCP",),
            ),
        ),
        education=("MSc Computer Science — Technical University Demo of Berlin, 2017 - 2019",),
        skills=(
            ("Languages", "Python, SQL, C++"),
            ("ML", "PyTorch, scikit-learn, Hugging Face"),
            ("Cloud", "GCP, Docker"),
        ),
        projects=(
            (
                "Resume screening assistant",
                ("Semantic search over CVs with sentence embeddings and FastAPI",),
            ),
        ),
        languages="English (fluent), German (C1)",
        certifications=("TensorFlow Developer Certificate",),
        truth=Truth(
            skills=frozenset(
                {
                    "Machine Learning",
                    "RAG",
                    "LLM",
                    "LangChain",
                    "pgvector",
                    "PyTorch",
                    "Hugging Face",
                    "NLP",
                    "spaCy",
                    "NLTK",
                    "ETL",
                    "Spark",
                    "Airflow",
                    "GCP",
                    "Python",
                    "SQL",
                    "C++",
                    "scikit-learn",
                    "Docker",
                    "FastAPI",
                    "TensorFlow",
                }
            ),
            titles=("Machine Learning Engineer", "Research Engineer", "Data Engineer"),
            companies=("Vertex Robotics", "Open Lab Demo", "Datenfluss GmbH"),
            degrees=("MSc Computer Science",),
            languages=frozenset({"English", "German"}),
            n_certifications=1,
            n_projects=1,
            # Jul 2019 → nov. 2026, sans double comptage du chevauchement (89 mois).
            total_months_at_2026_11=89,
        ),
    ),
)


# --------------------------------------------------------------------------- rendu

Block = tuple[
    str, str
]  # (type, texte) : "name", "headline", "contact", "h", "line", "bold", "bullet"


def _blocks(cv: SyntheticCV) -> list[Block]:
    h = {**HEADINGS[cv.lang], **cv.extra}  # `extra` : titres de rubriques personnalisés
    blocks: list[Block] = [
        ("name", cv.name),
        ("headline", cv.headline),
        ("contact", f"{cv.email} | {cv.phone} | {cv.link}"),
        ("h", h["summary"]),
        ("line", cv.summary),
        ("h", h["experience"]),
    ]
    for job in cv.jobs:
        if cv.layout == "dated":
            blocks.append(("bold", f"{job.title} | {job.company}, {job.location} | {job.period}"))
        else:
            blocks += [
                ("bold", job.title),
                ("line", f"{job.company}, {job.location}"),
                ("line", job.period),
            ]
        blocks += [("bullet", b) for b in job.bullets]
    blocks.append(("h", h["education"]))
    blocks += [("line", e) for e in cv.education]
    blocks.append(("h", h["skills"]))
    if not cv.skills_in_table:
        blocks += [("line", f"{label}: {value}") for label, value in cv.skills]
    if cv.projects:
        blocks.append(("h", h["projects"]))
        for name, bullets in cv.projects:
            blocks.append(("bold", name))
            blocks += [("bullet", b) for b in bullets]
    blocks += [("h", h["languages"]), ("line", cv.languages)]
    if cv.certifications:
        blocks.append(("h", h["certifications"]))
        blocks += [("bullet", c) for c in cv.certifications]
    return blocks


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_pdf(cv: SyntheticCV) -> bytes:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=13)
    css = {
        "name": ParagraphStyle("name", parent=styles["Title"], fontSize=20, alignment=0),
        "headline": ParagraphStyle("headline", parent=body, fontSize=12, spaceAfter=2),
        "contact": body,
        "h": ParagraphStyle("h", parent=styles["Heading2"], fontSize=11, spaceBefore=10),
        "line": body,
        "bold": ParagraphStyle("bold", parent=body, fontName="Helvetica-Bold", spaceBefore=4),
        "bullet": ParagraphStyle("bullet", parent=body, leftIndent=12),
    }
    story = []
    for kind, text in _blocks(cv):
        story.append(Paragraph(("• " if kind == "bullet" else "") + _escape(text), css[kind]))
        if kind == "contact":
            story.append(Spacer(1, 6))
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm).build(story)
    return buffer.getvalue()


def render_docx(cv: SyntheticCV) -> bytes:
    document = new_docx()
    for kind, text in _blocks(cv):
        paragraph = document.add_paragraph()
        run = paragraph.add_run(("• " if kind == "bullet" else "") + text)
        run.bold = kind in ("name", "h", "bold")
        run.font.size = Pt({"name": 20, "headline": 12, "h": 11}.get(kind, 10))
        # Le tableau de compétences s'insère juste après le titre de la section.
        skills_heading = {**HEADINGS[cv.lang], **cv.extra}["skills"]
        if kind == "h" and text == skills_heading and cv.skills_in_table:
            table = document.add_table(rows=0, cols=2)
            for label, value in cv.skills:
                cells = table.add_row().cells
                cells[0].text, cells[1].text = label, value
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def render(cv: SyntheticCV) -> bytes:
    return render_pdf(cv) if cv.fmt == "pdf" else render_docx(cv)


def blank_pdf() -> bytes:
    """PDF valide sans aucun texte (simule un scan) : une seule forme graphique."""
    from reportlab.pdfgen.canvas import Canvas

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    canvas.rect(50, 50, 200, 200, fill=1)
    canvas.save()
    return buffer.getvalue()
