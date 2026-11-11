# ADR-003 : Analyse des CV par règles, profil traçable, propriété stricte

- **Statut** : accepté (2026-11-11)
- **Décideur** : l'auteur du projet (consigne : pas de LLM avant la Phase 7), sur proposition de
  son assistant technique (Claude)

## Contexte
Il faut transformer des CV PDF/DOCX non fiables, en français et en anglais, en données structurées
exploitables pour le matching, sans inventer d'information et sans exposer de données personnelles.

## Décisions
| Sujet | Choix | Alternatives écartées |
|---|---|---|
| Extraction | **Règles + référentiel bilingue** (déterministe, testable, sans coût ni fuite de données vers un tiers) | LLM : plus souple mais coûteux, non déterministe, envoie des données personnelles à un tiers (Phase 7 : à comparer) |
| Lecture PDF | **pdfplumber** | PyMuPDF (licence AGPL à vérifier) ; OCR (non implémenté : refus explicite des scans) |
| Représentation | **Profil Pydantic** avec `origin` (extrait / déduit) et `provenance` (section + extrait) | Dictionnaire libre (aucune traçabilité) |
| Stockage du profil | **JSONB** + copies du nom/e-mail en colonnes | Tables relationnelles par compétence/expérience (plus rigides tant que le modèle bouge) |
| Fichiers | Disque local, **nom UUID généré** | Nom d'origine (traversée de dossier) ; stockage objet (pas nécessaire en local) |
| Accès | **Filtre `owner_id` dans chaque requête**, 404 pour la ressource d'un autre, y compris pour un admin | Admin voit tout (moins de confidentialité des candidats) |
| Doublons | Empreinte SHA-256 du fichier, unique par propriétaire | Empreinte du texte extrait (détecterait les ré-exports ; non fait) |

## Principes éthiques appliqués
- Les caractéristiques protégées (naissance, nationalité, genre, situation familiale, adresse, photo)
  ne sont **pas extraites** ; les centres d'intérêt sont reconnus comme section mais non analysés.
- Une information absente reste absente (`None`) : rien n'est deviné. Les valeurs calculées sont
  marquées `inferred`.
- Le rapport d'extraction affiche une **complétude** (pas une exactitude) et les limites connues.

## Conséquences et risques
- (−) Qualité limitée sur les CV atypiques ; les chiffres sur CV synthétiques ne sont pas
  représentatifs (voir `docs/evaluation/cv-parsing.md`).
- (−) Données personnelles stockées en clair (fichier et texte) : chiffrement à prévoir.
- (−) Parsing de fichiers hostiles dans le processus de l'API, sans timeout ni isolation.
- (!) Le nom est présent dans le profil : le matching devra le masquer pour éviter les biais.
