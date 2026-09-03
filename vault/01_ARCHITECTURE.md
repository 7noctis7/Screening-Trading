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
  subgraph MANDAT[packages/mandate - definition declarative]
    MD[mandat JSON: contraintes + parametres]
    MH[identite = hash canonique]
    MP[harnais de purete: determinisme / env / equivalence]
    MD --> MH
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
  MD -. pilote .-> ST
  MH -. tracee dans .-> JRNL
  MP -. verifie .-> ST
  subgraph RESEARCH[packages/research - gate 4 etages]
    GATE[placebo -> DSR -> PBO -> sabotage]
    LEDGER[(ledger hypotheses.jsonl)]
    FDR[fdr: Benjamini-Hochberg criblage simultane]
    LEDGER -.-> GATE
    FDR -.-> GATE
  end
  subgraph STORE[Stockage]
    DB[(SQLite/DuckDB/Parquet)]
    FS[feature store GOLD]
    JRNL[(journal.db: live_journal + live_roundtrip FIFO)]
  end
  subgraph REPAIR[Reparation du registre - ordre NON commutatif]
    FILLS[ordres EXECUTES du courtier = verite terrain]
    COMP[completer_ouvertures: entrees manquantes, VWAP des fills non couverts]
    RECO[reconcilier_journal: sorties, idempotence en QUANTITE]
    DIAG[diag_journal_compte: couverture + identite comptable]
    FILLS --> COMP --> RECO --> DIAG
  end
  FILLS --> EX
  COMP --> JRNL
  RECO --> JRNL
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

## Modules SHADOW — écrits, testés, HORS des deux diagrammes (2026-09-02)

Les diagrammes ci-dessus décrivent la PRODUCTION. Les modules suivants existent, sont
testés, et n'ont **aucun appelant en production** : les dessiner dans le flux ferait
croire qu'ils y sont. Ils y entreront un par un, après la porte de
`vault/15_CERTIFICATION.md` — et le diagramme sera mis à jour à ce moment-là, pas avant.

| Module | Rôle | Ce qui manque pour sortir de SHADOW |
|---|---|---|
| `indicators/liquidite_ict` | SFP, BOS, CHoCH, zone OTE, order block (as-of `i`) | mesure au banc `candidats_lab` |
| `strategies/moteur_swing` | `MarketStructureEngine`, `RiskManager` (orchestration) | idem + données 1H pour la jambe de raffinement |
| `strategies/moteur_sortie` | `ExitEngine` : temps 15 j, liquidité opposée, partielle CVD | mesure contre la sortie actuelle (`sortie_lab`) |
| `risk/garde_swing` | filtre MM200 marché, plafond de corrélation 30 j | mesure de l'effet sur le portefeuille réel |
| `ml/caracteristiques_swing` | features z-score EMA, RSI multi, moments, squeeze | IC de Spearman + ratio OOS/IS via `ml/promotion` |
| `portfolio/metriques_survie` | Ulcer, temps sous l'eau, R² log, ES Cornish-Fisher | rien : mesure pure, branchable au dashboard |
| `backtest/coeur_multi_actifs` | cœur QQQ + obligations + or, parts déclarées | exécuter `make coeur-multi` et appliquer ADR-0053 |

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
| **Mandat (définition déclarative)** | `packages/mandate` | ✅ identité = hash canonique · cosmétique hors identité · cibles de résultat refusées · harnais de pureté déterminisme/env/équivalence (ADR-0048/0049/0050) |
| Backtest | `packages/backtest` | ✅ event-driven + walk-forward + DSR (S5) · dimensionnement **notionnel ou à risque constant** (`risque_par_trade`, 0,5 % en prod — banc `scripts/sizing_lab.py`, ADR-0051) |
| Risque (engine + règles) | `packages/risk` | ✅ engine+veto+kill-switch (S1) |
| Portefeuille | `packages/portfolio` | ✅ HRP/ERC/min-var, VaR/CVaR/EVT, PSR/DSR, stress (S11) · **intégrité des séries** (un NaN est un incident, jamais une valeur) · **fragilité** : marge de payoff, PF privé des 5 meilleurs, significativité corrigée de la dépendance, $ contre R (ADR-0051) |
| Exécution (paper) | `packages/execution` | ✅ SimBroker+AlpacaBroker+Bitmart gated · journal décision + round-trip FIFO (ADR-0028/0031) · LiveEngine = simulateur |
| ML | `packages/ml` | ✅ triple-barrier, CV purgée/embargo, calibration, conformal, champion/challenger (S9) |
| Alertes | `packages/alerts` | ✅ engine+sinks+throttle+wiring — BRANCHÉ sur `run_live.py` (BLOC 1c) |
| Reporting | `packages/reporting` | ✅ analytics, tearsheet, notes sociétés, miroir Obsidian (S13) |
| API / Web | `apps/` | ✅ FastAPI snapshot + Next.js (dashboard, /positions réel-vs-cible, /screener explicable, /crypto live, /echecs) + export statique Pages |
| Recherche & gate | `packages/research` | ✅ gate 4 étages (placebo→DSR→PBO→sabotage), ledger, **fdr Benjamini-Hochberg (ADR-0050)**, microstructure OFI/vPIN, alpha-decay (ADR-0024), `biais_fermeture` (réconciliation lots↔positions), `completion_ouvertures` (entrées manquantes, ADR-0057) |
| Screening | `packages/screening` | ✅ filtres YAML + composite z-score → `/screener` |
| Sentiment | `packages/sentiment` | ✅ FinBERT+lexique+RSS point-in-time + risk gate |
| Événements | `packages/events` | ✅ earnings (blackout) + IPOs |
| LLM | `packages/llm` | ✅ garde anti-hallucination + routeur local Ollama |
| MCP TradingView | `packages/mcp_tradingview` | ✅ overlays risque + alertes → kill-switch `run_live` |
| Certification | `packages/testing` | 🟡 protocole posé (`15_CERTIFICATION.md`) — registre à peupler (P1-8) |

> **Test de validation de l'archi** : *« ajouter un exchange / une stratégie /
> un indicateur / un facteur = 1 fichier, sans toucher au reste ».* Couvert par
> `tests/core/test_registry.py`.
