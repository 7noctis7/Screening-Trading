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
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_bars(ticker: str, years: int = 10):
    """Bars réels depuis la base (QUANT_PRICE_DB / YAHOO.db). [] si indispo."""
    try:
        from apps.api.snapshot import _price_db_path
        from packages.data.providers.db_provider import DBPriceProvider
        db = _price_db_path()
        if not db:
            return []
        start = datetime.now(UTC) - timedelta(days=365 * years)
        return DBPriceProvider(db).fetch_ohlcv(ticker, "1d", start)  # bars réels
    except Exception as e:  # noqa: BLE001
        print(f"⚠ chargement prix échoué : {e}")
        return []


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


def _insider_dates(ticker: str):
    """Dates de dépôts Form 4 pour le ticker (EDGAR full-text, best-effort). []."""
    try:
        from datetime import date

        from packages.data.sec_insiders import fetch_recent_form4
        out = []
        for f in fetch_recent_form4(limit=200):
            if f.get("ticker") == ticker and f.get("date"):
                out.append(date.fromisoformat(str(f["date"])[:10]))
        return sorted(set(out))
    except Exception:  # noqa: BLE001
        return []


def main() -> int:
    import numpy as np

    from packages.research.event_study import event_indices, significance

    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="AAPL")
    ap.add_argument("--source", default="earnings", choices=["earnings", "insider"])
    ap.add_argument("--post", type=int, default=5)
    a = ap.parse_args()
    tk = a.ticker.upper()

    bars = _load_bars(tk)
    if len(bars) < 60:
        print(f"❌ pas assez de prix pour {tk} ({len(bars)} barres). "
              "Branche QUANT_PRICE_DB / YAHOO.db.")
        return 1
    closes = np.array([b.close for b in bars], float)
    rets = closes[1:] / closes[:-1] - 1.0
    bar_dates = [b.ts.date() for b in bars][1:]            # aligné sur rets

    ev_dates = _earnings_dates(tk) if a.source == "earnings" else _insider_dates(tk)
    idx = event_indices(bar_dates, ev_dates)
    if len(idx) < 3:
        print(f"❌ trop peu d'events {a.source} pour {tk} ({len(idx)}). "
              "Essaie --source insider, ou un ticker plus suivi.")
        return 1

    res = significance(rets, idx, post=a.post, n_sims=1000, seed=7)
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
