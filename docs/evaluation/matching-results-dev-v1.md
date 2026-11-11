# Résultats d'évaluation du matching — graine 1

> **À lire avant les chiffres.** Ce jeu est SYNTHÉTIQUE : candidats, offres et règle de pertinence
> ont été écrits par la même personne (Claude). Aucun recruteur n'a jugé ces classements. Ces
> résultats mesurent la cohérence du système avec une règle explicite sur des CV propres et
> homogènes ; ils ne prédisent PAS la performance sur de vrais CV, qui sera inférieure.

## Jeu de données

- Graine **1** ; 126 candidats (9 familles de métiers × 14), 11 offres (9 mono-famille + 2 hybrides).
- CV en français et en anglais (mélangés), PDF et DOCX, rendus en vrais fichiers puis relus par le pipeline.
- Offres et CV de langues indépendantes : une partie des paires est inter-langues.
- Pertinence 0 à 3 calculée sur des attributs CACHÉS (voir `evaluation/generator.py::gold_grade`). Par offre : 12–26 candidats pertinents (niveau ≥ 2), 2–10 de niveau 3.
- 6% des compétences réellement possédées sont écrites avec un outil **absent du référentiel** (invisibles pour le système, par construction).
- Durée du calcul : 60 s. Égalités de score départagées au hasard, moyennées sur 20 tirages.

## 1. Qualité du classement

