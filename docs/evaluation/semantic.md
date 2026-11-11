# Évaluation de la recherche sémantique (Phase 6)

**Statut : évaluée uniquement sur le jeu SYNTHÉTIQUE de la Phase 5, avec un vrai modèle d'embeddings
(`paraphrase-multilingual-MiniLM-L12-v2`, local). Aucun recruteur n'a jugé ces résultats.** Les
requêtes, les CV, les offres et la règle de pertinence ont tous été écrits par l'auteur du système.

Rapports complets générés par `evaluation/run.py --embedder sentence_transformers` :
- `semantic-results.md` : **résultat final**, graine vierge **4242**, calculé **une seule fois**.
- `semantic-results-dev.md` : graine de développement 1 (version finale du code).

## Protocole

- **Graine 4242 jamais vue** avant la passe finale (la graine 2024 de la Phase 5 est « consommée »).
- **Règles de décision écrites avant la passe finale** (voir ADR-005) :
  1. la composante sémantique n'entre dans le score par défaut que si « défaut + sémantique (20 %) »
     dépasse le défaut d'au moins +0,01 de NDCG@10 avec un intervalle de confiance excluant 0 ;
  2. le mode de recherche `auto` reste « hybride » seulement si l'hybride n'est pas significativement
     moins bon que les mots-clés sur les requêtes descriptives et meilleur ou égal sur les requêtes à outils.
