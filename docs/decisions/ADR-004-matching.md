# ADR-004 : Matching explicable à composantes pondérées, équité par conception

- **Statut** : accepté (2026-11-11)
- **Décideur** : l'auteur du projet (consigne : approche classique avant les embeddings), sur
  proposition de son assistant technique (Claude)

## Contexte
Classer les CV d'un recruteur pour une offre, de façon que le recruteur comprenne chaque score et
puisse le contester. Aucune caractéristique protégée ne doit influencer le classement. La similarité
sémantique (embeddings) est prévue en Phase 6 : il faut d'abord une baseline mesurable.

## Décisions
| Sujet | Choix | Alternatives écartées |
|---|---|---|
| Structure du score | **5 composantes séparées** (compétences, expérience, études, TF-IDF, mots-clés), combinées par des **poids configurables** ; chaque composante est affichée | Un seul score opaque ; un LLM qui « note » (non reproductible, non explicable) |
| Composante non évaluable | **Écartée** et poids renormalisés ; jamais comptée comme zéro | Compter zéro (pénalise les erreurs de lecture du CV) |
| Expérience | **Années sur des postes qui mobilisent des compétences de l'offre**, chevauchements comptés une fois | Années totales (une candidate en marketing obtenait 26/100 pour un poste DevOps : défaut trouvé par les tests) |
| TF-IDF | **Implémentation directe** de la formule de scikit-learn (IDF lissé, TF sous-linéaire, norme L2) | scikit-learn : installation impossible ici (téléchargement bloqué), et ~100 Mo de dépendances pour 25 lignes |
| Offre | Texte libre analysé par règles, **corrigeable** par le recruteur ; compétence hors référentiel refusée | Saisie 100 % manuelle ; accepter des compétences qu'aucun candidat ne pourrait « avoir » |
| Confiance | Fiabilité **de l'analyse** (CV bien lu, composantes évaluées, offre structurée), pas probabilité de réussite | Pourcentage de « chances » (trompeur) |

## Équité par conception
- Le texte comparé exclut l'**en-tête** (nom, titre, contacts, liens), les **langues parlées** et les
  **centres d'intérêt**. Le nom n'est ajouté à la réponse qu'après le calcul ; `anonymize=true` le retire.
- Le niveau d'études est utilisé, **pas l'établissement**.
- Formes féminines de métiers courants ramenées au masculin avant TF-IDF (liste courte, partielle).
- **Tests par contre-exemple** : changer nom, e-mail, téléphone, lien, titre d'en-tête ou langues
  parlées ne change pas le score ; un test de mutation (réintroduire l'en-tête) fait échouer 8 tests.

## Conséquences et risques résiduels
- (!) **Proxys non traités** : noms de sociétés et villes présents dans la section expérience
  entrent dans le texte comparé ; si une offre cite « Paris », elle favorise les candidats passés par
  Paris. Les écoles sont dans la section formation, également comparée.
- (!) La neutralisation du genre est partielle (≈25 formes).
- (−) Les poids par défaut (45/20/20/10/5) sont des **choix non validés** : ils ne sont calibrés sur
  aucun jugement de recruteur. Leur étude est le sujet de la Phase 5.
- (−) « Expérience pertinente » : un seul point commun suffit à compter un poste entier.
- (−) Pas de persistance des classements ni de piste d'audit ; pas de validation humaine formalisée
  (prévue avec les agents, Phase 10).
