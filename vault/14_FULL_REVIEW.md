# 14 — FULL REVIEW (revue complète multi-agents)

> Généré par le skill `/full-review` le **2026-07-02** sur la branche `ops-integration`
> (commit `627a0e2` : ops-kit + top1pct-pack + certification-kit). Read-only jusqu'à Phase 6.
> Chaque finding cite `fichier:ligne` ou une requête réelle. Rien n'est inventé.

## Résumé exécutif (10 lignes max)
1. **1 P0 dur** : trois fonctions du preset (`preset_equity_daily`, `preset_trade_log`, `preset_ledger`)
   sélectionnent l'univers avec le score **qualité du jour** sur tout l'historique 2015+ → **look-ahead +
   survivorship**. Ces courbes alimentent le **dashboard live** (`snapshot.py:2081`).
2. Le correctif `legacy_quality_universe=False` n'a été appliqué qu'à `preset_backtest()`, jamais aux 3 sœurs.
3. Conséquence : le **manifeste d'honnêteté** affirme « alpha 6,9 % détecté et corrigé » alors que le dashboard
   affiche toujours `alpha_annual 6,79 %` issu du chemin fuité (`Preset_Performance.md:24`). Claim **faux**.
4. **Mandat données-réelles NON satisfaisable** : le journal réel = 100 fills Alpaca bruts, **0/100** avec
   `features_snapshot`, **0/100** avec stratégie, aucun PnL → MFE/MAE, expectancy, Kelly = **UNCALIBRATED**.
5. Le journal est **en mémoire uniquement** (aucune persistance disque) ; MacroStore aussi (`:memory:`).
6. **top1pct-pack** : 11 modules livrés, **9 orphelins** (non câblés) ; `pbo` **dupliqué** (2 implémentations
   divergentes) ; `vol_target` nouveau non enregistré dans le registre Sizer.
7. `core` est **propre** (zéro dépendance cross-package), plugin pattern respecté, **0 secret** en dur.
8. Dérive vault sévère : table « État d'implémentation » fausse (ml/alerts/reporting/apps marqués ⬜ alors
   que livrés), journal en retard de 3 commits, **ADR-0026 manquant** pour l'ops-kit.
9. `adj_close` **99,7 % NULL** (1 992 686/1 998 545) → prix non ajustés des splits ⇒ momentum contaminé.
10. **Verdict** : la conclusion honnête « DSR≈0, pas d'alpha directionnel » **survit** ; le seul edge robuste
    reste la **réduction relative de drawdown ~2,6×** (même univers). Mais les chiffres **absolus** affichés
    sont des artefacts de fuite → **NE PAS engager de capital réel avant correction du P0**.

## Scores de santé (/10)
| Dimension | Score | Justification |
|---|---|---|
| **Architecture** | 6/10 | `core` dependency-free ✓, plugin registry ✓, 0 secret ✓. Mais 7 fichiers >400 l (dont `snapshot.py` **2526 l** god-object), 9 modules top1pct orphelins, `pbo` dupliqué. |
| **Données (réel)** | 3/10 | Journal 0/100 features + non persistant, MacroStore `:memory:`, `adj_close` 99,7 % NULL, medallion aspirationnel, crypto 13 j de retard. Dupes = 0 ✓, gaps equity = jours fériés ✓. |
| **Discipline quant** | 4/10 | Gate 4 étages rigoureux ✓, DSR≈0 assumé ✓. Mais **dashboard fuité** (P0), claim manifeste faux, `preset_equity_daily` **brut sans coûts**, pas d'OOS sur les chiffres headline, trial-count par-étude (pas global). |
| **Sync vault↔code** | 3/10 | Table état fausse (4 pkgs livrés marqués ⬜), diagramme Mermaid rate ~10 packages, journal en retard, ADR-0026 absent, 2 configs orphelines. |

---

## Phase 1 — Fuite de données (leakage-hunter)
| fichier:ligne | motif | verdict |
|---|---|---|
| `packages/backtest/preset_backtest.py:276-277` | `preset_equity_daily` : univers = qualité du jour sur tout l'historique | **LEAK P0** (alimente dashboard) |
| `packages/backtest/preset_backtest.py:372-373` | `preset_trade_log` : idem | **LEAK P0** |
| `packages/backtest/preset_backtest.py:445-446` | `preset_ledger` : idem → `snapshot.py:2081` (P&L dashboard) | **LEAK P0** |
| `packages/backtest/preset_backtest.py:323` | `preset_equity_daily` : `r_d=(w*ret).sum()` **sans coûts** (equity brute) | **P1** |
| `packages/fundamentals/fmp_provider.py:35` | `as_of = date` (fin de période, pas date de dépôt) ; `as_of` ignoré | **P1 dormant** |
| `packages/fundamentals/sec_provider.py:228-255` | `as_of` accepté mais **totalement ignoré** ; tri par `end` pas `filed` | **P1 dormant** |
| `config/macro_publication_lags.yaml` | lags corrects mais **aucun code ne les lit** | **P2** |
| MacroStore / `preset_backtest.py:35` (ledoit_wolf) / ml (PurgedKFold) / labeling triple-barrier | fenêtres trailing, purge/embargo OK | **SAFE (17 checks)** |

