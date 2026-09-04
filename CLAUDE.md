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
   structurant, maj des diagrammes si l'archi change, miroir Notion, push. → skill **`/close-session`**.

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
| `make audit` | audit PwC des bases de prix (gate CI : `--strict`) |
| `make brief` | brief unifié (priorités + journal + diffs + audit) — démarrage de session |
| `make sync` | récupère la branche de dev **sans conflit possible** (jamais `git pull` dessus) |
| `make labs` | les 4 bancs de mesure : candidats, sorties, dimensionnement, recouvrement des signaux |
| `make vault-search Q="..."` | recherche sémantique locale du vault (TF-IDF ; Ollama optionnel ; `--code`) |
| `make contracts` | gate d'intégrité OHLCV (bloque l'impossible) — aussi en CI |
| `make hf-push` / `hf-pull` | cache OHLCV souverain (HuggingFace, anti rate-limit yfinance) |
| `make notion-sync` | miroir Obsidian → Notion |
| `make supabase-kpis` | historique KPIs cloud (Supabase) |

## GARDE-FOUS (ne jamais enfreindre)
- **Paper par défaut.** Aucun ordre réel sans `--live --yes` **ET** clés API présentes.
- **Ne jamais passer un broker en live sans avoir fermé les P0-SI-LIVE de ce broker** (cf. `vault/03_TODO.md`).
  État 2026-07-05 : #4 idempotence Bitmart et #5 fills partiels FERMÉS (#293). Aucun P0-SI-LIVE ouvert,
  mais l'activation d'un broker réel reste conditionnée au **RDV paper du 2026-08-06** + décision explicite.
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
- **Dev `localhost:3000`** : après un `make site` (build export), faire `cd apps/web && rm -rf .next && npm run dev`
  (sinon `Cannot find module './682.js'` / `/_document` — le `.next` export n'est pas relisible par `next dev`).
- **`make start` ÉCRASAIT la branche que `make sync` venait de récupérer** (04/09). `start.sh` faisait
  `git reset --hard origin/main` : `make sync` alignait la branche de dev sur ses derniers commits,
  puis `make start` la ramenait sur `main` deux secondes plus tard. Les correctifs livrés ne
  tournaient **jamais**, et rien ne le signalait — on cherchait un bug de cache dans du code qui
  n'était pas chargé. Pire : le Makefile de `main` étant plus ancien, `make sync` disparaissait
  ensuite (« No rule to make target 'sync' »), ce qui rendait la sortie impossible sans les trois
  lignes d'amorçage. `start.sh` suit désormais la branche COURANTE et se contente d'AVERTIR du
  retard sur `main`. **Symptôme à reconnaître : la ligne `✓ <sha> → <autre sha>` de `make start`
  où le second sha n'est pas celui que `make sync` vient d'afficher.**
- **Le cache `.next` resert l'ANCIEN rendu après un `make sync`** (03/09). Symptôme trompeur : le code
  contient le correctif, le navigateur affiche la version d'avant, et **rien ne le signale** — on croit
  lire le résultat de son correctif, on lit celui d'avant. Constaté sur deux correctifs le même jour
  (onglet `/sentiment` remis dans la barre, étiquette macro « série arrêtée » corrigée). `start.sh`
  tamponne désormais le commit du build dans `apps/web/.quant-build-commit` et purge `.next` s'il a
  changé. **Avant de conclure qu'un correctif front ne marche pas, vérifier qu'il est BUILT.**
- **Ne JAMAIS faire `git pull` sur la branche de dev.** Elle est RÉÉCRITE à chaque déploiement
  (`reset --hard origin/main` + `push --force`), donc `pull` la voit divergée, tente une fusion et
  laisse des marqueurs `<<<<<<<` dans les sources — `SyntaxError` sur du code valide à l'origine.
  Utiliser **`make sync`** (`fetch` + `reset --hard`), qui abandonne d'abord tout merge en cours.
  Filet supplémentaire : `git config pull.ff only` fait ÉCHOUER un pull divergé au lieu de fusionner.
- **`make sync` n'existe pas AVANT le premier fetch** (piège d'amorçage, 03/09) : la cible vit dans
  le Makefile de la branche, donc un poste resté en arrière répond `No rule to make target 'sync'`.
  La commande qui sert à récupérer le code n'existe qu'une fois le code récupéré. **Amorçage manuel,
  une seule fois** — le `stash` d'abord, pour mettre de côté un éventuel travail local plutôt que
  de l'écraser :
  ```
  git stash push -u -m "avant-sync" 2>/dev/null
  git fetch origin claude/screening-trading-platform-me9p11
  git checkout -B claude/screening-trading-platform-me9p11 origin/claude/screening-trading-platform-me9p11
  ```
  `checkout -B` crée OU réaligne la branche selon qu'elle existe déjà : une seule forme pour les
  deux cas. Ensuite `make sync` est disponible et ces trois lignes ne resservent jamais.
- **Seuil sur `polyfit`/régression** : TOUJOURS une **tolérance relative** dans la comparaison
  (`x > band + 1e-9*max(1,|band|)`). Un canal **plat** (dispersion ~0) fait dériver la bande sous le
  niveau réel par erreur flottante → fausses cassures à chaque barre → capture du rendement de la barre
  de cassure = **mini look-ahead** (cf. `channel_break`, corrigé `3c1c771`).

## Sécurité (acquis)
CORS API verrouillé sur localhost (`QUANT_CORS_ORIGINS` pour élargir) · webhook protégé
(`QUANT_WEBHOOK_TOKEN` sinon localhost) · secrets en env (`.env.example` documente tout).

## Discipline architecture & données (ajout ops-kit — 02/07)
- **Taille des fichiers** : < 400 lignes/fichier, < 50 lignes/fonction. Un hook PostToolUse le signale ; refactorer immédiatement.
- **Plugins** : nouvelle stratégie/indicateur/facteur/source = 1 fichier auto-enregistré, jamais modifier le cœur.
- **Mandat données-réelles** : toute calibration, seuil ou recommandation vient de la DB/journal RÉELS. Données insuffisantes → dire "UNCALIBRATED", jamais inventer. Synthétique autorisé UNIQUEMENT dans tests/ pour valider la math.
- **Certification** : aucun composant en prod sans passer les gates de `vault/15_CERTIFICATION.md` (skill `/certify`). Un composant non-certifié en prod = finding P0.
- **Sub-agents dispo** : session-auditor, friction-clusterer, quant-critic, leakage-hunter, vault-architect, db-auditor. Les forker pour l'analyse lourde read-only.
