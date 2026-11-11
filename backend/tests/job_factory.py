"""Offres d'emploi SYNTHÉTIQUES pour les tests (sociétés fictives), alignées sur les CV de cv_factory.

Chaque offre indique quels CV sont censés lui correspondre (`relevant`). Cette « vérité » est écrite
à la main par la même personne que les CV : elle sert de garde-fou, pas de mesure de performance.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticJob:
    slug: str
    title: str
    description: str
    relevant: frozenset[str]  # slugs des CV qui doivent arriver en tête
    required: frozenset[str]
    optional: frozenset[str]
    min_years: int | None
    education_level: int | None


DATA_SCIENTIST_FR = SyntheticJob(
    slug="data_scientist_fr",
    title="Data Scientist NLP",
    description="""Lumen Analytics recherche un Data Scientist spécialisé en traitement du langage naturel.

Missions
- Concevoir et entraîner des modèles de traitement du langage naturel
- Déployer les modèles en production avec Docker et CI/CD
- Collaborer avec les équipes produit en méthodes agiles

Profil recherché
- Bac+5 (Master ou diplôme d'ingénieur)
- 3 ans d'expérience minimum en data science
- Maîtrise de Python, PyTorch et SQL
- Connaissance de PostgreSQL

Atouts
- Expérience de LangChain ou de pgvector
- AWS est un plus

Nous offrons
- Un environnement technique moderne (Kubernetes, Terraform) mais aucune expérience requise
""",
    relevant=frozenset({"fr_data_scientist", "en_ml_engineer"}),
    required=frozenset(
        {
            "NLP",
            "Docker",
            "CI/CD",
            "Agile",
            "Data Science",
            "Python",
            "PyTorch",
            "SQL",
            "PostgreSQL",
        }
    ),
    optional=frozenset({"LangChain", "pgvector", "AWS"}),
    min_years=3,
    education_level=5,
)

BACKEND_EN = SyntheticJob(
    slug="backend_en",
    title="Senior Backend Engineer",
    description="""We are hiring a Senior Backend Engineer to build REST APIs and microservices.

Responsibilities
- Design and build microservices in Java and Spring Boot
- Run services on Kubernetes with CI/CD

Requirements
- 5+ years of experience in backend development
- Strong knowledge of Java, SQL and PostgreSQL
- Bachelor's degree in computer science or equivalent

Nice to have
- Terraform
- Experience with Redis and GitHub Actions

Benefits
- Remote friendly, 25 days of holiday, Docker-powered laptops
""",
    relevant=frozenset({"en_backend_engineer"}),
    required=frozenset(
        {"REST API", "Microservices", "Java", "Spring", "Kubernetes", "CI/CD", "SQL", "PostgreSQL"}
    ),
    optional=frozenset({"Terraform", "Redis", "GitHub Actions"}),
    min_years=5,
    education_level=3,
)

DEVOPS_FR = SyntheticJob(
    slug="devops_fr",
    title="Ingénieur DevOps",
    description="""Orbite Cloud recrute un Ingénieur DevOps pour industrialiser sa plateforme cloud.

Vos missions
- Automatiser l'infrastructure avec Terraform et Ansible
- Mettre en place des pipelines d'intégration continue avec Jenkins ou GitLab CI
- Superviser avec Prometheus et Grafana

Votre profil
- Diplôme d'ingénieur (Bac+5)
- 4 ans d'expérience minimum
- Solide pratique de Kubernetes, Docker et Linux

Souhaité
- Certification Azure
""",
    relevant=frozenset({"fr_devops"}),
    required=frozenset(
        {
            "DevOps",
            "Terraform",
            "Ansible",
            "CI/CD",
            "Jenkins",
            "GitLab CI",
            "Prometheus",
            "Grafana",
            "Kubernetes",
            "Docker",
            "Linux",
        }
    ),
    optional=frozenset({"Azure"}),
    min_years=4,
    education_level=5,
)

ANALYST_EN = SyntheticJob(
    slug="analyst_en",
    title="Data Analyst",
    description="""Brightpath is looking for a Data Analyst to turn raw data into dashboards.

Requirements
- 2 years of experience in data analysis
- Power BI or Tableau, SQL and Excel
- Python for automation

Nice to have
- Airflow
- Snowflake
""",
    relevant=frozenset({"en_data_analyst"}),
    required=frozenset({"Data Analysis", "Power BI", "Tableau", "SQL", "Excel", "Python"}),
    optional=frozenset({"Airflow", "Snowflake"}),
    min_years=2,
    education_level=None,
)

MARKETING_FR = SyntheticJob(
    slug="marketing_fr",
    title="Responsable Marketing Digital",
    description="""Maison Lumière recherche un Responsable Marketing Digital.

Missions
- Piloter la stratégie de référencement naturel et l'acquisition
- Suivre les performances avec Google Analytics

Profil recherché
- Master en marketing (Bac+5)
- 5 ans d'expérience minimum
- Gestion de projet et maîtrise d'Excel
""",
    relevant=frozenset({"fr_marketing"}),
    required=frozenset({"SEO", "Google Analytics", "Project Management", "Excel"}),
    optional=frozenset(),
    min_years=5,
    education_level=5,
)

SYNTHETIC_JOBS = (DATA_SCIENTIST_FR, BACKEND_EN, DEVOPS_FR, ANALYST_EN, MARKETING_FR)