**Modules top1pct** : tous SAFE (fonctions math stateless, fenêtres `.tail()` passées uniquement).

## Phase 2 — Architecture du dépôt
- **Fichiers >400 lignes** : `apps/api/snapshot.py` **2526** · `packages/reporting/company_report_render.py` **1318**
  · `apps/web/preview/build_interactive.py` **1152** · `apps/api/main.py` **951** · `preset_backtest.py` **614**
  · `company_report.py` **495** · `reporting/obsidian.py` **485**. → refactor (snapshot.py = P2 connu, god-object).
- **`packages/core` dependency-free** : ✓ confirmé (aucun `from packages.*` hors `core`).
- **Plugin pattern** : ✓ registres présents (`risk_rules`, `factor_calcs`, sizing registry, strategies).
- **Secrets commités** : ✓ **aucun** littéral détecté (`grep` api_key/secret/token/password sur packages/apps/config/scripts).
- **Couverture tests par package (0 test)** : `packages/macro` **0** · `events` 1 · `mcp_tradingview` 1 · `testing` 1 · `llm` 2.
- **Seuils en dur** : `overnight`/`ts_momentum` enregistrés (`ranking/factors.py:86,108`) mais absents de `config/factors.yaml` ; stratégies sans YAML dans `config/strategies/` (seul `ma_crossover.yaml` existe).

## Phase 3 — Qualité quant (quant-critic)
- **Verdict global** : **FAIL** (chiffres dashboard) / PASS avec réserve (claim DD relatif).
- `vault/Preset_Performance.md:8-24` (Sharpe 0,9934 / alpha 6,79 % / MaxDD −26,46 %) → **DISTRUST / NEEDS-RERUN**
  (issu de `preset_ledger` fuité via `snapshot.py:2081`).
- `make backtest-preset` (CAGR 80,5 % / Sharpe 2,44 / MaxDD −9,0 %) → **DISTRUST absolu** (seed survivor-biaisé,
  bench EW CAGR 180 % = tell) / **TRUST réserve** sur le ratio DD −9,0 % vs −23,3 % (même univers, ~2,6×).
- Coûts : modélisés par classe (`costs.py:83-95`) **sauf** `preset_equity_daily` (brut). `market_impact_bps`/
  `stochastic_slippage_bps` existent (`costs.py:104-123`) mais **0 appelant** → pas de capacité/impact.
- Trial-count DSR/PBO : **par-étude** (27/64 combos), pas de compteur global au ledger (conservateur → conclusion tient).
- **Deflated-Sharpe** : Sharpe brut ~0,3-0,5 hors fuite ; après déflation ~30-60 configs → **DSR≈0 confirmé**.

## Phase 4 — Prêt à intégrer ? (top1pct-pack)
| Module | Point d'insertion | État | Note |
|---|---|---|---|
| `convex_drawdown_scaler` | RiskEngine / boucle DD `preset_backtest` | **READY** (orphelin) | insertion prête, non câblé |
| `vol_target` (sizing) | Sizer Protocol `interfaces.py:83` + sizing/ | **NEEDS-PREREQ** | fonction nue, **non enregistrée** au registre Sizer ; doublonne `construction.py::vol_target_from_drawdown` |
| `kelly_uncertain` | Sizer Protocol + sizing/ | **READY** (orphelin) | Kelly bridé — brancher via registre, A/B |
| `rebalance_bands` | `portfolio/construction.py` | **READY** (orphelin) | |
| `expectancy_filter` | `screening/engine.py` | **BLOCKED** | requiert win-rates réels par stratégie → **UNCALIBRATED (N=0)** |
| `atr_stops` | stratégies (stop/target ATR existants) | **READY** (orphelin) | |
| `sharpe_stats` | `backtest/validation/` | **READY** (orphelin) | |
| `pbo` (validation) | `backtest/validation/` | **NEEDS-PREREQ** | **DUPLIQUE** `portfolio/pbo.py` (câblé, divergent) → consolider en 1 |
| `mfe_mae` | `TradeRecord.mfe/mae` (`models.py:251-252`) ✓ | **BLOCKED** | schéma OK mais journal **0/100** peuplé → UNCALIBRATED |
| `cross_provider` | `data/quality/` | **READY** (orphelin) | gate qualité multi-source, non câblé |
| `correlation_shock` | RiskEngine | **READY** (orphelin) | |

