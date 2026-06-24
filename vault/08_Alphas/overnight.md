---
type: alpha_hypothesis
statut: hypothese
classe: [equity, etf]
horizon: swing
facteur: overnight
dsr: null
pbo: null
sharpe: null
maxdd: null
sources: ["[[paper_cooper_overnight]]"]
date_creation: 2026-06-24
---

# 🎯 Anomalie overnight (close → open)

## Thèse (sens économique)
> La prime de risque actions se concentre **overnight** (détenteurs nocturnes rémunérés pour le
> risque binaire des news hors séance) ; l'intraday est en grande partie du bruit.

## Implémentation
- Facteur `overnight` (`packages/ranking/factors.py::Overnight`) : moyenne des rendements
  `open[t] / close[t-1] - 1` sur `window` jours. Point-in-time.
- Backtestable via le screener / `make backtest-preset` (le facteur est dans `factor_calcs`).

## Résultats
- **À backtester sur données réelles** (DSR/PBO encore null). `make calibrate-preset` → loguera le DSR.

## Verdict
HYPOTHÈSE — gate : promu seulement si DSR>0.5 ET PBO<0.5 net de coûts.

## Liens
- Orthogonal au [[momentum_12_1]] (composante intraday vs overnight) → bon candidat à combiner.
