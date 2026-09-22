---
title: Standardised Trading Cost
type: concept
tags:
  - concept/couts
  - concept/trading
livres:
  - "[[Systematic Trading]]"
---

# Standardised Trading Cost

Trading cost expressed in **Sharpe ratio units surrendered per round trip**, so that costs across
instruments, currencies and volatilities become directly comparable — and so that "how fast should
I trade?" becomes a division rather than a temperament.

## Mechanism

```
standardised cost = (2 × cost to trade one block) ÷ (16 × instrument currency volatility)
annual cost in SR = standardised cost × turnover (round trips per year)
```

Cost per block includes half the bid-offer spread, per-ticket fees, per-unit fees and percentage
taxes. The 2 is the round trip; the 16 annualises the daily volatility.

## Why volatility-adjust

Because €5 to trade a Schatz future is not cheaper than €8 for a Euro Stoxx future if you need 20
Schatz to carry the same risk as 10 Euro Stoxx. The corollary matters more than the arithmetic:
**low-volatility instruments are expensive**, which is one more reason to exclude them. See
[[Volatility Standardisation]].

## The speed limit

Never spend more than **a third** of a conservative pre-cost Sharpe ratio on costs. That gives a
budget — 0.13 SR/year for a diversified systematic system assuming SR 0.40, 0.08 SR for a
discretionary trader or static allocator assuming 0.25 — and dividing the budget by an instrument's
standardised cost gives its **maximum turnover**.

Indicative costs (2014-15, recompute before use): cheapest futures ~0.001 SR, average future
~0.002-0.005, index spread bet ~0.01, ETF ~0.08.

## What it rules out

Day trading, arithmetically. Two round trips a day is ≥500 turnover, demanding a standardised cost
of 0.00025 SR — a quarter of what the cheapest futures achieve, of which a quarter is irreducible
commission. You would need **zero execution cost**: consistently trading at mid or better. Not
impossible, but a capability, not an assumption.

## The asymmetry that makes it powerful

Costs are predictable; pre-cost returns are not. So fitting on cost is legitimate where fitting on
performance is not — reject a rule variation because it is too expensive, never because it earned
less. See [[Over-fitting]].
