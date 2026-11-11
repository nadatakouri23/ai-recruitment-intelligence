# Journal de développement

Ce journal décrit ce qui a **réellement** été fait, par qui, et ce qui reste à faire.

## Légende des contributions
- **Auteur** : décisions, validation de l'architecture, exécution et vérification des commandes.
- **Claude** (assistant IA) : rédaction du code et de la documentation, relue par l'auteur.

## Phase 0 : Fondations (2026-11-10 → 2026-11-11)

### Décisions de l'auteur
Monolithe modulaire + PostgreSQL/pgvector ; RAG écrit à la main avant LangGraph ;
CV et offres en français et en anglais ; aucun LLM avant la phase 7 ; dépôt nommé
`talent-intelligence-platform` ; logging avec `structlog` ; PostgreSQL sur le port hôte 5433.

### Travail réalisé

| Étape | Contenu | Écrit par |
|---|---|---|
| 1 | `git init`, arborescence, `.gitignore` | Claude |
| 2 | Environnement virtuel `backend/.venv` | Claude |
| 3 | `requirements.txt` (fastapi, uvicorn, pydantic-settings, structlog) | Claude |
| 4 | `core/config.py`, `.env.example` | Claude |
| 5 | `core/logging.py` | Claude |
| 6 | `main.py` (factory), `api/health.py` | Claude |
| 7 | `tests/conftest.py`, `tests/test_health.py`, config pytest | Claude |
| 8 | Configuration Ruff | Claude |
| 9 | `docker-compose.yml`, `scripts/init-db.sql` | Claude |
| 10 | `.github/workflows/ci.yml` | Claude |
| 11 | README, ADR-001, architecture, ce journal | Claude |

L'auteur a exécuté et vérifié lui-même le lancement de l'API, Ruff et pytest (2026-11-11).

### Vérifications effectuées
- `pytest` : 3 tests passent (également sur une copie sans `.env`, pour simuler la CI).
- `ruff check` et `ruff format --check` : sans erreur.
- `GET /health` : 200 `{"status":"ok"}`.
- PostgreSQL : conteneur `healthy`, extension `vector` 0.8.7 active, opérateur `<=>` fonctionnel.
- Contrôle de secrets : aucune valeur sensible dans les fichiers à commiter.

### Incidents
- Une réécriture de `health.py` via PowerShell 5.1 a corrompu l'encodage (accents) et ajouté un BOM.
  Corrigé ; Ruff a détecté le BOM. Règle adoptée : ne pas réécrire de fichiers via PowerShell.
- `app = create_app()` à l'import faisait dépendre les tests du `.env`. Supprimé au profit de
  `uvicorn --factory`.