**Synthèse Phase 4** : le pack est **shelf-ware** — code livré, points d'insertion présents, mais **9/11 orphelins**.
2 nécessitent des prérequis (pbo dédupliqué, vol_target enregistré) ; 2 sont **BLOCKED sur données réelles**
(expectancy, mfe_mae) → conformes au mandat s'ils sont marqués **UNCALIBRATED** et non câblés.

---

## Liste de correctifs priorisée
> **P0 = invalide des résultats → passe avant TOUTE nouvelle feature.**

### 🔴 P0
- **P0-1** — Porter `legacy_quality_universe=False` (univers momentum prix-only) dans `preset_equity_daily`,
  `preset_trade_log`, `preset_ledger` (`preset_backtest.py:276-277, 372-373, 445-446`). Régénérer le dashboard
  + `Preset_Performance.md`. *C'est LE bloqueur capital réel.*
- **P0-2** — Corriger l'incohérence du **manifeste** : soit après P0-1 régénérer les chiffres, soit retirer le
  claim « alpha 6,9 % corrigé » (`12_MANIFESTE_HONNETETE.md:18`) tant que `alpha_annual 6,79 %` fuité est affiché.
- **P0-3** — `preset_equity_daily` : déduire les coûts (`preset_backtest.py:323`) — courbe dashboard actuellement brute.

### 🟠 P1
- **P1-1** — Journal réel : **persistance disque** (`data/journal.db`) + peupler `features_snapshot` à chaque fill
  (`execution/live_engine.py`) + ajouter `features_snapshot` à `journal.py::to_csv`. Débloque toutes les calibrations.
- **P1-2** — Providers fondamentaux PIT : `fmp_provider.py:35` utiliser `fillingDate`/`acceptedDate` ;
  `sec_provider.py` filtrer par `filed` (pas `end`). API `as_of` actuellement **trompeuse** (ignorée).
- **P1-3** — MacroStore : persister sur disque (`data/macro.db`) + vintages ALFRED réels (sinon look-ahead ML latent).
- **P1-4** — `adj_close` 99,7 % NULL : ré-ingérer `auto_adjust=True` (splits non ajustés → momentum contaminé).
- **P1-5** — Dédupliquer `pbo` : garder une seule implémentation (`portfolio/pbo.py` est la câblée).
- **P1-6** — Câbler (ou marquer explicitement « en attente ») les 9 modules top1pct orphelins ; enregistrer
  `vol_target`/`kelly_uncertain` au registre Sizer.
- **P1-7** — Dérive vault : corriger la table « État d'implémentation » (`01_ARCHITECTURE.md:100-105`), mettre à jour
  le diagramme Mermaid (~10 packages manquants), écrire l'entrée journal 2026-07-02, créer **ADR-0026** (ops-kit).

### 🟢 P2
- **P2-1** — Câbler `config/macro_publication_lags.yaml` dans l'ingestion FRED, ou le marquer « doc-only ».
- **P2-2** — `config/risk_top1pct.yaml` : brancher via `common/config.py` (sinon config orpheline).
- **P2-3** — Crypto DB 13 j de retard + 9 symboles délistés/renommés (MATIC→POL, FTM→S…) → `make hf-pull` + `delisted.csv`.
- **P2-4** — Tests pour `packages/macro` (0 test), `events`, `mcp_tradingview`, `testing`, `llm`.
- **P2-5** — Refactor `snapshot.py` (2526 l) en sections (`packages/sections/*` + registre) — god-object connu.
- **P2-6** — Documenter `overnight`/`ts_momentum` dans `config/factors.yaml` (section recherche, status hypothesis).
- **P2-7** — Bronze/silver/gold + `ingested_at` : corriger `08_DATA_MODEL.md` (schéma flat `prices(symbol,date)` = prod v1).

## Registre de certification
`vault/15_CERTIFICATION.md` existe (protocole DRAFT→CANDIDATE→CERTIFIED→REVOKED) mais **registre vide** : aucun
composant certifié. Par la règle CLAUDE.md « aucun composant en prod sans gate certif », le **preset en prod +
dashboard = composant non-certifié servant des chiffres fuités = finding P0** (recouvre P0-1).

---

