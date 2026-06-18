"""Calibration du preset : balaye (vol-cible × DD-cible × top-K × bande) et classe les combos par
**Sharpe déflaté** (DSR) — qui pénalise le nombre d'essais → anti-surapprentissage. Le DSR, pas le
CAGR, est le juge de paix : une combo qui gagne par chance sur N essais est démasquée.
"""

from __future__ import annotations

from itertools import product

from packages.backtest.preset_backtest import preset_backtest
from packages.portfolio.psr import deflated_sharpe_ratio


def calibrate_preset(data: dict, quality: dict, asset_classes: dict | None = None,
                     dd_targets=(0.15, 0.25, 0.35), top_ks=(15, 20, 30),
                     bands=(0.0, 0.03, 0.06), step: int = 21) -> dict:
    """Renvoie les combos triés par DSR (puis Sharpe), avec la meilleure mise en avant."""
    grid = list(product(dd_targets, top_ks, bands))
    n_trials = len(grid)
    per_year = 252.0 / step
    rows = []
    for dd, tk, band in grid:
        r = preset_backtest(data, quality, asset_classes=asset_classes,
                            dd_target=dd, band=band, top_k=tk, step=step)
        st = r.get("preset") if r.get("available") else None
        if not st or not st.get("available"):
            continue
        n = len(r["curves"]["preset"]) - 1
        sr_period = st["sharpe"] / (per_year ** 0.5) if st["sharpe"] else 0.0
        dsr = deflated_sharpe_ratio(sr_period, max(n, 3), n_trials=n_trials)
        rows.append({"dd_target": dd, "top_k": tk, "band": band,
                     "cagr": st["annualized"], "sharpe": st["sharpe"],
                     "max_drawdown": st["max_drawdown"], "dsr": dsr,
                     "turnover_annual": r["turnover_annual"]})
    if not rows:
        return {"available": False}
    rows.sort(key=lambda x: (x["dsr"], x["sharpe"]), reverse=True)
    return {"available": True, "n_trials": n_trials, "step_days": step,
            "best": rows[0], "results": rows,
            "note": "Classement par Sharpe déflaté (pénalise les essais multiples). "
                    "Si le meilleur DSR reste ~0, AUCUNE combo n'a d'edge robuste → garder la plus "
                    "défensive (DD-cible bas, bande haute, turnover bas)."}
