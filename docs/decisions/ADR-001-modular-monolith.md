# ADR-001 : Monolithe modulaire, PostgreSQL + pgvector

- **Statut** : accepté (2026-11-10)
- **Décideur** : l'auteur du projet, sur proposition de son assistant technique (Claude)

## Contexte
Le projet est une plateforme d'analyse de CV et d'offres d'emploi, développée par une seule
personne, avec des fonctionnalités IA à ajouter progressivement (matching, recherche
sémantique, RAG, agents). Les données sont personnelles (CV) : sécurité et contrôle d'accès
sont des exigences d'architecture.

## Décisions
1. **Monolithe modulaire** : un seul backend FastAPI, découpé en modules aux frontières claires
   (`api/`, `core/`, puis `modules/…`).
2. **PostgreSQL + pgvector** : une seule base pour les données relationnelles et les vecteurs.

## Alternatives considérées
| Sujet | Alternative | Raison du rejet |
|---|---|---|
| Architecture | Microservices | Complexité de déploiement, de tests et de réseau injustifiée pour un projet solo |
| Vecteurs | Base vectorielle dédiée (Qdrant, Pinecone, Chroma) | Un service de plus à opérer, permissions à dupliquer, pas de jointures SQL avec les documents |
| Vecteurs | SQLite | Pas de pgvector, pas adapté à la production |

## Conséquences
- (+) Transactions, jointures et permissions communes aux données et aux vecteurs.
- (+) Un seul composant à sauvegarder et à sécuriser.
- (−) Les performances de recherche vectorielle à très grande échelle seront inférieures à un
  moteur spécialisé. À réévaluer si le volume le justifie (mesure à l'appui).
- (−) Le dimensionnement de l'index vectoriel est à notre charge.

## À revoir
Cette décision sera réexaminée en Phase 6 (recherche sémantique), avec des mesures réelles.
