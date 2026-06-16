# Installation & mise sur GitHub

Guide pas-à-pas pour cloner le projet dans un nouveau dépôt GitHub, l'installer et
vérifier que tout fonctionne. **Aucun ordre réel n'est exécuté** (paper par défaut).

---

## 0. Prérequis

| Outil | Version | Pour |
|---|---|---|
| Python | 3.11+ (testé 3.12) | tout le backend |
| git | récent | versionnage |
| Node.js | 20+ | front Next.js (optionnel) |
| uv | dernier | gestion des dépendances Python (recommandé) |

Installer `uv` (rapide, recommandé) :
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS/Linux
# ou : pip install uv
```

---

## 1. Récupérer le code

Tu as reçu `quant-trading-system.zip`. Décompresse-le : il contient un dossier `project/`
qui **est** le dépôt complet (code, configs, tests, vault, front, CI).

```bash
unzip quant-trading-system.zip
mv project quant-trading-system      # renomme à ta convenance
cd quant-trading-system
```

---

## 2. Créer le dépôt GitHub

```bash
git init
git add .
git commit -m "Initial commit — système de screening & trading multi-actifs"
git branch -M main
# crée un dépôt vide sur github.com (sans README), puis :
git remote add origin https://github.com/<ton-user>/<ton-repo>.git
git push -u origin main
```
> `.gitignore` est déjà présent (exclut `.env`, `__pycache__`, `out/`, DB locales, `node_modules`).
> **Ne committe jamais `.env`** (clés d'API).

---

## 3. Installer les dépendances Python

### Option rapide (suffit pour tests + démos offline)
```bash
uv venv
source .venv/bin/activate            # Windows : .venv\Scripts\activate
uv pip install -e ".[dev,quant,ml,reporting]"
```
Cela installe numpy, pandas, scipy, scikit-learn, reportlab, pytest, ruff, mypy.

### Option complète (données réelles + API + portefeuille)
```bash
uv pip install -e ".[dev,quant,ml,reporting,data,api,portfolio,quality,orchestration]"
```
> **TA-Lib** (`indicators`) nécessite une lib système (`brew install ta-lib` / `apt install
> libta-lib0`). Le projet fonctionne **sans** : il a des indicateurs numpy intégrés.

---

## 4. Vérifier que tout fonctionne

### Tests
```bash
pytest -q
```
Attendu : **154 tests passés**.

### Démos offline (aucun réseau requis, données synthétiques)
```bash
python scripts/demo_backtest.py        # backtest event-driven + métriques
python scripts/demo_walkforward.py     # walk-forward + deflated Sharpe
python scripts/demo_macro_regime.py    # macro/régime point-in-time
python scripts/demo_ml.py              # triple-barrier + CV purgée
python scripts/demo_paper_loop.py      # exécution paper (parité live)
python scripts/demo_alerts.py          # alertes multi-canal
python scripts/demo_ops.py             # drift + audit + tear sheet PDF
```
Ou tout d'un coup : `make demos`.

### Aperçus visuels (HTML, ouvrables au navigateur)
```bash
python apps/web/preview/build_preview.py
# ouvre apps/web/preview/dashboard.html et portfolio.html
```

---

## 5. Lancer l'API + le front (optionnel)

```bash
# Terminal 1 — API
uv pip install -e ".[api]"
uvicorn apps.api.main:app --reload          # http://localhost:8000/api/dashboard

# Terminal 2 — front
cd apps/web && npm install && npm run dev    # http://localhost:3000
```

---

## 6. Brancher les données réelles (quand tu veux sortir du synthétique)

Crée un fichier `.env` à la racine (jamais committé) :
```bash
FRED_API_KEY=...            # https://fred.stlouisfed.org (gratuit) — macro
FMP_API_KEY=...             # financialmodelingprep.com (gratuit) — fondamentaux
ALPACA_API_KEY=...          # alpaca.markets — PAPER
ALPACA_API_SECRET=...
TELEGRAM_BOT_TOKEN=...      # alertes (optionnel)
TELEGRAM_CHAT_ID=...
```
Puis vérifie en ligne :
```bash
python scripts/verify_real_data.py    # yfinance + FMP + DuckDB
python scripts/verify_alpaca.py       # compte paper Alpaca (aucun ordre)
```

---

## 7. Docker (optionnel)
```bash
docker build -t quant-api .
docker run -p 8000:8000 quant-api
```

---

## Garde-fous (à lire)
- **Paper trading par défaut.** Aucun ordre réel sans modification explicite + capital plafonné + stops.
- **Ceci n'est pas un conseil en investissement.** Risque de perte en capital.
- Permissions d'API minimales (jamais de retrait), `.env` jamais committé, kill-switch testé avant tout live.

## Où regarder ensuite
- `vault/00_INDEX.md` — carte du projet · `vault/01_ARCHITECTURE.md` — diagrammes.
- `vault/04_JOURNAL.md` — historique des 13 sessions de construction.
- `README.md` — vue d'ensemble.
