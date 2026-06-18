# Quant Terminal — Screening & Trading systématique multi-actifs

Plateforme **open-source** de **screening** et de **trading systématique** (actions, ETF, forex,
crypto, commodités, indices) de niveau institutionnel, avec un **terminal web premium** (style
hedge-fund). Priorités : **robustesse & reproductibilité > maintenabilité > gestion du risque >
alpha > produit**. Architecture en **plugins** (« ajouter un fichier, jamais toucher au cœur »),
**config-driven** (YAML), **point-in-time partout** (anti-fuite du futur). **Paper trading par défaut.**

> ⚠️ Aide à la décision — **pas un conseil en investissement**. Risque de perte en capital.

---

## ✨ Le terminal en un coup d'œil

10 fenêtres : **Dashboard** (perf vs benchmarks, régime, playbook VIX, screener+ML) ·
**Thèmes de marché** (heatmap YTD par secteur 4ᵉ révolution industrielle) · **Signaux ML** ·
**Sentiment & news** (FinBERT optionnel / lexique / repli momentum, news RSS gratuites) ·
**Fondamentaux** (DCF, ratios, Piotroski, Altman Z, note technique + combinée) ·
**Univers** (929 actifs, recherche/filtres, table virtualisée) · **Données** (collecte, qualité, couverture) ·
**Portefeuille & Analyse** (Monte-Carlo, attribution, revue experte) · **Risque** (VaR/EVT/GARCH,
backtest VaR, ACP, budget de risque, limites, stress, allocation HRP/ERC, multi-stratégie) ·
**Positions** · **Trades** · **Portefeuille réel** (Alpaca/Bitmart, réconciliation, TCA).

> 🧭 Carte complète des modules : [`docs/MODULES.md`](docs/MODULES.md).
> 📱 **Installable (PWA)** : la preview génère `manifest.webmanifest` + `sw.js` → « Ajouter à
> l'écran d'accueil » sur téléphone = vraie app, utilisable **hors-ligne**. ⌘K · mode live · thème clair/sombre.
> 🤗 **Démo publique gratuite** : déployable en un Space HuggingFace (`deploy/hf_space/`).

- **Capital fictif 10 000 $** alloué aux **meilleurs setups** (force relative), exposition
  **pilotée par le VIX** (1.0 / 0.7 / 0.4, **sans levier**), objectif : **surperformer l'univers équipondéré**.
- **Données réelles** branchables (yfinance / FMP / votre `YAHOO.db`, ~4 Go) avec repli synthétique —
  le build affiche le **MODE DES DONNÉES** (réel / mixte / synthétique).
- **ML** : Gradient Boosting (sklearn) ou logit numpy, **CV purgée + embargo** (López de Prado),
  triple-barrier — aucune fuite du futur.
- **Graphiques chandeliers** au clic (volumes, MA20/50/100/200, EMA, Bollinger, RSI, timeframe D/W/M,
  marqueurs achat/vente ▲▼) · **tables triables** · **$ partout** · cash ≥ 0.
- **Exécuteur paper** (`make live` / `make live-go`) : réplique l'allocation cible (poids × capital)
  vers **Alpaca (paper)** et **Bitmart (crypto)** — **dry-run par défaut**.
- Une **preview autonome** `apps/web/preview/interactive.html` (un seul fichier, aucune install).

```bash
python apps/web/preview/build_interactive.py   # génère/ouvre la preview interactive
```

---

## 🗺️ Architecture (cartographie)

