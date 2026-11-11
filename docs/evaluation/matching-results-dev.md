# Résultats d'évaluation du matching — graine 1

> **À lire avant les chiffres.** Ce jeu est SYNTHÉTIQUE : candidats, offres et règle de pertinence
> ont été écrits par la même personne (Claude). Aucun recruteur n'a jugé ces classements. Ces
> résultats mesurent la cohérence du système avec une règle explicite sur des CV propres et
> homogènes ; ils ne prédisent PAS la performance sur de vrais CV, qui sera inférieure.

## Jeu de données

- Graine **1** ; 126 candidats (9 familles de métiers × 14), 11 offres (9 mono-famille + 2 hybrides).
- CV en français et en anglais (mélangés), PDF et DOCX, rendus en vrais fichiers puis relus par le pipeline.
- Offres et CV de langues indépendantes : une partie des paires est inter-langues.
- Pertinence 0 à 3 calculée sur des attributs CACHÉS (voir `evaluation/generator.py::gold_grade`). Par offre : 13–26 candidats pertinents (niveau ≥ 2), 1–10 de niveau 3.
- 7% des compétences réellement possédées sont écrites avec un outil **absent du référentiel** (invisibles pour le système, par construction).
- Durée du calcul : 52 s. Égalités de score départagées au hasard, moyennées sur 20 tirages.

## 1. Qualité du classement