# Audit adverse — 02/07 (soir) — scoring institutionnel sévère

> Second passage, barème **recalibré sur le scope ASSUMÉ** (daily/EOD, paper, 0 € infra, edge défensif
> DSR≈0 = constat honnête, pas un défaut). Les axes HFT/tick-data/ML-lourd/infra-orchestrée sont **(B) hors-scope,
> sortis du calcul**. Sévérité MAXIMALE sur l'in-scope (PIT, look-ahead, coûts, gates, qualité data, repro, secrets,
> honnêteté des chiffres). **Chaque finding = preuve exécutée `fichier:ligne` ou requête ; un ⚠️ non prouvé est retiré.**
> Cartographie complète des 6 axes par 6 agents d'inventaire (transcripts session 02/07).

## Verdicts des 6 findings capital/vérité (prouvés ou retirés)

| # | Sujet | Verdict | Sévérité | Capital ? | Preuve |
|---|---|---|---|---|---|
| 4 | Idempotence absente Bitmart | **CONFIRMÉ** | HIGH (si live-crypto) | **Oui** | `bitmart_broker.py:99` `create_order` sans `clientOrderId` ; `retry.py:28` retente sur REJECTED (`:103`) → retry redouble l'ordre marché réel. Gaté par `dry_run=True` + `QUANT_NO_CRYPTO_LIVE=1`. |
| 5 | Fills partiels non gérés | **CONFIRMÉ** | MEDIUM | Oui (divergence) | `live_engine.py:111` n'ouvre que sur `"filled"` strict ; `PARTIALLY_FILLED` mappé (`:16`) mais ignoré → position broker non trackée, ni stop ni target ; `reconcile.py:35` détecte mais alerte non branchée. |
| 1 | Fuite calibration Platt | Confirmé → **RÉTROGRADÉ** | LOW | **Non** | `snapshot.py:670` `PlattCalibrator().fit(p_te, y[cut:])` puis Brier sur le **même** `y[cut:]` (`:675`) = métrique in-sample optimiste. MAIS `cal`/`p_cal` meurent dans le dict reporting : les probas servies (`:657` `probs`) sont **brutes**, le sizing est VolTarget/Kelly, jamais la proba ML. Prémisse « contamine le sizing » **réfutée**. |
| 3 | Doublons DSR ×3 / `pbo_cscv` ×2 | **RECLASSÉ** dette | LOW/P2 | Non | Call-sites tracés : `portfolio/psr` = canonique + prod (`snapshot.py:1860`) ; `backtest/statistics` = 1 appelant (`walkforward.py:91`) ; `validation/sharpe_stats.deflated_sr` + `validation/pbo.pbo_cscv` = **0 importeur hors `test_smoke_all.py`** = code mort. Chaque call-site bien lié → pas de risque « mauvaise impl ». |
| 2 | `calibrate.py:34` signature DSR | **RETIRÉ** | — | — | Exécuté : `import` lie à `psr.py` `(sharpe,n,n_trials)` ; `deflated_sharpe_ratio(0.12,500,n_trials=27)` = `0.0`, aucun crash. Confusion agent avec `statistics.py`. |
| 6 | `.env` à la racine | **RETIRÉ (PASS)** | — | — | `git check-ignore .env` = ignoré ; `git log --all -- .env` = vide ; `diff-filter=A` historique complet = jamais ajouté. Aucune fuite. |

**Constat de tri** : les 2 seuls risques capital survivants (#4, #5) sont dans **l'exécution** — l'axe le plus (B)
du scope. Le cœur data/backtest/risque tient ; la périphérie live-broker a les trous. **Short** = scope v1 assumé
(`sim_broker.py:43`), **non documenté** dans le vault → dette de doc (cf. **ADR-0029**), pas une régression.

## Notes par axe (/20, barème recalibré)

- **Axe 1 — Data & Pipeline : 15/20.** PIT multi-couches prouvé (`pit_guard.py`, `macro_store` vintages ALFRED,
  `universe_repo` snapshots datés), survivorship (délistés+audit), validation OHLCV double bloquante, gate contrats
  CI, base réelle 1,99 M lignes/741 sym/2015→2026. Docké : retry/backoff **non câblé** aux scripts d'ingest (skip
  sur échec), `adj_close` NULL (P1-4, non re-vérifié ce soir), pas de calendrier de cotation réel.
