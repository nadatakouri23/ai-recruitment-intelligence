# Évaluation du parseur de CV (Phase 2)

## Ce qui est mesuré, et ce qui ne l'est pas

| | |
|---|---|
| **Données** | 6 CV **synthétiques** (noms, sociétés et coordonnées fictifs), FR et EN, PDF et DOCX |
| **Origine** | Écrits par Claude (`backend/tests/cv_factory.py`) ; fichiers dans `data/samples/cvs/` |
| **Vérité terrain** | Écrite à la main avec les CV : compétences, titres, entreprises, diplômes, langues |
| **Reproduction** | `backend\.venv\Scripts\python.exe scripts\generate_sample_cvs.py` |

## Résultat

Compétences du référentiel, par CV (précision / rappel) : **1,00 / 1,00** sur les 6 CV
(85 compétences attendues au total, 85 trouvées, aucune en trop).

## Pourquoi ce résultat NE prouve PAS que le parseur est bon

1. Les CV ont été écrits par la même personne (Claude) que le parseur, avec des formulations que le
   parseur sait lire.
2. Le parseur a été **ajusté en observant ces CV** (surapprentissage au sens large) : par exemple,
   la règle sur les alias ambigus a été assouplie pour retrouver « Spark ».
3. Six CV, mise en page simple sur une colonne : aucune des difficultés des vrais CV (colonnes,
   icônes, tableaux imbriqués, fautes, abréviations, formats exotiques).

Ce chiffre est un **test de régression** : si une modification fait baisser un de ces scores, quelque
chose s'est cassé. Il n'est pas une estimation de la qualité en production, qui sera plus basse.

## Ce qui est vérifié en plus (tests automatiques)

- Pièges de faux positifs : `Java`/`JavaScript`, `SQL`/`MySQL`, `C`/`R`/`Go` isolés, `Spring 2020`,
  `R&D`, « tableau de bord », « vue d'ensemble », liens `github.com/...`.
- Dates : mois en lettres FR/EN, `06/2015`, `2018-2020`, « présent » / « aujourd'hui », périodes
  inversées, cumul sans double comptage des chevauchements.
- Robustesse : texte vide ou absurde (aucune donnée inventée, avertissements), PDF corrompu ou
  scanné, faux PDF, DOCX piégé (archive ZIP géante), noms de fichiers hostiles.
- Éthique : date de naissance, nationalité, situation familiale, adresse et centres d'intérêt ne
  figurent jamais dans le profil extrait.

## Limites de la mesure et suite prévue

- **Phase 5** : constituer un jeu plus grand et plus varié (CV rédigés par plusieurs personnes ou
  générés avec des gabarits différents), avec annotations indépendantes, et mesurer ce qui compte pour
  le recrutement : qualité du **classement** (Precision@K, NDCG@K), pas seulement de l'extraction.
- **Phase 7** : comparer l'extraction par règles à une extraction par LLM sur les mêmes CV.
- Ne jamais utiliser de vrais CV sans autorisation explicite des personnes concernées.