- 27 requêtes (18 **descriptives** sans nom d'outil, FR/EN, et 9 à **outils** en contrôle), écrites
  une fois pour toutes **avant** de voir les résultats et **jamais modifiées**.
- Les classements utilisent le même code que l'API (`embeddings/ranking.py`, TF-IDF, cosinus).

## Résultats sur la graine vierge 4242

### Dans le score de matching (NDCG@10, 11 offres)

| Variante | NDCG@10 [IC 95 %] |
|---|---|
| Aléatoire | 0,20 |
| TF-IDF seul | 0,76 |
| Sémantique seule | 0,81 |
| Mots-clés seuls | 0,81 |
| Compétences seules | 0,83 |
| Compétences + sémantique | 0,87 |
| **Poids par défaut (sans sémantique)** | **0,90** [0,86–0,94] |
| Défaut + sémantique (20 %) | 0,90 [0,86–0,93] |

Écart « défaut + sémantique − défaut » : **−0,005** [−0,02 ; +0,02] → **la règle 1 n'est pas satisfaite : le
poids sémantique reste à 0 par défaut.** (Sur la graine de développement l'écart était +0,006 : du bruit.)

### Effet de la langue : le vrai apport mesuré

Rang moyen (en %, 0 % = tête) des candidats les plus pertinents, selon que l'offre et le CV ont la même langue ou non :

| Variante | Même langue | Langues différentes |
|---|---|---|
| TF-IDF seul | 3,1 | **15,8** |
| **Sémantique seule** | 4,5 | **5,5** |
| Compétences seules | 4,1 | 8,5 |
| Poids par défaut | 2,6 | 8,5 |

Le sémantique **efface presque** la pénalité inter-langues du TF-IDF. C'est son principal intérêt ici.

### Recherche de candidats (NDCG@10)

| Requêtes | Mots-clés | Sémantique | Hybride (RRF) |
|---|---|---|---|
| Descriptives (18) | 0,734 | 0,656 | 0,734 |
| À outils (9) | 0,874 | 0,863 | **0,931** |

- **Sur les requêtes descriptives, le sémantique n'est PAS meilleur que les mots-clés** (−0,078,
  intervalle [−0,22 ; +0,07] : indécidable ; sur la graine de développement il était significativement
  moins bon, −0,138). Résultat contraire à l'intuition, voir « Pourquoi » ci-dessous.
- L'hybride égale les mots-clés sur les requêtes descriptives et fait mieux sur les requêtes à outils :
  **la règle 2 est satisfaite, `auto` reste « hybride ».**
- Effet de la langue, requêtes descriptives (rang relatif en %) : mots-clés 11,1 → **26,1** ;
  sémantique 15,1 → **16,7** ; hybride 8,1 → 19,2. Le sémantique est le seul mode peu sensible à la langue, mais il part d'un niveau moins bon.

## Pourquoi le sémantique ne gagne pas sur les requêtes descriptives (diagnostic sur la graine dev)

- **Mes requêtes sont ambiguës** : « développeur d'applications serveur avec services web » convient
  autant à un profil Python qu'à un profil Java ; la règle de référence n'en accepte qu'un. Les deux
  méthodes obtiennent 0/10 sur cette requête.
- **Les mots génériques dominent le sens** : « ingénieur qui met en production des réseaux de
  neurones » a remonté 5 profils *frontend* parce que leurs intitulés contiennent « ingénieur ».
- **Mes CV et mes requêtes partagent des tournures** (« modèles prédictifs », « services web »), ce qui
  avantage les mots-clés. Sur de vrais CV, plus variés, l'avantage lexical serait moindre, mais ce n'est pas mesuré.
- Les passages de CV sont surtout des listes d'outils et des puces à modèle de phrase : peu de sens à capter.

Je n'ai **pas** réécrit les requêtes pour avantager le sémantique : cela aurait invalidé le protocole.

## Équité du composant sémantique

Même méthode que pour le lexical (un CV et son « jumeau » qui ne diffère que par un élément) :

| Élément modifié | Scores qui changent | Δ max (sur 100) | Top-10 conservé |
|---|---|---|---|
| Identité (nom, contacts, titre d'en-tête, langues parlées) | 0 % | 0,00 | 100 % |
| Genre des intitulés (« Ingénieure » / « Ingénieur ») | 0 % | 0,00 | 100 % |
| **Villes (employeurs, école)** | **98 %** | **3,37** | **95 %** |

- **Défaut trouvé puis corrigé** : avant correction, 32 % des scores changeaient (jusqu'à 0,86 point)
  entre « Ingénieure » et « Ingénieur », parce que la neutralisation du genre ne s'appliquait qu'aux
  mots du TF-IDF, pas au texte envoyé au modèle. Désormais toute vectorisation passe par
  `embed_texts`, qui neutralise d'abord les formes féminines connues (un test structurel interdit de
  contourner ce point d'entrée).
- **Risque non résolu** : changer les villes modifie presque tous les scores sémantiques (en moyenne
  0,6 point, jusqu'à 3,4) et 5 % des places du top 10. Les écoles et les villes restent dans les
  passages. C'est **nettement plus sensible que le lexical** (Phase 5 : 21 % des scores, 0,43 point au
  maximum, top 10 inchangé). Ce test ne mesure que des changements de ville : il ne dit rien des
  corrélations réelles entre origine et parcours, ni du prestige d'une école.
- La neutralisation du genre reste **partielle** (≈ 25 formes françaises).

## Ce qu'on peut affirmer / ne pas affirmer

**Affirmable sur ce jeu** : le sémantique relie bien le français et l'anglais (similarité 0,93–0,95 entre
phrases équivalentes contre 0,00–0,22 pour la doublure lexicale) ; il comble l'écart inter-langues du
TF-IDF ; combiné à l'hybride il améliore les requêtes à outils ; il n'améliore pas le score de matching
par défaut.

**Non affirmable** : que le sémantique aide sur de vrais CV et de vraies requêtes ; qu'il soit plus
équitable ou moins ; que 20 % soit le bon poids ; que les différences de 0,01 à 0,03 soient réelles.
Avec 11 offres et 27 requêtes, les intervalles de confiance sont larges.

## Reproduire

```powershell
cd backend
pip install -r requirements-ml.txt
.venv\Scripts\python.exe -m evaluation.run --seed 4242 --embedder sentence_transformers --output ..\docs\evaluation\semantic-results.md
```
Une à deux minutes, le modèle (~450 Mo) étant déjà en cache.
