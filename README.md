# Talent Intelligence Platform

Plateforme d'aide au recrutement : analyse de CV et d'offres d'emploi, classement explicable
des candidats, recherche sémantique et assistant IA. Elle **assiste** le recruteur et ne prend
aucune décision d'embauche ; les caractéristiques protégées ne sont jamais utilisées comme
critère de classement.

> **État : en construction (Phases 0 à 2, 4, 5 et 6 réalisées, Phase 3 partielle).**
> Le RAG, les LLM, les agents et l'interface web ne sont pas encore implémentés. Le classement a été évalué (Phase 5) **uniquement sur un jeu synthétique écrit par
> nous** : aucune validation par de vrais recruteurs (voir `docs/evaluation/matching.md`).

## Ce qui existe aujourd'hui
- **Recherche de candidats** par mots-clés (TF-IDF), par le sens (embeddings multilingues locaux +
  pgvector) ou hybride, avec le passage du CV qui justifie chaque résultat. Les embeddings sont
  **optionnels et désactivés par défaut**. Mesuré : le sémantique relie le français et l'anglais, mais
  n'améliore **pas** le score de matching par défaut (voir `docs/evaluation/semantic.md`).
- **Couche LLM optionnelle** (Gemini, Mistral ou Groq, **désactivée par défaut**) : extraction de
  profil, résumé de CV, analyse d'offre et explication d'un classement. Consentement exigé à chaque
  appel, texte anonymisé, chaque affirmation vérifiée par une citation exacte du document, aucune
  suggestion appliquée automatiquement. **Testée en réel seulement par un appel minimal** (Groq et Gemini ; Mistral jamais) : voir `docs/decisions/ADR-006-llm-layer.md`.
- **Offres d'emploi** : texte libre analysé automatiquement (compétences requises/optionnelles,
  expérience, niveau d'études, missions), corrigeable par le recruteur.
