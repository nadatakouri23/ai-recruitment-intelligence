# Évaluation du matching (Phase 5)

**Statut : évalué uniquement sur un jeu SYNTHÉTIQUE écrit par l'auteur du système (Claude), avec une
règle de pertinence que lui seul a définie. Aucun recruteur n'a jugé ces classements.** Les chiffres
disent si le système suit une règle explicite sur des CV propres ; ils ne disent PAS s'il aide de
vrais recruteurs avec de vrais CV, où il fera moins bien.

Rapports complets (générés par `evaluation/run.py`) :
- `matching-results.md` : **résultat final**, graine de test 2024, calculé **une seule fois**.
- `matching-results-dev.md` : graine de développement 1, version finale du jeu.
- `matching-results-dev-v1.md` : première passe dev, **conservée** : elle a révélé que le jeu était trop facile.

> **Phase 6 :** l'apport des embeddings (6ᵉ composante, recherche sémantique) est évalué à part, sur une
> graine vierge : voir `semantic.md`. Résultat : poids sémantique laissé à 0. La graine 2024 de cette
> page est « consommée » ; les conclusions sur les poids par défaut restent celles décrites ci-dessous.

## Protocole

1. **Jeu généré à partir d'attributs cachés** (famille de métier, niveau, compétences réellement
   possédées). Les CV sont rendus en vrais PDF/DOCX et relus par le pipeline complet. La pertinence
   de référence (0 à 3) vient des attributs cachés, jamais de la sortie du parseur.
2. **Deux graines** : « dev » pour regarder et corriger, « test » (2024) jamais examinée avant la
   passe finale. Aucun changement du moteur ni des poids après avoir vu le résultat « test ».
3. **126 candidats** (9 métiers × 14), **11 offres** (9 + 2 hybrides), français et anglais mélangés,
   offres et CV de langues indépendantes, titres de rubriques parfois inconnus, outils absents du
   référentiel, et quelques CV qui listent des compétences qu'ils n'ont pas.
4. **Métriques** : Precision@5/10, Recall@10, NDCG@10, MRR (pertinent = niveau ≥ 2), avec intervalle de
   confiance à 95 % par rééchantillonnage des offres. Comparaison à un classement aléatoire et à chaque
   composante prise seule. Métriques vérifiées contre des valeurs calculées à la main (20 tests).

## Résultats sur la graine de test (11 offres)

| Variante | NDCG@10 [IC 95 %] | P@10 |
|---|---|---|
| Aléatoire (espérance) | 0,188 [0,15–0,25] | 0,160 |
| Niveau d'études seul | 0,188 [0,14–0,25] | 0,163 |
| Expérience seule | 0,332 [0,27–0,40] | 0,303 |
| TF-IDF seul | 0,825 [0,76–0,89] | 0,827 |
| Texte (TF-IDF + mots-clés) | 0,859 [0,80–0,91] | 0,864 |
| Compétences seules | 0,870 [0,84–0,90] | 0,907 |
| Mots-clés seuls | 0,872 [0,82–0,92] | 0,873 |
| Compétences + expérience | 0,899 [0,86–0,94] | 0,879 |
| **Poids par défaut (45/20/20/10/5)** | **0,916 [0,88–0,95]** | **0,918** |

## Ce qu'on peut affirmer

- **Le système est très au-dessus du hasard** (0,92 contre 0,19) et chaque composante utile l'est aussi,
  tandis que l'expérience seule et le niveau d'études seul restent proches du hasard : ces deux
  composantes n'ont de sens qu'en complément des compétences.
- **La combinaison par défaut est la meilleure variante testée**, mais l'écart avec les composantes
  seules est petit (0,02 à 0,05 de NDCG) et, pour « mots-clés seuls », statistiquement indécidable.
- **Le TF-IDF seul se dégrade fortement quand l'offre et le CV n'ont pas la même langue** (rang moyen
  des candidats de pertinence 3 : 2,1 % même langue, 11,0 % langues différentes). Les poids par défaut
  atténuent ce défaut grâce aux compétences normalisées (4,6 % / 7,8 %), sans le supprimer.
- **Équité directe** : changer le nom, les contacts, le titre d'en-tête ou les langues parlées d'un
  même CV ne change jamais le score (écart 0,00 pour les 126 candidats × 11 offres). Aucun écart
  significatif entre familles de noms (p = 0,17).
- **Proxys géographiques** : remplacer toutes les villes (employeurs, école) modifie le score de 21 %
  des candidats, de 0,43 point au maximum (0,14 en moyenne pour les offres qui citent une ville), sans
  changer le top 10. Effet faible ici ; il pourrait être plus fort avec de vrais CV, où le lieu est corrélé à d'autres choses.
