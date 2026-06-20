# MCP TradingView — connecteur plug-and-play

Serveur **MCP** (Model Context Protocol) qui donne à l'agent IA des outils graphiques/quant pour
interagir avec le terminal et TradingView (`lightweight-charts`). **Package indépendant** : aucun
import du cœur de trading, aucun module du cœur ne l'importe.

## Lancer
```bash
make mcp-tv          # = python -m packages.mcp_tradingview.server   (transport stdio)
```
- Si le SDK `mcp` est installé (`uv pip install mcp`) → transport stdio standard.
- Sinon → repli **JSON-RPC 2.0 sur stdio** (sans dépendance), compatible MCP de base.

Brancher dans **Claude Desktop** (`claude_desktop_config.json`) :
```json
{
  "mcpServers": {
    "quant-tradingview": {
      "command": "bash",
      "args": ["-lc", "cd /chemin/Screening-Trading && source .venv/bin/activate && python -m packages.mcp_tradingview.server"]
    }
  }
}
```

## Outils exposés
| Outil | Rôle |
|---|---|
| `plot_signal_on_chart(ticker, markers \| timestamps+sides+prices)` | Marqueurs ▲▼ du journal réel/paper (net de frais) |
| `overlay_risk_bands(ticker, timestamps, upper_band, lower_band)` | Cônes VaR/EVT, no-trade bands |
| `set_blackout_zones(ticker, zones)` | Zones de blackout résultats (SEC EDGAR / FMP) |
| `generate_pine_script(strategy_name, yaml_config)` | Preset YAML → Pine Script v5 (cross-validation) |
| `fetch_tv_technical_alerts()` | Alertes TV (webhook) → veto/kill-switch risk-engine |
| `auto_risk_bands(ticker?, var, lookback)` | **Auto** : cône VaR/EVT calculé sur les prix réels (via l'API) → chart |
| `overlay_triple_barrier(ticker, pt, sl, horizon)` | Barrières ML (TP/SL/temps) du dernier achat → chart |
| `compare_pine_python(ticker, dd_target, lookback)` | Backtest Python équivalent au Pine → métriques de cross-validation + code Pine |
| `query_market_db(db, sql, limit)` | **Lecture seule** (SELECT) de `data/market.db` / `crypto.db` — audit data en langage naturel |

## Brancher d'autres serveurs MCP (officiels uniquement)
Exemple prêt à l'emploi : **`config/claude_desktop_config.example.json`** (remplace `/ABS/PATH/TO/...`).
Il câble, en plus de `quant-tradingview`, des serveurs **de référence Anthropic** : `filesystem`, `git`,
`fetch`, `memory`, `sequential-thinking`, `time`. Pour interroger tes bases de prix, préfère l'outil
audité **`query_market_db`** (lecture seule) plutôt qu'un serveur SQLite tiers en écriture.

### Cônes de risque automatiques (sans l'agent)
```bash
make mcp-overlays    # = python scripts/mcp_populate_overlays.py  (API démarrée requise)
```
Lit `/api/positions` (séries + marqueurs réels) et `/api/events` (blackouts résultats), calcule le
cône **VaR/EVT** point-in-time sur les prix réels, et écrit l'overlay store → le chart l'affiche.
Idéal en cron. Transport MCP natif : `uv pip install -e ".[mcp]"`.

## Pont vers le navigateur
Les outils ÉCRIVENT dans `.cache/tv_overlays.json` (overlay store, écriture atomique).
L'API les sert via **`GET /api/overlays?ticker=…`** ; le front (`TechnicalChart`, hook `useOverlays`)
les rend sur `lightweight-charts` (cônes + blackouts). Les alertes TV arrivent par
**`POST /api/tv/webhook`** → `.cache/tv_alerts.json`.

## Garde-fous
- **Point-in-time** : overlays & alertes sont **affichage / live uniquement** — JAMAIS lus par le
  backtest ni l'entraînement ML (CV purgée + embargo). Aucune fuite du futur.
- **Robustesse** : chaque outil encapsule ses erreurs (`{"error": …}`), le serveur ne crashe pas.
  Flux TV indisponible → dégradation propre (overlays vides, veto neutre), pas de données inventées.
- `.cache/*.json` est local et **jamais commité**.
