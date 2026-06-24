"""make event-study TICKER=AAPL — un event a-t-il un impact prix (CAR+placebo) ?

Tout-en-un : charge les prix réels (YAHOO.db), récupère les events (earnings PEAD ou
insiders Form 4), lance event-study + placebo, écrit le verdict dans vault/09_Events/
et logue au ledger. LE gate avant tout ML : significant=False (p≥0.05) → mirage.

Usage :
  make event-study TICKER=AAPL                 # earnings (PEAD) par défaut
  make event-study TICKER=AAPL ARGS="--source insider --post 10"
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_bars(ticker: str, years: int = 10):
    """Barres réelles (base + repli yfinance) — voir packages.data.price_loader."""
    from packages.data.price_loader import load_bars
    return load_bars(ticker, years)


def _earnings_dates(ticker: str):
    """Dates de résultats via yfinance (best-effort). []."""
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).get_earnings_dates(limit=40)
        if df is None:
            return []
        return sorted({d.date() for d in df.index.to_pydatetime()})
    except Exception:  # noqa: BLE001
        return []


def _insider_dates(ticker: str, buys: bool = False):
    """Dates Form 4 du ticker (EDGAR par CIK). `buys` → achats nets seulement. []."""
    try:
        from datetime import date

        from packages.data.sec_insiders import (
            form4_buy_dates_for_ticker,
            form4_dates_for_ticker,
        )
        raw = (form4_buy_dates_for_ticker(ticker) if buys
               else form4_dates_for_ticker(ticker))
        return sorted({date.fromisoformat(d[:10]) for d in raw})
    except Exception:  # noqa: BLE001
        return []


def _bench_returns(bench_tk: str, bar_dates):
    """Rendements du benchmark alignés sur `bar_dates` (0 si date absente)."""
    import numpy as np
    bb = _load_bars(bench_tk)
    if len(bb) < 60:
        return np.zeros(len(bar_dates))
    bc = np.array([x.close for x in bb], float)
    br = bc[1:] / bc[:-1] - 1.0
    m = dict(zip([x.ts.date() for x in bb][1:], br))
    return np.array([m.get(d, 0.0) for d in bar_dates], float)


def _returns_and_events(tk: str, source: str, min_gap: int = 0,
                        bench: str | None = None, buys: bool = False):
    """(returns, event_idx[, bench]) pour un ticker, ou None si données manquantes."""
    import numpy as np

    from packages.research.event_study import dedup_events, event_indices
    bars = _load_bars(tk)
    if len(bars) < 60:
        return None
    closes = np.array([b.close for b in bars], float)
    rets = closes[1:] / closes[:-1] - 1.0
    bar_dates = [b.ts.date() for b in bars][1:]
    ev = _earnings_dates(tk) if source == "earnings" else _insider_dates(tk, buys)
    idx = dedup_events(event_indices(bar_dates, ev), min_gap)
    if len(idx) < 3:
        return None
    if bench:
        return (rets, idx, _bench_returns(bench, bar_dates))
    return (rets, idx)


def _run_basket(tickers: list[str], source: str, post: int, min_gap: int = 0,
                bench: str | None = None, buys: bool = False) -> int:
    from packages.research.event_study import aggregate_significance
    series = {}
    for tk in tickers:
        s = _returns_and_events(tk.upper(), source, min_gap, bench, buys)
        if s:
            series[tk.upper()] = s
    if len(series) < 2:
        print(f"❌ trop peu de tickers ({len(series)}). Vérifie la source/base.")
        return 1
    res = aggregate_significance(series, post=post, n_sims=1000, seed=7)
    sig = res.get("significant")
    verdict = "✅ SIGNIFICATIF (cross-sect.)" if sig else "❌ NON significatif"
    flags = (f"{' · achats' if buys else ''}"
             f"{f' · gap={min_gap}j' if min_gap else ''}"
             f"{f' · vs {bench}' if bench else ''}")
    print(f"\nEvent-study PANIER · {source} · {res['n_assets']} tickers · "
          f"{res['n_events']} events · post={post}j{flags}")
    print(f"  CAR moyen poolé : {res['mean_car']*100:+.2f}%")
    print(f"  t-stat          : {res['t_stat']}")
    print(f"  p-value placebo : {res['placebo_p_value']}")
    print(f"  → {verdict}")
    if sig:
        print("  GO : le PEAD généralise → backteste pead_signal (DSR/PBO).")
    else:
        print("  STOP : pas d'edge cross-sect. → AAPL seul = probablement chance.")
    _write_basket_note(source, post, res)
    _log_basket(source, res)
    return 0


def main() -> int:
    import numpy as np

    from packages.research.event_study import (
        dedup_events,
        event_indices,
        significance,
    )

    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="AAPL")
    ap.add_argument("--tickers", default="", help="panier 'AAPL,MSFT' (cross-sect.)")
    ap.add_argument("--source", default="earnings", choices=["earnings", "insider"])
    ap.add_argument("--post", type=int, default=5)
    ap.add_argument("--min-gap-days", type=int, default=0,
                    help="dé-chevauche les events (anti-autocorrélation)")
    ap.add_argument("--benchmark", default="", help="CAR relatif (ex. SPY, QQQ)")
    ap.add_argument("--buys", action="store_true",
                    help="insider: achats nets seulement (Form 4 XML)")
    a = ap.parse_args()
    bench = a.benchmark.strip().upper() or None
    if a.tickers.strip():
        tks = [t.strip() for t in a.tickers.split(",") if t.strip()]
        return _run_basket(tks, a.source, a.post, a.min_gap_days, bench, a.buys)
    tk = a.ticker.upper()

    bars = _load_bars(tk)
    if len(bars) < 60:
        print(f"❌ pas assez de prix pour {tk} ({len(bars)} barres). "
              "Branche QUANT_PRICE_DB / YAHOO.db.")
        return 1
    closes = np.array([b.close for b in bars], float)
    rets = closes[1:] / closes[:-1] - 1.0
    bar_dates = [b.ts.date() for b in bars][1:]            # aligné sur rets

    if a.source == "earnings":
        ev_dates = _earnings_dates(tk)
    else:
        ev_dates = _insider_dates(tk, a.buys)
    idx = dedup_events(event_indices(bar_dates, ev_dates), a.min_gap_days)
    if len(idx) < 3:
        print(f"❌ trop peu d'events {a.source} pour {tk} ({len(idx)}). "
              "Essaie --source insider, ou un ticker plus suivi.")
        return 1

    bench_ret = _bench_returns(bench, bar_dates) if bench else None
    res = significance(rets, idx, post=a.post, bench_ret=bench_ret,
                       n_sims=1000, seed=7)
    sig = res.get("significant")
    verdict = "✅ SIGNIFICATIF" if sig else "❌ NON significatif (mirage)"
    print(f"\nEvent-study {tk} · {a.source} · post={a.post}j · {res['n']} events")
    print(f"  CAR moyen   : {res['mean_car']*100:+.2f}%")
    print(f"  t-stat      : {res['t_stat']}")
    print(f"  p-value placebo : {res['placebo_p_value']}")
    print(f"  → {verdict}")
    if not res.get("significant"):
        print("  STOP : pas d'edge prouvé → on ne code PAS le ML/LLM dessus.")
    else:
        print("  GO : feu vert ML/LLM (extraction as-of → triple-barrier).")

    _write_note(tk, a.source, a.post, res)
    _log(tk, a.source, res)
    return 0


def _write_note(tk: str, source: str, post: int, res: dict) -> None:
    try:
        d = ROOT / "vault" / "09_Events"
        d.mkdir(parents=True, exist_ok=True)
        today = datetime.now(UTC).date().isoformat()
        (d / f"{tk}.md").write_text(
            f"---\ntype: event_study_result\nticker: {tk}\nevent_type: {source}\n"
            f"n: {res['n']}\nmean_car: {res['mean_car']}\nt_stat: {res['t_stat']}\n"
            f"placebo_p_value: {res['placebo_p_value']}\n"
            f"significant: {str(res['significant']).lower()}\npost: {post}\n"
            f"date: {today}\n---\n\n# 🛰️ Event-study {tk} ({source})\n\n"
            f"CAR moyen {res['mean_car']*100:+.2f}% · t={res['t_stat']} · "
            f"p_placebo={res['placebo_p_value']} → "
            f"{'edge candidat' if res['significant'] else 'mirage'}.\n",
            encoding="utf-8")
        print(f"  📝 note → vault/09_Events/{tk}.md")
    except OSError:
        pass


def _write_basket_note(source: str, post: int, res: dict) -> None:
    try:
        d = ROOT / "vault" / "09_Events"
        d.mkdir(parents=True, exist_ok=True)
        today = datetime.now(UTC).date().isoformat()
        (d / f"_BASKET_{source}.md").write_text(
            f"---\ntype: event_study_result\nticker: PANIER\nevent_type: {source}\n"
            f"n: {res['n_events']}\nn_assets: {res['n_assets']}\n"
            f"mean_car: {res['mean_car']}\n"
            f"t_stat: {res['t_stat']}\nplacebo_p_value: {res['placebo_p_value']}\n"
            f"significant: {str(res['significant']).lower()}\npost: {post}\n"
            f"date: {today}\n---\n\n"
            f"# 🛰️ Event-study PANIER ({source})\n\n"
            f"{res['n_assets']} tickers · CAR {res['mean_car']*100:+.2f}% · "
            f"t={res['t_stat']} · p={res['placebo_p_value']} → "
            f"{'edge cross-sectionnel' if res['significant'] else 'mirage'}.\n",
            encoding="utf-8")
        print(f"  📝 note → vault/09_Events/_BASKET_{source}.md")
    except OSError:
        pass


def _log_basket(source: str, res: dict) -> None:
    try:
        from packages.research.ledger import append_record
        append_record({
            "date": datetime.now(UTC).date().isoformat(),
            "facteur": f"event_{source}_basket",
            "classe": ["equity"], "horizon": "swing",
            "dsr": None, "pbo": res["placebo_p_value"],
            "statut": "en_test" if res["significant"] else "rejete",
            "these": f"Event-study panier {source} ({res['n_assets']} tickers) : "
                     f"CAR {res['mean_car']*100:+.2f}%, p={res['placebo_p_value']}.",
        })
    except Exception:  # noqa: BLE001
        pass


def _log(tk: str, source: str, res: dict) -> None:
    try:
        from packages.research.ledger import append_record
        append_record({
            "date": datetime.now(UTC).date().isoformat(), "facteur": f"event_{source}",
            "classe": ["equity"], "horizon": "swing",
            "dsr": None, "pbo": res["placebo_p_value"],
            "statut": "en_test" if res["significant"] else "rejete",
            "these": f"Event-study {tk}/{source} : CAR {res['mean_car']*100:+.2f}%, "
                     f"placebo p={res['placebo_p_value']}.",
        })
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    raise SystemExit(main())
