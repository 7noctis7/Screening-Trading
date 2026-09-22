---
title: Skew
type: concept
tags:
  - concept/probabilites
  - concept/risque
livres:
  - "[[Systematic Trading]]"
---

# Skew

The asymmetry of a return distribution — whether the rare large moves fall on the gain side or the
loss side. The most overlooked characteristic of any strategy, and invisible in the Sharpe ratio.

## The two regimes

| | Positive skew | Negative skew |
|---|---|---|
| Pattern | Frequent small losses, rare large gains | Frequent small gains, rare large losses |
| Analogy | **Buying** insurance | **Selling** insurance |
| Examples | Trend following, long options, tail hedges | FX carry, relative value, market making, short straddles |
| Risk management | Easier — losses are small and continuous | Harder — the loss arrives all at once |
| Leverage | Less needed | Usually required to look attractive, which is what kills it |
| Difficulty | Psychological: mostly underwater | Epistemic: looks excellent until it doesn't |

## The diagnostic

**High hit rate plus steady profits plus few losers = probably short insurance, pre-claim.** Two
assets with an identical Sharpe ratio of 1.0 can differ as follows: the negative-skew one wins on
59% of days with a worst expected daily loss of -22%; the positive-skew one wins on 46% of days with
a worst daily loss of -10%.

## Why it's paid

Negative skew earns a genuine risk premium — people dislike rare catastrophes enough to pay to
avoid them, and overpay for lottery-like payoffs on the other side. It is not a mistake to sell
insurance. It is a mistake to sell it with leverage, at a size calibrated to the quiet period, and
to mistake the resulting Sharpe ratio for skill.

## Practical consequences

- Halve your [[Volatility Target]] for a negative-skew system.
- Sharpe ratios of negative- and positive-skew strategies are not comparable.
- A positive-skew *rule* applied to a negative-skew *instrument* partly offsets it.
- Very high Sharpe ratios are often hidden negative skew: LTCM's was ~4.6.

## Selon [[Systematic Trading]]

Carver runs about a third of his own system in negative-skew strategies deliberately, arguing for a
balance of styles that work in different environments — not for avoidance.
