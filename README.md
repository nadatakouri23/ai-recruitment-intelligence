# Talent Intelligence Platform

Plateforme d'aide au recrutement : analyse de CV et d'offres d'emploi, classement explicable
des candidats, recherche sémantique et assistant IA. Elle **assiste** le recruteur et ne prend
aucune décision d'embauche ; les caractéristiques protégées ne sont jamais utilisées comme
critère de classement.

> **État : en construction (Phase 0 terminée côté code, fondations uniquement).**
> Aucune fonctionnalité métier n'est encore implémentée.

## Ce qui existe aujourd'hui
- API FastAPI minimale avec `GET /health`
- Configuration validée au démarrage, secrets non exposés
- Logs structurés (`structlog`)
- Tests (`pytest`), lint et formatage (`Ruff`)
- PostgreSQL 16 + pgvector via Docker Compose
- Workflow CI GitHub Actions (écrit, pas encore exécuté)

## Ce qui est prévu (non implémenté)
Authentification JWT, import et parsing de CV (PDF/DOCX), analyse d'offres, matching
(TF-IDF puis embeddings), recherche sémantique, RAG avec citations, LLM multi-fournisseurs,
agents LangGraph, tableau de bord React. Voir `docs/` pour l'architecture et les décisions.

## Technologies
Python 3.12 · FastAPI · Pydantic · structlog · pytest · Ruff · Docker Compose · PostgreSQL + pgvector

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
uvicorn app.main:create_app --factory --reload         # API sur http://localhost:8000
```
Vérifier : `http://localhost:8000/health` et `http://localhost:8000/docs`.

## Qualité
```powershell
cd backend
ruff check .
ruff format --check .
pytest -v
```

## Configuration
Voir `.env.example`. Le fichier `.env` ne doit jamais être commité.

## Limites actuelles
Voir `DEVELOPMENT_LOG.md` (problèmes connus et dette technique).

## Données et vie privée
Le projet n'utilise que des données **synthétiques** ou autorisées. Aucun CV réel ne doit être
ajouté au dépôt (`data/uploads/` est ignoré par Git).

## Documentation
- `docs/architecture/overview.md`
- `docs/decisions/` (ADR)
- `DEVELOPMENT_LOG.md` : travail réalisé et contributions