- **Classement explicable des candidats** pour une offre : score de 0 à 100 décomposé en 5 composantes
  (compétences, expérience pertinente, niveau d'études, TF-IDF, mots-clés), poids configurables,
  compétences trouvées et manquantes avec preuves, explications, confiance et limites. Le nom, les
  contacts, les langues parlées et les centres d'intérêt n'entrent pas dans le calcul ; un mode
  anonyme les retire aussi de la réponse. C'est une **aide à la décision**, pas une décision.
- **Import de CV** (PDF et DOCX, français et anglais) : extraction du texte puis profil structuré
  (compétences, expérience, formation, projets, langues, certifications) avec la source de chaque
  information. Analyse **par règles**, sans LLM ; ses limites sont affichées avec chaque profil.
- Recherche de vos candidats par nom et par compétence (« apprentissage automatique » = « machine learning »)
- Chaque recruteur ne voit que ses propres candidats ; suppression complète (fichier + texte extrait)
- Authentification : inscription, connexion (JWT), profil, rôles `recruiter` / `admin`
- Mots de passe hachés avec Argon2 ; routes protégées ; liste des utilisateurs réservée aux admins
- PostgreSQL relié à l'API (SQLAlchemy) avec migrations Alembic
- API FastAPI avec `GET /health`
- Configuration validée au démarrage, secrets non exposés
- Logs structurés (`structlog`)
- Tests (`pytest`), lint et formatage (`Ruff`)
- PostgreSQL 16 + pgvector via Docker Compose
- Workflow CI GitHub Actions (écrit, pas encore exécuté)

## Ce qui est prévu (non implémenté)
Recherche sémantique par embeddings (avec comparaison à la baseline TF-IDF actuelle), évaluation
du classement (Precision@K, NDCG@K), import d'offres en fichier, RAG avec citations, agents LangGraph, tableau de bord React. Voir `docs/` pour l'architecture et
les décisions.

## Technologies
Python 3.12 · FastAPI · Pydantic · SQLAlchemy · Alembic · Argon2 · PyJWT · pdfplumber · python-docx · structlog · pytest · Ruff · Docker Compose · PostgreSQL + pgvector

## Prérequis
Python 3.12, Docker Desktop, Git.

## Installation
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cd ..
copy .env.example .env      # puis remplacer POSTGRES_PASSWORD par une valeur de développement
```

## Lancement
```powershell
docker compose up -d                                   # base de données (racine du projet)
cd backend
alembic upgrade head                                   # crée les tables (première fois, puis à chaque migration)
uvicorn app.main:create_app --factory --reload         # API sur http://localhost:8000
```
Vérifier : `http://localhost:8000/health` et `http://localhost:8000/docs`.

Dans Swagger (`/docs`) : `POST /auth/register`, puis le bouton **Authorize** (e-mail dans
`username` + mot de passe) pour appeler `GET /users/me`.

### Essayer avec des CV (synthétiques)
```powershell
backend\.venv\Scripts\python.exe scripts\generate_sample_cvs.py     # (re)génère data\samples\cvs\
```
Puis dans Swagger (`/docs`), après **Authorize** : `POST /candidates` avec un fichier de
`data/samples/cvs/`, et `GET /candidates?skill=machine learning`. N'envoyez jamais de CV réels de
tierces personnes sans leur autorisation.

### Classer des candidats pour une offre
Dans Swagger, après avoir importé quelques CV : `POST /jobs` avec un titre et le texte d'une offre
(vérifiez les compétences détectées, corrigez-les au besoin avec `PATCH /jobs/{id}`), puis
`POST /jobs/{id}/matches`. Corps facultatif :
```json
{"weights": {"skills": 3, "experience": 1, "tfidf": 0, "keyword": 0, "education": 0},
 "limit": 20, "min_score": 0, "anonymize": true}
```
Poids par défaut modifiables via la variable `MATCHING_WEIGHTS` (voir `.env.example`). Le score est
**relatif** à l'offre et au lot de candidats ; il ne mesure ni la compétence réelle ni l'aptitude au
poste.

### Rechercher des candidats (mots-clés, sémantique, hybride)
`POST /search/candidates` avec `{"query": "...", "mode": "auto"}`. Le passage du CV qui justifie chaque
résultat est renvoyé. Sans embeddings (défaut), seule la recherche par **mots-clés** est disponible ;
`GET /search/status` indique l'état de l'index.

Pour activer la recherche **par le sens** (français ↔ anglais), avec un modèle local :
```powershell
cd backend
pip install -r requirements-ml.txt          # PyTorch + sentence-transformers (~1 Go)
# dans .env :  EMBEDDING_PROVIDER=sentence_transformers   (le modèle ~450 Mo est téléchargé au 1er usage)
alembic upgrade head
```
Puis `POST /search/reindex` indexe les candidats déjà importés. Les nouveaux CV sont indexés à l'import.
Résultats mesurés : `docs/evaluation/semantic.md` (le sémantique n'est **pas** toujours meilleur).

### Évaluer le classement
```powershell
cd backend
.venv\Scripts\python.exe -m evaluation.run --seed 1 --output ..\docs\evaluation\matching-results-dev.md
```
Génère un jeu de CV/offres synthétiques, les classe avec le vrai moteur et écrit un rapport
(Precision@K, Recall@K, NDCG@K, comparaison des composantes, sensibilité aux poids, langue, équité).
La graine 1 sert à explorer ; la graine 2024 est réservée au résultat final (voir `docs/evaluation/`).

### Créer le premier administrateur
L'inscription publique crée toujours un recruteur. Pour un administrateur (depuis `backend/`) :
```powershell
python -m app.cli.create_admin --email admin@example.com --name "Admin"
```
Le mot de passe (12 caractères minimum) est demandé de façon masquée.

## Qualité
```powershell
cd backend
ruff check .
ruff format --check .
pytest -v
```

Les tests d'intégration utilisent une base dédiée `<POSTGRES_DB>_test`, créée automatiquement
(Docker doit être démarré). Ils ne touchent jamais à la base de développement.

## Configuration
Voir `.env.example`. Le fichier `.env` ne doit jamais être commité. Générer un secret JWT :
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

## Limites actuelles
- L'analyse des CV est **par règles** : un CV à colonnes ou à la mise en page atypique peut être mal
  lu, et seules 136 compétences (surtout techniques) sont reconnues.
- **L'évaluation du classement est synthétique** : NDCG@10 de 0,92 sur 11 offres et 126 CV générés
  par nous, contre 0,19 au hasard. Ce chiffre ne prédit pas la performance sur de vrais CV. Les poids
  par défaut ne sont pas démontrés optimaux (les deux jeux d'essai se contredisent). Le TF-IDF ne
  reconnaît pas les synonymes et se dégrade quand l'offre et le CV n'ont pas la même langue. Des proxys de
  biais subsistent (sociétés, villes, écoles citées dans le CV). Voir `docs/evaluation/matching.md`.
- **Les embeddings sont plus sensibles aux proxys géographiques que le lexical** (changer les villes
  d'un CV modifie 98 % des scores sémantiques, jusqu'à 3,4 points). Les noms d'écoles et de villes
  restent dans les passages vectorisés. Pas de validation sur de vrais CV.
- **Couche LLM non validée en réel** : formats d'API lus dans la documentation, jamais appelés ; la
  qualité d'extraction et la résistance des vrais modèles aux CV piégés ne sont pas mesurées. Les
  citations garantissent qu'une affirmation figure dans le CV, pas qu'elle soit vraie.
- Les PDF **scannés** (images) sont refusés : pas de reconnaissance de caractères (OCR).
- Les mesures de qualité actuelles portent sur 6 CV synthétiques écrits par nous : elles servent de
  garde-fou contre les régressions, **pas d'estimation de la performance réelle** (voir
  `docs/evaluation/cv-parsing.md`).
- Fichiers et texte extrait stockés **en clair** : à chiffrer avant tout usage réel.
- Voir aussi `DEVELOPMENT_LOG.md` (problèmes connus et dette technique).

## Données et vie privée
Le projet n'utilise que des données **synthétiques** ou autorisées. Aucun CV réel ne doit être
ajouté au dépôt (`data/uploads/` est ignoré par Git).

## Documentation
- `docs/architecture/overview.md`
- `docs/decisions/` (ADR)
- `DEVELOPMENT_LOG.md` : travail réalisé et contributions
