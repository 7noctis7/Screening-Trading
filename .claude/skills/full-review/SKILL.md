---
name: full-review
description: Full-project institutional review in one run - repository architecture, Obsidian vault coherence, real database quality, leakage scan, top1pct-pack integration plan. Writes vault/14_FULL_REVIEW.md and updates TODO. Long-running.
disable-model-invocation: true
---

Complete review, in phases. Work read-only until Phase 6. Keep a running
scoreboard. If a phase fails, note it and continue.

## Phase 0 — Ritual & safety (5 min)
Run the /session-open ritual. Verify `git status` is clean and we are on a
branch (create `full-review-YYYYMMDD` if on main). NO work on main.

## Phase 1 — Parallel deep scans (spawn 3 sub-agents AT ONCE)
- **vault-architect**: code <-> Mermaid drift, vault hygiene, config truth.
- **leakage-hunter**: full scan of packages/ for look-ahead/leakage.
- **db-auditor**: real-database audit (duplicates, gaps, point-in-time,
  journal completeness).
Collect all three reports.

## Phase 2 — Repository architecture audit (main context)
Against CLAUDE.md rules: files > 400 lines or functions > 50 (list them);
plugin pattern respected (adding a strategy = 1 file?); `packages/core`
truly dependency-free (check imports); hardcoded thresholds that belong in
config/ YAML; test coverage per package (which packages have NO tests);
secrets accidentally committed (grep api_key/secret/token patterns).

## Phase 3 — Quant-quality audit
Spawn **quant-critic** on the most recent backtest/strategy results found in
the repo or vault/10_BACKTEST_RESULTS.md. Additionally check: costs modeled
per asset class? trial counter present? walk-forward vs in-sample separated?

## Phase 4 — top1pct-pack integration readiness
For each module of the pack (convex_drawdown_scaler, vol_target,
kelly_uncertain, rebalance_bands, expectancy_filter, atr_stops,
sharpe_stats, pbo, mfe_mae, cross_provider): does the insertion point exist
in the current code (Sizer interface, risk engine, journal schema...)? Mark
READY / NEEDS-PREREQ (name the prereq) / BLOCKED.

## Phase 5 — Synthesis
Write `vault/14_FULL_REVIEW.md`: executive summary (10 lines max), health
scores /10 (architecture, data, quant discipline, vault sync), the full
findings tables from every phase, and a prioritized fix list P0/P1/P2 where
P0 = anything that invalidates results (leaks, duplicates, missing
point-in-time) — P0s outrank ALL new features.
Update `vault/03_TODO.md` with the new items. Run /vault-sync if available.

## Phase 6 — Apply (ONLY with explicit user approval, item by item)
Present the P0 list. For each approved item: smallest possible change,
run `pytest -q && ruff check .`, atomic commit. Stop after P0s — P1/P2 are
for the next session. Close with /session-close.

Rules: never fabricate findings; every claim cites file:line or a query
result. Paper trading rules remain absolute. If context gets heavy, push
detail into the report file and keep the conversation to decisions.

## REAL-DATA MANDATE (absolute)
Every parameter, threshold, calibration and recommendation produced by this
review MUST be derived from the user's REAL database and trade journal:
- MFE/MAE recommendations: computed on the actual journal table only.
- Expectancy filter inputs: actual per-strategy win rates from the journal,
  passed through shrunk_p() — never assumed probabilities.
- Vol targets / ATR multiples: from actual stored price history.
- If real data is insufficient for a calibration (N too small, table empty),
  SAY SO and fall back to the conservative defaults in config/risk_top1pct.yaml
  with an explicit "UNCALIBRATED — needs N>=X real trades" flag in the report.
NEVER generate, simulate or invent data to fill a gap. Synthetic data is
allowed for ONE purpose only: unit tests of the math (tests/), never for
calibration, thresholds, or any number that reaches the report or the vault.
