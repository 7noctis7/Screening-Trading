---
title: Systematic Trading
aliases:
  - Carver - Systematic Trading
sous_titre: A unique new method for designing trading and investing systems
auteur: Robert Carver
annee: 2015
editeur: Harriman House
isbn: 978-0857194459
langue: en
nb_pages: 308
type: technique
source: pdf
tags:
  - livre/technique/trading
  - livre/technique/finance
domaines:
  - trading systematique
  - gestion du risque
  - allocation de portefeuille
concepts_cles:
  - "[[Volatility Standardisation]]"
  - "[[Volatility Target]]"
  - "[[Kelly Criterion]]"
  - "[[Skew]]"
  - "[[Handcrafting]]"
  - "[[Diversification Multiplier]]"
  - "[[Law of Active Management]]"
  - "[[Standardised Trading Cost]]"
  - "[[Position Inertia]]"
  - "[[Over-fitting]]"
livres_lies: []
---

# Systematic Trading

Robert Carver — Harriman House, 2015 — [[Systematic Trading.pdf]]

> [!abstract] Pitch
> A former AHL portfolio manager argues that success in systematic trading comes almost
> entirely from avoiding a handful of well-understood errors — over-fitting, overtrading and
> over-betting — rather than from finding better trading rules. He supplies a modular framework
> that converts any forecast, systematic or discretionary, into correctly sized positions, and
> he quantifies every rule of thumb he offers.

## Synthèse

Carver's premise is that the trading rule is the least important part of a trading system. The
books and websites that sell systems get the ratio exactly backwards: they specify entry and exit
signals in obsessive detail, then wave at position sizing with an arbitrary "risk 3% of capital per
trade" and a stop loss calibrated to the reader's pain threshold. Carver's answer is a **modular
framework** — a pipeline in which each component is independently specified, independently
replaceable, and made of arithmetic simple enough for a spreadsheet:

```
forecasts → combined forecast → volatility target → position size → portfolio → trades
```

Two conventions hold it together. The first is **volatility standardisation**: every quantity in
the system is expressed relative to an instrument's expected volatility, so that the same rule can
be applied to a Schatz future and a crude oil contract, data can be pooled across instruments when
fitting, and every component contributes equal risk. The second is the **scaled forecast**: a
prediction is not "buy or sell" but a number proportional to the expected Sharpe ratio, scaled to
an average absolute value of 10 and capped at ±20. Because +10 means the same thing everywhere,
the same framework serves a systematic trader with 30 rule variations, a discretionary trader
converting a gut feeling into a number, and an asset allocator who refuses to forecast at all and
simply holds +10 forever (which turns out to be continuously rebalanced risk parity).

What makes the book unusual is that Carver quantifies the things other authors assert. How much
history do you need to prove a trading rule works? For a realistic Sharpe ratio of 0.3, **nearly
forty years**. To prove one rule beats another? Thirty years, unless they are both highly
correlated and wildly different in performance. What Sharpe ratio should you expect? 0.15 from a
single equity, 0.40 from a diversified multi-asset portfolio, 1.0 as an absolute ceiling that no
systematic hedge fund in a large sample sustained for more than a few years. What risk should you
run? Half-Kelly on a *pessimistically degraded* back-test Sharpe ratio — which for Carver's own
45-instrument system means 25%, not the 100% that full Kelly on a back-tested SR of 1.0 would
authorise. And what does the popular advice actually imply? A widely sold system holding positions
for a week with 10% of capital per trade is running a **160% volatility target** and needs 83% a
year before costs simply to break even.

The final third is the most operationally valuable: a cost model that makes speed decisions
arithmetic rather than temperamental. Costs are expressed in **Sharpe ratio units surrendered per
round trip**, turnover in round trips per year, and the product must never exceed a third of a
conservative pre-cost Sharpe ratio. From that single constraint, day trading falls out as
arithmetically impossible for anyone who cannot consistently trade at mid or better, expensive
instruments are shown to require slow rules rather than exclusion, and the whole question of "how
fast should I trade?" becomes a division.

The book closes with three complete worked systems — a discretionary trader on spread bets, a
pension fund on ETFs, a futures trader on $250,000 — each carried through every calculation, with
trading diaries in which the author's own discretionary instincts are repeatedly overruled by his
framework, to his benefit.

## Plan d'action

**Before designing anything — set the constraints**

- [ ] Compute your **realistic** Sharpe ratio, not your back-tested one: apply the pessimism factor
      for your fitting method (in-sample single-period 25%, out-of-sample bootstrap 75%, in-sample
      handcrafting 70%), and cap the result at 1.0 (0.5 discretionary, 0.4 static) — Ch.4, Ch.2
- [ ] Set the percentage volatility target = **half** that Sharpe ratio; halve it again for a
      negative-skew system. Never exceed 50% — Ch.9
- [ ] Write down what that target means in money using the loss tables, and confirm you can live
      with it before trading a single contract — Ch.9
- [ ] Fix the maximum annual cost budget: **0.13 SR** if systematic, **0.08 SR** if discretionary
      or static — Ch.12

**Instrument selection**

- [ ] Exclude anything without reliable daily price data — Ch.6
- [ ] Exclude very low volatility instruments (pegged currencies, short-maturity bonds, front
      Eurodollar under ZIRP): they need absurd leverage, cost more per unit of risk, and their calm
      ends abruptly — Ch.6, Ch.10
