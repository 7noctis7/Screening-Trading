from pathlib import Path

from packages.data.engine import read_prices_rows
from packages.data.hf_cache import parquet_url, write_sqlite


def test_write_sqlite_roundtrip(tmp_path: Path):
    rows = [
        {"symbol": "AAPL", "date": "2026-06-20", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100},
        {"symbol": "AAPL", "ts": "2026-06-21", "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 120},
        {"symbol": "NVDA", "date": "2026-06-21", "open": 9.0, "high": 9.0, "low": 8.0, "close": 8.5, "volume": 50},
    ]
    db = tmp_path / "market.db"
    n = write_sqlite(rows, db)
    assert n == 3
    back = read_prices_rows(db)
    syms = {r["symbol"] for r in back}
    assert syms == {"AAPL", "NVDA"}
    assert len(back) == 3


def test_write_sqlite_idempotent(tmp_path: Path):
    rows = [{"symbol": "AAPL", "date": "2026-06-20", "close": 1.5}]
    db = tmp_path / "m.db"
    write_sqlite(rows, db)
    write_sqlite(rows, db)                      # re-run → pas de doublon (PRIMARY KEY)
    assert len(read_prices_rows(db)) == 1


def test_write_sqlite_into_existing_wider_table(tmp_path: Path):
    import sqlite3
    db = tmp_path / "market.db"
    con = sqlite3.connect(db)                   # table préexistante avec une colonne EN PLUS (adj_close)
    con.executescript(
        "CREATE TABLE prices(symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
        "close REAL, adj_close REAL, volume REAL, PRIMARY KEY(symbol,date));")
    con.commit(); con.close()
    n = write_sqlite([{"symbol": "AAPL", "date": "2026-06-20", "close": 1.5, "volume": 10}], db)
    assert n == 1
    back = read_prices_rows(db)
    assert back and back[0]["symbol"] == "AAPL"


def test_parquet_url_uses_dataset():
    url = parquet_url("market", "Noctis777/screening-trading-cache")
    assert url == ("https://huggingface.co/datasets/Noctis777/screening-trading-cache"
                   "/resolve/main/market.parquet")
