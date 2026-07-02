---
name: certify
description: Run the certification gates on a component (data source, indicator, factor, strategy, ML model, risk rule) using REAL database data, then record the verdict in vault/15_CERTIFICATION.md. Usage - /certify <type> <name>
disable-model-invocation: true
---

Certify component `$ARGUMENTS` against vault/15_CERTIFICATION.md gates.

1. Identify the component file(s) and its type's gate list.
2. Pull REAL data from the database for the tests (never synthetic - synthetic
   is only allowed inside tests/ for math validation). If real data is
   insufficient, verdict = "BLOCKED - needs real data (N>=X)", never a pass.
3. Run the mechanical gates: packages/testing/certification.py harness
   (certify_indicator / certify_ohlcv), plus type-specific ones (leakage-hunter
   for strategies, sharpe_stats+pbo for backtests, cross_provider for sources).
4. Spawn quant-critic for strategy/model certifications - its FAIL is blocking.
5. Verdict: CERTIFIED / CANDIDATE (list what remains) / REJECTED (reasons).
6. Record in the registry table of vault/15_CERTIFICATION.md with date,
   evidence links, and next re-certification date (+3 months).
7. NEVER soften a rejection. A component that fails one gate fails.
