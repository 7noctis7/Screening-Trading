"""Backtest PEAD (earnings drift) — récupère les dates de résultats via yfinance (gratuit).

  python scripts/backtest_earnings.py --assets 40 --hold 21

Pour chaque action : dates de résultats (yfinance) + prix (snapshot réel/synthétique) →
event study PEAD. Métriques : rendement moyen/médian, win rate, t-stat, edge vs marché.
yfinance requis (pip install yfinance) + réseau. Honnête : si t-stat faible → pas d'edge.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _earnings_dates(symbol: str) -> list:
    """Dates de résultats passées via yfinance (gratuit). [] si indisponible."""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).get_earnings_dates(limit=24)
        if df is None or df.empty:
            return []
        return [ts.to_pydatetime() for ts in df.index]
    except Exception:  # noqa: BLE001
        return []


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest PEAD (earnings drift)")
    ap.add_argument("--assets", type=int, default=40)
    ap.add_argument("--hold", type=int, default=21)
    a = ap.parse_args()

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _seed_universe, _sector_of,
                                   datetime, timedelta, timezone)
    from packages.strategies.earnings_pead import pead_backtest

    instruments = _seed_universe()
    acmap = {m["symbol"]: m["asset_class"] for m in instruments}
    sector_of = {m["symbol"]: _sector_of(m) for m in instruments}
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode = _load_prices(instruments, sector_of, end - timedelta(days=_HISTORY_DAYS), end, 7)
    eqs = [s for s in data if acmap.get(s) in ("equity", "etf")][:a.assets]
    print(f"Mode des données : {mode} · {len(eqs)} actions · récupération des dates de résultats (yfinance)…")
    earnings = {}
    for s in eqs:
        d = _earnings_dates(s)
        if d:
            earnings[s] = d
    print(f"Dates de résultats trouvées pour {len(earnings)}/{len(eqs)} actions.")
    res = pead_backtest({s: data[s] for s in eqs}, earnings, hold=a.hold)
    if not res.get("available"):
        print(f"Indisponible ({res.get('n_events', 0)} évènements — pas assez de données yfinance)."); return
    print(f"\n  PEAD ({res['n_events']} évènements · détention {res['hold_days']} j) :")
    print(f"    rendement moyen   {res['mean_return']*100:+.2f}%   médian {res['median_return']*100:+.2f}%")
    print(f"    win rate          {res['win_rate']*100:.0f}%")
    print(f"    t-stat            {res['t_stat']:+.2f}   (|t|>2 = significatif)")
    print(f"    Sharpe / trade    {res['sharpe_per_trade']:+.3f}")
    print(f"    edge vs marché    {res['edge_vs_market']*100:+.2f}%  (PEAD − long passif même fenêtre)")
    print("\n→ Edge crédible si t-stat > 2 ET edge vs marché > 0. Sinon : pas d'anomalie exploitable ici.")


if __name__ == "__main__":
    main()
