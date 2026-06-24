"""make funding-study — un funding crypto extrême précède-t-il une reversion ?

Fade le positionnement : funding très positif → short, très négatif → long. Charge
le funding (Binance/Bybit, sans clé) + les prix (yfinance), aligne en quotidien,
z-score causal, event-study signé + placebo. Le gate AVANT tout backtest.

  make funding-study
  make funding-study ARGS="--symbols BTC,ETH,SOL --threshold 2 --post 5"
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_SYMBOLS = "BTC,ETH,SOL,XRP,ADA,DOGE,AVAX,LINK"


def _series(symbol: str, window: int):
    """(rets, fund_z) alignés en quotidien pour un symbole, ou None."""
    import numpy as np

    from packages.data.funding import daily_funding, fetch_funding
    from packages.data.price_loader import load_bars
    from packages.research.funding_study import zscore_causal
    fund = daily_funding(fetch_funding(symbol, limit=1000))
    if len(fund) < 60:
        return None
    bars = load_bars(f"{symbol}-USD", years=5)
    if len(bars) < 60:
        return None
    closes = np.array([b.close for b in bars], float)
    rets = closes[1:] / closes[:-1] - 1.0
    bar_dates = [b.ts.date() for b in bars][1:]
    f_aligned = np.array([fund.get(d, 0.0) for d in bar_dates], float)
    if np.count_nonzero(f_aligned) < 60:
        return None
    return rets, zscore_causal(f_aligned, window)


def main() -> int:
    ap = argparse.ArgumentParser(description="Event-study funding crypto (reversion)")
    ap.add_argument("--symbols", default=_SYMBOLS)
    ap.add_argument("--post", type=int, default=5)
    ap.add_argument("--threshold", type=float, default=1.5)
    ap.add_argument("--window", type=int, default=30)
    a = ap.parse_args()
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]

    from packages.research.funding_study import aggregate_significance
    print(f"Chargement funding + prix pour {len(syms)} cryptos…")
    series = {}
    for s in syms:
        v = _series(s, a.window)
        if v:
            series[s] = v
    if len(series) < 2:
        print(f"❌ trop peu de cryptos exploitables ({len(series)}). "
              "Binance/Bybit bloqué ? Réessaie depuis ton Mac.")
        return 1

    res = aggregate_significance(series, post=a.post, threshold=a.threshold,
                                 n_sims=1000, seed=7)
    if not res.get("available"):
        print(f"❌ trop peu d'events extrêmes ({res.get('n_events', 0)}).")
        return 1
    sig = res["significant"]
    verdict = "✅ SIGNIFICATIF (cross-actif)" if sig else "❌ NON significatif"
    print(f"\nFunding-study · {res['n_assets']} cryptos · {res['n_events']} events "
          f"· |z|>{a.threshold} · post={a.post}j")
    print(f"  CAR fade moyen  : {res['mean_car']*100:+.2f}%")
    print(f"  t-stat          : {res['t_stat']}")
    print(f"  p-value placebo : {res['placebo_p_value']}")
    print(f"  → {verdict}")
    if sig:
        print("  GO : reversion réelle → backtest net (crypto ≈50bps) + DSR/PBO.")
    else:
        print("  STOP : pas d'edge de reversion → on ne backteste pas.")
    _log(a, res)
    _note(a, res, sorted(series))
    return 0


def _log(a, res: dict) -> None:
    try:
        from packages.research.ledger import append_record
        append_record({
            "date": datetime.now(UTC).date().isoformat(),
            "facteur": "funding_reversion", "classe": ["crypto"], "horizon": "swing",
            "dsr": None, "pbo": res["placebo_p_value"],
            "statut": "en_test" if res["significant"] else "rejete",
            "these": f"Fade funding {res['n_assets']} cryptos (|z|>{a.threshold}) : "
                     f"CAR {res['mean_car']*100:+.2f}%, p={res['placebo_p_value']}.",
        })
    except Exception:  # noqa: BLE001
        pass


def _note(a, res: dict, syms: list[str]) -> None:
    try:
        d = ROOT / "vault" / "09_Events"
        d.mkdir(parents=True, exist_ok=True)
        today = datetime.now(UTC).date().isoformat()
        (d / "_FUNDING_reversion.md").write_text(
            f"---\ntype: event_study_result\nticker: FUNDING\n"
            f"event_type: funding_reversion\nn: {res['n_events']}\n"
            f"n_assets: {res['n_assets']}\nmean_car: {res['mean_car']}\n"
            f"t_stat: {res['t_stat']}\nplacebo_p_value: {res['placebo_p_value']}\n"
            f"significant: {str(res['significant']).lower()}\npost: {a.post}\n"
            f"date: {today}\n---\n\n# 🪙 Funding-study (reversion)\n\n"
            f"{res['n_assets']} cryptos · CAR fade {res['mean_car']*100:+.2f}% · "
            f"t={res['t_stat']} · p={res['placebo_p_value']} → "
            f"{'edge candidat' if res['significant'] else 'mirage'}.\n",
            encoding="utf-8")
        print("  📝 note → vault/09_Events/_FUNDING_reversion.md")
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