- **Axe 2 — ML & Feature Eng : 13/20.** `PurgedKFold`+embargo réellement en prod (`snapshot.py:627`), triple-barrier,
  méta-labeling, conformal, drift PSI. Docké : frac-diff/ADF codés mais **non appliqués en prod** (stationnarité des
  features de niveau non garantie), Platt in-sample (#1), pas de CPCV pour l'entraînement, `FeatureBuilder` PIT hors pipeline.
- **Axe 3 — Exécution : 10/20.** Parité backtest↔paper↔live, idempotence Alpaca/Sim, réconciliation, kill-switch armé
  à chaque pas. Docké dur : **#4 Bitmart** + **#5 fills partiels** (2 trous capital/ops confirmés), `cancel()` no-op.
  (async/WS/TWAP/routing/short = (B) exclus.)
- **Axe 4 — Portefeuille : 15/20.** HRP/min-var/ERC/IVP/Black-Litterman tous câblés, **Ledoit-Wolf par défaut**,
  concentration HHI + corrélation-aware, vol-target + Kelly bridé. Docké : sizers `kelly_capped`/`risk_parity` déclarés
  mais **non enregistrés** (config morte), pas de coût dans l'objectif d'optim (bandes ex-ante à la place), HRP simplifié.
- **Axe 5 — Risque & Backtest : 15/20.** Coûts réalistes appliqués (turnover, `broker_fee` réglementaire), métriques
  complètes (Sharpe/Sortino/MDD/Calmar/VaR/CVaR/Cornish-Fisher/EVT/fragilité Taleb/Kupiec-Christoffersen), kill-switch +
  **`DrawdownScaler` convexe** (borne max-DD par construction), stress MC/bootstrap, univers anti-fuite `_price_universe`.
  Docké : VaR/CVaR/EVT **non branchés** au kill-switch (drawdown seul), **pas de replay historique 2008/2020** sur
  séries réelles (données 2015+ disponibles → gap réel), anti-survivorship heuristique (univers figé début fenêtre),
  et rappel : une fuite d'univers avait atteint le dashboard (P0-1, corrigée + artefacts régénérés le 02/07).
- **Axe 6 — MLOps / Prod-readiness : 11/20.** CI pytest bloquant, gates de déploiement, gitleaks CI+pre-commit, logging
  JSON, andon `safe_section`, audit-trail append-only, drift PSI exposé. Docké dur : **alerting Telegram/Discord codé mais
  JAMAIS branché en prod** (démos seulement), **aucune détection de déconnexion API/reconnexion**, réentraînement cron
  aveugle (drift ne déclenche rien), lint/mypy/pip-audit non bloquants, `/health` trivial. (Prometheus/K8s/compose = (B).)

## Moyenne générale — double pondération (transparence)

| Axe | Note /20 | Poids égal | Poids-risque |
|---|---|---|---|
| Data | 15 | 1/6 | 25 |
| ML | 13 | 1/6 | 12 |
| Exécution | 10 | 1/6 | 6 |
| Portefeuille | 15 | 1/6 | 12 |
| Risque/Backtest | 15 | 1/6 | 25 |
| Prod-readiness | 11 | 1/6 | 20 |

- **Égal-pondéré (académique pur)** : (15+13+10+15+15+11)/6 = **13,2 / 20**.
- **Pondéré-risque** (Data25·Risque25·Prod20·ML12·Portef12·Exec6) : (375+156+60+180+375+220)/100 = **13,7 / 20**.

Le pondéré-risque est **plus haut** : le seul axe faible (Exécution 10) est sous-pondéré à 6, et les deux socles forts
(Data, Risque) portés à 25 — cohérent avec le fait que les trous survivants sont périphériques au scope.

## Synthèse (3 phrases)
1. **Viabilité live actuelle** : non viable pour du capital réel en l'état — cœur daily/backtest/risque de niveau
   institutionnel, mais la périphérie live-broker porte 2 trous capital/ops confirmés (#4, #5) et le filet
   opérationnel (alerting) est codé mais non branché ; **paper-ready, pas live-ready**.
2. **Plus gros risque de ruine** : non pas un blow-up unique mais une **combinaison** — un retry Bitmart peut redoubler
   un ordre crypto réel (#4) pendant qu'**aucune alerte branchée** ne capte une déconnexion / un kill-switch / une
   divergence de réconciliation → un incident live pourrait courir **non observé**.
3. **Potentiel si 100 % des correctifs appliqués** : #4/#5 fermés, VaR branchée au de-risking, alerting live, Platt/
   stationnarité durcis → le système atteint un vrai niveau institutionnel pour un mandat **daily/défensif à 0 €** ;
   mais son plafond reste défini par sa prémisse honnête (edge = gestion du risque, DSR≈0) : « 20/20 » = perfection
   **opérationnelle**, pas un oracle d'alpha.
