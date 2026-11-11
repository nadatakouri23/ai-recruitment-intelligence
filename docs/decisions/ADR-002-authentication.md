# ADR-002 : Authentification par JWT, mots de passe Argon2, rôles

- **Statut** : accepté (2026-11-11)
- **Décideur** : l'auteur du projet, sur proposition de son assistant technique (Claude)

## Contexte
Les CV sont des données personnelles : seuls des utilisateurs identifiés doivent y accéder, et
un recruteur ne doit pas pouvoir administrer la plateforme.

## Décisions
| Sujet | Choix | Alternatives écartées |
|---|---|---|
| Hachage | **Argon2** (`argon2-cffi`) | bcrypt (limite de 72 octets) ; `passlib` (non maintenu) ; SHA-256 (trop rapide) |
| Jeton | **JWT HS256** signé, 30 minutes, via **PyJWT** | Sessions serveur (état à stocker) ; `python-jose` (moins maintenu) |
| Accès base | **SQLAlchemy 2 synchrone** + psycopg 3 | Mode asynchrone (complexité sans besoin de charge) |
| Rôles | `recruiter` / `admin` ; l'inscription publique crée toujours un recruteur | Rôle choisi à l'inscription (élévation de privilèges) |
| Premier admin | Script `python -m app.cli.create_admin` | Route d'API dédiée (surface d'attaque) |
| Organisation | Module par fonctionnalité `modules/authentication/` | Dossiers par type technique |
| Tests | Base PostgreSQL de test dédiée, migrations rejouées | SQLite (comportements différents de la production) |

## Mesures de sécurité retenues
- Message d'erreur de connexion unique, hachage factice si l'e-mail est inconnu (anti-énumération).
- Algorithmes JWT imposés au décodage ; `exp` et `sub` obligatoires ; `alg: none` refusé (testé).
- Secret JWT obligatoire, sans valeur par défaut, jamais versionné.
- Longueur maximale de mot de passe (128) pour éviter un déni de service par hachage coûteux.
- Journalisation d'identifiants (`user_id`) uniquement, jamais d'e-mail, de mot de passe ou de jeton.

## Conséquences et limites
- (−) Un JWT n'est pas révocable avant expiration. Durée courte comme atténuation ; refresh
  tokens ou liste de révocation à envisager plus tard.
- (−) Pas de limitation de débit sur `/auth/login` pour l'instant.
- (−) Pas de vérification d'e-mail ni de réinitialisation de mot de passe.
