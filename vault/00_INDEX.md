# 🧠 00 — INDEX (tableau de bord)

> Mémoire = source de vérité. **Lire avant toute action, mettre à jour après chaque session.**
> Page d'accueil du cerveau : démarre toujours ici.

## 🚀 Accès rapide (clique un lien)
- 🏛️ [[01_ARCHITECTURE]] — schéma vivant, modules, conventions
- 🧭 [[02_DECISIONS]] — journal des choix (ADR)
- ✅ [[03_TODO]] — backlog priorisé (commence ta session ici)
- 📓 [[04_JOURNAL]] — log daté (lis les 3 dernières entrées)
- 🔌 [[05_DATA_SOURCES]] · 📈 [[06_STRATEGIES]] · 🛡️ [[07_RISK_POLICY]]
- 🗃️ [[08_DATA_MODEL]] · 🔬 [[09_RESEARCH]] · 📊 [[10_BACKTEST_RESULTS]]
- 🎨 [[11_DESIGN_SYSTEM]] · 🧮 [[12_FACTORS]] · 🪞 [[12_MANIFESTE_HONNETETE]] (DSR≈0 assumé = le wedge)

## Mission
Screening & trading systématique multi-actifs (actions, ETF, forex, crypto, commodities, indices),
niveau institutionnel, 100 % OSS. **Paper par défaut.**
Priorités : robustesse > maintenabilité > gestion du risque > recherche d'alpha > produit.

## 🔁 Rituel de session (sans qu'on le redemande)
> Auto-chargé : `CLAUDE.md` (racine du repo) rappelle ce rituel + les garde-fous à **chaque** session
> Claude Code. Skills : `/deploy`, `/audit-secrets`, `/company-note`, `/close-session` (dans `.claude/commands/`).
1. **Avant** : [[00_INDEX]] → [[01_ARCHITECTURE]] (les 2 diagrammes) → [[04_JOURNAL]] (3 dernières) → [[03_TODO]].
2. Reformuler en 3 lignes : où en est le projet, prochaine priorité (situer la tâche dans le schéma).
3. **Pendant** : exécuter par petits incréments testés.
4. **Après (clôture)** : maj [[03_TODO]], entrée datée [[04_JOURNAL]], log [[02_DECISIONS]] si choix
   structurant, maj des diagrammes si l'archi a changé, miroir Notion, push. → skill **`/close-session`**.
   (En auto : le **cron** régénère chaque jour le journal/attribution/post-mortems via `make vault-sync`.)
5. Laisser le projet reprenable par une autre instance (schéma à jour = garantie).

## ✍️ Ce que TU édites vs ce qui s'écrit TOUT SEUL
> Ne modifie jamais un fichier auto-généré : il est écrasé au prochain run. Pour annoter une société,
> crée une note séparée qui pointe vers la sienne (ex. `[[AAPL]]`).

| ✍️ Manuel (toi) | 🤖 Auto-généré — ne pas éditer | Commande |
|---|---|---|
| [[00_INDEX]] · [[01_ARCHITECTURE]] · [[02_DECISIONS]] · [[03_TODO]] · [[04_JOURNAL]] · [[06_STRATEGIES]] · [[07_RISK_POLICY]] · [[09_RESEARCH]] | `Performance_Report.md` | `make analytics` |
| | `04_Companies/` (notes société `#company`) | `make reports` |
| | `04_Companies/_TOP200.md` | `make watchlist` |
| | journal du jour · attribution · post-mortems | `make vault-sync` |

## 💻 Lancer en local
- **Site statique (= en ligne)** → `make site` → http://localhost:8080
- **Terminal dynamique (données live)** → fenêtre 1 `make api` · fenêtre 2 :
  `cd apps/web && rm -rf .next && npm run dev` → http://localhost:3000
  > ⚠️ Le `rm -rf .next` est **obligatoire** après un `make site` (sinon `Cannot find module './682.js'`).

## ⌨️ Raccourcis Obsidian essentiels
| Raccourci | Action |
|---|---|
| `Cmd/Ctrl + O` | aller à une note (quick switcher) |
| `Cmd/Ctrl + Shift + F` | recherche plein texte dans tout le vault |
| `Cmd/Ctrl + clic` | suivre un lien `[[...]]` |
| `[[` | créer un lien vers une note |
| `#` | poser un tag (ex. `#company`, `#decision`) |
| icône graphe (haut-gauche) | **Graph view** — la carte de tes idées |
| `Cmd/Ctrl + P` | palette de commandes |

