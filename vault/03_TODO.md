# 03 — TODO (backlog priorisé)

> P0 = socle indispensable · P1 = cœur de la valeur (screening→trading paper) ·
> P2 = sophistication (ML, front, live). On n'ouvre P1 que quand P0 est vert.

## 🌙 CE SOIR SUR LE MAC — 2026-07-06 (post-audit 3 volets, ~10 min)
> Les 4 gestes que l'agent ne peut pas faire à ta place (token Notion local, proxy git, clics GitHub).
- [ ] **1. Resynchroniser le repo local** (récupère #299 : remédiation audit + constraints) :
  ```bash
  qt && git fetch origin && git reset --hard origin/main
  ```
- [ ] **2. Rattraper le miroir Notion** (2 semaines de retard constatées à l'audit) :
  ```bash
  make notion-sync
  ```
- [ ] **3. Supprimer les 3 branches distantes fusionnées** (l'agent a été bloqué par le proxy, 403) :
  ```bash
  git push origin --delete ops-integration feat/ui-analytics feat/journal-features-snapshot
  ```
- [ ] **4. Runner cloud — secrets GitHub** (clics, pas de terminal) : repo → Settings →
      Secrets and variables → Actions → New : `ALPACA_API_KEY` + `ALPACA_API_SECRET` (compte
      **paper**) + `HF_TOKEN` (fine-grained, limité au dataset `Noctis777/quant-journal`).
      Puis Actions → « Rebalancement paper cloud » → **Run workflow** (test).
- [ ] **5bis. ⚠️ RE-BACKFILL AJUSTÉ (une fois, ~10 min)** — le fix P1-4 (splits) ne corrige
      l'HISTORIQUE qu'après ré-ingestion complète :
  ```bash
  python scripts/ingest_prices.py --since 2015-01-01   # OHLC ajustés splits+dividendes
  make ingest-crypto && make hf-push                    # reconstruit le cache HF en AJUSTÉ
  ```
- [ ] **6. Vintages macro RÉELS (P1-3, ~5 min)** : clé gratuite sur
      fred.stlouisfed.org/docs/api/api_key.html → `echo 'FRED_API_KEY=...' >> .env` puis :
  ```bash
  make ingest-macro    # ALFRED → data/macro.db (révisions datées de LEUR publication)
  ```
- [ ] **7. ⚡ BITMART — vérifier que les trades FONCTIONNENT (micro-test, ARGENT RÉEL)**
      ⚠️ Bitmart n'a pas de paper : tout ordre est réel. Protocole minimal (≈12 $, aller-retour) :
  ```bash
  make bitmart-check            # 1) verrous + connexion + MEMO (obligatoire) en lecture seule
  # 2) micro-test CONSCIENT (achat ~6 $ puis revente — teste le fix coût d'achat du 06/07) :
  .venv/bin/python -c "
  from packages.common.env import load_env; load_env()
  from packages.execution.bitmart_broker import BitmartBroker
  from packages.core.models import Side
  b = BitmartBroker(dry_run=False)
  print('ACHAT :', b.submit_notional('BTC/USDT', Side.LONG, 6.0).status)
  print('VENTE :', b.submit_notional('BTC/USDT', Side.SHORT, 6.0).status)"
  ```
      → attendu : FILLED/SUBMITTED aux 2 sens (le bug d'achat silencieux est corrigé). Si REJECTED :
      lire le log (désormais la CAUSE est affichée) — memo manquant = suspect n° 1.
      **Activation PERMANENTE dans le cron** (QUANT_NO_CRYPTO_LIVE=0 + réviser le routage ADR-0032) :
      NON recommandée avant le RDV 2026-08-06 — c'est une décision explicite à part (garde-fou CLAUDE.md).
- [ ] **5. Vérifier le PREMIER run journalisant du jour** (lundi = cron 16h05 a tourné) :
  ```bash
  tail -30 ~/Library/Logs/quant_live.log   # attendu : « Journal : N ouverture(s)/lot(s) fermé(s) »
  make verify-journal                       # legacy=0 doit enfin être > 0 si des ordres sont partis
  ```
  (Si « ✓ déjà aligné » partout = aucun ordre → journal inchangé, c'est normal et honnête.)

## 🚧 EN COURS — reprise 2026-07-03 (branche `feat/broker-hardening`)
> Journée broker-hardening (BLOC 1→4) démarrée. Base : `origin/main` à jour (#292 mergée = `323e53a`).
> Carry-over local non commité : `config/mobile_universe.csv` (data régénérée, hors périmètre — laisser tel quel).
> **Amendements validés** : 1a `_seen` rejoue le résultat RÉEL (y c. rejet), jamais de FILLED fabriqué ·
> 1b ouverture seule (sortie partielle → P2) + si `filled_qty=None` → NE PAS ouvrir + alerte CRITICAL · 1c OK.

- [x] **BLOC 1a — idempotence Bitmart** — LIVRÉ dans `main` via **#293** (audit 2026-07-05) :
      `_seen` rejoue le résultat RÉEL (y c. rejet, y c. qté partielle), `clientOrderId` passé en
      `params` ccxt (dédup côté exchange), `_remember()` après chaque submit définitif.
      Tests `test_bitmart_idempotency.py` verts.
- [x] **BLOC 1b — fills partiels** — LIVRÉ via **#293** : `live_engine.py` gère `PARTIALLY_FILLED`
      (ouvre à `filled_qty` réel + warning reliquat) ; `filled_qty=None` → position NON ouverte +
      alerte CRITICAL. Tests `test_partial_fills.py` verts.
- [x] **BLOC 1c — alerte de réconciliation branchée** — LIVRÉ via **#293** : `packages/alerts/wiring.py`
      (`default_engine` + `attach_to_bus`), `LiveTradingEngine(bus=…)` → `reconcile(bus=…)`,
      hook dans `run_live.py` (`_setup_alerts`).
- [x] **BLOC 2 — FAIT (2026-07-06)** : `make bitmart-check` (lecture seule) affiche les 3 verrous +
      teste la connexion (equity/positions, zéro ordre). Au passage, **vrai bug corrigé** : achat
      marché spot sans prix → `createMarketBuyOrderRequiresPrice` avalé = REJECTED **silencieux**
      (désormais : prix passé pour le coût + rejet LOGGÉ). Activation = décision post-RDV 06/08.
- [ ] **BLOC 3** — Crypto paper via Alpaca (BTC/USD, ETH/USD), sizing vol-target adapté (vol crypto ≫ actions),
      trades crypto → journal SQLite avec `features_snapshot`.
- [ ] **BLOC 4** — Optimisation Alpaca paper (opérationnel, PAS de tuning stratégie) : cron `cron_live.sh`, limit vs
      market, fractional shares, **chaque run alimente `journal.db`** (accumuler des trades avec features = calibration).
- [~] **BLOC 5** — UI/Analytics institutionnel : branche **SÉPARÉE** `feat/ui-analytics` (ne pas mélanger aux brokers).
      Mode plan **écran par écran** (plan avant code). Cf. brief détaillé du 02/07.
  - [x] **Dashboard principal** (2026-07-04, PR #294, commit `d2d11c1`) : `PerformancePanel` (equity+underwater
        synchronisés, zoom LTTB partagé `syncId`), `DrawdownChart`/`PositionsAlertsTable` nouveaux, `MetricCard`
        delta N−1, `RegimeBanner` tokens outline. Fix bug LTTB (pire DD sous-estimé). Cf. **ADR-0030**. `tsc` vert + contrôle visuel headless.
  - [x] **Écran 2 — /positions « réel vs cible »** (2026-07-05) : fusion positions réelles × cible preset
        (poids par poche de capital), barre d'écart divergente + bande de non-trading 3 %, HHI/N effectif/top 3,
        badge earnings, SortableTable (tri/filtre/CSV), route `/api/positions` expose `preset_allocation` +
        `earnings_risk`. Build statique + tests API verts.
  - [ ] **Écran suivant** (à planifier) : candidats `/screener` ou analyse portefeuille dédiée — plan avant code.
  - [ ] **Dette signalée par le hook (02/07, préexistante)** : `apps/api/main.py` 953 l > 400 + 3 fonctions
        >50 l (`_top_syms`, `_build_company_report_cached`, `_enrich_cross_source`) — même famille que le
        god-object `snapshot.py` (P2). Extraire en modules `apps/api/routes/*` lors du refactor sections.
> Contraintes : `make test` vert entre chaque bloc · commits atomiques · rien qui touche `--live` · garde-fous intacts.

## ☁️ RUNNER PAPER CLOUD (Mac éteint, 0 €) — 2 actions à faire par TOI (5 min)
> Livré 2026-07-05 : `.github/workflows/paper.yml` (lun-ven 14h35 UTC, Alpaca PAPER forcé,
> crypto neutralisée) + `scripts/hf_journal.py` (journal persisté sur dataset HF **PRIVÉ**).
> Idempotent vs le launchd du Mac : le 2ᵉ runner du jour voit des deltas ~0 et n'envoie rien.
- [ ] **Créer les secrets GitHub** (repo → Settings → Secrets and variables → Actions → New) :
      `ALPACA_API_KEY` + `ALPACA_API_SECRET` (les clés du compte **paper**) et, recommandé,
      `HF_TOKEN` (token huggingface.co « write » → persistance du journal, dataset créé PRIVÉ
      automatiquement : `Noctis777/quant-journal`).
- [ ] **Tester une fois** : onglet Actions → « Rebalancement paper cloud » → Run workflow ;
      vérifier dans le log « Terminé : N ordre(s) » puis « journal poussé … (privé) ».
- [ ] (Option) **Choisir le runner principal** : garder les deux est SANS DANGER (idempotent),
      mais le journal du Mac et celui du cloud divergent (chacun journalise SES ordres envoyés).
      Recommandé : cloud = principal → `make live-cron-uninstall` sur le Mac, et pour consulter :
      `make journal-pull && make verify-journal`.

## 🚨 FULL-REVIEW 2026-07-02 — findings (voir `vault/14_FULL_REVIEW.md`)
> Revue complète multi-agents sur `ops-integration`. **P0 = invalide des résultats → avant toute feature.**
### 🔴 P0 (bloqueurs capital réel)
- [x] **P0-1 FUITE — CODE CORRIGÉ** (fix `f78e18f`, 2026-07-02, dans `main`) : les 3 fonctions dashboard +
      `preset_backtest` sélectionnent désormais l'univers par **momentum prix-only** (`_price_universe`),
      jamais par le score `quality` du jour. Aucun appelant ne réactive la fuite (`legacy_quality_universe`
      reste `False` partout). **Verrou de non-régression ajouté** : `tests/backtest/test_dashboard_no_leak.py`
      (2 dicts `quality` opposés → sortie identique ; le mode legacy diverge = le test a du mordant).
  - [x] **Reliquat FERMÉ (2026-07-05, sur le Mac)** : `make vault-sync` a régénéré `Preset_Performance.md` →
        **`alpha_annual` 0.0755 → 0.0445** (la fuite gonflait l'alpha de ~3 pts — preuve empirique de P0-1).
        Lecture honnête : le 4,45 % restant est un **alpha d'attribution** (régression vs QQQ, beta 0.37,
        R² 0.63), **PAS un alpha gaté** (placebo/DSR/PBO/sabotage jamais passés dessus) — DSR≈0 reste le
        claim public. Edge prouvé = réduction du drawdown, pas la direction.
- [x] **P0-2 — FERMÉ (2026-07-05)** : manifeste honnête (« DSR≈0 après correction d'une fuite d'univers le
      02/07 ») + artefact local régénéré post-fix (alpha 4,45 % non gaté, cohérent avec le claim).
- [x] **P0-3 — coûts déduits** : `preset_equity_daily`/`preset_ledger` déduisent le coût de turnover par classe
      (`reb_cost`/`_tc`) à chaque rebalancement → equity NETTE, plus « brute ». (Vérifié dans le code courant.)
- [~] **P0-4 JOURNAL LIVE VIDE** (découvert BLOC 4, 2026-07-04) : le chemin de prod du cron
      (`cron_live.sh → run_live.py`) réconciliait chez le broker sans **jamais** écrire dans `data/journal.db`
      (seul `LiveEngine`, fantôme, journalisait) → **0 trade `legacy=0`** = calibration ML bloquée en paper.
      **Décision d'archi : (b) journal direct via `SqliteTradeJournal`** (validée 2026-07-04 ; (a) unifier sur
      LiveEngine = trop gros/risqué près de `--live`).
      - ✅ **Phase 1 (fait, 2026-07-04)** : `packages/execution/live_journal.py` + refactor `run_live.py`
        (main scindé en helpers ≤50 l) journalise chaque ACHAT envoyé (`legacy=0`). **Features figées à la
        DÉCISION** dans `build_snapshot()` (screener `score`+facteurs, poids cible, régime), transportées via
        le snapshot, **jamais reconstruites** ; **faits de fill** (prix/qté) lus des positions RÉELLES du broker
        (lookup tolérant BTC/USD↔BTCUSD). `id` déterministe/jour → idempotent. 7 tests (`test_live_journal.py`).
        `make verify-journal` passe de `UNCALIBRATED` à ✅ au 1er run réel.
      - [x] **Phase 2 (fait, 2026-07-05)** : round-trip — `packages/execution/live_roundtrip.py`
        (`open_lots`/`close_sells` FIFO, vente partielle = scission de lot id `-Xn` déterministe,
        UPSERT idempotent) + `run_live.py` capture les VENTES envoyées et ferme les lots
        (`exit_ts/exit_price/pnl/pnl_pct/is_win/duration_s` + **MFE/MAE** depuis la série OHLC du
        snapshot). Prix de sortie = FAIT broker (fill du jour via `orders()` → `last_price` →
        prix de position ; introuvable = lot laissé OUVERT, jamais estimé). 6 tests
        (`test_live_roundtrip.py`), suite 811 verts. Débloque expectancy/Kelly au RDV 2026-08-06.
      - [x] **Décision prise (2026-07-05, validée utilisateur)** : `LiveTradingEngine` **RÉTROGRADÉ**
        en moteur de simulation (docstring de statut, exports conservés, zéro churn tests/démos).
        Chemin de prod UNIQUE = `run_live.py`. Cf. **ADR-0031**.
### ⛔ P0-SI-LIVE — bloquants AVANT toute activation d'un broker réel (audit adverse 02/07, cf. `14_FULL_REVIEW.md`)
> Prouvés, sévérité capital/ops. **Ne jamais passer le broker concerné en live tant que son P0-SI-LIVE n'est pas fermé** (garde-fou CLAUDE.md).
- [x] **#4 Idempotence Bitmart — FERMÉ** (via #293, vérifié 2026-07-05) : `clientOrderId` en `params`
      ccxt + court-circuit `_seen` (rejoue le résultat réel, jamais de FILLED fabriqué). Tests verts.
- [x] **#5 Fills partiels — FERMÉ** (via #293, vérifié 2026-07-05) : `PARTIALLY_FILLED` ouvre à
      `filled_qty` réel (reliquat loggé) ; `filled_qty=None` → pas d'ouverture + alerte CRITICAL ;
      alerte de réconciliation branchée (bus → `default_engine`). Tests verts.
> ✅ Plus aucun P0-SI-LIVE ouvert. L'activation d'un broker réel reste conditionnée au RDV paper
> du 2026-08-06 (cf. garde-fou CLAUDE.md : jamais de live sans décision explicite).
### 🟠 P1
- [x] **P1-1** ✅ (2026-07-02, suite) : `SqliteTradeJournal` (`data/journal.db`, JSON features, UPSERT
      idempotent, flag `legacy` requêtable) + `LiveTradingEngine` persiste par défaut + `import_legacy_fills.py` (script one-shot, retiré 05/07)
      (137 fills importés `legacy=1`) + 8 tests (dont contrat anti-fuite). Cf. **ADR-0028**, commits `834338a`→`3c1c771`.
      **Reste** : la calibration MFE/MAE/expectancy/Kelly attend N>0 sur `legacy=0` (paper live → RDV 2026-08-06).
- [x] **P1-2 — FERMÉ côté FMP (2026-07-06)** : `as_of` = `fillingDate` (dépôt public), plus la
      clôture d'exercice (look-ahead). Test dédié. Reste `sec_provider` (filtrer `filed`) → P2.
- [x] **P1-3 — CODE FERMÉ (2026-07-06)** : MacroStore persistant (`data/macro.db`, env
      `QUANT_MACRO_DB`) + `make ingest-macro` (vintages ALFRED réels, `published` = realtime_start).
      Test PIT à travers une réouverture. Reste : lancer l'ingestion sur Mac (CE SOIR 6).
- [x] **P1-4 — CODE FERMÉ (2026-07-06)** : ingestion `auto_adjust=True` + détection de couture
      post-split (`_split_drift` → re-backfill auto du symbole). ⚠️ Historique corrigé seulement
      après le re-backfill complet sur Mac + `make hf-push` (cf. CE SOIR 5bis).
- [ ] **P1-5** : `pbo` **dupliqué** — consolider en 1 (garder `portfolio/pbo.py`, retirer `backtest/validation/pbo.py`).
- [ ] **P1-6** : 9 modules top1pct **orphelins** — câbler ou marquer « en attente » ; enregistrer `vol_target`/`kelly_uncertain` au registre Sizer.
- [x] **P1-7 — FERMÉ (2026-07-05, audit 3 volets)** : `01_ARCHITECTURE.md` réécrit (table d'état
      + Mermaid = 14 packages réels), ADR-0029 dédoublonné (→0032), TODO purgé (469→~300 l),
      `vault-lint` câblé en CI (informatif), orphelins liés, notes `paper_*` créées (09_References).
- [~] **P1-8 — passe 1 FAITE (2026-07-06)** : gates « exécution/infra » ajoutés au protocole +
      5 composants prod évalués sur preuves → **CANDIDATE** (registre daté). Reste la promotion
      CERTIFIED, mécanique après 20 j paper + drills (≈ RDV 2026-08-06).
### 🟢 P2
- [ ] **P2 (audit 02/07)** — **#1 Fuite Platt** (`snapshot.py:670-675`, LOW, non-capital) : fit Platt sur une tranche
      60-80 % **distincte** du test 80-100 % (aujourd'hui `brier_calibrated` est in-sample = optimiste, mais n'atteint
      ni les probas servies ni le sizing). **#3 Doublons DSR/PBO** : supprimer les 2 impl. **mortes** `validation/sharpe_stats.deflated_sr`
      + `validation/pbo.pbo_cscv` (0 importeur hors `test_smoke_all.py`) — étend P1-5.
- [ ] **P2** : câbler `macro_publication_lags.yaml` + `risk_top1pct.yaml` · crypto DB 13 j de retard + délistés ·
      tests `packages/macro` (0) · refactor `snapshot.py` (2526 l) · `overnight`/`ts_momentum` dans `factors.yaml` ·
      corriger `08_DATA_MODEL.md` (schéma flat prod v1).

## 📅 RENDEZ-VOUS — 2026-08-06 : REVUE COURBE PAPER (paper vs backtest)
> Audit 3× passé (score ~83/100, **PRÊT POUR CAPITAL RÉEL LIMITÉ** sous conditions).
> Paper défensif lancé le 2026-06-25 (`QUANT_DD_TARGET=0.15`). On laisse tourner ~6 semaines.
- [ ] **2026-08-06** — comparer la courbe paper réelle au backtest preset (Sharpe/MaxDD/CAGR
      concordent-ils ?). Décision : **premier euro réel limité** OU re-calibrage.
  - sortir la courbe : `make analytics` (QuantStats) + `make ledger-sweep` (journal discret).
  - critère GO : paper cohérent avec le backtest (pas de dérive Sharpe>1pt, MaxDD non dépassé).
  - si concordant → engager un capital réel **limité** + sizing défensif ; sinon → re-calibrer.

## 🗄️ Sessions « CE SOIR SUR LE MAC » de juin — CLÔTURÉES (purge 2026-07-05)
> 9 sections opérationnelles (2026-06-24 → 06-30) purgées : tout est LIVRÉ et mergé
> (PR #287/#288/#289 + suivantes). Les faits sont consignés là où ils doivent vivre :
> verdicts de gate → `12_MANIFESTE_HONNETETE.md` (F&G p=0,905 · cassure canal DSR 0/PBO 0,88…) ·
> récits de session → `04_JOURNAL.md` · reliquats réels repris ci-dessus (RDV 06-08, runner cloud).
> Historique complet : `git log vault/03_TODO.md`.

## 🎯 SPRINT « ALPHA / CALMAR » — à démarrer (2026-06-24)
> Objectif : **Calmar 0.17 → 0.6-0.9** en **divisant le Max DD par 2** + alpha honnête.
> Cible code : `packages/backtest/preset_backtest.py` (cœur de la stratégie de production).
> ✅ déjà fait : réplication idempotente **anti-levier** (`run_live.py`, réconciliation au delta).

### 🔴 P0 — Réduire le Max DD (le plus gros levier sur le Calmar)
- [x] **#6 Frein drawdown (marché)** : suivre DD depuis le pic ; `dd<-10%→gross×0.5`, `dd<-15%→gross×0` (ré-arme à la reprise). `preset_backtest.py` boucle `for t`.
- [x] **#5 Porte de régime sur le gross** : plein risque si `^NDX>MM200 & pente>0` ; 0.6 en distribution ; 0.2 sous MM200. (`packages/regime/` + passer la courbe NDX au backtest.)
- [x] **#3 Covariance Ledoit-Wolf** dans `_cov_annual` (`preset_backtest.py:27`) — utiliser `packages.data.engine.ledoit_wolf_shrinkage` (déjà dispo) au lieu de `np.cov` brut.
- [~] **#9 Rebalancement déclenché par la vol** : DIFFÉRÉ (parcimonie) — les portes #5/#6/#8 dé-risquent déjà à chaque step ; marginal. À n'ajouter QUE si le backtest réel le justifie.

### 🟠 P1 — Booster l'alpha (sans β subi)
- [x] **#1 Anti cash-drag (sans levier, k_dd→1.6)** : `preset_backtest.py:71` `gross=min(1,tgt_vol/pv)` → `clip(tgt_vol/pv,0,GROSS_MAX≈1.5)`, `tgt_vol≈0.15`.
- [x] **#4 Tilt momentum sur ERC** : `w ∝ w_erc × max(0,mom_12m)^γ` (renormalisé) — l'ERC pur étouffe les leaders (NVDA…).
- [~] **#7 Sizing demi-Kelly** : DIFFÉRÉ — conflit avec le sizing ERC+momentum déjà en place ; +1 paramètre = +overfit. À évaluer en A/B vs ERC seulement si besoin.
- [x] **#8 Gate breadth cross-asset** : `gross×clip(%univers>MM200 / 0.5, 0, 1)`.

### 🟢 Anti-overfitting (OBLIGATOIRE — rigueur López de Prado)
- [x] **#2 CRITIQUE — fuite de données (corrigée : univers backtest momentum prix-only)** : `preset_backtest.py:46-48` le tilt qualité utilise le score fondamental **actuel** sur tout l'historique (look-ahead + survivorship). → qualité **point-in-time** (vintages) OU univers **prix-only** (momentum 12-1). *Le 6.9 % d'alpha est probablement surestimé tant que ce n'est pas corrigé.*
- [x] **#10 Gate DSR (robuste/défensif)** sur `make calibrate-preset` : n'accepter des params que si **DSR>0 & PBO<0.5** (purged CV — briques `packages/ml` + `portfolio/psr.py`).

### 🌙 CE SOIR sur le Mac (ce que TOI tu dois faire)
- [ ] **Récupérer le code** : `qt && git pull origin main`.
- [ ] **Backtester les 2 nouveaux signaux d'alpha** (overnight, ts_momentum) sur tes données réelles :
  ```bash
  make backtest-preset          # vérifie que rien n'a régressé
  make calibrate-preset         # loggue + synchronise le DSR dans le ledger/notes (auto)
  # tester un signal isolé via le screener (édite config/screening.yaml -> weights: {overnight: 1}) :
  make screen
  ```
  → reporte le DSR obtenu : un facteur n'est **promu** que si DSR>0.5 ET PBO<0.5 (sinon il reste `hypothese`).
- [ ] **Installer + tester le plugin Obsidian Dataview** : Réglages → Modules complémentaires → désactiver
  le mode restreint → Parcourir → **Dataview** → activer. Ouvrir `vault/08_Alphas/00_Alpha_Dashboard.md`
  (les 7 hypothèses doivent apparaître, triées par DSR). Si vide : vérifier le frontmatter `type: alpha_hypothesis`.
- [ ] **Tester le connecteur prediction-markets** (lecture seule, sans clé, nécessite le réseau) :
  ```bash
  python -c "from packages.data.prediction_markets import fetch_markets; print(fetch_markets()[:3])"
  ```
- [ ] **Lancer un PREMIER event-study sur données réelles** (étape qui décide si on continue le ML/LLM) :
  ```bash
  python - <<'PY'
  from packages.data.sec_insiders import fetch_recent_form4   # ou tes dates d'earnings (PEAD)
  from packages.research.event_study import significance
  # 1) construire la série de rendements d'un ticker (ex. depuis ta YAHOO.db)
  # 2) trouver les indices de barres correspondant aux events (insiders / earnings)
  # 3) significance(returns, event_indices, post=5)  -> {mean_car, t_stat, placebo_p_value, significant}
  PY
  ```
  → **règle d'or** : si `significant=False` (p≥0.05 vs placebo) → on **ne code PAS** le ML/LLM (mirage).
  Si `True` → feu vert pour les étapes 4-6. Reporte-moi le résultat.
- [ ] **(rappel)** le LLM ne sert qu'à l'extraction de texte **as-of** (≤ ts_public), jamais à prédire.

### ⚙️ Opérationnel (rapide, côté utilisateur)
- [x] **Mesuré sur données réelles (2026-06-23)** : `make backtest-preset` → Preset CAGR 80,5 % · Sharpe 2,44 ·
  **MaxDD -9,0 %** vs équipondéré MaxDD -23,3 % (DD ÷ ~2,6). `make calibrate-preset` → 27 combos,
  **Sharpe déflaté ≤ 1 % partout = DSR≈0 CONFIRMÉ** (aucun alpha directionnel robuste).
- [ ] **Adopter le réglage défensif recommandé** : `echo 'QUANT_DD_TARGET=0.15' >> .env`
  (combo le moins overfit : DD-cible 15 % · top-K 20 · bande 3 % · turnover 0,20×).
- [ ] **Reset Alpaca paper + 1 seul `make live-go`** → annule le levier ~1,85× actuel.
- [ ] **Ménage disque macOS** (Data volume ~12 Go libres) : `prediction-market-analysis` 50 Go, `Desktop` 21 Go, `Library` 16 Go.
- [ ] Plugins Obsidian : **Smart Connections** + **Obsidian Git** (si pas encore activés).
- [ ] (Optionnel) Supabase : créer projet + table `daily_kpis` → `make supabase-kpis`.

### ✅ Audit « 5 entités » — feuille de route 5 lots FAITE (PR #242 + #243, 567 tests)
- [x] **Lot 1** chirurgie : indices `^` exclus du screener + retry/backoff broker (`packages/common/retry.py`).
- [x] **Lot 2** ADF + Minimum FFD (`ml/features.py` : `adf_stat`, `min_ffd`).
- [x] **Lot 3** Monte Carlo par séquences de trades (`portfolio/stress.monte_carlo_trades`).
- [x] **Lot 4** calendrier crypto 365 j (`data/audit` conscient de la classe).
- [x] **Lot 5** corrélation conditionnelle + kill-switch intraday (`make kill-check`).

### 🟢 PISTE D'ALPHA ACTIVE (2026-06-24) — PEAD significatif sur AAPL
- [x] **event-study AAPL/earnings SIGNIFICATIF** : CAR +2,0 % / 5 j · t=2,18 · placebo p=0,008 (`make event-study`).
- [ ] **VALIDER en cross-sectionnel** : event-study sur un PANIER (pas 1 ticker) → PEAD généralise-t-il ?
- [ ] **Backtester le signal `pead_signal`** comme stratégie (coûts + DSR>0.5 & PBO<0.5) avant d'y croire.
- [x] **#6 prediction-markets** (connecteur macro/actifs/résultats + page Macro) — FAIT [#249].
- [x] **Obsidian research-infra** (ledger + dashboard Dataview) — FAIT.
- [x] **Insider Form 4 buy/sell via XML** (`parse_form4_xml` + `net_insider_signal`) — FAIT.

### 🔭 Chantiers code restants (non urgents — palier déjà très bon)
- [ ] **Insider event-study par ticker** : `fetch_recent_form4` ne ramène que les dépôts GLOBAUX récents
  → requête EDGAR par CIK/ticker nécessaire pour l'historique d'une société (sinon 0 event).
- [ ] _(legacy)_ Obsidian research-infra — voir ci-dessus, fait.
  (frontmatter statut/dsr) + ledger d'essais `research/hypotheses.jsonl` + dashboard Dataview → boucle idée↔DSR.
- [ ] **#6** Facteur prediction-markets (Kalshi/Polymarket, API publiques gratuites) — vrai wedge data.
- [ ] **#9** GARCH(1,1) au sizing vol-target (module `packages/portfolio/garch.py` déjà présent) — derrière flag + A/B.
- [ ] **Suite #2** : extraction des sections du god-object `snapshot.py` en modules `packages/sections/*` + registre.
- [ ] **Burn-down ruff/mypy** (~3800) par lots → puis passer les gates **bloquants**.

### 📐 Méthode (chaque amélioration)
1. coder dans `preset_backtest.py` derrière un **flag** (comparer avant/après) ;
2. `make backtest-preset` + `make calibrate-preset` → vérifier **Calmar ↑ & MaxDD ↓** ;
3. **walk-forward OOS** (pas d'overfitting) ; 4. test pytest ; 5. PR → merge.
> ✅ **Sprint alpha 8/10** : #3 #5 #6 #1 #4 #2 #8 #10. **Audit « Conseil Suprême » 10/10 livrés** (gate
> publication, repro, lignage, property tests, isolation des fautes, PSR/honnêteté, Six Sigma, garde LLM,
> screener bout-en-bout, CI gate) + **verdict d'attribution honnête** (gaté sur t-stat). DSR≈0 confirmé en réel.

## ✅ Fait
- [x] **Sprint-0 Gouvernance (audit Conseil Suprême, 0 €)** : gate publication anti « site muet »
  (`check_build.py`), `_SNAP_VERSION` auto-hash + `make repro`, lignage/réconciliation
  (`packages/data/lineage.py`), tests de propriété hypothesis, `pip-audit` CI, manifeste honnêteté.
  Reportés : #2 god-object, #9 GARCH, #3 DSR-UI, #5 SPC, #8 validateur LLM, #6 prediction-markets.
- [x] **Design « radical » (robuste, 0 dép)** [PR #229] : aurora CSS (`body::after`), accents OKLCH
  (`@supports`+fallback), typo display (optical-sizing/ligatures/balance), nav desktop groupée (3 menus).
  Écartés (best practice, risque build CI) : WebGL/OGL, `next-view-transitions`, `next/font`.
- [x] **S13** Excellence op (drift PSI, audit trail, télémétrie, backup, tear sheets HTML/PDF)
- [x] **S12** Alertes multi-canal (moteur/sinks/throttle/handlers event-bus)
- [x] **S11** Analyse de portefeuille (relatif/risque/corrélation/attribution/stress/revue) + écrans portefeuille & positions
- [x] **S10** API FastAPI (payloads testés) + front Next.js (tokens+dashboard) + aperçu HTML statique
- [x] **S9** Module ML : triple-barrier, CV purgée/embargo, frac-diff, modèles, gouvernance champion/challenger
- [x] **S8** Exécution paper Alpaca + moteur live (parité backtest↔live) + idempotence + réconciliation
- [x] **S7** Macro & régime POINT-IN-TIME (vintages, délai publication, surprises, cartographie, cycle)
- [x] **S6** Providers réels yfinance/FMP via wrappers (fallback/cache/rate-limit) + DuckDB drop-in (même interface)
- [x] **S5** Feature store GOLD (anti-skew) + walk-forward + deflated Sharpe (anti-surapprentissage)
- [x] **S4** Univers MENSUEL (cadence + scheduler) + Russell 1000/3000 (iShares) + dédoublonnage par symbole
- [x] **S4** Module fondamental (ratios Vernimmen + valo Damodaran/DCF) → facteurs value/quality
- [x] **S3** Univers multi-marchés source-driven (CAC40/SP500/Nasdaq/NYSE/LSE/SBF120/MIB/Nikkei/KOSPI/CSI300/ETF/crypto/forex/commodities/indices) + snapshots datés point-in-time
- [x] **S3** Ranking multi-facteur explicable (momentum/trend/low-vol)
- [x] **S0** Monorepo + `core` (interfaces/models/registry) + `common` (config/log/event bus)
- [x] **S0** Vault initialisé + schéma vivant Mermaid + ADR-0001
- [x] **S0** Configs YAML d'exemple (universe/risk/factors/strategy) + tests d'archi

## P0 — Socle (sans quoi rien ne tient)
- [x] **CI** : **pytest bloquant** + **ruff & mypy informatifs** en GitHub Actions
  (`.github/workflows/ci.yml`), cache pip + concurrency. pre-commit en place (gitleaks/clé/gros fichiers).
  `(reste : ruff/mypy bloquants après burn-down du legacy ~3800)`
- [x] **Storage** : bronze/silver + **GOLD feature store** (SQLite, upsert idempotent, multi-TF, anti-skew) `(reste : DuckDB+Parquet, Alembic, Feast)`
- [x] **DataProvider** : synthetic + **yfinance** + wrappers **fallback/cache/rate-limit** + **FMP fondamental** + backend **DuckDB** pluggable `(reste : Finnhub/Alpaca temps réel)`
- [x] **Qualité DB** : contrats OHLCV (prix>0, cohérence, ts, gaps, fraîcheur) → **pipeline bloquant** `(reste : pandera/GE, alerte branchée)`
- [x] **Indicateurs** (familles, auto-enregistrés) : SMA/EMA/MACD/**régression log-linéaire z**/RSI/ROC/ATR/Bollinger — **tests anti-look-ahead verts** `(reste : ADX, Ichimoku, volume)`
- [x] **Backtest v0** : moteur event-driven maison + coûts réalistes (CostModel) — démo runnable `(reste : wrapper VectorBT recherche)`

## P1 — Cœur de la valeur (screening → paper trading)
- [x] **Macro & régime point-in-time** : MacroStore (vintages ALFRED) + FRED provider + surprises éco + cartographie macro→actifs + classifieur cycle `(reste : FMI/OCDE international, breadth)` + FMI/OCDE, **surprises éco (réalisé vs consensus)**, cartographie macro→actifs, classification cycle + risk-on/off → `RegimeState` quotidien point-in-time
- [x] **Fondamental & valo** : ratios Vernimmen + multiples/**DCF** Damodaran + facteurs **value/quality** sector-neutral `(reste : providers réels FMP/yfinance, DuPont détaillé, point-in-time réel)`
- [x] **Screening** : moteur de filtres YAML + scoring z-score cross-sectional
  (`packages/screening/` : `engine.py` filtres durs op/between/on_missing → survivants notés par
  composite z-score ; `metrics.py` réutilise le registre de facteurs + métriques prix ;
  `config/screening.yaml` ; 12 tests). Réutilise `_zscore` du ranking (DRY).
  **Branché** : section snapshot `screen` + `GET /api/screen` + dump statique + page front `/screener`
  (nav groupe Marché) + `make screen`. Smoke réel : 25 candidats / 929.
- [x] **Ranking multi-facteur** : momentum/trend/low-vol (z-score cross-sectional), pondérations **régime × classe** + applicabilité, top N **explicable** `(reste : value/quality du fondamental)`
- [x] **Stratégies** (plugins) : `ma_crossover` (trend), `rsi_reversion` (mean-rev), stop/target ATR `(reste : breakout, pairs, short, trailing, scaling)`
- [x] **Sizing** : `fixed_fractional`, `vol_target` (cap) `(reste : Kelly bridé, risk-parity)`
- [x] **Risk engine** : règles veto (R:R, max positions, expo/actif) + **kill-switch drawdown** — testé `(reste : expo par classe/corrélé)`
- [ ] **Portefeuille & risque global** : corrélation glissante + clustering, allocation (risk-parity/vol-target), **benchmarks BTC/SP500/Nasdaq/CAC40 + attribution**, métriques (Sharpe/Sortino/Calmar/DD via quantstats), VaR/CVaR, stress test (2008/COVID) + Monte Carlo, **revue experte CFA/FRM/CPA/CAIA** (ancrée sur métriques calculées)
- [x] **Exécution paper** : AlpacaBroker (interface Broker) + **moteur live (parité)** + retries idempotents + **réconciliation** + kill-switch `(reste : CCXT testnet crypto)`
- [x] **Journal de trades** (mémoire + export CSV) + **snapshot features à l'entrée** `(reste : persistance DuckDB + feature store)`
- [x] **Walk-forward + OOS + deflated Sharpe** (maison, stdlib) `(reste : Backtesting.py, Optuna pour l'optim fine)`

## P2 — Sophistication
- [ ] **ML** : triple-barrier + meta-labeling, features (techn.+fonda+macro point-in-time+frac. diff.), **purged & embargoed CV**, XGBoost/LightGBM, MLflow + champion/challenger, drift → re-train
- [ ] **Alertes** multi-canal (Telegram/Discord), hiérarchisées + throttling
- [ ] **Excellence op** : observabilité (logs JSON, dashboard santé), monitoring ML/drift, audit trail rejouable, sauvegardes testées, CI/CD Docker, tear sheets PDF
- [ ] **Front Next.js** : design system + API FastAPI + WebSocket ; écrans dashboard/screener/détail actif/**portefeuille-analyse**/positions/backtest
- [ ] **Live (optionnel, sur feu vert explicite)** : NautilusTrader, capital limité, monitoring renforcé
- [ ] **Boucle d'amélioration** : réentraînement walk-forward, drift, retour features→screening

## Garde-fous permanents (à ne jamais relâcher)
- Paper par défaut · pas de leverage par défaut · kill-switch testé avant tout live
- `.env` jamais commité · permissions exchange minimales (jamais retrait)
- Point-in-time partout · biais (survivorship/look-ahead/lag) traqués · Kelly bridé
