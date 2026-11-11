"""Familles de métiers du jeu d'évaluation SYNTHÉTIQUE.

Écrit par l'auteur de l'assistant (Claude), donc avec ses propres idées de ce qu'est « un profil
data scientist » : voir les limites dans docs/evaluation/matching-results.md.

- `core`   : compétences centrales du métier (celles qu'une offre exige).
- `extras` : compétences annexes fréquentes (celles qu'une offre cite comme « un plus »).
- `offtax` : outils équivalents ABSENTS du référentiel de compétences. Un candidat qui écrit
             « Dataiku » plutôt que « Machine Learning » possède réellement la compétence, mais le
             système ne peut pas la voir : cela mesure l'effet des limites du référentiel.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Family:
    name: str
    core: tuple[str, ...]
    extras: tuple[str, ...]
    offtax: tuple[str, ...]
    titles_en: tuple[str, ...]
    titles_fr: tuple[str, ...]
    topics_en: tuple[str, ...]
    topics_fr: tuple[str, ...]
    fields_en: tuple[str, ...]
    fields_fr: tuple[str, ...]


FAMILIES: dict[str, Family] = {
    f.name: f
    for f in (
        Family(
            "data_scientist",
            core=(
                "Python",
                "Machine Learning",
                "scikit-learn",
                "Pandas",
                "Statistics",
                "SQL",
                "Jupyter",
            ),
            extras=("NumPy", "Matplotlib", "PyTorch", "TensorFlow", "NLP", "Spark", "Tableau"),
            offtax=("Dataiku", "RapidMiner", "SAS", "Alteryx"),
            titles_en=("Data Scientist", "Senior Data Scientist", "Applied Scientist"),
            titles_fr=("Data Scientist", "Ingénieur Data Scientist", "Scientifique des données"),
            topics_en=("predictive models", "customer segmentation", "forecasting pipelines"),
            topics_fr=("modèles prédictifs", "segmentation clientèle", "prévisions de la demande"),
            fields_en=("Statistics", "Applied Mathematics", "Computer Science"),
            fields_fr=("Statistique", "Mathématiques appliquées", "Informatique"),
        ),
        Family(
            "ml_engineer",
            core=("Python", "PyTorch", "Machine Learning", "Deep Learning", "Docker", "Git"),
            extras=(
                "TensorFlow",
                "Kubernetes",
                "AWS",
                "FastAPI",
                "Hugging Face",
                "LLM",
                "Airflow",
                "CI/CD",
            ),
            offtax=("MLflow", "Kubeflow", "SageMaker", "ONNX"),
            titles_en=("Machine Learning Engineer", "ML Engineer", "AI Engineer"),
            titles_fr=("Ingénieur Machine Learning", "Ingénieur IA", "Ingénieur Deep Learning"),
            topics_en=("model serving", "training pipelines", "image analysis systems"),
            topics_fr=(
                "déploiement de modèles",
                "pipelines d'entraînement",
                "systèmes d'analyse d'images",
            ),
            fields_en=("Computer Science", "Artificial Intelligence", "Software Engineering"),
            fields_fr=("Informatique", "Intelligence Artificielle", "Génie logiciel"),
        ),
        Family(
            "data_analyst",
            core=("SQL", "Excel", "Power BI", "Tableau", "Data Analysis", "Python"),
            extras=("Pandas", "Statistics", "Google Analytics", "MySQL", "Snowflake"),
            offtax=("Looker", "Qlik Sense", "Cognos", "MicroStrategy"),
            titles_en=("Data Analyst", "Business Intelligence Analyst", "Reporting Analyst"),
            titles_fr=("Data Analyst", "Analyste BI", "Analyste de données"),
            topics_en=("sales dashboards", "KPI reporting", "ad hoc analyses"),
            topics_fr=(
                "tableaux de bord commerciaux",
                "reporting des indicateurs",
                "analyses ponctuelles",
            ),
            fields_en=("Economics", "Business Analytics", "Statistics"),
            fields_fr=("Économie", "Informatique décisionnelle", "Statistique"),
        ),
        Family(
            "data_engineer",
            core=("Python", "SQL", "Spark", "Airflow", "ETL", "Kafka"),
            extras=("AWS", "GCP", "Docker", "Snowflake", "BigQuery", "Hadoop", "dbt", "PostgreSQL"),
            offtax=("Talend", "Databricks", "Informatica", "Glue"),
            titles_en=("Data Engineer", "Senior Data Engineer", "Big Data Engineer"),
            titles_fr=("Data Engineer", "Ingénieur Data", "Ingénieur Big Data"),
            topics_en=("data pipelines", "a data lake", "streaming ingestion"),
            topics_fr=("pipelines de données", "un data lake", "l'ingestion en temps réel"),
            fields_en=("Computer Science", "Software Engineering", "Information Systems"),
            fields_fr=("Informatique", "Génie logiciel", "Systèmes d'information"),
        ),
        Family(
            "backend_java",
            core=("Java", "Spring", "SQL", "PostgreSQL", "REST API", "Microservices", "Git"),
            extras=("Docker", "Kubernetes", "Redis", "Kafka", "JUnit", "CI/CD", "Jenkins"),
            offtax=("Hibernate", "Maven", "JPA", "Quarkus"),
            titles_en=("Java Developer", "Backend Engineer", "Senior Java Engineer"),
            titles_fr=("Développeur Java", "Ingénieur Backend", "Développeur Back-end Java"),
            topics_en=("payment services", "internal APIs", "order management"),
            topics_fr=("services de paiement", "API internes", "gestion des commandes"),
            fields_en=("Computer Science", "Software Engineering"),
            fields_fr=("Informatique", "Génie logiciel"),
        ),
        Family(
            "backend_python",
            core=("Python", "SQL", "PostgreSQL", "REST API", "Docker", "Git"),
            extras=(
                "FastAPI",
                "Django",
                "Flask",
                "Redis",
                "Kubernetes",
                "CI/CD",
                "pytest",
                "Microservices",
            ),
            offtax=("Celery", "SQLAlchemy", "Gunicorn", "uWSGI"),
            titles_en=("Python Developer", "Backend Developer", "Software Engineer"),
            titles_fr=("Développeur Python", "Développeur Back-end", "Ingénieur Logiciel"),
            topics_en=("web services", "internal tools", "an API platform"),
            topics_fr=("services web", "outils internes", "une plateforme d'API"),
            fields_en=("Computer Science", "Software Engineering"),
            fields_fr=("Informatique", "Génie logiciel"),
        ),
        Family(
            "frontend",
            core=("JavaScript", "TypeScript", "React", "HTML", "CSS", "Git"),
            extras=(
                "Angular",
                "Vue.js",
                "Next.js",
                "Node.js",
                "Tailwind CSS",
                "Figma",
                "jQuery",
                "REST API",
            ),
            offtax=("Redux", "Webpack", "Storybook", "Jest"),
            titles_en=("Frontend Developer", "React Developer", "UI Engineer"),
            titles_fr=("Développeur Front-end", "Développeur React", "Intégrateur Web"),
            topics_en=("a design system", "customer web apps", "an e-commerce interface"),
            topics_fr=("un design system", "des applications web", "une interface e-commerce"),
            fields_en=("Computer Science", "Web Design", "Multimedia"),
            fields_fr=("Informatique", "Design web", "Multimédia"),
        ),
        Family(
            "devops",
            core=("Docker", "Kubernetes", "Terraform", "CI/CD", "Linux", "Ansible"),
            extras=(
                "AWS",
                "Azure",
                "GitLab CI",
                "Prometheus",
                "Grafana",
                "Bash",
                "GitHub Actions",
                "Jenkins",
            ),
            offtax=("Helm", "ArgoCD", "Packer", "Vault"),
            titles_en=("DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer"),
            titles_fr=("Ingénieur DevOps", "Ingénieur Cloud", "Administrateur Systèmes"),
            topics_en=("infrastructure automation", "deployment pipelines", "platform reliability"),
            topics_fr=(
                "l'automatisation de l'infrastructure",
                "les pipelines de déploiement",
                "la fiabilité de la plateforme",
            ),
            fields_en=("Computer Science", "Network Engineering", "Information Systems"),
            fields_fr=("Informatique", "Réseaux", "Systèmes d'information"),
        ),
        Family(
            "marketing",
            core=("SEO", "Google Analytics", "Project Management", "Excel"),
            extras=("Salesforce", "Figma", "Jira", "Agile"),
            offtax=("HubSpot", "Mailchimp", "SEMrush", "Canva", "Meta Ads", "LinkedIn Ads"),
            titles_en=("Digital Marketing Manager", "Growth Marketer", "SEO Specialist"),
            titles_fr=("Responsable Marketing Digital", "Chargé de Marketing", "Consultant SEO"),
            topics_en=("acquisition campaigns", "the content strategy", "brand awareness"),
            topics_fr=(
                "les campagnes d'acquisition",
                "la stratégie de contenu",
                "la notoriété de marque",
            ),
            fields_en=("Marketing", "Communication", "Business Administration"),
            fields_fr=("Marketing", "Communication", "Gestion"),
        ),
    )
}

# Familles voisines : un candidat de la famille B n'est pas hors sujet pour une offre de la famille A.
ADJACENT: frozenset[frozenset[str]] = frozenset(
    frozenset(pair)
    for pair in (
        ("data_scientist", "ml_engineer"),
        ("data_scientist", "data_analyst"),
        ("data_analyst", "data_engineer"),
        ("data_engineer", "data_scientist"),
        ("ml_engineer", "backend_python"),
        ("backend_java", "backend_python"),
        ("backend_python", "devops"),
        ("devops", "backend_java"),
        ("frontend", "backend_python"),
        ("frontend", "backend_java"),
    )
)

# Formes d'écriture alternatives (FR/EN, abréviations). La première est le nom canonique.
SURFACE: dict[str, tuple[str, ...]] = {
    "Machine Learning": ("Machine Learning", "apprentissage automatique", "ML"),
    "Deep Learning": ("Deep Learning", "apprentissage profond"),
    "NLP": ("NLP", "traitement du langage naturel"),
    "Data Analysis": ("Data Analysis", "analyse de données"),
    "Statistics": ("Statistics", "statistiques"),
    "Project Management": ("Project Management", "gestion de projet"),
    "CI/CD": ("CI/CD", "intégration continue"),
    "Kubernetes": ("Kubernetes", "K8s"),
    "PostgreSQL": ("PostgreSQL", "Postgres"),
    "Agile": ("Agile", "méthodes agiles"),
    "Microservices": ("Microservices", "architecture microservices"),
    "REST API": ("REST API", "API REST"),
}


def surface(skill: str, choice: float) -> str:
    """Forme d'écriture d'une compétence : `choice` (0 à 1) sélectionne parmi les variantes."""
    forms = SURFACE.get(skill, (skill,))
    return forms[int(choice * len(forms)) % len(forms)]


def are_adjacent(a: str, b: str) -> bool:
    return frozenset((a, b)) in ADJACENT
