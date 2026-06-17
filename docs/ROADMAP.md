# Pistes d'amélioration & écosystème utile

Recommandations priorisées pour faire évoluer le projet, avec les bibliothèques /
dépôts open-source pertinents à intégrer.

## ✅ Déjà livré (itération sentiment + mobile + démo)
- **Sentiment & news** : `packages/sentiment/` — lexique finance (stdlib, toujours dispo),
  **FinBERT** optionnel (`ProsusAI/finbert`), lecteur **RSS** gratuit ; onglet dédié dans le
  terminal (repli momentum hors-ligne, activable en news réelles via `QUANT_NEWS=1`).
- **PWA mobile** : `manifest.webmanifest` + `sw.js` générés → app installable, hors-ligne.
- **Bridge pandas-ta** : `packages/indicators/extended.py` (repli RSI maison si absent).
- **Adaptateur vectorbt** : `packages/backtest/vectorbt_adapter.py` (repli numpy si absent).
- **Démo HuggingFace Space** (gratuite) : `deploy/hf_space/` (Gradio).

## P0 — Fiabiliser le passage en réel
- **Exécution crypto réelle** : [`ccxt`](https://github.com/ccxt/ccxt) (Bitmart + 100 exchanges,
  API unifiée) pour le broker crypto, en miroir d'`AlpacaBroker` (actions). Garder paper par défaut.
- **Données marché robustes** : [`polygon.io`](https://polygon.io),
  [`tiingo`](https://www.tiingo.com), [`alpaca-py`](https://github.com/alpacahq/alpaca-py)
  (data + paper) en plus de yfinance ; cache + rate-limit déjà prévus côté wrappers.
- **Réconciliation & idempotence** live (déjà amorcé dans `packages/execution`) : tests de
  parité backtest↔paper sur données réelles.

## P1 — Backtest & recherche
- **Moteur vectorisé** pour la recherche massive : [`vectorbt`](https://github.com/polakowo/vectorbt)
  ou [`qlib`](https://github.com/microsoft/qlib) (Microsoft, pipeline quant complet + modèles).
  Garder notre `fast_swing` pour le snapshot, brancher vectorbt pour les sweeps de paramètres.
- **Indicateurs** : [`pandas-ta`](https://github.com/twopirllc/pandas-ta) /
  [`TA-Lib`](https://github.com/TA-Lib/ta-lib-python) pour élargir la bibliothèque.
- **Validation** : walk-forward + deflated/PBO (déjà présents) à exécuter systématiquement
  avant toute mise en prod d'une stratégie.

## P1 — Front / UX
- **Charts pro** : [`lightweight-charts`](https://github.com/tradingview/lightweight-charts)
  (TradingView, déjà en dépendance) pour des bougies/volumes interactifs dans le front Next.js.
- **PWA mobile** : manifest + service worker → installation sur téléphone, mode hors-ligne.
- **État serveur** : remplacer le cache snapshot unique par un vrai state live quand le broker
  est branché (websockets pour le temps réel).

## P2 — ML / MLOps
- Tracking d'expériences : [`mlflow`](https://github.com/mlflow/mlflow) (versions de modèles,
  métriques, champion/challenger). Le socle gouvernance existe (`packages/ml/governance.py`).
- Modèles : `scikit-learn` / `xgboost` / `lightgbm` via l'adaptateur déjà prévu
  (`packages/ml/model.py`) — repli numpy pur conservé pour la portabilité.
- Features store en ligne (Feast) si passage multi-actifs temps réel.

## P2 — Données & stockage
- **DuckDB + Parquet partitionné** par symbole pour de gros historiques (lecture analytique
  rapide, compatible cloud). Le lecteur `db_provider` accepte déjà SQLite ; étendre à DuckDB.
- **Qualité** : Great Expectations / pandera pour des contrats de données plus riches.

## Sécurité & conformité
- Secrets via gestionnaire dédié (jamais en clair) ; permissions API minimales (jamais de
  retrait) ; journal d'audit rejouable (déjà présent) ; limites de risque par config.
