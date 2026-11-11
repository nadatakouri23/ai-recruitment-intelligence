# Journal de développement

Ce journal décrit ce qui a **réellement** été fait, par qui, et ce qui reste à faire.

## Légende des contributions
- **Auteur** : décisions, validation de l'architecture, exécution et vérification des commandes.
- **Claude** (assistant IA) : rédaction du code et de la documentation, relue par l'auteur.

## Phase 0 : Fondations (2026-11-10 → 2026-11-11)

### Décisions de l'auteur
Monolithe modulaire + PostgreSQL/pgvector ; RAG écrit à la main avant LangGraph ;
CV et offres en français et en anglais ; aucun LLM avant la phase 7 ; dépôt nommé
`talent-intelligence-platform` ; logging avec `structlog` ; PostgreSQL sur le port hôte 5433.

### Travail réalisé

| Étape | Contenu | Écrit par |
|---|---|---|
| 1 | `git init`, arborescence, `.gitignore` | Claude |
| 2 | Environnement virtuel `backend/.venv` | Claude |
| 3 | `requirements.txt` (fastapi, uvicorn, pydantic-settings, structlog) | Claude |
| 4 | `core/config.py`, `.env.example` | Claude |
| 5 | `core/logging.py` | Claude |
| 6 | `main.py` (factory), `api/health.py` | Claude |
| 7 | `tests/conftest.py`, `tests/test_health.py`, config pytest | Claude |
| 8 | Configuration Ruff | Claude |
| 9 | `docker-compose.yml`, `scripts/init-db.sql` | Claude |
| 10 | `.github/workflows/ci.yml` | Claude |
| 11 | README, ADR-001, architecture, ce journal | Claude |

L'auteur a exécuté et vérifié lui-même le lancement de l'API, Ruff et pytest (2026-11-11).

### Vérifications effectuées
- `pytest` : 3 tests passent (également sur une copie sans `.env`, pour simuler la CI).
- `ruff check` et `ruff format --check` : sans erreur.
- `GET /health` : 200 `{"status":"ok"}`.
- PostgreSQL : conteneur `healthy`, extension `vector` 0.8.7 active, opérateur `<=>` fonctionnel.
- Contrôle de secrets : aucune valeur sensible dans les fichiers à commiter.

### Incidents
- Une réécriture de `health.py` via PowerShell 5.1 a corrompu l'encodage (accents) et ajouté un BOM.
  Corrigé ; Ruff a détecté le BOM. Règle adoptée : ne pas réécrire de fichiers via PowerShell.
- `app = create_app()` à l'import faisait dépendre les tests du `.env`. Supprimé au profit de
  `uvicorn --factory`.

### Problèmes connus et dette technique
- La CI n'a **pas encore été exécutée** : elle ne peut l'être qu'après un push sur GitHub.
- Aucun commit n'a été créé à ce jour.
- Les logs d'accès d'Uvicorn ne sont pas structurés (seuls ceux de l'application le sont).
- Pas de verrouillage complet des dépendances transitives.
- Avertissement de dépréciation `httpx` / `starlette.testclient` dans les tests.
- Aucun test sur `config.py` ni `logging.py`.
- Connexion à PostgreSQL depuis l'hôte (`localhost:5433`) non testée : aucun pilote Python installé.
- Pas de sauvegarde du volume PostgreSQL ; identifiants de développement uniquement.

### Prochaine phase
Phase 1 : authentification (SQLAlchemy, Alembic, JWT, rôles). L'auteur écrira le code principal.