Plugins cœur à activer (Settings → Core plugins) : Graph view · Backlinks · Outgoing links · Outline · Tag pane · Quick switcher · Search.

## 🌐 En ligne (PWA gratuite)
**https://7noctis7.github.io/Screening-Trading/** — front complet en statique, données réelles,
reconstruit chaque jour ouvré par GitHub Actions. Mac éteint, 0 €. Positions réelles **local-only**.

## 📍 État actuel
**2026-07-02** — **PRÊT POUR CAPITAL RÉEL LIMITÉ** (inchangé). **Journal de trades désormais PERSISTANT**
(`SqliteTradeJournal` → `data/journal.db`, features en JSON, UPSERT idempotent, flag `legacy` requêtable ;
cf. **ADR-0028**) : `LiveTradingEngine` persiste par défaut, features capturées à la décision (contrat
anti-fuite testé), **137 fills historiques importés** (`legacy=1`). P1-1 clos. La calibration
MFE/MAE/expectancy/Kelly attend N>0 sur `legacy=0` (paper live → RDV 2026-08-06). Suite verte : 773 tests.
Bug look-ahead `channel_break` corrigé (canal plat, `3c1c771`) — breakout **reste rejeté**.
**P0 full-review** (fuite univers preset) toujours en attente du re-run Mac.

<details><summary>Historique (2026-06-29)</summary>

**2026-06-29** — **PRÊT POUR CAPITAL RÉEL LIMITÉ** (inchangé). **Cockpit crypto `/crypto` complet** :
cockpit marché (robustesse/cache, peg, halving, altseason, **dérivés funding multi-CEX**, **Score
d'Accumulation 0-100**), **mini-fiche** + items cliquables + glossaire, **trio LIVE** (jauge de
sentiment + graphe Coinbase WebSocket + analyse « Œil de Hasheur ») en **client-direct** (cf.
**ADR-0025**), **RAG vault cité** (`vault-ask`) + **text-to-filter** (`crypto-screen`), **partage/
embed** (M5) + landing froide (M6). Gate : **7/7 négatifs** (F&G contrarian + cassure de canal
ajoutés ; le breakout a passé le placebo mais DSR 0 / PBO 0,88 / sabotage → **rejeté**, cas d'école).
Rebalancement **paper auto** quotidien (`make live-cron-install`). Commandes : `make crypto-cockpit /
crypto-brief / crypto-screen / vault-ask / regime-study / breakout-study`. **RDV 2026-08-06 : revue
courbe paper.**
</details>

<details><summary>Historique (2026-06-25)</summary>

**2026-06-25** — **Audité 3× (66 → 83/100) → PRÊT POUR CAPITAL RÉEL LIMITÉ** (sous sizing défensif +
track record paper). 4 hypothèses d'alpha directionnel testées → **4 négatifs propres** (DSR/placebo/PBO)
→ pivot acté (ADR-0024) : on durcit le risque, pas l'alpha. Livré : overlay d'exposition câblé au preset
(opt-in `QUANT_RISK_OVERLAY=1`), concentration corrélation-aware, source unique de vérité métriques,
survivorship corrigé (seed faillites bancaires), harnais de sensibilité (seuils prouvés robustes).
Commandes : `make risk-check / sensitivity / backtest-pead-smid / funding-study`.
**Rendez-vous 2026-08-06 : revue courbe paper vs backtest** → décision premier euro réel.

</details>

<details><summary>Historique (2026-06-23)</summary>

**2026-06-23** — PWA en ligne + **« Mastermind 100 » terminé** (gratuit) : FinOps LLM local (Ollama),
RAG sémantique (embeddings + code), hot-path vectorisé, snapshot incrémental (mémoïsation), brokers
parallèles, cache OHLCV souverain (HuggingFace), gate contrats OHLCV (CI), miroir Notion, KPIs Supabase,
webhook n8n. Sécurité : gitleaks + CORS + safe_pickle + audit propre. Cron quotidien branché (best-effort).
Commandes : `make brief / vault-search / contracts / hf-pull / notion-sync / supabase-kpis`.
**Sprint Alpha/Calmar fait (8/10)** : sur données réelles, Max DD −14.6 % (Calmar ≈ 5.4 vs 0.17) mais
**DSR≈0 = pas d'edge directionnel** → décision best-practice (ADR-0023) : **preset satellite risk-managed
`QUANT_DD_TARGET=0.25` + cœur QQQ 50 %** ; #7/#9 abandonnés (parcimonie). Le rendement absolu = plus de
QQQ (bêta honnête), pas d'alpha à presser. Prochaine priorité : ménage disque macOS ; data/delisted.csv.

</details>
