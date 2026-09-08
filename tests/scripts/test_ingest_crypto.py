"""Changer la source d'une série est un geste destructif : il doit être exact.

Le symbole court `ARB-USD` chez Yahoo désigne un autre jeton (mesuré : corrélation +0,04
sur 994 jours). Reprendre la série ailleurs impose d'effacer d'abord ce qui était là —
sinon les jours que la nouvelle source ne couvre pas gardent les prix de l'homonyme, et
la série finale est cousue de deux actifs : pire que l'une ou l'autre, et indétectable.
"""

from __future__ import annotations

import sqlite3

from scripts.ingest_crypto import (
    SOURCE_FORCEE,
    _purger,
    source_de,
    ticker_yahoo,
)

DDL = ("CREATE TABLE prices (symbol TEXT, date TEXT, open REAL, high REAL, low REAL, "
       "close REAL, volume REAL, PRIMARY KEY (symbol, date))")


def _base() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(DDL)
    return conn


def test_le_symbole_de_stockage_ne_depend_pas_de_la_source() -> None:
    """La lecture cherche `ARB-USD` via `_yahoo_aliases`. Une série venue de Binance
    rangée sous un autre nom serait invisible — présente en base, absente à l'écran."""
    assert ticker_yahoo("ARB") == "ARB-USD"
    assert ticker_yahoo("arb") == "ARB-USD"
    assert ticker_yahoo("BTC") == "BTC-USD"


def test_seules_les_bases_mesurees_fausses_changent_de_source() -> None:
    """Une source forcée sans mesure remplacerait une série fausse par une autre."""
    assert source_de("BTC") == "yahoo"
    assert source_de("ETH") == "yahoo"
    for base in ("TON", "UNI", "APT", "ARB", "STX"):
        assert source_de(base) == "binance", base
    assert set(SOURCE_FORCEE) == {"TON", "UNI", "APT", "ARB", "STX"}


def test_la_purge_efface_toute_la_serie_de_l_homonyme() -> None:
    """LE test. Sans purge, les dates que Binance ne couvre pas — l'histoire du jeton
    AVANT son existence, justement celle qui trahissait l'homonyme — resteraient."""
    conn = _base()
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)",
                     [("ARB-USD", f"2018-01-{j:02d}", 1, 1, 1, 1, 1)
                      for j in range(1, 21)])
    conn.commit()

    efface = _purger(conn, "ARB")

    assert efface == 20
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 0


def test_la_purge_ne_touche_pas_les_autres_series() -> None:
    """Contrôle négatif : une purge trop large détruirait des données saines."""
    conn = _base()
    conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?)",
                     [("ARB-USD", "2018-01-01", 1, 1, 1, 1, 1),
                      ("BTC-USD", "2018-01-01", 1, 1, 1, 1, 1),
                      ("ARBUSD", "2018-01-01", 1, 1, 1, 1, 1)])
    conn.commit()

    assert _purger(conn, "ARB") == 1
    restants = {r[0] for r in conn.execute("SELECT symbol FROM prices")}
    assert restants == {"BTC-USD", "ARBUSD"}


def test_purger_une_serie_absente_ne_leve_pas() -> None:
    assert _purger(_base(), "ZZZ") == 0
