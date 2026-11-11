# ADR-005 : Embeddings locaux, pgvector, recherche hybride, composante sémantique à poids 0

- **Statut** : accepté (2026-11-11)
- **Décideur** : l'auteur du projet (consigne : embeddings open source, pgvector), sur proposition de
  son assistant technique (Claude)

## Contexte
TF-IDF et mots-clés ne relient pas « apprentissage automatique » à « machine learning », ni un CV
français à une requête anglaise (mesuré en Phase 5). Il faut une recherche par le sens, sans envoyer
de données personnelles à un tiers, et sans dégrader ce qui marche déjà.

## Décisions
| Sujet | Choix | Alternatives écartées |
|---|---|---|
| Modèle | **`paraphrase-multilingual-MiniLM-L12-v2`** (384 dimensions, local, CPU, FR/EN) | API d'embeddings (Mistral, Gemini) : les CV quitteraient la machine ; `multilingual-e5-small` : équivalent, mais exige des préfixes de requête et n'a pas été comparé ici |
| Stockage | **pgvector** dans la base existante, index **HNSW** (cosinus) | Base vectorielle dédiée : un service de plus, permissions à dupliquer (ADR-001) |
| Unité indexée | **Passages** de ≤ 70 mots par section, avec recouvrement d'une ligne | CV entier : le modèle ne lit que ~128 tokens et dilue le sens |
| Recherche hybride | **Fusion des rangs (RRF)** des classements lexical et sémantique | Somme pondérée des scores : TF-IDF et cosinus n'ont pas la même échelle |
| Dans le score de matching | Composante **« sémantique » à poids 0 par défaut** | L'activer d'office sans preuve de gain |
| Activation | **Désactivée par défaut** (`EMBEDDING_PROVIDER=none`) ; dépendances lourdes dans `requirements-ml.txt` | Imposer 1 Go de dépendances à tout utilisateur |
| Tests et CI | **Doublure `hashing`** (sac de mots, déterministe) ; tests du vrai modèle ignorés s'il n'est pas en cache | Télécharger le modèle à chaque exécution de la CI |
| Échec d'indexation | **Jamais bloquant** pour l'import d'un CV ; rattrapage par `/search/reindex` | Refuser l'import (perte de données pour un souci annexe) |

## Règle d'activation, fixée AVANT l'évaluation finale
Rédigée après la passe de développement (graine 1) et avant de calculer le résultat sur la graine
vierge 4242 :

1. La composante sémantique **ne passe de 0 à 20 % du score par défaut** que si, sur la graine 4242,
   l'écart de NDCG@10 « défaut + sémantique (20 %) − défaut » est **≥ +0,01** ET que son intervalle de
   confiance à 95 % **exclut 0**. Sinon elle reste à 0.
2. Le mode de recherche par défaut (`auto`) reste « hybride » **seulement si** l'hybride n'est pas
   significativement moins bon que les mots-clés sur les requêtes descriptives ET meilleur ou égal sur
   les requêtes à outils ; sinon `auto` redevient « mots-clés ».
3. Aucun changement du code, des requêtes ou des poids après avoir vu le résultat sur 4242.

## Résultat de la règle d'activation (graine 4242)
- Règle 1 : écart « défaut + sémantique − défaut » = **−0,005** [−0,02 ; +0,02] → **non satisfaite, poids
  sémantique laissé à 0**.
- Règle 2 : hybride = mots-clés sur les requêtes descriptives (0,734 contre 0,734), meilleur sur les
  requêtes à outils (0,931 contre 0,874) → **satisfaite, `auto` reste « hybride »**.
- Détails et réserves : `docs/evaluation/semantic.md`.

## Équité par conception
- Les passages sont construits avec les mêmes règles que le matching : **ni en-tête, ni langues
  parlées, ni centres d'intérêt**. Le nom d'un candidat n'est donc jamais vectorisé.
- Les vecteurs portent le **nom du modèle** : on ne compare jamais des vecteurs de modèles différents.
- Le filtre par propriétaire figure dans la requête vectorielle elle-même (vérifié par mutation).

Ajout après mesure : toute vectorisation passe par **`embed_texts`**, qui neutralise d'abord les
formes féminines de métiers (la mesure avait montré que 32 % des scores sémantiques changeaient entre
« Ingénieure » et « Ingénieur »). Un test structurel interdit d'appeler le modèle autrement.

## Risques résiduels
- (!) **Mesuré** : remplacer les villes modifie 98 % des scores sémantiques (3,4 points au maximum) et
  5 % du top 10, bien plus que pour le lexical. Non corrigé.
- (!) Les **passages de formation contiennent le nom des écoles**, et ceux d'expérience les **villes** :
  un modèle d'embedding peut y encoder du prestige ou une origine géographique. Non mesuré sur des
  données réelles ; l'audit de proxys de la Phase 5 reste limité à des écarts de texte.
- (!) Les modèles d'embedding apprennent les biais de leurs données d'entraînement (genre, origine)
  d'une façon qu'on ne peut pas inspecter ligne à ligne.
- (−) Le modèle ne lit que ~128 tokens : une longue expérience est coupée en plusieurs passages.
- (−) Un passage « proche par le sens » n'est pas un passage « qualifié » : la recherche sémantique
  remonte aussi des profils seulement voisins (d'où l'affichage du passage justificatif).
- (−) Licence du modèle à vérifier avant tout usage commercial.
