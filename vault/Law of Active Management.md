---
title: Law of Active Management
type: concept
tags:
  - concept/portefeuille
  - concept/trading
livres:
  - "[[Systematic Trading]]"
---

# Law of Active Management

Richard Kahn, 1989: the Sharpe ratio of a strategy is proportional to the **square root of the
number of independent bets** made per year.

```
SR ∝ √(independent bets per year)
```

## The two readings

**Speed.** Bet once a year at SR 0.15, four times a year and you'd expect 0.30, every business day
and 2.4. This is the seductive reading, and it is where overtrading comes from.

**Breadth.** Four *uncorrelated* assets double your Sharpe ratio. A portfolio spanning several
asset classes reaches two to three times the Sharpe ratio of a single instrument. This is the
reading that actually pays, because the bets really are independent.

## Why the speed reading fails

- It ignores transaction costs entirely — and costs scale linearly with turnover while returns scale
  with its square root. See [[Standardised Trading Cost]].
- It assumes skill is constant across horizons. Rules have a "sweet spot": most assets show
  momentum over weeks to months and behave differently at shorter and longer horizons.
- The independence is usually imaginary; consecutive bets from the same rule are not independent.

## The practical corollary

**Diversify across instruments, not across rules.** The average correlation between two different
rules trading the same instrument is *higher* than between the same rule trading two different
instruments. Adding an instrument buys more independence than adding a rule — which is unfortunate,
since inventing rules is more fun than cleaning data.

## Selon [[Systematic Trading]]

The law underwrites the book's entire preference ordering: [[Handcrafting]] over optimisation,
breadth over cleverness, and *"finding the best trading rules is less important than designing your
trading system in the correct way."*
