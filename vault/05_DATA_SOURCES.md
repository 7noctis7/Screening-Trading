# 05 — DATA SOURCES
> APIs, clés (réf .env), quotas, schémas. À remplir au fil de l'intégration (P0/P1).

| Besoin | Source | Quota / notes | Clé (.env) |
|---|---|---|---|
| Actions/ETF/indices EOD+intraday | yfinance | fragile intraday → fallback | — |
| Temps réel stocks/forex/crypto | Finnhub | — | FINNHUB_API_KEY |
| Multi-actifs + 60 indicateurs | Alpha Vantage | quotas serrés → cache | ALPHAVANTAGE_API_KEY |
| Crypto réel/order book/exéc | CCXT (+ccxt.pro) | testnet d'abord | BINANCE_API_KEY |
| Actions/crypto + paper | Alpaca | paper natif | ALPACA_API_KEY |
| Macro US / taux / VIX | FRED (+ALFRED vintages) | illimité | FRED_API_KEY |
| Macro international | FMI/BM/OCDE/Eurostat/BCE/BLS | — | — |
| Fondamental/valo | FMP, OpenBB, Finnhub | — | FMP_API_KEY |

## Cadence de mise à jour (résumé — détail dans 08_DATA_MODEL.md)
- Socle **daily EOD** pour actions/ETF/facteurs/macro (point-in-time pour la macro).
- **4h+daily** crypto, **daily/4h** forex, **1h** seulement pour l'intraday justifié.
- Temps réel (WebSocket) = monitoring live des positions, pas le stockage historique.

## Sources d'univers (config/universe.yaml)
| Source | Type | Couvre | Réseau |
|---|---|---|---|
| forex/commodities/indices/etf/crypto/cac40/aex | static (CSV seed) | top20/100 + CAC40/AEX | non |
| sp500, nasdaq100, sbf120, ftse100, ftsemib, nikkei225, kospi, csi300 | wikipedia | constituants d'indices | oui |
| us_listings | nasdaq_trader | **NYSE + Nasdaq COMPLETS** (milliers) | oui |
| crypto_live | coingecko | top-N crypto par market cap | oui |

> Scraping Wikipédia : `table`/colonnes à vérifier au 1er run (mise en page évolue).
> Listings complets LSE/JPX/KRX/Borsa/SSE/SZSE : ajouter une source `exchange_listing`
> pointant leur fichier officiel (même patron que nasdaq_trader). Snapshot daté = point-in-time.

## Russell & cadence (S4)
- **russell1000 / russell3000** : `ishares_holdings` (IWB / IWV) — holdings iShares CSV.
- **Rebuild MENSUEL** : `rebuild_cadence_days: 30` ; `scripts/scheduler.py` (APScheduler,
  1er du mois 02:00 UTC) ou cron `0 2 1 * * python scripts/build_universe.py --network --force`.
- **Dédoublonnage par symbole** (priorité = ordre des sources) : zéro doublon d'actif.
