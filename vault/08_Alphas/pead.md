---
type: alpha_hypothesis
statut: hypothese
classe: [equity]
horizon: swing
facteur: pead
dsr: null
pbo: null
sharpe: null
maxdd: null
sources: ["[[paper_bernard_thomas_1989]]"]
date_creation: 2026-06-24
---

# 🎯 PEAD — Post-Earnings Announcement Drift

## Thèse (sens économique)
> Sous-réaction comportementale aux surprises de résultats (attention limitée, limites à
> l'arbitrage) → le cours **dérive** dans le sens de la surprise sur 1-60 jours.

## Implémentation
- `packages/research/pead.py::pead_signal(bars, earnings_dates, t, drift_window)` — rendement
  cumulé depuis la dernière annonce si elle est récente. Point-in-time.
- Dates d'earnings : yfinance (à fournir au signal). Idéalement combiner avec la **surprise** (SUE).

## Résultats
- **À backtester** (DSR/PBO null). Facteur encombré → l'edge résiduel est probablement mince net de coûts.

## Verdict
HYPOTHÈSE — gate DSR>0.5 & PBO<0.5. Bon candidat à **combiner** (orthogonal au momentum prix).

## Liens
- Complémentaire de [[insider_form4]] (deux signaux d'information distincts).
