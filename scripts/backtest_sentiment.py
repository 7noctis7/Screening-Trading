"""Backtest du signal sentiment (event-study) : le NLP a-t-il un edge ? (mesurer avant d'investir)

  export QUANT_PRICE_DB=/chemin/YAHOO.db
  python scripts/backtest_sentiment.py            # lit data/news.csv (symbol,date,headline)

Sans data/news.csv → message d'aide (un backtest sentiment HONNÊTE exige des news datées).
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_news(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                d = datetime.fromisoformat(r["date"][:10]).date()
            except Exception:  # noqa: BLE001
                continue
            out.append({"symbol": r.get("symbol", "").strip(),
                        "date": d, "headline": r.get("headline", "")})
    return out


def main() -> None:
    news_path = ROOT / "data" / "news.csv"
    if not news_path.exists():
        print("⛔ data/news.csv introuvable. Un backtest sentiment honnête EXIGE des news datées.")
        print("   Format (cf. data/news.csv.example) : symbol,date,headline")
        print("   Sources gratuites : FinNLP, OpenBB, GDELT, ou un export de tes flux RSS archivés.")
        return

    from apps.api.snapshot import (_HISTORY_DAYS, _load_prices, _seed_universe, _sector_of,
                                   datetime as _dt, timedelta, timezone)
    from packages.sentiment.news_backtest import sentiment_event_study

    inst = _seed_universe()
    so = {m["symbol"]: _sector_of(m) for m in inst}
    end = _dt.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    data, mode = _load_prices(inst, so, end - timedelta(days=_HISTORY_DAYS), end, 7)
    news = _load_news(news_path)
    print(f"Mode données : {mode} · {len(data)} actifs · {len(news)} news\n")

    for hold in (1, 5, 21):
        r = sentiment_event_study(data, news, hold=hold)
        if not r.get("available"):
            print(f"hold {hold:>2}j : {r.get('reason')}"); continue
        print(f"hold {hold:>2}j · {r['n_events']} évén. · IC {r['ic']:+.3f} · "
              f"Sharpe {r['sharpe']:+.2f} · DSR {r['dsr']*100:.0f}% · "
              f"pos {r['mean_fwd_positive']*100:+.2f}% / neg {r['mean_fwd_negative']*100:+.2f}%")
    print(f"\n{sentiment_event_study(data, news, hold=5).get('verdict','')}")
    print("Rappel : DSR≈0 ⇒ pas d'edge sentiment → le NLP doit rester un FILTRE de risque, pas un alpha.")


if __name__ == "__main__":
    main()