Moyenne sur les 11 offres, **[intervalle de confiance à 95 %]** par rééchantillonnage des offres (large, car il n'y a que 11 offres). Précision/rappel : pertinent = niveau ≥ 2.

| Variante | P@5 | P@10 | R@10 | NDCG@10 | MRR |
|---|---|---|---|---|---|
| Mots-clés seuls | 0.957 [0.91–1.00] | 0.880 [0.84–0.92] | 0.484 [0.40–0.57] | 0.767 [0.71–0.81] | 1.000 [1.00–1.00] |
| TF-IDF seul | 0.873 [0.76–0.96] | 0.891 [0.80–0.95] | 0.491 [0.40–0.58] | 0.735 [0.66–0.80] | 1.000 [1.00–1.00] |
| Texte (TF-IDF + mots-clés) | 0.964 [0.91–1.00] | 0.873 [0.80–0.94] | 0.480 [0.39–0.56] | 0.763 [0.70–0.82] | 1.000 [1.00–1.00] |
| Compétences seules | 0.995 [0.99–1.00] | 0.991 [0.97–1.00] | 0.544 [0.45–0.64] | 0.830 [0.79–0.87] | 1.000 [1.00–1.00] |
| Expérience seule | 0.324 [0.26–0.40] | 0.310 [0.25–0.38] | 0.177 [0.12–0.24] | 0.361 [0.29–0.43] | 0.551 [0.47–0.64] |
| Niveau d'études seul | 0.155 [0.11–0.19] | 0.142 [0.11–0.17] | 0.070 [0.06–0.08] | 0.169 [0.13–0.20] | 0.341 [0.28–0.40] |
| Compétences + expérience | 1.000 [1.00–1.00] | 0.981 [0.96–1.00] | 0.540 [0.45–0.64] | 0.926 [0.88–0.96] | 1.000 [1.00–1.00] |
| Poids par défaut (45/20/20/10/5) | 1.000 [1.00–1.00] | 1.000 [1.00–1.00] | 0.551 [0.45–0.65] | 0.897 [0.85–0.93] | 1.000 [1.00–1.00] |
| Aléatoire (espérance) | 0.155 [0.13–0.18] | 0.154 [0.13–0.18] | 0.078 [0.08–0.08] | 0.175 [0.15–0.21] | 0.343 [0.30–0.38] |

### Écart de NDCG@10 entre les poids par défaut et chaque autre variante

| Variante comparée | Écart moyen (défaut − variante) | IC 95 % | Conclusion |
|---|---|---|---|
| Mots-clés seuls | +0.130 | [+0.07, +0.18] | défaut meilleur |
| TF-IDF seul | +0.162 | [+0.08, +0.23] | défaut meilleur |
| Texte (TF-IDF + mots-clés) | +0.133 | [+0.07, +0.19] | défaut meilleur |
| Compétences seules | +0.066 | [+0.04, +0.10] | défaut meilleur |
| Expérience seule | +0.535 | [+0.47, +0.61] | défaut meilleur |
| Niveau d'études seul | +0.728 | [+0.66, +0.78] | défaut meilleur |
| Compétences + expérience | -0.029 | [-0.05, -0.01] | défaut moins bon |
| Aléatoire (espérance) | +0.722 | [+0.65, +0.78] | défaut meilleur |

### Détail par offre (poids par défaut)

| Offre | Langue | Pertinents | NDCG@10 | P@10 |
|---|---|---|---|---|
| Applied Scientist | en | 22 | 0.953 | 1.000 |
| Ingénieur IA | fr | 22 | 0.928 | 1.000 |
| Data Analyst | en | 22 | 0.924 | 1.000 |
| Ingénieur Data | fr | 13 | 0.969 | 1.000 |
| Backend Engineer | en | 23 | 0.889 | 1.000 |
| Backend Developer | en | 26 | 0.794 | 1.000 |
| Frontend Developer | en | 13 | 0.912 | 1.000 |
| Site Reliability Engineer | en | 13 | 0.964 | 1.000 |
| Responsable Marketing Digital | fr | 13 | 0.914 | 1.000 |
| Full-Stack Developer | en | 26 | 0.887 | 1.000 |
| Ingénieur Analytics | fr | 24 | 0.729 | 1.000 |

## 2. Sensibilité aux poids

400 jeux de poids tirés au hasard (loi de Dirichlet uniforme). NDCG@10 moyen : médiane 0.838, minimum 0.683, maximum 0.926. Poids par défaut : **0.897**, soit mieux que 91% des tirages.

Meilleurs poids trouvés : skills 0.49, experience 0.42, education 0.01, tfidf 0.01, keyword 0.06. **Ne pas adopter ces poids** : ils sont optimisés sur ces mêmes offres (surapprentissage garanti) et l'écart avec le défaut est à comparer à l'incertitude ci-dessus.

## 3. Effet de la langue (rang moyen des candidats de pertinence 3, en % ; 0 % = tête)

| Variante | Même langue offre/CV | Langues différentes |
|---|---|---|
| TF-IDF seul | 3.7 (n=33) | 13.4 (n=28) |
| Compétences seules | 6.6 (n=33) | 5.6 (n=28) |
| Poids par défaut (45/20/20/10/5) | 5.7 (n=33) | 5.4 (n=28) |

## 4. Qualité de la lecture (comparée aux attributs cachés)

- Compétences détectables (hors outils hors référentiel) : précision **0.983**, rappel **1.000**.
- Complétude moyenne de l'extraction des CV : 0.98.
- CV sans aucune expérience lue : 9/126 (dont 9 à cause d'un titre de rubrique non reconnu) ; échecs de lecture de fichier : 0.
- Analyse des offres, compétences requises : précision 1.000, rappel 1.000 ; optionnelles : précision 1.000, rappel 1.000 ; années d'expérience exactes : 11/11.

## 5. Équité

Chaque candidat est comparé à son « jumeau » (même CV, un seul élément changé). Δ = écart de score (sur 100) ; « top-10 conservé » = part du top 10 inchangée.

| Élément modifié | Δ max | Δ moyen | Candidats dont le score change | Top-10 conservé |
|---|---|---|---|---|
| identité (nom, contacts, titre d'en-tête, langues parlées) | 0.00 | 0.000 | 0% | 100% |
| genre des intitulés de poste (CV français) | 0.01 | 0.000 | 0% | 100% |
| proxys géographiques (villes des employeurs et de l'école) | 0.41 | 0.068 | 25% | 100% |

Sensibilité aux proxys géographiques selon que l'offre cite une ville ou non : offres citant une ville (n=6) : Δ moyen 0.125, top-10 conservé 1.00 ; offres sans ville (n=5) : Δ moyen 0.000, top-10 conservé 1.00.

Score moyen (poids par défaut) par famille de noms, parmi les candidats de pertinence 3 uniquement (à pertinence égale) :

| Famille de noms | Score moyen | Effectif |
|---|---|---|
| 1 | 60.89 | 7 |
| 2 | 58.29 | 10 |
| 3 | 64.52 | 10 |
| 4 | 62.06 | 11 |
| 5 | 57.72 | 9 |
| 6 | 61.50 | 14 |

Écart maximal entre familles de noms : 6.80 points. **Test de permutation** (3000 tirages, familles de noms redistribuées entre candidats) : p = 0.733, soit compatible avec le simple hasard de l'échantillonnage. Les familles de noms sont attribuées au hasard dans ce jeu : un écart significatif ne pourrait venir que d'un biais direct. L'absence d'écart significatif ne dit RIEN sur les corrélations réelles entre origine et parcours (écoles, villes, trous de carrière…) : un test sur ce jeu n'a pas la puissance d'en détecter de petites.

## 6. Bourrage de mots-clés

4 CV listent, dans leur seule section « compétences », des compétences d'une famille éloignée qu'ils ne possèdent pas (aucune trace dans leurs expériences). Places du top 10 occupées, sur l'ensemble des 11 offres, par de tels CV de pertinence ≤ 1 (espérance au hasard : 3.5) :

| Variante | Places occupées par des CV gonflés |
|---|---|
| Mots-clés seuls | 2 |
| Compétences seules | 1 |
| Compétences + expérience | 0 |
| Poids par défaut (45/20/20/10/5) | 0 |

## Limites de cette évaluation

- Jeu, offres et règle de pertinence écrits par la même personne ; aucune validation par des recruteurs.
- 11 offres seulement : les intervalles de confiance sont larges, des écarts modestes sont indécidables.
- CV propres et homogènes (une colonne, rubriques standard) : la vraie difficulté est sous-estimée.
- La pertinence de référence dépend des mêmes notions (compétences, années) que le moteur : un accord élevé est en partie attendu.
- Le niveau d'études n'entre pas dans la règle de pertinence mais entre dans le score du moteur.
- L'audit d'équité ne teste que les éléments qu'on a pensé à faire varier.
