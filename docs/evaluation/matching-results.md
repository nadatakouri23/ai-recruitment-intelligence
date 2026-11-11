# Résultats d'évaluation du matching — graine 2024

> **À lire avant les chiffres.** Ce jeu est SYNTHÉTIQUE : candidats, offres et règle de pertinence
> ont été écrits par la même personne (Claude). Aucun recruteur n'a jugé ces classements. Ces
> résultats mesurent la cohérence du système avec une règle explicite sur des CV propres et
> homogènes ; ils ne prédisent PAS la performance sur de vrais CV, qui sera inférieure.

## Jeu de données

- Graine **2024** ; 126 candidats (9 familles de métiers × 14), 11 offres (9 mono-famille + 2 hybrides).
- CV en français et en anglais (mélangés), PDF et DOCX, rendus en vrais fichiers puis relus par le pipeline.
- Offres et CV de langues indépendantes : une partie des paires est inter-langues.
- Pertinence 0 à 3 calculée sur des attributs CACHÉS (voir `evaluation/generator.py::gold_grade`). Par offre : 12–38 candidats pertinents (niveau ≥ 2), 0–10 de niveau 3.
- 8% des compétences réellement possédées sont écrites avec un outil **absent du référentiel** (invisibles pour le système, par construction).
- Durée du calcul : 49 s. Égalités de score départagées au hasard, moyennées sur 20 tirages.

## 1. Qualité du classement

