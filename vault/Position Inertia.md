---
title: Position Inertia
type: concept
tags:
  - concept/couts
  - concept/trading
livres:
  - "[[Systematic Trading]]"
---

# Position Inertia

A deadband on rebalancing: **do not trade unless the target position is more than 10% away from the
current one.**

## The problem

A continuously recalculated target position drifts constantly. Rounding it turns a drift of 0.04
contracts into a buy, then a sell, then a buy — paying commission and crossing the spread each time
for an economically meaningless adjustment.

## Mechanism

Compare the unrounded target with the *current* position, not with the previous target. Holding 133
contracts, a target moving to 133.52 (134 rounded) triggers nothing; the target must reach 147
before a trade is generated.

## Why it's nearly free

Costs fall significantly; pre-cost performance is essentially unaffected, because the trades
suppressed were not carrying information. This is one of the rare adjustments with no trade-off —
*"there is no downside to using it"* — provided holding periods are longer than a few days. For
very fast systems, use a smaller threshold or none.

## Generalisation

The same idea, applied to inputs rather than positions: don't update a volatility estimate on an
existing position unless it has moved more than 25%. Any input that feeds a position size can be
given a deadband, and each one removes turnover that was never going to earn its
[[Standardised Trading Cost]].
