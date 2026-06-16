# Tester le système

## A. Vérification automatique (1 commande)
```bash
source .venv/bin/activate
bash scripts/check_all.sh
```
Lance les **154 tests**, les **7 démos** offline, et génère les aperçus HTML.

## B. Voir le site INTERACTIF tout de suite (sans rien installer)
```bash
python apps/web/preview/build_interactive.py
# ouvre apps/web/preview/interactive.html dans ton navigateur
```
Interactivité à tester avec la souris :
- **Onglets** Dashboard / Portefeuille / Positions (clic).
- **Courbe d'equity** : survole → crosshair + tooltip (valeur portefeuille vs S&P 500 au point).
- **Compteurs** (Sharpe, rendement…) : animation au chargement.
- **Screener** : clic sur une ligne → barres de contribution des facteurs.
- **Heatmap de corrélation** : survole une case → la paire + la valeur (et zoom).

## C. Le vrai site Next.js (interactif, temps réel via l'API)
```bash
# Terminal 1 — API
uv pip install -e ".[api]"
uvicorn apps.api.main:app --reload        # http://localhost:8000/api/dashboard

# Terminal 2 — front
cd apps/web && npm install && npm run dev  # http://localhost:3000
```
Le dashboard utilise **Recharts** : graphique d'equity avec tooltip/crosshair au survol,
cartes réactives, données rafraîchies toutes les 15 s depuis l'API.

## Ce que tu dois voir (résumé attendu)
- `pytest -q` → `154 passed`.
- `demo_backtest` → rendement ~+41%, Sharpe ~1.13 (synthétique).
- `demo_walkforward` → **Deflated Sharpe ≈ 0** = « non significatif » (garde-fou OK).
- `interactive.html` → tout réagit au survol/clic.

## Si ça coince
- `ModuleNotFoundError` → venv non activé, ou `uv pip install -e ".[dev,quant,ml,reporting]"`.
- Erreur **TA-Lib** → ignore (optionnel ; indicateurs numpy intégrés).
- Front `npm run dev` échoue → vérifie Node 20+ ; `rm -rf node_modules && npm install`.
