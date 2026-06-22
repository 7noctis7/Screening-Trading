# CLAUDE.md — contexte auto-chargé à chaque session

> Ce fichier est lu automatiquement par Claude Code au démarrage. Il ne **duplique** pas la mémoire :
> il dit **où** la lire et **quelles règles** ne jamais enfreindre. La source de vérité reste le vault.

## Le projet en une ligne
**Quant Terminal** — screening & trading systématique multi-actifs (actions, ETF, forex, crypto,
commodités), niveau institutionnel, 100 % open-source. **Paper par défaut.** Front Next.js + API FastAPI.
Priorités : robustesse > maintenabilité > gestion du risque > alpha > produit.

## Mémoire (rituel — à faire SANS qu'on le redemande)
1. **Lire avant d'agir** : `vault/00_INDEX.md` → `vault/01_ARCHITECTURE.md` → `vault/04_JOURNAL.md`
   (3 dernières sessions) → `vault/03_TODO.md`.
2. Reformuler en 3 lignes : état du projet + prochaine priorité.
3. Agir par petits incréments **testés**.
4. **Clôturer** : maj `03_TODO`, entrée datée `04_JOURNAL`, ADR dans `02_DECISIONS` si choix
   structurant, maj des diagrammes si l'archi change, miroir Notion, push.

## En ligne (PWA gratuite)
**https://7noctis7.github.io/Screening-Trading/** — front complet en statique, données réelles,
reconstruit chaque jour ouvré par GitHub Actions (`.github/workflows/pages.yml`). Mac éteint, 0 €.

## Commandes clés
| Commande | Rôle |
|---|---|
| `make test` | suite de tests (pytest) — **lancer avant tout commit** |
| `make start` | API + front en local (positions réelles si `.env` présent) |
| `make site` | build du site statique mobile (watchlist + top 200 → `localhost:8080`) |
| `make watchlist` | régénère `config/mobile_universe.csv` + miroir Obsidian |
| `make reports` | notes d'analyse institutionnelles → `out/notes/` + vault |
| `make audit` | audit PwC des bases de prix |

## GARDE-FOUS (ne jamais enfreindre)
- **Paper par défaut.** Aucun ordre réel sans `--live --yes` **ET** clés API présentes.
- **Jamais committer** `.env`, `*.db` (YAHOO/market/crypto), `.cache/`, `site/`, `apps/web/public/{data,reports}` — déjà gitignorés. Vérifier avant un `git add -A`.
- **Repo PUBLIC** : aucune donnée confidentielle. Les **positions réelles courtier sont local-only**
  (le build CI n'a pas les clés). gitleaks tourne en CI + pre-commit.
- **Push uniquement sur** `claude/clever-lovelace-ognwya` (jamais `main` en direct).
- **Identifiant de modèle** : ne jamais l'écrire dans un commit, une PR, un commentaire de code ou un artefact (chat uniquement).
- **Déploiement** = PR → squash-merge → `git fetch origin main && git reset --hard origin/main && push --force` sur la branche. Voir le skill `/deploy`.
- **Compte GitHub** : ne pas le renommer pendant un run Actions (invalide le jeton OIDC → deploy KO).

## Pièges connus (déjà corrigés — ne pas régresser)
- Export statique : le JSON doit être **NaN-safe** (`scripts/dump_static.py::_clean`) sinon les pages
  restent bloquées en chargement.
- `real_macro_store` aligne valeurs↔dates (l'indice réel est plus long que le calendrier univers en CI).
- Historique CI **depuis 2015** (`QUANT_HISTORY_DAYS=4015`, ingest `--since 2015-01-01`).
- `pickle` chargé uniquement via `packages/common/safe_pickle` (anti-symlink + hash).

## Sécurité (acquis)
CORS API verrouillé sur localhost (`QUANT_CORS_ORIGINS` pour élargir) · webhook protégé
(`QUANT_WEBHOOK_TOKEN` sinon localhost) · secrets en env (`.env.example` documente tout).
