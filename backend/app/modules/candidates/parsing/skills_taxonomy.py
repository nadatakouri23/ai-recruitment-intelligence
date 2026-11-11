"""Référentiel de compétences bilingue (FR/EN).

Chaque compétence a un nom canonique unique et des alias (les alias français et anglais
pointent vers le même nom). Les alias sont écrits en minuscules SANS accents.

Les « strict_aliases » (lettres isolées comme R, C, Go) sont trop ambigus pour être cherchés
partout : ils ne sont reconnus qu'avec la casse exacte et dans les sections de compétences
et de projets.

Ce référentiel est volontairement limité (techno, data, cloud, quelques compétences métier) :
une compétence absente de la liste n'est PAS détectée. Il est à enrichir au fil des besoins.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillDef:
    name: str
    category: str
    aliases: tuple[str, ...]
    strict_aliases: tuple[str, ...] = ()


def _s(
    name: str,
    category: str,
    *aliases: str,
    strict: tuple[str, ...] = (),
    name_alias: bool = True,
) -> SkillDef:
    """`name_alias=False` : le nom lui-même est un mot courant (« Spring », « Tableau »…) et
    ne doit pas servir d'alias libre ; seuls les alias explicites ou stricts comptent."""
    base = (name.lower(),) if name_alias else ()
    return SkillDef(name, category, (*base, *aliases), strict)


