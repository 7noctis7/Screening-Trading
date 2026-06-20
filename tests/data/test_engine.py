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


def test_ledoit_wolf_shrinks_toward_target():
    import numpy as np
    rng = np.random.default_rng(1)
    X = rng.normal(0, 0.01, (8, 12))                         # n≈T → covariance empirique instable
    sigma, delta = E.ledoit_wolf_shrinkage(X)
    assert 0.0 <= delta <= 1.0 and delta > 0.0               # régularisation active
    assert sigma.shape == (8, 8)
    assert np.allclose(sigma, sigma.T)                       # symétrique
    assert (np.linalg.eigvalsh(sigma) > -1e-9).all()        # PSD (mieux conditionnée)


def test_covariance_shrink_flag_changes_result():
    import numpy as np
    rng = np.random.default_rng(2)
    rets = {f"S{i}": list(rng.normal(0, 0.01, 15)) for i in range(8)}
    _, cov_raw = E.covariance_matrix(rets, shrink=False, cache=False)
    _, cov_lw = E.covariance_matrix(rets, shrink=True, cache=False)
    assert not np.allclose(cov_raw, cov_lw)                  # le shrinkage modifie bien la matrice


def test_covariance_cache_returns_identical_object():
    import numpy as np
    rng = np.random.default_rng(3)
    rets = {"A": list(rng.normal(0, 0.01, 30)), "B": list(rng.normal(0, 0.02, 30))}
    a = E.covariance_matrix(rets, cache=True)
    b = E.covariance_matrix(rets, cache=True)
    assert a[1] is b[1]                                      # même objet → servi depuis le cache
