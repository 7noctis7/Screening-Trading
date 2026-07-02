# Roadmap sources de données (gratuit, API/MCP) — priorisé par valeur/coût de maintenance

> Règle d'admission d'une source : elle doit (a) alimenter un facteur réellement utilisé,
> (b) être validable contre une 2e source, (c) être point-in-time ou horodatable.
> Chaque source = 1 adaptateur DataProvider + contrats pandera + entrée ici.
> MCP = recherche interactive dans Claude ; la PRODUCTION ingère via API directe (cron, retries, cache).

## P0 — à intégrer en premier
| Source | Données | Pourquoi | Accès | Pièges |
|---|---|---|---|---|
| **FRED + ALFRED** | Macro US, taux, VIX, M2 | Cœur du régime top-down ; ALFRED = vintages point-in-time | API key gratuite, quasi illimité | Toujours joindre sur release_date, pas sur period |
| **SEC EDGAR** | États financiers (XBRL companyfacts), 13F, Form 4 insiders | LE fondamental point-in-time gratuit : daté par date de DÉPÔT → résout l'as-published pour actions US | API publique gratuite, 10 req/s, User-Agent requis | Parsing XBRL non trivial ; commencer par companyfacts JSON |
| **Binance via CCXT** | OHLCV, funding rates, open interest, order book | Cœur crypto : prix + coût réel du short (funding) + positionnement (OI) | Gratuit, WebSocket inclus | Historique funding limité selon endpoints → stocker en continu dès J1 |

## P1 — forte valeur, après le socle
| Source | Données | Usage | Accès |
|---|---|---|---|
| **Coinbase (via CCXT)** | OHLCV crypto | 2e provider → validation croisée (cross_provider.py) des prix Binance | Gratuit |
| **CBOE** | Put/call ratio, indice SKEW | Features risk-appetite complémentaires du VIX term structure | CSV gratuits |
| **Stooq** | EOD actions/indices monde | Fallback + validation croisée de yfinance | Gratuit, sans clé |
| **US Treasury FiscalData** | Émissions, dette, TGA | Liquidité macro fine | API gratuite |

## P2 — quand les stratégies le justifient
| Source | Données | Usage | Réserve honnête |
|---|---|---|---|
| **Coinglass** | Liquidations, long/short ratio, OI agrégé multi-exchanges | Signaux de positionnement crypto | Free tier restrictif (rate limits) ; funding/OI déjà récupérables par exchange via CCXT — n'ajoute vraiment que les liquidations et l'agrégation |
| **DefiLlama** | TVL, flux on-chain | Proxy « fondamental » crypto | Gratuit, fiable |
| **Alternative.me** | Fear & Greed crypto | Feature sentiment simple | Gratuit |
| **GDELT** | Flux news mondial | Sentiment NLP à grande échelle | Volumétrie énorme : filtrer agressivement |

## Déjà dans le spec (rappel)
yfinance (fragile → toujours cross-validé), Finnhub, Alpha Vantage, Twelve Data, Alpaca, FMI/OCDE/Eurostat/BCE, OpenBB, datasets Damodaran.

## Anti-pattern à refuser
Ajouter une source « parce qu'elle est gratuite ». Chaque source coûte : maintenance
d'adaptateur, quotas, checks qualité, risque de rupture d'API. Plus de données ≠
meilleur système ; plus de données VALIDÉES alimentant des facteurs UTILISÉS = meilleur système.
