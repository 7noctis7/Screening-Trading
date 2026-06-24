"""PEAD — Post-Earnings Announcement Drift (signal point-in-time, 0 dépendance).

Thèse : sous-réaction aux surprises de résultats → le cours dérive dans le sens de la
surprise plusieurs semaines (attention limitée, limites à l'arbitrage). On capture la
dérive DEPUIS l'annonce : rendement cumulé post-annonce. Point-in-time (barres ≤ t,
dates d'annonce passées ; dates d'earnings via yfinance, fournies au signal).
"""

from __future__ import annotations

from datetime import date


def _bar_date(b) -> date:
    ts = getattr(b, "ts", None)
    return ts.date() if hasattr(ts, "date") else ts


def pead_signal(bars: list, earnings_dates: list, t: int | None = None,
                drift_window: int = 20) -> float:
    """Dérive post-résultats à l'instant `t`.

    Si une annonce ∈ `earnings_dates` tombe dans les `drift_window` dernières barres,
    renvoie `close[t] / close[annonce] - 1` (la dérive à exploiter). Sinon `nan`.
    """
    if not bars or not earnings_dates:
        return float("nan")
    t = (len(bars) - 1) if t is None else min(t, len(bars) - 1)
    dates = [_bar_date(b) for b in bars]
    past = sorted(e for e in earnings_dates if e <= dates[t])
    if not past:
        return float("nan")
    last_e = past[-1]
    # 1re barre à/après l'annonce
    ev = next((i for i, d in enumerate(dates) if d >= last_e), None)
    if ev is None or ev > t or (t - ev) > drift_window:
        return float("nan")
    c0 = bars[ev].close
    return float(bars[t].close / c0 - 1.0) if c0 else float("nan")
