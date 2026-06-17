# Carte des modules — Quant Terminal

Catalogue complet du cœur métier (`packages/`) et des produits (`apps/`). Mise à jour : 2026-06-17.
**276 tests** · 11 fenêtres front (Next.js) + terminal autonome à parité · données réelles ou synthétiques.

> Convention : « ajouter un fichier, jamais toucher au cœur ». Tout module ci-dessous est **pur /
> testable hors-ligne**, avec repli gracieux quand une dépendance optionnelle manque.

## packages/ — cœur métier

### portfolio/ — analyse, risque, optimisation
| Module | Rôle |
|---|---|
| `metrics.py` · `risk_metrics.py` | perf (Sharpe/Sortino/Calmar/MaxDD) · VaR/CVaR (hist + paramétrique) |
| `risk_advanced.py` | **VaR Cornish-Fisher** (skew/kurtosis), **vol EWMA**, VaR composante |
| `garch.py` | **GARCH(1,1)** — vol conditionnelle prévue (variance targeting) |
| `evt.py` | **EVT** Peaks-Over-Threshold + GPD → VaR/ES 99,9 % (risque de queue) |
| `var_backtest.py` | **Kupiec POF + Christoffersen** (backtesting réglementaire de VaR) |
| `factor_risk.py` | **ACP** — risque systématique vs idiosyncratique |
| `psr.py` | **Sharpe probabiliste & déflaté** (anti-surapprentissage / essais multiples) |
| `risk_budget.py` | contribution au risque (MCTR/PCTR), ratio de diversification |
| `liquidity.py` | horizon de liquidation (ADV), % illiquide, VaR ajustée liquidité |
| `optimize.py` | **HRP**, min-variance, inverse-variance, **risk parity (ERC)** |
| `scenarios.py` | **stress-tests macro** (6 scénarios) + **hedging** (short indiciel) |
| `capacity.py` · `rebalance.py` | turnover/capacité ADV · bande de non-trading |
| `correlation.py` · `attribution.py` · `benchmark.py` · `review.py` · `stress.py` | corrélation/clusters · attribution · comparaison benchmarks · revue experte · Monte-Carlo |

### ml/ — apprentissage (anti-fuite)
| Module | Rôle |
|---|---|
| `cv.py` | **PurgedKFold + embargo** (López de Prado) |
| `labeling.py` | **triple-barrier** + meta-labels |
| `model.py` | LogitModel (numpy) · SklearnModel (GBM) — interface commune |
| `calibration.py` | **Platt** + Brier + courbe de fiabilité |
| `conformal.py` | **conformal prediction (LAC)** — couverture garantie |
| `meta.py` · `sizing.py` | **meta-labeling** (filtre faux positifs) · **bet sizing** par confiance |
| `drift.py` | **PSI** — dérive des features |
| `hpo.py` | **Optuna** (TPE) ou recherche aléatoire (repli) |
| `governance.py` · `evaluation.py` · `features.py` | champion/challenger, registre · AUC/precision · feature builder |

### backtest/
`fast_swing.py` (vectorisé, VIX, kill-switch, trailing ATR) · `multi_strategy.py` (tendance/momentum/retour moyenne + **ensemble**) · `walk_forward.py` (ancré/glissant) · `vectorbt_adapter.py` (optionnel) · `engine.py` · `statistics.py`

### execution/
`alpaca_broker.py` (actions paper) · `bitmart_broker.py` (crypto ccxt) · `sim_broker.py` · `algos.py` (**TWAP/VWAP**) · `reconciliation.py` (**cible↔réel**) · `tca.py` (**coûts d'exécution**) · `costs.py` · `live_engine.py` · `retry.py`

### fundamentals/
`provider.py` (synthétique + N-1) · `fmp_provider.py` (**FMP réel** si clé) · `ratios.py` · `valuation.py` (**DCF**, PER, EV/EBITDA) · `scoring.py` (**Piotroski complet**, **Altman Z**) · `factors.py` (value/quality)

### indicators/ · risk/ · strategies/ · storage/
`indicators` : momentum/trend/volatility · `extended.py` (pandas-ta) · **`technical_score.py`** (note 0-100) ·
`risk` : `engine.py` (kill-switch) · `rules.py` · **`limits.py`** (concentration/HHI) ·
`strategies` : swing, ma_crossover, rsi_reversion, **`ensemble.py`** ·
`storage` : bars/feature/journal/universe repos · `quality.py` · **`data_health.py`** (qualité + couverture)

## apps/ — produit
- **`apps/api/snapshot.py`** : assemble tout l'état (la source de vérité). `main.py` expose `/api/*` (cache TTL 15 min).
- **`apps/web/`** (Next.js) — 11 fenêtres : Dashboard, Thèmes, Signaux ML, **Fondamentaux**, Sentiment & news, Univers (virtualisé), Données, Portefeuille & Analyse, **Risque**, Positions, Trades. Mode **live** (auto-refresh), **⌘K**, thème clair/sombre, export CSV.
- **`apps/web/preview/build_interactive.py`** : terminal autonome `interactive.html` (un fichier, **PWA**, offline) à parité avec le front.
- **`deploy/hf_space/`** : démo Gradio (HuggingFace Space).

## Notes /20 (vs référence institutionnelle)
Risk **19** · UI/UX **19** · Trading **19** · ML **19** · Analyse fond./tech. **18** (→19 dès `FMP_API_KEY`). **Global ≈ 18,8/20.**
