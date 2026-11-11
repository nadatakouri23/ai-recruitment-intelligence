# Résultats d'évaluation du matching — graine 4242

> **À lire avant les chiffres.** Ce jeu est SYNTHÉTIQUE : candidats, offres et règle de pertinence
> ont été écrits par la même personne (Claude). Aucun recruteur n'a jugé ces classements. Ces
> résultats mesurent la cohérence du système avec une règle explicite sur des CV propres et
> homogènes ; ils ne prédisent PAS la performance sur de vrais CV, qui sera inférieure.

## Jeu de données

- Graine **4242** ; 126 candidats (9 familles de métiers × 14), 11 offres (9 mono-famille + 2 hybrides).
- CV en français et en anglais (mélangés), PDF et DOCX, rendus en vrais fichiers puis relus par le pipeline.
- Offres et CV de langues indépendantes : une partie des paires est inter-langues.
- Pertinence 0 à 3 calculée sur des attributs CACHÉS (voir `evaluation/generator.py::gold_grade`). Par offre : 11–37 candidats pertinents (niveau ≥ 2), 0–10 de niveau 3.
- 7% des compétences réellement possédées sont écrites avec un outil **absent du référentiel** (invisibles pour le système, par construction).
- Durée du calcul : 99 s. Égalités de score départagées au hasard, moyennées sur 20 tirages.

## 1. Qualité du classement

