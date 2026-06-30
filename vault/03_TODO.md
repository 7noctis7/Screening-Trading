# 03 — TODO (backlog priorisé)

> P0 = socle indispensable · P1 = cœur de la valeur (screening→trading paper) ·
> P2 = sophistication (ML, front, live). On n'ouvre P1 que quand P0 est vert.

## 📅 RENDEZ-VOUS — 2026-08-06 : REVUE COURBE PAPER (paper vs backtest)
> Audit 3× passé (score ~83/100, **PRÊT POUR CAPITAL RÉEL LIMITÉ** sous conditions).
> Paper défensif lancé le 2026-06-25 (`QUANT_DD_TARGET=0.15`). On laisse tourner ~6 semaines.
- [ ] **2026-08-06** — comparer la courbe paper réelle au backtest preset (Sharpe/MaxDD/CAGR
      concordent-ils ?). Décision : **premier euro réel limité** OU re-calibrage.
  - sortir la courbe : `make analytics` (QuantStats) + `make ledger-sweep` (journal discret).
  - critère GO : paper cohérent avec le backtest (pas de dérive Sharpe>1pt, MaxDD non dépassé).
  - si concordant → engager un capital réel **limité** + sizing défensif ; sinon → re-calibrer.

## ✅ CE SOIR SUR LE MAC — #287 MERGÉ & DÉPLOYÉ (2026-06-29, suite 3)
> PR #287 squash-mergée sur `main` → site reconstruit (~10 min). Trio live + landing/ticker +
> gate 7e négatif + RAG + growth + Obsidian (ADR-0025). À faire, par ordre :
- [ ] **Récupérer tout (code + Obsidian)** — s'aligner exactement sur le déployé :
  ```bash
  qt && git fetch origin && git reset --hard origin/claude/clever-lovelace-ognwya
  ```
- [ ] **Voir EN LIGNE** (après ~10 min) : https://7noctis7.github.io/Screening-Trading/crypto/
      et la landing — recharger en forçant le cache (**Cmd + Shift + R**).
- [ ] **Voir en LOCAL** : `make stop && make start` → localhost:3000 (landing+ticker) ·
      /crypto (jauge + graphe Coinbase WS + Œil de Hasheur) · /accueil (scroll animé + 3D).
- [ ] **Tester les interactions** : clic sur un ticker → fiche TradingView · clic sur un schéma
      du Gate → méthodo · bouton « Partager sur X » · /crypto/?embed=1 (widget).
- [ ] **Rebalancement paper auto** : déjà actif (launchd lun-ven 16h05). Vérifier :
      `cat /tmp/quant_live.log` (ou `make live` pour un aperçu dry-run).
- [ ] **(optionnel)** `make vault-ask Q="…"` · `make crypto-screen Q="cap > 5md top 10"` ·
      `make regime-study` / `make breakout-study` (re-tester au gate).