```mermaid
flowchart TD
  subgraph SRC["Sources de données"]
    SEED["Seeds CSV (univers offline)"]; YF["yfinance / FMP"]; YAHOO["YAHOO.db (local, 4+ Go)"]; FRED["FRED / macro"]
  end
  subgraph CORE["packages/ — domaine (plugins)"]
    UNIV["data.universe<br/>builder multi-sources"]
    PROV["data.providers<br/>synthetic · yfinance · db"]
    STORE["storage<br/>bronze/silver/gold · feature store · quality"]
    IND["indicators"]; FUND["fundamentals"]; RANK["ranking (multi-facteur)"]
    REG["regime (macro point-in-time)"]; STRAT["strategies (swing…)"]
    SIZE["portfolio.sizing (vol-target)"]; RISK["risk (kill-switch)"]
    BT["backtest (vectorisé fast_swing)"]; EXEC["execution (Sim · Alpaca paper)"]
    ML["ml (CV purgée, triple-barrier)"]; PORT["portfolio (VaR/CVaR · Monte-Carlo · attribution · revue)"]
  end
  subgraph APP["apps/ — produit"]
    SNAP["api.snapshot<br/>assemble tout l'état"]
    API["api.main (FastAPI)<br/>/api/* + cache TTL 15min"]
    WEB["web (Next.js)"]; PREV["preview/interactive.html"]
  end
  SEED --> UNIV; YF --> PROV; YAHOO --> PROV; FRED --> REG
  UNIV --> SNAP; PROV --> STORE --> SNAP
  IND & FUND --> RANK --> SNAP
  REG --> STRAT --> BT --> SNAP
  SIZE & RISK --> BT
  ML --> SNAP; PORT --> SNAP; EXEC --> SNAP
  SNAP --> API --> WEB
  SNAP --> PREV
```

**Pipeline** : `données → (régime macro) → screening/ranking + ML → stratégie swing →
sizing vol-target → risk engine (veto/kill-switch) → backtest vectorisé → portefeuille
(perf, VaR/CVaR, Monte-Carlo) → API → terminal web`. Mêmes interfaces backtest ↔ paper ↔ live
(parité). Diagrammes vivants : [`vault/01_ARCHITECTURE.md`](vault/01_ARCHITECTURE.md).

| Dossier | Rôle |
|---|---|
| `packages/` | Cœur métier en plugins (indicateurs, stratégies, risque, ML, portefeuille…) |
| `apps/api/` | FastAPI : `snapshot.py` assemble l'état, `main.py` expose `/api/*` (cache TTL 15 min) |
| `apps/web/` | Front Next.js + **preview autonome** `interactive.html` |
| `config/` | YAML (univers, facteurs, risque, macro…) |
| `data/seed/` | Univers offline (CSV) · `scripts/` ETL & démos · `tests/` miroir · `vault/` mémoire |

---

## 🚀 Démarrage

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,quant,ml,reporting]"
pytest -q
# Terminal autonome (aucune API requise) :
python apps/web/preview/build_interactive.py    # ouvre apps/web/preview/interactive.html
# API + front :
make api        # uvicorn apps.api.main:app --reload   (http://localhost:8000)
make web        # cd apps/web && npm install && npm run dev (http://localhost:3000)
```

## 🖥️ Se connecter en local (2 fenêtres de terminal)

Le terminal complet (API + front) tourne avec **deux fenêtres de terminal ouvertes en même temps** :
l'une fait tourner le backend, l'autre le site. Laisse les deux ouvertes pendant que tu travailles.

**Fenêtre 1 — le backend (API FastAPI)** → sert les données sur `http://localhost:8000`
```bash
cd ~/Screening-Trading
source .venv/bin/activate
export QUANT_PRICE_DB="$HOME/Desktop/YAHOO.db"   # ta base réelle (adapte le chemin)
export FRED_API_KEY="ta_cle_fred"               # page Macro chiffrée (le FMI marche sans clé)
# fondamentaux réels via yfinance = défaut si en ligne (QUANT_FUND=synthetic pour forcer l'offline)
export QUANT_NEWS=1                              # news RSS réelles
make api
```

**Fenêtre 2 — le front (site Next.js)** → l'interface sur `http://localhost:3000`
```bash
cd ~/Screening-Trading/apps/web
npm install     # la 1ʳᵉ fois seulement
npm run dev
```

Puis ouvre **`http://localhost:3000`** dans ton navigateur (`Cmd+Shift+R` pour forcer le rechargement
après un `git pull`). La fenêtre 1 doit rester lancée : le site interroge l'API en continu.