SKILLS: tuple[SkillDef, ...] = (
    # --- langages ---
    _s("Python", "programming", "python3"),
    _s("Java", "programming"),
    _s("JavaScript", "programming", "ecmascript", "es6"),
    _s("TypeScript", "programming"),
    _s("C++", "programming", "cpp"),
    _s("C#", "programming", "csharp"),
    _s("C", "programming", "langage c", strict=("C",), name_alias=False),
    _s("Go", "programming", "golang", strict=("Go",), name_alias=False),
    _s("R", "programming", "langage r", "r language", strict=("R",), name_alias=False),
    _s("PHP", "programming"),
    _s("Ruby", "programming"),
    _s("Rust", "programming"),
    _s("Kotlin", "programming"),
    _s("Swift", "programming"),
    _s("Scala", "programming"),
    _s("MATLAB", "programming"),
    _s("Bash", "programming", "shell scripting", "scripting shell"),
    _s("PowerShell", "programming"),
    _s("SQL", "programming"),
    _s("PL/SQL", "programming", "plsql"),
    _s("VBA", "programming"),
    _s("Dart", "programming"),
    # --- web ---
    _s("HTML", "web", "html5"),
    _s("CSS", "web", "css3"),
    _s("React", "web", "reactjs", "react.js"),
    _s("React Native", "web"),
    _s("Angular", "web", "angularjs"),
    # « vue » seul = « vue d'ensemble » en français : reconnu seulement avec la casse « Vue »
    # dans la section compétences.
    _s("Vue.js", "web", "vuejs", "vue.js", strict=("Vue",), name_alias=False),
    _s("Next.js", "web", "nextjs"),
    _s("Node.js", "web", "nodejs", "node js"),
    _s("Express.js", "web", "expressjs"),
    _s("Django", "web"),
    _s("Flask", "web"),
    _s("FastAPI", "web"),
    _s(
        "Spring",
        "web",
        "spring boot",
        "spring framework",
        "spring mvc",
        "spring security",
        strict=("Spring",),
        name_alias=False,
    ),  # fmt: skip
    _s(".NET", "web", "dotnet", "asp.net"),
    _s("Laravel", "web"),
    _s("Symfony", "web"),
    _s("Ruby on Rails", "web", "rails"),
    _s("Tailwind CSS", "web", "tailwind"),
    _s("Bootstrap", "web"),
    _s("jQuery", "web"),
    _s(
        "REST API",
        "web",
        "rest api",
        "rest apis",
        "restful",
        "api rest",
        "apis rest",
        "api restful",
        strict=("REST",),
        name_alias=False,
    ),  # fmt: skip
    _s("GraphQL", "web"),
    # --- data / ML / IA ---
    _s(
        "Machine Learning",
        "data_ml",
        "apprentissage automatique",
        "apprentissage statistique",
        "ml",
    ),
    _s("Deep Learning", "data_ml", "apprentissage profond"),
    _s(
        "NLP",
        "data_ml",
        "natural language processing",
        "traitement du langage naturel",
        "traitement automatique du langage",
    ),
    _s("Computer Vision", "data_ml", "vision par ordinateur", "vision artificielle"),
    _s("Data Science", "data_ml", "science des donnees"),
    _s("Data Analysis", "data_ml", "analyse de donnees", "data analytics", "analyse des donnees"),
    _s("Data Engineering", "data_ml", "ingenierie des donnees", "ingenierie de donnees"),
    _s("Statistics", "data_ml", "statistiques", "analyse statistique"),
    _s("TensorFlow", "data_ml"),
    _s("PyTorch", "data_ml"),
    _s("Keras", "data_ml"),
    _s("scikit-learn", "data_ml", "sklearn", "scikit learn"),
    _s("Pandas", "data_ml"),
    _s("NumPy", "data_ml"),
    _s("SciPy", "data_ml"),
    _s("Matplotlib", "data_ml"),
    _s("Hugging Face", "data_ml", "huggingface"),
    _s("spaCy", "data_ml"),
    _s("NLTK", "data_ml"),
    _s("LangChain", "data_ml"),
    _s("LangGraph", "data_ml"),
    _s(
        "LLM",
        "data_ml",
        "llms",
        "large language model",
        "large language models",
        "grands modeles de langage",
    ),
    _s("RAG", "data_ml", "retrieval-augmented generation", "retrieval augmented generation"),
    _s(
        "Generative AI", "data_ml", "genai", "ia generative", "intelligence artificielle generative"
    ),
    _s("XGBoost", "data_ml"),
    _s("Spark", "data_ml", "pyspark", "apache spark", strict=("Spark",), name_alias=False),
    _s("Hadoop", "data_ml"),
    _s("Kafka", "data_ml", "apache kafka"),
    _s("Airflow", "data_ml", "apache airflow"),
    _s("dbt", "data_ml"),
    _s("ETL", "data_ml"),
    _s("Jupyter", "data_ml", "jupyter notebook"),
    _s("Power BI", "data_ml", "powerbi"),
    # « tableau » = « table / tableau de bord » en français ; « excel » = verbe en anglais.
    _s(
        "Tableau",
        "data_ml",
        "tableau software",
        "tableau desktop",
        strict=("Tableau",),
        name_alias=False,
    ),
    _s("Excel", "tools", "microsoft excel", "ms excel", strict=("Excel",), name_alias=False),
    # --- bases de données ---
    _s("PostgreSQL", "database", "postgres"),
    _s("MySQL", "database"),
    _s("SQLite", "database"),
    _s("MongoDB", "database", "mongo"),
    _s("Redis", "database"),
    _s("Elasticsearch", "database", "elastic search"),
    _s("SQL Server", "database", "mssql", "microsoft sql server"),
    _s("Oracle", "database", "oracle database"),
    _s("NoSQL", "database"),
    _s("Cassandra", "database"),
    _s("Neo4j", "database"),
    _s("DynamoDB", "database"),
    _s("Snowflake", "database"),
    _s("BigQuery", "database"),
    _s("Pinecone", "database"),
    _s("pgvector", "database"),
    # --- cloud / devops ---
    _s("AWS", "cloud_devops", "amazon web services"),
    _s("Azure", "cloud_devops", "microsoft azure"),
    _s("GCP", "cloud_devops", "google cloud", "google cloud platform"),
    _s("Docker", "cloud_devops", "dockerfile"),
    _s("Kubernetes", "cloud_devops", "k8s"),
    _s("Terraform", "cloud_devops"),
    _s("Ansible", "cloud_devops"),
    _s("Jenkins", "cloud_devops"),
    _s("GitHub Actions", "cloud_devops"),
    _s("GitLab CI", "cloud_devops", "gitlab-ci"),
    _s("CI/CD", "cloud_devops", "cicd", "ci-cd", "integration continue", "continuous integration"),
    _s("Linux", "cloud_devops"),
    _s("Git", "cloud_devops"),
    _s("GitHub", "cloud_devops"),
    _s("GitLab", "cloud_devops"),
    _s("Nginx", "cloud_devops"),
    _s("Prometheus", "cloud_devops"),
    _s("Grafana", "cloud_devops"),
    _s("DevOps", "cloud_devops"),
    _s("MLOps", "cloud_devops"),
    _s("Microservices", "cloud_devops", "microservice", "architecture microservices"),
    # --- méthodes / outils / métier ---
    _s("Agile", "methodology", "methodes agiles", "methode agile", "methodologies agiles"),
    _s("Scrum", "methodology"),
    _s("Kanban", "methodology"),
    _s("Jira", "tools"),
    _s("Confluence", "tools"),
    _s("Figma", "tools"),
    _s("Postman", "tools"),
    _s("pytest", "tools"),
    _s("JUnit", "tools"),
    _s("Selenium", "tools"),
    _s("Unit Testing", "tools", "tests unitaires"),
    _s("UML", "methodology"),
    _s("Merise", "methodology"),
    _s(
        "Project Management",
        "business",
        "gestion de projet",
        "gestion de projets",
        "pilotage de projet",
    ),
    _s("Product Management", "business", "gestion de produit"),
    _s("SEO", "business", "referencement naturel"),
    _s("Google Analytics", "business"),
    _s("Salesforce", "business"),
    _s("SAP", "business"),
    _s("Cybersecurity", "business", "cybersecurite", "securite informatique"),
)
