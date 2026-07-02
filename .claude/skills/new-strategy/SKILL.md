---
name: new-strategy
description: Scaffold a new trading strategy as a self-registering plugin - strategy file, config YAML, tests, vault spec entry. Usage - /new-strategy <name> <archetype>
disable-model-invocation: true
---

Scaffold strategy `$ARGUMENTS` WITHOUT touching core code:

1. Read one existing strategy in `packages/strategies/` as the reference pattern
   (registry decorator, `Strategy` interface from `packages/core`).
2. Create `packages/strategies/<name>.py` (< 300 lines): docstring with
   hypothesis + favorable regime, entry/exit signals, position management hooks
   (trailing stop ATR, break-even, scaling). Self-register in the registry.
3. Create `config/strategies/<name>.yaml`: params, universe, regime activation,
   risk overrides. Nothing hard-coded in the .py.
4. Create `tests/strategies/test_<name>.py`: signal correctness on synthetic
   data, no-look-ahead test (truncate data at t, assert signal unchanged),
   registry discovery test.
5. Add spec entry to `vault/06_STRATEGIES.md` (hypothesis, regime, R:R, status: RESEARCH).
6. Run the tests. Then spawn `leakage-hunter` scoped to the new file.
7. Remind: backtest via /backtest-review before any paper allocation.
