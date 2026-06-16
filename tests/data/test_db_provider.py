import sqlite3
from datetime import datetime, timezone

from packages.data.providers.db_provider import DBPriceProvider


def _make_db(path, fmt="long"):
    c = sqlite3.connect(path)
    if fmt == "long":
        c.execute("CREATE TABLE prices(symbol TEXT,date TEXT,open REAL,high REAL,low REAL,close REAL,volume REAL)")
        for i in range(300):
            d = f"2023-{(i//28)%12+1:02d}-{i%28+1:02d}"
            c.execute("INSERT INTO prices VALUES(?,?,?,?,?,?,?)", ("AAPL", d, 100, 101, 99, 100 + i * 0.1, 1e6))
    else:  # une table par ticker
        c.execute('CREATE TABLE "AAPL"(date TEXT, close REAL)')
        for i in range(300):
            d = f"2023-{(i//28)%12+1:02d}-{i%28+1:02d}"
            c.execute('INSERT INTO "AAPL" VALUES(?,?)', (d, 100 + i * 0.1))
    c.commit(); c.close()


def test_db_provider_long_format(tmp_path):
    p = tmp_path / "y.db"; _make_db(p, "long")
    prov = DBPriceProvider(p)
    assert prov.schema.startswith("long")
    assert prov.supports("AAPL") and not prov.supports("ZZZZ")
    bars = prov.fetch_ohlcv("AAPL", "1d", datetime(2023, 1, 1, tzinfo=timezone.utc),
                            datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert len(bars) == 300 and bars[0].close == 100 and bars[-1].close > bars[0].close


def test_db_provider_per_ticker_format(tmp_path):
    p = tmp_path / "y.db"; _make_db(p, "per")
    prov = DBPriceProvider(p)
    bars = prov.fetch_ohlcv("AAPL", "1d", datetime(2023, 1, 1, tzinfo=timezone.utc),
                            datetime(2024, 1, 1, tzinfo=timezone.utc))
    assert len(bars) == 300 and bars[0].close == 100      # OHLC déduit du close si absent
