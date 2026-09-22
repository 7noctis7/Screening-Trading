---
title: Volatility Target
type: concept
tags:
  - concept/risque
  - concept/trading
livres:
  - "[[Systematic Trading]]"
---

# Volatility Target

A single number expressing how much risk a portfolio is meant to run: the long-run expected
annualised standard deviation of its returns, as a percentage of capital.

## Mechanism

```
annualised cash volatility target = trading capital × percentage volatility target
daily cash volatility target      = annualised ÷ 16          (√256 business days)
```

Position sizes are then whatever delivers that expected variation, given each instrument's
volatility. The percentage is fixed; the cash amount follows capital up **and down** daily.

## How to set it

Not by preference — by arithmetic. Half of a pessimistically estimated Sharpe ratio (see
[[Kelly Criterion]]), halved again for negative [[Skew]], and never above 50%. Then check the
implied losses and confirm you can actually live with them: at a 50% target on $100,000, a $32,000
monthly loss once a decade and a 10% chance of halving your capital over ten years.

## Why it's the key decision

It is the variable that determines whether you survive long enough for your edge, if any, to appear.
Most amateurs lose money not because their forecasts are worthless but because their positions are
too large for their account — and large losses are what make people abandon systems.

## When it fails

- When the Sharpe ratio it was derived from was over-fitted. Betting the Kelly optimum for an SR
  you don't have is the fastest route to ruin.
- When leverage required to reach it is absurd. If hitting the target needs 50× leverage on a
  pegged currency, the target is not achievable, it is merely postponed.
- When you change it. Revising the target because the system is doing badly is meddling with extra
  steps; if it must change, change it once and downwards.

## Selon [[Systematic Trading]]

*"Deciding your overall trading risk is the most important decision you will have to make when
designing your trading system."* Carver's own 45-instrument system, back-tested at SR 1.0, is run
at 25%.
