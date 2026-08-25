"""`read_prices_rows` doit lire les DEUX schémas — LONG et NORMALISÉ.

Régression du 24/08 : `make preset-lab` tournait et `make alpha-lab` plantait sur la MÊME
base (YAHOO.db, schéma normalisé), parce que deux détections de schéma coexistaient — celle
de `DBPriceProvider` (tolérante) et celle de `engine._detect_bars_table` (format LONG seul).
"""

import sqlite3

from packages.data.engine import read_prices_rows


def _base_normalisee(path) -> str:
    """Schéma réel de YAHOO.db : barres liées à la méta par un identifiant entier."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE Ticker (id_ticker INTEGER PRIMARY KEY, tx_symbol TEXT)")
    con.execute("CREATE TABLE P_1D (id_ticker INTEGER, dt_price TEXT, nb_open REAL, "
                "nb_high REAL, nb_low REAL, nb_close REAL, nb_volume REAL)")
    con.executemany("INSERT INTO Ticker VALUES (?,?)", [(1, "AAPL"), (2, "MSFT")])
    rows = []
    for i in range(5):
        d = f"2024-01-0{i + 1}"
        rows.append((1, d, 10.0 + i, 11.0 + i, 9.0 + i, 10.5 + i, 1000 + i))
        rows.append((2, d, 20.0 + i, 21.0 + i, 19.0 + i, 20.5 + i, 2000 + i))
    con.executemany("INSERT INTO P_1D VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return str(path)


def _base_longue(path) -> str:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE bars (symbol TEXT, ts TEXT, open REAL, high REAL, "
                "low REAL, close REAL, volume REAL)")
    con.executemany("INSERT INTO bars VALUES (?,?,?,?,?,?,?)",
                    [("AAPL", "2024-01-01", 10.0, 11.0, 9.0, 10.5, 1000.0)])
    con.commit()
    con.close()
    return str(path)


def test_schema_normalise_resout_les_symboles(tmp_path):
    db = _base_normalisee(tmp_path / "yahoo.db")
    rows = read_prices_rows(db)
    assert len(rows) == 10
    assert {r["symbol"] for r in rows} == {"AAPL", "MSFT"}       # l'id est traduit en symbole
    r0 = next(r for r in rows if r["symbol"] == "AAPL" and r["ts"] == "2024-01-01")
    assert r0["close"] == 10.5 and r0["volume"] == 1000.0


def test_schema_normalise_respecte_les_filtres(tmp_path):
    db = _base_normalisee(tmp_path / "yahoo.db")
    assert len(read_prices_rows(db, symbols=["AAPL"])) == 5
    assert len(read_prices_rows(db, start="2024-01-03")) == 6
    assert len(read_prices_rows(db, start="2024-01-02", end="2024-01-03")) == 4


def test_schema_long_inchange(tmp_path):
    rows = read_prices_rows(_base_longue(tmp_path / "long.db"))
    assert len(rows) == 1 and rows[0]["symbol"] == "AAPL"


def test_base_illisible_ne_leve_pas(tmp_path):
    """Une base sans aucune table de barres renvoie [] — elle ne casse plus le labo."""
    p = tmp_path / "vide.db"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE notes (txt TEXT)")
    con.commit()
    con.close()
    assert read_prices_rows(str(p)) == []
