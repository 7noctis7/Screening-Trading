---
title: Volatility Standardisation
type: concept
tags:
  - concept/risque
  - concept/trading
livres:
  - "[[Systematic Trading]]"
---

# Volatility Standardisation

Rescaling every quantity in a system by the instrument's expected standard deviation of returns, so
that unlike things become comparable and interchangeable.

## Mechanism

Divide by (or express relative to) a recent estimate of daily return volatility — typically a 25-day
moving average or a 36-day EWMA of daily returns. A raw signal in price points becomes a signal in
risk units; a position in contracts becomes a position carrying a known amount of risk.

## Why it matters

Three things become possible at once, and none of them is possible without it:

- **One rule, many instruments.** A forecast of +10 means the same thing on a 2-year Schatz future
  (2% annual volatility) and on crude oil (30%), so the same rule can be applied to both — and its
  history can be pooled across both when fitting, which is the only realistic route to statistical
  significance. See [[Over-fitting]].
- **Rules can be combined.** Forecasts on a common scale can be averaged. See
  [[Diversification Multiplier]].
- **Risk stays where you put it.** Every component contributes equal risk by construction, and the
  portfolio adapts as volatility changes rather than drifting.

## When it fails

When the volatility estimate is a lie. Low measured volatility produces large positions, and the
instruments with the lowest measured volatility are often those whose risk is being artificially
suppressed — currency pegs, front-month rates under ZIRP, credit derivatives before a repricing.
Calm ends abruptly and the position was sized for the calm. The defence is not a better estimator
but exclusion: don't trade instruments whose volatility is extremely low.

## Selon [[Systematic Trading]]

Carver calls it *"my favourite technique"* and *"one of the most powerful techniques I use"*. It is
the substrate for the scaled forecast (average absolute value 10, capped at ±20), for
[[Handcrafting]], and for [[Standardised Trading Cost]].
