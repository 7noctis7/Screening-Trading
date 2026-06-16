# Audit 10 axes — Quant Terminal

Audit technique, fonctionnel et visuel. Pour chaque axe : critique → cible concrète.
Statut : ✅ corrigé dans cette itération · ◻️ recommandé (suite).

---

## 1. Cohérence multi-fenêtres & intégrité des données (priorité absolue)

**Cause racine du bug constaté** : la matrice de **corrélation** était calculée sur
`_top_traded(journal, 8)` (les 8 actifs les plus tradés de TOUT l'historique), tandis que
**Positions/Trades** affichaient `broker.positions()` (positions ouvertes au dernier pas).
Deux sources différentes → actifs différents entre fenêtres.

✅ **Corrigé** : une **Single Source of Truth** = les positions ouvertes (`comp["rows"]`).
La corrélation, les **séries OHLC des graphes**, les KPI et le portefeuille réel dérivent
tous de ce même ensemble (`apps/api/snapshot.py`) :
```python
held = [r["symbol"] for r in comp["rows"]]
corr_syms = held[:12] if len(held) >= 2 else _top_traded(...)   # corrélation = positions
position_series = {r["symbol"]: ohlc(data[r["symbol"]]) for r in comp["rows"]}
```
Test de non-régression : `tests/api/test_snapshot.py::test_cross_window_coherence`
(`corr ⊆ positions`, 1 graphe par position, KPI = capital initial 10 000 $).

**Persistance / temps réel** : l'API met le snapshot en cache **TTL 15 min** ; le front
(React Query) refait un fetch toutes les 15 s → toute évolution se propage partout.
◻️ Cible plus poussée : websockets pour le live broker (push au lieu de pull).

## 2. Trading & exécution
- ✅ Coûts (frais + slippage bps) modélisés dès le backtest (`CostModel`).
- ✅ Stops/targets ATR ; sorties sur cassure de MM longue (faible rotation).
- ◻️ Types d'ordres : seuls Market sont simulés. Cible : Limit/Stop/Trailing dans `SimBroker`
  + détection de slippage réalisée vs théorique. ◻️ Fills **next-open** (anti look-ahead) au
  lieu de la clôture de la barre (cf. AUDIT.md). ◻️ Routage broker : Alpaca (actions) /
  Bitmart via `ccxt` (crypto).

## 3. Risk management
- ✅ Stop-loss/target ATR par position ; exposition par actif (`max_pct`) ; nb de positions max ;
  exposition brute plafonnée et **pilotée par le VIX** (×1.2 calme → ×0.3 panique).
- ✅ VaR/CVaR (`risk_metrics`), Monte-Carlo (proba de ruine + éventail).
- ◻️ **Daily max loss / kill-switch** existe (`packages/risk`) mais n'est pas câblé dans le
  backtest vectorisé `fast_swing` → l'ajouter (coupe les entrées si DD quotidien dépassé).
- ◻️ Expected Shortfall paramétrable, limites d'exposition **sectorielle** (déjà calculable
  via `sector_of`).

## 4. Portfolio allocation
- ✅ Allocation **par conviction** (force relative 6 mois) → surpondère les leaders ;
  benchmark juste = univers équipondéré (le swing le bat ~+90% vs +61%).
- ◻️ Modèles avancés à proposer en option : **risk parity**, **mean-variance** (PyPortfolioOpt),
  **Black-Litterman**. ◻️ Rebalancement calendaire (mensuel) avec prise en compte des frais
  (turnover-aware) plutôt que purement event-driven.

## 5. Analyse financière & technique
- ✅ Sharpe/Sortino/MaxDD/alpha/beta/IR ; **backtest vectorisé** O(n) par actif (plus de O(n²)).
- ✅ Indicateurs numpy (SMA cumsum, etc.). ◻️ Vectoriser RSI/ATR/EMA (boucles Python) ou passer
  à `pandas-ta`/TA-Lib pour la recherche massive.

## 6. Machine Learning & stratégie quant
- ✅ Pas de look-ahead : features point-in-time, **holdout temporel** (1 an) + AUC.
- ✅ Pipeline avancée présente (`packages/ml` : triple-barrière, **CV purgée + embargo**,
  frac-diff) conforme López de Prado.
- ◻️ Le score ML du dashboard utilise une régression logistique simple (démo) ; brancher la CV
  purgée + un modèle GBM (xgboost/lightgbm via l'adaptateur existant) et `TimeSeriesSplit`.
  ◻️ Suivi d'expériences (mlflow) + détection de drift (déjà `packages/ml/drift.py`).

## 7. Data pipeline & architecture
- ✅ Architecture en plugins (registries), config YAML, contrats qualité OHLCV.
- ✅ **Ingestion réelle** (`scripts/ingest_prices.py`, yfinance/FMP, append idempotent) +
  lecteur **SQLite/DuckDB** (`db_provider`) → branche votre `YAHOO.db`.
- ◻️ Reconnexion/retry réseau pour les flux live (websockets) ; ◻️ migrer le socle vers
  **DuckDB + Parquet partitionné** pour de gros historiques.

## 8. UI/UX & design (standards Apple)
- ✅ Top bar glassmorphism, hiérarchie claire, typographie tabulaire pour les chiffres,
  couleurs P&L sobres, animations d'apparition, heatmap, **graphique technique en chandeliers
  au clic** (SMA/EMA/Bollinger/RSI). 
- ◻️ Unifier la charte (tokens partagés entre preview HTML et Next.js — actuellement dupliquée).
  ◻️ Mode clair optionnel. ◻️ Charts Next.js via `lightweight-charts` (TradingView).

## 9. Fluidité & UX
- ✅ Onglets animés + clavier (ARIA), mobile (onglets défilables), tooltips au survol non
  bloquants, crosshair initialisé sur le point récent.
- ◻️ Rafraîchissement temps réel sans reflow (diffing/virtualisation des grandes tables ;
  l'explorateur univers limite déjà à 500 lignes). ◻️ Squelettes de chargement partout
  (déjà `loading.tsx`).

## 10. Plan d'action — 5 priorités (impact max / effort min)

| # | Action | Impact | Effort | Statut |
|---|---|---|---|---|
| 1 | **Single source of truth** (corrélation/graphes/KPI = positions ouvertes) | 🔴 élevé | faible | ✅ fait |
| 2 | **Daily max-loss / kill-switch** câblé dans `fast_swing` | 🔴 élevé | faible | ◻️ |
| 3 | **Fills next-open** + types d'ordres (Limit/Stop/Trailing) | 🟠 moyen | moyen | ◻️ |
| 4 | **ccxt (Bitmart) + Alpaca paper** : exécuter les ordres cibles | 🔴 élevé | moyen | ◻️ |
| 5 | **Unifier la charte** + `lightweight-charts` côté Next.js | 🟠 moyen | faible | ◻️ |