- [ ] Compute each candidate's standardised cost `(2 × cost per block) ÷ (16 × instrument currency
      volatility)` and reject anything above `cost budget ÷ your minimum achievable turnover` — Ch.12
- [ ] Compute the maximum possible position `2 × volatility scalar × instrument weight ×
      diversification multiplier`; **act if it is below 4 blocks**, and never include an instrument
      below 1 — Ch.12
- [ ] Prefer exchange over OTC; prefer the cheapest access route that clears the minimum-size test — Ch.6
- [ ] Hold the most diversified portfolio that satisfies the four-block rule, one instrument per
      asset class first — Ch.12

**Trading rules**

- [ ] Start with **two** rules of opposite skew: EWMAC (trend, positive skew) and carry (negative
      skew). They account for ~85% of the back-tested performance of Carver's full system — Ch.7
- [ ] Keep at least three EWMAC variations; use the fixed 1:4 fast/slow ratio (16:64, 32:128,
      64:256) and the published forecast scalars — Appendix B
- [ ] Select variations on **behaviour only** — speed and correlation — never on performance:
      drop either of any pair correlated above 95%, drop anything held longer than a few months,
      drop anything whose turnover breaches the cost budget — Ch.3, Ch.12
- [ ] Rescale any imported rule: make it continuous, volatility-standardise it, recalculate it
      daily independent of your position, and multiply by `10 ÷ its natural average absolute
      forecast` — Ch.7
- [ ] Cap every forecast at ±20, before and after combining — Ch.7, Ch.8

**Fitting and weights**

- [ ] Never fit in-sample. Use an expanding (anchored) window; use a rolling one only if you have
      the decades to spare — Ch.3
- [ ] Pool data across instruments rather than fitting each one separately — Ch.3
- [ ] Set forecast and instrument weights by **handcrafting**: group correlated assets, read the
      weights off the lookup table, multiply through the levels — Ch.4
- [ ] Adjust weights for Sharpe ratio **only** when you genuinely know the difference (costs) or
      have more than ten years of data. Under ten years, do not adjust at all — Ch.4
- [ ] Make no instrument-weight adjustment for cost differences: post-cost returns do not
      reliably differ once the speed limit is respected — Ch.12
- [ ] Apply the forecast and instrument diversification multipliers, floor correlations at zero,
      and **cap both multipliers at 2.5** — Ch.8, Ch.11

**Running the system**

- [ ] Estimate price volatility with a 25-day moving average (or 36-day EWMA); slow it to 20 weeks
      only if the cost saving is material, which it is only for very slow systems — Ch.10, Ch.12
- [ ] Recompute trading capital daily (hourly if automated above a 15% target, weekly at minimum if
      leveraged) and let the cash volatility target follow it up **and** down — Ch.9
- [ ] Round to whole blocks **only at the final step** — Ch.10, Ch.11
- [ ] Apply **position inertia**: do not trade unless the target is more than 10% away — Ch.11
- [ ] Never change the percentage volatility target; if you must, change it once and downwards — Ch.9
- [ ] If discretionary: never revise a forecast on an open position, exit only on the trailing stop
      (X × daily price volatility, X = 4 for spread bets), no profit targets, no more than 40
      forecast units on one instrument, and stop opening bets at the maximum — Ch.13

**Permanent warning signs**

- [ ] Steady gains, high hit rate, few losses → you are probably short insurance and haven't paid
      the claim yet. Halve the risk — Ch.2, Ch.9
- [ ] A back-tested Sharpe ratio above 1.0 on a single instrument → over-fitting, hidden negative
      skew, or both — Ch.2
- [ ] A forecast that is large because volatility is *low* rather than because the return is high
      → exactly when the cap earns its keep — Ch.7
- [ ] Wanting to intervene → the intervention is the risk. *"Don't be tempted to meddle, improve or
      risk manage."* — Epilogue

## Résumé détaillé

### Introduction (p. 1-7)

**Core idea.** Two stories from Carver's career — a Barclays trade in January 2009 and AHL's
billion-dollar day in September 2008 — make the same point: the trading system kept working
precisely when the humans running it were too frightened to act.

- Less than 10% of actively managed global assets is fully systematically traded, but the
  conditions have never been better: free price data, cheap execution, ETFs covering every
  index, brokers with APIs, and a Raspberry Pi able to run a serious strategy.
- Passive indexing is itself a (very simple) systematic strategy. Alternative beta — the value
  premium, for instance — needs no skill, only rules, and is still sold expensively in fund form.
- The car-dealership analogy sets up the book's thesis: published trading systems are
  **non-modular** (one model, one colour, one speed) and cannot be adapted, questioned or
  retuned. Carver's answer is a framework of interchangeable components.
- The danger is quantified rather than asserted: a real spread-betting system recommending
  5% of capital per trade at weekly turnover would need **83% a year just to break even**, and
  **339% pre-cost** to avoid a high chance of ruin (p. 6).

> "Success in systematic trading is mostly down to avoiding common mistakes such as over
> complicating your system, being too optimistic about likely returns, taking excessive risks,
> and trading too often." (p. 6-7)

### Ch.1 — The Flawed Human Brain (p. 11-23)

**Core idea.** Human brains are excellent at complex analysis and terrible at financial
decisions; systematic trading is a commitment mechanism against our own cognitive biases,
and simultaneously a way to harvest the biases of everyone still trading discretionarily.

- **Prospect theory** explains the disposition effect — "get-evenitis" (Shefrin): we refuse to
  crystallise losses because an unrealised loss does not feel real, and we snatch small profits
  to minimise regret and confirm the original decision was right.
- Carver tests this rather than asserting it. An "early profit taker" rule (take profit at 5,
  stop at 20) versus an "early loss taker" (take profit at 20, stop at 5): across 31 futures
  contracts **the early loss taker beat the early profit taker in 27** (p. 15). The rule that
  mimics our instincts loses.
- **Addictive-gambling parallel.** The three features of the most addictive games — illusion of
  control, near misses, speed and continuity — map onto active trading, and especially onto day
  trading. Systematic investing removes the feeling of control, which is exactly why people
  find it hard to do.
- **Meddling** is Carver's term for the internal monologue that overrides the system, and it is
  driven by overconfidence: we really are cleverer and better informed than the system — but
  biases mean we still decide worse.
- The commitment mechanism (Odysseus and the mast; Niederhoffer locking himself in a racquetball
  court and instructing Susan to ignore his pleas) requires the system to be **objective**: a
  rule vague enough to reinterpret ("sell for small losses") will be reinterpreted at the first
  loss. Objectivity also enables back-testing, and is the precondition for automation.
- Automation aids commitment but does not create it. Every good automated system has an
  emergency override, and if you do not trust the rules there will be frequent "emergencies":
  *"A system which is fully automated but not completely trusted is potentially lethal."* (p. 19)
- **The three design pitfalls that organise the rest of the book:** over-fitting (narrative
  fallacy — seeing patterns that are not there), overtrading (illusory superiority — costs you
  will not overcome), and over-betting (unbounded confidence meeting easy leverage).

**Key numbers.**
- Annualisation: volatility scales with the square root of time — ~256 business days a year, so
  **daily σ × 16 = annual σ**; average returns scale linearly (× 256). (p. 21)
- Reference volatilities: equities ~20% annualised, 2-year bond ~1.5%, 10-year bond ~8%. (p. 21)
- A 200% annualised σ system (the leverage some brokers permit) means a 12.5% daily σ: losses
  above 24.2% every couple of months, and a 37.2% one-day loss roughly every three years (p. 23).
  And the normal distribution *understates* the tails — the Dow fell more than 4σ about 30 times
  between 1914 and 2014, against a theoretical once a century.

> "Humans are better than computers at complex intellectual tasks. But... our emotions prevent
> us from fully utilising this intelligence." (p. 3)

### Ch.2 — Systematic Trading Rules (p. 25-48)

**Core idea.** A trading rule is only trustworthy when you can say *why* it made money;
the chapter builds a taxonomy of return sources, trading styles and — crucially — the Sharpe
ratios you may realistically expect, which is the antidote to over-betting and overtrading.

- **Ideas first vs data first.** Ideas first: form a hypothesis, build a rule, test it. Data
  first (data mining): find profitable patterns, then build rules. Carver favours ideas first —
  simpler, intuitive, explainable, less fitting — while conceding data first controls the degree
  of fitting *explicitly* and may find genuinely novel patterns (and suits high-frequency work,
  where data is plentiful). He quotes Leda Braga of Systematica: *"We don't mine the data to
  come up with ideas."* (p. 26)
- **Four marks of a good rule** (p. 26-29): built from ideas or data deliberately; explainable
  profits; intuitively understandable behaviour; as simple as possible; and systematisable —
  which excludes both the irreducibly subjective (candlestick patterns, merger arbitrage) and
  the data-starved (Twitter sentiment: "good press releases", not enough history to evaluate).
- **Why back-tested rules fail** (p. 29-30): it never really worked (over-fitting, forward-looking
  data, survivorship bias, underestimated costs, too-short history missing the blow-up — the
  "Peso problem"); or the world changed (crowding kills relative value; trend followers instead
  reinforce each other until the synchronised rush for the exit).

**Where returns actually come from** (p. 30-37) — the most reusable part of the chapter:

| Source | Mechanism |
|---|---|
| Persistent risk premia | Equity over bonds, term premium, value/size factors |
| Time-varying risk premia | Risk appetite swings (2006 euphoria → 2009 panic); a mean-reversion trade |
| Skew premium | Payment for accepting rare large losses; also our overpayment for lottery-like payoffs |
| Leverage constraints | Investors who can't borrow bid up high-return/high-risk assets, leaving high-SR/low-vol assets cheap |
| Liquidity and size | Illiquidity and smallness pay, because big institutions need to exit fast |
| Forced traders | Central banks defending a peg, year-end tax and window dressing, insurers buying long bonds to hedge |
| Barriers to entry | Co-located servers, due diligence — compensation for effort and capital, *not* skill |
| Behavioural effects | Prospect theory biases, exploitable because of shorting bans and the weight of biased money |
| Self-fulfilling prophecy | Fibonacci and friends: unjustified, but widely watched |
| Pure alpha | Buffett, Templeton, Lynch — real but probably not reducible to rules |

- **Skew is the most overlooked characteristic of a strategy** (p. 32-34, 40-41). Positive skew =
  buying insurance: frequent small losses, rare large gains, easier risk management, less leverage
  needed (trend following, long options, tail-protection funds). Negative skew = selling insurance:
  frequent small gains, rare catastrophic losses, needs leverage to look attractive, "so gets killed
  in bad times" (FX carry, LTCM-style fixed-income relative value, market making, short straddles —
  Leeson's $1bn). **Warning sign:** *"If you are making steady profits nearly every day, and most of
  your trades are winners, then there is a good chance you are engaged in negative skew trading.
  It's just that you haven't yet seen any rare large losses."* (p. 40)
  Carver's illustration (p. 34) makes the trap concrete — two assets, *identical* SR of 1.0:

| | Negative skew | Positive skew |
|---|---|---|
| Hit rate (% positive days) | **59%** | 46% |
| Average gain : average loss | 0.8 | 1.4 |
| Expected annual worst daily loss | **-22%** | -10% |
| Expected annual best daily gain | 10% | 22% |

  The negative-skew asset wins more often and feels better to trade, while carrying twice the
  worst-day loss.

- **Static strategies come in four degrees** (p. 38-39): buy and hold → rebalance to equal cash →
  equal risk (risk parity) → constant expected risk allocation. The asset allocating investor runs
  the fourth degree: no trading rules, but the framework keeps portfolio risk where it was intended.
- **Volatility standardisation** is named as the single most powerful technique in the framework
  (p. 40): rescale every asset's returns to the same expected risk, and you can then apply the same
  rule across instruments, combine rules, and give every component an equal risk contribution.
- **Law of active management** (Kahn, 1989, p. 42): SR ∝ √(independent bets per year). Hence
  diversification, not rule selection, is the main lever — four zero-correlation assets double your
  SR; a multi-asset-class portfolio reaches 2-3× a single asset. Its two flaws: skill is assumed
  constant across holding periods (rules have a "sweet spot"), and costs are ignored.
- **Leverage is not itself risk** (p. 44-45); the danger is leverage applied to something whose
  low measured volatility is an illusion. The Greek 4-year vs 5-year bond trade of 2007-2010 is the
  worked example: negligible volatility, heavy leverage, then correlation breakdown, margin calls
  and forced liquidation at the worst price — on a position that would have been profitable held to
  maturity.

**Realistic Sharpe ratios** (p. 46-47) — the numbers to hold onto:

| Strategy | Expected annualised SR |
|---|---|
| Single equity | 0.15 |
| 20+ equities, one country, diversified sectors (or an index) | 0.20 |
| Global multi-country equities | 0.25 |
| Multi-asset-class static portfolio | **0.40** (realistic maximum for static) |
| Diversified trading rules, single instrument | 0.40 |
| Diversified rules, multiple asset classes | ~0.80 |
| Competent semi-automatic (discretionary) trader, one instrument | 0.25 (≤0.50 if diversified) |

Back-tested SR of 2.0-3.0 on a single instrument are over-fitting artefacts: *"SR consistently
greater than 1.0 are rarely achieved, even by sophisticated institutional investors"* — no fund in
a large CTA sample sustained SR > 1.0 for more than a few years (p. 47).

- **The two false shortcuts to a higher SR.** (1) Hidden negative skew: a strategy returning
  +100%/+65% alternately for 20 years shows SR 4.6, then loses everything in year 21 — and *still*
  reports SR 1.7 afterwards. LTCM's SR was also ~4.6. (2) Trading faster: theoretically an SR of
  0.40 at one month becomes 1.8 daily and 5.2 hourly — until costs are deducted (p. 48):

| Holding period | Theoretical pre-cost SR | After cost, average future | After cost, average spread bet |
|---|---|---|---|
| 1 month | 0.40 | 0.37 | 0.28 |
| 1 week | 0.83 | 0.71 | 0.27 |
| 1 day | 1.8 | 1.2 | **-0.75** |
| Half a day | 2.6 | 1.4 | **-2.5** |
| 1 hour | 5.2 | 0.28 | **-16.4** |

- **Carver's own conclusion is not anti-negative-skew** — about a third of his system is in that
  category. The point is a balanced combination of styles that work in different environments, and
  *"finding the best trading rules is less important than designing your trading system in the
  correct way."* (p. 48)

### Ch.3 — Fitting (p. 51-68)

**Core idea.** Selecting rules on past performance is the central danger of systematic trading;
Carver's answer is not better fitting but *less* fitting — he chooses rules without ever looking
at their returns, and lets portfolio allocation down-weight the weak ones.

- **The 50-model kid.** A young quant at a prop firm proudly back-tested 50 profitable rules in
  a month with off-the-shelf software. Carver walked away from the deal; the firm was liquidated
  a few months later (p. 52).
- **The three fitting windows** (p. 54-57):
  - *In sample* — fit and test on the same ten years. "Efficient but dishonest": requires a time
    machine, produces spectacular back-tests and favours needlessly complex rules.
  - *Half out of sample* — fit on 1990-94, test 1995-2000. Honest but wastes half the data.
  - *Expanding window* (anchored fitting) — **Carver's preference**: each year, fit only on
    everything before it. Honest and wastes nothing.
  - *Rolling window* (walk-forward) — same, but discards data older than N years. Adapts to
    structural change, but rarely leaves enough history to be significant.
- **The demonstration that fitting loses** (p. 58). 90 variations of the early loss taker on CME
  gold futures, one-year rolling window:

| Method | Sharpe ratio |
|---|---|
| Pick last year's best variation | 0.07 |
| Pick a variation at random each January | 0.20 |
| **Keep all 90, equally weighted average of forecasts** | **0.33** |

  Selection is worse than randomness; using everything beats both. Three reasons: choosing one
  variation is overconfidence, one year of data decides nothing, and 90 candidates is far too many.

- **Multiple testing** (Table 3, p. 59): from a pool of rules with a *true* expected return of zero,
  even a demanding SR 2.0 cutoff still admits 1.2 rules out of 50 tested and 2.3 out of 100. At an
  SR 0.5 cutoff, a pool of 100 yields 30 accepted rules — all worthless.
- **Table 4 (p. 60):** the SR cutoff needed to hold the false-positive rate at 5%. With 1 year of
  data and 10 rules, you need SR 2.8; with 30 years and 10 rules, 0.6 — still above the ~0.3 that a
  genuinely good single-instrument rule delivers. **The bar cannot be set both safely and usefully.**
- **How much history to prove a rule works** (Table 5, p. 62, T-test at 2σ):

| True SR | 0.2 | 0.3 | 0.4 | 0.5 | 0.7 | 1.0 | 1.5 | 2.0 |
|---|---|---|---|---|---|---|---|---|
| Years to pass T-test | 45 | 37 | 33 | 20 | 10 | 6 | 3 | 1.4 |

  A realistic single-instrument rule (SR ~0.3) needs **nearly 40 years** of data to prove it makes
  money at all.
- **How much history to prove one rule beats another** (Table 6, p. 64): an SR advantage of 0.25
  between uncorrelated rules needs 45 years; 0.5 needs 37. Only the rare combination of *high
  correlation and large SR gap* is distinguishable quickly (0.95 correlation + 0.5 advantage: 3
  years). *"It's difficult to justify picking one rule over another on performance alone."* (p. 66)
- **Pool data across instruments** (p. 64-65). Fitting each instrument separately is the narrative
  fallacy in action — and the default in most back-testing packages. Pooling gives you the history
  you need: two of Carver's rules with single-instrument SR of 0.05 and 0.30 (45 years to tell
  apart) become 0.13 and 1.13 across a portfolio — **11 years to tell apart**. This is also why
  rules should be written generically, to work on any instrument.
- **Rules for effective fitting, if you insist** (p. 65-67): keep the method simple; test fewer
  alternatives; ban time machines; don't drop rules casually; pool across instruments; compare like
  with like (SR flatters negative skew); and beware benchmarking against 40 years of falling
  inflation, which will not repeat.

**Carver's own three-step process — the practical heart of the chapter** (p. 67):

1. A small number of trading rules, one or two per idea about market behaviour.
2. A few variations per rule, chosen on **behaviour** — trading speed, correlation — never on
   performance. Drop a variation if it correlates >95% with another, or if its costs are too high;
   never because it earned less.
3. Allocate forecast weights using returns data, accounting for uncertainty in Sharpe ratios. Weak
   rules get a small weight rather than exclusion; anything left with a negligible weight can be
   dropped from live trading afterwards.

> "Far too much time and effort is spent by both amateur and professional trading system designers
> in looking for more, and better, trading rules... The average correlation between different rules
> trading a particular instrument is higher than between instruments trading the same rule. So
> diversification amongst instruments is preferable to rule diversification." (p. 68)

Carver's own system runs eight rules across five themes; starting from scratch he would begin with
**two** — trend following and carry.

### Ch.4 — Portfolio Allocation (p. 69-90)

**Core idea.** Classic Markowitz optimisation produces extreme, unstable portfolios because it
treats noisy estimates as certainties. Carver replaces it with **handcrafting**: a pencil-and-paper
method, built from bootstrapping experiments, that anyone can reproduce identically.

- **Two things make allocation easier inside this framework** (p. 71): weights can never be
  negative (you cannot short a trading rule), and volatility standardisation gives every component
  the same expected standard deviation — so only **Sharpe ratios and correlations** matter.
- **The failure demonstrated** (p. 71-72). Single-period Markowitz on NASDAQ, S&P 500 and a US
  20-year bond, refitted annually on an expanding window: everything into NASDAQ at the top of the
  tech boom, NASDAQ permanently expelled after it implodes, then years of 100% bonds.
  *"These are what the optimiser came up with"* is the answer Carver kept getting from quants
  asked to defend such portfolios (p. 71).
- **Why it fails:** the optimiser sees only point estimates, not their uncertainty. In the example,
  the three assets' Sharpe ratios are statistically indistinguishable over 15 years — but their
  **correlations are clearly distinguishable**. The right response is to allocate on correlation
  (diversification) and largely ignore SR differences, which is exactly what the optimiser cannot do.
- **Equal weights are the right answer only when** all assets share the same volatility, the same
  Sharpe ratio and the same correlation (p. 73). Volatility standardisation gives you the first for
  free; insufficient data usually makes the second a fair assumption; the third is normally false,
  and that is the opening to beat 1/N.
- **Bootstrapping** (p. 75-76): run the optimisation many times over randomly drawn sub-periods and
  average the weights — *"the average of many optimisations, rather than one optimisation on the
  average of all data."* The justification: the past is a guide to the future, but you don't know
  *which* past will repeat. Noisy data self-corrects towards equal weights; genuine differences
  survive the averaging. Cost: real code or "a black belt in spread-sheeting".

**Handcrafting — the method to actually use** (p. 77-83). Group correlated assets bottom-up, assign
weights from a lookup table, then allocate across groups, multiplying through the levels.

| Group | Weights |
|---|---|
| One asset | 100% |
| Two assets (any correlation) | 50% / 50% |
| Any size, identical correlations | Equal weights |
| Four or more, non-identical correlations | Re-split into smaller groups until a row matches |
| 3 assets, correlations AB/AC/BC = 0.0, 0.5, 0.0 | 30% / 40% / 30% |
| 0.0, 0.9, 0.0 | 27% / 46% / 27% |
| 0.5, 0.0, 0.5 | 37% / 26% / 37% |
| 0.0, 0.5, 0.9 | 45% / 45% / 10% |
| 0.9, 0.0, 0.9 | 39% / 22% / 39% |
| 0.5, 0.9, 0.5 | 29% / 42% / 29% |
| 0.9, 0.5, 0.9 | 42% / 16% / 42% |

Correlations are rounded to the nearest listed value and **negative correlations floored at zero**
(they would otherwise produce absurd allocations). Keep groups to one, two or three members and you
barely need correlations at all — only the grouping. Carver's 16-asset worked example (UK/US banks,
retailers and bonds across four grouping levels) uses correlations exactly once, inside the US bond
group.

**Results on the three-asset example** (p. 81, 89):

| | Equal | Single period | Bootstrapped | Handcrafted (grouped) | Handcrafted + SR |
|---|---|---|---|---|---|
| US 20y bond | 33% | 68% | 53% | 50% | 58% |
| S&P 500 | 33% | 32% | 27% | 25% | 24% |
| NASDAQ | 33% | **0%** | 20% | 25% | 18% |

Handcrafting lands near the bootstrap "in a few seconds and needing no computing power".

- **Adjusting for Sharpe ratios** (Table 12, p. 86). Multiply the handcrafted weight by a factor
  driven by the asset's SR *relative to its group average*, and by how much you trust the estimate:

| SR vs group average | (A) Known with certainty, e.g. costs | (B) Estimated, >10 years' data | (C) Estimated, <10 years' data |
|---|---|---|---|
| -0.50 | 0.32 | 0.65 | **1.0** |
| -0.25 | 0.60 | 0.85 | **1.0** |
| 0 | 1.00 | 1.00 | 1.0 |
| +0.25 | 1.48 | 1.15 | **1.0** |
| +0.50 | 1.83 | 1.35 | **1.0** |

  Column C is the quietly devastating one: **with less than ten years of data, do not adjust for
  Sharpe ratio at all.** Column A is reserved for differences you genuinely know — above all
  **trading costs**, which are far more certain than returns.
- Procedure: handcrafted weights → SR per asset → difference to group average → multiplier from
  A/B/C → multiply → normalise to 100%. Repeat at each grouping level, using each group's average
  SR when moving up.
- **Honesty check** (p. 84-85, 89). Handcrafting is in-sample: you use knowledge of the whole
  history. Carver argues the damage is small because the weights are not extreme and correlations
  move slowly — validated on his chapter-15 system: in-sample handcrafting SR 0.54 vs out-of-sample
  bootstrapping 0.52, while in-sample single-period optimisation showed a fantasy 0.84 that
  collapsed to 0.3 when refitted out of sample.
- **Pessimism factors** — the proportion of back-tested return you should expect to actually get
  (Table 14, p. 90), assuming 25% of past performance came from unrepeatable secular trends:

| Fitting method | Keep |
|---|---|
| Single period, in sample | **25%** |
| Single period, out of sample | 75% |
| Bootstrapping, in sample | 60% |
| Bootstrapping, out of sample | 75% |
| Handcrafted, no SR, in sample | 70% |
| Handcrafted, with SR, in sample | 65% |

### Ch.5 — Framework Overview (p. 93-100)

**Core idea.** The framework's central claim: **separate what depends on the market from what
depends on you.** Rules and stops answer to price volatility only; the volatility target answers to
your wealth and pain threshold; position size is where the two meet.

- **The bad example** (p. 94-95) — the kind of system found in most trading books: enter on a
  20/40-day moving average cross, reverse on the opposite cross, never more than 10 Eurodollar
  futures or £10 per spread-bet point, never more than 3% of capital per trade, 3% trailing stop,
  *"if you find yourself triggering stops too frequently, then widen them"*. Carver leaves the entry
  and exit rules alone and demolishes everything else:
  - Why 3%? With 40 simultaneous positions that risks 120% of the portfolio.
  - Position limits in contracts only suit one account size, at one date, for listed instruments.
  - **A stop based on your capital and pain threshold is simply wrong**: a stop that made sense in
    oil futures is absurd in USD/CAD; one calibrated in the calm of 2006 would be shredded in 2008.
    Quoting Colm O'Shea via Schwager: *"I was setting stops based on my pain threshold. When I get
    out of a trade now it is because I was wrong."* (p. 95)
- **Why modular** (p. 96-97): flexibility (any rule plugs in, including discretionary forecasts and
  the asset allocator's non-forecast); transparency (no black boxes — unlike swapping one mystery
  PC component for another); **well-defined interfaces** — a forecast of +1.5 must mean the same
  thing in every instrument and every trading style; and "getting the boring bit right", the dull
  wrapper nobody wants to build being precisely what determines survival.
- Every module is *"just a few steps of basic arithmetic which require just a calculator or simple
  spreadsheet"* (p. 96) — not thousands of lines of code.

**The pipeline** (Table 15, p. 98), per instrument then across instruments:

```
trading rule variations → forecasts
        ↓ forecast weights
   combined forecast (one per instrument)
        ↓ volatility target + position sizing
   subsystem position (one instrument, as if it were your whole portfolio)
        ↓ instrument weights (+ diversification multiplier)
   portfolio weighted position → trades
        ↘ customised throughout for speed and size