## 🪙 CE SOIR SUR LE MAC — cockpit crypto LIVE + gate + croissance (2026-06-29, suite 2)
> Tout est sur `claude/clever-lovelace-ognwya` (PR #287, auto-merge dès CI verte → redéploiement).
- [ ] **Récupérer (pour voir l'Obsidian à jour + le code)** : `qt && git pull origin claude/clever-lovelace-ognwya`.
- [ ] **Voir le trio LIVE** : `make stop && make start` → http://localhost:3000/crypto
      (jauge de sentiment + graphe Coinbase WebSocket + analyse « Œil de Hasheur »).
- [ ] **Tester l'embed** : http://localhost:3000/crypto/?embed=1 (widget read-only, nav masquée).
- [ ] **Verdicts de gate déjà obtenus** : F&G contrarian ❌ p=0,905 (6e) · cassure de canal ❌
      DSR 0/PBO 0,88/sabotage (7e). Rien câblé au ML. (Re-run : `make regime-study` / `breakout-study`.)
- [ ] **RAG vault** : `make vault-ask Q="…"` · **screener NL** : `make crypto-screen Q="cap > 5md top 10"`.
- [ ] **Rebalancement paper auto** : déjà activé (`make live-cron-install`, launchd lun-ven 16h05).
- [ ] **Partager** : bouton « Partager sur X / Farcaster » + « Intégrer (iframe) » en haut de /crypto.

## 🪙 CE SOIR SUR LE MAC — cockpit crypto + test régime F&G (2026-06-29)
> Livré : page `/crypto` (cockpit marché, gratuit), note Obsidian déterministe, et un TEST honnête
> du Fear & Greed comme signal contrarian BTC (gate placebo). **Réseau bloqué côté agent** → ces 3
> commandes doivent tourner sur ton Mac (les API crypto y sont joignables).
- [ ] **Récupérer** : `qt && git pull origin main`.
- [ ] **Note de marché crypto → Obsidian** (contexte, indexée par vault-search) :
  ```bash
  make crypto-brief        # → vault/11_Crypto/Cockpit.md (humeur, pouls, narratifs, movers)
  ```
- [ ] **⭐ Verdict du gate — F&G contrarian sur BTC** (LE test ML/régime) :
  ```bash
  make regime-study        # télécharge F&G (2018+) + prix BTC, lance placebo
  ```
  → reporte la **p-value placebo** et le **verdict** (SIGNIFICATIF / BRUIT). Loggé au ledger +
  note `vault/10_Backtests/Regime_FearGreed.md`.
  - **si BRUIT** (attendu, prior bas) → 6ᵉ négatif propre, **rien câblé au ML**. Ajoute-le au manifeste.
  - **si SIGNIFICATIF** → candidat **overlay de régime** (pas alpha) : validation DSR/PBO ensuite,
    puis branchement `FNG` dans `real_macro_store` (plomberie `FeatureBuilder`/`MacroStore.as_of`
    déjà prête, point-in-time anti-fuite).
- [ ] **(option)** voir le cockpit en ligne : `cd apps/web && npm run dev` → http://localhost:3000/crypto

## 🪙 CE SOIR SUR LE MAC — on-chain crypto (multi-sources gratuites, 2026-06-29)
> Livré : fondamentaux on-chain (CoinGecko + DefiLlama, sans clé) + étude alt-data TVL/MCap.
- [ ] **Récupérer** : `qt && git pull origin main`.
- [ ] **Table fondamentaux on-chain** des 8 (turnover · float · TVL · TVL/MCap · DD-ATH · momentum) :
  ```bash
  make crypto-onchain
  ```
  → repère : **float bas** = overhang d'unlocks (ONDO/RENDER/HYPE) ; **TVL/MCap haut** = cap adossée.
- [ ] **Tester l'edge on-chain** (TVL/MCap → rendements, via le gate placebo) :
  ```bash
  make onchain-study
  ```
  → reporte la **p-value placebo**. ⚠️ Attendu : ❌ non significatif (échantillon mince) — c'est
  une info honnête, pas un échec. Loggé au ledger automatiquement.
- [ ] **(option)** widget on-chain sur la page crypto du dashboard = **PR2 (A)**, en cours côté repo.

## 🎨 CE SOIR SUR LE MAC — tester la NOUVELLE UI (landing 3D + polish, 2026-06-25)
> Livré : landing cinématique (R3F/Three.js + Lenis, route isolée `/landing`) + polish dashboard (CSS).
- [ ] **Récupérer + installer les nouvelles deps front** (three, fiber, lenis) :
  ```bash
  qt && git pull origin main
  cd apps/web && rm -rf .next && npm install && npm run dev
  ```
- [ ] **Voir la landing cinématique** : http://localhost:3000/landing
  → bouge la souris dans le hero (✦ spotlight + particules 3D réactives) ; scroll (inertiel Lenis,
  dolly caméra). Vérifie le 60fps + le rendu mobile (DevTools responsive).
- [ ] **Voir le dashboard poli** : http://localhost:3000/ → survole les cartes (arête « verre » + lift).
- [ ] **Vérifier le build statique** (comme la CI Pages) avant de te fier au déploiement :
  ```bash
  cd apps/web && STATIC_EXPORT=1 npm run build   # doit finir « 23/23 pages », /landing OK
  ```
- [ ] **(option) faire de la landing la page d'entrée publique** : si tu veux que `7noctis7.github.io`
  ouvre sur la landing plutôt que le dashboard, dis-le-moi → je câble une redirection/rootswap propre.
- [ ] **Reporter** : fluidité du 3D sur ton Mac (et mobile si testé) → si ça rame, je baisse le
  nombre de particules / ajoute un toggle « perf ».

## 🌙 CE SOIR SUR LE MAC — tester le SABOTAGE + paper-watch (2026-06-25)
> Nouvelles fonctionnalités mergées : gate de sabotage adverse (#268) + watchdog paper (#267).
> But : voir le 4e étage du gate (placebo → DSR/PBO → **sabotage**) tourner sur tes données réelles.
- [ ] **Récupérer** : `qt && git pull origin main`.
- [ ] **Backtester le PEAD AVEC le sabotage** (la nouvelle ligne s'affiche automatiquement) :
  ```bash
  make backtest-pead-smid
  ```
  → lis la ligne **« Sabotage (coût×3 + bruit + latence) : Sharpe X→Y (rétention Z) → ✅/❌ »**.
  Reporte-moi `rétention` et si l'edge survit. (Rappel : le PEAD est déjà REJETÉ au DSR/PBO ;
  le sabotage confirme qu'il ne faut pas le trader.)
- [ ] **Stresser plus fort** (voir où l'edge casse — règle « zéro confiance ») :
  ```bash
  # coût ×5 + latence 2 j via un petit probe Python sur la série du backtest
  .venv/bin/python -c "from packages.research.adversarial import sabotage_verdict; \
from scripts.backtest_pead_smid import _load, _SMID; \
from packages.strategies.pead_portfolio import pead_daily_returns; \
d,e=_load([t for t in _SMID.split(',')]); _,r=pead_daily_returns(d,e,hold=21,cost_bps=10); \
print(sabotage_verdict(r, extra_cost_bps=50, latency=2, noise_mult=1.0))"
  ```
  → si même un (futur) edge survit à ça, il est vraiment robuste.
- [ ] **Tester le watchdog paper** : `make paper-watch`
  → dira « trop tôt » (<20 j) ; à brancher au cron : `0 23 * * 1-5 cd <repo> && make paper-watch`.
- [ ] **Linter le vault** (intégrité mémoire) : `make vault-lint`
  → liens morts / orphelins = avertissements ; `make vault-lint ARGS=--strict` = gate dur.
  Action : créer les notes `paper_*` manquantes OU retirer les `[[…]]` aspirationnels de
  `08_Alphas/`, et lier les 4 orphelins (PEAD_smid, low_vol, overnight, ts_momentum).
- [ ] **(rappel) confirmer le gate à 4 étages** sur un futur signal : placebo<0.05 ∧ DSR>0.5 ∧
      PBO<0.5 ∧ **survit au sabotage** → sinon il ne passe pas en prod.

## 🌙 EN RENTRANT SUR LE MAC (post-audit comité, 2026-06-25)
> Suite à l'audit contradictoire (score ~66→~78/100, verdict **PRÊT POUR PAPER**). Le seul
> reliquat avant « capital réel limité » est **opérationnel** (élargir les délistés), pas du code.

- [ ] **Récupérer le code** : `qt && git pull origin main`.
- [ ] **🔴 CRITIQUE — élargir le survivorship** (le seul vrai bloqueur capital réel) :
  ```bash
  make ingest-delisted                 # détecte les titres délistés sur ta base COMPLÈTE
  python -c "from packages.data.survivorship import survivorship_audit, load_delisted; \
  print(survivorship_audit(['AAPL'], load_delisted()))"   # vise undersampled=False (coverage ≥5%)
  ```
  → si `undersampled: true` persiste, relance l'ingest sur un historique plus long / plus large.
- [ ] **Éprouver les seuils (anti sur-optim, audit #4)** : `make sensitivity`
  → note tout filtre `⚠ FRAGILE` (Jaccard < 0.7) ou gate régime `⚠ sensible` et reporte-moi.
- [ ] **Overlay de risque (edge prouvé)** : `make risk-check`
  → note l'exposition recommandée du jour (drawdown taper × vol prévue).
- [ ] **Activer le gate audit data en strict (optionnel, plus sévère)** :
  `echo 'QUANT_AUDIT=strict' >> .env` puis `make audit ARGS=--strict` (refuse de servir des prix
  à anomalie critique). Par défaut c'est déjà `warn` (audite + joint le rapport, sans bloquer).
- [ ] **Rafraîchir les métriques de référence** (source unique de vérité = `perf_summary`) :
  `make backtest-preset` → vérifie CAGR/Sharpe/MaxDD cohérents avec le manifeste (claim non sourcé
  retiré). `make calibrate-preset` resynchronise le DSR au ledger.
- [ ] **(rappel défensif)** `echo 'QUANT_DD_TARGET=0.15' >> .env` + 1 seul `make live-go` (annule le levier).

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
