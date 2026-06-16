# Front-end (Next.js + TypeScript)

Le front **consomme l'API** (`apps/api`) et ne contient aucune logique de trading.

## Lancer (ton environnement)
```bash
# 1) API
uv pip install fastapi uvicorn
uvicorn apps.api.main:app --reload          # http://localhost:8000

# 2) Front
cd apps/web && npm install && npm run dev    # http://localhost:3000
```
Design tokens : `lib/tokens.ts` (+ `tailwind.config.ts`), miroir de `vault/11_DESIGN_SYSTEM.md`.
Écrans prévus : Dashboard (✅ scaffold), Screener, Portefeuille/Analyse, Positions, Backtest.

## Aperçu sans build
`apps/web/preview/dashboard.html` — rendu statique depuis les vraies données du snapshot.
