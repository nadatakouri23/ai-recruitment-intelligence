# Architecture (état actuel : Phase 0)

> Ce document décrit ce qui **existe**. Les modules prévus sont signalés comme tels.

## Vue d'ensemble

```
Navigateur / client HTTP
        │
        ▼
 FastAPI (backend/app)         PostgreSQL 16 + pgvector
   api/health.py  ────────────  (conteneur Docker, port hôte 5433)
   core/config.py                 ▲
   core/logging.py                │  pas encore relié : SQLAlchemy arrive en Phase 1
```

## Responsabilités

| Composant | Rôle | État |
|---|---|---|
| `app/main.py` | Application factory `create_app(settings)` ; configure le logging ; assemble les routeurs | Implémenté |
| `app/core/config.py` | Configuration typée et validée au démarrage (`pydantic-settings`), secrets en `SecretStr` | Implémenté |
| `app/core/logging.py` | Logs structurés (`structlog`) : console en développement, JSON sinon | Implémenté |
| `app/api/health.py` | Route `GET /health` | Implémenté |
| `app/modules/…` | Modules métier (authentification, documents, matching, RAG, agents…) | **Prévu**, dossier vide |
| `docker-compose.yml` | PostgreSQL + pgvector pour le développement local | Implémenté |

## Flux de configuration
`.env` (local, ignoré par Git) → variables d'environnement → `Settings` (validées) → application.
`.env.example` documente les variables attendues.

## Choix structurants
- **Factory sans effet de bord à l'import** : lancer avec `uvicorn app.main:create_app --factory`.
  Les tests créent leur propre application avec leur propre configuration.
- Décisions détaillées : voir `docs/decisions/`.

## Prévu (non implémenté)
Authentification JWT, parsing de CV, matching, embeddings, RAG, agents, tableau de bord.