```

- A **trading subsystem** is a complete, self-contained system for one instrument — "just as the
  cells in the human body are each individual living organisms" — sized as though all your capital
  were in it; the portfolio stage then scales it down.
- The three reader types enter the same pipeline at different points: staunch systems traders use
  systematic rules; semi-automatic traders substitute discretionary forecasts; asset allocating
  investors use a single fixed forecast for every instrument.
- **Speed and size** is not a module but a set of principles applied across the whole system.

### Ch.6 — Instruments (p. 101-107)

**Core idea.** Before deciding how to trade, decide what is even eligible. Some instruments must be
excluded outright — and the disqualifying feature is usually *low* volatility, not high.

**Necessities** (p. 102-103):
- **Data.** No daily price data, no systematic trading. Carver cannot trade UK Gilt futures for
  want of a data licence.
- **Minimum size.** A JGB future is ~¥150m; his desired position is 0.1 of a contract, so the
  instrument is unusable. Minimum sizes make positions binary and cap how many instruments a small
  account can hold (developed in Ch.12).
- **Understand what moves the price.** *"More buyers than sellers" is not an acceptable answer.*
  Essential for designing ideas-first rules, and for spotting a market that has become
  dysfunctional. Carver avoided EUR/CHF and USD/CHF entirely because the price was set by central
  bank intervention, not by the factors present in the back-test — and so sat out the January 2015
  peg removal that wrecked systematic traders, hedge funds and banks alike.
- **Standard deviation must not be extremely low.** Pegged currencies are the archetype: risk
  returns sharply when it returns; reaching your risk target needs heavy leverage, magnifying the
  blow-up; they cap the risk the whole system can achieve; and they cost more to trade.

**Choosing among the survivors** (p. 103-105): as many instruments as minimum sizes allow;
prefer low average correlation (owning RBS and Barclays, don't add Lloyds); prefer cheap — an
expensive instrument must be traded more slowly, and above a cost threshold not at all; liquidity
matters most for large or impatient investors; and skew — a static strategy inherits the
instrument's skew, but a positive-skew rule such as trend following applied to a negative-skew
asset partly offsets it.

**Access** (p. 105-106):
- **Exchange over OTC.** In the January 2015 franc meltdown, OTC clients met refused orders,
  withdrawn quotes, trades not honoured, fills re-marked after the fact, and brokers going into
  liquidation. CHF/USD futures traders found thin liquidity but a functioning market.
- **Cash vs derivative.** Derivatives give straightforward leverage — often the only way to reach
  a volatility target — with different costs, minimum sizes and tax treatment (UK spread bets are
  taxed as gambling: winnings free, losses not deductible). A FTSE future is cheaper, more liquid
  and exchange-traded compared with the equivalent spread bet, but its larger minimum size shuts
  out small accounts. Options and non-linear derivatives are deliberately excluded.
- **Collective funds** (ETFs, trackers) are the fallback when leverage is unavailable or a market
  is otherwise inaccessible: low fees and small minimums, but usually dearer to trade than the
  derivative. Active funds only where nothing else exists — fees are higher and manager skill is
  very hard to prove.

### Ch.7 — Forecasts (p. 109-123)

**Core idea.** The single most transferable convention in the book: a forecast is not "buy or
sell" but a **number proportional to the expected risk-adjusted return, scaled so its average
absolute value is 10 and capped at ±20**. That convention is the interface that lets any rule,
any instrument and any account size share one framework.

- **Sergei's three questions** (p. 110-111), the skeleton of the whole framework: *"How much do
  you like this trade?"* (the heart — the forecast), *"How much can you afford to lose?"* (the gut
  — the volatility target), *"How risky is it?"* (the head — the instrument's volatility).
- **Why scaled, not binary** (p. 111): forecasts near zero are empirically less profitable than
  large ones; binary systems cost double to trade because reversing means selling two full
  positions at once; and the rest of the framework assumes forecasts with a stable standard
  deviation and no lumpiness.
- **Why proportional to risk-adjusted return** (p. 112). A forecast in contracts fails three ways:
  it ignores account size, it ignores volatility changing over time, and it cannot be shared across
  instruments. Worked example: Bund at 2% expected return with 8% volatility scores 0.25; Schatz
  at 1% with 2% volatility scores 0.5 — so **the Schatz forecast should be twice the Bund's**.
  Since return ÷ standard deviation is the Sharpe ratio, *"expected Sharpe ratios make good
  forecasts"*.
- **Scale: expected absolute value of 10.** +10 an average buy, -10 an average sell, +5 a weak buy,
  -20 a very strong sell. The exact scale is arbitrary but it must be consistent, and it propagates
  into every later component.
- **Cap at ±20** (p. 113-114), for five reasons: risk control (no single rule variation should
  dominate a diversified system); limited data (a Gaussian forecast exceeds 20 only ~5% of the
  time, so there is little evidence such forecasts are proportionally right); extremes behave
  differently (dead cat bounce; a 50% dividend yield means bankruptcy, not value); a large forecast
  may reflect *low volatility* rather than high expected return, and quiet periods are followed by
  volatility jumps and reversals; and the cost of capping is small. Carver's own case: very strong
  JGB forecasts in January 2013, driven by low volatility, met Abe's reforms — *"because my
  forecasts were capped the damage was contained."*
- **Discretionary forecasts** (Table 16, p. 115) — the semi-automatic trader's conversion table:

| Very strong sell | Strong sell | Sell | Weak sell | Neutral | Weak buy | Buy | Strong buy | Very strong buy |
|---|---|---|---|---|---|---|---|---|
| -20 | -15 | -10 | -5 | 0 | +5 | +10 | +15 | +20 |

  Two rules attached: **never exceed ±20, even for the trade of a lifetime**, and **never change a
  forecast while the position is open** — that is exactly where meddling enters. Positions are
  closed by a systematic trailing stop instead, which also makes the discretionary trader behave
  like an early loss taker and inherit positive skew.
- **The asset allocator's "no-rule" rule** (p. 116): a constant forecast of **+10 on every
  instrument at all times**. Because forecasts are risk-adjusted, an equal forecast everywhere is
  equivalent to assuming equal Sharpe ratios — which produces continuously rebalanced risk parity
  (the "fourth degree" static portfolio). Its edge over a bought risk-parity fund: better-than-equal
  weights from handcrafting, volatility re-estimated as it changes (most risk parity funds are only
  "third degree"), cost-aware rebalancing, and no management fee.
- **Two example rules** (p. 117-119), deliberately of opposite skew, and together **~85% of the
  back-tested performance of Carver's full system**:
  - **EWMAC** (exponentially weighted moving average crossover) — fast EWMA above slow means
    uptrend. Positive skew, price data only, explained by prospect theory, academic support back to
    the 1960s.
  - **Carry** — the return earned if prices don't move at all: yield minus funding. FX carry
    (borrow yen at 0.5%, invest AUD at 3.5%), a dividend yield of 3% against 1% funding, or the
    0.07 pickup rolling June 2018 Eurodollars to March 2018. Steady gains, then sudden breakdown:
    *"evil negative skew"*, which is precisely why it is paid.
- **Adapting someone else's rule** (p. 120-121), the five-step recipe, illustrated on "Close to
  Open":
  1. Pare it down to something simple and objective: *"Buy if the open is higher than yesterday's
     close."*
  2. Make it continuous, not binary: raw forecast = `Open − Close`.
  3. Volatility standardise: `(Open − Close) ÷ recent standard deviation of daily returns`.
  4. Recalculate the forecast every day, independent of the current position — **separate entry and
     exit rules do not fit the framework**; if you must use one, use the semi-automatic trader's
     stop loss, never a bespoke exit rule ("usually over-fitted").
  5. Rescale with a **forecast scalar** = 10 ÷ natural average absolute forecast. Here 10 ÷ 0.33
     = **30**. Find it from data *without looking at performance*.
- **Selecting variations** (p. 122), consistent with Ch.3: drop either of any pair correlated above
  **95%**; exclude anything holding positions longer than a few months (no statistically
  significant Sharpe) or trading too fast for that instrument's costs — which may mean a different
  variation set per instrument.

### Ch.8 — Combined Forecasts (p. 125-133)

**Core idea.** When rules disagree — EWMAC bullish on crude while Carry is still bearish — you do
not pick a winner. You take a weighted average, then **rescale it**, because averaging imperfectly
correlated forecasts shrinks the result below the scale the rest of the framework assumes.

- **Forecast weights** are portfolio weights over trading rule variations: all positive, summing to
  100%, found by handcrafting (Ch.4) on the correlations between rules. Worked example: EWMAC
  forecast +15 and Carry -10 with 50/50 weights gives a raw combined forecast of **+2.5** (p. 126).
- **Grouping for handcrafting**: group variations within a rule, then allocate across rules. With
  EWMAC(16,64), EWMAC(32,128), EWMAC(64,256) and Carry, adjacent EWMAC variations correlate 0.9 and
  the extremes 0.7 → row 11 of Table 8 gives 42% / 16% / 42% inside the group, then 50/50 across
  rules (p. 127):

| Rule variation | Within group | Across groups | Final |
|---|---|---|---|
| EWMAC 16,64 | 42% | 50% | 21% |
| EWMAC 32,128 | 16% | 50% | 8% |
| EWMAC 64,256 | 42% | 50% | 21% |
| Carry | 100% | 50% | **50%** |

  Note what this produces: a single carry rule gets half the risk, because diversification across
  *styles* is worth more than three flavours of the same trend.
- **The forecast diversification multiplier** (p. 128-132). Averaging uncorrelated forecasts that
  each ranged ±20 produces a combined forecast ranging only -15 to +12; the multiplier restores the
  intended scale of 10.

| Number of assets | corr 0.0 | 0.25 | 0.5 | 0.75 | 1.0 |
|---|---|---|---|---|---|
| 2 | 1.41 | 1.27 | 1.15 | 1.10 | 1.0 |
| 3 | 1.73 | 1.41 | 1.22 | 1.12 | 1.0 |
| 4 | 2.0 | 1.51 | 1.27 | 1.10 | 1.0 |
| 5 | 2.2 | 1.58 | 1.29 | 1.15 | 1.0 |
| 10 | 3.2 | 1.75 | 1.35 | 1.17 | 1.0 |
| 20 | 4.5 | 1.86 | 1.38 | 1.18 | 1.0 |
| 50+ | 7.1 | 1.94 | 1.40 | 1.19 | 1.0 |

- **Rule-of-thumb correlations** when you have no back-test (p. 131): selected variations of the
  *same* rule ~0.7 (up to 0.9); different rules of the same style ~0.5; rules of different styles
  ~0.25. The four-variation example averages 0.5 → multiplier 1.27 from the table, against 1.31
  computed precisely.
- **Two hard limits.** Floor all correlations at zero (negative correlations produce dangerously
  large multipliers), and **cap the multiplier at 2.5** whatever the estimate says — otherwise the
  combined forecast sits at its ±20 cap almost permanently and the system degenerates into the
  binary all-in/all-out behaviour the framework exists to avoid.
- **Cap the combined forecast at ±20 too** (p. 132): with two +16 forecasts, equal weights and a
  1.5 multiplier, the combined forecast is 24 and must be cut back to 20.

**Pipeline recap:** individual forecasts (avg |10|, capped ±20) → weighted average by forecast
weights → × forecast diversification multiplier (1.0 to 2.5) → cap at ±20 → final combined forecast.

### Ch.9 — Volatility Targeting (p. 135-151)

**Core idea.** *"Deciding your overall trading risk is the most important decision you will have to
make when designing your trading system."* Nearly all amateurs lose money because positions are too
large for the account — and painful losses are the main reason both amateurs and professionals
start meddling. The answer is a single number, the **percentage volatility target**, set by
Half-Kelly against a *realistic* Sharpe ratio.

- **Definitions** (p. 137-138). Volatility target = expected annualised standard deviation of
  returns. Trading capital = cash currently at risk. Cash volatility target = capital × percentage
  target ($1m at 10% → $100,000). Daily cash target = annualised ÷ 16. The annualised target is
  **not** a maximum or even an average annual loss — you will sometimes lose more.
- **Four questions to set it** (p. 138): how much can you lose; how much risk can you cope with;
  can you realise that risk given leverage available; and is that level right for your system.
  *"Never put in more than you can afford to lose. Never trade with borrowed money, or money
  earmarked to pay off debts."*
- **What each target actually feels like** (Table 20, p. 139 — $100,000 capital, SR 0.5, zero skew):

| Expected | 25% | 50% | 100% | 200% |
|---|---|---|---|---|
| Worst daily loss each month | $2,500 | $5,000 | $10,000 | $20,000 |
| Worst weekly loss each year | $6,900 | $14,000 | $28,000 | $55,000 |
| Worst monthly loss every ten years | $16,000 | $32,000 | $63,000 | $80,000 |
| Worst daily loss every 30 years | $5,400 | $11,000 | $22,000 | $43,000 |
| Cumulative loss, 10% of the time at least | $9,300 | $15,000 | $30,500 | $62,000 |
| Cumulative loss, 1% of the time at least | $11,000 | $18,500 | $37,000 | $75,000 |

- **Skew changes the shape** (Tables 21-22, p. 140-141). Negative skew: worse individual days
  (worst daily loss every 30 years at a 25% target: $11,500 vs $5,400), but *smaller* cumulative
  losses. Positive skew: much gentler individual losses ($2,800), but higher typical drawdowns —
  *"the difficulty is psychological; committing to a system when you spend most of your time
  suffering cumulative losses."*
- **Ten-year ruin probabilities** (Table 23, p. 142, SR 0.5, zero skew):

| | 25% | 50% | 100% | 200% |
|---|---|---|---|---|
| Chance of losing half | <1% | 10% | 40% | **93%** |
| Chance of losing 90% | <1% | 1.1% | 22% | **88%** |

- **Leverage that cannot survive the move should not be taken.** EUR/CHF carried ~1% annual
  volatility before January 2015, so a 50% target on it alone needed **50× leverage** — offered
  freely by retail FX brokers (some up to 500×). The move was over 16%: only 7× or less survived,
  implying a maximum honest target of 7%. Rule: no single position should wipe you out after the
  largest conceivable move (p. 142-143).
- **The Kelly criterion** (p. 143-145). Betting the maximum ignores compounding: +100% average per
  trade can still leave you with 29% of your capital (lose 90%, then make 190%). The rule reduces
  to something startlingly simple: **set your percentage volatility target equal to your expected
  Sharpe ratio.** SR 0.5 → 50% target.

| Expected SR | Optimal (full Kelly) target | Expected return |
|---|---|---|
| 0.2 | 20% | 4% |
| 0.5 | 50% | 25% |
| 1.0 | 100% | 100% |
| 2.0 | 200% | 400% |

  And immediately the warning: this table is *"potentially dangerous when used by an over confident
  investor"*. Believe an over-fitted SR of 2.0 and Kelly appears to authorise 400% a year — which
  is how someone with $20,000 concludes they can earn $80,000 trading full time, and how brokers
  find willing customers for the leverage.
- **Use Half-Kelly, on a degraded Sharpe ratio** (p. 146-147). Carver's own system: 45 instruments,
  8 rules, 30 variations, 35-year back-test, SR ~1.0 after costs. He applies the 0.75 pessimism
  factor from Table 14 → realistic SR 0.75 → full Kelly 75% → **halved to 37%**, and notes he
  actually runs **25%**. Ed Thorp is quoted: *"most cautious investors who use Kelly find the
  frequency of substantial bankroll reductions to be uncomfortably large."*

**Recommended targets** (Tables 25-26, p. 147-148) — halve again for negative skew:

| Realistic back-tested SR | Systems trader, skew ≥ 0 | Systems trader, negative skew |
|---|---|---|
| 0.25 | 12% | 6% |
| 0.40 | 20% | 10% |
| 0.50 | 25% | 12% |
| 0.75 | 37% | 19% |
| 1.0 or more | 50% | 25% |

| Expected SR | Asset allocating investor | Semi-auto, skew ≥ 0 | Semi-auto, negative skew |
|---|---|---|---|
| 0.20 | 10% | 10% | 5% |
| 0.30 | 15% | 15% | 7% |
| 0.40 | 20% | 20% | 10% |
| 0.50+ | 20% (capped) | 25% | 12% |

**Nobody should exceed a 50% volatility target, and most people should use far less.**

- **Never change the percentage target** — that is meddling's back door. One exception: a one-off
  *downward* revision if you badly misjudged your tolerance. The right way to ease in is to start
  with **less capital** at the same percentage target, increasing capital gradually (p. 148).
- **Roll up profits and losses** (p. 149). Kelly requires risk to follow current capital. Lose
  $2,000 of $100,000 at a 30% target and your effective target is now 30.6% — recompute to 30% of
  $98,000 = $29,400. Gains compound the same way. Carver's system re-checks hourly; manual systems
  above a 15% target should check at least daily, and anything leveraged at least weekly.
- **Translating "% of capital per trade"** (Table 27, p. 150), assuming two positions held on
  average and an average bet of half the maximum:

| Average holding period | 1% at risk | 2.5% | 5% | 10% | 20% |
|---|---|---|---|---|---|
| 1 day | 40% | 100% | 200% | ! | ! |
| 1 week | 16% | 40% | 80% | **160%** | ! |
| 2 weeks | 8% | 19% | 38% | 76% | 152% |
| 6 weeks | 4% | 10% | 21% | 41% | 82% |
| 3 months | 3% | 7% | 13% | 27% | 53% |

  This closes the loop on the book's opening example: a system holding a week with 10% of capital
  per trade is running a **160% volatility target**, which is only Kelly-optimal if the strategy
  truly earns SR 1.6 — an expected return of 256% a year. *"There is some serious overconfidence at
  work here. Worse still, this is nowhere near the most aggressive system I've ever seen."* (p. 151)

### Ch.10 — Position Sizing (p. 153-163)

**Core idea.** The arithmetic bridge from an abstract forecast to a number of contracts. Five
quantities chained together, none of them rounded until the very end.

**The chain:**

| Term | Definition |
|---|---|
| **Instrument block** | What "one" of the instrument is — one share (or 100), one futures contract, the minimum spread-bet stake per point |
| **Block value** | Cash gained or lost per **1% price move** of one block |
| **Price volatility** | Expected daily standard deviation of price, in % |
| **Instrument currency volatility** | Block value × price volatility — daily risk of one block, in the instrument's currency |
| **Instrument value volatility** | × exchange rate (instrument currency ÷ account currency) — the same, in *your* currency |
| **Volatility scalar** | Daily cash volatility target ÷ instrument value volatility — blocks to hold at a forecast of +10 |
| **Subsystem position** | Volatility scalar × forecast ÷ 10 |

- **Block values are not obvious** (p. 154-155): an equity block is 1% of the share price; a £10/point
  FTSE spread bet has a block value of ten times 1% of the price (a move from 6500 to 6565 costs
  £650); a WTI contract is 1,000 barrels, so at $75 a 1% move is $750; a Eurodollar future is $1m
  for three months, so a 1% price rise is worth $2,450.
- **Measuring recent standard deviation** (p. 155-156), three methods: eyeball the chart (fine for
  semi-automatic traders, not recommended otherwise); a simple moving average over a look-back
  window; or an EWMA. Carver found **almost no performance difference for look-backs from a few
  days to six months**, so rather than risk over-fitting he defaults to **25 business days** (the
  industry standard, as in RiskMetrics), equivalently a **36-day EWMA**.
- **The recurring warning, in its sharpest form** (p. 156): estimating position size from recent
  volatility *"would be a disaster if you were using this method to trade Credit Default Swaps in
  early 2007, the front of the Eurodollar futures curve at any time in the US zero interest rate
  period, or for that matter Swiss franc FX in early January 2015."* Low measured volatility →
  large blocks → *"after periods of calm markets have a nasty habit of becoming crazy overnight,
  leaving you with dangerously large positions."*

**Worked example** (p. 162-163) — UK investor, £1,000,000 annualised cash volatility target,
WTI crude, combined forecast **-6**:

```
daily cash vol target   = £1,000,000 ÷ 16            = £62,500
price volatility        = $1 daily move on $75       = 1.33%
block value             = 1% × $75 × 1000 barrels    = $750
instrument ccy vol      = $750 × 1.33               = $997.50
instrument value vol    = $997.50 × 0.67 (USD/GBP)   = £668.325
volatility scalar       = £62,500 ÷ £668.325         = 93.52 contracts
subsystem position      = 93.52 × (-6) ÷ 10          = short 56.11 contracts
```

- **The +10 convention pays off here.** The volatility scalar *is* the position for a forecast of
  +10; a forecast of +5 halves it, -20 doubles it and flips the sign. For an asset allocating
  investor, whose forecast is permanently +10, the position is always exactly the volatility scalar.
- Positions rise with larger absolute forecasts, bigger accounts and greater risk appetite, and
  fall with higher instrument price volatility. **No rounding anywhere in the chain** — rounding
  is deferred to the trading stage (Ch.11-12).

### Ch.11 — Portfolios (p. 165-175)

**Core idea.** Each subsystem was sized as though it owned all your capital; now they share it.
Multiply by an instrument weight, then multiply back up by an instrument diversification
multiplier — and only now round, and only trade if the gap is worth it.

> "Diversification really is the only free lunch in investment." (p. 165)

- **Instrument weights** come from handcrafting on the correlations of **subsystem** returns, not
  instrument returns. The rule of thumb: **subsystem correlation ≈ 0.7 × instrument correlation**
  for a dynamic system; **× 1.0** for asset allocating investors, whose static strategy inherits
  the underlying correlations (p. 167-168).
- **Do not adjust instrument weights for Sharpe ratio** — there is rarely enough evidence of
  performance differences between instruments, even after accounting for costs (p. 168).
- **Semi-automatic traders** have no fixed instrument set, so allocate equally across a *notional
  maximum number of concurrent bets*: ten bets → 10% each. The maximum should be **no more than
  2.5× the average** number of bets held (p. 169).
- **Instrument diversification multiplier** (p. 169-171): same logic as the forecast multiplier —
  a diversified portfolio of volatility-standardised subsystems undershoots the risk target. Use
  Table 18 with the number of subsystems and their average correlation. For semi-automatic traders
  it is simply **maximum bets ÷ average bets** (5 ÷ 4 = 1.25), a deliberately conservative formula
  that assumes all bets are perfectly correlated. **Cap at 2.5 in every case** — *"in a crisis such
  as the 2008 crash, correlations tend to jump higher exposing us to serious losses"*.
- Floor negative correlations at zero before computing any multiplier.

**Full worked example** (p. 172-173), Euro investor, €100,000 annualised cash volatility target
(→ €6,250 daily), January 2015 figures, arbitrary forecasts:

| | Price vol %/day | Block value | Instr. ccy vol | ×USD/EUR 0.88 | Vol scalar | Forecast | Subsystem pos | Instr. weight | × DM 1.41 | **Portfolio pos** | Rounded | Current | **Trade** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| US 20y bond | 0.52 | $1500 | $780 | €686 | 9.11 | +10 | 9.11 | 50% | | **6.42** | 6 | 4 | Buy 2 |
| S&P 500 | 0.84 | $1145 | $956 | €841 | 7.43 | -10 | -7.43 | 25% | | **-2.62** | -3 | -2 | Sell 1 |
| NASDAQ | 0.87 | $880 | $766 | €674 | 9.28 | -15 | -13.9 | 25% | | **-4.91** | -5 | -5 | None |

- **Position inertia** (p. 173-174) — the last and cheapest trick in the framework: **do not trade
  until the target position is more than 10% away from the current position.** A target drifting
  from 133.48 to 133.52 Italian bond futures would otherwise trigger a buy and then a sell for a
  0.04 contract change; with inertia, the target must reach 147 before you trade. Carver's
  research: it *"significantly reduces trading costs"* while having a negligible effect on pre-cost
  performance — **"there is no downside to using it"** (except for very fast systems, which he
  doubts are viable anyway).
- **Rounding happens exactly once**, at the very end of the chain, immediately before comparing
  with the current position.

### Ch.12 — Speed and Size (p. 177-205)

**Core idea.** The longest and most operational chapter. Costs are *knowable*; pre-cost returns are
not. So costs, not back-tested performance, should drive which instruments you trade, how fast, and
which rules you keep. The governing rule: **never pay more than a third of your expected profits in
trading costs.**

- **The opening test case** (p. 178): a rule with a back-tested pre-cost SR of 1.5 that pays away
  two-thirds of its profits, netting SR 0.5. At a 20% volatility target that is 30% gross, 20%
  costs, 10% net. If the realised pre-cost SR comes in below 1.0, the strategy **loses money**.
  *"Overtrading is a result of overconfidence."*
- **Cost components** (p. 179-181): execution cost (assume **half the bid-offer spread** if your
  order is smaller than the depth at the inside spread), per-ticket fees (£5-£15 typical for UK
  retail brokers), per-contract or per-100-shares fees, and percentage value fees and taxes (UK
  stamp duty 0.5%). Holding costs (rolls, fund charges) are ignored as they don't affect speed.

**Standardised cost** (p. 182) — the unit that makes everything comparable:

```
standardised cost (SR units per round trip) = (2 × cost per block) ÷ (16 × instrument currency volatility)
```

It answers: how much annualised Sharpe ratio do I surrender for one buy-and-sell? Crucially,
**cost is higher for lower-volatility instruments** — one more reason to exclude them.

| Instrument | Standardised cost |
|---|---|
| Cheapest futures (FTSE 100, NASDAQ) | ~0.001 SR |
| Euro Stoxx future | 0.002 SR |
| Australian interest rate futures | ~0.03 SR |
| Index spread bet (FTSE) | **0.01 SR** (benchmark for spread bets) |
| ETF (IGIL inflation-linked bond) | **0.08 SR** (benchmark for ETFs) |

- **Turnover** (p. 184-185) is the matching standardised measure of speed: round trips per year of
  an *average-sized* position. Turnover 1 = twelve-month holding period; 52 = one week.
  **Annual cost in SR = standardised cost × turnover.** Sources of turnover, in descending order:
  forecast changes; changes in price volatility; changes in trading capital (~3% a day at a 50%
  volatility target, ~1% at 16%); exchange rates; and system parameters — *"You can eliminate the
  trades that result from this element by not meddling with your system!"*
- **Turnover from a simple back-test:** blocks traded per year ÷ (2 × average absolute blocks held).

**The speed limit** (p. 187-188) — the chapter's central prescription:

| Trader type | Assumed max pre-cost SR per instrument | Max annual cost |
|---|---|---|
| Staunch systems trader | 0.40 | **0.13 SR** |
| Semi-automatic trader / asset allocating investor | 0.25 | **0.08 SR** |

Turnover speed limit = max cost ÷ standardised cost. Euro Stoxx: 0.13 ÷ 0.002 = **65 round trips
a year**, just under a week's holding period.

- **Why day trading is arithmetically excluded** (p. 188). Two round trips a day is ≥500 turnover,
  requiring a standardised cost of 0.13 ÷ 500 = 0.00025 SR — a quarter of what the cheapest futures
  achieve. Since roughly a quarter of those costs are irreducible commissions (~$1/contract),
  **you would need zero execution cost — consistently trading at mid or better** — and for three
  round trips a day, consistently *negative* execution costs. *"This is why the vast majority of
  amateur day traders are unprofitable."*
- **Feasible speeds by instrument** (Tables 34-35, p. 190-191):

| Holding period | Turnover | Max cost at 0.08 SR | Instruments |
|---|---|---|---|
| 1 day | 256 | 0.00031 | **None** |
| 3 days | 85 | 0.001 | Cheapest futures (NASDAQ) |
| 1 month | 12 | 0.0067 | Nearly all futures except short-maturity bonds, STIR |
| 6.5 weeks | 8 | 0.01 | Index spread bets (FTSE) |
| 3 months | 4 | 0.02 | Individual equity spread bets |
| 6 months | 2.0 | 0.04 | — *slowest semi-automatic trader* |
| 1 year | 1.0 | 0.08 | Cheapest ETFs |
| 2.5 years | 0.4 | 0.20 | Most individual equities — *slowest asset allocator* |

For staunch systems traders at 0.13 SR: EWMAC(2,8) turns over 128×/year and needs the cheapest
futures; EWMAC(4,16) 54×; **the chapter-15 rule set turns over 12.5×/year**, affording a 0.01 SR
instrument — nearly all major futures and index spread bets; EWMAC(64,256) 7.5×.

- **The spread-betting system from the introduction, finally costed** (p. 192): weekly holding =
  52 turnover × 0.01 SR = **0.52 SR a year in costs**, against the 160% implied volatility target
  → **83% a year pre-cost simply to break even**. This is the source of the figure quoted on p. 6.
- **Fit on costs, never on pre-cost performance** (p. 193-194). The Ch.3 prohibition applies only
  to pre-cost returns: back-testing *turnover* to reject expensive variations is actively
  encouraged. For forecast weights, Carver has *"never found consistent evidence that faster
  trading rules have a higher pre-cost SR"* — so assume equal pre-cost SR and adjust weights using
  **column A ("with certainty") of the SR adjustment table**, since costs are known. Within the
  speed limit these adjustments never exceed ×0.95 / ×1.05 and are usually not worth making.
- **Slow the volatility estimate to save costs** (Table 36, p. 196-197). Changing the look-back
  barely matters once trading-rule turnover is ≥5. It matters enormously at the slow end: the
  asset allocator's "no-rule" rule gives turnover 1.6 at the default 5-week look-back (1.6 × 0.08 =
  0.13 SR, **breaking their own speed limit**) but 0.40 at a 20-week look-back (0.032 SR). Beyond
  20 weeks, performance degrades badly. Semi-automatic traders eyeballing a chart should use a
  one-month window and **not adjust an existing position's volatility estimate unless it has moved
  more than 25%**.
- **Do not under-weight expensive instruments** (p. 198-199). Carver's research: costlier
  instruments usually perform *somewhat better* after costs — consistent with the liquidity premium
  — provided turnover stays under 15. Since the speed limit already forces expensive instruments to
  be traded slowly, **assume the same post-cost SR for all subsystems and make no instrument-weight
  adjustment for costs.**
- **Too much capital** (p. 199-200): once your order exceeds the depth at the inside spread, the
  half-spread assumption collapses. Selling 5,000 Euro Stoxx lots into the book shown costs **4.3
  points**, not 0.5. Showing the order invites the market to move away; working it in chunks leaks
  information. Large traders need real cost models and real execution work.
- **Too little capital** (p. 200-202) — the granularity problem:

```
maximum position = 2 × volatility scalar × instrument weight × instrument diversification multiplier
                   (1 × instead of 2 × for asset allocating investors, whose forecast is fixed at +10)
