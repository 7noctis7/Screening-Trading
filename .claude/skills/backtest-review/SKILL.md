---
name: backtest-review
description: Run the institutional backtest review - quant-critic sub-agent verdict, deflated Sharpe sanity, then record result in vault/10_BACKTEST_RESULTS.md with config hash. Use after any backtest.
---

1. Identify the backtest: strategy file, config YAML, results (tear sheet / metrics).
2. Compute the config hash: `sha256sum` of the strategy file + its YAML → short hash.
3. Spawn **quant-critic** with paths to strategy, config, results. Get the verdict.
4. If FAIL: report blocking issues, do NOT record the result. Stop.
5. If PASS (or reservations): append to `vault/10_BACKTEST_RESULTS.md`:
   date, strategy, config hash, period, N trades, gross/net Sharpe, deflated
   Sharpe (with trial count!), max DD + duration, turnover, verdict, reservations.
6. Increment the trial counter for this strategy family in the same file —
   every experiment counts toward multiple-testing correction, including failures.
