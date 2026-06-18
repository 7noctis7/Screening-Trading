"""Backtest event-study du signal SENTIMENT : a-t-il un edge prédictif ? (mesurer avant d'investir).

Pour chaque news datée : score de sentiment → rendement réalisé sur `hold` jours APRÈS la
publication (point-in-time, entrée à J+1). On mesure :
  - **IC** (corrélation de Spearman-like via Pearson sur rangs) entre sentiment et rendement futur ;
  - rendement moyen des news positives vs négatives ;
  - **DSR** d'une stratégie long-positif / short-négatif (juge de paix anti-surapprentissage).
Nécessite un historique de news daté (`data/news.csv`). numpy pur.
"""

from __future__ import annotations

import numpy as np

from packages.portfolio.psr import deflated_sharpe_ratio
from packages.sentiment.lexicon import score_text


def _idx_ge(dates: list, d) -> int | None:
    lo, hi = 0, len(dates)
    while lo < hi:
        mid = (lo + hi) // 2
        if dates[mid] < d:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(dates) else None


def sentiment_event_study(data: dict, news: list[dict], hold: int = 5, entry_lag: int = 1) -> dict:
    """`news`: [{symbol, date(datetime/date), headline}]. `data`: {sym: bars(.ts,.close)}."""
    scores, fwd = [], []
    pos, neg = [], []
    for ev in news:
        sym = ev.get("symbol")
        bars = data.get(sym)
        if not bars or not ev.get("headline") or ev.get("date") is None:
            continue
        sc = score_text(ev["headline"])
        if sc == 0.0:
            continue
        dates = [b.ts.date() if hasattr(b.ts, "date") else b.ts for b in bars]
        closes = [b.close for b in bars]
        d = ev["date"].date() if hasattr(ev["date"], "date") else ev["date"]
        i = _idx_ge(dates, d)
        if i is None:
            continue
        entry, ex = i + entry_lag, i + entry_lag + hold
        if ex >= len(closes) or closes[entry] <= 0:
            continue
        r = closes[ex] / closes[entry] - 1
        scores.append(sc); fwd.append(r)
        (pos if sc > 0 else neg).append(r)
    if len(scores) < 20:
        return {"available": False, "reason": f"trop peu d'événements exploitables ({len(scores)})"}
    s = np.array(scores); f = np.array(fwd)
    # IC = corrélation de rang (Pearson sur les rangs)
    ic = float(np.corrcoef(s.argsort().argsort(), f.argsort().argsort())[0, 1])
    # stratégie : +1 si sentiment>0, -1 sinon, rendement réalisé
    strat = np.where(s > 0, 1.0, -1.0) * f
    sd = float(strat.std())
    per_year = 252.0 / hold
    sharpe = float(strat.mean() / sd * np.sqrt(per_year)) if sd > 0 else 0.0
    dsr = deflated_sharpe_ratio(float(strat.mean() / sd) if sd > 0 else 0.0, len(strat), n_trials=10)
    return {"available": True, "n_events": len(scores), "ic": round(ic, 4),
            "mean_fwd_positive": round(float(np.mean(pos)) if pos else 0.0, 4),
            "mean_fwd_negative": round(float(np.mean(neg)) if neg else 0.0, 4),
            "sharpe": round(sharpe, 2), "dsr": round(dsr, 3), "hold_days": hold,
            "verdict": ("Edge sentiment plausible" if dsr >= 0.9 and abs(ic) > 0.03 else
                        "Pas d'edge sentiment prouvé (IC≈0 / DSR≈0) — ne pas surpondérer le NLP")}
