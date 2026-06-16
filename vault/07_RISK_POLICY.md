# 07 — RISK POLICY

> Source de vérité : `config/risk.yaml`. Implémenté dans `packages/risk/`.

## Par trade
- Risque ≤ `max_risk_pct` du capital (via distance au stop).
- **R:R ≥ `min_reward_risk`** (défaut 2.0) sinon trade rejeté (`reward_risk` rule).
- **Stop obligatoire** (ATR-based) ; target = multiple d'ATR.

## Portefeuille
- `max_positions`, `max_exposure_per_asset_pct` (règle veto), `max_gross_exposure` (pas de levier par défaut).
- **`max_daily_drawdown_pct` → kill-switch** : arme et refuse toute entrée jusqu'au reset quotidien.

## Défense en profondeur (ADR-0004)
Le sizer dimensionne dans les limites ; le risk engine reste un backstop dur. Un seul veto bloque.

## À venir (P1)
expo par classe & par cluster corrélé, VaR/CVaR comme contrainte, stop de portefeuille.