Moyenne sur les 11 offres, **[intervalle de confiance à 95 %]** par rééchantillonnage des offres (large, car il n'y a que 11 offres). Précision/rappel : pertinent = niveau ≥ 2.

| Variante | P@5 | P@10 | R@10 | NDCG@10 | MRR |
|---|---|---|---|---|---|
| Mots-clés seuls | 0.957 [0.90–1.00] | 0.846 [0.80–0.90] | 0.491 [0.38–0.59] | 0.808 [0.75–0.86] | 1.000 [1.00–1.00] |
| TF-IDF seul | 0.909 [0.82–0.98] | 0.855 [0.81–0.90] | 0.498 [0.38–0.61] | 0.761 [0.67–0.84] | 0.955 [0.86–1.00] |
| Texte (TF-IDF + mots-clés) | 0.945 [0.89–1.00] | 0.873 [0.81–0.93] | 0.506 [0.39–0.61] | 0.807 [0.74–0.87] | 1.000 [1.00–1.00] |
| Compétences seules | 0.981 [0.95–1.00] | 0.931 [0.91–0.96] | 0.536 [0.43–0.64] | 0.833 [0.77–0.88] | 1.000 [1.00–1.00] |
| Expérience seule | 0.275 [0.23–0.32] | 0.261 [0.22–0.30] | 0.144 [0.11–0.18] | 0.347 [0.30–0.40] | 0.488 [0.45–0.53] |
| Niveau d'études seul | 0.185 [0.14–0.24] | 0.169 [0.12–0.22] | 0.084 [0.07–0.10] | 0.214 [0.17–0.28] | 0.379 [0.32–0.44] |
| Compétences + expérience | 0.925 [0.86–0.98] | 0.839 [0.77–0.91] | 0.470 [0.39–0.55] | 0.863 [0.82–0.90] | 1.000 [1.00–1.00] |
| Poids par défaut (45/20/20/10/5) | 0.982 [0.95–1.00] | 0.936 [0.90–0.97] | 0.539 [0.43–0.65] | 0.903 [0.86–0.94] | 1.000 [1.00–1.00] |
| Sémantique seule | 0.927 [0.84–1.00] | 0.873 [0.81–0.94] | 0.510 [0.39–0.62] | 0.810 [0.76–0.85] | 1.000 [1.00–1.00] |
| Compétences + sémantique | 1.000 [1.00–1.00] | 0.982 [0.95–1.00] | 0.565 [0.45–0.68] | 0.874 [0.82–0.92] | 1.000 [1.00–1.00] |
| Texte + sémantique | 0.945 [0.87–1.00] | 0.900 [0.85–0.95] | 0.530 [0.40–0.66] | 0.829 [0.76–0.89] | 1.000 [1.00–1.00] |
| Défaut + sémantique (20 %) | 1.000 [1.00–1.00] | 0.909 [0.87–0.95] | 0.527 [0.41–0.64] | 0.898 [0.86–0.93] | 1.000 [1.00–1.00] |
| Aléatoire (espérance) | 0.160 [0.12–0.20] | 0.160 [0.12–0.21] | 0.080 [0.08–0.08] | 0.201 [0.15–0.27] | 0.351 [0.30–0.41] |

### Écart de NDCG@10 entre les poids par défaut et chaque autre variante

| Variante comparée | Écart moyen (défaut − variante) | IC 95 % | Conclusion |
|---|---|---|---|
| Mots-clés seuls | +0.095 | [+0.05, +0.14] | défaut meilleur |
| TF-IDF seul | +0.142 | [+0.08, +0.20] | défaut meilleur |
| Texte (TF-IDF + mots-clés) | +0.096 | [+0.04, +0.15] | défaut meilleur |
| Compétences seules | +0.070 | [+0.05, +0.10] | défaut meilleur |
| Expérience seule | +0.556 | [+0.50, +0.62] | défaut meilleur |
| Niveau d'études seul | +0.689 | [+0.62, +0.75] | défaut meilleur |
| Compétences + expérience | +0.040 | [+0.02, +0.06] | défaut meilleur |
| Sémantique seule | +0.093 | [+0.04, +0.14] | défaut meilleur |
| Compétences + sémantique | +0.029 | [+0.02, +0.04] | défaut meilleur |
| Texte + sémantique | +0.074 | [+0.02, +0.12] | défaut meilleur |
| Défaut + sémantique (20 %) | +0.005 | [-0.02, +0.02] | indécidable |
| Aléatoire (espérance) | +0.702 | [+0.63, +0.76] | défaut meilleur |

### Détail par offre (poids par défaut)

| Offre | Langue | Pertinents | NDCG@10 | P@10 |
|---|---|---|---|---|
| Senior Data Scientist | en | 31 | 0.961 | 1.000 |
| AI Engineer | en | 19 | 0.900 | 0.900 |
| Data Analyst | en | 14 | 0.808 | 0.900 |
| Ingénieur Big Data | fr | 14 | 0.861 | 0.900 |
| Backend Engineer | en | 18 | 0.955 | 1.000 |
| Développeur Back-end | fr | 31 | 0.772 | 1.000 |
| Développeur Front-end | fr | 12 | 0.982 | 1.000 |
| Cloud Engineer | en | 14 | 0.851 | 0.900 |
| Growth Marketer | en | 11 | 0.929 | 0.900 |
| Full-Stack Developer | en | 37 | 1.000 | 1.000 |
| Ingénieur Analytics | fr | 20 | 0.912 | 0.800 |

## 2. Sensibilité aux poids

400 jeux de poids tirés au hasard (loi de Dirichlet uniforme). NDCG@10 moyen : médiane 0.851, minimum 0.716, maximum 0.909. Poids par défaut : **0.903**, soit mieux que 99% des tirages.

Meilleurs poids trouvés : skills 0.21, experience 0.16, education 0.07, tfidf 0.19, keyword 0.02, semantic 0.36. **Ne pas adopter ces poids** : ils sont optimisés sur ces mêmes offres (surapprentissage garanti) et l'écart avec le défaut est à comparer à l'incertitude ci-dessus.

## 3. Effet de la langue (rang moyen des candidats de pertinence 3, en % ; 0 % = tête)

| Variante | Même langue offre/CV | Langues différentes |
|---|---|---|
| TF-IDF seul | 3.1 (n=32) | 15.8 (n=21) |
| Sémantique seule | 4.5 (n=32) | 5.5 (n=21) |
| Compétences seules | 4.1 (n=32) | 8.5 (n=21) |
| Poids par défaut (45/20/20/10/5) | 2.6 (n=32) | 8.5 (n=21) |

## 4. Qualité de la lecture (comparée aux attributs cachés)

- Compétences détectables (hors outils hors référentiel) : précision **0.973**, rappel **1.000**.
- Complétude moyenne de l'extraction des CV : 0.98.
- CV sans aucune expérience lue : 12/126 (dont 12 à cause d'un titre de rubrique non reconnu) ; échecs de lecture de fichier : 0.
- Analyse des offres, compétences requises : précision 1.000, rappel 1.000 ; optionnelles : précision 1.000, rappel 1.000 ; années d'expérience exactes : 11/11.

## 5. Équité

Chaque candidat est comparé à son « jumeau » (même CV, un seul élément changé). Δ = écart de score (sur 100) ; « top-10 conservé » = part du top 10 inchangée.

| Élément modifié | Δ max | Δ moyen | Candidats dont le score change | Top-10 conservé |
|---|---|---|---|---|
| identité (nom, contacts, titre d'en-tête, langues parlées) | 0.00 | 0.000 | 0% | 100% |
| genre des intitulés de poste (CV français) | 0.00 | 0.000 | 0% | 100% |
| proxys géographiques (villes des employeurs et de l'école) | 0.42 | 0.086 | 29% | 100% |

Sensibilité aux proxys géographiques selon que l'offre cite une ville ou non : offres citant une ville (n=7) : Δ moyen 0.135, top-10 conservé 1.00 ; offres sans ville (n=4) : Δ moyen 0.000, top-10 conservé 1.00.

Score moyen (poids par défaut) par famille de noms, parmi les candidats de pertinence 3 uniquement (à pertinence égale) :

| Famille de noms | Score moyen | Effectif |
|---|---|---|
| 1 | 59.16 | 10 |
| 2 | 58.38 | 8 |
| 3 | 63.35 | 10 |
| 4 | 68.82 | 3 |
| 5 | 59.22 | 10 |
| 6 | 60.11 | 12 |

Écart maximal entre familles de noms : 10.44 points. **Test de permutation** (3000 tirages, familles de noms redistribuées entre candidats) : p = 0.259, soit compatible avec le simple hasard de l'échantillonnage. Les familles de noms sont attribuées au hasard dans ce jeu : un écart significatif ne pourrait venir que d'un biais direct. L'absence d'écart significatif ne dit RIEN sur les corrélations réelles entre origine et parcours (écoles, villes, trous de carrière…) : un test sur ce jeu n'a pas la puissance d'en détecter de petites.

## 6. Bourrage de mots-clés

8 CV listent, dans leur seule section « compétences », des compétences d'une famille éloignée qu'ils ne possèdent pas (aucune trace dans leurs expériences). Places du top 10 occupées, sur l'ensemble des 11 offres, par de tels CV de pertinence ≤ 1 (espérance au hasard : 7.0) :

| Variante | Places occupées par des CV gonflés |
|---|---|
| Mots-clés seuls | 2 |
| Sémantique seule | 0 |
| Compétences seules | 4 |
| Compétences + expérience | 6 |
| Poids par défaut (45/20/20/10/5) | 5 |
| Défaut + sémantique (20 %) | 4 |

## Limites de cette évaluation

- Jeu, offres et règle de pertinence écrits par la même personne ; aucune validation par des recruteurs.
- 11 offres seulement : les intervalles de confiance sont larges, des écarts modestes sont indécidables.
- CV propres et homogènes (une colonne, rubriques standard) : la vraie difficulté est sous-estimée.
- La pertinence de référence dépend des mêmes notions (compétences, années) que le moteur : un accord élevé est en partie attendu.
- Le niveau d'études n'entre pas dans la règle de pertinence mais entre dans le score du moteur.
- L'audit d'équité ne teste que les éléments qu'on a pensé à faire varier.

## 7. Recherche de candidats : mots-clés, sémantique, hybride

Modèle d'embeddings : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`. Requêtes écrites une fois pour toutes avant les résultats (`evaluation/search_eval.py`). Pertinence : 2 = candidat de la famille visée, 1 = voisine, 0 = autre ; précision : pertinent = niveau 2. Intervalles de confiance à 95 % par rééchantillonnage des requêtes.

### Requêtes descriptives (sans nom d'outil), 18 requêtes

| Mode | P@5 | P@10 | NDCG@10 | MRR |
|---|---|---|---|---|
| Mots-clés (TF-IDF) | 0.700 [0.50–0.87] | 0.617 [0.46–0.76] | 0.734 [0.61–0.84] | 0.793 [0.61–0.94] |
| Sémantique | 0.567 [0.39–0.74] | 0.511 [0.35–0.67] | 0.656 [0.53–0.78] | 0.705 [0.52–0.88] |
| Hybride (RRF) | 0.689 [0.51–0.84] | 0.611 [0.46–0.75] | 0.734 [0.63–0.83] | 0.790 [0.61–0.93] |

- NDCG@10, sémantique − Mots-clés (TF-IDF) : -0.078 [-0.22, +0.07] → indécidable.
- NDCG@10, sémantique − Hybride (RRF) : -0.078 [-0.18, -0.01] → sémantique moins bon.

### Requêtes avec noms d'outils (contrôle), 9 requêtes

| Mode | P@5 | P@10 | NDCG@10 | MRR |
|---|---|---|---|---|
| Mots-clés (TF-IDF) | 0.889 [0.78–0.98] | 0.811 [0.68–0.93] | 0.874 [0.78–0.96] | 1.000 [1.00–1.00] |
| Sémantique | 0.844 [0.69–0.96] | 0.778 [0.67–0.88] | 0.863 [0.78–0.93] | 1.000 [1.00–1.00] |
| Hybride (RRF) | 0.978 [0.93–1.00] | 0.878 [0.78–0.97] | 0.931 [0.87–0.98] | 1.000 [1.00–1.00] |

- NDCG@10, sémantique − Mots-clés (TF-IDF) : -0.011 [-0.13, +0.09] → indécidable.
- NDCG@10, sémantique − Hybride (RRF) : -0.068 [-0.14, -0.01] → sémantique moins bon.

### Effet de la langue (requêtes descriptives) : rang relatif moyen des bons candidats, en % (0 % = tête)

| Mode | CV dans la langue de la requête | CV dans l'autre langue |
|---|---|---|
| Mots-clés (TF-IDF) | 11.1 (n=126) | 26.1 (n=126) |
| Sémantique | 15.1 (n=126) | 16.7 (n=126) |
| Hybride (RRF) | 8.1 (n=126) | 19.2 (n=126) |

Limites : requêtes écrites par la même personne que les CV ; pertinence = appartenance à une famille de métier ; CV générés avec des modèles de phrases (peu de variété lexicale) ; 27 requêtes seulement.

## 8. Équité de la composante sémantique

Même méthode que la section 5 (jumeaux), appliquée au score sémantique (0 à 100) des 126 candidats pour les 11 offres.

| Élément modifié | Δ max | Δ moyen | Scores qui changent | Top-10 conservé |
|---|---|---|---|---|
| identité (nom, contacts, titre d'en-tête, langues parlées) | 0.00 | 0.000 | 0% | 100% |
| genre des intitulés de poste (CV français) | 0.00 | 0.000 | 0% | 100% |
| proxys géographiques (villes des employeurs et de l'école) | 3.37 | 0.573 | 98% | 95% |

Les écoles et les villes restent dans les passages vectorisés : un modèle d'embedding peut y encoder un prestige ou une origine. Ce test ne mesure que la sensibilité à des changements de ville ; il ne dit rien des corrélations réelles.
