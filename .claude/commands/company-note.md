---
description: Génère une note d'analyse institutionnelle (Vernimmen + Damodaran + audit PwC) pour un ticker, en HTML/PDF, et l'archive dans le vault.
argument-hint: "<TICKER> (ex. AAPL)"
---

Génère la **note d'analyse institutionnelle** pour le ticker demandé (`$ARGUMENTS`).

Contenu attendu (moteur : `packages/reporting/company_report.py` + `company_report_render.py`) :
Portfolio Snowflake (VALUE/FUTURE/PAST/HEALTH/DIVIDEND), Vernimmen (ROCE/WACC/EVA/DuPont/gearing),
Damodaran (DCF scénarios + inversé, multiples vs secteur), 3 scores (fondamental/technique/ML),
risk management (vol/VaR/CVaR/Sharpe/Sortino/stop), historique annuel + trimestriel (yfinance → SEC
EDGAR 10-Q), actionnariat (institutionnels/insiders en %), conversion devise ADR, et **gouvernance
PwC** (audit d'intégrité + réconciliation GAAP vs Non-GAAP, blocking alert, pénalité de surévaluation).

Étapes :
1. **À la demande (local, API lancée)** : ouvrir
   `http://localhost:8000/api/company_report?ticker=<TICKER>&format=html&theme=dark`
   (formats : `html`/`pdf`, thèmes : `dark`/`light`).
2. **En batch / archivage** : `make reports` pré-génère les notes (top-conviction + positions) dans
   `out/notes/AAAA-MM-JJ/` + miroir Obsidian (`vault/04_Companies/`, tag `#company`).
3. **Données réelles** : `QUANT_FUND=yf` (défaut en ligne) ; repli synthétique si hors-ligne.
   Vérifier qu'aucune valeur n'est `NaN`/`Inf` dans la sortie (formatteurs NaN-safe).
4. Si la note doit apparaître sur le site statique, elle est régénérée par le build
   (`scripts/dump_static.py` → `apps/web/public/reports/<TICKER>.html`).

Rappel : ces notes portent sur des sociétés cotées (données publiques) — aucune donnée perso/courtier.