### Problèmes connus et dette technique
- La CI n'a **pas encore été exécutée** : elle ne peut l'être qu'après un push sur GitHub.
- Aucun commit n'a été créé à ce jour.
- Les logs d'accès d'Uvicorn ne sont pas structurés (seuls ceux de l'application le sont).
- Pas de verrouillage complet des dépendances transitives.
- Avertissement de dépréciation `httpx` / `starlette.testclient` dans les tests.
- Aucun test sur `config.py` ni `logging.py`.
- Connexion à PostgreSQL depuis l'hôte (`localhost:5433`) non testée : aucun pilote Python installé.
- Pas de sauvegarde du volume PostgreSQL ; identifiants de développement uniquement.

## Phase 1 : Authentification et utilisateurs (2026-11-11)

### Qui a écrit quoi
Tout le code de cette phase a été écrit par **Claude**, à la demande explicite de l'auteur
(« compléter tout le projet »). Le plan prévoyait que l'auteur écrive les modules principaux ;
ce n'a pas été le cas. L'auteur n'a pas encore relu ni modifié ce code.

### Travail réalisé
- Dépendances : SQLAlchemy 2.1, Alembic, psycopg 3, argon2-cffi, PyJWT, email-validator, python-multipart.
- `core/database.py` : moteur, fabrique de sessions, `Base`.
- `core/security.py` : hachage Argon2, création et validation de JWT.
- `modules/authentication/` : modèle `User`, schémas, repository, service, routes.
- `api/deps.py` : session par requête, `get_current_user`, `require_admin`.
- Migration Alembic `create users table` (relue, testée en `upgrade`/`downgrade`).
- `app/cli/create_admin.py` : création du premier administrateur (mot de passe saisi de façon masquée).
- Routes : `POST /auth/register`, `POST /auth/login`, `GET /users/me`, `GET /users` (admin).
- CI : service PostgreSQL ajouté.

### Vérifications effectuées
- 33 tests passent (unitaires sécurité, intégration API sur une base `talent_platform_test`,
  synchronisation modèles/migrations). Également dans une copie sans `.env` configurée par
  variables d'environnement (simulation de la CI).
- Test de mutation manuel : désactiver le contrôle admin fait échouer
  `test_recruiter_cannot_list_users` (le test détecte bien la faille).
- Test de bout en bout avec un vrai serveur : inscription, login, `/users/me`, 403 pour un
  recruteur, 401 sans jeton, liste complète pour un admin, script `create_admin`.
- Aucun mot de passe, e-mail ou jeton dans les logs du serveur lors de ce scénario.

### Décisions de conception
- Inscription publique : le rôle est toujours `recruiter` ; un admin ne se crée que par le script.
- Mots de passe : 12 à 128 caractères ; Argon2 ; message d'erreur de connexion identique pour
  email inconnu / mauvais mot de passe / compte désactivé, et hachage factice pour égaliser le temps.
- JWT HS256, durée 30 minutes (configurable), algorithmes imposés au décodage.
- E-mails normalisés (minuscules, sans espaces) avant stockage et recherche.

### Incidents
- `.env` avait un BOM (mon fichier de l'étape 4), ce qui faisait ignorer silencieusement `APP_NAME`.
  Corrigé. `extra="ignore"` masque ce genre d'erreur.
- `localhost` se résout en IPv6 d'abord sous Windows alors que Docker n'écoute qu'en IPv4 :
  connexions très lentes ou bloquées. L'hôte par défaut est maintenant `127.0.0.1`.
- Collision de nom entre notre dossier `backend/alembic/` et la bibliothèque : déclarée à Ruff
  (`known-third-party`).

### Problèmes connus et dette technique (Phase 1)
- **Pas de limitation de débit** : la force brute sur `/auth/login` n'est pas freinée.
- **Pas de révocation de jeton** : la « déconnexion » consiste à oublier le jeton ; un jeton volé
  reste valable jusqu'à son expiration.
- `POST /auth/register` révèle qu'une adresse existe déjà (409). Compromis accepté pour la
  facilité d'usage ; à revoir si l'exposition publique devient un enjeu.
- Pas de vérification de l'adresse e-mail, pas de réinitialisation de mot de passe.
- Les logs applicatifs n'ont pas de test automatique garantissant l'absence de données sensibles
  (vérifié manuellement une fois).
- La CI n'a toujours pas tourné sur GitHub.
- Aucun commit n'a encore été créé pour la Phase 1.

## Phase 2 : Traitement des CV (2026-11-11)

### Qui a écrit quoi
Tout le code a été écrit par **Claude**, à la demande de l'auteur. L'auteur n'a pas relu ni modifié
ce code à ce jour.

### Travail réalisé
- Import de CV PDF/DOCX : `POST /candidates` (multipart), `GET /candidates` (filtres `q`, `skill`,
  pagination), `GET /candidates/{id}`, `GET /candidates/{id}/text`, `DELETE /candidates/{id}`.
- `modules/documents/` : validation (taille, extension ET signature réelle, DOCX = archive ZIP
  contrôlée contre les « zip bombs »), extraction PDF (pdfplumber, limite de pages) et DOCX
  (paragraphes + tableaux, dans l'ordre), stockage sous nom UUID généré.
- `modules/candidates/parsing/` : nettoyage de texte, découpage en sections FR/EN, dates (mois en
  lettres/chiffres, « présent »), référentiel de compétences bilingue (136 compétences), extracteurs
  (contact, expérience, formation, projets, langues, certifications), détection de langue, rapport
  d'extraction (complétude, avertissements, limites).
- Profil structuré (`profile.py`) : chaque information porte sa provenance (section + extrait) et son
  origine `extracted` / `inferred` (durées et total d'expérience = déduits).
- Migration Alembic `create documents and candidates tables` (JSONB, clés étrangères en cascade).
- 6 CV synthétiques (FR/EN, PDF/DOCX, mises en page variées) dans `data/samples/cvs/`, générés par
  `scripts/generate_sample_cvs.py`, avec vérité terrain dans `backend/tests/cv_factory.py`.
- Tests : 190 au total (157 ajoutés dans cette phase), également dans une copie sans `.env`.

### Décisions de conception
- **Propriété stricte** : chaque requête filtre par `owner_id`, même pour un administrateur ;
  l'accès à la ressource d'un autre renvoie 404 (identique à « n'existe pas »).
- **Caractéristiques protégées** : date de naissance, nationalité, genre, situation familiale,
  adresse et photo ne sont volontairement pas extraites (testé).
- **Pas de LLM** : extraction par règles, déterministe. Un LLM (Phase 7) sera comparé sur les mêmes CV.
- Les noms de fichier envoyés ne servent qu'à l'affichage (nettoyés) ; le disque reçoit un UUID.
- Aucun nom, e-mail ou nom de fichier dans les logs (vérifié sur un serveur réel).

### Vérifications effectuées
- 190 tests passent ; Ruff et `alembic check` propres.
- Tests de mutation manuels : retirer le filtre `owner_id` fait échouer 2 tests d'isolation ; retirer
  la suppression du fichier fait échouer le test de suppression.
- Test réel : serveur Uvicorn, 6 CV envoyés par `curl`, recherche française, suppression avec
  disparition du fichier, faux PDF refusé ; base de développement et `data/uploads` intactes.

### Mesure sur les CV synthétiques : À INTERPRÉTER AVEC PRUDENCE
Précision et rappel des compétences : 1,00 / 1,00 sur les 6 CV. **Ces CV ont été écrits par Claude
et le parseur a été ajusté en les observant.** Ce chiffre sert de garde-fou contre les régressions ;
il ne dit RIEN de la performance sur de vrais CV, qui sera plus faible. Voir `docs/evaluation/`.

### Bogues trouvés grâce aux tests
- Puces de PDF extraites sous la forme `(cid:127)` : un projet était coupé en deux. Corrigé.
- Titre et entreprise sur deux lignes au-dessus de la date : titre faux. Corrigé (jusqu'à 2 lignes).
- Faux positifs de compétences (`github.com/...`, « vue d'ensemble », « tableau de bord », « Spring 2020 »,
  `R&D`…) : corrigés par alias stricts et tests de pièges.
- Un test de doublon était faux (reportlab rend des octets différents à chaque PDF) : corrigé, et la
  limite réelle documentée (voir ci-dessous).

### Problèmes connus et dette technique (Phase 2)
- **Extraction par règles** : un CV à colonnes, tableaux complexes ou mise en page atypique sera mal
  lu. Les titres/entreprises sont déduits de la forme des lignes et peuvent être inversés.
- **Référentiel limité** (136 compétences, plutôt tech/data) : toute autre compétence est ignorée.
  Un CV non technique donne donc peu de compétences.
- **Pas d'OCR** : un PDF scanné est refusé avec un message explicite (422).
- **Doublons exacts à l'octet près** : le même CV ré-exporté n'est pas reconnu comme doublon.
- **Fichiers stockés en clair** dans `data/uploads/`, texte extrait en clair en base : à protéger par
  chiffrement du disque / de la base avant tout usage réel.
- **Parsing de fichiers non fiables dans le processus de l'API**, sans délai maximal (timeout) ni
  isolation : taille (5 Mo) et pages (30) sont limitées, mais un PDF malveillant peut encore coûter
  du CPU. Pas d'analyse antivirus.
- **Pas de limitation de débit** sur les imports.
- **Supprimer un utilisateur en base** supprime ses lignes en cascade mais PAS ses fichiers sur
  disque (il n'existe pas encore de route de suppression d'utilisateur).
- Le nom du candidat est stocké dans le profil : **le matching (Phase 4) devra l'ignorer** pour ne pas
  introduire de biais (les prénoms/noms sont corrélés à des caractéristiques protégées).
- Pas d'index GIN sur le profil JSONB : le filtre par compétence parcourt la table (acceptable à petite
  échelle).
- Pas de suivi du consentement des candidats (RGPD) ; seule la suppression existe.

## Phase 4 : Matching (2026-11-11), avec le minimum de la Phase 3

### Qui a écrit quoi
Tout le code a été écrit par **Claude**, à la demande de l'auteur (« passer à la phase 4 »). L'auteur
n'a pas relu ni modifié ce code à ce jour.

### Écart par rapport à la feuille de route
La Phase 3 (offres d'emploi) était un prérequis du matching : j'ai construit **le strict nécessaire**
(création d'une offre en texte libre, analyse par règles, correction par le recruteur, liste,
suppression). Il manque encore à la Phase 3 : import d'offres en fichier PDF/DOCX, extraction par LLM,
interface.

### Travail réalisé
- `modules/jobs/` : `POST/GET/PATCH/DELETE /jobs`, analyse du texte (compétences requises/optionnelles,
  années d'expérience, niveau d'études, missions, préférences), migration `create jobs table`.
- `modules/matching/` : `POST /jobs/{id}/matches`. Composantes : compétences, expérience pertinente,
  niveau d'études, TF-IDF, mots-clés ; poids configurables (défaut serveur ou par requête) ;
  composantes non évaluables écartées ; explications, preuves, expérience pertinente, avertissements,
  confiance, limites ; mode anonyme.
- Corrections du parseur de CV découvertes en chemin : « maîtrise » pris pour le diplôme Bac+4,
  Excel classé comme compétence technique, portée des indices « un plus » (phrase et non ligne).
- Tests : 344 réussis + 1 ignoré (équivalence scikit-learn), dont 154 ajoutés dans cette phase.

### Vérifications effectuées
- 344 tests passent, également en simulation de CI sans `.env` ; Ruff et `alembic check` propres.
- Tests de mutation : réintégrer l'en-tête et les langues dans le texte fait échouer 8 tests ;
  utiliser l'expérience totale fait échouer 2 tests ; retirer le filtre par propriétaire des offres
  fait échouer le test d'isolation.
- Test réel : serveur Uvicorn, 6 CV importés depuis les fichiers, 4 offres analysées et classées,
  mode anonyme, poids personnalisés ; aucune donnée personnelle dans les logs ; base de développement
  et `data/uploads` intactes.

### Décision subie : TF-IDF sans scikit-learn
`pip install scikit-learn` a échoué à plusieurs reprises : les téléchargements depuis
`files.pythonhosted.org` étaient coupés (« connexion abandonnée par un logiciel de l'ordinateur hôte »,
sans doute antivirus ou pare-feu). TF-IDF est donc implémenté directement, avec la même formule que
`TfidfVectorizer` (voir `matching/tfidf.py`). Le test d'équivalence existe mais **n'a jamais été exécuté**.
Si scikit-learn s'installe un jour, lancer ce test ; on pourra alors, au choix, le garder ou passer à
la bibliothèque.

### Défauts trouvés grâce aux tests, et corrigés
- Une candidate en marketing obtenait 26/100 pour un poste DevOps (années totales + master comptés) :
  l'expérience est désormais l'expérience **pertinente**.
- La confiance d'un CV illisible était « moyenne » : la qualité de lecture du CV pèse maintenant 50 %.
- « Maîtrise de Python » était lu comme un diplôme Bac+4.

### Problèmes connus et dette technique (Phase 4)
- **Aucune évaluation réelle du classement** : jeux d'essai écrits par nous, jugés par nous. Voir
  `docs/evaluation/matching.md`.
- **Poids par défaut non validés** (45/20/20/10/5).
- **« Expérience pertinente » trop généreuse** : une seule compétence en commun suffit à compter un
  poste entier (constaté : une data scientist obtient 1,00 en expérience pour un poste DevOps parce que
  deux postes citent Docker et CI/CD).
- **Niveau d'études sans le domaine** : un master quelconque donne le score maximal pour tout poste.
- **Proxys de biais non traités** : noms de sociétés et villes de la section expérience, écoles de la
  section formation. Neutralisation du genre limitée à ≈25 formes.
- **TF-IDF lexical** : pas de synonymes ni de passage FR/EN (les compétences normalisées compensent
  en partie) ; valeurs dépendantes du lot ; peu significatives avec très peu de candidats.
- **Analyse d'offre par règles** : « R », « Go », « C » ne sont pas détectés dans le texte d'une offre
  (à ajouter par correction) ; la séparation requis/optionnel est heuristique.
- **Composantes écartées** : un candidat dont l'expérience est illisible voit ses poids renormalisés,
  ce qui peut le favoriser ou le défavoriser ; c'est signalé mais non résolu.
- **Pas de persistance ni de piste d'audit** des classements ; pas de validation humaine formalisée.
- **Plafond de 500 candidats** par classement (1,2 s mesurées sur des CV courts).

## Phase 5 : Évaluation du matching (2026-11-11)

### Qui a écrit quoi
Tout le code et les rapports sont de **Claude**, à la demande de l'auteur (« passer à l'étape 5 »).
L'auteur n'a pas relu ni modifié ce code à ce jour.

### Travail réalisé
- `modules/evaluation/metrics.py` : Precision@K, Recall@K, DCG/NDCG@K (gain exponentiel), MRR, moyenne
  des valeurs définies, intervalle de confiance bootstrap, différence appariée. 20 tests, valeurs
  calculées à la main.
- `backend/evaluation/` (banc d'essai, hors de l'application) : générateur de 126 CV et 11 offres à
  partir d'attributs cachés, règle de pertinence 0-3, jumeaux pour l'audit d'équité, exécution complète
  et génération du rapport. 35 tests.
- Protocole dev / test avec deux graines (1 et 2024), rapports dans `docs/evaluation/`.

### Résultat principal (graine de test 2024, 11 offres)
NDCG@10 : poids par défaut 0,916 [0,88–0,95] ; compétences + expérience 0,899 ; compétences seules 0,870 ;
mots-clés seuls 0,872 ; TF-IDF seul 0,825 ; aléatoire 0,188. **Les poids par défaut ne sont pas
confirmés comme optimaux** : sur la graine dev, la conclusion était inverse. Voir
`docs/evaluation/matching.md` pour ce qu'on peut et ne peut pas en conclure.

### Vérifications effectuées
- 403 tests passent (1 ignoré : équivalence scikit-learn, jamais exécutée) ; Ruff et `alembic check` propres.
- Calibration du test de permutation sur 5 graines supplémentaires, sans toucher à la graine de test.
- Aucune modification du moteur ou des poids après la passe finale sur la graine de test.

### Défauts du système trouvés grâce au banc d'essai, et corrigés
- Les outils ambigus (`Spark`, `Tableau`, `Excel`, `Spring`) n'étaient pas reconnus en début de puce ou
  dans une liste d'exigences d'une offre : mode « listing » et règle de contexte (voir
  `candidates/parsing/skills.py`). **Corrigé d'après mes propres données générées : peut être trop
  adapté à ma façon d'écrire.**
- Un test de permutation donnait p = 0,003 sans signification réelle : enquêté, non reproduit.

### Problèmes connus et dette technique (Phase 5)
- **Le résultat dépend d'un jeu écrit par l'auteur du système** : aucune validation humaine. C'est la
  principale limite du projet à ce stade.
- **Jeu trop favorable aux compétences** : vocabulaires de métiers presque disjoints, règle de pertinence
  fondée sur les compétences.
- **Poids non identifiables avec 11 offres** : ne pas les optimiser tant qu'il n'y a pas de données réelles.
- **Audit d'équité limité** : jumeaux sur les éléments pensés à l'avance ; puissance faible ; pas de
  corrélations réalistes entre origine et parcours.
- **Parseur ajusté sur mes propres CV** : la robustesse sur des CV réels est inconnue.
- Le banc d'essai importe `tests.cv_factory` : le générateur de PDF vit dans le dossier de tests.
- Équivalence TF-IDF / scikit-learn toujours non vérifiée.
- Rapports « dev » et « test » générés avec la date de calcul fixée à 2026-11-11 pour les postes en cours.

## Phase 6 : Embeddings et recherche sémantique (2026-11-11)

### Qui a écrit quoi
Tout le code est de **Claude**, à la demande de l'auteur (« compléter l'étape 6 »). L'auteur n'a pas
relu ni modifié ce code à ce jour.

### Travail réalisé
- `modules/embeddings/` : interface `Embedder` (modèle local `paraphrase-multilingual-MiniLM-L12-v2`,
  384 dimensions, ou doublure déterministe `hashing`), découpage des CV en passages sans identité,
  table `candidate_chunks` (pgvector, index HNSW cosinus), indexation à l'import (jamais bloquante),
  `POST /search/candidates` (mots-clés, sémantique, hybride par fusion de rangs RRF), `GET /search/status`,
  `POST /search/reindex`.
- 6ᵉ composante du score de matching « sémantique », **poids 0 par défaut**.
- Migration `create candidate chunks table` (écrite à la main en partie : l'extension `vector` doit
  être activée par la migration elle-même, sinon elle échoue sur une base neuve).
- Banc d'essai étendu : variantes sémantiques, évaluation de la recherche (27 requêtes), équité du
  sémantique. Graine de développement 1, graine vierge 4242, règles de décision écrites avant la passe finale.
- Installation réelle de `scikit-learn` (le test d'équivalence TF-IDF **passe enfin**), PyTorch,
  sentence-transformers. `requirements-ml.txt` pour les dépendances optionnelles.
- Tests : 492 au total (88 ajoutés), aucun ignoré sur cette machine ; en CI, les tests du vrai
  modèle sont ignorés (modèle absent du cache).

### Résultat principal (graine vierge 4242)
Le sémantique **n'améliore pas** le score de matching par défaut (écart −0,005, indécidable) : poids
laissé à 0. Il **efface la pénalité inter-langues** du TF-IDF. En recherche, l'hybride égale les
mots-clés sur les requêtes descriptives et les dépasse sur les requêtes à outils (`auto` = hybride).
Détails et réserves : `docs/evaluation/semantic.md`.

### Vérifications effectuées
- 492 tests, Ruff, `alembic check`.
- Tests de mutation : retirer le filtre par propriétaire de la requête vectorielle, retirer le filtre
  sur le modèle, rendre l'import fragile à une panne d'indexation : trois détectés. **La troisième
  n'était pas détectée au premier essai** (un `try/except` interne masquait l'externe) : test ajouté.
- Vrai modèle chargé : similarité 0,93–0,95 entre phrases équivalentes FR/EN, 0,14–0,24 entre phrases sans rapport.

### Défauts trouvés et corrigés en route
- Migration autogénérée sans `import pgvector` ni activation de l'extension.
- Mon script de téléchargement du modèle avait récupéré tout le dépôt (2,8 Go de variantes ONNX
  inutiles) : arrêté et nettoyé, le cache fait 454 Mo.
- Sensibilité au genre des embeddings (32 % de scores modifiés) : neutralisation avant vectorisation,
  point d'entrée unique `embed_texts` imposé par un test structurel.
- Formes féminines absentes de la liste (« Intégratrice ») ajoutées.

### Problèmes connus et dette technique (Phase 6)
- **Sémantique évalué sur un jeu écrit par moi**, avec des requêtes écrites par moi et partageant des
  tournures avec les CV. Aucun recruteur n'a jugé.
- **Sensibilité aux villes et aux écoles** : 98 % des scores sémantiques changent quand on remplace les
  villes, 5 % du top 10 bouge. Nettement plus sensible que le lexical. Non corrigé.
- **Passages de formation = noms d'écoles** : risque de prestige/origine encodé par le modèle. Non mesuré sur des données réelles.
- **Neutralisation du genre partielle** (≈ 25 formes).
- **Le modèle ne lit que ~128 tokens** : passages courts, contexte perdu entre passages.
- **Dépendances lourdes** (PyTorch ~200 Mo + modèle ~450 Mo) : optionnelles mais non testées en CI.
- **Licence du modèle non revérifiée** (à contrôler avant tout usage commercial).
- **Pas de recherche vectorielle approximative testée à l'échelle** : l'index HNSW existe mais la base
  contient quelques centaines de passages ; ses performances à 100 000 CV ne sont pas mesurées.
- Un modèle indisponible au démarrage est journalisé et désactive silencieusement le sémantique
  (visible dans `/search/status`) au lieu de bloquer l'API.

## Phase 7 — Couche LLM (2026-11-11)
Code écrit par Claude, **non relu par l'utilisateur**.

### Réalisé
- Interface `LLMProvider.complete_json` ; Gemini, Mistral, Groq en HTTP direct (httpx), faux fournisseur de test.
- Désactivé par défaut (`LLM_PROVIDER=none`). Clé manquante : erreur 503 qui nomme la variable.
- Routes : `/llm/status`, extraction et résumé d'un CV, analyse d'une offre, explication d'un classement.
- Garde-fous : consentement explicite à chaque appel ; texte anonymisé + expurgé (e-mails, téléphones, liens)
  et plafonné ; document non fiable enfermé dans `<document>` (balises forgées neutralisées) ;
  chaque compétence / expérience / formation exige une citation exacte retrouvée dans le texte envoyé,
  sinon écartée et comptée ; résumé ou explication retenus s'ils citent une compétence absente ;
  suggestions jamais appliquées ; erreurs sans URL, clé ni contenu ; journaux sans texte.
- Tests : 102 nouveaux (fournisseurs, garde-fous, API de bout en bout avec un faux modèle menteur).
  Suite complète : 594 réussis, Ruff propre, `alembic check` sans écart.
- Mutations vérifiées : citations toujours valides (9 tests échouent), consentement désactivé (2), isolation entre recruteurs (1).

### Problèmes connus et dette technique (Phase 7)
- **Test réel minimal (2026-11-11)** : une extraction sur un court texte synthétique a réussi avec Groq (`openai/gpt-oss-20b`) et Gemini (`gemini-3.1-flash-lite`, un 503 absorbé par les retries) ; `gemini-3.8-flash` expirait. **Mistral jamais appelé.** Format des erreurs 429 non vérifié. Un seul texte de 4 compétences : rien sur la qualité.
- **Qualité d'extraction non évaluée** face à l'extraction par règles ; la comparaison est exposée dans la réponse mais pas mesurée.
- **Injection** : testée seulement avec un faux modèle ; le comportement de vrais modèles est inconnu. Une citation prouve qu'une phrase est dans le CV, pas qu'elle est vraie.
- Les noms d'écoles, villes et sociétés restent dans le texte envoyé (proxys de biais) ; seuls nom, contacts et liens sont retirés.
- Le consentement est une case à cocher par requête, sans journal d'audit ni politique de conservation du fournisseur.
- Pas de limitation de débit ni de suivi du coût.
