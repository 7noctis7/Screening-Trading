"""Moteur de lecture vectorisé — repli SQLite + covariance pure (numpy)."""
import sqlite3
import pytest
from packages.data import engine as E


def _make_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE bars (symbol TEXT, ts TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL)")
    rows = [("AAPL", f"2026-01-{d:02d}", 10, 11, 9, 10 + d, 100) for d in range(1, 11)]
    rows += [("MU", f"2026-01-{d:02d}", 5, 6, 4, 5 + d, 50) for d in range(1, 11)]
    con.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?)", rows)
    con.commit(); con.close()


def test_read_prices_rows_fallback(tmp_path):
    db = tmp_path / "market.db"; _make_db(str(db))
    rows = E.read_prices_rows(db, symbols=["AAPL"])
    assert rows and all(r["symbol"] == "AAPL" for r in rows)
    assert {"symbol", "ts", "open", "high", "low", "close", "volume"} <= set(rows[0])


def test_read_prices_rows_missing_db(tmp_path):
    assert E.read_prices_rows(tmp_path / "nope.db") == []


def test_covariance_matrix_shape_and_symmetry():
    import numpy as np
    rng = np.random.default_rng(0)
    rets = {"A": list(rng.normal(0, 0.01, 200)), "B": list(rng.normal(0, 0.02, 200))}
    syms, cov = E.covariance_matrix(rets)
    assert syms == ["A", "B"] and cov.shape == (2, 2)
    assert abs(cov[0, 1] - cov[1, 0]) < 1e-12               # symétrique
    assert cov[1, 1] > cov[0, 0]                            # B plus volatile


def test_available_keys():
    a = E.available()
    assert {"duckdb", "polars", "numpy"} <= set(a)