Moyenne sur les 11 offres, **[intervalle de confiance à 95 %]** par rééchantillonnage des offres (large, car il n'y a que 11 offres). Précision/rappel : pertinent = niveau ≥ 2.

| Variante | P@5 | P@10 | R@10 | NDCG@10 | MRR |
|---|---|---|---|---|---|
| Mots-clés seuls | 0.925 [0.85–0.98] | 0.814 [0.71–0.89] | 0.507 [0.42–0.59] | 0.790 [0.75–0.83] | 1.000 [1.00–1.00] |
| TF-IDF seul | 0.891 [0.84–0.95] | 0.864 [0.78–0.93] | 0.542 [0.45–0.63] | 0.762 [0.70–0.82] | 1.000 [1.00–1.00] |
| Texte (TF-IDF + mots-clés) | 0.945 [0.89–1.00] | 0.873 [0.79–0.94] | 0.549 [0.46–0.64] | 0.794 [0.75–0.84] | 1.000 [1.00–1.00] |
| Compétences seules | 1.000 [1.00–1.00] | 0.962 [0.93–0.99] | 0.604 [0.52–0.68] | 0.872 [0.84–0.90] | 1.000 [1.00–1.00] |
| Expérience seule | 0.274 [0.20–0.38] | 0.281 [0.21–0.38] | 0.182 [0.12–0.26] | 0.346 [0.27–0.45] | 0.470 [0.38–0.57] |
| Niveau d'études seul | 0.128 [0.11–0.15] | 0.130 [0.11–0.15] | 0.079 [0.07–0.09] | 0.147 [0.13–0.17] | 0.308 [0.27–0.34] |
| Compétences + expérience | 0.982 [0.95–1.00] | 0.865 [0.78–0.94] | 0.538 [0.46–0.61] | 0.894 [0.85–0.93] | 1.000 [1.00–1.00] |
| Poids par défaut (45/20/20/10/5) | 0.982 [0.95–1.00] | 0.927 [0.86–0.98] | 0.584 [0.49–0.67] | 0.899 [0.86–0.93] | 1.000 [1.00–1.00] |
| Aléatoire (espérance) | 0.133 [0.11–0.16] | 0.133 [0.11–0.16] | 0.078 [0.08–0.08] | 0.157 [0.13–0.18] | 0.310 [0.28–0.35] |

### Écart de NDCG@10 entre les poids par défaut et chaque autre variante

| Variante comparée | Écart moyen (défaut − variante) | IC 95 % | Conclusion |
|---|---|---|---|
| Mots-clés seuls | +0.109 | [+0.06, +0.15] | défaut meilleur |
| TF-IDF seul | +0.137 | [+0.09, +0.19] | défaut meilleur |
| Texte (TF-IDF + mots-clés) | +0.105 | [+0.06, +0.14] | défaut meilleur |
| Compétences seules | +0.026 | [+0.00, +0.06] | défaut meilleur |
| Expérience seule | +0.553 | [+0.46, +0.63] | défaut meilleur |
| Niveau d'études seul | +0.752 | [+0.70, +0.80] | défaut meilleur |
| Compétences + expérience | +0.004 | [-0.02, +0.02] | indécidable |
| Aléatoire (espérance) | +0.741 | [+0.68, +0.79] | défaut meilleur |

### Détail par offre (poids par défaut)

| Offre | Langue | Pertinents | NDCG@10 | P@10 |
|---|---|---|---|---|
| Data Scientist | en | 14 | 0.957 | 1.000 |
| Ingénieur Machine Learning | fr | 21 | 0.907 | 0.800 |
| Business Intelligence Analyst | en | 17 | 0.901 | 1.000 |
| Data Engineer | fr | 12 | 0.901 | 1.000 |
| Senior Java Engineer | en | 14 | 0.923 | 0.800 |
| Développeur Back-end | fr | 26 | 0.734 | 1.000 |
| Développeur React | fr | 13 | 0.985 | 1.000 |
| Ingénieur Cloud | fr | 15 | 0.818 | 0.900 |
| Consultant SEO | fr | 14 | 0.926 | 1.000 |
| Full-Stack Developer | en | 25 | 0.960 | 1.000 |
| Ingénieur Analytics | fr | 15 | 0.877 | 0.700 |

## 2. Sensibilité aux poids

400 jeux de poids tirés au hasard (loi de Dirichlet uniforme). NDCG@10 moyen : médiane 0.836, minimum 0.689, maximum 0.907. Poids par défaut : **0.899**, soit mieux que 98% des tirages.

Meilleurs poids trouvés : skills 0.65, experience 0.22, education 0.05, tfidf 0.02, keyword 0.06. **Ne pas adopter ces poids** : ils sont optimisés sur ces mêmes offres (surapprentissage garanti) et l'écart avec le défaut est à comparer à l'incertitude ci-dessus.

## 3. Effet de la langue (rang moyen des candidats de pertinence 3, en % ; 0 % = tête)

| Variante | Même langue offre/CV | Langues différentes |
|---|---|---|
| TF-IDF seul | 4.4 (n=32) | 7.7 (n=23) |
| Compétences seules | 4.9 (n=32) | 3.5 (n=23) |
| Poids par défaut (45/20/20/10/5) | 4.2 (n=32) | 3.6 (n=23) |

## 4. Qualité de la lecture (comparée aux attributs cachés)

- Compétences détectables (hors outils hors référentiel) : précision **0.978**, rappel **1.000**.
- Complétude moyenne de l'extraction des CV : 0.99.
- CV sans aucune expérience lue : 7/126 (dont 7 à cause d'un titre de rubrique non reconnu) ; échecs de lecture de fichier : 0.
- Analyse des offres, compétences requises : précision 0.982, rappel 0.982 ; optionnelles : précision 1.000, rappel 1.000 ; années d'expérience exactes : 11/11.

## 5. Équité

Chaque candidat est comparé à son « jumeau » (même CV, un seul élément changé). Δ = écart de score (sur 100) ; « top-10 conservé » = part du top 10 inchangée.

| Élément modifié | Δ max | Δ moyen | Candidats dont le score change | Top-10 conservé |
|---|---|---|---|---|
| identité (nom, contacts, titre d'en-tête, langues parlées) | 0.00 | 0.000 | 0% | 100% |
| genre des intitulés de poste (CV français) | 0.01 | 0.000 | 0% | 100% |
| proxys géographiques (villes des employeurs et de l'école) | 0.41 | 0.075 | 25% | 100% |

Sensibilité aux proxys géographiques selon que l'offre cite une ville ou non : offres citant une ville (n=6) : Δ moyen 0.137, top-10 conservé 1.00 ; offres sans ville (n=5) : Δ moyen 0.000, top-10 conservé 1.00.

Score moyen (poids par défaut) par famille de noms, parmi les candidats de pertinence 3 uniquement (à pertinence égale) :

| Famille de noms | Score moyen | Effectif |
|---|---|---|
| 1 | 67.28 | 8 |
| 2 | 61.96 | 8 |
| 3 | 57.89 | 9 |
| 4 | 58.32 | 8 |
| 5 | 61.84 | 12 |
| 6 | 66.47 | 10 |

Écart maximal entre familles de noms : 9.39 points. Les familles de noms sont attribuées au hasard dans ce jeu : cet écart ne peut refléter qu'un biais direct du système ou du bruit d'échantillonnage. Il ne dit RIEN sur les corrélations réelles entre origine et parcours (écoles, villes, trous de carrière…).

## Limites de cette évaluation

- Jeu, offres et règle de pertinence écrits par la même personne ; aucune validation par des recruteurs.
- 11 offres seulement : les intervalles de confiance sont larges, des écarts modestes sont indécidables.
- CV propres et homogènes (une colonne, rubriques standard) : la vraie difficulté est sous-estimée.
- La pertinence de référence dépend des mêmes notions (compétences, années) que le moteur : un accord élevé est en partie attendu.
- Le niveau d'études n'entre pas dans la règle de pertinence mais entre dans le score du moteur.
- L'audit d'équité ne teste que les éléments qu'on a pensé à faire varier.