- **Bourrage de mots-clés** : avec les poids par défaut, 2 places du top 10 sont prises par des CV qui
  listent des compétences qu'ils n'ont pas (contre 4 pour les compétences seules ; 5,2 au hasard).
  La composante « expérience pertinente » protège partiellement, sans faire de miracle.

## Ce qu'on ne peut PAS affirmer

- **Que les poids par défaut sont les bons.** Les deux jeux se contredisent : sur la graine de
  développement, « compétences + expérience » battait les poids par défaut (écart −0,029, significatif) ;
  sur la graine de test, c'est l'inverse (+0,017, significatif). Les « meilleurs poids aléatoires » sont
  totalement différents d'un jeu à l'autre (dev : compétences 0,49 / expérience 0,42 ; test :
  mots-clés 0,37 / TF-IDF 0,28). **Avec 11 offres, les poids ne sont pas identifiables.** Ne pas les
  « optimiser » sur ces données : ce serait ajuster le système à notre propre règle de pertinence.
- **Que le système fonctionnerait sur de vrais CV.** Ils sont plus bruités, plus variés et moins bien
  structurés. Les familles de métiers ont des vocabulaires presque disjoints ici : même les mots-clés
  seuls atteignent 0,87.
- **Que la règle de pertinence est bonne.** Elle repose sur les compétences possédées et les années :
  elle favorise mécaniquement les composantes qui les mesurent, et ne peut créditer ni le niveau
  d'études ni le texte. Un accord élevé est en partie attendu.
- **Qu'il n'y a aucun biais.** L'audit ne teste que ce qu'on a pensé à faire varier. Il ne peut
  détecter ni les corrélations réelles entre origine et parcours (écoles, villes, interruptions de
  carrière), ni les petits effets (puissance statistique faible avec ~10 candidats par groupe).
- **La précision de la lecture des CV en conditions réelles.** Compétences détectables : précision
  0,976, rappel 1,000, sur des CV générés avec nos propres modèles de phrases. L'analyse des offres
  atteint 100 % parce que les offres sont écrites avec nos propres modèles.

## Historique complet des modifications (transparence)

Après la **première passe dev** (v1, `matching-results-dev-v1.md`) :
- Le jeu était trop facile (MRR = 1,00 presque partout, mots-clés seuls à 0,79) : ajout de CV qui
  gonflent leur liste de compétences, taux variable d'outils hors référentiel (0 à 40 % selon le candidat).
- Un écart de 9,4 points entre familles de noms était présenté sans test de signification : ajout d'un
  test de permutation.

Après la **deuxième passe dev**, tests du banc d'essai et cas d'échec :
- `Spring`, `Spark`, `Tableau`, `Excel` en début de puce ou dans une liste (« Java, Spring et SQL »)
  n'étaient pas reconnus dans les offres : ajout d'un mode « listing » et d'une règle de contexte
  (accepté si la phrase contient déjà une compétence sans ambiguïté). **Ces corrections ont été motivées
  par des échecs de MES données générées : elles sont partiellement adaptées à ma façon d'écrire.**
- Titres du jeu rendus neutres (sans nom de compétence) et thèmes de mission sans terme du référentiel,
  pour que la vérité terrain des exigences soit exacte.

**Rien n'a été modifié après la passe finale sur la graine de test.**

Test de calibration : le test de permutation sur les noms avait donné p = 0,003 sur la graine 1 (première
version du jeu). Vérifié sur 5 autres graines (p = 0,78 ; 0,35 ; 0,48 ; 0,09 ; 0,43) et par le test direct
(même CV, autre nom : écart 0,00) : coup du sort, pas un biais. Un résultat « significatif » isolé ne
suffit pas à conclure.

## Reproduire

```powershell
cd backend
.venv\Scripts\python.exe -m evaluation.run --seed 2024 --output ..\docs\evaluation\matching-results.md
```
Environ une minute. Les tests du banc d'essai (`tests/test_evaluation_dataset.py`) vérifient que le
générateur est déterministe, que les outils « hors référentiel » sont réellement invisibles, que la
règle de pertinence ne dépend que des attributs cachés, et que l'évaluation recombine les composantes
exactement comme le moteur.

## Suite nécessaire pour que l'évaluation compte

- **Des jugements humains** : faire classer des CV (autorisés) par de vrais recruteurs, plusieurs par
  offre, mesurer leur accord, et comparer au système.
- **Beaucoup plus d'offres** (plusieurs dizaines) pour que les intervalles de confiance permettent de
  trancher entre des variantes proches.
- **Des CV réels et variés** (avec consentement) : colonnes, scans, fautes, formats exotiques.
- **Un audit d'équité sur des données réelles**, incluant les proxys corrélés.
- Comparer aux embeddings (Phase 6) sur ce même banc ; ne les adopter que s'ils apportent un gain
  net, ce qui se mesurera surtout sur les cas inter-langues.
- Vérifier l'équivalence TF-IDF / scikit-learn dès que la bibliothèque est installable.
