"""Watchdog de dérive PAPER vs BACKTEST — déterministe (pas un LLM-loop).

Phase d'attente : on accumule un track record paper avant tout euro réel. Plutôt que
d'attendre la revue manuelle, ce watchdog compare chaque nuit la perf paper RÉELLE
(courbe d'equity Alpaca) aux bornes du backtest preset. S'il DÉRIVE (Sharpe qui
s'effondre, ou drawdown plus profond que le backtest), il alerte (exit≠0 côté CLI).

Métriques via `perf_summary` (source unique de vérité) → cohérence backtest↔paper.
"""

from __future__ import annotations

from packages.portfolio.metrics import perf_summary, returns_from_equity


def drift_report(equity, ref: dict, *, sharpe_drop: float = 1.0,
                 dd_buffer: float = 0.05, min_obs: int = 20) -> dict:
    """Compare une courbe d'equity paper aux bornes backtest `ref` (sharpe, maxDD).

    Dérive si : Sharpe paper < `ref.sharpe − sharpe_drop` OU drawdown paper plus profond
    que `ref.max_drawdown − dd_buffer`. `min_obs` rendements requis (sinon trop tôt).
    Renvoie {available, drift, alerts, paper, ref}.
    """
    r = returns_from_equity([float(x) for x in (equity or [])])
    if r.size < min_obs:
        return {"available": False, "n": int(r.size), "min_obs": min_obs}
    ps = perf_summary(r)
    alerts: list[str] = []
    rs = ref.get("sharpe")
    if rs is not None and ps["sharpe"] < rs - sharpe_drop:
        alerts.append(f"Sharpe paper {ps['sharpe']} < backtest {rs} − {sharpe_drop}")
    rdd = ref.get("max_drawdown")
    if rdd is not None and ps["max_drawdown"] < rdd - dd_buffer:
        alerts.append(f"MaxDD paper {ps['max_drawdown']} plus profond que "
                      f"backtest {rdd} (buffer {dd_buffer})")
    return {"available": True, "drift": bool(alerts), "alerts": alerts,
            "paper": {k: ps[k] for k in ("n", "sharpe", "max_drawdown", "cagr")},
            "ref": ref}
