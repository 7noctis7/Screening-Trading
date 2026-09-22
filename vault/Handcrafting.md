---
title: Handcrafting
type: concept
tags:
  - concept/portefeuille
  - concept/optimisation
livres:
  - "[[Systematic Trading]]"
---

# Handcrafting

A pencil-and-paper method for setting portfolio weights, built to reproduce what bootstrapped
optimisation would give without running an optimiser — and without the extreme, unstable weights
that classical mean-variance produces.

## The problem it solves

Markowitz optimisation treats noisy estimates as certainties. Fed fifteen years of data on NASDAQ,
the S&P 500 and a long bond, it puts everything into NASDAQ at the top of the tech boom, expels it
permanently after the crash, then sits at 100% bonds. Asked to defend such portfolios, quants say
*"these are what the optimiser came up with."* The underlying failure: Sharpe ratios are usually
statistically indistinguishable while correlations are clearly distinguishable, and the optimiser
cannot tell the difference.

## The method

1. Group correlated assets bottom-up (by sector, country, asset class — the grouping is usually
   obvious). Keep groups to one, two or three members.
2. Read the within-group weights off a lookup table: one asset → 100%; two assets → 50/50 whatever
   the correlation; identical correlations → equal weights; three assets → a table of seven
   correlation patterns (e.g. 0.0/0.5/0.0 → 30/40/30; 0.9/0.5/0.9 → 42/16/42).
3. Allocate across groups the same way, and multiply the weights through the levels.
4. Optionally adjust for Sharpe ratio — but **only** where the difference is genuinely known
   (costs) or backed by 10+ years of data. Below ten years, no adjustment at all.

Round correlations to the nearest tabulated value; floor negative correlations at zero.

## Why it works

The weights encode the only information that is statistically reliable — the correlation structure
— and deliberately ignore the information that isn't. It is reproducible: the same data gives the
same answer regardless of who operates it, which is not true of an expert quietly torturing an
optimiser until it produces something plausible.

## When it fails

It is an in-sample method: you use knowledge of the whole history to group and weight. Carver's
defence — correlations move slowly and the weights aren't extreme, so the damage is small — sits
awkwardly beside the well-known fact that correlations jump in a crisis. Apply a pessimism factor
to any back-test built on it.

## Selon [[Systematic Trading]]

Validated against the alternatives on one system: in-sample handcrafting SR 0.54, out-of-sample
bootstrapping 0.52, in-sample single-period optimisation a fantasy 0.84 that collapsed to 0.3 out
of sample.
