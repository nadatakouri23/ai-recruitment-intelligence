# Architecture (état actuel : Phases 0 à 2, 4, 5 et 6)

> Ce document décrit ce qui **existe**. Les modules prévus sont signalés comme tels.

## Vue d'ensemble

```
Navigateur / client HTTP
        │
        ▼
 FastAPI (backend/app)
   api/health.py, api/deps.py
   modules/authentication/ (router → service → repository → models)
   core/ (config, logging, database, security)
        │  SQLAlchemy (session par requête) + Alembic (migrations)
        ▼
 PostgreSQL 16 + pgvector (conteneur Docker, port hôte 5433)
   table users  (pgvector activé, pas encore utilisé)
```

## Pipeline d'import d'un CV (`POST /candidates`)

```
fichier ─▶ validation (taille, extension, signature) ─▶ doublon ? (SHA-256 par propriétaire)
       ─▶ extraction du texte (PDF/DOCX) ─▶ nettoyage ─▶ sections ─▶ extracteurs ─▶ CandidateProfile
       ─▶ fichier écrit sous un UUID ─▶ transaction : documents + candidates (profil JSONB)
```
Tout échec après l'écriture du fichier le supprime (pas de fichier orphelin). Les requêtes de lecture
filtrent toujours par propriétaire.

## Pipeline de recherche (`POST /search/candidates`)

```
import d'un CV ─▶ passages (≤ 70 mots, sections liées au poste, sans identité)
             ─▶ [si EMBEDDING_PROVIDER ≠ none] vecteurs de 384 dimensions ─▶ candidate_chunks (pgvector, HNSW)
requête ─▶ mots-clés : TF-IDF sur les passages ─┐
        ─▶ sémantique : similarité cosinus (SQL) ─┴▶ fusion des RANGS (RRF) ─▶ candidats + passage justificatif
```
Un échec d'indexation n'annule jamais l'import d'un CV ; `/search/reindex` rattrape. Chaque vecteur
porte le nom du modèle qui l'a produit. Le filtre par propriétaire est dans la requête vectorielle.

## Pipeline de matching (`POST /jobs/{id}/matches`)

```
offre (JobProfile)  ─┐
candidats du recruteur ─▶ texte anonymisé (sans en-tête, langues, centres d'intérêt)
                         ├─ compétences     (couverture requis 80 % / optionnel 20 %)
                         ├─ expérience      (années sur postes mobilisant les compétences de l'offre)
                         ├─ niveau d'études (niveau seulement, pas l'établissement)
                         ├─ TF-IDF          (cosinus, formule de scikit-learn)
                         ├─ mots-clés       (mots de l'offre retrouvés)
                         └─ sémantique      (embeddings ; poids 0 par défaut, voir ADR-005)
        ─▶ poids normalisés (composantes non évaluables écartées) ─▶ score 0-100 + explications
        ─▶ tri (égalités : identifiant croissant) ─▶ ajout du nom pour l'affichage (sauf mode anonyme)
```
Le moteur (`engine.rank`) est une fonction pure : il sera réutilisé tel quel par l'évaluation (Phase 5).

Chaîne d'une requête protégée : jeton Bearer → `get_current_user` (décodage JWT, lecture de
l'utilisateur, refus s'il est inactif) → `require_admin` si nécessaire → route.

## Responsabilités

| Composant | Rôle | État |
|---|---|---|
| `app/main.py` | Application factory `create_app(settings)` ; configure le logging ; assemble les routeurs | Implémenté |
| `app/core/config.py` | Configuration typée et validée au démarrage (`pydantic-settings`), secrets en `SecretStr` | Implémenté |
| `app/core/logging.py` | Logs structurés (`structlog`) : console en développement, JSON sinon | Implémenté |
| `app/api/health.py` | Route `GET /health` | Implémenté |
| `app/core/database.py` | Moteur SQLAlchemy, fabrique de sessions, `Base` | Implémenté |
| `app/core/security.py` | Hachage Argon2, JWT | Implémenté |
| `app/api/deps.py` | Dépendances : session, utilisateur courant, rôle admin | Implémenté |
| `app/modules/authentication/` | Inscription, connexion, profil, liste admin | Implémenté |
| `app/modules/documents/` | Validation d'upload, extraction PDF/DOCX, stockage UUID, modèle `Document` | Implémenté |
| `app/modules/candidates/` | Import de CV, profil structuré, recherche, suppression | Implémenté |
| `app/modules/candidates/parsing/` | Analyse par règles : sections, dates, compétences, extracteurs | Implémenté |
| `app/modules/jobs/` | Offres : création avec analyse par règles, correction, liste, suppression | Implémenté (Phase 3 partielle : pas d'import de fichier) |
| `app/modules/matching/` | Moteur de classement (fonction pure), composantes, TF-IDF, poids, route | Implémenté |
| `app/modules/llm/` | Interface fournisseur (Gemini, Mistral, Groq par HTTP direct), expurgation, délimitation anti-injection, vérification des citations, extraction / résumé / analyse d'offre / explication | Implémenté (non testé en réel) |
| `app/modules/embeddings/` | Embeddings locaux (modèle réel ou doublure), découpage en passages, table pgvector + index HNSW, recherche mots-clés / sémantique / hybride (RRF), réindexation | Implémenté |
| `app/modules/evaluation/` | Métriques de classement (Precision/Recall/NDCG@K, MRR, intervalles de confiance) | Implémenté |
| `backend/evaluation/` | Banc d'essai hors application : jeu synthétique, règle de pertinence, jumeaux d'équité, rapport | Implémenté |
| `alembic/` | Migrations de schéma (4 : `users` ; `documents` et `candidates` ; `jobs` ; `candidate_chunks` avec activation de l'extension `vector`) | Implémenté |
| `app/modules/…` (documents, matching, RAG, agents…) | Modules métier suivants | **Prévu** |
| `docker-compose.yml` | PostgreSQL + pgvector pour le développement local | Implémenté |

## Flux de configuration
`.env` (local, ignoré par Git) → variables d'environnement → `Settings` (validées) → application.
`.env.example` documente les variables attendues.

## Choix structurants
- **Factory sans effet de bord à l'import** : lancer avec `uvicorn app.main:create_app --factory`.
  Les tests créent leur propre application avec leur propre configuration.
- Décisions détaillées : voir `docs/decisions/`.

## Prévu (non implémenté)
Import d'offres en fichier, RAG, agents, tableau de bord.