```

With €40,000 of capital, the S&P 500 subsystem's maximum position is 1.05 contracts: forecast and
volatility can both double and the position stays at one contract. **Carver's threshold: act if the
maximum possible position is under four blocks** — increase the instrument weight (in moderation),
reduce the number of instruments, drop the instrument, or live with it (six of his own 40+ futures
are below four contracts). The absolute floor is one block, *"or there is clearly no point
including the relevant asset."*

- **Portfolio construction rule** (p. 202): hold the most diversified portfolio possible **subject
  to** the four-block constraint — at least one instrument per major asset class, adding more only
  while no maximum-position problem appears in the new or existing instruments.

*Two internal inconsistencies in this chapter: the body gives the slowest semi-automatic turnover
as 2.0 round trips/year (max cost 0.04 SR) while the summary on p. 204 gives 1.8 and 0.044 SR; and
that summary cross-references "table 13 (page 89)" for the SR adjustment factors, which are in
table 12 on page 86.*

### Ch.13 — Semi-automatic Trader (p. 209-224)

**Core idea.** The discretionary trader keeps the buy/sell call and gives up everything else. Entry
is human; **exit is exclusively a systematic trailing stop** — no other exit rule is permitted.

**The example system:** £100,000 capital, quarterly spread bets on equity indices and FX, 15%
volatility target, maximum 4 concurrent bets, average 3.

- **The stop loss rule** (p. 211-213). Set a parameter **X**, and place a trailing stop **X × the
  daily standard deviation of price (in price points)** from the high since entry (long) or low
  since entry (short). Crude at a $70 high with $1.5 daily volatility and X = 4 → stop at $64.
  Update the volatility estimate through the life of the trade (but only if it moved >25%), and
  trail the stop with new highs/lows.

| X | Average holding period | Turnover | Max instrument cost |
|---|---|---|---|
| 1 | 4 days | 64 | 0.0013 |
| 2 | 9 days | 29 | 0.0027 |
| 3 | 17 days | 15 | 0.0053 |
| 4 | **6.5 weeks** | **8** | **0.01** |
| 8 | 13 weeks | 4.0 | 0.02 |
| 10 | 26 weeks | 2.0 | 0.04 |

  X = 4 is chosen because spread bets cost 0.01 SR: 8 × 0.01 = 0.08 SR, exactly the speed limit.
  **Match your forecasting horizon to X** — *"There is no point making a forecast of prices for the
  next six months if you're likely to be stopped out by next Tuesday."* Use one X for all
  instruments, set by the most expensive one.
- **No profit targets.** Carver's research finds no evidence systematic profit targets work: most
  markets trend, and a target exits trends too early (p. 213). The stop-only design is what gives
  the discretionary trader the positive skew of a trend follower.
- **Cost check:** 0.08 SR × 15% volatility target = **1.2% a year** performance drag, plus ~0.6%
  for rolling quarterly bets — *"more than most passive ETFs, but significantly cheaper than a
  hedge fund."*
- **Portfolio mechanics** (p. 215-216): instrument weight = 100% ÷ maximum bets (4 → 25%);
  diversification multiplier = maximum ÷ average (4 ÷ 3 = 1.33). **At the maximum number of bets
  you simply cannot open another** — *"If they all continue to be profitable then perhaps your new
  bet wasn't necessary after all."*
- **Pyramiding is allowed, reducing is not.** A new, separate bet on an instrument you already hold
  is permitted (own stop, own life, counts towards the maximum), but it must not shrink or reverse
  the existing position, and **total absolute forecast on one instrument must not exceed 40**.
- **Capital at risk per bet**, for comparison with traditional money management (p. 216):

```
(X × forecast × % volatility target) ÷ (10 × 16 × average number of bets)
= (4 × 10 × 15%) ÷ (10 × 16 × 3) = 1.25% per bet on average, 2.5% at a maximum forecast of 20
```

- **Daily process** (p. 217-218): check stops → today's account value → cash volatility target →
  charts → eyeball price volatility (update only if >25% change) → re-trail stops → volatility
  scalar → subsystem position → × instrument weight × multiplier → round → trade only if >10% away
  → look for new setups.

**The trading diary** (p. 219-224), October-November 2014, is the most instructive part of the
chapter because the discretionary calls are mostly *wrong* and the framework rescues them:

- Opens long crude (+10) at $83, long S&P 500 (+15) at 1880, short Euro Stoxx (-10) at 2900.
- Adds a second S&P bet at +25 (reaching the 40-unit ceiling); crude stops out for -£1,333;
  Euro Stoxx stops out for -£1,380; a belated crude short at $75 initially loses.
- *"I'm tempted to take profits on my only profitable trade, the S&P 500 longs, but I can't because
  it isn't part of the system!"* and later *"If I wasn't trading systematically I'd also be tempted
  to cut my oil short, as I don't seem to be calling crude very well."* — both instincts would have
  been wrong; accumulated profit reaches **£7,682**.
- When crude drops $5 in a day, doubling the volatility estimate from $1 to $2 **halves the
  position and doubles the stop gap** ($8), leaving the capital at risk unchanged. Carver
  underlines that this is not profit-taking: *"the system is trading automatically to keep the
  amount of capital at risk constant."*

### Ch.14 — Asset Allocating Investor (p. 225-244)

**Core idea.** The framework applied by someone who makes no forecasts at all: ten ETFs, a constant
forecast of +10, no leverage, no shorting. It produces continuously rebalanced risk parity under an
institutional mandate.

**Setup:** €10,000,000 (a small pension fund), ten ETFs in 100-share blocks, mandate constraints —
maximum 40% bonds, maximum 30% of equities in emerging markets, maximum 25% of bonds in each of
emerging markets and inflation-linked. All constraints expressed in *risk-adjusted* proportions.

- **Instrument choice** (p. 226-227): lowest total expense ratios; **avoid bond ETFs with annual
  sigma below 5%** (hence longer-maturity funds), because without leverage low-volatility assets
  make the risk target unreachable and cost more per unit of risk. The most expensive instrument
  (IGIL, 0.08 SR) is used conservatively as the cost for all of them.
- **A 20-week (100-day) volatility look-back**, not the default 5 weeks — the saving is large at
  this speed: turnover falls to 0.4 round trips a year, costing 0.4 × 0.08 = **0.032 SR** instead
  of 0.13 SR, which would have breached the 0.08 speed limit (p. 228).
- **Setting the volatility target when you cannot borrow** (p. 228-230) — a two-step procedure
  worth extracting:
  1. Pick a **desired leverage factor** = portfolio value ÷ trading capital. Carver recommends
     **90%** for unleveraged investors — deliberately below 100% so that falling volatility (which
     demands buying more) doesn't run you out of cash.
  2. Initial guess for the volatility target = **the lowest annualised price volatility of any
     instrument** (here 6.88%, the inflation-linked bond ETF; the range runs to 22.4% for EM
     equities).
  3. Run the full position calculation, total the cash value of all positions, and compute the
     **realised leverage factor** (here €8,262,000 ÷ €10,000,000 = 82.6%).
  4. Scale: 90% ÷ 82.6% = 1.089 → target = 6.88% × 1.089 = **7.5%**.
- **Sobering expected return** (p. 230): at a maximum realistic SR of 0.4, 7.5% volatility gives
  **3.0% a year** plus the risk-free rate. To do better you must use leverage or cut the
  low-volatility instruments — that is, give up diversification. Costs: 0.032 × 7.5% = **0.24% a
  year**, plus ETF holding costs of 0.05% (S&P tracker) to 0.55% (EM equities).
- **Handcrafted weights under mandate constraints** (p. 230-232): group by region/sub-class, then
  asset class, then across asset classes; wherever the mandate binds, the constraint *is* the
  weight (40% bonds, 30% of equities in EM, 25/25% of bonds). Final weights: US/Euro/UK bonds 6.67%
  each, EM bonds 10%, inflation-linked 10%, the four developed equity ETFs 10.5% each, EM equities
  18%. Instrument diversification multiplier **1.61**.
- **Expressing a house view without trading like a discretionary trader** (p. 232-233). Translate a
  price target into a Sharpe ratio — "Euro Stoxx will hit 3,000" is an 8% rise against 16%
  annualised volatility = **SR 0.50** — then adjust *instrument weights* with **column B ("without
  certainty")** of the SR table, renormalise to 100%, and leave the diversification multiplier
  alone. These adjustments *"should ideally be small and infrequent"*.
- **Weekly rebalancing** is suggested; quarterly for committee-driven funds, annual for amateurs at
  the tax year end.

**The 2008 diary** (p. 234-244) — the instructive numbers:
- At outset, **57% of the portfolio's cash value is in bonds despite a 40% instrument weight** —
  the visible signature of risk parity: lower-risk assets need more cash.
- On 1 October 2008, with strategists "insanely bullish" on equities (SR 0.6) and expecting nothing
  from bonds (SR 0.0), the column-B adjustment moves bond weights by ×0.83 and equity weights by
  ×1.17 — a deliberately modest shift for a strong opinion.
- By the final entry the system is selling equities heavily (Sell 268 UK blocks, Sell 247 Japan).
  Carver's closing observation: **"most of the equity selling is caused by increases in price
  volatility, rather than the changes to instrument weights."** The risk model, not the house view,
  did the de-risking into the crash.

### Ch.15 — Staunch Systems Trader (p. 245-258)

**Core idea.** The full framework, end to end: $250,000, six futures, two rules, four variations,
run part-time on free daily data. This is the chapter to copy if you want a complete worked system.

**Instruments** (Table 42, p. 246) — chosen as one future per asset class, subject to the four-block
minimum-position rule:

| Future | Standardised cost | Currency | Maximum position |
|---|---|---|---|
| Eurodollar (~3 years out) | 0.008 | USD | 8 |
| US 5-year note | 0.004 | USD | 5 |
| Euro Stoxx | 0.002 | EUR | 4 |
| V2TX (European equity volatility) | 0.009 | EUR | 11 |
| MXP/USD | 0.007 | USD | 15 |
| Corn | 0.005 | USD | 9 |

  A US investor ends up in European equities and European volatility *because they are the only
  liquid contracts small enough* — a candid illustration that account size, not view, drives the
  instrument list. Eurodollar is traded three years out to escape the near-zero volatility of the
  front months under ZIRP.
- **Rule selection by cost** (Table 43, p. 248): EWMAC(2,8) turns over 54×/year and needs an
  instrument cheaper than 0.0024 SR — only Euro Stoxx qualifies; EWMAC(4,16) needs 0.0046;
  EWMAC(8,32) is too fast for V2TX. So the example keeps **EWMAC 16/32/64 plus carry** — four
  variations usable on every instrument. Carver insists on **at least three EWMAC variations**,
  since there is no evidence for preferring one.
- **Forecast weights** (p. 249): carry 50%, EWMAC16 21%, EWMAC32 8%, EWMAC64 21%; forecast
  diversification multiplier **1.31**. Cost differences between rules are only 0.031 SR, so no
  Sharpe adjustment is made.
- **Volatility target** (p. 250): out-of-sample bootstrapped back-test SR **0.53** → ×0.75
  pessimism factor → **0.40 realistic** → Table 25 → **20% volatility target** → $50,000
  annualised cash target. Carver notes this is *higher* than he runs his own (25% on a much more
  diversified system — i.e. he is more conservative than his own worked example).
- **Volatility look-back decision, shown as arithmetic** (p. 250-251): weighted average rule
  turnover 9.57 × 1.31 = **12.5**; Table 36 gives 12.6 at the 5-week look-back and 11.7 at 20
  weeks; against V2TX's 0.009 SR that is 0.113 vs 0.105 SR a year. **The 0.008 SR saving isn't
  worth it** — keep the 25-day default (36-day EWMA). At a 20% target, 0.113 SR = a **2.3% annual
  performance drag** on the most expensive instrument, safely inside the 0.13 speed limit.
- **Instrument weights** (p. 251-253): grouped interest rates / equities / FX / commodities.
  Inter-asset correlations of 0.07-0.18 all round to zero → equal weights across groups. But
  **Euro Stoxx needs at least 20% to clear the four-contract minimum**, so equities get 30% instead
  of 25% (two-thirds to Euro Stoxx, one-third to V2TX) and the other three groups take 23.3% each.
  Final: Eurodollar 11.7%, T-note 11.7%, Euro Stoxx 20%, V2TX 9.8%, MXP/USD 23.3%, Corn 23.3%.
  Instrument diversification multiplier **1.89**. Carver flags the adjustment explicitly: *"I'm
  comfortable with this adjustment, since the alternative is not to trade equities at all, but a
  larger shift in weights would concern me."*
- **The diary** (p. 255-257) shows the machinery running: on 15 October 2014, combined forecasts of
  +15.8 (Eurodollar), +20 (T-note, capped), -2.1 (Euro Stoxx), -11.7 (V2TX) produce positions of
  6, 5, 0 and -6 contracts. By 1 December, +$10,000 of profit has raised the capital to $260,000
  and the daily target to $3,250, and the equity rally has flipped Euro Stoxx long. No trade list
  is shown *"because there would have been trading almost every day between these two snapshot
  dates"*.

### Epilogue — What Makes a Good Systematic Trader? (p. 259-260)

The book's own summary, as a list of dispositions rather than techniques:

- **Humble** — underestimate your intelligence, skill and luck. Assume it will go badly.
  *"Don't try anything too clever; it is probably unnecessary and it's more likely to go wrong."*
- **Sceptical** — *"Do not trust anybody"*: not the broker encouraging you to trade, not the
  trainer selling a course, not the author with a system that worked for them — with a footnote
  reading in full: *"This includes me."*
- **Pessimistic** — don't trust back-tests even when honestly built. Ceilings: SR 1.0 for a highly
  diversified systematic system, 0.5 for a semi-automatic trader, 0.4 for an asset allocator.
- **Alert to hidden skew** — steady gains with few losses probably means negative skew that hasn't
  blown up yet; cut the volatility target accordingly.
- **Thoughtful** — know why you might be making money, and why you might not.
- **Thrifty** — know your costs; never spend more than a third of the pessimistic expected Sharpe
  ratio on them. *"Don't make your broker, or market makers, any wealthier."*
- **Nervous** — only capital you can afford to lose; Half-Kelly; maximum diversification; stay away
  from low volatility instruments, *"they're expensive to trade and dangerous"*.
- **Diligent in design, lazy in operation** — *"Put the hard work into designing a safe system that
  you are comfortable with and then do not change it. Make a commitment: don't be tempted to
  meddle, improve or risk manage. These time-consuming activities usually destroy performance."*
- **Lucky** — *"You can't entirely eliminate risk from investing but you should quantify it, and
  make sure you can cope with the likely downside."*

### Appendices (p. 273-300)

- **A — Resources**: further reading and the book's website, systematictrading.org.
- **B — Trading rules**: full specification of EWMAC and carry, plus the generic "A and B" stop
  system used in the early examples.
  - EWMAC: `(fast EWMA − slow EWMA) ÷ standard deviation of daily price changes in price points`,
    then × forecast scalar, then capped at ±20.
  - **Slow look-back is fixed at 4× the fast** (performance was flat for ratios of 2 to 6, so the
    parameter was removed rather than fitted), giving the series 2:8, 4:16, 8:32, 16:64, 32:128,
    64:256 — adjacent pairs correlate 0.90, and anything in between would exceed the 0.95 pruning
    threshold. Beyond 64:256 holding periods get too long to pay.
  - Forecast scalars: **2,8 → 10.6 · 4,16 → 7.5 · 8,32 → 5.3 · 16,64 → 3.75 · 32,128 → 2.65 ·
    64,256 → 1.87**.
  - Carry: annualised, volatility-standardised expected return if prices don't move, specified
    separately for cash FX, spread bets and futures (preferring a contract that is not the nearest).
- **C — Portfolio optimisation**: the bootstrapping procedure, plus the indicative correlation
  tables (50-57) that make handcrafting possible without any back-test.
- **D — Framework details**: the exact formulas for the diversification multiplier, forecast
  scalars, and moving-average / EWMA volatility estimation.

## Citations

> "In every case the accuracy of experts was matched or exceeded by a simple algorithm... Why are
> experts inferior to algorithms? One reason... is that experts try to be clever, think outside the
> box, and consider complex combinations of features in making their predictions. Complexity may
> work in the odd case but more often than not it reduces validity."
> — Daniel Kahneman, quoted as the book's epigraph

> "Humans are better than computers at complex intellectual tasks. But... our emotions prevent us
> from fully utilising this intelligence. The solution is to use systems to make trading decisions."
> (p. 3)

> "Success in systematic trading is mostly down to avoiding common mistakes such as over
> complicating your system, being too optimistic about likely returns, taking excessive risks, and
> trading too often." (p. 6-7)

> "A system which is fully automated but not completely trusted is potentially lethal." (p. 19)

> "If you are making steady profits nearly every day, and most of your trades are winners, then
> there is a good chance you are engaged in negative skew trading. It's just that you haven't yet
> seen any rare large losses." (p. 40)

> "Finding the best trading rules is less important than designing your trading system in the
> correct way." (p. 48)

> "Far too much time and effort is spent by both amateur and professional trading system designers
> in looking for more, and better, trading rules... The average correlation between different rules
> trading a particular instrument is higher than between instruments trading the same rule. So
> diversification amongst instruments is preferable to rule diversification." (p. 68)

> "I was setting stops based on my pain threshold. When I get out of a trade now it is because I
> was wrong."
> — Colm O'Shea, quoted from Schwager's *Hedge Fund Wizards* (p. 95)

> "Deciding your overall trading risk is the most important decision you will have to make when
> designing your trading system." (p. 136)

> "Most cautious ... investors who use Kelly find the frequency of substantial bankroll reductions
> to be uncomfortably large."
> — Ed Thorp, quoted from *Fortune's Formula* (p. 146)

> "Diversification really is the only free lunch in investment." (p. 165)

> "Overtrading is a result of overconfidence." (p. 179)

> "You can eliminate the trades that result from this element by not meddling with your system!"
> (p. 186)

> "Put the hard work into designing a safe system that you are comfortable with and then do not
> change it. Make a commitment: don't be tempted to meddle, improve or risk manage. These
> time-consuming activities usually destroy performance." (p. 260)

> "Do not trust anybody. Don't trust the broker encouraging you to trade more, the trainer peddling
> you an expensive course, or the author with a trading system that apparently worked for them, but
> might not be right for you." — with the footnote: *"This includes me."* (p. 259)

## Esprit critique

**What the book does unusually well.** Almost every prescription comes with the number behind it
and the experiment that produced it. Where most trading books assert that over-fitting is bad,
Carver runs the experiment (90 variations of one rule on gold futures) and reports that *selecting*
the best variation each year returns SR 0.07 while keeping all 90 equally weighted returns 0.33 —
selection is worse than randomness. Where most assert that you should diversify, he derives from
the law of active management how much it is worth. He also routinely argues against his own
interest: he tells you his back-tested SR of 1.0 should be treated as 0.75, then halves it again,
then admits he runs lower still.

**Where the argument is weaker.**

- **The framework is validated largely on the author's own system.** The pessimism factors of Table
  14, the 0.7 subsystem-correlation adjustment, the 2.5 cap on diversification multipliers, the
  four-block minimum — these are presented as general constants but are calibrated on one futures
  portfolio, by one person, over one back-test. They are reasonable and conservative; they are not
  independently established, and the book does not report sensitivity to them.
- **The central argument cuts against verification.** Carver's own statistics say that distinguishing
  two rules requires thirty years of data. That applies to his framework as well: with ten years of
  live evidence there is, on his own showing, no way to demonstrate that handcrafting beats equal
  weights, or that position inertia is free. The intellectual honesty is complete but the consequence
  is that the reader must take most of the design on faith and argument rather than proof.
- **Handcrafting is in-sample and he says so, but the defence is soft.** "Correlations usually don't
  move enough that handcrafted weights would be dramatically different over time" is exactly the kind
  of assumption 2008 punishes — and he elsewhere warns that correlations jump in a crisis, which is
  why he caps the diversification multiplier. The two arguments sit uneasily together.
- **The cost and market data is from 2014-2015 and has aged.** Spread betting economics, ETF
  expense ratios, commission levels and above all the interest rate environment (the book is written
  under ZIRP, and treats the risk-free rate as negligible) have all moved. The *method* for computing
  standardised cost is durable; every specific figure in Tables 34, 35, 42 and 43 needs recomputing
  before use.
- **Almost nothing is said about execution.** The half-the-spread assumption is acknowledged as
  wrong for large orders and then set aside — "you need to do serious research" — which is fine for
  the target reader but leaves a real gap between the book's system and a working one. Similarly,
  futures rolling, data cleaning and back-adjustment (the "Panama method") get a footnote each,
  though they consume much of the effort in practice.
- **The three reader archetypes are a pedagogical device that occasionally strains.** The
  "semi-automatic trader" — someone whose entries are pure discretion but whose exits are wholly
  mechanical — is a coherent design, but the book never confronts the obvious objection that a
  trader whose stop is set by volatility rather than by their thesis will be stopped out of correct
  trades routinely. Carver's own trading diary shows this happening twice and treats it as a feature.
- **The claim that profit targets don't work is asserted, not demonstrated.** "My own research shows
  no evidence that systematic profit targets work consistently" is the whole argument, in a book that
  elsewhere shows its working.

**Two internal slips worth noting** (both caught while reading, neither material): the Ch.12 summary
gives the slowest semi-automatic turnover as 1.8 round trips a year where the body says 2.0, and it
cross-references "table 13 (page 89)" for the Sharpe adjustment factors that are in table 12 on
page 86.

**What has held up.** The 2015 predictions that have since been tested went the right way: that
sustained Sharpe ratios above 1.0 would remain rare; that leverage on low-volatility instruments
would keep blowing people up (written weeks after the Swiss franc de-peg, and applicable without
alteration to the 2018 short-volatility unwind); that retail day trading would remain
overwhelmingly unprofitable. The framework itself has since been released as open-source code
(pysystemtrade), which is the strongest available evidence that the author trades what he wrote.

**Verdict.** The most useful parts are the risk framework (Ch.9-11) and the cost model (Ch.12); they
transfer to any discretionary or systematic process, including ones with nothing to do with futures.
The weakest part is the implicit promise that following the framework produces a profitable system:
it does not, and Carver says as much. What it produces is a system that will not destroy you while
you find out whether your forecasts have any value — which he argues, persuasively, is the only
thing a book can honestly offer.

## Liens

The corpus currently contains no other book, so there is nothing yet to agree or disagree with.
The works Carver leans on most heavily are the natural candidates to read next, and each would
sharpen a specific part of this note:

- **Kahneman, *Thinking, Fast and Slow*** — supplies the cognitive-bias machinery Carver borrows
  wholesale in Ch.1 (prospect theory, narrative fallacy, overconfidence). Reading it would let the
  concept notes on meddling and over-fitting stand on their own evidence rather than on Carver's
  summary.
- **Poundstone, *Fortune's Formula*** — the source Carver cites for Kelly. Would test whether his
  "volatility target = Sharpe ratio" simplification survives contact with the original derivation.
- **Taleb, *The Black Swan* / *Antifragile*** — the direct adversary on [[Skew]]. Carver keeps a
  third of his system in negative-skew strategies and argues the skew premium is real payment for
  real risk; Taleb argues the payment is systematically too small. That is a genuine, testable
  disagreement worth a note of its own.
- **Ilmanen, *Expected Returns*** — Carver explicitly defers to it for the full treatment of where
  returns come from (Ch.2). The obvious source for deepening the risk-premia table.
- **Shefrin, *Beyond Greed and Fear*** — the behavioural-finance overview Carver recommends for the
  disposition effect ("get-evenitis").
- **Lowenstein, *When Genius Failed*** — LTCM as the worked example of leverage plus negative skew
  plus crowding, which Carver invokes three times without developing.
- **Kaufman, *Trading Systems and Methods*** — the thousand-page rule catalogue Carver points to
  precisely because his own book deliberately supplies only two rules.