> 💡 **Sans rien installer** : `python apps/web/preview/build_interactive.py` génère un fichier
> autonome `apps/web/preview/interactive.html` à ouvrir directement (aucune des 2 fenêtres requise).

## 📈 Brancher VOS données réelles (yfinance / FMP / YAHOO.db)

Le projet utilise une **vraie base si elle existe**, sinon le synthétique (cf.
[`docs/REAL_DATA.md`](docs/REAL_DATA.md)). Avec votre `YAHOO.db` (à garder hors Git) :

```bash
# ⚠️ deux commandes SÉPARÉES — remplacez le chemin par le vôtre :
export QUANT_PRICE_DB="/Users/thierryfanlo/data/YAHOO.db"
make api          # ou : python apps/web/preview/build_interactive.py
```

Mettre à jour la base chaque jour (append idempotent, jamais d'écrasement) :
```bash
python scripts/ingest_prices.py --since 2015-01-01   # backfill complet
python scripts/ingest_prices.py --daily              # incrémental quotidien
```

**Backtest walk-forward du preset best-practice** (qualité + risk-parity + DD-target + blackout +
no-trade band) **et de l'overlay volatilité gérée**, sur VOS données (point-in-time, net de coûts) :
```bash
export QUANT_PRICE_DB="$HOME/Desktop/YAHOO.db"   # sinon synthétique
make backtest-preset                              # preset vs swing vs équipondéré + Moreira-Muir
make calibrate-preset                             # meilleure combo (DD × top-K × bande) par Sharpe déflaté
make preset-report                                # rapport HTML (courbes + drawdowns) → out/preset_report.html
```

> **Biais du survivant** : l'univers ne contient que les titres *encore cotés*. Pour des backtests
> longs honnêtes, déposer `data/delisted.csv` (cf. `data/delisted.csv.example`) — l'audit s'affiche
> sur la page Données. Allocation **Black-Litterman** (vues = conviction) et **régime de volatilité**
> (calme/normal/stress) exposés dans Portefeuille / Risque.

**Automatiser la maj quotidienne en une commande** (macOS launchd / Linux crontab, 22h30 lun-ven) :
```bash
make cron-install      # active la tâche planifiée (logs : /tmp/quant_daily.log)
make cron-uninstall    # la désactive
```

**Depuis le téléphone** : lancez l'API sur le Mac en réseau local
(`make api-lan` → `uvicorn … --host 0.0.0.0`), puis ouvrez `http://IP_DU_MAC:8000` /
le front depuis le navigateur du téléphone (même Wi-Fi). Détails et cron : `docs/REAL_DATA.md`.

## 🤖 Répliquer l'allocation en paper (Alpaca + Bitmart)
```bash
make live          # APERÇU (dry-run) : affiche les ordres cibles, n'envoie RIEN
make live-go       # EXÉCUTE en paper (clés API .env requises) — Alpaca reste en paper
```
Routage : actions/ETF → **Alpaca (paper)** · crypto → **Bitmart** (ccxt). Le mode réel exige
`--live --yes` ET des clés API présentes. Clés dans `.env` (jamais committées).

## 🛡️ Garde-fous
Paper par défaut · aucun ordre réel sans feu vert + capital plafonné + stops · permissions API
minimales (jamais retrait) · `.env`/`*.db` jamais committés · kill-switch drawdown testé.

## 🔍 Audit du site (UI/UX, ML, finance, trading, data, risque)
Audit transversal honnête, noté /20 par critère avec axes de correction priorisés :
[`docs/AUDIT_SITE.md`](docs/AUDIT_SITE.md).

## 🔭 Pistes d'amélioration & écosystème
Voir [`docs/ROADMAP.md`](docs/ROADMAP.md) : moteur de backtest vectorisé (vectorbt/qlib),
charts pro (lightweight-charts/TradingView), exécution crypto (ccxt), data (polygon/tiingo),
features techniques (pandas-ta), PWA mobile, et durcissement MLOps.

## Licence
MIT recommandé (usage personnel open-source).
