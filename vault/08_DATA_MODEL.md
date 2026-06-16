# 08 — DATA MODEL

## Couches medallion (bronze → silver → gold)
- **bronze** : OHLCV brut, immuable, horodaté + `ingested_at` (lineage). Jamais réécrit.
- **silver** : validé (contrats qualité) + normalisé UTC, dédupliqué. Source des features.
- **gold** : indicateurs/facteurs/scores (à construire P1, table dédiée / feature store).

## Clé & idempotence
Clé primaire `(symbol, timeframe, ts)` + UPSERT → zéro doublon. Rechargement sûr
(incrémental via `last_ts()`, ou backfill). Implémenté : `SqliteBarsRepository`
(stdlib, testable). **Cible prod : DuckDB+Parquet** via la même interface (ADR-0006).

## Politique de TIMEFRAME & de cadence (réponse design)
> Distinguer **timeframe de barre** et **cadence de mise à jour**.

| Couche / usage | Timeframe canonique | Cadence d'update | Pourquoi |
|---|---|---|---|
| Actions/ETF · facteurs · screening/ranking | **daily** | batch **EOD** | moins bruité, moins d'overfit, moins cher, meilleure couverture gratuite ; c'est là que vivent factor investing & fondamentaux |
| Macro / régime | daily (donnée sous-jacente mensuelle/trim.) | quotidienne | **point-in-time** (vintages ALFRED) + délai de publication |
| Crypto (24/7) | **4h + daily** | continue/EOD | marché permanent, swing intraday pertinent |
| Forex | daily / 4h | EOD | piloté par différentiels macro |
| Stratégies intraday (si activées) | **1h** | intraday | seulement si l'edge le justifie |
| Monitoring positions live | tick / WS | temps réel | exécution & risque live, **pas** du stockage historique |

**Règles d'or** : ne jamais stocker plus fin que l'horizon de détention ne le justifie
(plus fin = plus de bruit, plus d'overfit, plus de coût). Stocker le plus fin *nécessaire*
puis **resampler vers le haut**. Le multi-timeframe est natif (clé `timeframe`).

## Journal de trades
Table dédiée (cf. `packages/storage/journal.py` + `TradeRecord`) avec **snapshot des
features à l'entrée** (non négociable pour le réapprentissage ML).
