---
title: Diversification Multiplier
type: concept
tags:
  - concept/portefeuille
  - concept/risque
livres:
  - "[[Systematic Trading]]"
---

# Diversification Multiplier

The factor by which a diversified portfolio must be scaled **up** to hit its intended risk, because
combining imperfectly correlated components mechanically reduces volatility below that of the
components themselves.

## Mechanism

Two assets, each 10% volatility, equally weighted: at correlation 1.0 the portfolio is 10%; at 0.5
it is 8.66%; at 0.0 it is 7.07%. The multiplier restores the target:

```
multiplier = target volatility ÷ natural portfolio volatility
           = 10 ÷ 8.66 = 1.15   (corr 0.5)
           = 10 ÷ 7.07 = 1.44   (corr 0.0)
```

Approximate values by number of components and average correlation:

| n | 0.0 | 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| 2 | 1.41 | 1.27 | 1.15 | 1.10 | 1.0 |
| 5 | 2.2 | 1.58 | 1.29 | 1.15 | 1.0 |
| 20 | 4.5 | 1.86 | 1.38 | 1.18 | 1.0 |
| 50+ | 7.1 | 1.94 | 1.40 | 1.19 | 1.0 |

## Where it applies

Twice, at two different levels: when averaging several rule forecasts into one (otherwise the
combined forecast is smaller than the ±20 scale the system assumes), and when combining
volatility-standardised subsystems into a portfolio. It is also a measure of the number of
independent bets — see [[Law of Active Management]].

## The two safety rules

- **Floor correlations at zero.** Negative correlations produce arbitrarily large multipliers.
- **Cap the multiplier at 2.5**, whatever the estimate says. A high multiplier means the combined
  forecast sits permanently at its cap (degenerating to binary all-in/all-out), and it assumes a
  diversification that evaporates exactly when it is needed: *in a crisis, correlations jump.*

## Selon [[Systematic Trading]]

For a discretionary trader the whole calculation reduces to `maximum bets ÷ average bets` — a
deliberately conservative formula that assumes all open bets are perfectly correlated.
