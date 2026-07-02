"""Smoke tests on synthetic data: every module runs and the math behaves."""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd

from packages.risk.convex_drawdown_scaler import DrawdownScaler, current_drawdown
from packages.risk.correlation_shock import mean_pairwise_corr, shock_multiplier
from packages.risk.atr_stops import atr, stop_levels, time_stop_hit
from packages.portfolio.sizing.vol_target import final_weight, realized_vol
from packages.portfolio.sizing.kelly_uncertain import sized_kelly, kelly_fraction
from packages.portfolio.rebalance_bands import rebalance_orders
from packages.screening.expectancy_filter import evaluate_setup
from packages.backtest.validation.sharpe_stats import sr_moments, psr, deflated_sr, min_trl
from packages.backtest.validation.pbo import pbo_cscv
from packages.reporting.mfe_mae import analyze
from packages.data.quality.cross_provider import diff_report

rng = np.random.default_rng(7)
ok = 0

# 1. DD scaler: monotone, respects bounds
ds = DrawdownScaler()
assert ds.multiplier(-0.05) == 1.0 and abs(ds.multiplier(-0.15) - 0.75) < 1e-9
assert ds.multiplier(-0.25) == 0.375 and ds.multiplier(-0.31) == 0.0
assert abs(current_drawdown([100, 120, 90]) - (-0.25)) < 1e-9; ok += 1

# 2. Corr shock
r = pd.DataFrame(rng.normal(0, 0.01, (100, 5)))
common = rng.normal(0, 0.01, 100)
r_cr = r.add(common * 3, axis=0)
lo, hi = mean_pairwise_corr(r), mean_pairwise_corr(r_cr)
assert hi > 0.8 > lo and shock_multiplier(hi) < shock_multiplier(lo) == 1.0; ok += 1

# 3. ATR stops
px = pd.DataFrame({"high": 101 + rng.normal(0, 1, 50).cumsum(),
                   "low": 99 + rng.normal(0, 1, 50).cumsum(),
                   "close": 100 + rng.normal(0, 1, 50).cumsum()})
px["high"] = px[["high", "low", "close"]].max(axis=1) + 0.5
px["low"] = px[["high", "low", "close"]].min(axis=1) - 0.5
a = atr(px).iloc[-1]
lv = stop_levels(100, a, "long", k_sl=2.5, k_tp=5.0)
assert lv["sl"] < 100 < lv["tp"] and time_stop_hit(25, 20, 0.0); ok += 1

# 4. Sizing: vol-target + conviction + risk multipliers compose
w = final_weight(asset_vol=0.40, p_calibrated=0.60, dd_mult=0.5, corr_mult=1.0)
w_full = final_weight(asset_vol=0.40, p_calibrated=0.60, dd_mult=1.0, corr_mult=1.0)
assert 0 < w == 0.5 * w_full; ok += 1

# 5. Kelly under uncertainty: shrinks with fewer trades, capped, never <0
assert sized_kelly(0.55, 2.0, n_trades=30) < sized_kelly(0.55, 2.0, n_trades=1000)
assert sized_kelly(0.30, 1.0, 100) == 0.0 and sized_kelly(0.9, 5, 10000) <= 0.05; ok += 1

# 6. Band rebalancing: small drifts ignored, breaches traded
cur = pd.Series({"A": 0.22, "B": 0.10, "C": 0.099})
tgt = pd.Series({"A": 0.15, "B": 0.10, "C": 0.10})
vols = pd.Series({"A": 0.2, "B": 0.2, "C": 0.2})
o = rebalance_orders(cur, tgt, vols)
assert o["A"] < 0 and o["B"] == 0 and o["C"] == 0; ok += 1

# 7. Expectancy filter: RR 2 @ p=0.30 rejected, RR 1.5 @ p=0.55 accepted
assert not evaluate_setup(0.30, 2.0).accept and evaluate_setup(0.55, 1.5).accept; ok += 1

# 8. PSR/DSR/MinTRL: skilled series passes, noise fails
skilled = rng.normal(0.001, 0.01, 1000)   # SR_daily = 0.1
noise = rng.normal(0.0, 0.01, 1000)
sr, sk, ku, n = sr_moments(skilled)
assert psr(sr, sk, ku, n) > 0.95
sr2, sk2, ku2, n2 = sr_moments(noise)
assert psr(sr2, sk2, ku2, n2) < 0.95
assert deflated_sr(skilled, n_trials=1, var_sr_across_trials=0.0) > 0.95
assert deflated_sr(skilled, n_trials=10000, var_sr_across_trials=0.02) < deflated_sr(skilled, 2, 0.001)
m = min_trl(sr, sk, ku)
assert 100 < m < 1000; ok += 1  # ~ (1.645/0.1)^2 ≈ 271 days

# 9. PBO: pure-noise config family => PBO ~ 0.5 ; one truly skilled config => low PBO
M_noise = rng.normal(0, 0.01, (750, 40))
p1 = pbo_cscv(M_noise)["pbo"]
M_skill = M_noise.copy(); M_skill[:, 7] += 0.0015
p2 = pbo_cscv(M_skill)["pbo"]
assert 0.3 < p1 < 0.7 and p2 < 0.2, (p1, p2); ok += 1

# 10. MFE/MAE recommendations trigger correctly
j = pd.DataFrame({
    "r_multiple": [2.0, 1.5, -1.0, -1.0, 1.8, -1.0, 2.2, 1.2],
    "mfe_R":      [3.5, 2.8,  0.9,  0.2, 3.0,  0.8, 4.0, 2.5],
    "mae_R":      [0.9, 0.95, 1.0,  1.0, 0.85, 1.0, 0.9, 0.92],
    "win":        [True, True, False, False, True, False, True, True]})
rep = analyze(j)
assert rep["profit_factor"] > 1 and any("TOO TIGHT" in r for r in rep["recommendations"]); ok += 1

# 11. Cross-provider diff: clean match passes, corrupted print flagged
idx = pd.date_range("2026-01-01", periods=200, freq="D", tz="UTC")
pa = pd.DataFrame({"close": 100 + rng.normal(0, 1, 200).cumsum()}, index=idx)
pb = pa.copy(); rep1 = diff_report(pa, pb)
pb2 = pa.copy(); pb2.iloc[50:60] *= 1.05
rep2 = diff_report(pa, pb2)
assert rep1["flagged"] == 0 and not rep1["quarantine"]
assert rep2["flagged"] >= 10 and rep2["quarantine"]; ok += 1

print(f"ALL {ok}/11 CHECKS PASSED")
print(f"  DD scaler @-15%: x{DrawdownScaler().multiplier(-0.15)}")
print(f"  Kelly(p=.55,b=2,n=30): {sized_kelly(0.55,2.0,30):.4f} vs n=1000: {sized_kelly(0.55,2.0,1000):.4f} (pure Kelly: {kelly_fraction(0.55,2.0):.3f})")
print(f"  MinTRL(SR_d=0.1): {m:.0f} jours de track record avant live")
print(f"  PBO bruit pur: {p1:.2f} | avec 1 config skillee: {p2:.2f}")
print(f"  Reco MFE/MAE: {rep['recommendations'][0][:70]}...")
