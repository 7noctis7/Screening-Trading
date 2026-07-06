# 01 — ARCHITECTURE (schéma vivant)

> **Source de vérité.** Ce schéma reflète l'état réel du code. S'ils divergent,
> **le code a raison** → corriger le schéma immédiatement. Miroir Notion synchronisé,
> Obsidian fait foi.

## Conventions
- **1 responsabilité / fichier**. Plafond : < 400 lignes/fichier, < 50 lignes/fonction.
- **Dépendre d'abstractions** (`packages/core/interfaces.py`), jamais des implémentations.
- **Plugins auto-enregistrés** via `Registry` (`packages/core/registry.py`).
- **Config-driven** (YAML dans `config/`), **injection de dépendances** explicite, pas d'état global.
- **Event bus** interne (`packages/common/event_bus.py`) : un signal émis ≠ appel direct à l'exécution.
- **Point-in-time** obligatoire pour macro & fondamentaux.

## Couches (Clean / Hexagonal)
`core` (domaine pur, zéro dépendance) ← `adapters` (data/execution/storage) ← `apps` (api/web).
Le domaine ne dépend **jamais** de l'API, la DB ou l'UI.

---

## Diagramme 1 — Architecture (composants & couches)
```mermaid
graph TD
  subgraph EXT[Sources externes]
    A1[APIs marche: yfinance/Finnhub/CCXT/Alpaca]
    A2[Macro: FRED/ALFRED/FMI/OCDE]
    A3[Fondamental: OpenBB/FMP/SEC EDGAR]
    A4[Brokers: Alpaca paper / Bitmart gated]
    A5[News RSS + crypto: CoinGecko/DefiLlama/Binance]
  end
  subgraph CORE[packages/core - interfaces and models]
    C1[DataProvider / Broker / Strategy]
    C2[RiskRule / Factor / Sizer / Indicator]
  end
  subgraph PIPE[Chaine de traitement]
    D[data + pit_guard anti-fuite] --> R[macro and regime]
    R --> S[screening: filtres YAML + z-score]
    R --> F[fondamental and valo]
    SENT[sentiment: FinBERT/RSS PIT] --> K
    S --> K[ranking multi-facteur]
    F --> K
    K --> ST[strategies]
    ST --> PF[portefeuille and risque]
    PF --> EX[execution: run_live.py = chemin PROD unique]
  end
  subgraph RESEARCH[packages/research - gate 4 etages]
    GATE[placebo -> DSR -> PBO -> sabotage]
    LEDGER[(ledger hypotheses.jsonl)]
    LEDGER -.-> GATE
  end
  subgraph STORE[Stockage]
    DB[(SQLite/DuckDB/Parquet)]
    FS[feature store GOLD]
    JRNL[(journal.db: live_journal + live_roundtrip FIFO)]
  end
  subgraph LEARN[Apprentissage]
    JRNL --> ML[ML triple-barrier and meta-labeling, CV purgee]
    ML -. boucle .-> K
  end
  subgraph APP[Interface]
    API[API FastAPI + snapshot] --> WEB[Front Next.js + export statique Pages]
  end
  EXT --> D
  A4 --> EX
  EX --> JRNL
  D --> DB
  ML --> FS
  PF --> API
  JRNL --> API
  GATE -. rien ne passe en prod sans verdict .-> ST
  ALERTS[alertes: engine+sinks+throttle] --> EX
  ALERTS --> API
  LLMG[llm: garde anti-hallucination] -.-> API
  MCPTV[mcp_tradingview: overlays + kill-switch TV] -.-> EX
  CERT[testing/certification] -.-> PF
```

## Diagramme 2 — Flux de fonctionnement (bout en bout)
```mermaid
flowchart LR
  A[Donnee brute temps reel] --> B[Nettoyage et stockage point-in-time]
  B --> C[Macro and regime: VIX/Fed/FMI/cycle]
  C --> D[Screening technique + fondamental]
  D --> E[Ranking multi-facteur -> top actifs]
  E --> F[Strategie selon regime]
  F --> G{Filtre risque: R:R, stop, limites}
  G -- rejete --> X[Pas de trade]
  G -- valide --> H[Sizing: vol-target/Kelly bride]
  H --> I[Execution paper/live]
  I --> J[Journal: motif, PRU, PnL, features]
  J --> K[Analyse portefeuille + benchmarks + revue experte]
  J --> L[Reentrainement ML walk-forward]
  L -. ameliore .-> D
```

---

## État d'implémentation (mis à jour à chaque session)
| Module | Package | État |
|---|---|---|
| Core (interfaces + models + registry) | `packages/core` | ✅ posé (session 0) |
| Common (config/log/event bus) | `packages/common` | ✅ posé (session 0) |
| Data providers + univers | `packages/data` | ✅ +yfinance/FMP/wrappers/DuckDB (S6) |
| Indicateurs | `packages/indicators` | ✅ 8 indicateurs (S1) |
| Storage (bronze/silver/gold) | `packages/storage` | ✅ bronze/silver/GOLD feature store (S5) |
| Macro & régime | `packages/regime` | ✅ point-in-time vintages + cycle + surprises (S7) |
| Fondamental & valo | `packages/fundamentals` | ✅ ratios+DCF+value/quality (S4) |
| Ranking multi-facteur | `packages/ranking` | ✅ momentum/trend/low-vol (S3) |
| Stratégies | `packages/strategies` | ✅ 2 plugins (S1) |
| Backtest | `packages/backtest` | ✅ event-driven + walk-forward + DSR (S5) |
| Risque (engine + règles) | `packages/risk` | ✅ engine+veto+kill-switch (S1) |
| Portefeuille | `packages/portfolio` | ✅ HRP/ERC/min-var, VaR/CVaR/EVT, PSR/DSR, stress (S11) |
| Exécution (paper) | `packages/execution` | ✅ SimBroker+AlpacaBroker+Bitmart gated · journal décision + round-trip FIFO (ADR-0028/0031) · LiveEngine = simulateur |
| ML | `packages/ml` | ✅ triple-barrier, CV purgée/embargo, calibration, conformal, champion/challenger (S9) |
| Alertes | `packages/alerts` | ✅ engine+sinks+throttle+wiring — BRANCHÉ sur `run_live.py` (BLOC 1c) |
| Reporting | `packages/reporting` | ✅ analytics, tearsheet, notes sociétés, miroir Obsidian (S13) |
| API / Web | `apps/` | ✅ FastAPI snapshot + Next.js (dashboard, /positions réel-vs-cible, /screener explicable, /crypto live, /echecs) + export statique Pages |
| Recherche & gate | `packages/research` | ✅ gate 4 étages (placebo→DSR→PBO→sabotage), ledger, microstructure OFI/vPIN, alpha-decay (ADR-0024) |
| Screening | `packages/screening` | ✅ filtres YAML + composite z-score → `/screener` |
| Sentiment | `packages/sentiment` | ✅ FinBERT+lexique+RSS point-in-time + risk gate |
| Événements | `packages/events` | ✅ earnings (blackout) + IPOs |
| LLM | `packages/llm` | ✅ garde anti-hallucination + routeur local Ollama |
| MCP TradingView | `packages/mcp_tradingview` | ✅ overlays risque + alertes → kill-switch `run_live` |
| Certification | `packages/testing` | 🟡 protocole posé (`15_CERTIFICATION.md`) — registre à peupler (P1-8) |

> **Test de validation de l'archi** : *« ajouter un exchange / une stratégie /
> un indicateur / un facteur = 1 fichier, sans toucher au reste ».* Couvert par
> `tests/core/test_registry.py`.
