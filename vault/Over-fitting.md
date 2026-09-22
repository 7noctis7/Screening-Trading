---
title: Over-fitting
type: concept
tags:
  - concept/statistiques
  - concept/trading
livres:
  - "[[Systematic Trading]]"
---

# Over-fitting

Selecting rules or parameters that fit past data too closely, producing a back-test that looks
excellent and a live system that doesn't work. The dominant failure mode of systematic trading, and
the reason most published trading systems are worthless.

## Why it's so hard to avoid

Not carelessness — statistics. The amount of data needed to establish anything about a trading rule
is far beyond what markets provide:

| True Sharpe ratio | 0.2 | 0.3 | 0.4 | 0.5 | 0.7 | 1.0 | 1.5 | 2.0 |
|---|---|---|---|---|---|---|---|---|
| Years to prove it's profitable | 45 | 37 | 33 | 20 | 10 | 6 | 3 | 1.4 |

A realistic single-instrument rule (SR ~0.3) needs **nearly forty years** to prove it makes money
at all. Proving one rule beats another is worse: an SR advantage of 0.25 between uncorrelated rules
needs ~45 years.

## The multiple testing problem

Test enough worthless rules and some will look excellent by chance. From a pool of 100 rules whose
true expected return is zero, an SR 0.5 cutoff admits **30**; even an SR 2.0 cutoff admits 2.3. The
threshold needed to keep false positives at 5% (SR 2.8 with one year and ten rules) is far above
what a genuinely good rule produces (~0.3). **The bar cannot be set both safely and usefully.**

## Defences, in order of effectiveness

1. **Don't select on performance at all.** Choose rules on behaviour — speed, correlation, cost —
   and let portfolio weights down-weight the weak ones. Selection is demonstrably worse than
   randomness: 90 variations on gold futures gave SR 0.07 picking last year's best, 0.20 picking at
   random, **0.33 using all 90 equally weighted**.
2. **Test few things.** Fewer candidates, lower required threshold.
3. **Never fit in-sample.** Use an expanding (anchored) window — fit only on the past, waste
   nothing. A rolling window adapts to structural change but rarely leaves enough history.
4. **Pool across instruments.** Two rules with single-instrument SRs of 0.05 and 0.30 need 45 years
   to tell apart; run on a portfolio they become 0.13 and 1.13 — **11 years**.
5. **Discount whatever survives.** Apply a pessimism factor (25% of an in-sample single-period
   optimisation, 75% of an out-of-sample bootstrap) before using the number for anything, above all
   before feeding it to the [[Kelly Criterion]].

## The implicit form

Even a disciplined researcher testing "ideas first" tends to test ideas they already know worked —
market lore, published anomalies. This is over-fitting through the literature, and no amount of
out-of-sample rigour removes it. Expect your back-tested Sharpe to be overstated anyway.
