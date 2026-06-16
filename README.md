# Système de screening & trading systématique multi-actifs

Plateforme open-source de **screening** et de **trading systématique** (actions, ETF, forex,
crypto, commodities, indices), de niveau institutionnel. Priorités : **robustesse &
reproductibilité > maintenabilité > gestion du risque > alpha > produit**.
Architecture en plugins (« ajouter un fichier, jamais toucher au cœur »), config-driven (YAML),
**point-in-time partout** (anti-fuite du futur). **Paper trading par défaut.**

> ⚠️ Aide à la décision — **pas un conseil en investissement**. Risque de perte en capital.

## Installation
Voir **[INSTALL.md](INSTALL.md)**. Démarrage rapide :
```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,quant,ml,reporting]"
pytest -q            # 154 tests
make demos           # démos offline (données synthétiques)
```

## Ce qui est implémenté (13 sessions, 154 tests)
| Domaine | Contenu |
|---|---|
| **Univers & données** | Builder mensuel multi-marchés source-driven (sans doublons) ; providers synthetic/yfinance/FMP via wrappers fallback/cache/rate-limit ; backend SQLite↔DuckDB pluggable |
| **Stockage** | Medallion bronze/silver/gold ; feature store (anti training/serving skew) ; qualité bloquante (pandera-like) |
| **Macro & régime** | **Point-in-time (vintages ALFRED)** : MacroStore `as_of`, surprises éco, cartographie macro→actifs, classifieur de cycle |
| **Screening & ranking** | Indicateurs anti-look-ahead ; fondamental Vernimmen + valo Damodaran (sector-neutral) ; ranking multi-facteur explicable |
| **Stratégies & risque** | Stratégies plugin (trend/momentum/range/breakout) ; sizing (fixed/vol-target/Kelly bridé) ; risk engine + R:R + **kill-switch** |
| **Backtest & validation** | Moteur event-driven ; **walk-forward + deflated Sharpe** (anti-surapprentissage) |
| **ML** | Triple-barrier + meta-labeling ; **CV purgée & embargo** ; frac-diff ; champion/challenger |
| **Exécution** | SimBroker + **AlpacaBroker** (paper) ; **moteur live (parité backtest↔live)** ; retries idempotents ; réconciliation |
| **Portefeuille** | Mesures relatives (alpha/beta/IR…) ; VaR/CVaR ; corrélation/clustering ; attribution ; stress/Monte Carlo ; **revue experte CFA/FRM/CPA/CAIA** |
| **Alertes** | Multi-canal (Telegram/Discord/console), sévérité, throttle, handlers event-bus |
| **Excellence op** | Drift PSI ; audit trail rejouable ; télémétrie ; backup/restore ; **tear sheets HTML/PDF** |
| **API & front** | FastAPI (payloads testés) ; front Next.js (Dashboard, Portefeuille, Positions) ; aperçus HTML |

## Architecture
Monorepo : `packages/` (domaine, plugins) · `apps/` (api, web) · `config/` (YAML) · `tests/`
(miroir) · `vault/` (mémoire Obsidian = source de vérité) · `scripts/` (démos, ETL).
Diagrammes Mermaid vivants dans [`vault/01_ARCHITECTURE.md`](vault/01_ARCHITECTURE.md).

## Données réelles
Clés gratuites dans `.env` (FRED, FMP, Alpaca paper) puis `scripts/verify_real_data.py` /
`scripts/verify_alpaca.py`. Voir INSTALL.md §6.

## Garde-fous
Paper par défaut · aucun ordre réel sans feu vert explicite + capital plafonné + stops ·
permissions API minimales (jamais retrait) · `.env` jamais committé · kill-switch testé.

## Licence
À définir (MIT recommandé pour un usage personnel open-source).
