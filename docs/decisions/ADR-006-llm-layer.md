# ADR-006 : Couche LLM optionnelle, multi-fournisseurs, avec garde-fous

- **Statut** : accepté (2026-11-11), **validé seulement par un appel minimal Groq et Gemini ; Mistral jamais appelé**
- **Décideur** : l'auteur du projet (consigne : Gemini / Mistral / Groq, LLM à partir de la phase 7), sur proposition de son assistant technique (Claude)

## Contexte
Les règles lisent mal les CV atypiques et ne rédigent rien. Un LLM peut aider, mais envoie du texte
personnel à un tiers, peut inventer, et obéit à des instructions cachées dans un CV.

## Décisions
| Sujet | Choix | Alternatives écartées |
|---|---|---|
| Accès | HTTP direct (httpx) derrière `LLMProvider.complete_json` | SDK de chaque fournisseur : dépendances et comportements cachés |
| Activation | Désactivée par défaut ; clé en variable d'environnement | Activée dès qu'une clé existe |
| Consentement | Champ `confirm_external_processing` **obligatoire** à chaque appel | Réglage global unique |
| Données envoyées | Texte anonymisé, expurgé (e-mail, téléphone, liens), plafonné | CV brut |
| Injection | Document enfermé dans `<document>`, balises forgées neutralisées, consigne « donnée non fiable » | Confiance dans le modèle |
| Hallucination | Citation exacte exigée pour chaque élément, vérifiée par notre code ; sinon écarté | Valider le seul format JSON |
| Autorité | Le LLM suggère ; rien n'est appliqué ni classé automatiquement | Écriture directe dans les profils |
| Erreurs | Messages génériques ; la clé Gemini passe dans l'URL, donc exceptions réécrites sans URL | Relayer l'erreur du fournisseur |

## Limites assumées
- La vérification des citations garantit la **présence** dans le document, pas la **véracité** ni la pertinence.
- Un modèle réel peut contourner les consignes malgré la délimitation ; seul un faux modèle a été testé.
- Les modèles par défaut ne sont pas vérifiés comme économiques. Aucune mesure de coût ni de qualité.
- Les proxys de biais (écoles, villes, sociétés) ne sont pas retirés du texte envoyé.

## À faire avant tout usage réel
Fournir des clés, appeler chaque fournisseur, mesurer l'extraction contre les règles sur des CV
autorisés, tester des CV piégés, vérifier les conditions de rétention de données du fournisseur.