Moyenne sur les 11 offres, **[intervalle de confiance à 95 %]** par rééchantillonnage des offres (large, car il n'y a que 11 offres). Précision/rappel : pertinent = niveau ≥ 2.

| Variante | P@5 | P@10 | R@10 | NDCG@10 | MRR |
|---|---|---|---|---|---|
| Mots-clés seuls | 0.944 [0.86–1.00] | 0.873 [0.79–0.94] | 0.478 [0.38–0.57] | 0.872 [0.82–0.92] | 0.980 [0.94–1.00] |
| TF-IDF seul | 0.927 [0.85–1.00] | 0.827 [0.74–0.91] | 0.461 [0.35–0.57] | 0.825 [0.76–0.89] | 1.000 [1.00–1.00] |
| Texte (TF-IDF + mots-clés) | 0.927 [0.85–1.00] | 0.864 [0.78–0.94] | 0.475 [0.38–0.58] | 0.859 [0.80–0.91] | 1.000 [1.00–1.00] |
| Compétences seules | 0.969 [0.93–1.00] | 0.907 [0.84–0.96] | 0.490 [0.41–0.56] | 0.870 [0.84–0.90] | 1.000 [1.00–1.00] |
| Expérience seule | 0.293 [0.23–0.37] | 0.303 [0.24–0.39] | 0.164 [0.12–0.23] | 0.332 [0.27–0.40] | 0.499 [0.43–0.57] |
| Niveau d'études seul | 0.165 [0.12–0.22] | 0.163 [0.13–0.20] | 0.081 [0.07–0.09] | 0.188 [0.14–0.25] | 0.359 [0.30–0.43] |
| Compétences + expérience | 0.932 [0.85–0.99] | 0.879 [0.79–0.95] | 0.470 [0.39–0.55] | 0.899 [0.86–0.94] | 1.000 [1.00–1.00] |
| Poids par défaut (45/20/20/10/5) | 0.964 [0.91–1.00] | 0.918 [0.84–0.97] | 0.494 [0.41–0.57] | 0.916 [0.88–0.95] | 1.000 [1.00–1.00] |
| Aléatoire (espérance) | 0.157 [0.13–0.19] | 0.160 [0.13–0.20] | 0.079 [0.08–0.08] | 0.188 [0.15–0.25] | 0.342 [0.30–0.39] |

### Écart de NDCG@10 entre les poids par défaut et chaque autre variante

| Variante comparée | Écart moyen (défaut − variante) | IC 95 % | Conclusion |
|---|---|---|---|
| Mots-clés seuls | +0.044 | [-0.01, +0.09] | indécidable |
| TF-IDF seul | +0.091 | [+0.02, +0.16] | défaut meilleur |
| Texte (TF-IDF + mots-clés) | +0.057 | [+0.00, +0.11] | défaut meilleur |
| Compétences seules | +0.046 | [+0.02, +0.08] | défaut meilleur |
| Expérience seule | +0.584 | [+0.52, +0.64] | défaut meilleur |
| Niveau d'études seul | +0.729 | [+0.67, +0.78] | défaut meilleur |
| Compétences + expérience | +0.017 | [+0.01, +0.03] | défaut meilleur |
| Aléatoire (espérance) | +0.728 | [+0.67, +0.78] | défaut meilleur |

### Détail par offre (poids par défaut)

| Offre | Langue | Pertinents | NDCG@10 | P@10 |
|---|---|---|---|---|
| Ingénieur Data Scientist | fr | 20 | 0.996 | 1.000 |
| AI Engineer | en | 28 | 0.860 | 0.900 |
| Analyste de données | fr | 12 | 0.793 | 0.600 |
| Ingénieur Big Data | fr | 18 | 0.898 | 1.000 |
| Ingénieur Backend | fr | 19 | 0.942 | 0.900 |
| Ingénieur Logiciel | fr | 28 | 0.886 | 1.000 |
| UI Engineer | en | 14 | 0.951 | 1.000 |
| Administrateur Systèmes | fr | 15 | 0.989 | 1.000 |
| Responsable Marketing Digital | fr | 14 | 0.906 | 0.900 |
| Full-Stack Developer | en | 38 | 1.000 | 1.000 |
| Ingénieur Analytics | fr | 18 | 0.858 | 0.800 |

## 2. Sensibilité aux poids

400 jeux de poids tirés au hasard (loi de Dirichlet uniforme). NDCG@10 moyen : médiane 0.877, minimum 0.713, maximum 0.924. Poids par défaut : **0.916**, soit mieux que 97% des tirages.

Meilleurs poids trouvés : skills 0.16, experience 0.14, education 0.05, tfidf 0.28, keyword 0.37. **Ne pas adopter ces poids** : ils sont optimisés sur ces mêmes offres (surapprentissage garanti) et l'écart avec le défaut est à comparer à l'incertitude ci-dessus.

## 3. Effet de la langue (rang moyen des candidats de pertinence 3, en % ; 0 % = tête)

| Variante | Même langue offre/CV | Langues différentes |
|---|---|---|
| TF-IDF seul | 2.1 (n=32) | 11.0 (n=32) |
| Compétences seules | 5.6 (n=32) | 7.7 (n=32) |
| Poids par défaut (45/20/20/10/5) | 4.6 (n=32) | 7.8 (n=32) |

## 4. Qualité de la lecture (comparée aux attributs cachés)

- Compétences détectables (hors outils hors référentiel) : précision **0.976**, rappel **1.000**.
- Complétude moyenne de l'extraction des CV : 0.97.
- CV sans aucune expérience lue : 13/126 (dont 13 à cause d'un titre de rubrique non reconnu) ; échecs de lecture de fichier : 0.
- Analyse des offres, compétences requises : précision 1.000, rappel 1.000 ; optionnelles : précision 1.000, rappel 1.000 ; années d'expérience exactes : 11/11.

## 5. Équité

Chaque candidat est comparé à son « jumeau » (même CV, un seul élément changé). Δ = écart de score (sur 100) ; « top-10 conservé » = part du top 10 inchangée.

| Élément modifié | Δ max | Δ moyen | Candidats dont le score change | Top-10 conservé |
|---|---|---|---|---|
| identité (nom, contacts, titre d'en-tête, langues parlées) | 0.00 | 0.000 | 0% | 100% |
| genre des intitulés de poste (CV français) | 0.01 | 0.000 | 1% | 100% |
| proxys géographiques (villes des employeurs et de l'école) | 0.43 | 0.061 | 21% | 100% |

Sensibilité aux proxys géographiques selon que l'offre cite une ville ou non : offres citant une ville (n=5) : Δ moyen 0.135, top-10 conservé 1.00 ; offres sans ville (n=6) : Δ moyen 0.000, top-10 conservé 1.00.

Score moyen (poids par défaut) par famille de noms, parmi les candidats de pertinence 3 uniquement (à pertinence égale) :

| Famille de noms | Score moyen | Effectif |
|---|---|---|
| 1 | 60.17 | 13 |
| 2 | 65.79 | 11 |
| 3 | 57.50 | 10 |
| 4 | 63.69 | 12 |
| 5 | 54.94 | 9 |
| 6 | 63.88 | 9 |

Écart maximal entre familles de noms : 10.85 points. **Test de permutation** (3000 tirages, familles de noms redistribuées entre candidats) : p = 0.173, soit compatible avec le simple hasard de l'échantillonnage. Les familles de noms sont attribuées au hasard dans ce jeu : un écart significatif ne pourrait venir que d'un biais direct. L'absence d'écart significatif ne dit RIEN sur les corrélations réelles entre origine et parcours (écoles, villes, trous de carrière…) : un test sur ce jeu n'a pas la puissance d'en détecter de petites.

## 6. Bourrage de mots-clés

6 CV listent, dans leur seule section « compétences », des compétences d'une famille éloignée qu'ils ne possèdent pas (aucune trace dans leurs expériences). Places du top 10 occupées, sur l'ensemble des 11 offres, par de tels CV de pertinence ≤ 1 (espérance au hasard : 5.2) :

| Variante | Places occupées par des CV gonflés |
|---|---|
| Mots-clés seuls | 0 |
| Compétences seules | 4 |
| Compétences + expérience | 2 |
| Poids par défaut (45/20/20/10/5) | 2 |

## Limites de cette évaluation

- Jeu, offres et règle de pertinence écrits par la même personne ; aucune validation par des recruteurs.
- 11 offres seulement : les intervalles de confiance sont larges, des écarts modestes sont indécidables.
- CV propres et homogènes (une colonne, rubriques standard) : la vraie difficulté est sous-estimée.
- La pertinence de référence dépend des mêmes notions (compétences, années) que le moteur : un accord élevé est en partie attendu.
- Le niveau d'études n'entre pas dans la règle de pertinence mais entre dans le score du moteur.
- L'audit d'équité ne teste que les éléments qu'on a pensé à faire varier.
