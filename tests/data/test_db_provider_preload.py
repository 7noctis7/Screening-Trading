import sqlite3
from datetime import datetime, timezone

from packages.data.providers.db_provider import DBPriceProvider


def _mk_db(path):
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE prices(symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
        "close REAL, volume REAL, PRIMARY KEY(symbol,date));")
    rows = []
    for sym in ("AAPL", "NVDA"):
        for i, d in enumerate(("2026-06-18", "2026-06-19", "2026-06-20")):
            rows.append((sym, d, 10 + i, 11 + i, 9 + i, 10.5 + i, 1000 + i))
    con.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)", rows)
    con.commit(); con.close()


def test_preload_matches_sql(tmp_path):
    db = tmp_path / "market.db"
    _mk_db(db)
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 30, tzinfo=timezone.utc)

    # 1) chemin SQL classique (sans preload)
    p_sql = DBPriceProvider(db)
    sql_bars = p_sql.fetch_ohlcv("AAPL", "1d", start, end)

    # 2) chemin vectorisé (preload) → doit donner EXACTEMENT les mêmes barres
    p_bulk = DBPriceProvider(db)
    assert p_bulk.preload(["AAPL", "NVDA"], "1d", start, end) is True
    bulk_bars = p_bulk.fetch_ohlcv("AAPL", "1d", start, end)

    assert len(sql_bars) == len(bulk_bars) == 3
    assert [b.close for b in sql_bars] == [b.close for b in bulk_bars]
    assert [b.ts for b in sql_bars] == [b.ts for b in bulk_bars]


def test_preload_window_mismatch_falls_back_to_sql(tmp_path):
    db = tmp_path / "market.db"
    _mk_db(db)
    p = DBPriceProvider(db)
    p.preload(["AAPL"], "1d", datetime(2026, 6, 1, tzinfo=timezone.utc),
              datetime(2026, 6, 30, tzinfo=timezone.utc))
    # fenêtre différente → ne sert pas le cache, repli SQL (doit quand même renvoyer les barres)
    got = p.fetch_ohlcv("AAPL", "1d", datetime(2026, 6, 18, tzinfo=timezone.utc),
                        datetime(2026, 6, 19, tzinfo=timezone.utc))
    assert len(got) == 2
