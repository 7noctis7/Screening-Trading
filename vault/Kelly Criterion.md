---
title: Kelly Criterion
type: concept
tags:
  - concept/probabilites
  - concept/risque
livres:
  - "[[Systematic Trading]]"
---

# Kelly Criterion

The bet size that maximises the long-run growth rate of capital — the geometric, not arithmetic,
mean of returns.

## Mechanism

Betting to maximise *average* return is wrong because returns compound. Make +100% on average per trade by losing 90% and then making 190%, and you hold 29% of what you started with. Kelly finds the fraction that maximises compounded growth; for a trading system it collapses to a remarkably simple form:

```
optimal percentage volatility target = expected Sharpe ratio
```

SR 0.5 → 50% volatility target. SR 1.0 → 100%.

## Half-Kelly

Full Kelly is correct and unusable. Even with a *correct* Sharpe estimate it implies a 10% chance
of halving your capital over ten years at SR 0.5 — and Sharpe estimates are never correct, always
biased upwards by [[Over-fitting]]. The practical rule is to halve the optimum, and to halve it
again for negative [[Skew]], where the penalty for overbetting is steepest.

## The trap

Kelly is dangerous in the hands of the overconfident precisely because it *rewards* an inflated
Sharpe ratio with a larger bet. Believe a back-tested SR of 2.0 and Kelly appears to authorise a
200% volatility target and 400% annual returns. Overbet relative to your true edge and the growth
rate turns negative — you lose not despite having an edge but because of how much you bet on it.

## When it fails

Whenever the input is an estimate rather than a known quantity, which is always in markets. Kelly
assumes you know your edge; the whole difficulty of trading is that you do not.

## Selon [[Systematic Trading]]

Carver applies a pessimism factor to the back-test *first* (×0.75 for out-of-sample bootstrapping),
then takes Half-Kelly, then rounds down. Ed Thorp, quoted: *"most cautious investors who use Kelly
find the frequency of substantial bankroll reductions to be uncomfortably large."*
